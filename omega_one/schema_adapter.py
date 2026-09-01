"""Omega-One schema-first adapter compiler, preserved from the v0.8.3 feature set.

This is a non-effect translation layer. It turns OpenAPI 3.x descriptions into the
richer Omega-One Universal Capability Contract (UCC), preserving enums, unions,
local references, sensitive-field semantics and symbolic authentication boundaries.
It performs no HTTP request, credential resolution, SDK installation or provider effect.

The resulting UCC can then be projected through the v0.8.5 zero-dilution
MCP/A2A/OpenTelemetry spine without replacing the richer internal contract.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
import time
from dataclasses import asdict, dataclass
from typing import Any, Iterable, Mapping

from .interop import EffectClass, InteropBundle, OmegaInteropSpine, UniversalCapabilityContract


_SUPPORTED_METHODS = ("get", "head", "post", "put", "patch", "delete", "options", "trace")
_READ_METHODS = {"GET", "HEAD", "OPTIONS"}
_COMPLEX_AUTH_TYPES = {"oauth2", "openidconnect", "mutualtls"}
_SECRET_NAME = re.compile(
    r"(?:^|[_\-])(authorization|api[_\-]?key|access[_\-]?token|refresh[_\-]?token|password|passwd|secret|private[_\-]?key)(?:$|[_\-])",
    re.I,
)
_AUTH_NAME = re.compile(
    r"(?:^|[_\-])(authorization|api[_\-]?key|access[_\-]?token|refresh[_\-]?token|secret|private[_\-]?key)(?:$|[_\-])",
    re.I,
)
_IDENTIFIER = re.compile(r"[^A-Za-z0-9_]+")


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def _sha(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _normalise_id(value: str) -> str:
    clean = _IDENTIFIER.sub("_", value.strip()).strip("_")
    if not clean:
        clean = "operation"
    if clean[0].isdigit():
        clean = f"op_{clean}"
    return clean


def _semantic_for_method(method: str) -> str:
    method = method.upper()
    if method in {"GET", "HEAD", "OPTIONS"}:
        return "READ_API_RESOURCE"
    if method == "POST":
        return "CREATE_API_RESOURCE"
    if method in {"PUT", "PATCH"}:
        return "UPDATE_API_RESOURCE"
    if method == "DELETE":
        return "DELETE_API_RESOURCE"
    return "EXECUTE_API_OPERATION"


def _effect_for_method(method: str) -> EffectClass:
    return EffectClass.READ if method.upper() in _READ_METHODS else EffectClass.WRITE


@dataclass(frozen=True)
class CompiledAdapterOperation:
    adapter_operation_id: str
    source_operation_id: str
    method: str
    path: str
    tags: tuple[str, ...]
    effect_class: EffectClass
    semantic_operation: str
    contract: UniversalCapabilityContract
    symbolic_auth_requirements: tuple[str, ...]
    sensitive_fields: tuple[str, ...]
    schema_hash: str

    def digest(self) -> str:
        return _sha(asdict(self))


@dataclass(frozen=True)
class HeldSchemaOperation:
    source_operation_id: str
    method: str
    path: str
    reason: str
    symbolic_auth_requirements: tuple[str, ...] = ()


@dataclass(frozen=True)
class SchemaCompileResult:
    source_id: str
    openapi_version: str
    operations: tuple[CompiledAdapterOperation, ...]
    held: tuple[HeldSchemaOperation, ...]
    filtered_out: int
    compiler_version: str
    compile_ms: float
    result_hash: str

    @property
    def total_seen(self) -> int:
        return len(self.operations) + len(self.held) + self.filtered_out

    @property
    def coverage_ratio(self) -> float:
        actionable = len(self.operations) + len(self.held)
        return 1.0 if actionable == 0 else round(len(self.operations) / actionable, 6)


@dataclass(frozen=True)
class SchemaInteropResult:
    schema_result: SchemaCompileResult
    bundles: tuple[InteropBundle, ...]
    result_hash: str


class SchemaFirstAdapterCompiler:
    """OpenAPI 3.x -> Omega-One UCC compiler with v0.8.3 feature parity.

    Complex authentication remains preserved as a held operation for a purpose-built
    adapter. Credential-like examples/defaults are stripped, while sensitive business
    fields such as a password input remain in the schema as explicit secret-reference
    requirements instead of being silently deleted.
    """

    VERSION = "0.8.5"

    def __init__(self, *, default_privacy_class: str = "P1_INTERNAL") -> None:
        self.default_privacy_class = default_privacy_class

    def compile(
        self,
        spec: Mapping[str, Any],
        *,
        source_id: str,
        include_tags: Iterable[str] = (),
        include_operation_ids: Iterable[str] = (),
    ) -> SchemaCompileResult:
        start = time.perf_counter()
        if not isinstance(spec, Mapping):
            raise ValueError("SCHEMA_SPEC_MAPPING_REQUIRED")
        version = str(spec.get("openapi", ""))
        if not version.startswith("3."):
            raise ValueError("OPENAPI_3_X_REQUIRED")
        if not source_id.strip():
            raise ValueError("SCHEMA_SOURCE_ID_REQUIRED")
        paths = spec.get("paths")
        if not isinstance(paths, Mapping):
            raise ValueError("OPENAPI_PATHS_REQUIRED")

        tag_filter = {str(x) for x in include_tags if str(x).strip()}
        op_filter = {str(x) for x in include_operation_ids if str(x).strip()}
        components = spec.get("components") if isinstance(spec.get("components"), Mapping) else {}
        root_security = spec.get("security", [])
        raw_ops: list[tuple[str, str, Mapping[str, Any], Mapping[str, Any]]] = []
        filtered = 0
        for path in sorted(str(k) for k in paths.keys()):
            path_item = paths[path]
            if not isinstance(path_item, Mapping):
                continue
            for method in _SUPPORTED_METHODS:
                operation = path_item.get(method)
                if not isinstance(operation, Mapping):
                    continue
                source_op_id = str(operation.get("operationId") or f"{method}_{path}")
                tags = {str(t) for t in operation.get("tags", []) if str(t).strip()}
                if tag_filter and not tag_filter.intersection(tags):
                    filtered += 1
                    continue
                if op_filter and source_op_id not in op_filter:
                    filtered += 1
                    continue
                raw_ops.append((path, method.upper(), operation, path_item))

        base_counts: dict[str, int] = {}
        for path, method, operation, _ in raw_ops:
            source_op_id = str(operation.get("operationId") or f"{method}_{path}")
            base = _normalise_id(source_op_id)
            base_counts[base] = base_counts.get(base, 0) + 1

        compiled: list[CompiledAdapterOperation] = []
        held: list[HeldSchemaOperation] = []
        for path, method, operation, path_item in raw_ops:
            source_op_id = str(operation.get("operationId") or f"{method}_{path}")
            auth = self._auth_requirements(operation, root_security, components)
            complex_types = tuple(sorted({kind for _, kind in auth if kind.lower() in _COMPLEX_AUTH_TYPES}))
            symbolic_auth = tuple(sorted({f"AUTH_REF:{name}:{kind}" for name, kind in auth}))
            if complex_types:
                held.append(
                    HeldSchemaOperation(
                        source_op_id,
                        method,
                        path,
                        f"COMPLEX_AUTH_REQUIRES_PURPOSE_BUILT_ADAPTER:{','.join(complex_types)}",
                        symbolic_auth,
                    )
                )
                continue

            try:
                input_schema, sensitive_fields, parameter_auth = self._input_schema(spec, path_item, operation)
                symbolic_auth = tuple(sorted(set(symbolic_auth) | set(parameter_auth)))
                output_schema = self._output_schema(spec, operation)
            except ValueError as exc:
                held.append(HeldSchemaOperation(source_op_id, method, path, str(exc), symbolic_auth))
                continue

            semantic = str(operation.get("x-omega-semantic-operation") or _semantic_for_method(method)).strip().upper()
            if not semantic:
                semantic = _semantic_for_method(method)
            effect = _effect_for_method(method)
            base = _normalise_id(source_op_id)
            adapter_id = base if base_counts[base] == 1 else f"{base}__{_sha({'method': method, 'path': path})[:8]}"
            capability_id = f"UCC-OAS-{_sha({'source': source_id, 'method': method, 'path': path, 'operation': source_op_id})[:20].upper()}"
            description = str(operation.get("description") or operation.get("summary") or f"{method} {path}")
            contract = UniversalCapabilityContract(
                capability_id=capability_id,
                name=source_op_id,
                description=description,
                input_schema=input_schema,
                output_schema=output_schema,
                effect_class=effect,
                authority_ceiling="A1_INTERNAL" if effect == EffectClass.READ else "A2_EFFECT",
                privacy_class=str(operation.get("x-omega-privacy-class") or self.default_privacy_class),
                rollback_required=effect != EffectClass.READ,
                proof_required=("semantic_readback",) if effect == EffectClass.READ else ("rollback", "semantic_readback"),
                metadata={
                    "omega.schema_source_id": source_id,
                    "omega.semantic_operation": semantic,
                    "omega.http.method": method,
                    "omega.http.path": path,
                    "omega.symbolic_auth_requirements": list(symbolic_auth),
                    "omega.sensitive_fields": sorted(sensitive_fields),
                    "omega.schema_compiler_version": self.VERSION,
                    "omega.portable_projection_only": True,
                    "omega.zero_dilution": True,
                },
            )
            contract.validate()
            schema_hash = _sha({"input": input_schema, "output": output_schema})
            compiled.append(
                CompiledAdapterOperation(
                    adapter_operation_id=adapter_id,
                    source_operation_id=source_op_id,
                    method=method,
                    path=path,
                    tags=tuple(sorted(str(t) for t in operation.get("tags", []) if str(t).strip())),
                    effect_class=effect,
                    semantic_operation=semantic,
                    contract=contract,
                    symbolic_auth_requirements=symbolic_auth,
                    sensitive_fields=tuple(sorted(sensitive_fields)),
                    schema_hash=schema_hash,
                )
            )

        compiled.sort(key=lambda x: (x.path, x.method, x.adapter_operation_id))
        held.sort(key=lambda x: (x.path, x.method, x.source_operation_id))
        payload = {
            "source_id": source_id,
            "openapi_version": version,
            "operations": [asdict(x) for x in compiled],
            "held": [asdict(x) for x in held],
            "filtered_out": filtered,
            "compiler_version": self.VERSION,
        }
        elapsed = round((time.perf_counter() - start) * 1000.0, 6)
        return SchemaCompileResult(
            source_id,
            version,
            tuple(compiled),
            tuple(held),
            filtered,
            self.VERSION,
            elapsed,
            _sha(payload),
        )

    def compile_interop(
        self,
        spec: Mapping[str, Any],
        *,
        source_id: str,
        mission_id: str,
        trace_id: str = "",
        include_tags: Iterable[str] = (),
        include_operation_ids: Iterable[str] = (),
    ) -> SchemaInteropResult:
        schema_result = self.compile(
            spec,
            source_id=source_id,
            include_tags=include_tags,
            include_operation_ids=include_operation_ids,
        )
        bundles = tuple(
            OmegaInteropSpine.compile(operation.contract, mission_id=mission_id, trace_id=trace_id)
            for operation in schema_result.operations
        )
        payload = {
            "schema_result_hash": schema_result.result_hash,
            "bundles": [bundle.bundle_sha256 for bundle in bundles],
        }
        return SchemaInteropResult(schema_result, bundles, _sha(payload))

    def _auth_requirements(
        self,
        operation: Mapping[str, Any],
        root_security: Any,
        components: Mapping[str, Any],
    ) -> tuple[tuple[str, str], ...]:
        security = operation.get("security", root_security)
        if security == []:
            return ()
        schemes = components.get("securitySchemes", {}) if isinstance(components, Mapping) else {}
        results: set[tuple[str, str]] = set()
        if isinstance(security, list):
            for requirement in security:
                if not isinstance(requirement, Mapping):
                    continue
                for name in requirement.keys():
                    detail = schemes.get(name, {}) if isinstance(schemes, Mapping) else {}
                    kind = str(detail.get("type", "unknown")) if isinstance(detail, Mapping) else "unknown"
                    results.add((str(name), kind))
        return tuple(sorted(results))

    def _resolve_ref(self, spec: Mapping[str, Any], ref: str) -> Any:
        if not ref.startswith("#/"):
            raise ValueError("EXTERNAL_SCHEMA_REF_REQUIRES_PURPOSE_BUILT_RESOLVER")
        node: Any = spec
        for raw in ref[2:].split("/"):
            key = raw.replace("~1", "/").replace("~0", "~")
            if not isinstance(node, Mapping) or key not in node:
                raise ValueError("OPENAPI_LOCAL_REF_NOT_FOUND")
            node = node[key]
        return node

    def _sanitize_schema(
        self,
        spec: Mapping[str, Any],
        schema: Any,
        *,
        field_name: str = "",
        seen: frozenset[str] = frozenset(),
    ) -> Any:
        if not isinstance(schema, Mapping):
            return copy.deepcopy(schema)
        if "$ref" in schema:
            ref = str(schema["$ref"])
            if ref in seen:
                return {"type": "object", "x-omega-recursive-ref": ref}
            resolved = self._resolve_ref(spec, ref)
            return self._sanitize_schema(spec, resolved, field_name=field_name, seen=seen | {ref})
        out: dict[str, Any] = {}
        for key in sorted(schema.keys()):
            if key in {"example", "examples", "default"}:
                continue
            value = schema[key]
            if key == "properties" and isinstance(value, Mapping):
                out[key] = {
                    str(name): self._sanitize_schema(spec, sub, field_name=str(name), seen=seen)
                    for name, sub in sorted(value.items())
                }
                continue
            if key in {"items", "additionalProperties", "not"}:
                out[key] = self._sanitize_schema(spec, value, field_name=field_name, seen=seen)
                continue
            if key in {"oneOf", "anyOf", "allOf"} and isinstance(value, list):
                out[key] = [self._sanitize_schema(spec, part, field_name=field_name, seen=seen) for part in value]
                continue
            out[key] = copy.deepcopy(value)
        if field_name and _SECRET_NAME.search(field_name):
            out.pop("example", None)
            out.pop("examples", None)
            out.pop("default", None)
            out["x-omega-secret-reference-required"] = True
        return out

    def _parameters(
        self,
        spec: Mapping[str, Any],
        path_item: Mapping[str, Any],
        operation: Mapping[str, Any],
    ) -> tuple[list[Mapping[str, Any]], set[str], set[str]]:
        merged: dict[tuple[str, str], Mapping[str, Any]] = {}
        for group in (path_item.get("parameters", []), operation.get("parameters", [])):
            if not isinstance(group, list):
                continue
            for parameter in group:
                if not isinstance(parameter, Mapping):
                    continue
                if "$ref" in parameter:
                    parameter = self._resolve_ref(spec, str(parameter["$ref"]))
                if not isinstance(parameter, Mapping):
                    continue
                name = str(parameter.get("name", ""))
                location = str(parameter.get("in", ""))
                if name and location:
                    merged[(location, name)] = parameter
        params: list[Mapping[str, Any]] = []
        auth_fields: set[str] = set()
        sensitive: set[str] = set()
        for (location, name), parameter in sorted(merged.items()):
            if _AUTH_NAME.search(name):
                auth_fields.add(f"{location}.{name}")
                sensitive.add(f"{location}.{name}")
                continue
            if _SECRET_NAME.search(name):
                sensitive.add(f"{location}.{name}")
            params.append(parameter)
        return params, auth_fields, sensitive

    def _input_schema(
        self,
        spec: Mapping[str, Any],
        path_item: Mapping[str, Any],
        operation: Mapping[str, Any],
    ) -> tuple[dict[str, Any], set[str], tuple[str, ...]]:
        params, auth_fields, sensitive = self._parameters(spec, path_item, operation)
        sections: dict[str, dict[str, Any]] = {}
        required_sections: list[str] = []
        for parameter in params:
            location = str(parameter.get("in"))
            name = str(parameter.get("name"))
            schema = self._sanitize_schema(spec, parameter.get("schema", {"type": "string"}), field_name=name)
            section = sections.setdefault(location, {"type": "object", "properties": {}, "required": []})
            section["properties"][name] = schema
            if parameter.get("required") is True:
                section["required"].append(name)
            if _SECRET_NAME.search(name):
                sensitive.add(f"{location}.{name}")
        properties: dict[str, Any] = {}
        for location, section in sorted(sections.items()):
            if not section["required"]:
                section.pop("required")
            else:
                section["required"] = sorted(section["required"])
            properties[location] = section
            if location == "path" and "required" in section:
                required_sections.append(location)

        request_body = operation.get("requestBody")
        if isinstance(request_body, Mapping):
            if "$ref" in request_body:
                request_body = self._resolve_ref(spec, str(request_body["$ref"]))
            content = request_body.get("content", {}) if isinstance(request_body, Mapping) else {}
            media = None
            if isinstance(content, Mapping):
                media = content.get("application/json") or next(
                    (value for key, value in sorted(content.items()) if key.endswith("+json")),
                    None,
                )
            if isinstance(media, Mapping):
                body_schema = self._sanitize_schema(spec, media.get("schema", {"type": "object"}))
                properties["body"] = body_schema
                if request_body.get("required") is True:
                    required_sections.append("body")
                sensitive.update(self._sensitive_paths(body_schema, prefix="body"))
            elif request_body.get("required") is True:
                raise ValueError("UNSUPPORTED_REQUIRED_REQUEST_MEDIA_REQUIRES_PURPOSE_BUILT_ADAPTER")

        result: dict[str, Any] = {"type": "object", "properties": properties}
        if required_sections:
            result["required"] = sorted(set(required_sections))
        parameter_auth = tuple(sorted(f"PARAM_AUTH_REF:{field}" for field in auth_fields))
        return result, sensitive, parameter_auth

    def _output_schema(self, spec: Mapping[str, Any], operation: Mapping[str, Any]) -> dict[str, Any]:
        responses = operation.get("responses", {})
        if not isinstance(responses, Mapping) or not responses:
            return {"type": "object", "x-omega-response-unmodeled": True}
        preferred_keys = [str(key) for key in responses.keys() if str(key).startswith("2")]
        key = sorted(preferred_keys)[0] if preferred_keys else (
            "default" if "default" in responses else sorted(str(k) for k in responses.keys())[0]
        )
        response = responses[key]
        if isinstance(response, Mapping) and "$ref" in response:
            response = self._resolve_ref(spec, str(response["$ref"]))
        content = response.get("content", {}) if isinstance(response, Mapping) else {}
        media = None
        if isinstance(content, Mapping):
            media = content.get("application/json") or next(
                (value for media_type, value in sorted(content.items()) if media_type.endswith("+json")),
                None,
            )
        if isinstance(media, Mapping):
            return self._sanitize_schema(spec, media.get("schema", {"type": "object"}))
        return {"type": "object", "x-omega-response-unmodeled": True, "x-omega-http-status": key}

    def _sensitive_paths(self, schema: Any, *, prefix: str) -> set[str]:
        found: set[str] = set()
        if not isinstance(schema, Mapping):
            return found
        properties = schema.get("properties")
        if isinstance(properties, Mapping):
            for name, sub in properties.items():
                path = f"{prefix}.{name}"
                if _SECRET_NAME.search(str(name)):
                    found.add(path)
                found.update(self._sensitive_paths(sub, prefix=path))
        for key in ("items", "additionalProperties"):
            if key in schema:
                found.update(self._sensitive_paths(schema[key], prefix=prefix))
        for key in ("oneOf", "anyOf", "allOf"):
            parts = schema.get(key, []) if isinstance(schema.get(key), list) else []
            for part in parts:
                found.update(self._sensitive_paths(part, prefix=prefix))
        return found
