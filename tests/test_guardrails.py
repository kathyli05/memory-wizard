"""Guardrail tests: structural invariants from CLAUDE.md, enforced in CI.

Two promises this codebase makes that must stay true as it grows:
  1. It can never send a message (or execute anything) on the user's
     behalf — no AppleScript, no shells, no direct network sockets. The
     only permitted network egress is the anthropic SDK.
  2. The source Messages database is only ever opened read-only.

These are text-level checks on our own source files, deliberately blunt:
if one fires on a legitimate future change, that change deserves the
explicit conversation CLAUDE.md requires before weakening a constraint.
"""

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
THIS_FILE = Path(__file__).resolve()

# Modules that grant execution or message-sending ability, or open network
# channels the anthropic SDK doesn't mediate.
FORBIDDEN_IMPORTS = {
    "subprocess",
    "socket",
    "requests",
    "urllib",
    "http",
    "httpx",
    "aiohttp",
    "ctypes",
    "osascript",
    "applescript",
    "ScriptingBridge",
    "py_imessage",
    "imessage",
}

# Explicitly approved, fixed-path, no-shell bridge to the read-only native
# Contacts helper. No other Python module may gain subprocess capability.
CONTACTS_HELPER_WRAPPER = Path("contacts/macos_contacts.py")

_IMPORT_RE = re.compile(r"^\s*(?:import|from)\s+([A-Za-z_][\w]*)", re.MULTILINE)

# Call-sites that reach execution without an import keyword match.
FORBIDDEN_CALLS = ["os.system(", "os.popen(", "os.exec", "osascript"]


def _source_files():
    for path in sorted(REPO_ROOT.rglob("*.py")):
        if path == THIS_FILE:
            continue
        if any(part in {".venv", "venv", "__pycache__"} for part in path.parts):
            continue
        yield path


def test_no_send_or_exec_capability_in_source():
    violations = []
    for path in _source_files():
        text = path.read_text()
        rel = path.relative_to(REPO_ROOT)

        for match in _IMPORT_RE.finditer(text):
            if (match.group(1) in FORBIDDEN_IMPORTS
                    and not (rel == CONTACTS_HELPER_WRAPPER
                             and match.group(1) == "subprocess")):
                violations.append(f"{rel}: imports {match.group(1)!r}")

        for token in FORBIDDEN_CALLS:
            if token in text:
                violations.append(f"{rel}: contains {token!r}")

    assert not violations, (
        "send/exec-capable code found — CLAUDE.md forbids the agent gaining "
        "the ability to send messages or run commands:\n  " + "\n  ".join(violations)
    )


def test_contacts_helper_is_fixed_path_read_only_and_no_shell():
    wrapper = (REPO_ROOT / CONTACTS_HELPER_WRAPPER).read_text()
    helper = (REPO_ROOT / "native/contacts_helper/main.m").read_text()

    assert "HELPER_PATH = (" in wrapper
    assert "shell=False" in wrapper
    assert "[str(HELPER_PATH), command]" in wrapper
    assert "CNSaveRequest" not in helper
    assert "CNMutableContact" not in helper
    assert ".execute(" not in helper


def test_contacts_names_never_enter_triage_agent_or_storage():
    triage_agent = (REPO_ROOT / "triage/triage_agent.py").read_text()
    triage_store = (REPO_ROOT / "triage/store_triage_results.py").read_text()
    profile_store = (REPO_ROOT / "contacts/store_profiles.py").read_text()

    assert "MacOSContactResolver" not in triage_agent
    assert "resolved_contact" not in triage_store
    assert "resolved_contact" not in profile_store


def test_source_db_paths_only_opened_read_only():
    """Every sqlite3.connect() in the ingestion layer that touches the
    source must go through a mode=ro URI; the backup-dest connect is the
    single permitted writable connection and it must never point at a
    source path (enforced at runtime by copy_chat_db's self-copy guard,
    exercised in test_copy_chat_db)."""
    copy_src = (REPO_ROOT / "ingestion" / "copy_chat_db.py").read_text()
    parse_src = (REPO_ROOT / "ingestion" / "parse_messages.py").read_text()

    assert 'f"file:{source}?mode=ro"' in copy_src
    assert "mode=ro" in parse_src

    # exactly one writable connect in the copier: the backup destination
    writable_connects = [
        line.strip()
        for line in copy_src.splitlines()
        if "sqlite3.connect(" in line and "mode=ro" not in line
    ]
    assert writable_connects == ["dest_conn = sqlite3.connect(dest)"], writable_connects


def test_dashboard_never_renders_untrusted_fields_as_markdown():
    """reasoning/thread_name are model-output/third-party influenced —
    st.markdown on them re-opens the injection→exfiltration channel
    (SECURITY_REVIEW.md F2)."""
    app_src = (REPO_ROOT / "dashboard" / "app.py").read_text()
    assert "st.markdown(reasoning" not in app_src
    assert 'st.markdown(result["reasoning"]' not in app_src


def test_dashboard_feedback_is_separate_from_dismiss_and_nudge_wording_is_clear():
    app_src = (REPO_ROOT / "dashboard" / "app.py").read_text()
    assert 'st.button("Correct"' in app_src
    assert 'st.popover("Wrong urgency")' in app_src
    assert 'st.button("Not reply-worthy"' in app_src
    assert "remind me to reply" in app_src
    assert "consider sending a nudge" not in app_src


def test_streamlit_config_pins_localhost():
    config = (REPO_ROOT / ".streamlit" / "config.toml").read_text()
    assert re.search(r'address\s*=\s*"localhost"', config), (
        ".streamlit/config.toml must bind the dashboard to localhost "
        "(SECURITY_REVIEW.md F1)"
    )
