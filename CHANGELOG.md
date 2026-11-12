# Changelog

## 0.1.0 — 2026-11-12

First release: classic TwinCAT NC (`Tc2_MC2`) on 3.1.4024. Field-tested on 4024.55 with
simulated axes; never run against a real drive (README, *Status*).

- Release: README gains the non-affiliation and safety notices, install steps and a
  verified / not-verified status; the Draft banners are gone; `AGENTS.md` points every agent
  at the contributor rules; `ATTRIBUTIONS.md` lists the bundled fixtures, twincat-st and more
  trademarks. `boundaries.md`: a drive linked to an NC axis must not also be driven by
  PLC code that writes its controlword, such as cia402-motion's `FB_Cia402Axis`.
- Pre-release fixes from the field-test re-review: `nc_error.py` explains the templates' own
  error codes (16#0001_xxxx) and keeps them clear of NC codes; `FB_HomePlc` checks the switch
  again after moving off it (not yet re-run); `homing.md` no longer claims the "not
  implemented" modes are absent from `Tc2_MC2`; the feed-enable eval expects 0x4223 for a
  missing enable at start; `check_private.py` no longer skips an address on a line that
  mentions a version.
- Field test on TwinCAT 4024.55 / `Tc2_MC2` 3.3.59 with simulated axes, folded in; new statements say "observed" and name that setup. `config-changes.md`: `axis-change.ps1` could never apply a change (the produced XML holds values as element text, not attributes); the CSV now names the value element (`XPath,Old,New`) and the script sets its text. Also new there: online parameter download and *Persistent Changes*, and what XAE does to a hand-edited `.xti`. `coupling.md`: an absent `AllowMotionCmdToSlave` is FALSE; `MC_Halt` on a protected slave gives 0x4267; `MC_GearIn.InGear` stays TRUE after the slave is decoupled (read `Coupled`); `MC_GearIn` onto a moving master is refused (0x425A); `MC_GearOut` with `MC_GearInDyn.Enable` held leaves the slave decoupled; phasing works on plain `MC_CamIn` and does nothing with the master stopped; the cam jump happens on the master's first movement; the external set-point setting's real `.xti` name. `homing.md`: observed `HomingState` numbers, the ±1.0E10 position during NC homing, `MC_Halt` aborting `MC_Home` (0x4B0A, no axis error), `MC_SetPosition` keeps `Homed`, all four retain options and per-axis *Data Persistence*. `axis-lifecycle.md` / `triage.md`: an explicit `MC_Halt` deceleration can ramp more gently than the move; velocity 0 gave 0x4359; a pulsed `Execute` hides an override's `CommandAborted`; a missing direction enable gives only 0x4223 on the block. `axis-parameters.md`: the three time-compensation places. `nc_error.py`: 0x4251, 0x4267, 0x4359 (meanings checked on InfoSys), 0x425A covers a moving master, 0x4B0A covers an `MC_Halt` abort. `axis_xti.py`: `ParameterChanged` is bookkeeping, kept out of `show` and of the parameter diff; more friendly names. Templates: unchanged code; README and headers say they were built and run on a simulated axis. Field-test protocol: fixes from the run, and the `MC_CamTableSelect` compile fix.
- `triage.md`, `axis-parameters.md`: the AX8000 is a CoE (CiA 402) drive, not SoE. `axis-parameters.md` gains AX8000 notes for the NC: position scaling 0x3005:01 must agree with the NC encoder scaling, the 0x605E "NC handling" fault reaction, and no drive homing.
- `nc_error.py`: ten more codes for coupling, superimposed moves and cam tables (0x4216, 0x421B, 0x4243, 0x4245, 0x424A, 0x425A, 0x4261, 0x4296, 0x4A00, 0x4A06). `triage.md`: a coupled slave's move is refused or silently decouples it, depending on an axis parameter.
- `references/coupling.md`: gearing (`MC_GearIn`, `GearInDyn`, `GearInMultiMaster`, flying-saw pointer), phasing, cam plates with `Tc2_MC2_Camming` (tables, coupling without a jump, activation and scaling), `MC_MoveSuperImposed`, touch-probe registration, the external set-point generator, and slave protected mode. Notes that axes created in 4024.55 allow motion commands on a slave, so a stray move silently decouples it.
- `templates/`: `FB_Axis` wrapper on Tc2_MC2 (power, reset, moves and halt behind methods, edge-safe triggering, one error path), `FB_HomePlc` (PLC-based homing; marks homed by own flag or the NC's state) and `FB_HomeNc` (`MC_Home`), with an example program. Reviewed, not run: they pass twincat-st v0.6.0's `tcpou.py check` and `st_review.py --pedantic`, which CI now runs.
- SKILL.md body: scope and safety notice, the rules (no safety logic, never move an axis, no `.xti` edits, look codes up, NC2 only, who closes the loop, triage first), reading table and hand-offs to the sibling skills.
- `references/`: triage for an axis that won't enable or move, axis lifecycle and Tc2_MC2 behaviour, axis parameters with worked scaling and reference-velocity examples, all six homing options, proposing configuration changes (parameter table or Automation Interface script), safety and skill boundaries, and a pointer page for what is out of scope (MC3, NCI/CNC, XTS, XPlanar, kinematics, TF54xx).
- `scripts/axis_xti.py`: shows, lints and diffs TwinCAT NC axis files (`.xti`) without XAE. Lints explicit values only, since a file stores only non-defaults. Tested on four public sample axes, shipped with their licences in `tests/fixtures/xti/`.
- `scripts/nc_error.py`: explains about 60 hand-picked TwinCAT NC error codes, each with what to check and a link to its InfoSys page. Any other code gets its family and that family's page. Exact matches only.
- Repository scaffold: draft SKILL.md, contributor rules, CI frontmatter check.
