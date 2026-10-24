# Cross-integration repair results — 2026-10-24

Authorization: Rudy requested fixing all audit issues after explicitly authorizing
push/publication. USB install and HA encryption pairing were separately confirmed.
The original read-only audit is retained as historical evidence.

| Findings | Repair | Observed validation |
| --- | --- | --- |
| A01 | Device-wide operations, stop generations, compensating confirmed stop | Simulated each resume failure/cancel; later-stop/stale queue tests; live native-feed→tide |
| A02 | Durable original curve and pending intensity saved before writes | Partial write/reload/retry preserves 80→50%=40; 100 restores80; no live corruption injection |
| A03 | Framing/interface matching, legacy field echo, mandatory readback | Bad/mismatched notifications rejected; generic v2 readback failure rejected; real native path passed |
| A04 | Persist real feed deadline/recovery, cancel on unload, retry failed recovery | Fake clock/restart/unload/failed recovery tests; runtime loaded after restart |
| A05 | New preset replaces overlay baseline at current scale | New preset→100 restores new curve, including restart; partial preset pending recovery retained |
| A06 | Shared priority/generation for effects and modes | Old effect cannot override off; feed→view priority; curve transport never sends START independently |
| A07 | Restore outlets independently before pump recovery; startup reconcile | HA native blueprint validation; custom outlet targets preserved; no live outlet power cycle |
| A08 | API encryption, encrypted OTA, protected fallback AP | Firmware compiled, USB hash verified, HA encrypted reconfigure success, real event |
| A09 | Mode/outlet state listeners and shared-mode ownership | Timer/HA start/reconnect structure, shared and unknown mode tests; installed native validation |
| A10 | Required controller selection on six gesture events | Native expanded filters checked; actual selected controller long-event trace finished |
| A11 | Cancellable hold and release scripts | Timing model/structure, firmware compile, normal physical unlock/long accepted; abnormal physical timing still open |
| A12 | Refuse missing option snapshots; serialize read/modify/write | Read failure sends nothing; concurrent option edits preserve unrelated bits |

Software suites: GTS49 tests/16 subtests; Zetlight43 tests/9 subtests;
DualKey11 tests. Transport tests execute production classes through AST extraction
with fake BLE/UDP/store; they are not a full installed-HA unit test suite. HA native
validation was separately run against all four installed blueprints with real
triggers and empty optional inputs. Initial incorrect template entity listeners
were caught by actual HA save and replaced; the corrected save and validation passed.

Runtime: HA2026.10.2, native configuration check succeeded; GTS0.6.2 and
Zetlight0.22.0 loaded after restart. Live pump test: nativefeed/0 → tide/sine/55;
both cuco outlets unchanged/on. DualKey actual unlock12:06:24 and long12:06:27
Asia/Shanghai passed through encrypted pairing and scoped automation.

A proposed synthetic production event test was rejected by automatic approval
review and not executed. Safer read-only validation and real user input were used.
A first native pump test request incorrectly requested service response data and
was rejected before execution; the standard no-response service route then passed.

Remaining gates are in each project's existing ledger: actual return-pump outlet
cycle, light cross-mode/effect visual acceptance, abnormal physical key timing,
long-term connection stability, measured battery calibration and an actual status
severity source. No schedules, alarm thresholds, battery calibration coefficients,
or physical water-flow observations have been invented.
