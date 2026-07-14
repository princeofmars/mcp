"""Small MCP client for the local gateway.

Run after the MCP service is available:
    MCP_AGENT_TOKEN=mcp_demo_change_me python examples/client.py
"""
from __future__ import annotations

import asyncio
import os

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client


async def main() -> None:
    token = os.environ.get("MCP_AGENT_TOKEN", "mcp_demo_change_me")
    url = os.environ.get("MCP_URL", "http://localhost:8001/mcp")
    async with streamablehttp_client(url, headers={"Authorization": f"Bearer {token}"}) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            print("Tools:", [tool.name for tool in tools.tools])
            result = await session.call_tool(
                "prepare_prevention_brief",
                arguments={"member_id": "member-123", "days": 30},
            )
            print(result.structuredContent or result.content)


if __name__ == "__main__":
    asyncio.run(main())
