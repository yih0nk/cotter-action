#!/usr/bin/env bash
#
# Execute Cotter and normalize the result for the composite action.
#
# Cotter exits 0 (all categories passed), 1 (a category failed / regression),
# or 2 (config/usage error). We translate 0/1 into an "outcome" output and
# always exit 0 for those, so the reporting and artifact steps still run; a
# usage error (>=2) is a genuine failure and propagates.
#
# Optional flags (--report-html on run/compare, --report on compare) are
# feature-detected from --help, so the action works with any cotterbot
# version: older ones simply skip the artifacts they do not support.

set -uo pipefail

REPORT_JSON="${RUNNER_TEMP:-/tmp}/cotter-report.json"
REPORT_HTML="${RUNNER_TEMP:-/tmp}/cotter-report.html"
rm -f "$REPORT_JSON" "$REPORT_HTML"

command="${INPUT_COMMAND:-run}"

env_opt=()
if [ -n "${INPUT_ENV:-}" ]; then
  env_opt=(--env "$INPUT_ENV")
fi

# --report-html is spelled the same for both subcommands.
html_opt=()
if cotter "$command" --help 2>/dev/null | grep -q -- '--report-html'; then
  html_opt=(--report-html "$REPORT_HTML")
fi

echo "::group::cotter $command"
case "$command" in
  run)
    cotter run \
      --policy "$INPUT_POLICY" \
      --config "$INPUT_CONFIG" \
      "${env_opt[@]}" \
      --report "$REPORT_JSON" \
      "${html_opt[@]}"
    ;;
  compare)
    if [ -z "${INPUT_BASELINE:-}" ]; then
      echo "::error::command 'compare' requires the 'baseline' input"
      exit 2
    fi
    # 'compare' gained --report (JSON) later than --report-html; detect it.
    json_opt=()
    if cotter compare --help 2>/dev/null | grep -q -- '--report '; then
      json_opt=(--report "$REPORT_JSON")
    fi
    cotter compare \
      --baseline "$INPUT_BASELINE" \
      --candidate "$INPUT_POLICY" \
      --config "$INPUT_CONFIG" \
      "${env_opt[@]}" \
      "${json_opt[@]}" \
      "${html_opt[@]}"
    ;;
  *)
    echo "::error::unknown command '$command' (expected 'run' or 'compare')"
    exit 2
    ;;
esac
code=$?
echo "::endgroup::"

if [ "$code" -eq 0 ]; then
  outcome="pass"
elif [ "$code" -eq 1 ]; then
  outcome="fail"
else
  echo "::error::cotter exited with status $code (configuration or usage error)"
  exit "$code"
fi

{
  echo "outcome=$outcome"
  [ -f "$REPORT_JSON" ] && echo "report-json=$REPORT_JSON"
  [ -f "$REPORT_HTML" ] && echo "report-html=$REPORT_HTML"
} >> "${GITHUB_OUTPUT:-/dev/stdout}"

echo "COTTER_REPORT_JSON=$REPORT_JSON" >> "${GITHUB_ENV:-/dev/null}"
echo "Cotter outcome: $outcome (exit $code)"
