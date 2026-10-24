# GTS HA recovery task ledger

This is the execution ledger for the GTS integration. Firmware/controller work
is tracked in the reef-dualkey repository ledger.

| ID | Source / authorization | Owner / order | Scope / dependencies | State | Acceptance / evidence | Next action |
| --- | --- | --- | --- | --- | --- | --- |
| GTS-R01 | Rudy 2026-10-24: finish interrupted work; deployment and brief live test explicitly approved | Codex / P0 | Finish 0.6.2 tide restart; no dependencies | Implemented, software-tested, deployed; native-feed recovery observed | Old 0.6.1 fails restart regression; 28 tests and 4 subtests pass with fix. Preserve manual/explicit-percentage control, propagate BLE errors. Retained device mode covers HA reload/native feed. | Native feed reported feed/0, later heartbeat tide/sine/55; source hash matches deployed file. Off/on across a real HA restart remains a separate acceptance gap |
| GTS-R02 | Rudy's interrupted request: GTS native feeding; cuco is return-pump outlet, retain power-cut behavior | Codex / P0 | Existing feeding automation; depends GTS-R01 | Implemented and loaded; outlet cycle not physically tested | Start uses native feed button. End restores cuco power before BLE recovery; preserve outlet targets. Verify current 10-minute durations and cancel/restore. | Run supervised whole-tank feed/end acceptance, including return-pump outlets, when separately authorized |
| GTS-R03 | Interrupted 0.6.2 release work; public publication requires final authorization | Codex / P1 | Commit, push, tag and HACS GitHub Release; depends GTS-R01 | Publication authorized, held by GTS-R06/A01 | Manifest and changelog match; tests; remote main, tag target and non-draft/non-prerelease Release verified separately | Local commit exists; Rudy explicitly approved push/release. Fix GTS-R06 first, then resume authorized publication without asking for push approval again |
| GTS-R04 | Found during recovery: installed storm automation lacks run-mode selector although upstream blueprint changed | Codex / P1 | Installed storm blueprint and its existing automation; tracked as F17 in ha-zetlight-led roadmap | Applied and HA-expanded config verified | Installed blueprint exposes run-mode inputs and automation selects tide after storm; no storm hardware test implied | F17 also fixes restart cancellation on clear/unavailable weather. Seven transition cases pass; do not claim a live storm test |

Software tests do not prove physical flow. HA telemetry proves reported state,
not measured water movement. No aquarium or release acceptance may be inferred.

## 2026-10-24 read-only audit findings

Source: Rudy requested auditing GTS/Zetlight/DualKey after authorizing publication.
Evidence and proposed fixes: [cross-integration review](audits/2026-10-24-cross-integration-review.md).
These rows record findings; the audit itself does not authorize expanded implementation.

| ID | Authorization | Owner / order | Scope / dependencies | State | Success criteria / evidence | Next action |
| --- | --- | --- | --- | --- | --- | --- |
| GTS-R06 | Audit requested; implementation proposal | Unassigned / P0 | A01: whole-operation ordering and failure/cancel recovery | Confirmed by simulated transport; release blocker | Later stop must remain effective; no unexplained manual power80 after failed tide write; exercise each failed stage and cancellation | Strong reasoning: design/implement transaction and recovery boundary, then re-review before 0.6.2 publication |
| GTS-R07 | Audit requested; implementation proposal | Unassigned / P1 | A02: partial tidal writes and immutable baseline | Confirmed by partial-write/retry probe | Partial failure must not replace original curve or compound scaling; original 80→50% stays40 in every segment | Add durable baseline/operation state and explicit retry/readback policy |
| GTS-R08 | Audit requested; implementation proposal | Unassigned / P1 | A03: response validation and request correlation | Confirmed: invalid ACK accepted | Bad/unrelated/late/error frames cannot confirm current write; unsupported confirmation remains unknown | Trace captured ACK contract and add matcher/readback tests |
