"""Publish a Cotter report to the GitHub Actions job summary and, on a
pull request, a sticky PR comment.

Standard library only (urllib) so the action needs no extra pip installs.
The comment is *sticky*: it carries a hidden marker keyed by ``--tag`` and
is updated in place on re-runs instead of piling up new comments.

Exit status is always 0 — reporting must never fail the build. Gate
enforcement is a separate step in ``action.yml``.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from report_markdown import marker, to_markdown  # noqa: E402

API = "https://api.github.com"


def _log(msg: str) -> None:
    print(f"[cotter-action] {msg}", file=sys.stderr)


def _load_report(path: str) -> dict | None:
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError) as exc:
        _log(f"could not read report at {path}: {exc}")
        return None


def _fallback_report(outcome: str, policy: str, env: str) -> dict:
    """A minimal report stand-in when Cotter produced no JSON (e.g. a
    usage error, or an older cotterbot without the flag)."""
    return {
        "policy_name": policy or "?",
        "env_id": env or "?",
        "overall_passed": outcome == "pass",
        "results": [],
    }


def _event() -> dict:
    path = os.environ.get("GITHUB_EVENT_PATH")
    if not path or not os.path.exists(path):
        return {}
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def _pr_number(event: dict) -> int | None:
    if "pull_request" in event and isinstance(event["pull_request"], dict):
        num = event["pull_request"].get("number")
        if isinstance(num, int):
            return num
    num = event.get("number")
    if isinstance(num, int):
        return num
    # refs/pull/<n>/merge fallback
    ref = os.environ.get("GITHUB_REF", "")
    parts = ref.split("/")
    if len(parts) >= 3 and parts[1] == "pull" and parts[2].isdigit():
        return int(parts[2])
    return None


def _request(method: str, url: str, token: str, payload: dict | None = None) -> dict | list:
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    req.add_header("User-Agent", "cotter-action")
    if data is not None:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=30) as resp:
        body = resp.read().decode()
    return json.loads(body) if body else {}


def _find_sticky(repo: str, pr: int, token: str, tag: str) -> int | None:
    needle = marker(tag)
    page = 1
    while True:
        url = f"{API}/repos/{repo}/issues/{pr}/comments?per_page=100&page={page}"
        try:
            comments = _request("GET", url, token)
        except urllib.error.URLError as exc:
            _log(f"could not list comments: {exc}")
            return None
        if not isinstance(comments, list) or not comments:
            return None
        for c in comments:
            if needle in (c.get("body") or ""):
                return c.get("id")
        if len(comments) < 100:
            return None
        page += 1


def _upsert_comment(repo: str, pr: int, token: str, tag: str, body: str) -> None:
    existing = _find_sticky(repo, pr, token, tag)
    try:
        if existing is not None:
            _request(
                "PATCH",
                f"{API}/repos/{repo}/issues/comments/{existing}",
                token,
                {"body": body},
            )
            _log(f"updated sticky comment {existing}")
        else:
            _request(
                "POST",
                f"{API}/repos/{repo}/issues/{pr}/comments",
                token,
                {"body": body},
            )
            _log("created sticky comment")
    except urllib.error.URLError as exc:
        _log(f"could not post comment: {exc} (need 'pull-requests: write' permission?)")


def _write_summary(body: str) -> None:
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not path:
        _log("GITHUB_STEP_SUMMARY not set; printing report instead")
        print(body)
        return
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(body)
        fh.write("\n")


def main() -> int:
    ap = argparse.ArgumentParser(description="Publish a Cotter report to CI surfaces.")
    ap.add_argument("--report", required=True, help="path to the JSON report")
    ap.add_argument("--title", default="Cotter report")
    ap.add_argument("--tag", default="default")
    ap.add_argument("--outcome", default="", help="pass | fail (used only as a fallback)")
    ap.add_argument("--policy", default="", help="policy name for the fallback report")
    ap.add_argument("--env", default="", help="env id for the fallback report")
    ap.add_argument("--comment", action="store_true", help="post/update a sticky PR comment")
    args = ap.parse_args()

    report = _load_report(args.report) or _fallback_report(args.outcome, args.policy, args.env)

    run_url = None
    server = os.environ.get("GITHUB_SERVER_URL")
    repo = os.environ.get("GITHUB_REPOSITORY")
    run_id = os.environ.get("GITHUB_RUN_ID")
    if server and repo and run_id:
        run_url = f"{server}/{repo}/actions/runs/{run_id}"

    body = to_markdown(report, title=args.title, tag=args.tag, run_url=run_url)

    _write_summary(body)

    if not args.comment:
        return 0
    if os.environ.get("GITHUB_EVENT_NAME") not in {"pull_request", "pull_request_target"}:
        _log("not a pull_request event; skipping PR comment")
        return 0
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("INPUT_GITHUB_TOKEN")
    if not token:
        _log("no token available; skipping PR comment")
        return 0
    pr = _pr_number(_event())
    if pr is None or not repo:
        _log("could not determine PR number; skipping PR comment")
        return 0

    _upsert_comment(repo, pr, token, args.tag, body)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
