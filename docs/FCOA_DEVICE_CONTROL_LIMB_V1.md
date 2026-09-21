# FCOA Device-Control Limb v1

The existing FCOA-Ω identity gains a FUSE-owned Windows device-control limb.

Capabilities: screen capture, cursor/foreground readback, pointer move/click/scroll, keyboard key/text injection, short-lived mission/device/effect leases, optional foreground-window allowlists, hash-chained audit events, pause and emergency stop.

Virtual surfaces use semantic/direct API or browser/VM adapters first. Physical desktop input is a fallback or explicit route when GUI interaction is required.

Security boundaries: localhost only; host bootstrap secret excluded from model context; consequential external effects need a separate mission authority receipt; no Windows secure-desktop/UAC bypass; no credential fabrication; no foreign-fence overwrite.

Build proof: Go policy/audit court 10/10 PASS; deterministic windows/amd64 PE32+ GUI helper built. Source ZIP SHA-256 7315aab34e5fcbf94db09edf59f5279eda974c15cb854871efa0212080c56a81. Helper EXE SHA-256 c84d04b34a3d2c8106ab1febfc7dfa9d8e62aceba746117bde177d877177b4b8.

Truth boundary: owner PC MosianeKK-LPT is presently offline to the authorized remote relay, so live physical input on that actual device is not yet claimed. This capability is OS-level Windows input injection; true USB-HID/KVM hardware emulation remains a separate optional hardware limb.
