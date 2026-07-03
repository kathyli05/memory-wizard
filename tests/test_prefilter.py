"""Tests for triage.prefilter.

Guards two things: obvious automated notifications don't reach the paid
Claude API call, and anything with an imperative ask never gets filtered
even if it also looks automated — false negatives here cost API calls,
false positives here silently drop something the user needed to see.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from triage.prefilter import automated_filter_reason, is_likely_automated


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


def test_opt_out_footer_is_treated_as_automated_not_as_an_ask():
    # "Reply STOP to unsubscribe" is a compliance footer, not a real ask —
    # it must not ride the reply/stop override into a paid API call.
    assert is_likely_automated("782929", "Reply STOP to unsubscribe from alerts.")


def test_marketing_spam_from_full_number_with_opt_out_footer_is_filtered():
    assert is_likely_automated(
        "+18885551234",
        "FLASH SALE 🔥 40% off everything this weekend only! Text STOP to opt out.",
    )


def test_real_ask_survives_an_opt_out_footer():
    # The footer is stripped, but the remaining genuine ask still overrides.
    assert not is_likely_automated(
        "65123",
        "Reply Y to confirm your appointment for Friday. Reply STOP to cancel reminders.",
    )


def test_human_saying_stop_still_overrides():
    assert not is_likely_automated("+15556667777", "can you stop by tomorrow?")


def test_filter_reasons_are_specific_and_contain_no_private_input():
    private_sender = "+18885551234"
    private_text = "Private sale details. Text STOP to opt out."

    reason = automated_filter_reason(private_sender, private_text)

    assert reason == (
        "contains an unsubscribe/opt-out footer, which is a strong "
        "automated-marketing signal"
    )
    assert private_sender not in reason
    assert private_text not in reason


def test_filter_reason_categories_cover_code_and_shortcode_rules():
    assert (
        automated_filter_reason("782929", "Your verification code is 482910.")
        == "matches a verification or one-time-code pattern and contains "
        "no genuine reply request"
    )
    assert (
        automated_filter_reason("65123", "Your package has been delivered.")
        == "comes from a 4–6 digit shortcode and contains no genuine reply request"
    )
