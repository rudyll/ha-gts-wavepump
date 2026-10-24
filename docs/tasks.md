# GTS HA recovery task ledger

This is the execution ledger for the GTS integration. Firmware/controller work
is tracked in the reef-dualkey repository ledger.

| ID | Source / authorization | Owner / order | Scope / dependencies | State | Acceptance / evidence | Next action |
| --- | --- | --- | --- | --- | --- | --- |
| GTS-R01 | Rudy recovery/deploy/brief pump test approved | Codex / P0 | 0.6.2 tide restart | Implemented, software-tested, deployed; bounded live test passed | After this HA restart: native feed/0 → tide/sine/55; both cuco outlets stayed on. 49 tests/16 subtests. Physical water movement not measured | Release tracked in GTS-R03 |
| GTS-R02 | Rudy's interrupted request: GTS native feeding; cuco is return-pump outlet, retain power-cut behavior | Codex / P0 | Existing feeding automation; depends GTS-R01 | Implemented and loaded; outlet cycle not physically tested | Start uses native feed button. End restores cuco power before BLE recovery; preserve outlet targets. Verify current 10-minute durations and cancel/restore. | Run supervised whole-tank feed/end acceptance, including return-pump outlets, when separately authorized |
| GTS-R03 | Rudy explicitly approved public push and formal release | Codex / P1 | 0.6.2 release; depends GTS-R06–08 | Released and verified | Remote manifest0.6.2, v0.6.2 target70a2dec, latest non-draft/non-prerelease GitHub Release and exact notes all verified; source deployed and native short test passed | No release work remains; separate hardware acceptance stays in linked rows |
| GTS-R04 | Found during recovery: installed storm automation lacks run-mode selector although upstream blueprint changed | Codex / P1 | Installed storm blueprint and its existing automation; tracked as F17 in ha-zetlight-led roadmap | Applied and HA-expanded config verified | Installed blueprint exposes run-mode inputs and automation selects tide after storm; no storm hardware test implied | F17 also fixes restart cancellation on clear/unavailable weather. Seven transition cases pass; do not claim a live storm test |

Software tests do not prove physical flow. HA telemetry proves reported state,
not measured water movement. No aquarium or release acceptance may be inferred.

## 2026-10-24 read-only audit findings

Source: Rudy requested auditing GTS/Zetlight/DualKey after authorizing publication.
Evidence and proposed fixes: [cross-integration review](audits/2026-10-24-cross-integration-review.md).
These findings were subsequently approved for implementation by Rudy: fix all problems.

| ID | Authorization | Owner / order | Scope / dependencies | State | Success criteria / evidence | Next action |
| --- | --- | --- | --- | --- | --- | --- |
| GTS-R06 | Rudy: fix all problems | Codex / P0 | A01 operation ordering and failed/cancelled start recovery | Implemented and tested; deployed | Generation gate, queued stale-work rejection, failure/cancel safe stop, explicit unconfirmed-stop error; normal native feed→tide live test passed | Retain abnormal BLE loss injection as a separate supervised test |
| GTS-R07 | Rudy: fix all problems | Codex / P1 | A02 immutable durable baseline | Implemented and software-tested; deployed | Original/pending state saved before hardware; restart/retry does not compound scaling; full curve readback | No live schedule corruption/failure injection performed; retry explicitly after real failure |
| GTS-R08 | Rudy: fix all problems | Codex / P1 | A03 response framing/matching/readback | Implemented, software-tested and normal native path tested | Invalid/wrong interface/field ignored; generic v2 ACK requires readback; timeout/cancel disconnects stream. Real feed and resume confirmed | Protocol lacks proven v2 request token; readback remains required |
