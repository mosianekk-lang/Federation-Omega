# FUSE X OAuth v4 — Custody-Stable Source-Independent Candidate

This package is a source-independent successor built after exact OAuth-v3 bytes were not recoverable
from the current runtime or canonical artifact registries. It does **not** claim source admission,
live X authentication, account authority, provider entitlement, or social effects.

Key properties:
- OAuth 2.0 Authorization Code + PKCE S256 public client
- callback fixed to `http://127.0.0.1:8080/callback`
- no client secret
- `users.email` omitted
- Windows current-user DPAPI-only persistent token custody
- read-only `/2/users/me`, Home timeline, and recent-search endpoints
- write effects require action-specific owner + policy authority
- Follow/Unfollow/Like/Unlike are Enterprise-only under current official X access mapping
- Quote-Post is not self-serve under current official changelog
- profile-field mutation API remains unverified
