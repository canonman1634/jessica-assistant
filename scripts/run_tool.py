"""
CLI bridge so a Claude Code session can invoke Jessica's Python tools (which
aren't native Claude Code tools) via Bash. Dispatches through the same
registry agent.py defines, so tool logic isn't duplicated here.

Usage:
    python scripts/run_tool.py <tool_name> '<json args>'
    python scripts/run_tool.py search_restaurants '{"location": "Deer Park, IL", "term": "italian restaurants"}'
    python scripts/run_tool.py list_recent_calls
"""
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from agent import _TOOL_HANDLERS


def main() -> None:
    if len(sys.argv) < 2:
        print(f"Usage: python {sys.argv[0]} <tool_name> ['<json args>']", file=sys.stderr)
        print(f"Available tools: {', '.join(sorted(_TOOL_HANDLERS))}", file=sys.stderr)
        sys.exit(1)

    tool_name = sys.argv[1]
    handler = _TOOL_HANDLERS.get(tool_name)
    if not handler:
        print(f"Unknown tool: {tool_name}. Available: {', '.join(sorted(_TOOL_HANDLERS))}", file=sys.stderr)
        sys.exit(1)

    args = json.loads(sys.argv[2]) if len(sys.argv) > 2 else {}
    result = asyncio.run(handler(args))

    for block in result.get("content", []):
        if block.get("type") == "text":
            print(block["text"])

    if result.get("is_error"):
        sys.exit(1)


if __name__ == "__main__":
    main()
