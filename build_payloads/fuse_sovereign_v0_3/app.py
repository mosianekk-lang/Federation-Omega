from __future__ import annotations

import argparse
import json
import tkinter as tk
from tkinter import ttk, messagebox

from fuse_sovereign.update import FuseUpdateClient, LLMUpdateBridge, UpdateError

VERSION = "0.3.0"


def self_test() -> dict:
    client = FuseUpdateClient(cache_dir=".fuse-selftest-cache", require_verified_commit=False)
    bridge = LLMUpdateBridge(client)
    assert bridge.client is client
    return {"version": VERSION, "update_bridge": "PASS", "mode": "DATA_ONLY_NO_EFFECT_AUTHORITY"}


def fetch_updates(require_verified: bool = True) -> dict:
    client = FuseUpdateClient(require_verified_commit=require_verified)
    return LLMUpdateBridge(client).fetch_context()


def launch_gui():
    root = tk.Tk()
    root.title(f"FUSE Sovereign Platform {VERSION}")
    root.geometry("900x620")

    outer = ttk.Frame(root, padding=18)
    outer.pack(fill="both", expand=True)
    ttk.Label(outer, text="FUSE Sovereign Capability Platform", font=("Segoe UI", 20, "bold")).pack(anchor="w")
    ttk.Label(outer, text="LLM Update Bridge • verified FUSE currentness • no remote effect authority").pack(anchor="w", pady=(4, 14))

    status = tk.StringVar(value="Update state: not fetched")
    ttk.Label(outer, textvariable=status).pack(anchor="w", pady=(0, 8))

    text = tk.Text(outer, wrap="word", font=("Consolas", 10))
    text.pack(fill="both", expand=True)

    def do_fetch():
        status.set("Update state: fetching...")
        root.update_idletasks()
        try:
            ctx = fetch_updates(require_verified=True)
            text.delete("1.0", "end")
            text.insert("1.0", json.dumps(ctx, indent=2, sort_keys=True))
            status.set(f"Update state: {ctx.get('freshness')} • sequence {ctx.get('sequence')} • commit {ctx.get('source_commit','')[:12]}")
        except Exception as exc:
            status.set(f"Update state: rejected • {exc}")
            messagebox.showerror("FUSE Update Rejected", str(exc))

    buttons = ttk.Frame(outer)
    buttons.pack(fill="x", pady=(12, 0))
    ttk.Button(buttons, text="Fetch Verified FUSE Updates", command=do_fetch).pack(side="left")
    ttk.Button(buttons, text="Exit", command=root.destroy).pack(side="right")

    root.mainloop()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--fetch-updates", action="store_true")
    parser.add_argument("--allow-unverified-commit", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        print(json.dumps(self_test(), sort_keys=True))
        return 0
    if args.fetch_updates:
        try:
            print(json.dumps(fetch_updates(require_verified=not args.allow_unverified_commit), indent=2, sort_keys=True))
            return 0
        except UpdateError as exc:
            print(json.dumps({"state": "REJECTED", "error": str(exc)}, sort_keys=True))
            return 2
    launch_gui()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
