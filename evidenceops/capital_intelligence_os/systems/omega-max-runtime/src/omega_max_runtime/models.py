from dataclasses import dataclass, asdict
from typing import Any

@dataclass(frozen=True)
class MutationContract:
    contract_id: str
    action: str
    target: str
    desired: Any
    expected_before: Any
    authority: str
    reversible: bool
    allow_remediation: bool = False

    @classmethod
    def from_dict(cls, data):
        required = {"contract_id", "action", "target", "desired", "expected_before", "authority", "reversible"}
        missing = sorted(required - set(data))
        if missing:
            raise ValueError(f"missing contract fields: {missing}")
        if data["action"] != "SET_JSON":
            raise ValueError("only SET_JSON is supported")
        if data["authority"] not in {"A0", "A1"}:
            raise ValueError("authority exceeds runtime envelope")
        if data["reversible"] is not True:
            raise ValueError("contract must be reversible")
        return cls(
            str(data["contract_id"]), str(data["action"]), str(data["target"]),
            data["desired"], data["expected_before"], str(data["authority"]), True,
            bool(data.get("allow_remediation", False)),
        )

    def to_dict(self):
        return asdict(self)
