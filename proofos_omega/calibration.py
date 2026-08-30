from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from .policy_loader import _load_policy
from .core import (
    ProofPolicy,
    ProofRunner,
    RunnerError,
    load_manifest,
    proof_key_for_test,
    sha256_bytes,
    sha256_json,
)


class CalibrationError(RuntimeError):
    pass


@dataclass(frozen=True)
class ShadowResult:
    test_id: str
    status: str
    returncode: int
    elapsed_seconds: float
    proof_key: str
    stdout_sha256: str
    stderr_sha256: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "test_id": self.test_id,
            "status": self.status,
            "returncode": self.returncode,
            "elapsed_seconds": round(self.elapsed_seconds, 6),
            "proof_key": self.proof_key,
            "stdout_sha256": self.stdout_sha256,
            "stderr_sha256": self.stderr_sha256,
        }


@dataclass(frozen=True)
class CalibrationReceipt:
    schema: str
    version: str
    manifest_sha256: str
    config_sha256: str
    selected_sentinels: tuple[str, ...]
    results: tuple[ShadowResult, ...]
    escape_candidates: tuple[Mapping[str, Any], ...]
    status: str
    receipt_sha256: str

    def deterministic_payload(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "version": self.version,
            "manifest_sha256": self.manifest_sha256,
            "config_sha256": self.config_sha256,
            "selected_sentinels": list(self.selected_sentinels),
            "results": [r.to_dict() for r in self.results],
            "escape_candidates": [dict(x) for x in self.escape_candidates],
            "status": self.status,
        }

    def to_dict(self) -> dict[str, Any]:
        payload = self.deterministic_payload()
        payload["receipt_sha256"] = self.receipt_sha256
        return payload


class CalibrationConfig:
    def __init__(self, raw: Mapping[str, Any]):
        self.raw = json.loads(json.dumps(raw))
        if self.raw.get("schema") != "FEDERATION-PROOFOS-SHADOW-CALIBRATION-V1":
            raise CalibrationError("unsupported calibration schema")
        self.version = str(self.raw.get("version", ""))
        if self.raw.get("authority_ceiling") != "A1_INTERNAL":
            raise CalibrationError("calibration may not expand authority")
        if self.raw.get("external_effect") is not False:
            raise CalibrationError("calibration must remain effect-free")
        self.percent = int(self.raw.get("omitted_proof_sample_percent", 0))
        self.max_sentinels = int(self.raw.get("max_sentinels", 0))
        self.exclude_test_ids = frozenset(str(x) for x in self.raw.get("exclude_test_ids", []))
        if not 0 <= self.percent <= 100:
            raise CalibrationError("invalid sample percent")
        if not 0 <= self.max_sentinels <= 25:
            raise CalibrationError("invalid max sentinels")
        self.sha256 = sha256_json(self.raw)

    @classmethod
    def from_path(cls, path: str | Path) -> "CalibrationConfig":
        return cls(json.loads(Path(path).read_text(encoding="utf-8")))


class ShadowCalibrator:
    """Non-blocking selector falsification over omitted registered proof groups.

    A sentinel failure is evidence that the selector may have missed a dependency,
    not permission to silently fail a PR and not proof of a causal graph edge.
    """

    def __init__(self, *, policy: ProofPolicy, config: CalibrationConfig, repo_root: str | Path):
        self.policy = policy
        self.config = config
        self.repo_root = Path(repo_root)
        self.runner = ProofRunner(policy=policy, repo_root=self.repo_root)

    def choose(self, manifest) -> tuple[str, ...]:
        omitted = {x.test_id for x in manifest.omitted_tests}
        candidates = sorted(
            tid
            for tid in omitted
            if tid in self.policy.tests
            and self.policy.tests[tid].sentinel_eligible
            and tid not in self.config.exclude_test_ids
            and not self.policy.tests[tid].hard_always_run
        )
        if not candidates or self.config.percent <= 0 or self.config.max_sentinels <= 0:
            return ()
        count = min(
            self.config.max_sentinels,
            max(1, math.ceil(len(candidates) * self.config.percent / 100.0)),
        )
        seed = f"{manifest.manifest_sha256}:{self.config.sha256}"
        ranked = sorted(
            candidates,
            key=lambda tid: hashlib.sha256(f"{seed}:{tid}".encode()).hexdigest(),
        )
        return tuple(ranked[:count])

    def run(self, manifest) -> CalibrationReceipt:
        if not manifest.verify():
            raise RunnerError("manifest integrity failure")
        if manifest.policy_sha256 != self.policy.sha256:
            raise RunnerError("manifest/policy mismatch")

        selected = self.choose(manifest)
        results: list[ShadowResult] = []
        escapes: list[dict[str, Any]] = []
        runtime = self.runner.runtime_identity()

        for tid in selected:
            spec = self.policy.tests[tid]
            key = proof_key_for_test(
                repo_root=self.repo_root,
                manifest=manifest,
                policy=self.policy,
                spec=spec,
                runtime_identity={**runtime, "shadow_calibration": self.config.version},
            )
            if not self.runner._present(spec):
                status = "SKIPPED_NOT_PRESENT" if spec.optional_if_missing else "FAIL_NOT_PRESENT"
                rc = 0 if spec.optional_if_missing else 2
                result = ShadowResult(
                    tid,
                    status,
                    rc,
                    0.0,
                    key,
                    sha256_bytes(b""),
                    sha256_bytes(b"required shadow proof target not present" if rc else b""),
                )
            else:
                start = time.monotonic()
                try:
                    process = subprocess.run(
                        self.runner._argv(spec),
                        cwd=self.repo_root,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        timeout=spec.timeout_seconds,
                        check=False,
                        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
                    )
                    result = ShadowResult(
                        tid,
                        "PASS" if process.returncode == 0 else "FAIL",
                        process.returncode,
                        time.monotonic() - start,
                        key,
                        sha256_bytes(process.stdout),
                        sha256_bytes(process.stderr),
                    )
                except subprocess.TimeoutExpired as exc:
                    result = ShadowResult(
                        tid,
                        "FAIL_TIMEOUT",
                        124,
                        time.monotonic() - start,
                        key,
                        sha256_bytes(exc.stdout or b""),
                        sha256_bytes(exc.stderr or b""),
                    )
            results.append(result)
            if result.status not in {"PASS", "SKIPPED_NOT_PRESENT"}:
                escapes.append(
                    {
                        "test_id": tid,
                        "classification": "SELECTOR_ESCAPE_CANDIDATE",
                        "reason": "OMITTED_REGISTERED_PROOF_FAILED_IN_SHADOW",
                        "requires_confirmation": True,
                        "may_auto_block_current_admission": False,
                        "original_failure_class": spec.failure_class,
                        "original_block_scope": spec.block_scope,
                    }
                )

        status = "PASS_WITH_ESCAPE_CANDIDATE" if escapes else "PASS_NO_ESCAPE"
        payload = {
            "schema": "FEDERATION-PROOFOS-SHADOW-CALIBRATION-RECEIPT-V1",
            "version": "1.0.0",
            "manifest_sha256": manifest.manifest_sha256,
            "config_sha256": self.config.sha256,
            "selected_sentinels": list(selected),
            "results": [r.to_dict() for r in results],
            "escape_candidates": escapes,
            "status": status,
        }
        return CalibrationReceipt(
            payload["schema"],
            payload["version"],
            manifest.manifest_sha256,
            self.config.sha256,
            selected,
            tuple(results),
            tuple(escapes),
            status,
            sha256_json(payload),
        )


def _write_json(path: str | Path, payload: Mapping[str, Any]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="proofos-shadow-calibration")
    parser.add_argument("--policy", required=True)
    parser.add_argument("--config", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    try:
        policy = _load_policy(args.policy, args.repo_root)
        config = CalibrationConfig.from_path(args.config)
        manifest = load_manifest(args.manifest)
        receipt = ShadowCalibrator(policy=policy, config=config, repo_root=args.repo_root).run(manifest)
        _write_json(args.output, receipt.to_dict())
        print(
            "PROOFOS_SHADOW_CALIBRATION"
            f" status={receipt.status}"
            f" sentinels={len(receipt.selected_sentinels)}"
            f" escape_candidates={len(receipt.escape_candidates)}"
            f" receipt={receipt.receipt_sha256}"
        )
        return 0
    except Exception as exc:
        print(f"PROOFOS_SHADOW_CALIBRATION_ERROR {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
