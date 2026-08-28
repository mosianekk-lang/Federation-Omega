# Runtime boundary note

`ops/sovara_sovereign_intelligence_court_v2.py` intentionally imports the existing v1 OpenRouter evaluator rather than copying provider code. This preserves a single provider implementation and reduces dilution risk.

The v2 court owns mission/checkpoint/degradation semantics. The v1 evaluator owns OpenRouter request/receipt semantics. The MCP adapter owns only ChatGPT-facing transport.

No layer is permitted to infer provider authority from another layer.
