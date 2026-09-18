# FUSE-X xurl Adapter v1

Optional credential-isolation adapter around X's official xurl CLI. FUSE owns mission/state/observations/cursors/index/verification/finality; xurl is only a replaceable transport/auth helper.

The governed agent may inspect non-secret auth status and perform read-only X operations. It must never read ~/.xurl, print tokens, use secret-bearing flags, enable verbose auth output, invoke OAuth login inside agent context, or perform X account mutations. OAuth app registration and consent remain provider/owner-side.

Windows installation is user-space and pins official xurl v1.3.1 SHA-256 6b5e7435daa98d03a620b2a31b8c78162601959a63274e945ae372c799073305. Installation is not authorization; authorization is not Home-timeline proof. Provider whoami + Home timeline, durable/recovery courts and independent Judge remain required.
