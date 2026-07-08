#!/usr/bin/env python3
"""PreToolUse hook: blocks Bash commands that install nonexistent (hallucinated) packages."""

import json
import os
import sys

PLUGIN_ROOT = os.environ.get("CLAUDE_PLUGIN_ROOT") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOOKS_DIR = os.path.join(PLUGIN_ROOT, "hooks")
if HOOKS_DIR not in sys.path:
    sys.path.insert(0, HOOKS_DIR)

from lib.extract import extract_candidates  # noqa: E402
from lib.registries import check_package, NEW_PACKAGE_THRESHOLD_DAYS  # noqa: E402


def main():
    try:
        input_data = json.load(sys.stdin)
    except Exception:
        sys.exit(0)

    if input_data.get("tool_name") != "Bash":
        sys.exit(0)

    command = (input_data.get("tool_input") or {}).get("command", "")
    if not command:
        sys.exit(0)

    try:
        candidates = extract_candidates(command)
    except Exception:
        sys.exit(0)  # never block due to a parsing bug

    if not candidates:
        sys.exit(0)

    missing = []
    suspicious = []
    for ecosystem, name in candidates:
        try:
            result = check_package(ecosystem, name)
        except Exception:
            continue  # fail open on any lookup error

        if result.get("error"):
            continue  # fail open on network/registry errors

        if not result.get("exists"):
            missing.append((ecosystem, name))
        else:
            days = result.get("published_days_ago")
            if days is not None and days < NEW_PACKAGE_THRESHOLD_DAYS:
                suspicious.append((ecosystem, name, round(days, 1)))

    if missing:
        names = ", ".join(f"{name} ({eco})" for eco, name in missing)
        reason = (
            f"slopstop: blocked install. {names} do not exist on the registry. "
            "This matches the profile of an AI-hallucinated package name (slopsquatting risk): "
            "attackers register plausible-but-fake names that LLMs commonly hallucinate. "
            "Double-check the exact package name before retrying, or confirm you actually "
            "intend to publish/create it yourself."
        )
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": reason,
            }
        }))
        sys.exit(0)

    if suspicious:
        names = ", ".join(f"{name} ({eco}, published {days}d ago)" for eco, name, days in suspicious)
        print(json.dumps({
            "systemMessage": (
                f"slopstop warning: {names}. This package exists but was published very recently. "
                "Recently-registered packages are a common slopsquatting pattern (registered reactively "
                "after being observed as an AI hallucination). Verify it's the package you actually meant."
            )
        }))
        sys.exit(0)

    sys.exit(0)


if __name__ == "__main__":
    main()
