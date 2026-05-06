"""
LINE-MCP — FastMCP server.

Exposes read + send tools over stdio for Claude Desktop.
Reads from Supabase (via asyncpg). Sends via LINE Messaging API (via httpx).
"""

import os
from dotenv import load_dotenv
from fastmcp import FastMCP

from lib.db import init_db_pool
from lib.line_client import init_line_client
from tools.read import register_read_tools
from tools.send import register_send_tools

load_dotenv()

mcp = FastMCP("line-mcp")


@mcp.startup
async def on_startup():
    await init_db_pool(os.environ["SUPABASE_DB_URL"])
    init_line_client(os.environ["LINE_CHANNEL_ACCESS_TOKEN"])


# Register tools
register_read_tools(mcp)
register_send_tools(mcp)


if __name__ == "__main__":
    mcp.run()
