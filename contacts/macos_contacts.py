"""Permission-aware wrapper around the fixed local Contacts helper.

The helper is the sole approved subprocess in this repository. It receives
lookup data over stdin, returns captured JSON over stdout, never uses a shell,
and exposes no arbitrary command or path selection.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Iterable, Literal

from contacts.name_resolver import (
    ContactRecord,
    choose_unambiguous_name,
    default_phone_region,
    identifier_kind,
)

_REPO_ROOT = Path(__file__).resolve().parent.parent
HELPER_PATH = (
    _REPO_ROOT
    / "native"
    / "contacts_helper"
    / ".build"
    / "MemoryWizardContacts.app"
    / "Contents"
    / "MacOS"
    / "MemoryWizardContacts"
)
_COMMANDS = {"status", "request-access", "resolve"}
AccessCommand = Literal["status", "request-access", "resolve"]


class MacOSContactResolver:
    def __init__(self, *, region: str | None = None) -> None:
        self.region = region or default_phone_region()

    def _invoke(self, command: AccessCommand, payload: dict | None = None) -> dict:
        if command not in _COMMANDS or not HELPER_PATH.is_file():
            return {"status": "unavailable"}
        try:
            completed = subprocess.run(
                [str(HELPER_PATH), command],
                input=json.dumps(payload or {}),
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
                shell=False,
            )
            if completed.returncode != 0:
                return {"status": "unavailable"}
            response = json.loads(completed.stdout)
            return response if isinstance(response, dict) else {"status": "unavailable"}
        except (OSError, subprocess.SubprocessError, json.JSONDecodeError):
            return {"status": "unavailable"}

    def authorization_status(self) -> str:
        return str(self._invoke("status").get("status", "unavailable"))

    def request_access(self) -> str:
        return str(self._invoke("request-access").get("status", "unavailable"))

    def resolve(self, identifiers: Iterable[str]) -> dict[str, str]:
        unique = list(dict.fromkeys(value for value in identifiers if value))
        lookups = []
        originals = {}
        for value in unique:
            classified = identifier_kind(value, region=self.region)
            if classified is None:
                continue
            kind, query = classified
            index = len(lookups)
            lookups.append({"index": index, "kind": kind, "query": query})
            originals[index] = value
        if not lookups:
            return {}

        response = self._invoke("resolve", {"lookups": lookups})
        if response.get("status") not in {"authorized", "limited"}:
            return {}

        resolved = {}
        raw_results = response.get("results", {})
        for index, original in originals.items():
            candidates = raw_results.get(str(index), [])
            records = []
            for candidate in candidates:
                try:
                    records.append(
                        ContactRecord(
                            contact_id=str(candidate["contact_id"]),
                            given_name=str(candidate.get("given_name", "")),
                            middle_name=str(candidate.get("middle_name", "")),
                            family_name=str(candidate.get("family_name", "")),
                            nickname=str(candidate.get("nickname", "")),
                            organization_name=str(candidate.get("organization_name", "")),
                            phone_numbers=tuple(candidate.get("phone_numbers", [])),
                            email_addresses=tuple(candidate.get("email_addresses", [])),
                        )
                    )
                except (KeyError, TypeError):
                    continue
            name = choose_unambiguous_name(original, records, region=self.region)
            if name is not None:
                resolved[original] = name
        return resolved
