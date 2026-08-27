# Provider Boundary — Luno v1

The Luno integration is deliberately split into two source surfaces.

## Public market adapter

`LunoPublicRESTClient` uses only allowlisted HTTPS GET endpoints for ticker, top/full order book, recent trades, candles and market metadata. It contains explicit fail-closed stubs for create-order, cancel-order and convert.

## Authenticated account observer

`LunoReadOnlyAccountObserver` resolves a symbolic credential reference at call time and permits only GET operations for balances, order history and fee information. The credential contract allows only read permissions (`Perm_R_Balance`, `Perm_R_Transactions`, `Perm_R_Orders`). Write permission expectations are rejected before a provider call.

Source implementation does not prove a Luno credential exists, that it has the expected permissions, or that the account can be read. Those require separate authenticated provider readback.

## Explicitly absent

- create order
- cancel order
- conversion
- send
- withdrawal
- transfer
- live execution lease
- capital promotion

The official Luno MCP may be attached later as an additional control/observation surface, but write operations must remain disabled for the observer phase. The native REST/WebSocket data plane remains separate from the reasoning/control plane.
