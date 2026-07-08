"""Pull candidate package names + ecosystem out of a shell command string."""

import re
import shlex

NPM_INSTALLERS = {"install", "i", "add", "ci"}
NPM_BINARIES = {"npm", "yarn", "pnpm", "npx", "bun"}
PIP_INSTALLERS = {"install", "add"}
PIP_BINARIES = {"pip", "pip3", "uv"}

FLAG_WITH_VALUE = {
    "-r", "--requirement", "--index-url", "-i", "--extra-index-url",
    "--target", "-t", "--prefix", "--python", "-p",
}


def split_chained(command: str):
    """Split on &&, ;, | so each subcommand can be inspected independently."""
    parts = re.split(r"&&|;|\|\|?", command)
    return [p.strip() for p in parts if p.strip()]


def _is_flag(token: str) -> bool:
    return token.startswith("-")


def _is_local_or_url(token: str) -> bool:
    return (
        token.startswith(".")
        or token.startswith("/")
        or token.startswith("git+")
        or token.startswith("http://")
        or token.startswith("https://")
        or token.startswith("file:")
        or token.startswith("workspace:")
        or "://" in token
    )


def _strip_version(token: str, sep_chars):
    for sep in sep_chars:
        idx = token.find(sep)
        if idx > 0:
            return token[:idx]
    return token


def _parse_args(args):
    """Yield cleaned package name tokens from an argument list, skipping flags/paths."""
    skip_next = False
    for tok in args:
        if skip_next:
            skip_next = False
            continue
        if _is_flag(tok):
            if tok in FLAG_WITH_VALUE:
                skip_next = True
            continue
        if _is_local_or_url(tok):
            continue
        yield tok


def extract_npm_packages(argv):
    """argv is the tokenized command, e.g. ['npm', 'install', 'left-pad', '-D']."""
    if not argv:
        return []
    binary = argv[0]
    if binary not in NPM_BINARIES:
        return []

    if binary == "npx":
        # npx <pkg> [args...] -- only the first non-flag token is the package
        rest = argv[1:]
        names = list(_parse_args(rest))
        if not names:
            return []
        first = names[0]
        if first.startswith("@"):
            return [first[: first.index("@", 1)]] if "@" in first[1:] else [first]
        return [_strip_version(first, ["@"])]

    if len(argv) < 3 or argv[1] not in NPM_INSTALLERS:
        return []

    rest = argv[2:]
    names = list(_parse_args(rest))
    cleaned = []
    for n in names:
        if n.startswith("@"):
            # scoped package: @scope/name[@version]
            if "@" in n[1:]:
                at_idx = n.index("@", 1)
                cleaned.append(n[:at_idx])
            else:
                cleaned.append(n)
        else:
            cleaned.append(_strip_version(n, ["@"]))
    return [c for c in cleaned if c]


def extract_pypi_packages(argv):
    if not argv:
        return []
    binary = argv[0]

    # handle "python -m pip install X" / "python3 -m pip install X"
    if binary in {"python", "python3"} and len(argv) >= 4 and argv[1] == "-m" and argv[2] == "pip":
        argv = argv[2:]
        binary = "pip"

    if binary not in PIP_BINARIES:
        return []

    if binary == "uv":
        # uv add X / uv pip install X
        if len(argv) >= 2 and argv[1] == "add":
            rest = argv[2:]
        elif len(argv) >= 3 and argv[1] == "pip" and argv[2] == "install":
            rest = argv[3:]
        else:
            return []
    else:
        if len(argv) < 3 or argv[1] not in PIP_INSTALLERS:
            return []
        rest = argv[2:]

    names = list(_parse_args(rest))
    cleaned = []
    for n in names:
        cleaned.append(_strip_version(n, ["==", ">=", "<=", "!=", "~=", ">", "<", "["]))
    return [c for c in cleaned if c]


def extract_candidates(command: str):
    """Returns list of (ecosystem, package_name) tuples found in a shell command."""
    results = []
    for sub in split_chained(command):
        try:
            argv = shlex.split(sub)
        except ValueError:
            continue
        if not argv:
            continue
        for pkg in extract_npm_packages(argv):
            results.append(("npm", pkg))
        for pkg in extract_pypi_packages(argv):
            results.append(("pypi", pkg))
    return results
