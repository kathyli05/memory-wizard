"""Validate or deliberately run the isolated synthetic triage evaluation."""

import argparse
import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.run_triage import _create_anthropic_client, _redacted_request, _safe_error_type
from contacts.build_profiles import compute_all_profiles
from triage.pricing import PRICING_VERSION, estimate_cost_usd
from triage.triage_agent import (
    MODEL, PROMPT_VERSION, last_n_messages, prompt_fingerprint, run_triage
)

DEFAULT_CASES = Path("evals/triage_cases.jsonl")
DEFAULT_REPORT_DIR = Path("evals/reports")
CLASSES = ("low", "med", "high")
TOKEN_FIELDS = (
    "input_tokens", "output_tokens", "cache_creation_tokens", "cache_read_tokens"
)


def load_cases(path: Path) -> list[dict]:
    cases = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    seen = set()
    for case in cases:
        required = {"case_id", "split", "as_of", "tags", "messages", "expected"}
        if set(case) != required:
            raise ValueError(f"{case.get('case_id', '<unknown>')}: invalid top-level shape")
        if case["case_id"] in seen:
            raise ValueError(f"duplicate case_id: {case['case_id']}")
        seen.add(case["case_id"])
        if case["split"] not in {"development", "holdout"}:
            raise ValueError(f"{case['case_id']}: invalid split")
        if not 1 <= len(case["messages"]) <= 5:
            raise ValueError(f"{case['case_id']}: messages must contain 1-5 items")
        expected = case["expected"]
        if set(expected) != {"urgency", "suggest_nudge", "needs_review"}:
            raise ValueError(f"{case['case_id']}: invalid expected shape")
        if expected["urgency"] not in CLASSES:
            raise ValueError(f"{case['case_id']}: invalid urgency")
        case["as_of"] = datetime.fromisoformat(case["as_of"])
        for message in case["messages"]:
            message["timestamp"] = datetime.fromisoformat(message["timestamp"])
        profiles = compute_all_profiles(case["messages"], now=case["as_of"])
        if len(profiles) != 1:
            raise ValueError(f"{case['case_id']}: messages must describe one thread")
        case["profile"] = profiles[0]
        case["request_messages"] = last_n_messages(
            case["messages"], profiles[0]["thread_id"], n=5
        )
    return cases


def metrics(rows: list[dict]) -> dict:
    successful = [row for row in rows if row["status"] == "success"]
    matrix = {actual: {predicted: 0 for predicted in CLASSES} for actual in CLASSES}
    for row in successful:
        matrix[row["expected"]["urgency"]][row["prediction"]["urgency"]] += 1
    per_class = {}
    for label in CLASSES:
        tp = matrix[label][label]
        predicted = sum(matrix[actual][label] for actual in CLASSES)
        actual = sum(matrix[label].values())
        per_class[label] = {
            "precision": tp / predicted if predicted else 0.0,
            "recall": tp / actual if actual else 0.0,
        }
    high_negative = sum(sum(matrix[label].values()) for label in ("low", "med"))
    high_fp = sum(matrix[label]["high"] for label in ("low", "med"))
    count = len(successful)
    return {
        "overall_urgency_agreement": (
            sum(matrix[label][label] for label in CLASSES) / count if count else 0.0
        ),
        "confusion_matrix": matrix,
        "per_class": per_class,
        "high_urgency_false_positive_rate": high_fp / high_negative if high_negative else 0.0,
        "suggest_nudge_agreement": sum(
            row["prediction"]["suggest_nudge"] == row["expected"]["suggest_nudge"]
            for row in successful
        ) / count if count else 0.0,
        "needs_review_agreement": sum(
            row["prediction"]["needs_review"] == row["expected"]["needs_review"]
            for row in successful
        ) / count if count else 0.0,
    }


def _split_counts(cases: list[dict]) -> dict:
    counts = Counter(case["split"] for case in cases)
    return {"development": counts["development"], "holdout": counts["holdout"]}


def _percent(value: float) -> str:
    return f"{value * 100:.1f}%"


def _markdown_report(report: dict) -> str:
    lines = [
        "# Synthetic triage evaluation",
        "",
        f"- Mode: `{report['mode']}`",
        f"- Created: `{report['created_at']}`",
        f"- Prompt: `{report['prompt_version']}`",
        f"- Fingerprint: `{report['prompt_fingerprint']}`",
        f"- Model: `{report['model']}`",
        f"- Cases: {report['case_count']} "
        f"({report['split_counts']['development']} development, "
        f"{report['split_counts']['holdout']} holdout)",
        f"- API calls: {report['api_call_count']}",
        "",
    ]
    if report["mode"] == "preview":
        lines.extend([
            "## Validation result",
            "",
            "All selected cases passed structural validation. Requests were "
            "previewed only after private-shaped fields were redacted.",
            "",
            "No model predictions or accuracy metrics exist for a preview run.",
            "",
        ])
    else:
        metric = report["metrics"]
        lines.extend([
            "## Results",
            "",
            f"- Successful cases: {report['success_count']}",
            f"- Failed cases: {report['failure_count']}",
            f"- Overall urgency agreement: {_percent(metric['overall_urgency_agreement'])}",
            f"- High-urgency recall: {_percent(metric['per_class']['high']['recall'])}",
            "- High-urgency false-positive rate: "
            f"{_percent(metric['high_urgency_false_positive_rate'])}",
            f"- Suggest-nudge agreement: {_percent(metric['suggest_nudge_agreement'])}",
            f"- Needs-review agreement: {_percent(metric['needs_review_agreement'])}",
            "",
            "### Per-class precision and recall",
            "",
            "| Class | Precision | Recall |",
            "|---|---:|---:|",
        ])
        for label in CLASSES:
            values = metric["per_class"][label]
            lines.append(
                f"| {label} | {_percent(values['precision'])} | {_percent(values['recall'])} |"
            )
        lines.extend([
            "",
            "### Confusion matrix",
            "",
            "Rows are expected labels; columns are predictions.",
            "",
            "| Expected \\ Predicted | low | med | high |",
            "|---|---:|---:|---:|",
        ])
        for actual in CLASSES:
            row = metric["confusion_matrix"][actual]
            lines.append(f"| {actual} | {row['low']} | {row['med']} | {row['high']} |")
        lines.append("")

    tokens = report["token_totals"]
    lines.extend([
        "## Usage",
        "",
        f"- Input tokens: {tokens['input_tokens']}",
        f"- Output tokens: {tokens['output_tokens']}",
        f"- Cache-creation tokens: {tokens['cache_creation_tokens']}",
        f"- Cache-read tokens: {tokens['cache_read_tokens']}",
        f"- Estimated cost: ${report['estimated_cost_usd']:.6f}",
        f"- Pricing version: `{report['pricing_version']}`",
        "",
        "## Methodology",
        "",
        "Cases are synthetic and split into development and holdout sets. The "
        "harness uses the production profile calculator, request builder, and "
        "last-five-message cap. Reports exclude request payloads and model reasoning.",
        "",
    ])
    return "\n".join(lines)


def write_report(report: dict, report_dir: Path) -> tuple[Path, Path]:
    """Write durable JSON plus a readable summary and refresh latest copies."""
    report_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.fromisoformat(report["created_at"]).strftime("%Y%m%dT%H%M%S%f")
    stem = f"triage-eval-{stamp}-{report['mode']}"
    json_path = report_dir / f"{stem}.json"
    markdown_path = report_dir / f"{stem}.md"
    json_text = json.dumps(report, indent=2) + "\n"
    markdown_text = _markdown_report(report)
    json_path.write_text(json_text)
    markdown_path.write_text(markdown_text)
    (report_dir / "latest.json").write_text(json_text)
    (report_dir / "latest.md").write_text(markdown_text)
    return json_path, markdown_path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--max-cases", type=int)
    parser.add_argument("--call", action="store_true")
    parser.add_argument("--confirm-eval", action="store_true")
    parser.add_argument("--report-dir", type=Path, default=DEFAULT_REPORT_DIR)
    args = parser.parse_args()
    if args.max_cases is not None and args.max_cases <= 0:
        parser.error("--max-cases must be greater than zero")
    if args.call and not args.confirm_eval:
        parser.error("--call requires explicit --confirm-eval")

    cases = load_cases(args.cases)
    if args.max_cases is not None:
        cases = cases[:args.max_cases]
    print(f"validated {len(cases)} synthetic case(s)")
    print(f"API calls about to be made: {len(cases) if args.call else 0}")

    if not args.call:
        for case in cases:
            request = _redacted_request(case["profile"], case["request_messages"])
            print(json.dumps({"case_id": case["case_id"], "request": request}, default=str))
        report = {
            "created_at": datetime.now().isoformat(),
            "mode": "preview",
            "validation_status": "passed",
            "prompt_version": PROMPT_VERSION,
            "prompt_fingerprint": prompt_fingerprint(),
            "model": MODEL,
            "pricing_version": PRICING_VERSION,
            "case_count": len(cases),
            "split_counts": _split_counts(cases),
            "api_call_count": 0,
            "token_totals": {name: 0 for name in TOKEN_FIELDS},
            "estimated_cost_usd": 0.0,
            "cases": [{
                "case_id": case["case_id"], "split": case["split"],
                "tags": case["tags"], "status": "validated",
            } for case in cases],
        }
        json_path, markdown_path = write_report(report, args.report_dir)
        print("zero-token redacted preview complete; no client created")
        print(f"reports written: {json_path} and {markdown_path}")
        return

    client = _create_anthropic_client()
    rows = []
    totals = Counter()
    for case in cases:
        try:
            result = run_triage(client, case["profile"], case["request_messages"])
            usage = result.pop("_usage")
            totals.update(usage)
            rows.append({
                "case_id": case["case_id"], "split": case["split"],
                "tags": case["tags"], "status": "success",
                "expected": case["expected"],
                "prediction": {name: result[name] for name in case["expected"]},
                "usage": usage, "estimated_cost_usd": estimate_cost_usd(usage),
            })
        except Exception as exc:
            rows.append({
                "case_id": case["case_id"], "split": case["split"],
                "tags": case["tags"], "status": "failure",
                "error_type": _safe_error_type(exc), "expected": case["expected"],
            })
    report = {
        "created_at": datetime.now().isoformat(),
        "mode": "paid",
        "prompt_version": PROMPT_VERSION,
        "prompt_fingerprint": prompt_fingerprint(),
        "model": MODEL,
        "pricing_version": PRICING_VERSION,
        "case_count": len(cases),
        "split_counts": _split_counts(cases),
        "api_call_count": len(cases),
        "success_count": sum(row["status"] == "success" for row in rows),
        "failure_count": sum(row["status"] == "failure" for row in rows),
        "token_totals": {name: totals[name] for name in TOKEN_FIELDS},
        "estimated_cost_usd": estimate_cost_usd(totals),
        "metrics": metrics(rows),
        "cases": rows,
    }
    json_path, markdown_path = write_report(report, args.report_dir)
    print(json.dumps({key: report[key] for key in report if key != "cases"}, indent=2))
    print(f"reports written: {json_path} and {markdown_path}")


if __name__ == "__main__":
    main()
