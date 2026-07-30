"""
Seed a working demo: workflows, workflow-backed tools, and a voice agent.

Creates an end-to-end setup for testing voice -> intent -> tool -> workflow ->
third-party API -> spoken answer, using only free, keyless APIs:

  * open-meteo geocoding + forecast  (weather)
  * coingecko simple price           (crypto)

Run from the backend directory:

    ./venv/bin/python -m scripts.seed_demo_agent            # create/update
    ./venv/bin/python -m scripts.seed_demo_agent --clean    # remove the demo

Existing demo rows are matched by name and updated, so re-running is safe.
"""
import argparse
import asyncio
import logging
import sys
import uuid
from typing import Any, Dict, List, Optional

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.agent import Agent
from app.models.integration import Workflow
from app.models.tool import Tool, AgentToolAssignment
from app.models.user import OrganizationMember, User

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("seed")

DEMO_TAG = "[demo]"


# ---------------------------------------------------------------------------
# Graph helpers
# ---------------------------------------------------------------------------


def node(nid: str, ntype: str, name: str, y: int, config: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": nid,
        "type": ntype,
        "name": name,
        "position": {"x": 340, "y": y},
        "config": config,
        "settings": {},
    }


def edge(src: str, tgt: str, handle: str = "out") -> Dict[str, Any]:
    return {
        "id": f"e_{src}_{handle}_{tgt}",
        "source": src,
        "sourceHandle": handle,
        "target": tgt,
        "targetHandle": "in",
    }


# ---------------------------------------------------------------------------
# Workflow 1 — Weather
# ---------------------------------------------------------------------------
# trigger(city) -> geocode -> forecast -> branch(hot?) -> set fields
#
# Two chained API calls prove data flows between nodes: the forecast node reads
# latitude/longitude out of the geocode node's response.

WEATHER_GRAPH = {
    "schema_version": 2,
    "nodes": [
        node("trigger", "trigger", "When called by the agent", 40, {
            "inputs": [
                {
                    "name": "city",
                    "type": "string",
                    "description": "The city to get the weather for, e.g. Tokyo",
                    "required": True,
                }
            ]
        }),
        node("geocode", "webhook", "Look up the city", 210, {
            "url": "https://geocoding-api.open-meteo.com/v1/search"
                   "?name={{trigger.city}}&count=1",
            "method": "GET",
            "timeout": 15,
        }),
        node("forecast", "webhook", "Fetch the forecast", 380, {
            "url": "https://api.open-meteo.com/v1/forecast"
                   "?latitude={{steps.geocode.body.results[0].latitude}}"
                   "&longitude={{steps.geocode.body.results[0].longitude}}"
                   "&current=temperature_2m,wind_speed_10m",
            "method": "GET",
            "timeout": 15,
        }),
        node("is_hot", "condition", "Is it hot?", 550, {
            "variable": "steps.forecast.body.current.temperature_2m",
            "operator": "greater_than",
            "value": "25",
        }),
        node("hot", "transform", "Hot advice", 720, {
            "transformations": {
                "location": "{{steps.geocode.body.results[0].name}}",
                "temperature_c": "{{steps.forecast.body.current.temperature_2m}}",
                "advice": "It's warm — stay hydrated and wear something light.",
            }
        }),
        node("mild", "transform", "Mild advice", 720, {
            "transformations": {
                "location": "{{steps.geocode.body.results[0].name}}",
                "temperature_c": "{{steps.forecast.body.current.temperature_2m}}",
                "advice": "It's on the cooler side — a jacket would be sensible.",
            }
        }),
    ],
    "edges": [
        edge("trigger", "geocode"),
        edge("geocode", "forecast"),
        edge("forecast", "is_hot"),
        edge("is_hot", "hot", "true"),
        edge("is_hot", "mild", "false"),
    ],
}

# Nudge the two branch nodes apart so the canvas is readable.
for _n in WEATHER_GRAPH["nodes"]:
    if _n["id"] == "hot":
        _n["position"]["x"] = 120
    if _n["id"] == "mild":
        _n["position"]["x"] = 560


# ---------------------------------------------------------------------------
# Workflow 2 — Crypto price
# ---------------------------------------------------------------------------

CRYPTO_GRAPH = {
    "schema_version": 2,
    "nodes": [
        node("trigger", "trigger", "When called by the agent", 40, {
            "inputs": [
                {
                    "name": "coin",
                    "type": "string",
                    "description": (
                        "CoinGecko coin id, lowercase. Examples: bitcoin, "
                        "ethereum, dogecoin, solana, cardano."
                    ),
                    "required": True,
                }
            ]
        }),
        # /coins/markets returns an array with fixed field names. The simpler
        # /simple/price keys its response by the coin id, which would need
        # nested interpolation — {{steps.price.body.{{trigger.coin}}.usd}} —
        # and the {{...}} pattern does not nest.
        node("price", "webhook", "Fetch the price", 210, {
            "url": "https://api.coingecko.com/api/v3/coins/markets"
                   "?vs_currency=usd&ids={{trigger.coin}}",
            "method": "GET",
            "timeout": 15,
        }),
        node("shape", "transform", "Build the answer", 380, {
            "transformations": {
                "coin_name": "{{steps.price.body[0].name}}",
                "price_usd": "{{steps.price.body[0].current_price}}",
                "change_24h_percent": "{{steps.price.body[0].price_change_percentage_24h}}",
            }
        }),
    ],
    "edges": [edge("trigger", "price"), edge("price", "shape")],
}


# ---------------------------------------------------------------------------
# Agent system prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
You are Aria, a friendly voice assistant for Voicecon. You are speaking with \
someone on a phone call, so everything you say is heard, never read.

## How to speak
- Keep replies to one or two short sentences. Long answers do not work on a call.
- Use plain spoken language. No bullet points, markdown, emoji, or symbols.
- Say numbers the way a person would: "twenty two degrees", "sixty five \
thousand dollars", not "22C" or "$65,000".
- Never read out raw data, JSON, field names, or URLs.

## Using your tools
You can look things up using the tools available to you. Follow these rules:

1. When the caller asks for something a tool covers, call that tool. Do not \
guess or answer from memory — live data changes.
2. Work out the parameters from what the caller said. If they say "what's the \
weather in Tokyo", the city is Tokyo.
3. If a required detail is missing, ask one short question to get it, then call \
the tool. Do not invent a value.
4. Call one tool at a time and wait for the result.
5. For cryptocurrency, convert the spoken name to the coin id: "bitcoin" is \
bitcoin, "ethereum" or "ether" is ethereum, "doge" is dogecoin.

## After a tool runs
- Answer using the data the tool returned, in your own words.
- If the tool reports an error, apologise briefly and offer to try again or \
help another way. Never invent a result.
- If the caller asks something no tool covers, just answer normally and be \
honest about what you cannot do.

## Tone
Warm, brief, and natural. You are a helpful person on the phone, not a search \
engine reading out a page.
"""

FIRST_MESSAGE = (
    "Hi, this is Aria. I can check the weather or a crypto price for you. "
    "What would you like to know?"
)


# ---------------------------------------------------------------------------
# Seeding
# ---------------------------------------------------------------------------


async def _resolve_owner(db, email: Optional[str]) -> tuple:
    """
    Resolve which account owns the demo rows.

    The email is required. Picking an arbitrary account seeded the demo under
    a different user, so nothing showed up in the dashboard — the rows existed
    but every list endpoint filters by the logged-in user.

    Args:
        db: Database session
        email: The account to seed into

    Returns:
        (user_id, organization_id)
    """
    users = (await db.execute(select(User))).scalars().all()

    if not email:
        logger.error("Pass --email to say which account to seed into.\n")
        logger.error("Available accounts:")
        for user in users:
            logger.error(f"  {user.email}")
        sys.exit(1)

    user = next((u for u in users if u.email.lower() == email.lower()), None)
    if not user:
        logger.error(f"No account found for {email!r}. Available accounts:")
        for candidate in users:
            logger.error(f"  {candidate.email}")
        sys.exit(1)

    membership = (
        await db.execute(
            select(OrganizationMember)
            .where(OrganizationMember.user_id == user.id)
            .limit(1)
        )
    ).scalar_one_or_none()

    if not membership:
        logger.error(f"{email} has no organization membership.")
        sys.exit(1)

    logger.info(f"Seeding into {user.email}  (org {membership.organization_id})")
    return user.id, membership.organization_id


async def _upsert_workflow(db, owner, name, description, graph) -> Workflow:
    user_id, org_id = owner
    full_name = f"{DEMO_TAG} {name}"

    workflow = (
        await db.execute(select(Workflow).where(Workflow.name == full_name))
    ).scalar_one_or_none()

    if workflow is None:
        workflow = Workflow(
            user_id=user_id,
            organization_id=org_id,
            name=full_name,
            trigger_type="manual",
            trigger_config={},
            workflow_steps=graph,
            is_active=True,
            error_handling="stop",
            max_retries=1,
            retry_delay=2,
        )
        db.add(workflow)
        logger.info(f"  created workflow  {full_name}")
    else:
        workflow.workflow_steps = graph
        # A workflow-backed tool cannot run an inactive workflow.
        workflow.is_active = True
        workflow.version += 1
        logger.info(f"  updated workflow  {full_name}")

    workflow.description = description
    await db.commit()
    await db.refresh(workflow)
    return workflow


async def _upsert_tool(db, owner, name, description, workflow_id, filler) -> Tool:
    user_id, org_id = owner
    full_name = f"{DEMO_TAG} {name}"

    tool = (
        await db.execute(select(Tool).where(Tool.name == full_name))
    ).scalar_one_or_none()

    config = {"workflow_id": str(workflow_id), "filler_message": filler}

    if tool is None:
        tool = Tool(
            id=uuid.uuid4(),
            user_id=user_id,
            organization_id=org_id,
            name=full_name,
            description=description,
            category="assistant",
            tool_type="workflow",
            config=config,
            is_active=True,
        )
        db.add(tool)
        logger.info(f"  created tool      {full_name}")
    else:
        tool.config = config
        tool.description = description
        tool.is_active = True
        logger.info(f"  updated tool      {full_name}")

    await db.commit()
    await db.refresh(tool)
    return tool


async def _upsert_agent(db, owner) -> Agent:
    user_id, org_id = owner
    name = f"{DEMO_TAG} Aria"

    agent = (
        await db.execute(select(Agent).where(Agent.name == name))
    ).scalar_one_or_none()

    if agent is None:
        agent = Agent(user_id=user_id, organization_id=org_id, name=name)
        db.add(agent)
        logger.info(f"  created agent     {name}")
    else:
        logger.info(f"  updated agent     {name}")

    agent.description = "Demo agent for testing voice -> tool -> workflow"
    agent.system_prompt = SYSTEM_PROMPT
    agent.first_message = FIRST_MESSAGE
    # Tool calling is only wired for OpenAI today.
    agent.llm_provider = "openai"
    agent.llm_model = "gpt-4o-mini"
    agent.is_active = True

    await db.commit()
    await db.refresh(agent)
    return agent


async def _assign(db, agent_id, tool_id) -> None:
    existing = (
        await db.execute(
            select(AgentToolAssignment).where(
                AgentToolAssignment.agent_id == agent_id,
                AgentToolAssignment.tool_id == tool_id,
            )
        )
    ).scalar_one_or_none()

    if existing is None:
        db.add(AgentToolAssignment(agent_id=agent_id, tool_id=tool_id))
        await db.commit()


async def seed(email: Optional[str]) -> None:
    async with AsyncSessionLocal() as db:
        owner = await _resolve_owner(db, email)

        logger.info("Seeding demo…")

        weather = await _upsert_workflow(
            db, owner, "Get weather",
            "Looks up the current weather for a city using open-meteo.",
            WEATHER_GRAPH,
        )
        crypto = await _upsert_workflow(
            db, owner, "Get crypto price",
            "Looks up a cryptocurrency price in USD using CoinGecko.",
            CRYPTO_GRAPH,
        )

        weather_tool = await _upsert_tool(
            db, owner, "Get weather",
            "Get the current weather and temperature for a city. Use this "
            "whenever the caller asks about weather, temperature, or what it is "
            "like outside somewhere.",
            weather.id,
            "Let me check the weather for you.",
        )
        crypto_tool = await _upsert_tool(
            db, owner, "Get crypto price",
            "Get the current US dollar price of a cryptocurrency. Use this "
            "whenever the caller asks about the price or value of a coin such "
            "as bitcoin, ethereum, or dogecoin.",
            crypto.id,
            "Let me look up that price.",
        )

        agent = await _upsert_agent(db, owner)
        await _assign(db, agent.id, weather_tool.id)
        await _assign(db, agent.id, crypto_tool.id)

        logger.info("")
        logger.info("Done.")
        logger.info(f"  Agent      {agent.id}")
        logger.info(f"  Weather    workflow {weather.id}  tool {weather_tool.id}")
        logger.info(f"  Crypto     workflow {crypto.id}  tool {crypto_tool.id}")
        logger.info("")
        logger.info(f"  Test it:   /dashboard/agents/{agent.id}/test")


async def clean(email: Optional[str]) -> None:
    async with AsyncSessionLocal() as db:
        # Scope the delete to one account: an unqualified name match would
        # remove demo rows belonging to other users.
        user_id, _ = await _resolve_owner(db, email)

        for model, label in ((Tool, "tool"), (Workflow, "workflow"), (Agent, "agent")):
            rows = (
                await db.execute(
                    select(model).where(
                        model.name.like(f"{DEMO_TAG}%"),
                        model.user_id == user_id,
                    )
                )
            ).scalars().all()
            for row in rows:
                await db.delete(row)
                logger.info(f"  deleted {label:9} {row.name}")
        await db.commit()
        logger.info("Demo removed.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--clean", action="store_true", help="remove the demo rows")
    parser.add_argument(
        "--email",
        help="account to seed into (required; run without it to list accounts)",
    )
    args = parser.parse_args()

    asyncio.run(clean(args.email) if args.clean else seed(args.email))
