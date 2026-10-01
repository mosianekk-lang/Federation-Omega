# FUSE LocalLLM Desktop v0.2.2

This is the correction to the v0.1.1 product-maturity mismatch.

v0.1.1 was a **runtime/source bundle**. v0.2.2 is designed as a **Windows desktop product**:

- chat-first UI
- left navigation
- recent chat history
- local GGUF model picker
- model scan and switching
- streaming generation
- settings and runtime diagnostics
- text/code attachments
- OpenAI-compatible local API
- core Ollama-compatible endpoints
- background runtime
- Start-menu/Desktop shortcut installation
- normal launch with no command window

## Normal user experience after build/install

1. Launch **FUSE LocalLLM** from Start or Desktop.
2. The FUSE runtime starts hidden in the background.
3. A standalone Edge app-mode window opens on the FUSE LocalLLM UI.
4. The newest GGUF in `Downloads\Programs\FUSE` is loaded automatically.
5. Select another discovered model from the top model picker or Models page.
6. Chat locally.

No separate Ollama, LM Studio, Python, Node, .NET or Docker service is required.

## Build once on Windows

Double-click `BUILD_INSTALL_LAUNCH_WINDOWS.cmd`.

That builds:
- `FUSE-LocalLLM.exe` — FUSE inference/runtime service
- `FUSE-LocalLLM-Desktop.exe` — no-console Windows desktop launcher

The runtime uses a statically linked pinned MIT `llama.cpp` inference-kernel donor at:
`60081bb2b5b3294165a4d67c5cbeebe74c868014`

FUSE owns the product shell, API contract, UX, model discovery, model switching, receipts and SFCP boundary.

## Current proof boundary

The source/UI/API contract is tested here. The actual Windows EXEs, your 15.4 GB Qwen GGUF load, GPU offload and runtime performance still require execution on the Windows node. They are not inferred from source readiness.

## Why this is structurally closer to the competitor

Current Ollama desktop source uses a separate desktop app plus its local server and a web UI stack. FUSE v0.2 adopts the **mechanism**, not their code or branding: background inference process + desktop shell + local UI/API + model management. FUSE keeps its own runtime contract and can replace the inference kernel later.
