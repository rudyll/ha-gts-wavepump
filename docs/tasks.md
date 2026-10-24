# GTS HA recovery task ledger

This is the execution ledger for the GTS integration. Firmware/controller work
is tracked in the reef-dualkey repository ledger.

| ID | Source / authorization | Owner / order | Scope / dependencies | State | Acceptance / evidence | Next action |
| --- | --- | --- | --- | --- | --- | --- |
| GTS-R01 | Rudy 2026-10-24: finish interrupted work; deployment and brief live test explicitly approved | Codex / P0 | Finish 0.6.2 tide restart; no dependencies | Implemented, software-tested, deployed; native-feed recovery observed | Old 0.6.1 fails restart regression; 28 tests and 4 subtests pass with fix. Preserve manual/explicit-percentage control, propagate BLE errors. Retained device mode covers HA reload/native feed. | Native feed reported feed/0, later heartbeat tide/sine/55; source hash matches deployed file. Off/on across a real HA restart remains a separate acceptance gap |
| GTS-R02 | Rudy's interrupted request: GTS native feeding; cuco is return-pump outlet, retain power-cut behavior | Codex / P0 | Existing feeding automation; depends GTS-R01 | Implemented and loaded; outlet cycle not physically tested | Start uses native feed button. End restores cuco power before BLE recovery; preserve outlet targets. Verify current 10-minute durations and cancel/restore. | Run supervised whole-tank feed/end acceptance, including return-pump outlets, when separately authorized |
| GTS-R03 | Interrupted 0.6.2 release work; public publication requires final authorization | Codex / P1 | Commit, push, tag and HACS GitHub Release; depends GTS-R01 | Local preparation | Manifest and changelog match; tests; remote main, tag target and non-draft/non-prerelease Release verified separately | Commit intended paths; obtain publication authorization before push/tag/release |
| GTS-R04 | Found during recovery: installed storm automation lacks run-mode selector although upstream blueprint changed | Codex / P1 | Installed storm blueprint and its existing automation; tracked as F17 in ha-zetlight-led roadmap | Applied and HA-expanded config verified | Installed blueprint exposes run-mode inputs and automation selects tide after storm; no storm hardware test implied | F17 also fixes restart cancellation on clear/unavailable weather. Seven transition cases pass; do not claim a live storm test |

Software tests do not prove physical flow. HA telemetry proves reported state,
not measured water movement. No aquarium or release acceptance may be inferred.
