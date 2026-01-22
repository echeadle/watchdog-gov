"""AI Agent using Anthropic Claude with tool-use for data retrieval."""

import json
from typing import Optional

import anthropic
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import Conversation, Message
from app.services.congress_api import congress_client
from app.services.fec_api import fec_client
from app.services.news_api import news_client

settings = get_settings()

SYSTEM_PROMPT = """You are WatchdogGov Assistant, an AI that helps citizens learn about their elected representatives in the US Congress.

You have access to tools to search for legislators, get their bills, votes, news, and campaign finance information.

When answering questions:
1. Use the available tools to fetch current data
2. Provide factual, nonpartisan information
3. Cite specific bills, votes, or financial data when relevant
4. If you cannot find information, say so clearly

Be helpful, accurate, and transparent about the sources of your information."""

TOOLS = [
    {
        "name": "search_legislators",
        "description": "Search for members of Congress by name or state. Returns a list of matching legislators with their basic information.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Name to search for (e.g., 'Warren', 'Schumer')"
                },
                "state": {
                    "type": "string",
                    "description": "Two-letter state code (e.g., 'MA', 'NY')"
                }
            }
        }
    },
    {
        "name": "get_legislator_details",
        "description": "Get detailed information about a specific legislator including their bio, contact info, and current role.",
        "input_schema": {
            "type": "object",
            "properties": {
                "bioguide_id": {
                    "type": "string",
                    "description": "The unique Bioguide ID of the legislator"
                }
            },
            "required": ["bioguide_id"]
        }
    },
    {
        "name": "get_legislator_bills",
        "description": "Get bills sponsored or cosponsored by a legislator.",
        "input_schema": {
            "type": "object",
            "properties": {
                "bioguide_id": {
                    "type": "string",
                    "description": "The unique Bioguide ID of the legislator"
                },
                "include_cosponsored": {
                    "type": "boolean",
                    "description": "Whether to include cosponsored bills (default: false)"
                }
            },
            "required": ["bioguide_id"]
        }
    },
    {
        "name": "get_legislator_news",
        "description": "Get recent news articles mentioning a legislator.",
        "input_schema": {
            "type": "object",
            "properties": {
                "bioguide_id": {
                    "type": "string",
                    "description": "The unique Bioguide ID of the legislator"
                }
            },
            "required": ["bioguide_id"]
        }
    },
    {
        "name": "get_campaign_finance",
        "description": "Get campaign finance summary for a legislator including receipts, disbursements, and contribution sources.",
        "input_schema": {
            "type": "object",
            "properties": {
                "bioguide_id": {
                    "type": "string",
                    "description": "The unique Bioguide ID of the legislator"
                }
            },
            "required": ["bioguide_id"]
        }
    }
]


class AIAgent:
    """AI Agent for answering questions about legislators."""

    def __init__(self):
        self.client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        self.model = "claude-sonnet-4-20250514"

    async def process_message(
        self, db: AsyncSession, conversation_id: int, user_message: str
    ) -> str:
        """Process a user message and return the assistant's response."""
        messages = await self._get_conversation_messages(db, conversation_id)

        messages.append({"role": "user", "content": user_message})

        user_msg = Message(
            conversation_id=conversation_id,
            role="user",
            content=user_message,
        )
        db.add(user_msg)
        await db.commit()

        response = await self._get_response(db, messages)

        assistant_msg = Message(
            conversation_id=conversation_id,
            role="assistant",
            content=response,
        )
        db.add(assistant_msg)
        await db.commit()

        return response

    async def _get_response(
        self, db: AsyncSession, messages: list[dict]
    ) -> str:
        """Get response from Claude, handling tool calls."""
        if not settings.anthropic_api_key:
            return "AI chat is not configured. Please set the ANTHROPIC_API_KEY environment variable."

        response = self.client.messages.create(
            model=self.model,
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=messages,
        )

        while response.stop_reason == "tool_use":
            tool_results = []

            for content in response.content:
                if content.type == "tool_use":
                    result = await self._execute_tool(db, content.name, content.input)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": content.id,
                        "content": json.dumps(result),
                    })

            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user", "content": tool_results})

            response = self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                system=SYSTEM_PROMPT,
                tools=TOOLS,
                messages=messages,
            )

        final_text = ""
        for content in response.content:
            if hasattr(content, "text"):
                final_text += content.text

        return final_text

    async def _execute_tool(
        self, db: AsyncSession, tool_name: str, tool_input: dict
    ) -> dict:
        """Execute a tool and return the result."""
        try:
            if tool_name == "search_legislators":
                results = await congress_client.search_members(
                    db,
                    query=tool_input.get("query"),
                    state=tool_input.get("state"),
                )
                return {
                    "legislators": [
                        {
                            "bioguide_id": m.get("bioguideId"),
                            "name": m.get("name"),
                            "party": m.get("partyName"),
                            "state": m.get("state"),
                            "chamber": m.get("terms", {}).get("item", [{}])[-1].get("chamber")
                            if m.get("terms") else None,
                        }
                        for m in results[:10]
                    ]
                }

            elif tool_name == "get_legislator_details":
                member = await congress_client.get_member(
                    db, tool_input["bioguide_id"]
                )
                if not member:
                    return {"error": "Legislator not found"}
                return {
                    "bioguide_id": member.get("bioguideId"),
                    "name": member.get("directOrderName"),
                    "party": member.get("partyHistory", [{}])[-1].get("partyName")
                    if member.get("partyHistory") else None,
                    "state": member.get("terms", [{}])[-1].get("stateCode")
                    if member.get("terms") else None,
                    "chamber": member.get("terms", [{}])[-1].get("chamber")
                    if member.get("terms") else None,
                    "website": member.get("officialWebsiteUrl"),
                }

            elif tool_name == "get_legislator_bills":
                bioguide_id = tool_input["bioguide_id"]
                sponsored = await congress_client.get_member_bills(db, bioguide_id)

                bills_data = [
                    {
                        "bill_id": f"{b.get('type', '').upper()} {b.get('number')}",
                        "title": b.get("title"),
                        "introduced": b.get("introducedDate"),
                        "latest_action": b.get("latestAction", {}).get("text"),
                    }
                    for b in sponsored[:10]
                ]

                if tool_input.get("include_cosponsored"):
                    cosponsored = await congress_client.get_member_cosponsored_bills(
                        db, bioguide_id
                    )
                    for b in cosponsored[:5]:
                        bills_data.append({
                            "bill_id": f"{b.get('type', '').upper()} {b.get('number')}",
                            "title": b.get("title"),
                            "introduced": b.get("introducedDate"),
                            "cosponsored": True,
                        })

                return {"bills": bills_data}

            elif tool_name == "get_legislator_news":
                articles = await news_client.get_legislator_news(
                    db, tool_input["bioguide_id"]
                )
                return {
                    "articles": [
                        {
                            "title": a.get("title"),
                            "source": a.get("source", {}).get("name"),
                            "published": a.get("publishedAt"),
                            "url": a.get("url"),
                        }
                        for a in articles[:5]
                    ]
                }

            elif tool_name == "get_campaign_finance":
                finance = await fec_client.get_candidate_finances(
                    db, tool_input["bioguide_id"]
                )
                if not finance:
                    return {"error": "Campaign finance data not found"}
                return {
                    "cycle": finance.get("cycle"),
                    "total_receipts": finance.get("receipts"),
                    "total_disbursements": finance.get("disbursements"),
                    "cash_on_hand": finance.get("cash_on_hand_end_period"),
                    "individual_contributions": finance.get("individual_contributions"),
                    "pac_contributions": finance.get("other_political_committee_contributions"),
                }

            else:
                return {"error": f"Unknown tool: {tool_name}"}

        except Exception as e:
            return {"error": str(e)}

    async def _get_conversation_messages(
        self, db: AsyncSession, conversation_id: int
    ) -> list[dict]:
        """Get messages for a conversation in Claude API format."""
        from sqlalchemy import select

        result = await db.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at)
        )
        messages = result.scalars().all()

        return [
            {"role": msg.role, "content": msg.content}
            for msg in messages
        ]

    async def create_conversation(self, db: AsyncSession) -> Conversation:
        """Create a new conversation."""
        conversation = Conversation()
        db.add(conversation)
        await db.commit()
        await db.refresh(conversation)
        return conversation


ai_agent = AIAgent()
