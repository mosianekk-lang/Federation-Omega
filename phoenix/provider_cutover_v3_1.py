#!/usr/bin/env python3
"""Phoenix provider cutover v3.1 exact-lease entrypoint.

This module preserves the tested v3 dual-authority engine and replaces only its
git push implementation. Apply is accepted only from the canonical live-source
guarded launcher, which sets ``FEDOMEGA_GUARDED_APPLY=1`` after authorization
and current-source checks. Direct CLI apply is fail-closed.

The v3 base path is now a fail-closed module boundary. Its preserved engine is
opened for apply only inside this v3.1 call after the outer guarded-launcher
context has been verified.
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
BASE_CANDIDATES = [HERE / "provider_cutover_v3_base.py", HERE / "provider_cutover_v3.py"]
BASE_PATH = next((path for path in BASE_CANDIDATES if path.is_file()), None)
if BASE_PATH is None:
    raise RuntimeError("Phoenix v3 base controller is missing")

SPEC = importlib.util.spec_from_file_location("phoenix_provider_cutover_v3_base", BASE_PATH)
assert SPEC and SPEC.loader
V3 = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = V3
SPEC.loader.exec_module(V3)

_SHA = re.compile(r"^[0-9a-fA-F]{40}$")
GUARDED_APPLY_ENV = "FEDOMEGA_GUARDED_APPLY"
DEFAULT_INTERNAL_APPLY_ENV = "FEDOMEGA_PHOENIX_V3_ENGINE_APPLY"


def parse_remote_main_sha(refs: str) -> str | None:
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


def git_push_exact_lease(token: str, owner: str, repo: str, source: Path, replace_existing_main: bool) -> str:
    remote = f"https://github.com/{owner}/{repo}.git"
    with tempfile.TemporaryDirectory(prefix="phoenix-askpass-v3-1-") as temp:
        askpass = Path(temp) / "askpass.sh"
        askpass.write_text(
            "#!/bin/sh\ncase \"$1\" in\n  *Username*) printf '%s\\n' 'x-access-token' ;;\n  *) printf '%s\\n' \"$PHOENIX_GIT_TOKEN\" ;;\nesac\n",
            encoding="utf-8",
        )
        askpass.chmod(stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)
        environment = os.environ.copy()
        environment.update({"GIT_ASKPASS": str(askpass), "GIT_TERMINAL_PROMPT": "0", "PHOENIX_GIT_TOKEN": token})
        refs = V3.run(["git", "ls-remote", "--heads", remote, "main"], source, environment)
        remote_main_sha = parse_remote_main_sha(refs)
        if remote_main_sha and not replace_existing_main:
            raise V3.CutoverError(f"Refusing to replace existing main in {owner}/{repo}")
        V3.run(["git", "init", "-b", "main"], source, environment)
        V3.run(["git", "config", "user.name", "Federation Omega Phoenix"], source)
        V3.run(["git", "config", "user.email", "phoenix@users.noreply.github.com"], source)
        V3.run(["git", "add", "--all"], source)
        V3.run(["git", "commit", "-m", "Establish verified Federation Omega Phoenix baseline"], source)
        V3.run(["git", "remote", "add", "origin", remote], source)
        push = ["git", "push", "--set-upstream", "origin", "main"]
        if remote_main_sha:
            push.append("--force-with-lease=" f"refs/heads/main:{remote_main_sha}")
        V3.run(push, source, environment)
        return V3.run(["git", "rev-parse", "HEAD"], source)


V3.git_push = git_push_exact_lease
if hasattr(V3, "ENGINE"):
    V3.ENGINE.git_push = git_push_exact_lease


def guarded_apply_context(argv: list[str] | None = None) -> bool:
    args = list(sys.argv if argv is None else argv)
    if "--apply" not in args:
        return True
    return os.getenv(GUARDED_APPLY_ENV) == "1"


def main() -> int:
    if not guarded_apply_context():
        raise V3.CutoverError(
            "Direct Phoenix v3.1 --apply is prohibited; use provider_cutover_guarded.py so live-source and authorization guards are enforced"
        )

    internal_env = getattr(V3, "INTERNAL_APPLY_ENV", DEFAULT_INTERNAL_APPLY_ENV)
    applying = "--apply" in sys.argv
    existed = internal_env in os.environ
    previous = os.environ.get(internal_env)
    if applying:
        os.environ[internal_env] = "1"
    try:
        return V3.main()
    finally:
        if applying:
            if existed and previous is not None:
                os.environ[internal_env] = previous
            else:
                os.environ.pop(internal_env, None)


if __name__ == "__main__":
    raise SystemExit(main())
