"""Optional external API account lookup tool."""

from app.connectors.external_api import list_accounts, lookup_account
from tools.base import LocalTool, ParameterSchema, ToolArguments, ToolOutput


LOOKUP_ACCOUNT_PARAMETER_SCHEMA: ParameterSchema = {
    "type": "object",
    "properties": {
        "account_id": {
            "type": "string",
            "description": (
                "Business account id, e.g. AC-1001. "
                "Omit to return all configured accounts."
            ),
        },
    },
}


def run_lookup_account(arguments: ToolArguments) -> ToolOutput:
    account_id = arguments.get("account_id")
    if account_id is None or account_id == "":
        return list_accounts()
    if not isinstance(account_id, str):
        raise ValueError("account_id must be a string when provided.")
    return lookup_account(account_id)


LOOKUP_ACCOUNT_TOOL = LocalTool(
    name="lookup_account",
    description=(
        "Look up one business account by id, or list all accounts when "
        "account_id is omitted."
    ),
    parameter_schema=LOOKUP_ACCOUNT_PARAMETER_SCHEMA,
    run=run_lookup_account,
)
