#!/usr/bin/env python3
"""Phoenix provider cutover v3.1 exact-lease entrypoint.

This module preserves the tested v3 dual-authority engine and replaces only its
Git push implementation. Template-generated repositories already contain a
``main`` branch, so a generic ``--force-with-lease`` has no locally known remote
tracking value and may fail. v3.1 binds the lease explicitly to the SHA returned
by ``git ls-remote``.

In the source repository the base engine is ``provider_cutover_v3.py``. In the
exported Ops package it is copied beside this file as
``provider_cutover_v3_base.py``.
"""

from __future__ import annotations

import importlib.util
import os
import re
import stat
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE_CANDIDATES = [
    HERE / "provider_cutover_v3_base.py",
    HERE / "provider_cutover_v3.py",
]
BASE_PATH = next((path for path in BASE_CANDIDATES if path.is_file()), None)
if BASE_PATH is None:
    raise RuntimeError("Phoenix v3 base controller is missing")

SPEC = importlib.util.spec_from_file_location("phoenix_provider_cutover_v3_base", BASE_PATH)
assert SPEC and SPEC.loader
V3 = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = V3
SPEC.loader.exec_module(V3)

_SHA = re.compile(r"^[0-9a-fA-F]{40}$")


def parse_remote_main_sha(refs: str) -> str | None:
    """Return the exact remote main SHA from git-ls-remote output."""

    matches: list[str] = []
    for line in refs.splitlines():
        fields = line.strip().split()
        if len(fields) != 2 or fields[1] != "refs/heads/main":
            continue
        if not _SHA.fullmatch(fields[0]):
            raise V3.CutoverError("Remote main returned a malformed SHA")
        matches.append(fields[0].lower())
    if len(matches) > 1:
        raise V3.CutoverError("Remote main returned multiple conflicting refs")
    return matches[0] if matches else None


def git_push_exact_lease(
    token: str,
    owner: str,
    repo: str,
    source: Path,
    replace_existing_main: bool,
) -> str:
    """Push a clean baseline, binding replacement to provider-read main SHA."""

    remote = f"https://github.com/{owner}/{repo}.git"
    with tempfile.TemporaryDirectory(prefix="phoenix-askpass-v3-1-") as temp:
        askpass = Path(temp) / "askpass.sh"
        askpass.write_text(
            "#!/bin/sh\n"
            "case \"$1\" in\n"
            "  *Username*) printf '%s\\n' 'x-access-token' ;;\n"
            "  *) printf '%s\\n' \"$PHOENIX_GIT_TOKEN\" ;;\n"
            "esac\n",
            encoding="utf-8",
        )
        askpass.chmod(stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)
        environment = os.environ.copy()
        environment.update(
            {
                "GIT_ASKPASS": str(askpass),
                "GIT_TERMINAL_PROMPT": "0",
                "PHOENIX_GIT_TOKEN": token,
            }
        )

        refs = V3.run(
            ["git", "ls-remote", "--heads", remote, "main"],
            source,
            environment,
        )
        remote_main_sha = parse_remote_main_sha(refs)
        if remote_main_sha and not replace_existing_main:
            raise V3.CutoverError(
                f"Refusing to replace existing main in {owner}/{repo}"
            )

        V3.run(["git", "init", "-b", "main"], source, environment)
        V3.run(
            ["git", "config", "user.name", "Federation Omega Phoenix"],
            source,
        )
        V3.run(
            [
                "git",
                "config",
                "user.email",
                "phoenix@users.noreply.github.com",
            ],
            source,
        )
        V3.run(["git", "add", "--all"], source)
        V3.run(
            [
                "git",
                "commit",
                "-m",
                "Establish verified Federation Omega Phoenix baseline",
            ],
            source,
        )
        V3.run(["git", "remote", "add", "origin", remote], source)

        push = ["git", "push", "--set-upstream", "origin", "main"]
        if remote_main_sha:
            push.append(
                "--force-with-lease="
                f"refs/heads/main:{remote_main_sha}"
            )
        V3.run(push, source, environment)
        return V3.run(["git", "rev-parse", "HEAD"], source)


V3.git_push = git_push_exact_lease


def main() -> int:
    return V3.main()


if __name__ == "__main__":
    raise SystemExit(main())
