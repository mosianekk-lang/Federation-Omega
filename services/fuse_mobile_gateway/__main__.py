import os

import uvicorn


if __name__ == "__main__":
    uvicorn.run(
        "services.fuse_mobile_gateway.app:app",
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "8080")),
        log_level="info",
    )
