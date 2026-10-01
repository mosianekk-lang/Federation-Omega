"""Ephemeral localhost UI test host; uses the real runtime with no provider executor."""
import json, os, secrets, sys, tempfile
from pathlib import Path
import uvicorn
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
# The app module constructs a default context on import. Discard inherited
# provider, worker and private snapshot bindings before that construction.
for key in list(os.environ):
    if key.startswith(('FUSE_MOBILE_', 'SOL62_')):
        os.environ.pop(key, None)
with tempfile.TemporaryDirectory(prefix='fuse-ui-') as temporary:
    base = Path(temporary)
    os.environ.update(SOL62_CLIENT_ROOT=str(base/'default'), SOL62_STRATEGY_ROOT=str(base/'strategy'), FUSE_GENESIS_HOST_ROOT=str(base/'genesis'))
    from services.sol62_client_runtime import app as module
    from services.fuse_mobile_gateway.runtime import GatewayRuntime, SessionCodec, VerifiedIdentity
    from sol_61_runtime.sol_62 import GatewayPolicy, Sol62Runtime, WorkloadIdentityPolicy
    codec = SessionCodec(secrets.token_bytes(32))
    gateway = GatewayRuntime(session_codec=codec)
    runtime = Sol62Runtime(base/'runtime', gateway_policy=GatewayPolicy('sol-gateway','sol-6.2'), identity_policy=WorkloadIdentityPolicy(allowed_issuers={'test'}, audience='test', subject_prefix='test:'))
    context = module.ServiceContext(gateway=gateway, sol=runtime)
    token, _ = codec.issue(VerifiedIdentity('test:ui-owner'))
    # The parent consumes this single IPC line in memory; it must never log it.
    print(json.dumps({'session': token}), flush=True)
    app = module.create_app(context)
    try:
        uvicorn.run(app, host='127.0.0.1', port=int(os.getenv('FUSE_UI_TEST_PORT', '18762')), log_level='error')
    finally:
        context.close()
        module.app.state.sol62_context.close()
