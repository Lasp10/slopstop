"""Heuristic extraction of dependency names out of edited manifest file content."""

import re

PACKAGE_JSON_DEP_RE = re.compile(
    r'"([A-Za-z0-9@][\w.\-/]*)"\s*:\s*"(\^|~)?[\w.\-]+"'
)
PYPROJECT_DEP_LINE_RE = re.compile(r'^\s*([A-Za-z0-9][\w.\-]*)\s*=\s*["\'][^"\']*["\']')
PYPROJECT_LIST_ITEM_RE = re.compile(r'["\']([A-Za-z0-9][\w.\-]*)\s*[><=!~^]?')


def manifest_kind(file_path: str):
    name = file_path.rsplit("/", 1)[-1]
    if name == "package.json":
        return "npm"
    if name in ("requirements.txt",):
        return "pypi"
    if name == "pyproject.toml":
        return "pypi"
    return None


def extract_deps(file_path: str, content: str):
    kind = manifest_kind(file_path)
    if kind is None or not content:
        return []

    names = set()

    if kind == "npm":
        for m in PACKAGE_JSON_DEP_RE.finditer(content):
            key = m.group(1)
            if key in ("name", "version", "description", "main", "license", "author",
                       "private", "type", "scripts", "engines", "homepage"):
                continue
            names.add(key)

    elif file_path.endswith("requirements.txt"):
        for line in content.splitlines():
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("-"):
                continue
            pkg = re.split(r"[=<>!~\[; ]", line, 1)[0].strip()
            if pkg:
                names.add(pkg)

    elif file_path.endswith("pyproject.toml"):
        for line in content.splitlines():
            stripped = line.strip()
            if stripped.startswith("#") or not stripped:
                continue
            m = PYPROJECT_DEP_LINE_RE.match(stripped)
            if m and m.group(1) not in ("name", "version", "description", "readme",
                                         "requires-python", "license", "authors"):
                names.add(m.group(1))
                continue
            for lm in PYPROJECT_LIST_ITEM_RE.finditer(stripped):
                names.add(lm.group(1))

    return sorted(names)
