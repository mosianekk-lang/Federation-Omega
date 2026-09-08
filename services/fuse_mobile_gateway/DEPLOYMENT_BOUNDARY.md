# FUSE Mobile Gateway deployment boundary

This source can be containerized, but source admission does not authorize or prove a deployed public mobile endpoint.

A deployment candidate must remain private/no-traffic or otherwise staging-bounded until all of the following are separately proven:

1. exact admitted source SHA and image digest;
2. runtime service identity;
3. real owner identity verification path;
4. server-side session signing secret from protected secret storage;
5. dynamic capability health readback;
6. KDV/source retrieval with provenance;
7. at least one provider-native semantic route;
8. effect-gate behavior;
9. rollback path;
10. no provider/backend secret exposure to the client.

Google AI Studio qualification should use the existing SOVARA direct semantic-canary route with runtime-injected authorization key and provider-native dynamic model discovery. It is not a reason to expose the key to FUSE Mobile.
