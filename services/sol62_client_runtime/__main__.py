from __future__ import annotations
import os
import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "services.sol62_client_runtime.app:app",
        host=os.getenv("SOL62_CLIENT_HOST", "127.0.0.1"),
        port=int(os.getenv("SOL62_CLIENT_PORT", "8762")),
        reload=False,
    )
