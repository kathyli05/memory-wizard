"""Deterministic, non-AI pre-filter for automated/non-actionable messages.

Excludes obvious automated notifications (verification codes, shortcode
senders) from triage candidates before they reach the paid Claude API call,
per CLAUDE.md's "minimize what goes to the Claude API" constraint. Same
"no AI call" posture as triage.detect_unanswered.

Conservative by design: any imperative-ask language (reply, confirm, Y/N,
STOP, ...) overrides the filter, since that could be a real action item —
better to send a borderline case to triage than silently drop something
that needed a response.
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

_IMPERATIVE_OVERRIDE_PATTERNS = [
    re.compile(r"\breply\b", re.I),
    re.compile(r"\bconfirm\b", re.I),
    re.compile(r"\by\s*/\s*n\b", re.I),
    re.compile(r"\byes\s*/\s*no\b", re.I),
    re.compile(r"\brsvp\b", re.I),
    re.compile(r"\brespond\b", re.I),
    re.compile(r"\bstop\b", re.I),
]


def is_likely_automated(sender: str, text: str) -> bool:
    """True if this message is an obvious automated notification that
    doesn't need triage (an OTP code, a shortcode ping) and False otherwise
    — including whenever the text carries an imperative ask, regardless of
    the other signals."""
    if any(p.search(text) for p in _IMPERATIVE_OVERRIDE_PATTERNS):
        return False

    if _SHORTCODE_SENDER.match(sender or ""):
        return True

    return any(p.search(text) for p in _AUTOMATED_TEXT_PATTERNS)
