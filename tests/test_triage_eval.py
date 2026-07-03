import json
import sys

from scripts import run_triage_eval


def test_cases_validate_and_preserve_last_five_cap():
    cases = run_triage_eval.load_cases(run_triage_eval.DEFAULT_CASES)
    assert len(cases) == 10
    assert {case["split"] for case in cases} == {"development", "holdout"}
    assert all(len(case["request_messages"]) <= 5 for case in cases)
    assert all(case["profile"]["median_response_latency_seconds_365d"] is None
               for case in cases)
    assert all("profile" not in json.loads(line) for line in
               run_triage_eval.DEFAULT_CASES.read_text().splitlines())


def test_default_eval_is_redacted_zero_call_and_writes_safe_reports(
    monkeypatch, capsys, tmp_path
):
    monkeypatch.setattr(
        run_triage_eval, "_create_anthropic_client",
        lambda: (_ for _ in ()).throw(AssertionError("client must not be created")),
    )
    report_dir = tmp_path / "reports"
    monkeypatch.setattr(sys, "argv", [
        "run_triage_eval.py", "--max-cases", "1", "--report-dir", str(report_dir)
    ])
    run_triage_eval.main()
    output = capsys.readouterr().out
    assert "API calls about to be made: 0" in output
    assert "Fictional Rowan Quill" not in output
    assert "Moonbase safety shift" not in output
    assert "[REDACTED THREAD]" in output
    assert report_dir.exists()
    report = json.loads((report_dir / "latest.json").read_text())
    markdown = (report_dir / "latest.md").read_text()
    serialized = json.dumps(report)
    assert report["mode"] == "preview"
    assert report["api_call_count"] == 0
    assert report["token_totals"] == {
        "input_tokens": 0, "output_tokens": 0,
        "cache_creation_tokens": 0, "cache_read_tokens": 0,
    }
    assert "request" not in report
    assert "Moonbase safety shift" not in serialized
    assert "Fictional Rowan Quill" not in serialized
    assert "No model predictions or accuracy metrics" in markdown
    assert len(list(report_dir.glob("*-preview.json"))) == 1
    assert len(list(report_dir.glob("*-preview.md"))) == 1


def test_paid_eval_requires_both_confirmation_flags(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["run_triage_eval.py", "--call"])
    try:
        run_triage_eval.main()
    except SystemExit as exc:
        assert exc.code == 2
    else:
        raise AssertionError("missing confirmation must stop the run")


def test_mocked_paid_eval_writes_separate_report(monkeypatch, capsys, tmp_path):
    report_dir = tmp_path / "reports"

    def fake_client():
        assert "API calls about to be made: 1" in capsys.readouterr().out
        return object()

    monkeypatch.setattr(run_triage_eval, "_create_anthropic_client", fake_client)
    monkeypatch.setattr(run_triage_eval, "run_triage", lambda *args: {
        "urgency": "high", "suggest_nudge": True, "needs_review": False,
        "reasoning": "Mocked derived rationale", "thread_id": 900001,
        "_usage": {"input_tokens": 200, "output_tokens": 40,
                   "cache_creation_tokens": 20, "cache_read_tokens": 10},
    })
    monkeypatch.setattr(sys, "argv", [
        "run_triage_eval.py", "--call", "--confirm-eval", "--max-cases", "1",
        "--report-dir", str(report_dir),
    ])
    run_triage_eval.main()
    report = json.loads((report_dir / "latest.json").read_text())
    markdown = (report_dir / "latest.md").read_text()
    assert report["mode"] == "paid"
    assert report["success_count"] == 1
    assert report["failure_count"] == 0
    assert report["metrics"]["per_class"]["high"]["recall"] == 1.0
    assert report["token_totals"]["input_tokens"] == 200
    assert "reasoning" not in json.dumps(report)
    assert "Overall urgency agreement: 100.0%" in markdown
    assert "High-urgency recall: 100.0%" in markdown
    assert len(list(report_dir.glob("*-paid.json"))) == 1
    assert len(list(report_dir.glob("*-paid.md"))) == 1


def test_metrics_include_high_recall_and_false_positive_rate():
    rows = [
        {"status": "success", "expected": {"urgency": "high", "suggest_nudge": True, "needs_review": False},
         "prediction": {"urgency": "high", "suggest_nudge": True, "needs_review": False}},
        {"status": "success", "expected": {"urgency": "low", "suggest_nudge": False, "needs_review": False},
         "prediction": {"urgency": "high", "suggest_nudge": True, "needs_review": False}},
    ]
    report = run_triage_eval.metrics(rows)
    assert report["per_class"]["high"]["recall"] == 1.0
    assert report["high_urgency_false_positive_rate"] == 1.0
    assert report["overall_urgency_agreement"] == 0.5
