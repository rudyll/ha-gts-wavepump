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

## GTS-R10 — bounded daily-baseline gain source candidate (2026-10-26)

User clarifies that normal100% must preserve the tuned daily curve; adverse
weather adds gain above100 rather than reducing normal first. Public source
candidate expands tidal gain10–200, retains raw POWER_MAX99 and immutable24h
baseline. Repeated writes/retry/restart do not compound;100 restores exactly.
Requested/persisted invalid gains are rejected. Entity IDs/storage keys unchanged.

Software scope:57 local tests/28subtests passed before publication; matching
weather-blueprint source has a live entity-max guard. Neither gain nor command
percentage proves actual flow. Firmware/hardware bounds not recharacterized.
No integration version/tag/HACS release or live deployment performed. Released
0.6.2 still exposes max100; paired publication is source only. User authorizes
GitHub update, not device operation. Owner Codex/P1; next linked F26-P01 strong
reasoning: align manual storm to daily baseline, then separately approve a
coordinated release/installation/test window. Private raw acceptance records
from unrelated local history are excluded from this publication tree.

## GTS-R11 — release preparation after version question (2026-10-26)

User asks why integration versions were not updated. Prepared0.7.0 manifest and
matching changelog/release body,57tests/28subtests PASS; intended tag absent and
current official version0.6.2 verified. Local candidate only, no new tag/Release
or HA/device change. Formal non-prerelease publication awaits explicit approval
under global high-impact-change rule; source GitHub update authority stays valid.
Use this isolated public branch, never primary private acceptance history.
Next R11 publish paired with Zetlight0.23.0 if approved, strong reasoning.

## GTS-R12 — baseline-relative transient storm action (2026-10-26)

Rudy approves linked ZetlightF26-P01 source/tests before release. Codex/P1;
depends R10. SOURCE/TEST COMPLETE: storm_gain reads fresh config/current hour
under operation lock, immutable baseline, cap/weather/off/feed/pending/clock
guards, bank preloading before mode selection and confirmed heartbeat/failure
stop.70tests/41subtests; actual blueprint→fan method day/night simulation passes.
No live HA connection/device operation. Config-v2 only; manual banks retain the
last transient setpoint. Actual tank flow and clock agreement unverified.
Source is in this public-isolated worktree, not primary private acceptance branch.
R11 publication remains HELD pending explicit approval; changelog/release body
updated to include software scope. Next R11/F28 review, strong reasoning, then
separately authorized supervised deployment/acceptance.

### GTS-R11-P01 — preflight stop-diagnostic correction (2026-10-26)

User “继续” advances local review, not formal publication. Codex/P1, R12 dependency.
DONE for source preflight: reproduced two failing diagnostic assertions, then
exposed confirmed-stop/recovery versus stop-unconfirmed, preserving failure/cancel.
71tests/41subtests and joint/native offline validation PASS. Candidate0.7.0 body
updated exactly with changelog. Public ancestry/private exclusion PASS. No HA/device
action or publication; R11/F28 remains pending explicit approval. Paired report
is Zetlight docs/release-preflight-20261026.md. Next publication decision, strong
reasoning; primary GTS private history must never be pushed.

### F28-R01 / GTS-R11 publication authorization — 2026-10-26

Source: Rudy explicitly says “可以” to formal paired publication of GTS0.7.0 and
Zetlight0.23.0. Codex/P1, dependencies F28-P01/R11-P01 complete. ACTIVE: authorize
final default-branch push, matching vtags and non-draft/non-prerelease GitHub
Releases with exact reviewed changelog notes, followed by remote verification.
Scope excludes HA installation/reload/import/activation and all device actions.
Use isolated public GTS tree, never primary private acceptance-history branch.
Success: remote versions/tags/final commit/official status/exact notes match.
Next complete and record actual remote readback, strong reasoning.
