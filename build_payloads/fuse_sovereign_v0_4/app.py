from __future__ import annotations

import argparse
from dataclasses import asdict
import json
import os
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog

from fuse_sovereign import (
    CapabilityAdvertisement,
    FCOABridge,
    FuseUpdateClient,
    LLMGateway,
    LLMGatewayError,
    LLMUpdateBridge,
    OpenAICompatibleHTTPProvider,
    SovereignEngine,
    UpdateError,
)

VERSION = "0.4.0"


def build_update_bridge(require_verified: bool = True) -> LLMUpdateBridge:
    return LLMUpdateBridge(FuseUpdateClient(require_verified_commit=require_verified))


def build_llm_gateway() -> LLMGateway:
    gateway = LLMGateway([])
    base_url = os.environ.get("FUSE_LLM_BASE_URL", "").strip()
    model = os.environ.get("FUSE_LLM_MODEL", "").strip()
    if base_url and model:
        gateway.register(OpenAICompatibleHTTPProvider(
            provider_id=os.environ.get("FUSE_LLM_PROVIDER_ID", "configured-llm"),
            base_url=base_url,
            default_model=model,
            token_loader=lambda: os.environ.get("FUSE_LLM_API_TOKEN") or None,
        ))
    return gateway


def build_engine() -> SovereignEngine:
    engine = SovereignEngine([
        CapabilityAdvertisement("fuse-update-local", ("fuse.update.read",), local=True, private=True),
        CapabilityAdvertisement("platform-status-local", ("platform.status.read",), local=True, private=True),
    ])
    engine.bind_handler("fuse-update-local", lambda task: build_update_bridge().fetch_context())
    engine.bind_handler("platform-status-local", lambda task: {"version": VERSION, "mode": "FUSE_SOVEREIGN"})
    return engine


def build_fcoa(require_verified: bool = True) -> FCOABridge:
    return FCOABridge(
        engine=build_engine(),
        llm_gateway=build_llm_gateway(),
        update_bridge=build_update_bridge(require_verified=require_verified),
    )


def self_test() -> dict:
    bridge = build_update_bridge(require_verified=False)
    assert bridge.client is not None
    fcoa = build_fcoa(require_verified=False)
    caps, _ = fcoa.capability_snapshot()
    assert "fuse.update.read" in caps
    return {
        "version": VERSION,
        "update_bridge": "PASS",
        "fcoa_bridge": "PASS",
        "fcoa_agent_id": fcoa.profile.agent_id,
        "llm_gateway": "PASS",
        "llm_provider_count": len(fcoa.llm_gateway.providers()),
        "mode": "MISSION_SCOPED_NO_AUTHORITY_INHERITANCE",
    }


def fetch_updates(require_verified: bool = True) -> dict:
    return build_update_bridge(require_verified=require_verified).fetch_context()


def fcoa_status(require_verified: bool = True) -> dict:
    fcoa = build_fcoa(require_verified=require_verified)
    snap = fcoa.bootstrap()
    return {
        "schema": "FCOA_PLATFORM_ACCESS_STATUS_V1",
        "version": VERSION,
        "agent_id": snap.agent_id,
        "work_plane_id": snap.work_plane_id,
        "passport_id": snap.passport_id,
        "bootstrap_digest": snap.digest,
        "fuse_update": dict(snap.fuse_update),
        "llm_providers": list(snap.llm_providers),
        "capabilities": list(snap.capabilities),
        "executors": list(snap.executors),
        "authority_boundary": snap.authority_boundary,
    }


def fcoa_think(prompt: str, *, require_verified: bool = True, model: str = "") -> dict:
    fcoa = build_fcoa(require_verified=require_verified)
    response = fcoa.think(
        request_id="FCOA-CLI-THINK-001",
        mission_id="MISSION-FCOA-INTERACTIVE-001",
        prompt=prompt,
        model=model or os.environ.get("FUSE_LLM_MODEL", ""),
    )
    return asdict(response)


def launch_gui():
    root = tk.Tk()
    root.title(f"FUSE Sovereign Platform {VERSION}")
    root.geometry("980x700")

    outer = ttk.Frame(root, padding=18)
    outer.pack(fill="both", expand=True)
    ttk.Label(outer, text="FUSE Sovereign Capability Platform", font=("Segoe UI", 20, "bold")).pack(anchor="w")
    ttk.Label(outer, text="FCOA-Ω • verified FUSE currentness • provider-neutral LLM gateway • governed execution").pack(anchor="w", pady=(4, 14))

    status = tk.StringVar(value="State: not fetched")
    ttk.Label(outer, textvariable=status).pack(anchor="w", pady=(0, 8))

    text = tk.Text(outer, wrap="word", font=("Consolas", 10))
    text.pack(fill="both", expand=True)

    def show(value):
        text.delete("1.0", "end")
        text.insert("1.0", json.dumps(value, indent=2, sort_keys=True, default=str))

    def do_updates():
        status.set("State: fetching verified FUSE updates...")
        root.update_idletasks()
        try:
            ctx = fetch_updates(True)
            show(ctx)
            status.set(f"FUSE update: {ctx.get('freshness')} • sequence {ctx.get('sequence')} • commit {ctx.get('source_commit','')[:12]}")
        except Exception as exc:
            status.set(f"FUSE update rejected: {exc}")
            messagebox.showerror("FUSE Update Rejected", str(exc))

    def do_fcoa_status():
        status.set("FCOA: bootstrapping...")
        root.update_idletasks()
        try:
            value = fcoa_status(True)
            show(value)
            status.set(f"FCOA: {value['authority_boundary']} • LLM providers {len(value['llm_providers'])} • capabilities {len(value['capabilities'])}")
        except Exception as exc:
            status.set(f"FCOA bootstrap rejected: {exc}")
            messagebox.showerror("FCOA Bootstrap Rejected", str(exc))

    def do_fcoa_think():
        prompt = simpledialog.askstring("FCOA Cognition", "Prompt for FCOA-Ω:", parent=root)
        if not prompt:
            return
        status.set("FCOA: invoking configured LLM...")
        root.update_idletasks()
        try:
            value = fcoa_think(prompt, require_verified=True)
            show(value)
            status.set(f"FCOA cognition: provider {value.get('provider_id')} • model {value.get('model')}")
        except LLMGatewayError as exc:
            status.set(f"FCOA LLM unavailable: {exc}")
            messagebox.showinfo("No Qualified LLM Provider", "No genuine LLM endpoint is currently bound. Configure FUSE_LLM_BASE_URL and FUSE_LLM_MODEL, then restart the app.")
        except Exception as exc:
            status.set(f"FCOA cognition rejected: {exc}")
            messagebox.showerror("FCOA Cognition Rejected", str(exc))

    buttons = ttk.Frame(outer)
    buttons.pack(fill="x", pady=(12, 0))
    ttk.Button(buttons, text="Fetch Verified FUSE Updates", command=do_updates).pack(side="left")
    ttk.Button(buttons, text="FCOA Access Status", command=do_fcoa_status).pack(side="left", padx=8)
    ttk.Button(buttons, text="FCOA Think", command=do_fcoa_think).pack(side="left")
    ttk.Button(buttons, text="Exit", command=root.destroy).pack(side="right")

    root.mainloop()


def _emit(value: dict, output_file: str = "") -> None:
    payload = json.dumps(value, indent=2, sort_keys=True, default=str)
    if output_file:
        with open(output_file, "w", encoding="utf-8") as handle:
            handle.write(payload + "\n")
    print(payload)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--fetch-updates", action="store_true")
    parser.add_argument("--fcoa-status", action="store_true")
    parser.add_argument("--fcoa-think", type=str, default="")
    parser.add_argument("--model", type=str, default="")
    parser.add_argument("--allow-unverified-commit", action="store_true")
    parser.add_argument("--output-file", type=str, default="")
    args = parser.parse_args()
    require_verified = not args.allow_unverified_commit
    if args.self_test:
        _emit(self_test(), args.output_file)
        return 0
    if args.fetch_updates:
        try:
            _emit(fetch_updates(require_verified), args.output_file)
            return 0
        except UpdateError as exc:
            _emit({"state": "REJECTED", "error": str(exc)}, args.output_file)
            return 2
    if args.fcoa_status:
        try:
            _emit(fcoa_status(require_verified), args.output_file)
            return 0
        except Exception as exc:
            _emit({"state": "REJECTED", "error": str(exc)}, args.output_file)
            return 2
    if args.fcoa_think:
        try:
            _emit(fcoa_think(args.fcoa_think, require_verified=require_verified, model=args.model), args.output_file)
            return 0
        except LLMGatewayError as exc:
            _emit({"state": "NO_QUALIFIED_LLM_PROVIDER", "error": str(exc)}, args.output_file)
            return 3
    launch_gui()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
