# Changelog

All notable changes to this project are documented in this file.

## [v0.02] - 2026-07-31

### Summary
This release updates `djs.py` to v0.02 and introduces improved report generation, enhanced hash scanning (including resume support and using last-generated file lists), more structured CLI options, and refined file discovery behavior. Also adds a small .gitignore entry for repository metadata.

### Added
- APP_VERSION bumped to `v0.02`.
- New helper functions for report generation and metadata:
  - `latest_report_file(command: str)`
  - `emit_comment`, `emit_reading`, `emit_scanning`, `emit_processing`, `emit_resuming`, `emit_skipping`, `emit_copied`, `emit_listed`, `emit_hashed`
- Hash scanning enhancements:
  - `--lastfilelist` (use the last generated `find` report as the input file list).
  - `--resume` (resume an interrupted `hashscan` using the most recent `hashscan` report).
- Reports now include standardized headers and footers with run metadata (directory, command, timestamp, extensions).
- `find_files()` results are now sorted before being returned.

### Changed
- `find_files()` behavior:
  - Previous `.noscan` marker-based skipping removed.
  - Directories whose names begin with `.` are now skipped (dot-directory exclusion).
  - Returned file and skipped-directory lists are sorted.
- `hashscan` workflow:
  - Can read file lists from an explicit file, the most recent `find` report, or perform a fresh scan.
  - Resume mode copies existing hash records into the new report and hashes only remaining files.
- CLI improvements:
  - Program description now includes version.
  - `hashscan` argument group reworked and new flags added.

### Removed
- `NOSCAN_FILE` constant and `.noscan`-based skip behavior.
- `collect_stats()` function replaced by inline `Counter`/`defaultdict` logic in `cmd_stats`.

### Fixed
- No user-facing bugfixes in code other than the new functionality described here.

### Notes / Migration
- If you relied on `.noscan` marker files to exclude directories, those will no longer be honored; dot-prefixed directories are excluded instead. Review any workflows that used `.noscan`.
- There is a likely typo in `cmd_stats` referencing `args.hashliist` (should be `args.hashlist`). A small follow-up fix is proposed.

---
