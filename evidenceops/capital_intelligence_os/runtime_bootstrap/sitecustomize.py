"""Phoenix PST artifact-download redirect guard.

Python's default urllib redirect handler copies request headers to the redirected
request.  GitHub artifact downloads redirect from ``api.github.com`` to a signed
blob-storage URL; forwarding the GitHub bearer token to that different host
causes the blob service to reject the otherwise valid signed request.

During the authorised Phoenix PST verification context only, strip authorization
headers when—and only when—the redirect crosses hosts.  The original GitHub API
request remains authenticated and same-host redirects remain unchanged.
"""

from __future__ import annotations

import os
import urllib.parse
import urllib.request


def _enabled() -> bool:
    return (
        os.environ.get("GITHUB_ACTIONS") == "true"
        and os.environ.get("GITHUB_WORKFLOW")
        == "Phoenix Emergency Execution Freeze"
        and bool(os.environ.get("PST_VERIFY_ROOT"))
    )


if _enabled():
    _original_redirect_request = urllib.request.HTTPRedirectHandler.redirect_request

    def _redirect_request(
        self: urllib.request.HTTPRedirectHandler,
        req: urllib.request.Request,
        fp: object,
        code: int,
        msg: str,
        headers: object,
        newurl: str,
    ) -> urllib.request.Request | None:
        redirected = _original_redirect_request(
            self, req, fp, code, msg, headers, newurl
        )
        if redirected is None:
            return None

        old_host = urllib.parse.urlsplit(req.full_url).netloc.lower()
        new_host = urllib.parse.urlsplit(newurl).netloc.lower()
        if old_host != new_host:
            for collection_name in ("headers", "unredirected_hdrs"):
                collection = getattr(redirected, collection_name, {})
                for key in list(collection):
                    if key.lower() == "authorization":
                        del collection[key]
        return redirected

    urllib.request.HTTPRedirectHandler.redirect_request = _redirect_request
