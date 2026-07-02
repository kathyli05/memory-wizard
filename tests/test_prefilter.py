"""Tests for triage.prefilter.

Guards two things: obvious automated notifications don't reach the paid
Claude API call, and anything with an imperative ask never gets filtered
even if it also looks automated — false negatives here cost API calls,
false positives here silently drop something the user needed to see.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from triage.prefilter import is_likely_automated


def test_otp_from_shortcode_is_filtered():
    assert is_likely_automated(
        "782929", "Your verification code is 482910. Don't share this code with anyone."
    )


def test_shortcode_sender_alone_is_filtered():
    assert is_likely_automated("65123", "Your package has been delivered.")


def test_personal_contact_is_not_filtered():
    assert not is_likely_automated(
        "+15556667777", "hey, haven't heard from you in a while, you doing ok?"
    )


def test_imperative_ask_overrides_otp_pattern():
    # Looks automated (has "code") but asks for a real decision — must not filter.
    assert not is_likely_automated(
        "65123", "Reply Y to confirm your appointment, or N to reschedule. Your code: 4821."
    )


def test_imperative_ask_overrides_shortcode_sender():
    assert not is_likely_automated("65123", "RSVP by Friday — are you coming?")


def test_stop_keyword_overrides_filter():
    assert not is_likely_automated("782929", "Reply STOP to unsubscribe from alerts.")
