from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence
from urllib.parse import urljoin
from urllib.request import Request, urlopen


CATALOG_URL = "https://openrouter.ai/api/v1/images/models"
GENERATION_ENDPOINT = "https://openrouter.ai/api/v1/images"
DEFAULT_MODEL = "recraft/recraft-v3"
DEFAULT_FREE_ALIAS = "recraft/recraft-v3:free"
USER_AGENT = "SOVARA-Creative-ReadOnly-Catalog-Probe/1.0"


class CatalogProbeError(RuntimeError):
    pass


def _canonical_hash(value: object) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return sha256(raw.encode("utf-8")).hexdigest()


def fetch_json(url: str, *, timeout: float = 20.0) -> dict[str, Any]:
    if not url.startswith("https://openrouter.ai/api/v1/images/") and url != CATALOG_URL:
        raise CatalogProbeError("read-only probe refuses non-OpenRouter image-catalog URL")
    request = Request(
        url,
        method="GET",
        headers={"Accept": "application/json", "User-Agent": USER_AGENT},
    )
    with urlopen(request, timeout=timeout) as response:  # nosec B310 - URL allowlisted above
        if getattr(response, "status", 200) != 200:
            raise CatalogProbeError(f"catalog GET failed with HTTP {response.status}")
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, dict):
        raise CatalogProbeError("catalog response must be a JSON object")
    return payload


def _records(payload: Mapping[str, Any], *keys: str) -> list[Mapping[str, Any]]:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, Mapping)]
    return []


def find_model(catalog: Mapping[str, Any], model_id: str) -> Mapping[str, Any] | None:
    for item in _records(catalog, "data", "models"):
        if str(item.get("id", "")).strip() == model_id:
            return item
    return None


def _pricing_rows(endpoint: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    pricing = endpoint.get("pricing")
    if isinstance(pricing, list):
        for item in pricing:
            if not isinstance(item, Mapping):
                continue
            cost = item.get("cost_usd")
            try:
                cost_float = float(cost)
            except (TypeError, ValueError):
                continue
            if cost_float < 0:
                continue
            rows.append(
                {
                    "billable": str(item.get("billable", "")).strip(),
                    "unit": str(item.get("unit", "")).strip(),
                    "cost_usd": cost_float,
                }
            )
    elif isinstance(pricing, Mapping):
        # Defensive compatibility with simple provider records.
        for key, value in pricing.items():
            if "image" not in str(key).lower():
                continue
            try:
                cost_float = float(value)
            except (TypeError, ValueError):
                continue
            if cost_float >= 0:
                rows.append({"billable": str(key), "unit": "image", "cost_usd": cost_float})
    return rows


def _endpoint_rows(payload: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    records = _records(payload, "data", "endpoints")
    if records:
        return records
    # Some APIs may return one endpoint object directly.
    if any(key in payload for key in ("pricing", "provider", "name")):
        return [payload]
    return []


def build_receipt(
    catalog: Mapping[str, Any],
    endpoints_payload: Mapping[str, Any] | None,
    *,
    model_id: str = DEFAULT_MODEL,
    free_alias: str = DEFAULT_FREE_ALIAS,
    catalog_url: str = CATALOG_URL,
    endpoints_url: str | None = None,
) -> dict[str, Any]:
    models = _records(catalog, "data", "models")
    ids = tuple(str(item.get("id", "")).strip() for item in models if item.get("id"))
    model = find_model(catalog, model_id)
    free_alias_present = free_alias in ids

    image_output_verified = False
    model_endpoint_path = None
    if model:
        architecture = model.get("architecture") if isinstance(model.get("architecture"), Mapping) else {}
        modalities = architecture.get("output_modalities") if isinstance(architecture, Mapping) else []
        image_output_verified = isinstance(modalities, list) and "image" in [str(x).lower() for x in modalities]
        model_endpoint_path = str(model.get("endpoints", "")).strip() or None

    endpoint_rows = _endpoint_rows(endpoints_payload or {})
    price_rows: list[dict[str, Any]] = []
    provider_labels: list[str] = []
    for endpoint in endpoint_rows:
        price_rows.extend(_pricing_rows(endpoint))
        for key in ("provider", "name", "provider_name"):
            value = endpoint.get(key)
            if isinstance(value, str) and value.strip():
                provider_labels.append(value.strip())
                break

    image_prices = [
        float(row["cost_usd"])
        for row in price_rows
        if row.get("unit") == "image" or "image" in str(row.get("billable", "")).lower()
    ]
    unit_price = min(image_prices) if image_prices else None

    if model is None:
        state = "HOLD_MODEL_CATALOG"
    elif not image_output_verified:
        state = "HOLD_IMAGE_CAPABILITY"
    elif endpoints_payload is None or not endpoint_rows:
        state = "HOLD_ENDPOINT_READBACK"
    elif unit_price is None:
        state = "HOLD_PRICE_READBACK"
    elif unit_price == 0.0:
        state = "ZERO_COST_ROUTE_VERIFIED"
    else:
        state = "PAID_ROUTE_VERIFIED"

    receipt: dict[str, Any] = {
        "schema": "SOVARA_OPENROUTER_IMAGE_CATALOG_READBACK_V1",
        "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
        "state": state,
        "catalog_url": catalog_url,
        "endpoints_url": endpoints_url,
        "generation_endpoint": GENERATION_ENDPOINT,
        "selected_model": model_id,
        "selected_model_present": model is not None,
        "free_alias": free_alias,
        "free_alias_present": free_alias_present,
        "image_output_verified": image_output_verified,
        "model_endpoint_path": model_endpoint_path,
        "catalog_model_count": len(ids),
        "endpoint_count": len(endpoint_rows),
        "providers": sorted(set(provider_labels)),
        "pricing": price_rows,
        "unit_price_usd": unit_price,
        "pricing_unit": "image" if unit_price is not None else None,
        "zero_cost_verified": unit_price == 0.0 if unit_price is not None else False,
        "credential_used": False,
        "authorization_header_sent": False,
        "http_methods_used": ["GET"],
        "provider_effect_performed": False,
        "image_generation_performed": False,
        "spend_performed": False,
        "case_data_processed": False,
        "real_person_processed": False,
        "truth_boundary": (
            "This receipt proves only a read-only public OpenRouter image catalog and endpoint-pricing readback. "
            "It does not authorize or prove credential binding, provider effect, image generation, spend, asset "
            "quality, semantic verification, rollback, repeated success, commercial value, publishing or production readiness."
        ),
    }
    receipt["catalog_sha256"] = _canonical_hash(catalog)
    receipt["endpoints_sha256"] = _canonical_hash(endpoints_payload) if endpoints_payload is not None else None
    receipt["receipt_sha256"] = _canonical_hash(receipt)
    return receipt


def run_probe(
    *,
    model_id: str = DEFAULT_MODEL,
    free_alias: str = DEFAULT_FREE_ALIAS,
    fetcher: Callable[[str], dict[str, Any]] = fetch_json,
) -> dict[str, Any]:
    catalog = fetcher(CATALOG_URL)
    model = find_model(catalog, model_id)
    endpoint_path = str(model.get("endpoints", "")).strip() if model else ""
    endpoints_url = urljoin("https://openrouter.ai", endpoint_path) if endpoint_path else None
    endpoints_payload = fetcher(endpoints_url) if endpoints_url else None
    return build_receipt(
        catalog,
        endpoints_payload,
        model_id=model_id,
        free_alias=free_alias,
        endpoints_url=endpoints_url,
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only OpenRouter image catalog probe")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--free-alias", default=DEFAULT_FREE_ALIAS)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)

    receipt = run_probe(model_id=args.model, free_alias=args.free_alias)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(receipt, sort_keys=True))
    return 0 if receipt["state"] in {"PAID_ROUTE_VERIFIED", "ZERO_COST_ROUTE_VERIFIED"} else 3


if __name__ == "__main__":
    raise SystemExit(main())
