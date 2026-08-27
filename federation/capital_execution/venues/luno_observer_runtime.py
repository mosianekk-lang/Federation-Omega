from __future__ import annotations

from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Mapping
from urllib.parse import parse_qs, urlparse
import hashlib
import json
import os

from .luno_account_observer import LunoCredentialReference, LunoReadOnlyAccountObserver
from .luno_permission_proof import LunoPermissionProof, parse_permission_proof
from .luno_public import LunoPublicRESTClient


PUBLIC_ONLY = "PUBLIC_ONLY"
ACCOUNT_READ_ONLY = "ACCOUNT_READ_ONLY"


@dataclass(frozen=True)
class BindingContext:
    mode: str
    key_id: str = ""
    credential_material: str = ""
    proof: LunoPermissionProof | None = None

    @property
    def observer_bound(self) -> bool:
        return self.mode == ACCOUNT_READ_ONLY and self.proof is not None

    @property
    def proof_digest(self) -> str | None:
        return self.proof.digest() if self.proof else None


def build_binding_context(env: Mapping[str, str] | None = None) -> BindingContext:
    source = dict(os.environ if env is None else env)
    mode = source.get("LUNO_BINDING_MODE", PUBLIC_ONLY).strip().upper() or PUBLIC_ONLY
    if mode == PUBLIC_ONLY:
        return BindingContext(mode=PUBLIC_ONLY)
    if mode != ACCOUNT_READ_ONLY:
        raise ValueError("unsupported LUNO_BINDING_MODE")

    key_id = source.get("LUNO_OBSERVER_KEY_ID", "")
    material = source.get("LUNO_OBSERVER_KEY_MATERIAL", "")
    proof_raw = source.get("LUNO_OBSERVER_PERMISSION_PROOF", "")
    if not key_id or not material or not proof_raw:
        raise PermissionError("LUNO_ACCOUNT_BINDING_REQUIRES_DEDICATED_CREDENTIAL_AND_PERMISSION_PROOF")
    proof = parse_permission_proof(proof_raw, key_id=key_id)
    return BindingContext(mode=ACCOUNT_READ_ONLY, key_id=key_id, credential_material=material, proof=proof)


class LunoObserverRuntime:
    """Private read-only runtime. No method in this class can create a financial effect."""

    def __init__(self, context: BindingContext | None = None) -> None:
        self.context = context or build_binding_context()
        self.public = LunoPublicRESTClient(timeout_seconds=8.0)
        self.account: LunoReadOnlyAccountObserver | None = None
        if self.context.observer_bound:
            credential = LunoCredentialReference(
                "runtime-ref://luno-observer-v1-2",
                expected_permissions=tuple(self.context.proof.permissions),
            )
            self.account = LunoReadOnlyAccountObserver(
                credential,
                lambda _reference: (self.context.key_id, self.context.credential_material),
                timeout_seconds=8.0,
            )

    def health(self) -> Mapping[str, Any]:
        return {
            "service": "federation-luno-observer",
            "version": "1.2.0",
            "state": "HEALTHY",
            "binding_mode": self.context.mode,
            "observer_bound": self.context.observer_bound,
            "financial_effects": False,
            "write_operations": False,
        }

    def ready(self) -> Mapping[str, Any]:
        return {
            **self.health(),
            "state": "OBSERVER_BOUND" if self.context.observer_bound else "PUBLIC_MARKET_READY",
            "permission_proof_digest": self.context.proof_digest,
        }

    def public_ticker(self, pair: str) -> Mapping[str, Any]:
        payload = self.public.ticker(pair)
        return {
            "state": "PUBLIC_MARKET_READBACK_VERIFIED",
            "pair": pair,
            "timestamp": payload.get("timestamp"),
            "bid": payload.get("bid"),
            "ask": payload.get("ask"),
            "last_trade": payload.get("last_trade"),
            "source": "LUNO_PUBLIC:/api/1/ticker",
        }

    def public_orderbook(self, pair: str) -> Mapping[str, Any]:
        snapshot = self.public.snapshot(pair)
        return {
            "state": "PUBLIC_ORDERBOOK_READBACK_VERIFIED",
            "pair": pair,
            "timestamp_ms": snapshot.timestamp_ms,
            "bid_levels": len(snapshot.bids),
            "ask_levels": len(snapshot.asks),
            "best_bid": str(snapshot.best_bid),
            "best_ask": str(snapshot.best_ask),
            "spread_bps": str(snapshot.spread_bps),
            "source": snapshot.source_ref,
        }

    def account_semantic_summary(self, pair: str) -> Mapping[str, Any]:
        if self.account is None or not self.context.observer_bound:
            raise PermissionError("LUNO_ACCOUNT_OBSERVER_NOT_BOUND")
        balances = self.account.balances()
        rows = list(balances.get("balance", ()))
        orders = self.account.list_orders(pair=pair, limit=10)
        fee = self.account.fee_info(pair)

        account_ids: list[int] = []
        for row in rows:
            if not isinstance(row, Mapping):
                continue
            candidate = row.get("account_id", row.get("id"))
            try:
                value = int(candidate)
            except (TypeError, ValueError):
                continue
            if value > 0:
                account_ids.append(value)

        if not account_ids:
            raise ValueError("LUNO_BALANCE_READBACK_MISSING_ACCOUNT_ID")
        transactions = self.account.account_transactions(account_ids[0], min_row=-1, max_row=0)
        transaction_rows = transactions.get("transactions", transactions.get("entries", ()))
        if not isinstance(transaction_rows, (list, tuple)):
            transaction_rows = ()

        structural = {
            "balance_rows": len(rows),
            "account_id_count": len(account_ids),
            "order_rows": len(list(orders.get("orders", ()))),
            "transaction_rows_sampled": len(transaction_rows),
            "fee_fields": sorted(key for key in fee if key in {"maker_fee", "taker_fee", "thirty_day_volume"}),
        }
        digest = hashlib.sha256(
            json.dumps(structural, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        return {
            "state": "AUTHENTICATED_READ_ONLY_SEMANTIC_CANARY_VERIFIED",
            "pair": pair,
            **structural,
            "structural_digest": digest,
            "permission_proof_digest": self.context.proof_digest,
            "private_values_returned": False,
            "financial_effects": False,
            "write_operations": False,
        }


class Handler(BaseHTTPRequestHandler):
    runtime: LunoObserverRuntime | None = None

    def log_message(self, fmt: str, *args: Any) -> None:
        return

    def _json(self, status: int, payload: Mapping[str, Any]) -> None:
        data = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("content-type", "application/json")
        self.send_header("cache-control", "no-store")
        self.send_header("content-length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _deny_write(self) -> None:
        self._json(405, {"state": "METHOD_NOT_ALLOWED_READ_ONLY", "financial_effects": False})

    do_POST = _deny_write
    do_PUT = _deny_write
    do_PATCH = _deny_write
    do_DELETE = _deny_write

    def do_GET(self) -> None:
        runtime = self.runtime or LunoObserverRuntime()
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)
        pair = str(query.get("pair", ["XBTZAR"])[0]).upper()
        try:
            if parsed.path == "/health":
                payload = runtime.health()
            elif parsed.path == "/ready":
                payload = runtime.ready()
            elif parsed.path == "/v1/public/ticker":
                payload = runtime.public_ticker(pair)
            elif parsed.path == "/v1/public/orderbook":
                payload = runtime.public_orderbook(pair)
            elif parsed.path == "/v1/account/semantic-canary":
                payload = runtime.account_semantic_summary(pair)
            else:
                self._json(404, {"state": "NOT_FOUND"})
                return
            self._json(200, payload)
        except PermissionError as exc:
            self._json(403, {"state": str(exc), "financial_effects": False})
        except ValueError as exc:
            self._json(400, {"state": str(exc), "financial_effects": False})
        except Exception as exc:
            self._json(502, {"state": "UPSTREAM_READ_FAILURE", "error_type": type(exc).__name__, "financial_effects": False})


def main() -> None:
    context = build_binding_context()
    Handler.runtime = LunoObserverRuntime(context)
    port = int(os.environ.get("PORT", "8080"))
    if not 1 <= port <= 65535:
        raise ValueError("PORT out of range")
    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    server.serve_forever()


if __name__ == "__main__":
    main()
