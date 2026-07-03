from contacts.macos_contacts import MacOSContactResolver
from contacts.name_resolver import (
    ContactRecord,
    UNKNOWN_CONTACT,
    choose_unambiguous_name,
    resolved_thread_names,
)


class FakeResolver:
    def __init__(self, names):
        self.names = names
        self.requested = None

    def resolve(self, identifiers):
        self.requested = set(identifiers)
        return {key: value for key, value in self.names.items() if key in self.requested}


def test_phone_matching_across_formatting_variants():
    record = ContactRecord(
        contact_id="one",
        given_name="Alex",
        family_name="Chen",
        phone_numbers=("(415) 555-0123",),
    )
    assert choose_unambiguous_name(
        "+1 415-555-0123", [record], region="US"
    ) == "Alex Chen"


def test_email_matching_is_case_insensitive():
    record = ContactRecord(
        contact_id="one",
        given_name="Alex",
        email_addresses=("Alex.Chen@Example.COM",),
    )
    assert choose_unambiguous_name(
        "alex.chen@example.com", [record], region="US"
    ) == "Alex"


def test_unicode_contact_name_is_preserved():
    record = ContactRecord(
        contact_id="one",
        given_name="李",
        family_name="小龍",
        phone_numbers=("+886 912 345 678",),
    )
    assert choose_unambiguous_name(
        "+886912345678", [record], region="TW"
    ) == "李 小龍"


def test_duplicate_contact_matches_are_ambiguous_even_with_same_name():
    records = [
        ContactRecord(
            contact_id=contact_id,
            given_name="Alex",
            phone_numbers=("4155550123",),
        )
        for contact_id in ("one", "two")
    ]
    assert choose_unambiguous_name("+14155550123", records, region="US") is None


def test_duplicate_rows_for_one_unified_contact_are_not_ambiguous():
    record = ContactRecord(
        contact_id="one",
        nickname="Mom",
        phone_numbers=("4155550123",),
    )
    assert choose_unambiguous_name(
        "+14155550123", [record, record], region="US"
    ) == "Mom"


def test_denied_contacts_permission_returns_no_names(monkeypatch):
    resolver = MacOSContactResolver(region="US")
    monkeypatch.setattr(resolver, "_invoke", lambda command, payload=None: {"status": "denied"})
    assert resolver.resolve(["+14155550123"]) == {}


def test_no_matching_contact_falls_back_to_identifier():
    resolver = FakeResolver({})
    threads = [{
        "thread_id": 1,
        "thread_display_name": None,
        "thread_identifier": "+14155550123",
    }]
    assert resolved_thread_names(threads, resolver) == {1: "+14155550123"}


def test_named_group_chat_wins_without_contact_lookup():
    resolver = FakeResolver({"group-identifier": "Wrong Contact"})
    threads = [{
        "thread_id": 1,
        "thread_display_name": "Weekend Plans",
        "thread_identifier": "group-identifier",
    }]
    assert resolved_thread_names(threads, resolver) == {1: "Weekend Plans"}
    assert resolver.requested == set()


def test_blank_and_null_identifiers_use_unknown_contact():
    resolver = FakeResolver({})
    threads = [
        {"thread_id": 1, "thread_display_name": None, "thread_identifier": "   "},
        {"thread_id": 2, "thread_display_name": None, "thread_identifier": None},
    ]
    assert resolved_thread_names(threads, resolver) == {
        1: UNKNOWN_CONTACT,
        2: UNKNOWN_CONTACT,
    }
