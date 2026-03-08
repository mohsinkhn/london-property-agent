"""Main orchestrator — runs the property hunting agent with all MCP servers."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from claude_agent_sdk import (
    query,
    ClaudeAgentOptions,
    AssistantMessage,
    ResultMessage,
    SystemMessage,
)

from src.agent.config import PropertySearchConfig
from src.agent.prompt import SYSTEM_PROMPT

# ── Project root ────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")

# ── MCP server paths ───────────────────────────────────────────────────────
MCP_DIR = PROJECT_ROOT / "src" / "mcp_servers"


def _stdio_server(script: str, env_extra: dict | None = None) -> dict:
    """Build a stdio MCP server config pointing at one of our server scripts."""
    env = {**os.environ, **(env_extra or {})}
    return {
        "command": sys.executable,
        "args": [str(MCP_DIR / script)],
        "env": env,
    }


def build_mcp_servers() -> dict:
    """Return the mcp_servers dict for ClaudeAgentOptions."""
    servers: dict = {
        "rightmove": _stdio_server("rightmove.py"),
        "zoopla": _stdio_server("zoopla.py"),
        "tfl": _stdio_server("tfl_commute.py"),
        "crime": _stdio_server("crime.py"),
        "schools": _stdio_server("schools.py"),
        "land_registry": _stdio_server("land_registry.py"),
        "epc": _stdio_server("epc.py"),
    }
    return servers


def build_allowed_tools() -> list[str]:
    """Wildcard-allow every tool from every MCP server + Skills."""
    return [
        # Skills — Claude autonomously invokes these based on task context
        "Skill",
        # MCP data source tools
        "mcp__rightmove__*",
        "mcp__zoopla__*",
        "mcp__tfl__*",
        "mcp__crime__*",
        "mcp__schools__*",
        "mcp__land_registry__*",
        "mcp__epc__*",
    ]


async def run_agent(config: PropertySearchConfig, verbose: bool = False) -> str:
    """Run the property hunting agent and return the final result text."""
    mcp_servers = build_mcp_servers()
    allowed_tools = build_allowed_tools()

    options = ClaudeAgentOptions(
        cwd=str(PROJECT_ROOT),
        setting_sources=["project"],  # Load Skills from .claude/skills/
        system_prompt=SYSTEM_PROMPT,
        mcp_servers=mcp_servers,
        allowed_tools=allowed_tools,
        permission_mode="bypassPermissions",
    )

    user_prompt = (
        f"Find me the best properties to buy in London matching these criteria:\n\n"
        f"{config.to_prompt()}\n\n"
        f"Search all specified areas, enrich each property with commute time, "
        f"crime stats, school ratings, sold prices, and EPC data, then score and "
        f"rank them. Return the top 10."
    )

    result_text = ""

    async for message in query(prompt=user_prompt, options=options):
        # Log MCP server connection status
        if isinstance(message, SystemMessage) and message.subtype == "init":
            mcp_info = message.data.get("mcp_servers", [])
            connected = [s for s in mcp_info if s.get("status") == "connected"]
            failed = [s for s in mcp_info if s.get("status") != "connected"]
            print(f"✓ MCP servers connected: {len(connected)}/{len(mcp_info)}")
            if failed:
                for s in failed:
                    print(f"  ✗ {s.get('name', '?')}: {s.get('status', 'unknown')}")

        # Stream assistant output
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if hasattr(block, "text"):
                    if verbose:
                        print(block.text)
                elif hasattr(block, "name"):
                    tool_name = block.name
                    print(f"  → calling {tool_name}")

        # Capture final result
        if isinstance(message, ResultMessage):
            if message.subtype == "success":
                result_text = message.result
                print("\n✓ Agent completed successfully.")
            else:
                print(f"\n✗ Agent finished with status: {message.subtype}")
                result_text = getattr(message, "result", "No result")

    return result_text


def save_results(result: str, output_dir: Path) -> None:
    """Save agent results to files."""
    output_dir.mkdir(parents=True, exist_ok=True)
    # Save raw result
    (output_dir / "results.md").write_text(result, encoding="utf-8")
    print(f"Results saved to {output_dir / 'results.md'}")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="London Property Hunter Agent")
    p.add_argument(
        "--areas",
        nargs="+",
        default=["SE15", "SE22", "SE5", "E8", "E5"],
        help="London areas/postcodes to search",
    )
    p.add_argument("--budget", type=int, default=600_000, help="Max price in GBP")
    p.add_argument("--min-beds", type=int, default=2, help="Minimum bedrooms")
    p.add_argument("--max-beds", type=int, default=None, help="Maximum bedrooms")
    p.add_argument(
        "--commute-to",
        default="Kings Cross",
        help="Commute destination (station or postcode)",
    )
    p.add_argument(
        "--max-commute", type=int, default=45, help="Max commute minutes"
    )
    p.add_argument("--verbose", "-v", action="store_true", help="Show all agent output")
    return p.parse_args()


def cli() -> None:
    args = parse_args()

    config = PropertySearchConfig(
        areas=args.areas,
        max_price=args.budget,
        min_beds=args.min_beds,
        max_beds=args.max_beds,
        commute_target=args.commute_to,
        max_commute_mins=args.max_commute,
    )

    print("=" * 60)
    print("London Property Hunter Agent")
    print("=" * 60)
    print(f"Search: {config.to_prompt()}")
    print("=" * 60)

    result = asyncio.run(run_agent(config, verbose=args.verbose))
    save_results(result, PROJECT_ROOT / "data")


if __name__ == "__main__":
    cli()
