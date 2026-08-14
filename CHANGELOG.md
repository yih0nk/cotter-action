# Changelog

## v0.1.0

Initial release.

- Composite GitHub Action that installs `cotterbot`, runs the Cotter test
  battery (`run`) or a regression check (`compare`), and gates the build on
  the result.
- Sticky pull-request comment with a per-category Markdown report, updated
  in place on re-runs.
- GitHub Actions job summary with the same report.
- JSON (and HTML, where the installed `cotterbot` supports it) report
  uploaded as a workflow artifact.
- Renders the **reproducibility manifest** and **content hash** when the
  report carries them (cotterbot ≥ 0.2.0, report schema v2).
- Optional flags (`--report`, `--report-html`) are feature-detected, so the
  action works across `cotterbot` versions.
- Self-test workflow exercising both modes against a bundled
  InvertedPendulum fixture; actions pinned to current majors (Node 24).
