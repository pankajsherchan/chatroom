"""Built-in agents backed by backend-configured connector tools."""

from __future__ import annotations

from app.agents import LocalAgent
from app.connectors.external_api import external_api_is_configured
from app.connectors.snowflake import snowflake_is_configured
from app.settings import Settings, get_settings


CONNECTOR_SALES_PIPELINE_ID = "connector_sales_pipeline"
CONNECTOR_ACCOUNT_DIRECTORY_ID = "connector_account_directory"


def is_connector_agent_id(agent_id: str) -> bool:
    return agent_id.startswith("connector_")


def list_connector_agents(settings: Settings | None = None) -> list[LocalAgent]:
    settings = settings or get_settings()
    agents: list[LocalAgent] = []

    if snowflake_is_configured(settings):
        agents.append(
            LocalAgent(
                id=CONNECTOR_SALES_PIPELINE_ID,
                name="Sales pipeline",
                description="Query deal stages, regions, and revenue.",
                system_prompt=(
                ''' You answer sales pipeline questions using the query_snowflake tool.
                    Always call query_snowflake with a read-only SELECT.
                    Table: pipeline_deals
                    Columns: deal_id, close_month, region, segment, product_line, stage, owner, revenue, probability_pct
                    Prefer aggregation for "by region" style questions. Limit to 10 rows unless asked for more.'''
                ),
                tools=("query_snowflake",),
            )
        )

    if external_api_is_configured(settings):
        agents.append(
            LocalAgent(
                id=CONNECTOR_ACCOUNT_DIRECTORY_ID,
                name="Account directory",
                description="Look up customer accounts, segments, and status.",
                system_prompt=(
                    "You answer questions about customer accounts. "
                    "Always call the lookup_account tool. "
                    "Pass account_id when the user mentions a specific id like AC-1001. "
                    "Omit account_id to list all configured accounts."
                ),
                tools=("lookup_account",),
            )
        )

    return agents


def list_connector_agent_ids(settings: Settings | None = None) -> list[str]:
    return [agent.id for agent in list_connector_agents(settings)]


def get_connector_agent(agent_id: str, settings: Settings | None = None) -> LocalAgent | None:
    for agent in list_connector_agents(settings):
        if agent.id == agent_id:
            return agent
    return None
