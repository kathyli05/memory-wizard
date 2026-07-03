"""Deterministic, non-AI pre-filter for automated/non-actionable messages.

Excludes obvious automated notifications (verification codes, shortcode
senders) from triage candidates before they reach the paid Claude API call,
per CLAUDE.md's "minimize what goes to the Claude API" constraint. Same
"no AI call" posture as triage.detect_unanswered.

Conservative by design: any imperative-ask language (reply, confirm, Y/N,
STOP, ...) overrides the filter, since that could be a real action item —
better to send a borderline case to triage than silently drop something
that needed a response.

One deliberate exception: compliance opt-out footers ("Reply STOP to
unsubscribe") are a hallmark of automated marketing, not a real ask, and
they contain exactly the words ("reply", "stop") that trip the imperative
override. The footer is stripped before the override check and counts as
an automated-text signal itself — otherwise nearly all marketing spam
would ride its own unsubscribe footer into a paid API call, feeding the
most adversarial text on the phone straight into the model prompt.
"""

from __future__ import annotations

import re

# Real contacts text from full phone numbers or emails; shortcodes (typically
# 4-6 numeric digits, no "+") are how 2FA/notification services send.
_SHORTCODE_SENDER = re.compile(r"^\d{4,6}$")

_AUTOMATED_TEXT_PATTERNS = [
    re.compile(r"\bverification code\b", re.I),
    re.compile(r"\bone[- ]time (code|password|passcode)\b", re.I),
    re.compile(r"\bOTP\b"),
    re.compile(r"\bsecurity code\b", re.I),
    re.compile(r"\byour code is\b", re.I),
    re.compile(r"\bis your\b.{0,20}\bcode\b", re.I),
    re.compile(r"do ?n['’]?t share this code", re.I),
]

# "Reply STOP to unsubscribe" / "Text STOP to opt out" / "STOP to end" —
# the standard carrier-compliance footer on automated marketing texts.
_OPT_OUT_FOOTER = re.compile(
    r"(?:\breply\b|\btext\b|\bsend\b)[^a-z0-9]{0,3}stop\b"
    r"|\bstop\s*(?:to|=|2)\s*(?:cancel|end|quit|opt[\s-]?out|unsub\w*)",
    re.I,
)

_IMPERATIVE_OVERRIDE_PATTERNS = [
    re.compile(r"\breply\b", re.I),
    re.compile(r"\bconfirm\b", re.I),
    re.compile(r"\by\s*/\s*n\b", re.I),
    re.compile(r"\byes\s*/\s*no\b", re.I),
    re.compile(r"\brsvp\b", re.I),
    re.compile(r"\brespond\b", re.I),
    re.compile(r"\bstop\b", re.I),
]


def automated_filter_reason(sender: str, text: str) -> str | None:
    """Return a privacy-safe filter category, or None when triage should run.

    The returned labels describe only which deterministic rule matched; they
    never contain sender or message content.
    """
    text_without_footer = _OPT_OUT_FOOTER.sub(" ", text)
    if any(p.search(text_without_footer) for p in _IMPERATIVE_OVERRIDE_PATTERNS):
        return None

    if _OPT_OUT_FOOTER.search(text):
        return (
            "contains an unsubscribe/opt-out footer, which is a strong "
            "automated-marketing signal"
        )

    if any(p.search(text) for p in _AUTOMATED_TEXT_PATTERNS):
        return (
            "matches a verification or one-time-code pattern and contains "
            "no genuine reply request"
        )

    if _SHORTCODE_SENDER.match(sender or ""):
        return (
            "comes from a 4–6 digit shortcode and contains no genuine reply request"
        )

    return None


def is_likely_automated(sender: str, text: str) -> bool:
    """True when a message matches a deterministic automated filter rule."""
    return automated_filter_reason(sender, text) is not None
