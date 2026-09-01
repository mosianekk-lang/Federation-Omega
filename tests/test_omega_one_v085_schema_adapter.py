import json
import unittest

from omega_one.interop import EffectClass
from omega_one.schema_adapter import SchemaFirstAdapterCompiler


def petstore_spec():
    return {
        "openapi": "3.1.0",
        "info": {"title": "Tiny Pets", "version": "1"},
        "components": {
            "schemas": {
                "Pet": {
                    "type": "object",
                    "required": ["id", "status"],
                    "properties": {
                        "id": {"type": "integer"},
                        "status": {"type": "string", "enum": ["new", "ready"]},
                        "api_key": {"type": "string", "example": "SUPER-SECRET-VALUE"},
                        "mode": {"oneOf": [{"type": "string"}, {"type": "integer"}]},
                    },
                }
            },
            "securitySchemes": {
                "ApiKeyAuth": {"type": "apiKey", "in": "header", "name": "X-API-Key"},
                "OAuth": {
                    "type": "oauth2",
                    "flows": {
                        "clientCredentials": {
                            "tokenUrl": "https://example.invalid/token",
                            "scopes": {},
                        }
                    },
                },
            },
        },
        "security": [{"ApiKeyAuth": []}],
        "paths": {
            "/pets/{petId}": {
                "parameters": [
                    {
                        "name": "petId",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "integer"},
                    }
                ],
                "get": {
                    "operationId": "getPet",
                    "tags": ["pets"],
                    "responses": {
                        "200": {
                            "description": "ok",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/Pet"}
                                }
                            },
                        }
                    },
                },
                "patch": {
                    "operationId": "updatePet",
                    "tags": ["pets"],
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/Pet"}
                            }
                        },
                    },
                    "responses": {
                        "200": {
                            "description": "ok",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/Pet"}
                                }
                            },
                        }
                    },
                },
            },
            "/admin": {
                "post": {
                    "operationId": "adminAction",
                    "security": [{"OAuth": []}],
                    "responses": {"200": {"description": "ok"}},
                }
            },
        },
    }


class SchemaFirstAdapterTests(unittest.TestCase):
    def test_compiles_openapi_into_ucc_without_execution_authority(self):
        result = SchemaFirstAdapterCompiler().compile(petstore_spec(), source_id="tiny-pets")
        self.assertEqual(len(result.operations), 2)
        self.assertEqual(len(result.held), 1)
        get_op = next(x for x in result.operations if x.source_operation_id == "getPet")
        patch_op = next(x for x in result.operations if x.source_operation_id == "updatePet")
        self.assertEqual(get_op.effect_class, EffectClass.READ)
        self.assertEqual(get_op.contract.authority_ceiling, "A1_INTERNAL")
        self.assertEqual(get_op.semantic_operation, "READ_API_RESOURCE")
        self.assertFalse(get_op.contract.rollback_required)
        self.assertEqual(patch_op.effect_class, EffectClass.WRITE)
        self.assertEqual(patch_op.contract.authority_ceiling, "A2_EFFECT")
        self.assertTrue(patch_op.contract.rollback_required)
        self.assertTrue(result.held[0].reason.startswith("COMPLEX_AUTH_REQUIRES_PURPOSE_BUILT_ADAPTER"))

    def test_ref_enum_oneof_and_secret_sanitization_are_preserved_safely(self):
        result = SchemaFirstAdapterCompiler().compile(petstore_spec(), source_id="tiny-pets")
        patch = next(x for x in result.operations if x.source_operation_id == "updatePet")
        body = patch.contract.input_schema["properties"]["body"]
        self.assertEqual(body["properties"]["status"]["enum"], ["new", "ready"])
        self.assertEqual(len(body["properties"]["mode"]["oneOf"]), 2)
        self.assertTrue(body["properties"]["api_key"]["x-omega-secret-reference-required"])
        blob = json.dumps(result, default=lambda x: x.__dict__, sort_keys=True)
        self.assertNotIn("SUPER-SECRET-VALUE", blob)
        self.assertIn("body.api_key", patch.sensitive_fields)

    def test_symbolic_auth_is_retained_without_raw_secret(self):
        result = SchemaFirstAdapterCompiler().compile(petstore_spec(), source_id="tiny-pets")
        get_op = next(x for x in result.operations if x.source_operation_id == "getPet")
        self.assertEqual(get_op.symbolic_auth_requirements, ("AUTH_REF:ApiKeyAuth:apiKey",))
        self.assertNotIn("X-API-Key", json.dumps(get_op.contract.input_schema))

    def test_operation_collision_has_deterministic_suffix(self):
        spec = petstore_spec()
        spec["paths"]["/other"] = {
            "get": {"operationId": "getPet", "responses": {"200": {"description": "ok"}}}
        }
        compiler = SchemaFirstAdapterCompiler()
        first = compiler.compile(spec, source_id="tiny-pets")
        second = compiler.compile(spec, source_id="tiny-pets")
        ids_first = [x.adapter_operation_id for x in first.operations]
        ids_second = [x.adapter_operation_id for x in second.operations]
        self.assertEqual(ids_first, ids_second)
        self.assertEqual(len(set(ids_first)), len(ids_first))
        self.assertTrue(all(x.startswith("getPet__") for x in ids_first if x.startswith("getPet")))
        self.assertEqual(first.result_hash, second.result_hash)

    def test_filters_tags_and_operation_ids(self):
        compiler = SchemaFirstAdapterCompiler()
        by_tag = compiler.compile(petstore_spec(), source_id="tiny", include_tags=("pets",))
        self.assertEqual({x.source_operation_id for x in by_tag.operations}, {"getPet", "updatePet"})
        self.assertFalse(by_tag.held)
        by_id = compiler.compile(
            petstore_spec(), source_id="tiny", include_operation_ids=("getPet",)
        )
        self.assertEqual([x.source_operation_id for x in by_id.operations], ["getPet"])

    def test_external_ref_fails_closed_to_held_operation(self):
        spec = {
            "openapi": "3.0.3",
            "paths": {
                "/x": {
                    "get": {
                        "operationId": "x",
                        "responses": {
                            "200": {
                                "description": "ok",
                                "content": {
                                    "application/json": {
                                        "schema": {"$ref": "https://example.invalid/schema.json"}
                                    }
                                },
                            }
                        },
                    }
                }
            },
        }
        result = SchemaFirstAdapterCompiler().compile(spec, source_id="external-ref")
        self.assertFalse(result.operations)
        self.assertEqual(result.held[0].reason, "EXTERNAL_SCHEMA_REF_REQUIRES_PURPOSE_BUILT_RESOLVER")

    def test_operation_security_empty_overrides_root_security(self):
        spec = petstore_spec()
        spec["paths"]["/pets/{petId}"]["get"]["security"] = []
        result = SchemaFirstAdapterCompiler().compile(spec, source_id="tiny-pets")
        get_op = next(x for x in result.operations if x.source_operation_id == "getPet")
        self.assertEqual(get_op.symbolic_auth_requirements, ())

    def test_extension_semantic_operation_is_honored(self):
        spec = petstore_spec()
        spec["paths"]["/pets/{petId}"]["get"]["x-omega-semantic-operation"] = "FETCH_PET_EVIDENCE"
        result = SchemaFirstAdapterCompiler().compile(spec, source_id="tiny-pets")
        get_op = next(x for x in result.operations if x.source_operation_id == "getPet")
        self.assertEqual(get_op.semantic_operation, "FETCH_PET_EVIDENCE")
        self.assertEqual(get_op.contract.metadata["omega.semantic_operation"], "FETCH_PET_EVIDENCE")

    def test_invalid_openapi_rejected(self):
        with self.assertRaisesRegex(ValueError, "OPENAPI_3_X_REQUIRED"):
            SchemaFirstAdapterCompiler().compile({"swagger": "2.0", "paths": {}}, source_id="bad")

    def test_no_http_client_or_live_binding_is_exposed(self):
        compiler = SchemaFirstAdapterCompiler()
        self.assertFalse(hasattr(compiler, "execute"))
        self.assertFalse(hasattr(compiler, "request"))
        result = compiler.compile(petstore_spec(), source_id="tiny-pets")
        self.assertTrue(result.operations[0].contract.metadata["omega.portable_projection_only"])

    def test_contract_ids_are_source_bound(self):
        compiler = SchemaFirstAdapterCompiler()
        first = compiler.compile(petstore_spec(), source_id="a")
        second = compiler.compile(petstore_spec(), source_id="b")
        self.assertNotEqual(
            [x.contract.capability_id for x in first.operations],
            [x.contract.capability_id for x in second.operations],
        )

    def test_result_coverage_excludes_filtered_operations(self):
        result = SchemaFirstAdapterCompiler().compile(
            petstore_spec(), source_id="tiny", include_tags=("pets",)
        )
        self.assertEqual(result.coverage_ratio, 1.0)
        self.assertEqual(result.filtered_out, 1)

    def test_sensitive_business_password_is_retained_as_secret_reference(self):
        spec = {
            "openapi": "3.0.3",
            "paths": {
                "/login": {
                    "get": {
                        "operationId": "login",
                        "parameters": [
                            {"name": "username", "in": "query", "schema": {"type": "string"}},
                            {
                                "name": "password",
                                "in": "query",
                                "schema": {"type": "string", "example": "dont-copy-me"},
                            },
                        ],
                        "responses": {"200": {"description": "ok"}},
                    }
                }
            },
        }
        result = SchemaFirstAdapterCompiler().compile(spec, source_id="login")
        query = result.operations[0].contract.input_schema["properties"]["query"]["properties"]
        self.assertIn("password", query)
        self.assertTrue(query["password"]["x-omega-secret-reference-required"])
        self.assertNotIn("dont-copy-me", json.dumps(result, default=lambda x: x.__dict__, sort_keys=True))

    def test_explicit_api_key_parameter_becomes_symbolic_boundary_reference(self):
        spec = {
            "openapi": "3.0.3",
            "paths": {
                "/x": {
                    "get": {
                        "operationId": "x",
                        "parameters": [
                            {
                                "name": "api_key",
                                "in": "header",
                                "schema": {"type": "string", "example": "dont-copy"},
                            }
                        ],
                        "responses": {"200": {"description": "ok"}},
                    }
                }
            },
        }
        result = SchemaFirstAdapterCompiler().compile(spec, source_id="auth-param")
        operation = result.operations[0]
        self.assertIn("PARAM_AUTH_REF:header.api_key", operation.symbolic_auth_requirements)
        self.assertNotIn("api_key", json.dumps(operation.contract.input_schema))
        self.assertNotIn("dont-copy", json.dumps(operation, default=lambda x: x.__dict__))

    def test_required_non_json_body_is_held_for_purpose_built_adapter(self):
        spec = {
            "openapi": "3.0.3",
            "paths": {
                "/upload": {
                    "post": {
                        "operationId": "upload",
                        "requestBody": {
                            "required": True,
                            "content": {
                                "application/octet-stream": {
                                    "schema": {"type": "string", "format": "binary"}
                                }
                            },
                        },
                        "responses": {"200": {"description": "ok"}},
                    }
                }
            },
        }
        result = SchemaFirstAdapterCompiler().compile(spec, source_id="binary")
        self.assertFalse(result.operations)
        self.assertEqual(
            result.held[0].reason,
            "UNSUPPORTED_REQUIRED_REQUEST_MEDIA_REQUIRES_PURPOSE_BUILT_ADAPTER",
        )

    def test_schema_to_ucc_to_standards_preserves_zero_dilution(self):
        result = SchemaFirstAdapterCompiler().compile_interop(
            petstore_spec(), source_id="tiny-pets", mission_id="M-SCHEMA", trace_id="T-SCHEMA"
        )
        self.assertEqual(len(result.bundles), 2)
        for operation, bundle in zip(result.schema_result.operations, result.bundles):
            self.assertEqual(bundle.source_contract, operation.contract)
            self.assertTrue(bundle.zero_dilution_verified)
            self.assertTrue(bundle.mcp.tool["_meta"]["omega.zero_dilution"])
            self.assertEqual(bundle.otel.attributes["omega.trace.id"], "T-SCHEMA")
        write_bundle = next(
            bundle
            for operation, bundle in zip(result.schema_result.operations, result.bundles)
            if operation.effect_class == EffectClass.WRITE
        )
        self.assertTrue(write_bundle.source_contract.rollback_required)
        self.assertFalse(write_bundle.a2a.execution_ready)


if __name__ == "__main__":
    unittest.main()
