## Latest: GTS-R14 / ZetlightF35 App119 dynamic headroom prepared — 2026-10-26

Rudy confirms119% is App selectable maximum, not merely red warning. Source uses
raw99 and newer-firmware nonzero+20 App units, dynamic gain from daily maximum,
fresh curve/conflict checks and explicit storm unit metadata. Legacy raw display
retained.75tests/41subtests PASS; paired native HA2blueprints and actual-template→
actual-service three-baseline simulations PASS. Software-only, NOT installed or
released. No physical output/safety/flow acceptance. Guide docs/app-power-gain.md.

Actual two idle weather/storm rules protectively OFF and initial_statefalse
persisted without reload; user's restored lamp curve differs from oldHA baseline.
No pump/lamp service, curve/preset write, adoption, restart or newmonitor. Private
receipts/migration candidate retained in ignored Zetlight.private/headroom-20261026;
public docs contain no actual bindings/curve. Source worktree is this public-isolated
branch; NEVER push primary GTS private history. Existing0.7.0 manifest unchanged.
Next F35-D01/R14-D01 coordinated publication/install approval and explicit current
lamp baseline adoption, then runtime validation and authorized resume; strong reasoning.

---

## Latest: paired formal publication authorized and in progress — 2026-10-26

Rudy explicitly replies “可以” to publishing GTS0.7.0 and Zetlight0.23.0: push final
contents, create version tags and official GitHub/HACS releases. This does not
include HA installation/reload, blueprint import/activation or device actions.
F28/R11 publication is now authorized, superseding previous pending-approval
entries. Software preflight remains71GTS/102Zetlight tests,41/52subtests plus
native offline/joint validation; private acceptance history excluded. Remote
publication will only be marked complete after manifest/tag/Release/notes readback.
Next verify paired publication, strong reasoning; physical acceptance remains open.

---

## Latest: F28 preflight complete; publication decision pending — 2026-10-26

Release preflight found and fixed ambiguous storm failure telemetry: confirmed
stop/recovery versus stop unconfirmed. GTS71tests/41subtests PASS; Zetlight source
unchanged since102tests/52subtests PASS. Native offline config/service validation
and paired day/night actual-template→fan simulation PASS. Version/changelog/body
and private-history exclusion checks PASS. Read-only remote official versions
remain0.6.2/0.22.0, candidate tags absent. Known F27-A01 diagnostic width issue is
explicit in0.23.0 release notes, remains an open proposal. No publication/HA/
device action or monitor. See Zetlight docs/release-preflight-20261026.md.
Next F28/GTS-R11 explicit publication decision, strong reasoning; no further
consequential action inferred from “继续”. Earlier evidence remains historical.

---

## Latest: F26-P01 relative storm source/tests complete, release held — 2026-10-26

Rudy approves completing relative storm before formal publication. New additive
whole_tank_storm_gain blueprint requires GTS storm_gain and explicit pump/HA clock
agreement. Immutable daily baseline for both phases, gap >= current weather gain,
raw/gain caps, hour/off guards and owned tide restoration. Legacy storm_v2 unchanged.
70GTS/102Zetlight tests with41/52subtests pass; joint actual templates→fan method
simulations and offline native HA expanded-config validation pass. No HA connection,
config write/reload, device operation, activation, new monitor or publication.

GTS source belongs to public-isolated worktree /private/tmp/gts-weather-gain-public-20261026;
never push primary private acceptance history. Prepared0.7.0/0.23.0 changelogs and
release bodies now include this SOFTWARE scope. Physical flow/clock/night/restoration
acceptance and formal publication remain unapproved. See docs/storm-gain.md in
Zetlight for defaults/migration/limitations. Next F28/GTS-R11 paired release review,
strong reasoning; then separately authorized deployment/acceptance. Historical
notes below about unfinished F26-P01 are superseded by this entry for source only.

---

## Latest:0.7.0 release files prepared, not published — 2026-10-26

User asks about missing version update. Prepared manifest0.7.0 and changelog with
matching body/private temporary release file.57tests/28subtests PASS; official
latest remains0.6.2, v0.7.0 tag absent. This local release candidate is not pushed
or released. Paired Zetlight0.23.0 prepared. Formal publication approval pending;
no HA integration reload/device change or automation activation. Fixed manual
storm gain is not included/complete. Next GTS-R11 approved publication, strong
reasoning. Publish only from isolated public branch.

---

## Latest source candidate: GTS-R10 bounded weather gain — 2026-10-26

Normal100 preserves the tuned24h curve; above100 adds gain from that baseline.
Candidate entity range10–200, raw99 ceiling unchanged, exact100 restore and
retry/restart invariants tested. Invalid requested/saved values fail before writes.
57tests/28subtests passed on implementation; isolated public tree test below.

User authorizes GitHub source update. This tree contains only source/tests and
necessary notes, excluding unrelated private acceptance artifacts in local history.
No manifest/version/tag/release, HA/device change or new monitor. Deployed0.6.2
remains max100. Related weather blueprint checks live capability; fixed manual
storm needs baseline-relative redesign before activation. Next GTS-R10/F26-P01,
strong reasoning; release/installation remains separate and unapproved.

---

## Publication verified — 2026-10-24

- [rudyll/ha-gts-wavepump 0.6.2](https://github.com/rudyll/ha-gts-wavepump/releases/tag/v0.6.2): remote manifest, annotated tag target, latest release, non-draft/non-prerelease status, and exact changelog notes verified. Release source commit `70a2dec2314f`.
- [rudyll/ha-zetlight-led 0.22.0](https://github.com/rudyll/ha-zetlight-led/releases/tag/v0.22.0): remote manifest, annotated tag target, latest release, non-draft/non-prerelease status, and exact changelog notes verified. Release source commit `6091a096c770`.
- DualKey source push completed; no binary or private configuration published.
- Subsequent commits only record verification evidence unless specifically noted below.

# Current audit repair status — 2026-10-24

## Runtime evidence added after deployment

HA native config check passed; the single requested restart completed. GTS,
Zetlight and ESPHome entries are loaded. New GTS native short test observed
feed/0 then running tide/sine/55; both original cuco outlets remained on. GTS
command_error is null and recovery_required false. Zetlight active_mode=schedule,
command_error null, no pending curve recovery; its actual light on/off remains
unknown because the device only reports program setpoints.

DualKey pairing completed through the official encrypted reconfigure flow.
New firmware's real unlock event arrived at 12:06:24 Asia/Shanghai; the real
key1-long at 12:06:27 matched the selected device and finished its empty action.
All six current event filters are scoped to that device. A proposed synthetic
live-event injection was rejected by automatic approval review; it was not run
or bypassed. Read-only native config validation and the user's real physical
sequence provided the safer verification path.

All local listeners exited; no persistent observation job was installed.
Physical abnormal combo timing, continuous WiFi/battery stability, battery ADC
calibration, actual status/alarm source and whole-tank outlet cycling remain
explicit acceptance/input gaps, not unimplemented audit fixes.

## Latest: audit fixes implemented; runtime/release verification in progress

GTS-R06/R07/R08: device-wide reentrant operation gate, stop generations,
confirmed compensating stop on failed/cancelled starts; strict frame/interface
matching plus write readback; durable immutable intensity baseline and pending
write state. Unsupported firmware and incomplete curves fail closed. Commands
and pending recovery are visible in entity attributes. Full curve replacement
requires clearing an active intensity overlay. Runtime files and manifest 0.6.2
are staged on HA; native `ha core check` succeeded and one restart was requested.

Verification: 49 pytest tests, 16 subtests passed. Tests execute production
control classes with simulated BLE/store; no live failed-write injection.
The initial generic unittest runner lacked pytest; rerunning in the existing
pytest environment passed. Four installed blueprints passed HA native validation
with empty optional inputs. Initial templated entity listeners were rejected
by HA and replaced with native direct-input entity listeners before validation.

Pending: observe loaded entries; short native feed→tide recovery without cutting
outlets; verify public main/tag/GitHub Release. Whole-tank outlet cycling remains
a separate supervised acceptance gate. Next GTS-R03 / strong reasoning.

Rudy explicitly requested fixing all audit findings on 2026-10-24. Earlier
push/release authorization persists. Software tests simulate transport/storage;
they do not establish physical pump flow, LED colour, or outlet recovery.
No global scheduler or monitor was installed. The unrelated AquaTank checkout
was not changed. Runtime deployment was backed up under HA's
`/config/.reef-audit-fixes-20261024-115758`; blueprint/automation snapshots are in
`/config/.reef-blueprint-fixes-*`. Never blindly restore a whole automation file.

---

# Recovery progress — 2026-10-24

## Latest: cross-integration audit, publication held

Rudy explicitly approved pushing all three repositories and publishing GTS
0.6.2, then asked for a broader audit. The publication authorization persists;
no push/tag/release has run. A01/GTS-R06 also affects this session's new resume
helper and blocks publishing it unchanged. The earlier device short test does
not cover this error/concurrency path.

[Full read-only audit](../audits/2026-10-24-cross-integration-review.md): 12
findings, 7 high and 5 medium. Real-class simulated-I/O probes reproduced eight
counterexamples; configuration-derived combo timing supplies another. Production
code was not changed during this audit. Next proposed implementation task is
GTS-R06 with strong reasoning; original recovery checkpoints below remain
traceable. Fix approval is distinct from the already granted publish approval.

Rudy asked to recover Claude's interrupted GTS pump and DualKey work, and
explicitly approved deploying/restarting HA and a brief native-feed test without
switching the return-pump outlets. Current queue: [tasks.md](../tasks.md).

## Observed result

- Completed 0.6.2 restart sequence and added retained run-mode fallback after an
  HA restart/native feed. Manual/explicit-percentage paths remain manual.
- 28 tests plus 4 subtests passed. Replacing the fix with 0.6.1 reproduces the
  missing restart command failure. Tests isolate the real fan class AST and
  simulate BLE; they do not validate HA registration or physical water flow.
- Deployed fan.py and manifest 0.6.2 after backing up HA's prior code/config.
  Local/deployed fan SHA256 both:
  `66cf0c3741432185de079b412317365ce250e98a49f780129c3b78fd3e5073c6`.
- Authorized live test: running tide/sine/55 → native feed/0 → running
  tide/sine/55 observed on the subsequent heartbeat. The first immediate read
  was stale and failed the test assertion; a later read confirmed restoration.
  Do not report the immediate assertion as passing.
- Updated existing feeding automation: native GTS feed on start; on end restore
  the original return-pump outlets before attempting BLE recovery. Both feed
  durations read 10 minutes. Configuration saved and loaded; the entire outlet
  cycle has not been physically exercised in this session.
- Storm repair lives in the light repository's authoritative roadmap F17:
  clear-weather restart run now reaches restoration; existing installed
  automation now supplies the GTS tide selector. Seven software transition
  cases pass. HA's own substituted blueprint confirms the new condition and
  selector. No actual lightning/storm test ran.
- Final snapshot: pump on, tide/sine, reported power 60; return-pump outlets on;
  feeding/viewing modes off. The hour's schedule had advanced; 55 is the earlier
  test reading, not the final reading.

## Files and boundaries

Intended files: fan.py, manifest.json, CHANGELOG.md, tests/test_fan.py, this
progress note and docs/tasks.md. Existing untracked .DS_Store was not included.
No protocol/curve/intensity changes; no other aquarium data or AquaTank-native
files changed. No push/tag/GitHub Release performed yet. The full dedicated
stop/start cycle across HA restart remains an acceptance gap distinct from the
native-feed test.

Remote rollback backups are in HA's `/config/.reef-recovery-20261024/`.
Use its original fan/manifest and automation backup only after checking for
subsequent edits; never overwrite the whole current automation file blindly.

## Verification commands

- `python -m pytest -q -p no:cacheprovider tests` (isolated temporary pytest env)
- `git diff --check`
- SHA256 comparison with deployed fan.py; HA REST state reads and native-feed
  call/recovery; HA configuration API for feeding and key mapping.
- Official HA 2026.10.2 blueprint/save updates the cache and reloads only its
  consumers; blueprint/substitute confirmed loaded expansion. No global
  automation reload was needed.

## Next

GTS-R03: publish only after explicit authorization; verify remote main, manifest,
tag and non-draft/non-prerelease GitHub Release separately. GTS-R02: supervised
whole-tank feed/end acceptance including outlet power. GTS-R04/F17: real storm
acceptance remains open. Use strong reasoning for recovery/acceptance design;
normal model for a fully authorized mechanical release.
