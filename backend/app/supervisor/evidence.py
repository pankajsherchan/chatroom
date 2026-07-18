"""Final-answer synthesis and evidence packaging."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Any

from app.models.supervisor import AgentRunResult, SupervisorRequest
from app.providers import ModelMessage, ModelProvider
from app.supervisor.formatters import _custom_tool_summary, _is_plain_number
from app.turn_report import TurnTrace
from tools import BUILD_CHART_SPEC_TOOL


def _artifacts_from_agent_results(
    agent_results: Sequence[AgentRunResult],
) -> tuple[Mapping[str, Any], ...]:
    artifacts: list[Mapping[str, Any]] = []
    for result in agent_results:
        for tool_output in result.tool_outputs:
            if tool_output.get("tool_name") == BUILD_CHART_SPEC_TOOL.name:
                output = tool_output.get("output")
                if isinstance(output, Mapping):
                    artifacts.append(
                        {
                            "type": "chart",
                            "agent_id": result.agent_id,
                            "spec": output,
                        }
                    )
    return tuple(artifacts)


def _synthesize_final_answer(
    provider: ModelProvider,
    request: SupervisorRequest,
    agent_results: Sequence[AgentRunResult],
    *,
    trace: TurnTrace | None = None,
) -> str:
    """Ask the model to answer from tool evidence; fall back to deterministic text."""

    if not agent_results:
        return "No specialist agents were selected."

    messages = _final_answer_messages(request, agent_results)
    evidence = _evidence_payload(agent_results)
    readable = _readable_tool_summaries(agent_results)
    response = provider.generate(messages)
    text = (response.content or "").strip()
    used_model_answer = bool(
        text
        and not _looks_like_manager_json(text)
        and not _looks_like_evidence_refusal(text)
    )
    final_text = text if used_model_answer else _synthesize_agent_results(agent_results)
    if trace is not None:
        trace.add(
            "final_answer",
            "Final answer synthesis",
            messages=messages,
            readable_evidence=readable,
            evidence_payload=evidence,
            raw_provider_content=response.content,
            used_model_answer=used_model_answer,
            used_deterministic_fallback=not used_model_answer,
            final_text=final_text,
        )
    return final_text


def _final_answer_messages(
    request: SupervisorRequest,
    agent_results: Sequence[AgentRunResult],
) -> tuple[ModelMessage, ...]:
    evidence = _evidence_payload(agent_results)
    evidence_json = json.dumps(evidence, ensure_ascii=True, default=str)
    readable = _readable_tool_summaries(agent_results)
    readable_block = "\n\n".join(readable) if readable else "(no readable tool summaries)"
    user_prompt = (
        "Answer the user's question using the evidence below.\n"
        "The readable evidence and JSON are the same source of truth.\n"
        "Compute answers from the rows that are present "
        "(for example, find the max GPA in the returned rows).\n"
        "Do not mention JSON, incompleteness, or missing fields unless a required "
        "value is truly absent from every row.\n\n"
        f"User question: {request.user_input}\n\n"
        f"Readable evidence:\n{readable_block}\n\n"
        f"Raw tool evidence (JSON):\n{evidence_json}"
    )
    return (
        ModelMessage(
            role="system",
            content=(
                "You are the local group chat supervisor. "
                "Write the final answer for the user. "
                "Use only facts present in the tool evidence. "
                "Do not invent rows, numbers, or names. "
                "Be concise and directly answer the question. "
                "Never say the question or JSON is incomplete when rows are present."
            ),
            agent_name="supervisor",
        ),
        ModelMessage(role="user", content=user_prompt, agent_name="supervisor"),
    )


def _looks_like_evidence_refusal(text: str) -> bool:
    lowered = text.casefold()
    refusal_markers = (
        "json data",
        "incomplete",
        "does not provide the full",
        "full json",
        "evidence is incomplete",
        "missing the full",
    )
    return any(marker in lowered for marker in refusal_markers)


def _evidence_payload(agent_results: Sequence[AgentRunResult]) -> list[dict[str, Any]]:
    payload: list[dict[str, Any]] = []
    for result in agent_results:
        tool_outputs: list[dict[str, Any]] = []
        for tool_output in result.tool_outputs:
            output = tool_output.get("output")
            tool_outputs.append(
                {
                    "tool_name": tool_output.get("tool_name"),
                    "arguments": tool_output.get("arguments"),
                    "output": _truncate_evidence_output(output),
                }
            )
        entry: dict[str, Any] = {
            "agent_id": result.agent_id,
            "tool_outputs": tool_outputs,
        }
        if not tool_outputs:
            entry["notes"] = result.content
        payload.append(entry)
    return payload


def _truncate_evidence_output(output: Any) -> Any:
    if not isinstance(output, Mapping):
        return output

    trimmed = dict(output)
    for key in ("rows", "groups", "accounts"):
        value = trimmed.get(key)
        if isinstance(value, list) and len(value) > 25:
            trimmed[key] = value[:25]
            trimmed[f"{key}_truncated"] = True

    rows = trimmed.get("rows")
    if isinstance(rows, list) and rows and isinstance(rows[0], Mapping) and "gpa" in rows[0]:
        trimmed["rows"] = sorted(
            [row for row in rows if isinstance(row, Mapping)],
            key=lambda row: float(row["gpa"]) if _is_plain_number(row.get("gpa")) else float("-inf"),
            reverse=True,
        )
    return trimmed


def _looks_like_manager_json(text: str) -> bool:
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return False
    return isinstance(parsed, Mapping) and "agent_ids" in parsed


def _synthesize_agent_results(agent_results: Sequence[AgentRunResult]) -> str:
    if not agent_results:
        return "No specialist agents were selected."

    tool_summaries = _readable_tool_summaries(agent_results)
    if tool_summaries:
        return "\n".join(tool_summaries)

    agent_names = ", ".join(result.agent_id for result in agent_results)
    lines = [f"Supervisor synthesized results from: {agent_names}."]
    lines.extend(f"- {_format_agent_content(result.content)}" for result in agent_results)

    artifact_summaries = _artifact_summaries(agent_results)
    if artifact_summaries:
        lines.append("Artifacts:")
        lines.extend(f"- {summary}" for summary in artifact_summaries)

    return "\n".join(lines)


def _readable_tool_summaries(agent_results: Sequence[AgentRunResult]) -> list[str]:
    summaries: list[str] = []
    for result in agent_results:
        for tool_output in result.tool_outputs:
            tool_name = str(tool_output.get("tool_name", ""))
            output = tool_output.get("output")
            if not isinstance(output, Mapping):
                continue
            summary = _custom_tool_summary(tool_name, output)
            if summary is not None:
                summaries.append(summary)
    return summaries


def _format_agent_content(content: str) -> str:
    return content.replace("\n", "\n  ")


def _artifact_summaries(agent_results: Sequence[AgentRunResult]) -> tuple[str, ...]:
    summaries: list[str] = []
    for result in agent_results:
        for tool_output in result.tool_outputs:
            if tool_output.get("tool_name") != BUILD_CHART_SPEC_TOOL.name:
                continue
            output = tool_output.get("output")
            if isinstance(output, Mapping):
                title = output.get("title", "Untitled chart")
                chart_type = output.get("chart_type", "chart")
                summaries.append(f"{chart_type} chart: {title}")
    return tuple(summaries)
