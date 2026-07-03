"""Local contact-name resolution without persistence or network access."""

from __future__ import annotations

import locale
import os
import re
from dataclasses import dataclass
from typing import Iterable, Protocol

import phonenumbers

UNKNOWN_CONTACT = "Unknown contact"
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+$")


@dataclass(frozen=True)
class ContactRecord:
    contact_id: str
    given_name: str = ""
    middle_name: str = ""
    family_name: str = ""
    nickname: str = ""
    organization_name: str = ""
    phone_numbers: tuple[str, ...] = ()
    email_addresses: tuple[str, ...] = ()


class ContactResolver(Protocol):
    def resolve(self, identifiers: Iterable[str]) -> dict[str, str]:
        """Return identifier -> unambiguous saved name for known contacts."""


class NullContactResolver:
    def resolve(self, identifiers: Iterable[str]) -> dict[str, str]:
        return {}


def default_phone_region() -> str | None:
    configured = os.environ.get("CONTACTS_PHONE_REGION", "").strip().upper()
    if configured:
        return configured
    language, _ = locale.getlocale()
    if language and "_" in language:
        return language.rsplit("_", 1)[1].upper()
    return None


def normalize_phone(value: str, *, region: str | None) -> str | None:
    try:
        parsed = phonenumbers.parse(value, region)
    except phonenumbers.NumberParseException:
        return None
    if not phonenumbers.is_possible_number(parsed):
        return None
    return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)


def identifier_kind(value: str, *, region: str | None) -> tuple[str, str] | None:
    stripped = value.strip()
    if _EMAIL.fullmatch(stripped):
        return "email", stripped.casefold()
    normalized = normalize_phone(stripped, region=region)
    if normalized is not None:
        return "phone", normalized
    return None


def _display_name(record: ContactRecord) -> str | None:
    full_name = " ".join(
        part.strip()
        for part in (record.given_name, record.middle_name, record.family_name)
        if part and part.strip()
    )
    for candidate in (full_name, record.nickname.strip(), record.organization_name.strip()):
        if candidate:
            return candidate
    return None


def choose_unambiguous_name(
    identifier: str,
    records: Iterable[ContactRecord],
    *,
    region: str | None,
) -> str | None:
    classified = identifier_kind(identifier, region=region)
    if classified is None:
        return None
    kind, normalized_identifier = classified

    matches: dict[str, ContactRecord] = {}
    for record in records:
        if kind == "email":
            matched = any(
                address.strip().casefold() == normalized_identifier
                for address in record.email_addresses
            )
        else:
            matched = any(
                normalize_phone(number, region=region) == normalized_identifier
                for number in record.phone_numbers
            )
        if matched:
            matches[record.contact_id] = record

    if len(matches) != 1:
        return None
    return _display_name(next(iter(matches.values())))


def resolved_thread_names(
    threads: Iterable[dict], resolver: ContactResolver
) -> dict[int, str]:
    """Apply the display-name -> Contacts -> identifier -> unknown order."""
    thread_list = list(threads)
    identifiers = {
        thread.get("thread_identifier")
        for thread in thread_list
        if not (thread.get("thread_display_name") or "").strip()
        and (thread.get("thread_identifier") or "").strip()
    }
    resolved = resolver.resolve(identifier for identifier in identifiers if identifier)

    names = {}
    for thread in thread_list:
        display_name = (thread.get("thread_display_name") or "").strip()
        identifier = (thread.get("thread_identifier") or "").strip()
        names[thread["thread_id"]] = (
            display_name
            or resolved.get(identifier)
            or identifier
            or UNKNOWN_CONTACT
        )
    return names
