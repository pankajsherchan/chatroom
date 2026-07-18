"""Supervisor keyword-triggered summarize/chart follow-ups."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from app.models.supervisor import AgentHandoffRequest, AgentRunResult, SupervisorRequest
from app.routing import prompt_wants_summarize, prompt_wants_visualize
from app.supervisor.findings import (
    _chart_arguments,
    _findings_for_summarize,
    _latest_chart_findings,
    _summary_content,
)
from app.supervisor.handoff import _handoff_request
from tools import BUILD_CHART_SPEC_TOOL, SUMMARIZE_FINDINGS_TOOL


def _run_supervisor_follow_ups(
    request: SupervisorRequest,
    agent_results: list[AgentRunResult],
) -> list[AgentRunResult]:
    if not agent_results:
        return []

    follow_ups: list[AgentRunResult] = []
    prompt = request.user_input

    if prompt_wants_summarize(prompt):
        handoff_request = _handoff_request(request, "summarizer", agent_results)
        follow_ups.append(_run_summarizer(handoff_request, agent_results))

    working_results = [*agent_results, *follow_ups]
    if prompt_wants_visualize(prompt):
        handoff_request = _handoff_request(request, "visualizer", working_results)
        chart_findings = _latest_chart_findings(working_results)
        if not chart_findings:
            follow_ups.append(
                AgentRunResult(
                    agent_id="visualizer",
                    content=(
                        "Visualizer skipped because no chartable findings "
                        "were available."
                    ),
                    handoff_request=handoff_request,
                )
            )
        else:
            try:
                follow_ups.append(
                    _run_visualizer(handoff_request, working_results, chart_findings)
                )
            except ValueError as error:
                follow_ups.append(
                    AgentRunResult(
                        agent_id="visualizer",
                        content=f"Visualizer failed: {error}",
                        handoff_request=handoff_request,
                    )
                )

    return follow_ups


def _run_summarizer(
    handoff_request: AgentHandoffRequest,
    agent_results: Sequence[AgentRunResult],
) -> AgentRunResult:
    findings = _findings_for_summarize(agent_results)
    arguments = {
        "findings": findings,
        "max_bullets": 4,
    }
    output = SUMMARIZE_FINDINGS_TOOL.run(arguments)
    tool_output = {
        "tool_name": SUMMARIZE_FINDINGS_TOOL.name,
        "arguments": arguments,
        "output": output,
    }
    return AgentRunResult(
        agent_id="summarizer",
        content=_summary_content(output),
        handoff_request=handoff_request,
        tool_outputs=(tool_output,),
    )

def _run_visualizer(
    handoff_request: AgentHandoffRequest,
    agent_results: Sequence[AgentRunResult],
    findings: Mapping[str, Any] | None = None,
) -> AgentRunResult:
    chart_findings = findings or _latest_chart_findings(agent_results)
    arguments = _chart_arguments(chart_findings, handoff_request.original_user_input)
    output = BUILD_CHART_SPEC_TOOL.run(arguments)
    tool_output = {
        "tool_name": BUILD_CHART_SPEC_TOOL.name,
        "arguments": arguments,
        "output": output,
    }
    return AgentRunResult(
        agent_id="visualizer",
        content=f"Visualizer built {output['chart_type']} chart: {output['title']}.",
        handoff_request=handoff_request,
        tool_outputs=(tool_output,),
    )
