"""Specialist tool execution via provider calls and heuristic defaults."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from app.agents import LocalAgent
from app.models.supervisor import AgentHandoffRequest, AgentRunResult
from app.providers import ModelMessage, ModelProvider
from app.supervisor.defaults import default_arguments_for_tool
from app.supervisor.findings import (
    _chart_arguments,
    _latest_findings,
    _latest_grouped_findings,
)
from app.supervisor.formatters import _custom_tool_summary
from app.tool_registry import list_tool_specs, run_registered_tool
from app.turn_report import TurnTrace
from tools import BUILD_CHART_SPEC_TOOL, SUMMARIZE_FINDINGS_TOOL
from tools.lookup_account import LOOKUP_ACCOUNT_TOOL
from tools.snowflake_query import QUERY_SNOWFLAKE_TOOL


def _run_custom_agent(
    agent: LocalAgent,
    handoff_request: AgentHandoffRequest,
    agent_results: Sequence[AgentRunResult],
    *,
    provider: ModelProvider | None = None,
    trace: TurnTrace | None = None,
) -> AgentRunResult:
    tool_outputs: list[Mapping[str, Any]] = []
    lines = [f"{agent.name} applied its local prompt to: {handoff_request.original_user_input}"]
    tools_run_via_provider: set[str] = set()

    # Step 4: ask the model for tool calls (SQL args) when a provider is available.
    if provider is not None and agent.tools:
        tools_run_via_provider = _run_provider_tool_calls(
            provider=provider,
            agent=agent,
            handoff_request=handoff_request,
            tool_outputs=tool_outputs,
            lines=lines,
            trace=trace,
        )

    # Heuristic fallback for tools the model did not call (datasets only).
    # query_snowflake and lookup_account require provider-generated arguments.
    heuristic_runs: list[dict[str, Any]] = []
    for tool_name in agent.tools:
        if tool_name in tools_run_via_provider:
            continue
        arguments = _arguments_for_custom_tool(
            tool_name,
            handoff_request,
            agent_results,
        )
        if arguments is None:
            lines.append(f"Skipped {tool_name} because no safe default arguments were available.")
            heuristic_runs.append(
                {
                    "tool_name": tool_name,
                    "status": "skipped",
                    "reason": "no safe default arguments",
                }
            )
            continue
        try:
            output = run_registered_tool(tool_name, arguments)
            tool_outputs.append(
                {
                    "tool_name": tool_name,
                    "arguments": arguments,
                    "output": output,
                }
            )
            lines.append(f"Ran {tool_name}.")
            summary = _custom_tool_summary(tool_name, output)
            if summary is not None:
                lines.append(summary)
            heuristic_runs.append(
                {
                    "tool_name": tool_name,
                    "status": "ran",
                    "arguments": arguments,
                    "output": output,
                    "source": "heuristic_fallback",
                }
            )
        except ValueError as error:
            lines.append(f"Tool {tool_name} failed: {error}")
            heuristic_runs.append(
                {
                    "tool_name": tool_name,
                    "status": "failed",
                    "error": str(error),
                    "source": "heuristic_fallback",
                }
            )

    if heuristic_runs and trace is not None:
        trace.add(
            "tool_execution",
            f"Heuristic tool path for {agent.id}",
            agent_id=agent.id,
            runs=heuristic_runs,
        )

    if not agent.tools:
        lines.append(agent.system_prompt)

    return AgentRunResult(
        agent_id=agent.id,
        content="\n".join(lines),
        handoff_request=handoff_request,
        tool_outputs=tuple(tool_outputs),
    )


def _specialist_tool_messages(
    agent: LocalAgent,
    handoff_request: AgentHandoffRequest,
) -> tuple[ModelMessage, ...]:
    return (
        ModelMessage(
            role="system",
            content=agent.system_prompt,
            agent_name=agent.name,
        ),
        ModelMessage(
            role="user",
            content=handoff_request.specific_request,
            agent_name=agent.name,
        ),
    )


def _run_provider_tool_calls(
    *,
    provider: ModelProvider,
    agent: LocalAgent,
    handoff_request: AgentHandoffRequest,
    tool_outputs: list[Mapping[str, Any]],
    lines: list[str],
    trace: TurnTrace | None = None,
) -> set[str]:
    """Ask the provider to choose tools/args; run only allowed tool calls."""

    messages = _specialist_tool_messages(agent, handoff_request)
    try:
        specs = list_tool_specs(agent.tools)
    except ValueError as error:
        lines.append(f"Could not load tool schemas: {error}")
        if trace is not None:
            trace.add(
                "specialist_tool_loop",
                f"Specialist {agent.id} failed to load tool schemas",
                agent_id=agent.id,
                error=str(error),
            )
        return set()

    response = provider.generate(messages, tools=specs)
    if trace is not None:
        trace.add(
            "specialist_tool_loop",
            f"Specialist {agent.id} asked model for tool calls",
            agent_id=agent.id,
            agent_name=agent.name,
            system_prompt=agent.system_prompt,
            messages=messages,
            tool_specs=specs,
            raw_provider_content=response.content,
            tool_calls=list(response.tool_calls),
        )

    if not response.tool_calls:
        return set()

    allowed = set(agent.tools)
    ran: set[str] = set()
    for tool_call in response.tool_calls:
        if tool_call.name not in allowed:
            lines.append(f"Skipped unauthorized tool call: {tool_call.name}.")
            if trace is not None:
                trace.add(
                    "tool_execution",
                    f"Rejected unauthorized tool {tool_call.name}",
                    agent_id=agent.id,
                    tool_name=tool_call.name,
                    status="rejected",
                    arguments=dict(tool_call.arguments),
                )
            continue
        arguments = dict(tool_call.arguments)
        try:
            output = run_registered_tool(tool_call.name, arguments)
            tool_outputs.append(
                {
                    "tool_name": tool_call.name,
                    "arguments": arguments,
                    "output": output,
                }
            )
            lines.append(f"Ran {tool_call.name}.")
            summary = _custom_tool_summary(tool_call.name, output)
            if summary is not None:
                lines.append(summary)
            ran.add(tool_call.name)
            if trace is not None:
                trace.add(
                    "tool_execution",
                    f"Ran {tool_call.name}",
                    agent_id=agent.id,
                    tool_name=tool_call.name,
                    status="ok",
                    arguments=arguments,
                    argument_types={
                        key: type(value).__name__ for key, value in arguments.items()
                    },
                    output=output,
                    summary=summary,
                    source="provider_tool_call",
                )
        except ValueError as error:
            lines.append(f"Tool {tool_call.name} failed: {error}")
            if trace is not None:
                trace.add(
                    "tool_execution",
                    f"Tool {tool_call.name} failed",
                    agent_id=agent.id,
                    tool_name=tool_call.name,
                    status="failed",
                    arguments=arguments,
                    argument_types={
                        key: type(value).__name__ for key, value in arguments.items()
                    },
                    error=str(error),
                    source="provider_tool_call",
                )
    return ran

def _arguments_for_custom_tool(
    tool_name: str,
    handoff_request: AgentHandoffRequest,
    agent_results: Sequence[AgentRunResult],
) -> dict[str, Any] | None:
    if tool_name == SUMMARIZE_FINDINGS_TOOL.name:
        findings = _latest_findings(agent_results)
        if not findings:
            return None
        return {"findings": findings, "max_bullets": 4}

    if tool_name == BUILD_CHART_SPEC_TOOL.name:
        findings = _latest_grouped_findings(agent_results)
        if not findings:
            return None
        return _chart_arguments(findings, handoff_request.original_user_input)

    defaults = default_arguments_for_tool(tool_name)
    if defaults is not None:
        return defaults

    # query_snowflake / lookup_account require model-generated tool arguments.
    if tool_name in {QUERY_SNOWFLAKE_TOOL.name, LOOKUP_ACCOUNT_TOOL.name}:
        return None

    return {}
