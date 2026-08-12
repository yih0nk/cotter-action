"""Unit tests for the Markdown renderer (scripts/report_markdown.py)."""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from report_markdown import counts, marker, to_markdown  # noqa: E402

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "sample_report.json")


def load_sample():
    with open(FIXTURE, encoding="utf-8") as fh:
        return json.load(fh)


def test_counts():
    report = load_sample()
    n_pass, n_fail, n_info = counts(report)
    assert n_pass >= 1
    assert n_fail >= 1  # the sample has a failing learned-adversary category
    assert (n_pass + n_fail + n_info) == len(report["results"])


def test_marker_is_stable_and_tagged():
    assert marker("default") == "<!-- cotter-action:default -->"
    assert marker("nightly") != marker("default")


def test_renders_header_and_verdict():
    md = to_markdown(load_sample(), title="My gate", tag="default")
    assert md.startswith("<!-- cotter-action:default -->")
    assert "## My gate" in md
    # sample overall_passed is False
    assert "OVERALL: ❌ **FAIL**" in md
    assert "passing ·" in md


def test_one_table_row_per_result():
    report = load_sample()
    md = to_markdown(report)
    # a table row per result (lines starting with "| " and not the header)
    rows = [ln for ln in md.splitlines() if ln.startswith("| ") and "Category" not in ln]
    # minus the separator row
    rows = [ln for ln in rows if set(ln.replace("|", "").replace(":", "").strip()) - {"-", ""}]
    assert len(rows) == len(report["results"])


def test_pipes_in_summary_are_escaped():
    report = {
        "cotter_report_version": 1,
        "policy_name": "p",
        "env_id": "Env-v0",
        "overall_passed": True,
        "results": [
            {"category": "c", "name": "n", "passed": True, "summary": "a | b | c"}
        ],
    }
    md = to_markdown(report)
    assert "a \\| b \\| c" in md  # pipes escaped so the table is not broken


def test_run_url_in_footer():
    md = to_markdown(load_sample(), run_url="https://example.com/run/1")
    assert "[workflow run](https://example.com/run/1)" in md


def test_empty_results():
    report = {"cotter_report_version": 1, "policy_name": "p", "env_id": "E",
              "overall_passed": True, "results": []}
    md = to_markdown(report)
    assert "No test categories were executed" in md
    assert "OVERALL: ✅ **PASS**" in md


def test_no_tag_omits_marker():
    md = to_markdown(load_sample())
    assert not md.startswith("<!--")
