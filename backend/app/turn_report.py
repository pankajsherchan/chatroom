"""Capture one chat turn and write a reviewable HTML report."""

from __future__ import annotations

import html
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.settings import Settings, get_settings


SECRET_FIELD_MARKERS = (
    "password",
    "api_key",
    "apikey",
    "authorization",
    "secret",
    "token",
)
MAX_REPORTED_STRING_LENGTH = 4000


@dataclass
class TurnTrace:
    """Mutable collector filled while a supervisor turn runs."""

    meta: dict[str, Any] = field(default_factory=dict)
    steps: list[dict[str, Any]] = field(default_factory=list)

    def add(self, stage: str, title: str, **data: Any) -> None:
        self.steps.append(
            {
                "stage": stage,
                "title": title,
                "data": _json_safe(data),
            }
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "meta": _json_safe(self.meta),
            "steps": list(self.steps),
        }


def turn_reports_enabled(settings: Settings | None = None) -> bool:
    settings = settings or get_settings()
    return settings.turn_reports_enabled


def turn_reports_dir(settings: Settings | None = None) -> Path:
    settings = settings or get_settings()
    return settings.turn_reports_dir


def write_turn_report(
    trace: TurnTrace | Mapping[str, Any] | None,
    *,
    conversation_id: str | None = None,
    request_id: str | None = None,
    provider_id: str | None = None,
    model_name: str | None = None,
    final_answer: str | None = None,
    selected_agent_ids: Sequence[str] | None = None,
    request_context: Mapping[str, Any] | None = None,
    settings: Settings | None = None,
) -> Path | None:
    """Write an HTML (+ JSON) report for one chat turn. Returns the HTML path."""

    settings = settings or get_settings()
    if not turn_reports_enabled(settings) or trace is None:
        return None

    payload = trace.to_dict() if isinstance(trace, TurnTrace) else dict(trace)
    meta = dict(payload.get("meta") or {})
    steps = list(payload.get("steps") or [])
    if conversation_id:
        meta["conversation_id"] = conversation_id
    if request_id:
        meta["request_id"] = request_id
    if provider_id:
        meta["provider_id"] = provider_id
    if model_name:
        meta["model_name"] = model_name
    if selected_agent_ids is not None:
        meta["selected_agent_ids"] = list(selected_agent_ids)
    if final_answer is not None:
        meta["final_answer"] = final_answer
    meta.setdefault("generated_at", datetime.now(timezone.utc).isoformat())

    if request_context is not None and not any(
        step.get("stage") == "request_intake" for step in steps
    ):
        steps.insert(
            0,
            {
                "stage": "request_intake",
                "title": "UI → API request intake",
                "data": _json_safe(dict(request_context)),
            },
        )

    payload["meta"] = _json_safe(meta)
    payload["steps"] = _json_safe(steps)

    reports_dir = turn_reports_dir(settings)
    reports_dir.mkdir(parents=True, exist_ok=True)

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    slug = _slug(str(meta.get("user_input") or "turn"))[:48]
    cid = (conversation_id or "unknown")[:12]
    base_name = f"{stamp}_{cid}_{slug}"
    html_path = reports_dir / f"{base_name}.html"
    json_path = reports_dir / f"{base_name}.json"

    json_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=True, default=str),
        encoding="utf-8",
    )
    html_path.write_text(render_turn_report_html(payload), encoding="utf-8")
    return html_path


def render_turn_report_html(payload: Mapping[str, Any]) -> str:
    meta = payload.get("meta") or {}
    steps = payload.get("steps") or []
    user_input = str(meta.get("user_input") or "(no prompt)")
    final_answer = str(meta.get("final_answer") or "")
    checklist = _checklist_html(payload)

    step_cards = []
    for index, step in enumerate(steps, start=1):
        stage = str(step.get("stage") or f"step_{index}")
        title = html.escape(str(step.get("title") or stage))
        data = step.get("data") or {}
        narrative = _stage_narrative_html(stage, data, meta)
        messages_block = _llm_messages_html(stage, data)
        step_cards.append(
            f"""
            <section class="card" id="step-{index}">
              <div class="card-head">
                <span class="badge">{index}. {html.escape(stage)}</span>
                <h2>{title}</h2>
              </div>
              {narrative}
              {messages_block}
            </section>
            """
        )

    flow_nodes = " → ".join(
        html.escape(str(step.get("stage") or "?")) for step in steps
    ) or "(no steps captured)"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Turn report — {html.escape(user_input[:80])}</title>
  <style>
    :root {{
      --bg: #0f1419;
      --panel: #1a222c;
      --text: #e7ecf1;
      --muted: #9aa7b5;
      --accent: #6cb6ff;
      --ok: #3dd68c;
      --warn: #f5a524;
      --border: #2c3642;
      --mono: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      --sans: "IBM Plex Sans", "Segoe UI", sans-serif;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: var(--sans);
      background: radial-gradient(1200px 600px at 10% -10%, #1b2a3a, var(--bg));
      color: var(--text);
      line-height: 1.45;
    }}
    header, main {{ max-width: 1100px; margin: 0 auto; padding: 1.25rem; }}
    header {{
      border-bottom: 1px solid var(--border);
      margin-bottom: 1rem;
    }}
    h1 {{ font-size: 1.35rem; margin: 0 0 0.5rem; }}
    .prompt {{
      font-size: 1.1rem;
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 0.9rem 1rem;
      white-space: pre-wrap;
    }}
    .meta {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 0.6rem;
      margin: 1rem 0;
    }}
    .meta div {{
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 0.65rem 0.75rem;
    }}
    .meta dt {{ color: var(--muted); font-size: 0.75rem; text-transform: uppercase; }}
    .meta dd {{ margin: 0.2rem 0 0; font-family: var(--mono); font-size: 0.85rem; word-break: break-all; }}
    .flow {{
      background: #122033;
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 0.85rem 1rem;
      font-family: var(--mono);
      font-size: 0.85rem;
      color: var(--accent);
      overflow-x: auto;
      white-space: nowrap;
      margin: 1rem 0;
    }}
    .checklist {{
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 0.85rem 1rem;
      margin: 1rem 0 1.5rem;
    }}
    .checklist li {{ margin: 0.25rem 0; }}
    .ok {{ color: var(--ok); }}
    .miss {{ color: var(--warn); }}
    .card {{
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 1rem;
      margin: 0 0 1rem;
    }}
    .card-head {{ display: flex; flex-direction: column; gap: 0.35rem; margin-bottom: 0.6rem; }}
    .card h2 {{ margin: 0; font-size: 1.05rem; }}
    .badge {{
      align-self: flex-start;
      background: #243246;
      color: var(--accent);
      border-radius: 999px;
      padding: 0.15rem 0.6rem;
      font-size: 0.75rem;
      font-family: var(--mono);
    }}
    pre {{
      margin: 0;
      padding: 0.85rem;
      background: #0c1117;
      border-radius: 8px;
      overflow: auto;
      font-family: var(--mono);
      font-size: 0.78rem;
      max-height: 420px;
    }}
    .answer {{
      white-space: pre-wrap;
      background: #0c1117;
      border-radius: 8px;
      padding: 0.85rem;
      border: 1px solid var(--border);
    }}
    .breakdown {{
      list-style: none;
      padding: 0;
      margin: 0 0 0.85rem;
      display: flex;
      flex-direction: column;
      gap: 0.65rem;
    }}
    .breakdown li {{
      background: #121922;
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 0.75rem 0.9rem;
    }}
    .breakdown .label {{
      color: var(--accent);
      font-size: 0.78rem;
      font-family: var(--mono);
      text-transform: uppercase;
      letter-spacing: 0.03em;
      margin-bottom: 0.3rem;
    }}
    .breakdown .detail {{
      white-space: pre-wrap;
      font-size: 0.95rem;
    }}
    .breakdown .code {{
      margin-top: 0.45rem;
      padding: 0.65rem;
      background: #0c1117;
      border-radius: 8px;
      font-family: var(--mono);
      font-size: 0.78rem;
      overflow: auto;
      white-space: pre-wrap;
      max-height: 240px;
    }}
    details.raw {{
      margin-top: 0.35rem;
      color: var(--muted);
    }}
    details.raw summary {{
      cursor: pointer;
      margin-bottom: 0.4rem;
    }}
    footer {{
      max-width: 1100px;
      margin: 0 auto 2rem;
      padding: 0 1.25rem;
      color: var(--muted);
      font-size: 0.85rem;
    }}
  </style>
</head>
<body>
  <header>
    <h1>ChatRoom — Turn Report</h1>
    <div class="prompt"><strong>User prompt</strong><br />{html.escape(user_input)}</div>
    <div class="meta">
      {_meta_item("Conversation", meta.get("conversation_id"))}
      {_meta_item("Request", meta.get("request_id"))}
      {_meta_item("Provider", meta.get("provider_id"))}
      {_meta_item("Model", meta.get("model_name"))}
      {_meta_item("Generated (UTC)", meta.get("generated_at"))}
      {_meta_item("Team agents", ", ".join(meta.get("selected_agent_ids") or []))}
    </div>
    <div class="flow">Flow: {flow_nodes}</div>
    <div class="checklist">
      <strong>Quick checks</strong>
      <ul>{checklist}</ul>
    </div>
  </header>
  <main>
    {"".join(step_cards)}
    <section class="card">
      <div class="card-head">
        <span class="badge">final</span>
        <h2>Answer shown in UI</h2>
      </div>
      <div class="answer">{html.escape(final_answer) if final_answer else "(empty)"}</div>
    </section>
  </main>
  <footer>
    Auto-generated after each chat turn. JSON sibling file has the same payload for tooling.
    Enable with <code>TURN_REPORTS_ENABLED=1</code>.
  </footer>
</body>
</html>
"""


def _meta_item(label: str, value: Any) -> str:
    text = "—" if value in (None, "") else str(value)
    return (
        f"<div><dt>{html.escape(label)}</dt>"
        f"<dd>{html.escape(text)}</dd></div>"
    )


def _stage_narrative_html(
    stage: str,
    data: Mapping[str, Any],
    meta: Mapping[str, Any],
) -> str:
    if stage == "request_intake":
        items = _request_intake_breakdown(data)
    elif stage == "manager":
        items = _manager_breakdown(data, meta)
    elif stage == "specialist_tool_loop":
        items = _specialist_breakdown(data)
    elif stage == "tool_execution":
        items = _tool_execution_breakdown(data)
    elif stage == "follow_ups":
        items = _follow_ups_breakdown(data)
    elif stage == "final_answer":
        items = _final_answer_breakdown(data)
    else:
        return ""
    return f'<ol class="breakdown">{"".join(items)}</ol>'


def _llm_messages_html(stage: str, data: Mapping[str, Any]) -> str:
    """Show JSON only for the message list actually sent to the LLM."""

    if stage not in {"manager", "specialist_tool_loop", "final_answer"}:
        return ""

    messages = data.get("messages")
    if not isinstance(messages, list) or not messages:
        # Fall back to reconstructed manager messages when only split fields exist.
        if stage == "manager":
            messages = []
            system = data.get("manager_system_message")
            user = data.get("manager_user_message")
            if isinstance(system, str) and system:
                messages.append({"role": "system", "content": system})
            if isinstance(user, str) and user:
                messages.append({"role": "user", "content": user})
        if not messages:
            return ""

    payload: dict[str, Any] = {"messages": messages}
    tools = data.get("tool_specs")
    if isinstance(tools, list) and tools:
        payload["tools"] = tools

    return (
        '<details class="raw" open>'
        "<summary>Messages sent to the LLM (JSON)</summary>"
        f"<pre>{html.escape(json.dumps(payload, indent=2, ensure_ascii=True, default=str))}</pre>"
        "</details>"
    )


def _breakdown_item(label: str, detail: str, code: str | None = None) -> str:
    code_html = (
        f'<div class="code">{html.escape(code)}</div>' if code is not None else ""
    )
    return (
        "<li>"
        f'<div class="label">{html.escape(label)}</div>'
        f'<div class="detail">{html.escape(detail)}</div>'
        f"{code_html}"
        "</li>"
    )


def _request_intake_breakdown(data: Mapping[str, Any]) -> list[str]:
    method = str(data.get("http_method") or "POST")
    endpoint = str(data.get("api_endpoint") or "/conversations/{{id}}/messages/stream")
    body = data.get("request_body") or {}
    content = ""
    if isinstance(body, Mapping):
        content = str(body.get("content") or "")
    runtime = data.get("runtime") if isinstance(data.get("runtime"), Mapping) else {}
    persisted = (
        data.get("persisted_before_supervisor")
        if isinstance(data.get("persisted_before_supervisor"), Mapping)
        else {}
    )
    return [
        _breakdown_item(
            "1. From the UI",
            str(
                data.get("ui_action")
                or "User typed a message in the chat composer and pressed send."
            ),
            content or None,
        ),
        _breakdown_item(
            "2. API endpoint called",
            f"Browser/frontend calls {method} {endpoint}",
            f"{method} {endpoint}\nBody content: {content or '(empty)'}",
        ),
        _breakdown_item(
            "3. Backend prep before supervisor",
            (
                "FastAPI handler loads the conversation, appends the user message to SQLite, "
                "loads history, creates the model provider, then starts ProviderSupervisor."
            ),
            (
                f"prior_messages={persisted.get('prior_messages_before_this_turn', '—')}; "
                f"provider={runtime.get('provider_id', '—')}; "
                f"model={runtime.get('model_name', '—')}"
            ),
        ),
    ]


def _manager_breakdown(
    data: Mapping[str, Any],
    meta: Mapping[str, Any],
) -> list[str]:
    received = (
        data.get("received_from_ui")
        if isinstance(data.get("received_from_ui"), Mapping)
        else {}
    )
    decision = data.get("decision") if isinstance(data.get("decision"), Mapping) else {}
    provider_call = (
        data.get("provider_call")
        if isinstance(data.get("provider_call"), Mapping)
        else {}
    )
    available = data.get("available_specialists") or []
    available_lines = []
    if isinstance(available, list):
        for item in available:
            if not isinstance(item, Mapping):
                continue
            tools = item.get("tools") or []
            available_lines.append(
                f"- {item.get('id')}: {item.get('name')} "
                f"(tools={', '.join(str(tool) for tool in tools) or 'none'})"
            )
    chosen = decision.get("chosen_agent_ids") or []
    return [
        _breakdown_item(
            "1. What this step is",
            str(
                data.get("what_this_step_does")
                or (
                    "Manager routing: the model picks specialist agent ids. "
                    "No tools run here."
                )
            ),
        ),
        _breakdown_item(
            "2. What arrived from the UI / API",
            (
                f"User prompt: {received.get('user_prompt') or meta.get('user_input') or '(unknown)'}\n"
                f"Team agent ids on the conversation: "
                f"{', '.join(str(item) for item in (received.get('conversation_team_agent_ids') or meta.get('selected_agent_ids') or [])) or '(none)'}\n"
                f"Messages already in the supervisor request: "
                f"{received.get('prior_messages_in_request', '—')}"
            ),
        ),
        _breakdown_item(
            "3. Specialists the manager was allowed to choose",
            "Built from the agent catalog for this conversation.",
            "\n".join(available_lines) if available_lines else "(none listed)",
        ),
        _breakdown_item(
            "4. Provider call",
            str(
                provider_call.get("method")
                or "provider.generate(messages, tools=())"
            ),
            "No tool schemas are passed for manager routing.",
        ),
        _breakdown_item(
            "5. Raw model response",
            "Exact text returned by the provider for routing.",
            str(data.get("raw_provider_content") or "(empty)"),
        ),
        _breakdown_item(
            "6. Decision",
            str(decision.get("fallback_meaning") or "Parsed agent ids from the model."),
            f"chosen_agent_ids={chosen}; fallback={decision.get('used_keyword_routing_fallback')}",
        ),
    ]


def _specialist_breakdown(data: Mapping[str, Any]) -> list[str]:
    tool_calls = data.get("tool_calls") or []
    call_summary = json.dumps(tool_calls, indent=2, ensure_ascii=True, default=str)
    return [
        _breakdown_item(
            "1. Specialist",
            f"agent_id={data.get('agent_id')}; name={data.get('agent_name')}",
        ),
        _breakdown_item(
            "2. Provider call",
            "provider.generate(messages, tools=tool_specs) so the model can emit tool calls.",
        ),
        _breakdown_item(
            "3. Tool calls returned by the model",
            "These arguments are what the specialist wants to run next.",
            call_summary if tool_calls else "(no tool calls)",
        ),
        _breakdown_item(
            "4. Raw provider text (if any)",
            str(data.get("raw_provider_content") or "(empty)"),
        ),
    ]


def _tool_execution_breakdown(data: Mapping[str, Any]) -> list[str]:
    runs = data.get("runs")
    if isinstance(runs, list) and runs:
        return [
            _breakdown_item(
                "Heuristic / fallback tool runs",
                "Tools that ran without a provider tool-call (or were skipped).",
                json.dumps(runs, indent=2, ensure_ascii=True, default=str),
            )
        ]
    return [
        _breakdown_item(
            "1. Tool",
            f"{data.get('tool_name')} — status={data.get('status')}",
        ),
        _breakdown_item(
            "2. Arguments (as received)",
            "Includes argument types from the provider.",
            json.dumps(
                {
                    "arguments": data.get("arguments"),
                    "argument_types": data.get("argument_types"),
                    "source": data.get("source"),
                    "error": data.get("error"),
                },
                indent=2,
                ensure_ascii=True,
                default=str,
            ),
        ),
        _breakdown_item(
            "3. Output / summary",
            str(data.get("summary") or "(see output JSON)"),
            json.dumps(data.get("output"), indent=2, ensure_ascii=True, default=str)
            if data.get("output") is not None
            else None,
        ),
    ]


def _follow_ups_breakdown(data: Mapping[str, Any]) -> list[str]:
    return [
        _breakdown_item(
            "Supervisor follow-ups",
            f"Agents: {', '.join(str(item) for item in (data.get('follow_up_agent_ids') or [])) or '(none)'}",
            json.dumps(
                data.get("follow_up_tool_outputs") or [],
                indent=2,
                ensure_ascii=True,
                default=str,
            ),
        )
    ]


def _final_answer_breakdown(data: Mapping[str, Any]) -> list[str]:
    return [
        _breakdown_item(
            "1. What this step is",
            "Ask the model to write the user-facing answer from tool evidence.",
        ),
        _breakdown_item(
            "2. Evidence used",
            "Readable summaries + structured tool outputs.",
            json.dumps(
                {
                    "readable_evidence": data.get("readable_evidence"),
                    "evidence_payload": data.get("evidence_payload"),
                },
                indent=2,
                ensure_ascii=True,
                default=str,
            ),
        ),
        _breakdown_item(
            "3. Model vs fallback",
            (
                "Used model answer."
                if data.get("used_model_answer")
                else "Fell back to deterministic summary from tool outputs."
            ),
            str(data.get("raw_provider_content") or "(empty)"),
        ),
    ]


def _checklist_html(payload: Mapping[str, Any]) -> str:
    steps = payload.get("steps") or []
    stages = {str(step.get("stage")) for step in steps}
    tool_names: list[str] = []
    for step in steps:
        if step.get("stage") != "tool_execution":
            continue
        data = step.get("data") or {}
        name = data.get("tool_name")
        if isinstance(name, str):
            tool_names.append(name)

    checks = [
        ("manager", "Manager routing step recorded", "manager" in stages),
        (
            "specialist",
            "At least one specialist tool-call step",
            "specialist_tool_loop" in stages,
        ),
        (
            "tool",
            "Tool execution recorded",
            "tool_execution" in stages or bool(tool_names),
        ),
        ("final", "Final answer synthesis recorded", "final_answer" in stages),
        (
            "snowflake",
            "query_snowflake ran (when relevant)",
            "query_snowflake" in tool_names or "query_snowflake" not in str(payload),
        ),
    ]

    # Soften snowflake check: only warn if prompt looks sales-related and tool missing.
    meta = payload.get("meta") or {}
    prompt = str(meta.get("user_input") or "").casefold()
    sales_like = any(
        word in prompt for word in ("revenue", "region", "pipeline", "deal", "snowflake")
    )
    if sales_like:
        checks[4] = (
            "snowflake",
            "query_snowflake ran",
            "query_snowflake" in tool_names,
        )
    else:
        checks = checks[:4]

    items = []
    for _key, label, ok in checks:
        css = "ok" if ok else "miss"
        mark = "PASS" if ok else "CHECK"
        items.append(f'<li class="{css}">[{mark}] {html.escape(label)}</li>')
    return "".join(items)


def _slug(text: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "-", text.strip().casefold()).strip("-")
    return cleaned or "turn"


def _json_safe(value: Any, *, field_name: str | None = None) -> Any:
    if field_name and _looks_like_secret_field(field_name):
        return "[REDACTED]"
    if value is None or isinstance(value, (int, float, bool)):
        return value
    if isinstance(value, str):
        if len(value) > MAX_REPORTED_STRING_LENGTH:
            return value[:MAX_REPORTED_STRING_LENGTH] + "…[truncated]"
        return value
    if isinstance(value, Mapping):
        return {
            str(key): _json_safe(item, field_name=str(key))
            for key, item in value.items()
        }
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_json_safe(item) for item in value]
    if hasattr(value, "role") and hasattr(value, "content"):
        return {
            "role": getattr(value, "role", None),
            "content": _json_safe(getattr(value, "content", None), field_name="content"),
            "agent_name": getattr(value, "agent_name", None),
        }
    if hasattr(value, "name") and hasattr(value, "arguments"):
        arguments = dict(getattr(value, "arguments", {}) or {})
        return {
            "name": getattr(value, "name", None),
            "arguments": _json_safe(arguments),
            "argument_types": {
                key: type(item).__name__ for key, item in arguments.items()
            },
        }
    return str(value)


def _looks_like_secret_field(field_name: str) -> bool:
    lowered = field_name.casefold().replace("-", "_")
    return any(marker in lowered for marker in SECRET_FIELD_MARKERS)
