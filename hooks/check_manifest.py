#!/usr/bin/env python3
"""PostToolUse hook: warns when an Edit/Write/MultiEdit adds a nonexistent dependency
to package.json, requirements.txt, or pyproject.toml. Can only warn (the edit already
happened), not block."""

import json
import os
import sys

PLUGIN_ROOT = os.environ.get("CLAUDE_PLUGIN_ROOT") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOOKS_DIR = os.path.join(PLUGIN_ROOT, "hooks")
if HOOKS_DIR not in sys.path:
    sys.path.insert(0, HOOKS_DIR)

from lib.manifest import manifest_kind, extract_deps  # noqa: E402
from lib.registries import check_package, NEW_PACKAGE_THRESHOLD_DAYS  # noqa: E402


def new_content_from_input(input_data):
    tool_name = input_data.get("tool_name")
    tool_input = input_data.get("tool_input") or {}
    file_path = tool_input.get("file_path", "")

    if tool_name == "Write":
        return file_path, tool_input.get("content", "")
    if tool_name == "Edit":
        return file_path, tool_input.get("new_string", "")
    if tool_name == "MultiEdit":
        edits = tool_input.get("edits") or []
        combined = "\n".join(e.get("new_string", "") for e in edits)
        return file_path, combined
    return file_path, ""


def main():
    try:
        input_data = json.load(sys.stdin)
    except Exception:
        sys.exit(0)

    file_path, content = new_content_from_input(input_data)
    if not file_path or manifest_kind(file_path) is None:
        sys.exit(0)

    kind = manifest_kind(file_path)

    try:
        deps = extract_deps(file_path, content)
    except Exception:
        sys.exit(0)

    if not deps:
        sys.exit(0)

    missing = []
    suspicious = []
    for name in deps:
        try:
            result = check_package(kind, name)
        except Exception:
            continue
        if result.get("error"):
            continue
        if not result.get("exists"):
            missing.append(name)
        else:
            days = result.get("published_days_ago")
            if days is not None and days < NEW_PACKAGE_THRESHOLD_DAYS:
                suspicious.append((name, round(days, 1)))

    if not missing and not suspicious:
        sys.exit(0)

    lines = [f"slopstop: reviewed dependencies added to {file_path}"]
    if missing:
        lines.append(
            "  MISSING (do not exist on the registry - likely hallucinated, possible "
            f"slopsquatting risk): {', '.join(missing)}"
        )
    if suspicious:
        susp_str = ", ".join(f"{n} ({d}d old)" for n, d in suspicious)
        lines.append(f"  RECENTLY PUBLISHED (verify before trusting): {susp_str}")

    print(json.dumps({"systemMessage": "\n".join(lines)}))
    sys.exit(0)


if __name__ == "__main__":
    main()
