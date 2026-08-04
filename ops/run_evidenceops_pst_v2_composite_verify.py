#!/usr/bin/env python3
"""Run the PST composite verifier with a redirect-safe artifact downloader.

GitHub's artifact download endpoint authenticates the repository API request and
then returns a short-lived signed URL on a different storage host.  Repository
bearer tokens must never be forwarded to that storage host.  This adapter keeps
all verification logic in ``evidenceops_pst_v2_composite_verify.py`` unchanged
and replaces only its transport function:

1. authenticate the GitHub API hop;
2. stop automatic cross-host redirect handling;
3. read the signed ``Location`` header;
4. download the signed object without an Authorization header;
5. retain the original retry and atomic-partial-file semantics.
"""

from __future__ import annotations

import importlib.util
import os
import shutil
import sys
import time
import urllib.error
import urllib.request
from email.message import Message
from pathlib import Path

HERE = Path(__file__).resolve().parent
TARGET_PATH = HERE / "evidenceops_pst_v2_composite_verify.py"

SPEC = importlib.util.spec_from_file_location(
    "evidenceops_pst_v2_composite_verify_target", TARGET_PATH
)
assert SPEC and SPEC.loader
TARGET = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = TARGET
SPEC.loader.exec_module(TARGET)

_REDIRECT_CODES = {301, 302, 303, 307, 308}


class NoCrossHostRedirect(urllib.request.HTTPRedirectHandler):
    """Return redirects to the caller so authorization cannot leak cross-host."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def github_api_headers(token: str) -> dict[str, str]:
    return {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "EvidenceOps-PST-Composite-Verifier/1.1",
    }


def signed_storage_headers() -> dict[str, str]:
    # The signed URL itself is the storage authorization.  Never add the
    # repository bearer token to this request.
    return {"User-Agent": "EvidenceOps-PST-Composite-Verifier/1.1"}


def _location_from_redirect(exc: urllib.error.HTTPError) -> str | None:
    if exc.code not in _REDIRECT_CODES:
        return None
    return exc.headers.get("Location") if exc.headers else None


def download_artifact(repo: str, artifact_id: int, output: Path) -> None:
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not token:
        raise RuntimeError("GITHUB_TOKEN_MISSING")

    api_url = (
        f"https://api.github.com/repos/{repo}/actions/artifacts/"
        f"{artifact_id}/zip"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    partial = output.with_suffix(output.suffix + ".partial")
    opener = urllib.request.build_opener(NoCrossHostRedirect())
    last_error: Exception | None = None

    for attempt in range(1, 5):
        partial.unlink(missing_ok=True)
        try:
            api_request = urllib.request.Request(
                api_url,
                headers=github_api_headers(token),
            )
            signed_url: str | None = None
            direct_response = None
            try:
                direct_response = opener.open(api_request, timeout=180)
            except urllib.error.HTTPError as exc:
                signed_url = _location_from_redirect(exc)
                if not signed_url:
                    raise

            if signed_url:
                storage_request = urllib.request.Request(
                    signed_url,
                    headers=signed_storage_headers(),
                )
                with urllib.request.urlopen(
                    storage_request, timeout=180
                ) as response, partial.open("wb") as target:
                    shutil.copyfileobj(response, target, 8 * 1024 * 1024)
            else:
                if direct_response is None:
                    raise RuntimeError("ARTIFACT_RESPONSE_MISSING")
                with direct_response as response, partial.open("wb") as target:
                    shutil.copyfileobj(response, target, 8 * 1024 * 1024)

            if partial.stat().st_size <= 0:
                raise RuntimeError("EMPTY_ARTIFACT_DOWNLOAD")
            partial.replace(output)
            return
        except (OSError, RuntimeError, urllib.error.URLError) as exc:
            last_error = exc
            partial.unlink(missing_ok=True)
            if attempt < 4:
                time.sleep(attempt * 8)

    raise RuntimeError(
        f"ARTIFACT_DOWNLOAD_FAILED:{artifact_id}:{last_error}"
    )


TARGET.download_artifact = download_artifact


def main() -> int:
    return TARGET.main()


if __name__ == "__main__":
    raise SystemExit(main())
