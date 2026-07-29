#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
FONT = ImageFont.load_default()


def box(draw, xy, title, lines, fill, outline=(30, 30, 30)):
    x1, y1, x2, y2 = xy
    draw.rounded_rectangle(xy, radius=14, fill=fill, outline=outline, width=2)
    draw.text((x1 + 12, y1 + 10), title, font=FONT, fill=(0, 0, 0))
    y = y1 + 30
    for line in lines:
        draw.text((x1 + 12, y), line, font=FONT, fill=(20, 20, 20))
        y += 16


def arrow(draw, start, end):
    draw.line([start, end], fill=(40, 40, 40), width=3)
    x, y = end
    draw.polygon([(x, y), (x - 8, y - 5), (x - 8, y + 5)], fill=(40, 40, 40))


def architecture():
    image = Image.new("RGB", (1500, 920), "white")
    d = ImageDraw.Draw(image)
    d.text((30, 20), "MODISA–EvidenceOps Sovereign Legal Intelligence OS v2", font=FONT, fill=(0, 0, 0))
    box(d, (540, 65, 960, 145), "HUMAN AUTHORITY PLANE", ["Owner / authorised counsel", "Exact approvals and legal responsibility"], (230, 240, 255))
    arrow(d, (750, 145), (750, 190))
    box(d, (540, 190, 960, 285), "CHIEF COUNSEL + SPECIALIST CHAMBERS", ["GPT-5.6 Sol / Terra routing", "Agents-as-tools; no independent external effect"], (236, 250, 236))
    arrow(d, (540, 238), (470, 238)); arrow(d, (960, 238), (1030, 238))
    box(d, (40, 175, 470, 300), "DETERMINISTIC CONTROL CORE", ["Proof ledger", "Claim/evidence/authority graph", "Release policy", "Approval/action state machine"], (255, 244, 220))
    box(d, (1030, 175, 1460, 300), "INDEPENDENT ADVERSARIAL COUNCIL", ["Applicant / respondent", "Neutral adjudicator", "Evidence / authority / procedure", "Inspector-General"], (255, 232, 232))
    arrow(d, (750, 285), (750, 340))
    box(d, (70, 360, 440, 520), "EVIDENCE PLANE", ["AES-256-GCM vault", "SHA-256 identity", "Recursive EML/ZIP inventory", "Prompt-injection tainting", "Resource-abuse limits"], (242, 242, 255))
    box(d, (565, 360, 935, 520), "MATTER + LEGAL KNOWLEDGE GRAPH", ["Claims and legal elements", "Primary-law versions", "Authorities and treatment", "Contrary evidence", "Deadlines and remedies"], (240, 252, 244))
    box(d, (1060, 360, 1430, 520), "CONNECTOR + ACTION PLANE", ["Capability contracts", "Secret-manager references", "Current health canaries", "Provider execution", "Independent readback"], (255, 245, 238))
    arrow(d, (440, 440), (565, 440)); arrow(d, (935, 440), (1060, 440))
    arrow(d, (750, 520), (750, 570))
    box(d, (400, 570, 1100, 690), "PROOF-BOUND RELEASE ENGINE", ["Verifies signed proof chain and mission scope", "Requires evidence, law, contrary search, forum, privacy and council proofs", "External claims require approval + execution + readback", "Outputs RELEASE / CAVEAT / HOLD / REJECT"], (255, 253, 220))
    arrow(d, (750, 690), (750, 735))
    box(d, (400, 735, 1100, 835), "DURABLE WORKFLOW + CONTINUITY", ["Database leases, retries, approval waits and restart recovery", "Snapshot, isolated restore and chain-verification canary"], (235, 245, 250))
    image.save(DOCS / "architecture.png")


def release_flow():
    image = Image.new("RGB", (1600, 720), "white")
    d = ImageDraw.Draw(image)
    d.text((30, 20), "Proof-bound release flow", font=FONT, fill=(0, 0, 0))
    stages = [
        ("MISSION", ["Scope", "risk", "forum"]),
        ("SOURCES", ["Read", "complete", "hash"]),
        ("ANALYSIS", ["Claims", "law", "contrary"]),
        ("COUNCIL", ["Independent", "7 roles"]),
        ("VERIFY", ["Proof chain", "claim links"]),
        ("DECIDE", ["Release", "hold", "reject"]),
    ]
    x = 35
    boxes = []
    for idx, (title, lines) in enumerate(stages):
        xy = (x, 120, x + 215, 250)
        boxes.append(xy)
        box(d, xy, title, lines, (240 + (idx % 2) * 8, 245, 250 - (idx % 2) * 8))
        x += 260
    for a, b in zip(boxes, boxes[1:]):
        arrow(d, (a[2], 185), (b[0], 185))
    box(d, (360, 360, 750, 520), "CONSEQUENTIAL ACTION BRANCH", ["Exact parameter digest", "Matching approval", "Connector canary", "Provider action ID", "Provider readback"], (255, 241, 230))
    box(d, (850, 360, 1240, 520), "FAIL-CLOSED STATES", ["HOLD_FOR_EVIDENCE", "HOLD_FOR_COUNCIL", "HOLD_FOR_APPROVAL", "REJECT_FALSE_CERTAINTY", "EXECUTION_UNCERTAIN"], (255, 232, 232))
    arrow(d, (700, 250), (555, 360)); arrow(d, (1000, 250), (1045, 360))
    d.text((400, 600), "A model cannot replace any proof, approval, provider receipt or independent readback.", font=FONT, fill=(0, 0, 0))
    image.save(DOCS / "release-flow.png")


if __name__ == "__main__":
    DOCS.mkdir(parents=True, exist_ok=True)
    architecture()
    release_flow()
    print(DOCS / "architecture.png")
    print(DOCS / "release-flow.png")
