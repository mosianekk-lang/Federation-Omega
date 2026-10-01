# FUSE-X Public-Client OAuth v1

X developer documentation classifies Native App and Single Page App clients as public clients: OAuth 2.0 Authorization Code + PKCE is used without a client secret. FUSE-X therefore uses a Native App/public-client path for the owner desktop route.

Only client_id is durable non-secret configuration. Access/refresh tokens are protected with Windows current-user DPAPI under %LOCALAPPDATA%\FUSE\X\auth and never printed. Requested scopes are tweet.read users.read offline.access; no write scope.

One-time consent starts a loopback callback on 127.0.0.1:8080, opens X authorization, verifies state, exchanges the code with the PKCE verifier and persists token state. Refresh is automatic. This removes routine re-authentication burden but does not automate X Developer App creation or the user's consent decision.

Provider whoami and Home timeline readback remain mandatory before live-finality promotion.
