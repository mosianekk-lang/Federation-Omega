from __future__ import annotations

"""Formation Network Intelligence v1.

Passive, evidence-bound device/network identity fusion for FUSE Formation.
No active exploitation, credential use, authority expansion, or provider effects.
"""

from dataclasses import dataclass, asdict
from enum import StrEnum
from hashlib import sha256
import ipaddress
import json
import math
from typing import Iterable


SCHEMA = "FUSE_FORMATION_NETWORK_INTELLIGENCE_V1"
VERSION = "1.0.0"
CONTRACT_ID = "FUSE-FORMATION-NETWORK-INTEL-001"


class EvidenceKind(StrEnum):
    ARP = "ARP"
    DHCP = "DHCP"
    DNS = "DNS"
    NETBIOS = "NETBIOS"
    MDNS = "MDNS"
    SSDP = "SSDP"
    SMB = "SMB"
    RPC = "RPC"
    RDP = "RDP"
    ROUTER = "ROUTER"
    SECURITY_PRODUCT = "SECURITY_PRODUCT"
    LOCAL_ADAPTER = "LOCAL_ADAPTER"
    USER_ASSERTION = "USER_ASSERTION"


class IdentityState(StrEnum):
    CURRENT = "CURRENT"
    HISTORICAL = "HISTORICAL"
    UNRESOLVED = "UNRESOLVED"
    CONFLICTED = "CONFLICTED"


@dataclass(frozen=True, slots=True)
class NetworkEvidence:
    evidence_id: str
    kind: EvidenceKind
    observed_at: str
    source: str
    ip: str | None = None
    mac: str | None = None
    hostname: str | None = None
    vendor: str | None = None
    model: str | None = None
    service: str | None = None
    value: str | None = None
    current: bool = True
    independent: bool = False

    def normalized_mac(self) -> str | None:
        if not self.mac:
            return None
        raw = "".join(ch for ch in self.mac if ch.isalnum()).upper()
        if len(raw) != 12:
            return None
        return ":".join(raw[i:i+2] for i in range(0, 12, 2))

    def valid_ip(self) -> bool:
        if not self.ip:
            return False
        try:
            ipaddress.ip_address(self.ip)
            return True
        except ValueError:
            return False


@dataclass(frozen=True, slots=True)
class MacClassification:
    mac: str
    unicast: bool
    locally_administered: bool
    globally_administered: bool
    vendor_oui_trustworthy: bool


@dataclass(frozen=True, slots=True)
class DeviceIdentityAssessment:
    schema: str
    contract_id: str
    identity_state: str
    candidate_device_ids: tuple[str, ...]
    current_ips: tuple[str, ...]
    historical_ips: tuple[str, ...]
    observed_macs: tuple[str, ...]
    hostnames: tuple[str, ...]
    vendors: tuple[str, ...]
    models: tuple[str, ...]
    services: tuple[str, ...]
    confidence: float
    ip_reuse_detected: bool
    private_mac_present: bool
    maliciousness: str
    contradictions: tuple[str, ...]
    next_evidence: tuple[str, ...]
    truth_boundary: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def stable_digest(value: object) -> str:
    data = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return sha256(data.encode("utf-8")).hexdigest()


def classify_mac(mac: str) -> MacClassification:
    raw = "".join(ch for ch in mac if ch.isalnum())
    if len(raw) != 12:
        raise ValueError("NETWORK_INTEL_INVALID_MAC")
    first = int(raw[:2], 16)
    multicast = bool(first & 0x01)
    local = bool(first & 0x02)
    normalized = ":".join(raw[i:i+2] for i in range(0, 12, 2)).upper()
    return MacClassification(
        mac=normalized,
        unicast=not multicast,
        locally_administered=local,
        globally_administered=not local,
        vendor_oui_trustworthy=(not multicast and not local),
    )


def _uniq(values: Iterable[str | None]) -> tuple[str, ...]:
    return tuple(sorted({v for v in values if v}))


class FormationNetworkIntelligence:
    """Fuse passive observations into a conservative identity assessment."""

    TRUTH_BOUNDARY = (
        "PASSIVE_EVIDENCE_FUSED!=DEVICE_OWNER_IDENTIFIED!=MALICIOUSNESS_PROVEN"
        "!=ROUTER_AUTHENTICATED!=ACTIVE_PROBE_AUTHORIZED!=COMPLETE"
    )

    def assess(self, evidence: Iterable[NetworkEvidence]) -> DeviceIdentityAssessment:
        items = tuple(evidence)
        if not items:
            raise ValueError("NETWORK_INTEL_EVIDENCE_REQUIRED")

        macs = _uniq(item.normalized_mac() for item in items)
        current_ips = _uniq(item.ip for item in items if item.current and item.valid_ip())
        historical_ips = _uniq(item.ip for item in items if not item.current and item.valid_ip())
        hostnames = _uniq(item.hostname for item in items)
        vendors = _uniq(item.vendor for item in items)
        models = _uniq(item.model for item in items)
        services = _uniq(item.service for item in items)

        private_mac = False
        for mac in macs:
            try:
                private_mac = private_mac or classify_mac(mac).locally_administered
            except ValueError:
                pass

        contradictions: list[str] = []
        by_ip: dict[str, set[str]] = {}
        for item in items:
            mac = item.normalized_mac()
            if item.ip and mac:
                by_ip.setdefault(item.ip, set()).add(mac)
        reused_ips = sorted(ip for ip, seen in by_ip.items() if len(seen) > 1)
        if reused_ips:
            contradictions.append("IP_REUSED_ACROSS_DISTINCT_MAC_IDENTITIES:" + ",".join(reused_ips))

        current_mac_sets = {
            item.normalized_mac()
            for item in items
            if item.current and item.normalized_mac()
        }
        historical_mac_sets = {
            item.normalized_mac()
            for item in items
            if not item.current and item.normalized_mac()
        }
        if current_mac_sets and historical_mac_sets and current_mac_sets.isdisjoint(historical_mac_sets):
            contradictions.append("CURRENT_AND_HISTORICAL_MAC_IDENTITIES_DIVERGE")

        independent_sources = len({item.source for item in items if item.independent})
        current_sources = len({item.source for item in items if item.current})
        signal_count = sum(bool(x) for x in (macs, current_ips, hostnames, vendors, models, services))
        confidence = min(
            0.95,
            0.20
            + 0.08 * signal_count
            + 0.07 * min(independent_sources, 3)
            + 0.05 * min(current_sources, 3)
            - 0.15 * len(contradictions),
        )
        if private_mac:
            confidence = max(0.05, confidence - 0.10)

        if contradictions:
            state = IdentityState.CONFLICTED
        elif current_ips or any(item.current for item in items):
            state = IdentityState.CURRENT
        elif historical_ips:
            state = IdentityState.HISTORICAL
        else:
            state = IdentityState.UNRESOLVED

        anchors = {
            item.hostname or item.normalized_mac() or item.ip or item.evidence_id
            for item in items
        }
        candidate_ids = tuple(
            sorted(f"DEV-{stable_digest(anchor)[:16].upper()}" for anchor in anchors if anchor)
        )

        next_evidence: list[str] = []
        if private_mac:
            next_evidence.append("CORRELATE_DHCP_CLIENT_ID_OR_ROUTER_ASSOCIATION_HISTORY")
        if not hostnames:
            next_evidence.append("COLLECT_MDNS_NETBIOS_DNS_HOSTNAME_WHEN_DEVICE_REAPPEARS")
        if reused_ips:
            next_evidence.append("SEPARATE_IP_EPOCHS_BY_TIMESTAMP_MAC_AND_DHCP_LEASE")
        if not vendors:
            next_evidence.append("USE_VENDOR_ONLY_FOR_GLOBALLY_ADMINISTERED_MAC_OR_DEVICE_SELF_REPORT")
        if not current_ips:
            next_evidence.append("WAIT_FOR_PASSIVE_REAPPEARANCE_OR_ROUTER_LEASE_READBACK")
        next_evidence.append("PRESERVE_SOURCE_TIMESTAMPS_AND_DO_NOT_INFER_OWNER_FROM_IP_ALONE")

        return DeviceIdentityAssessment(
            schema=SCHEMA,
            contract_id=CONTRACT_ID,
            identity_state=state.value,
            candidate_device_ids=candidate_ids,
            current_ips=current_ips,
            historical_ips=historical_ips,
            observed_macs=macs,
            hostnames=hostnames,
            vendors=vendors,
            models=models,
            services=services,
            confidence=round(confidence, 3),
            ip_reuse_detected=bool(reused_ips),
            private_mac_present=private_mac,
            maliciousness="UNKNOWN_UNLESS_SEPARATE_SECURITY_EVIDENCE",
            contradictions=tuple(contradictions),
            next_evidence=tuple(dict.fromkeys(next_evidence)),
            truth_boundary=self.TRUTH_BOUNDARY,
        )


__all__ = [
    "CONTRACT_ID",
    "DeviceIdentityAssessment",
    "EvidenceKind",
    "FormationNetworkIntelligence",
    "IdentityState",
    "MacClassification",
    "NetworkEvidence",
    "SCHEMA",
    "VERSION",
    "classify_mac",
]
