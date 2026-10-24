# Recovery progress — 2026-10-24

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
