from __future__ import annotations
from dataclasses import dataclass
from typing import FrozenSet, Mapping

CALLBACK_URI = "http://127.0.0.1:8080/callback"
AUTHORIZATION_URL = "https://twitter.com/i/oauth2/authorize"
TOKEN_URL = "https://api.x.com/2/oauth2/token"
API_BASE = "https://api.x.com/2"
DOCS_HEAD = "0df2c1043ac5ba0ca12130f3df23849913acd072"
PREDECESSOR_V3_SHA256 = "7e6670fdf44189339c9c94bf4f133115586e3aede3818aa03596dda9db5774aa"

READ_ONLY_SCOPES: FrozenSet[str] = frozenset({
    "tweet.read", "users.read", "offline.access"
})

# These scopes are action-enablement inputs only. They never grant FUSE action authority.
ACTION_READY_SCOPES: FrozenSet[str] = frozenset({
    "tweet.write",
    "like.read", "like.write",
    "follows.read", "follows.write",
    "bookmark.read", "bookmark.write",
    "list.read", "list.write",
    "block.read", "block.write",
    "mute.read", "mute.write",
})

FULL_SURFACE_SCOPES: FrozenSet[str] = READ_ONLY_SCOPES | ACTION_READY_SCOPES

ACTION_REQUIRED_SCOPES: Mapping[str, FrozenSet[str]] = {
    "X_POST": frozenset({"tweet.write"}),
    "X_REPLY": frozenset({"tweet.write"}),
    "X_LIKE": frozenset({"like.write"}),
    "X_FOLLOW": frozenset({"follows.write"}),
    "X_BOOKMARK_WRITE": frozenset({"bookmark.write"}),
    "X_LIST_WRITE": frozenset({"list.write"}),
    "X_BLOCK": frozenset({"block.write"}),
    "X_MUTE": frozenset({"mute.write"}),
}

ENTERPRISE_ONLY_ACTIONS = frozenset({"X_LIKE", "X_FOLLOW"})
NOT_SELF_SERVE_ACTIONS = frozenset({"X_QUOTE_POST"})
PROFILE_MUTATION_API_VERIFIED = False

READ_ENDPOINTS = {
    "me": "/users/me",
    "home_timeline": "/users/{id}/timelines/reverse_chronological",
    "recent_search": "/tweets/search/recent",
}

@dataclass(frozen=True)
class OAuthProfile:
    name: str
    scopes: FrozenSet[str]

READ_ONLY = OAuthProfile("READ_ONLY", READ_ONLY_SCOPES)
FULL_SURFACE = OAuthProfile("FULL_SURFACE", FULL_SURFACE_SCOPES)
