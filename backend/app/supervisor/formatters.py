"""Domain-specific tool output formatters for specialist results."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from tools import SUMMARIZE_FINDINGS_TOOL
from tools.lookup_account import LOOKUP_ACCOUNT_TOOL
from tools.snowflake_query import QUERY_SNOWFLAKE_TOOL


def _custom_tool_summary(tool_name: str, output: Mapping[str, Any]) -> str | None:
    if tool_name == LOOKUP_ACCOUNT_TOOL.name:
        return _lookup_account_content(output)
    if tool_name == QUERY_SNOWFLAKE_TOOL.name:
        return _snowflake_query_content(output)
    if tool_name.startswith("query_dataset_"):
        return _dataset_query_content(output)
    if tool_name == SUMMARIZE_FINDINGS_TOOL.name:
        bullets = output.get("bullets")
        if isinstance(bullets, list) and bullets:
            return "\n".join(str(bullet) for bullet in bullets)
    return None


def _dataset_query_content(output: Mapping[str, Any]) -> str:
    row_count = output.get("row_count", 0)
    filters = output.get("filters") or {}
    group_by = output.get("group_by")
    lines = [f"Matched {row_count} rows from the knowledge base."]

    if isinstance(filters, Mapping) and filters:
        filter_text = ", ".join(f"{key}={value}" for key, value in filters.items())
        lines.append(f"Filters: {filter_text}.")
    if group_by:
        lines.append(f"Grouped by {group_by}.")

    averages = [
        f"{key.removeprefix('average_')}={value}"
        for key, value in output.items()
        if isinstance(key, str) and key.startswith("average_") and _is_plain_number(value)
    ]
    preferred = [item for item in averages if item.startswith("gpa=")]
    other = [item for item in averages if not item.startswith("gpa=")]
    shown_averages = (preferred + other)[:6]
    if shown_averages:
        lines.append(f"Averages: {', '.join(shown_averages)}.")

    groups = output.get("groups")
    if isinstance(groups, list) and groups:
        lines.append(f"Returned {len(groups)} groups:")
        for group in groups[:8]:
            if not isinstance(group, Mapping):
                continue
            parts = [f"{key}={value}" for key, value in group.items()]
            lines.append(f"- {', '.join(parts)}")
        if len(groups) > 8:
            lines.append(f"... and {len(groups) - 8} more groups.")
        return "\n".join(lines)

    rows = output.get("rows")
    if not isinstance(rows, list) or not rows:
        return "\n".join(lines)

    highlight = _dataset_row_highlights(rows)
    if highlight is not None:
        lines.append(highlight)

    lines.append(f"Sample rows ({min(len(rows), 8)} of {len(rows)} returned):")
    for row in rows[:8]:
        if not isinstance(row, Mapping):
            continue
        lines.append(f"- {_format_dataset_row(row)}")
    if len(rows) > 8:
        lines.append(f"... and {len(rows) - 8} more rows.")
    return "\n".join(lines)

def _is_plain_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _format_dataset_row(row: Mapping[str, Any]) -> str:
    preferred_keys = (
        "student_name",
        "name",
        "student_id",
        "gpa",
        "grade_level",
        "homeroom",
        "math",
        "english",
        "science",
    )
    ordered: list[str] = []
    seen: set[str] = set()
    for key in preferred_keys:
        if key in row:
            ordered.append(f"{key}={row[key]}")
            seen.add(key)
    for key, value in row.items():
        if key in seen:
            continue
        ordered.append(f"{key}={value}")
        if len(ordered) >= 8:
            break
    return ", ".join(ordered)


def _dataset_row_highlights(rows: Sequence[Mapping[str, Any]]) -> str | None:
    numeric_rows = [row for row in rows if isinstance(row, Mapping)]
    if not numeric_rows:
        return None

    # Prefer an explicit GPA highlight when the column exists.
    if any("gpa" in row for row in numeric_rows):
        scores = [
            (float(row["gpa"]), row)
            for row in numeric_rows
            if _is_plain_number(row.get("gpa"))
        ]
        if not scores:
            return None
        best = max(score for score, _ in scores)
        winners = [
            _row_display_name(row)
            for score, row in scores
            if score == best
        ]
        return f"Highest gpa among returned rows: {best} ({', '.join(winners)})."
    return None


def _row_display_name(row: Mapping[str, Any]) -> str:
    for key in ("student_name", "name"):
        value = row.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    student_id = row.get("student_id")
    if isinstance(student_id, str) and student_id.strip():
        return student_id.strip()
    return "unknown"


def _lookup_account_content(output: Mapping[str, Any]) -> str:
    accounts = output.get("accounts")
    if isinstance(accounts, list):
        lines = [f"Found {output.get('row_count', len(accounts))} accounts:"]
        for account in accounts:
            if not isinstance(account, Mapping):
                continue
            account_id = account.get("account_id", "unknown")
            name = account.get("name", "Unknown account")
            segment = account.get("segment", "unknown segment")
            status = account.get("status", "unknown status")
            lines.append(
                f"- {account_id}: {name} ({segment}, status={status})"
            )
        return "\n".join(lines)

    account_id = output.get("account_id", "unknown")
    name = output.get("name", "Unknown account")
    segment = output.get("segment", "unknown segment")
    status = output.get("status", "unknown status")
    return (
        f"Account {account_id} is {name} "
        f"({segment}, status={status})."
    )


def _snowflake_query_content(output: Mapping[str, Any]) -> str:
    rows = output.get("rows", [])
    columns = output.get("columns", [])
    row_count = output.get("row_count", 0)

    if not isinstance(rows, list) or not rows:
        return f"Query returned {row_count} rows."

    if row_count == 1 and isinstance(rows[0], Mapping):
        deal = rows[0]
        deal_id = deal.get("deal_id")
        if deal_id:
            product_line = deal.get("product_line", "Unknown product")
            region = deal.get("region", "unknown region")
            stage = deal.get("stage", "unknown stage")
            revenue = deal.get("revenue", "unknown revenue")
            owner = deal.get("owner", "unknown owner")
            return (
                f"Deal {deal_id}: {product_line} in {region} "
                f"({stage}, revenue={revenue}, owner={owner})."
            )

    lines = [f"Returned {row_count} rows:"]
    for row in rows[:5]:
        if not isinstance(row, Mapping):
            continue
        if isinstance(columns, list) and columns:
            parts = [f"{column}={row.get(column)}" for column in columns]
        else:
            parts = [f"{key}={value}" for key, value in row.items()]
        lines.append(f"- {', '.join(parts)}")
    if len(rows) > 5:
        lines.append(f"... and {len(rows) - 5} more rows.")
    return "\n".join(lines)
