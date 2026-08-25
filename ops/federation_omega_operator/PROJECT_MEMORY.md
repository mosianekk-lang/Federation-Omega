# Project memory

The public operator was healthy as `fo-operator-v1-image-cloudbuild` but its server source was absent from GitHub. The original implementation was recovered from the durable Library file `install_fo_ais.sh`. The live contract exposed five actions and required `FO_ADMIN_TOKEN`; GitHub WIF returned `invalid_target` and could not recover that token.

This repair restores the server as normal source, preserves the existing service identity and actions, adds Google OIDC principal authentication, and introduces a single hash-locked CFRE binding action. The canonical repaired CFRE archive SHA-256 is `58c1e456f02642bcccdf13c8029a07dc4f497f6418c274afc6d8185365f7407b`; its respawn-manifest file SHA-256 is `c581e04c3a5f15e59451e1fc6201ad1b07032418f632994001bf2d449f6b93e7`.
