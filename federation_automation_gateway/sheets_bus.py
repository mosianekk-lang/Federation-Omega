from __future__ import annotations

import json
from typing import Any

import google.auth
from googleapiclient.discovery import build

from .contracts import Command, EffectClass, MissionLease


class SheetsBus:
    QUEUE_RANGE = "COMMAND_QUEUE!A2:X5000"
    LEASE_RANGE = "AUTHORITY_LEASES!A2:Q1000"
    RECEIPT_APPEND = "COMMAND_RECEIPTS!A:T"
    HEARTBEAT_APPEND = "RUNTIME_HEARTBEAT!A:L"

    def __init__(self, spreadsheet_id: str):
        credentials, _ = google.auth.default(
            scopes=["https://www.googleapis.com/auth/spreadsheets"]
        )
        self.api = build("sheets", "v4", credentials=credentials, cache_discovery=False)
        self.spreadsheet_id = spreadsheet_id

    def _values(self, range_name: str) -> list[list[Any]]:
        result = (
            self.api.spreadsheets()
            .values()
            .get(spreadsheetId=self.spreadsheet_id, range=range_name)
            .execute()
        )
        return result.get("values", [])

    def queued(self, limit: int = 20) -> list[tuple[int, Command]]:
        rows = self._values(self.QUEUE_RANGE)
        commands: list[tuple[int, Command]] = []
        for row_number, row in enumerate(rows, start=2):
            padded = row + [""] * (24 - len(row))
            if padded[14] != "QUEUED":
                continue
            payload = json.loads(padded[10] or "{}")
            proofs = tuple(json.loads(padded[11] or "[]"))
            command = Command(
                command_id=padded[0],
                created_at_sast=padded[1],
                requested_by_chat=padded[2],
                engine=padded[3],
                mission_id=padded[4],
                lease_id=padded[5],
                adapter_id=padded[6],
                action=padded[7],
                effect_class=EffectClass(padded[8]),
                target_alias=padded[9],
                payload=payload,
                required_proofs=proofs,
                idempotency_key=padded[12],
                priority=padded[13] or "P2",
            )
            commands.append((row_number, command))
            if len(commands) >= limit:
                break
        return commands

    def completed_idempotency_keys(self) -> set[str]:
        keys: set[str] = set()
        for row in self._values(self.QUEUE_RANGE):
            padded = row + [""] * (24 - len(row))
            state = padded[14]
            key = padded[12]
            if key and state in {"DONE", "PARTIAL"}:
                keys.add(key)
        return keys

    def lease(self, lease_id: str) -> MissionLease | None:
        if not lease_id:
            return None
        for row in self._values(self.LEASE_RANGE):
            padded = row + [""] * (17 - len(row))
            if padded[0] != lease_id:
                continue
            return MissionLease(
                lease_id=padded[0],
                state=padded[2],
                scope=json.loads(padded[3] or "{}"),
                allowed_effects=tuple(filter(None, str(padded[4]).split(","))),
                allowed_targets=tuple(filter(None, str(padded[5]).split(","))),
                issued_by=padded[6],
                issued_at_sast=padded[7],
                expires_at_sast=padded[8],
                max_commands=int(padded[9] or 0),
                commands_used=int(padded[10] or 0),
                rollback_required=str(padded[11]).upper() == "TRUE",
                readback_required=str(padded[12]).upper() == "TRUE",
                communications_allowed=str(padded[13]).upper() == "TRUE",
                destructive_allowed=str(padded[14]).upper() == "TRUE",
            )
        return None

    def consume_lease_command(self, lease_id: str) -> None:
        if not lease_id:
            return
        rows = self._values(self.LEASE_RANGE)
        for row_number, row in enumerate(rows, start=2):
            padded = row + [""] * (17 - len(row))
            if padded[0] != lease_id:
                continue
            used = int(padded[10] or 0) + 1
            (
                self.api.spreadsheets()
                .values()
                .update(
                    spreadsheetId=self.spreadsheet_id,
                    range=f"AUTHORITY_LEASES!K{row_number}",
                    valueInputOption="RAW",
                    body={"values": [[used]]},
                )
                .execute()
            )
            return
        raise RuntimeError(f"Lease disappeared before consumption: {lease_id}")

    def claim(
        self,
        row_number: int,
        *,
        owner: str,
        until_sast: str,
        started_at_sast: str,
    ) -> None:
        (
            self.api.spreadsheets()
            .values()
            .batchUpdate(
                spreadsheetId=self.spreadsheet_id,
                body={
                    "valueInputOption": "RAW",
                    "data": [
                        {
                            "range": f"COMMAND_QUEUE!O{row_number}:S{row_number}",
                            "values": [[
                                "EXECUTING",
                                1,
                                owner,
                                until_sast,
                                started_at_sast,
                            ]],
                        }
                    ],
                },
            )
            .execute()
        )

    def finish(
        self,
        row_number: int,
        *,
        state: str,
        completed_at_sast: str,
        receipt_id: str,
        error_code: str = "",
    ) -> None:
        # Keep column S (started_at_sast) intact so the provider execution
        # interval remains auditable after the queue row reaches terminal state.
        (
            self.api.spreadsheets()
            .values()
            .batchUpdate(
                spreadsheetId=self.spreadsheet_id,
                body={
                    "valueInputOption": "RAW",
                    "data": [
                        {
                            "range": f"COMMAND_QUEUE!O{row_number}:R{row_number}",
                            "values": [[state, 1, "", ""]],
                        },
                        {
                            "range": f"COMMAND_QUEUE!T{row_number}:V{row_number}",
                            "values": [[completed_at_sast, receipt_id, error_code]],
                        },
                    ],
                },
            )
            .execute()
        )

    def append_receipt(self, values: list[Any]) -> None:
        (
            self.api.spreadsheets()
            .values()
            .append(
                spreadsheetId=self.spreadsheet_id,
                range=self.RECEIPT_APPEND,
                valueInputOption="RAW",
                insertDataOption="INSERT_ROWS",
                body={"values": [values]},
            )
            .execute()
        )

    def append_heartbeat(self, values: list[Any]) -> None:
        (
            self.api.spreadsheets()
            .values()
            .append(
                spreadsheetId=self.spreadsheet_id,
                range=self.HEARTBEAT_APPEND,
                valueInputOption="RAW",
                insertDataOption="INSERT_ROWS",
                body={"values": [values]},
            )
            .execute()
        )
