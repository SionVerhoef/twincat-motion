# Changelog

## Unreleased

- A/B evals made fairer: the baseline arm gets the same tools as the skill arm (Read, Bash
  and the rest), and every arm is audited for reads, shell commands and web requests that
  reach the skill. Evals whose reference rests on a fact seen only on a simulated axis name
  it in `sim_only`: the judge does not hold an answer to it, and `grade.py` also reports the
  score without those evals. README leads with the Haiku round (33 vs 19), not Opus.
- `evals/grade.py` no longer passes three wrong answers as right: denying a missing feed
  enable (`triage-feed-enable`), keeping `Execute` TRUE and calling `MC_Reset`
  (`mcstop-lock`), and guessing 0x4B11's meaning after saying it is unverified
  (`nc-error-neighbour-unknown`). Each is now a trapped answer in `selftest.py`.
- `agents/openai.yaml` gives OpenAI Codex a display name and blurb; `check_skill.py` guards
  their lengths (blurb 25-64 characters).
- The `description` opens with what the skill is, then "Use when …", keeping "load it before
  answering, or opening any file" and every covered topic and exclusion. Scored level with the
  previous one (Opus 40/42 vs 42/42, Haiku 36/42 vs 35/42, sibling skills installed);
  `evals/README.md` also records why two trigger evals must not run in parallel.
- `SKILL.md` and `templates/README.md`: load the project's own written coding standard, if
  it has one, before adapting a template. It outranks the templates on naming, layout and
  structure, not on the `Tc2_MC2` behaviour they are built around or the safety rules.
- `templates/README.md`: plain *Add > Existing Item* is the default way to bring the
  templates in; twincat-st's `tcpou.py` is optional, for fresh GUIDs when a template goes
  into one project twice. The field test (B1) gains a duplicate-GUID check.
- References trimmed, no rule dropped: field-test provenance is a `(sim, 4024.55)` marker
  (defined in `SKILL.md`, Status), repeated facts have one home with pointers, the triage
  step 4 table is scannable, and the `MC_Stop` release wording agrees. 15097 → 14865 words.

## 0.2.0 — 2026-11-17

Second release: three field-test runs on simulated axes folded in, `FB_Axis` limit and
homed-gate inputs, and a step-chain sequencer for the field test. Still never run against a
real drive.

- Third field-test run (4024.55, sequencer): the templates build with 0 warnings. Now
  observed: an `Acceleration` of 0 uses the axis default; a second rising edge on a busy
  move changes nothing; `MC_Halt` with `Deceleration` 0 on a decoupled slave uses the
  slave's own default. `triage.md` / `nc_error.py`: 0x4357 / 0x4358 never reach the PLC,
  they appear in the XAE error list next to the block's 0x4223. Protocol and sequencer: D5
  tells the operator to read the error list, E3 reads Axis 2's dynamics with
  `MC_ReadParameter` and logs the master's velocity, E1/E7 no longer log `InGear`. New
  `evals/field-test/read-log.ps1`, a read-only ADS reader for the sequencer log.
- Second field-test run (4024.55, sequencer): `FB_Axis.MoveAbsolute` no longer reads the
  `VAR_IN_OUT` `Axis` from a method (compiler warning); the body copies `Axis.Status.Homed`
  for it. Limit inputs, homed gate, `FB_HomeNc` timeout and the `FB_HomePlc` switch re-check
  now observed. References: a direction enable dropping mid-move stops the axis with no
  code; `NotMoving` reads FALSE during a move at override 0; `MC_GearInDyn` onto a moving
  master is refused with 0x425A, and held enabled after `MC_GearOut` its `Error` pulses
  with 0x425A; `TaskDelayCycles="1"` is XAE writing its own default. Protocol and
  sequencer: C7 and E3 at 1200 mm/s so jerk no longer hides the value, C8 waits for A's
  second target to be decided, D5 clears the NC homed mark, E4 couples at standstill and
  samples `Error`, E7 skips the re-couple. `axis-change.ps1` stamps in milliseconds.
- Field test: new check D5 for `FB_Axis`'s limit switches and homed gate, also recording
  which code a direction enable dropping mid-move gives. B3 keeps `stMachine` in the test
  copy and adds an ungated move; the sequencer runs D5.
- `FB_Axis`: a `stMachine` input (`ST_AxisMachineIn`): its limit switches (default TRUE) feed
  `MC_Power`'s feed enables, and `MoveAbsolute` is refused until the axis is homed
  (`Axis.Status.Homed`, or `bHomedOwn` for `FB_HomePlc`'s own record). Not yet run.
- `out-of-scope.md`: CODESYS SoftMotion axes and the servo tuning procedure are covered by no
  skill.
- Field test: `evals/field-test/PRG_FieldTestSeq.st` runs sections C to E as step chains,
  with a per-step timeout and operator WAIT steps. It logs results, codes in hex and FB-flag
  changes as a 32-bit mask. Not built yet. `PRG_FieldTest`'s commands are now `VAR_INPUT`
  so it can write them; B3 patches `PRG_AxisExample` the same way. New check B4 runs
  project `lint` on the test project, and G1 expects L6 for the unlinked torque limit. The
  results template records the commit tested.
- `axis_xti.py lint` on a project folder or `.tsproj` checks the project, not only axis
  files: NC configuration inline or in `NC.xti`, axes inline or in files, links wherever
  they are stored. Rules P1-P3 (axis file missing or unlisted, shared Id) and L1-L8 (drive,
  encoder or PLC side linked to nothing; links to an axis that is gone; unrestored links
  still missing; drive outputs in the PDO assignment that nothing links, a limit as a
  warning). Inline axes now get the per-axis lint too. Checked against the 30 public projects
  with NC axes (132 axes) found among 352; six of them, trimmed, are the new fixtures in
  `tests/fixtures/tsproj/`.
- `axis_xti.py diff --table` prints a change as the parameter-change table of
  `config-changes.md`; `diff --ai-csv PRODUCED_XML CHANGES_CSV` writes it as `changes.csv`
  for `axis-change.ps1`, with each row looked up in the target axis's produced XML and its
  old value read from there. Nothing is written unless every row resolves.
- `axis-parameters.md`: EL70x7 stepper terminals on the NC. Automatic mode follows the PDO
  assignment, so a process-data edit can change the mode. Velocity scaling against 0x8012:05.
  The positioning interface is an alternative to the NC. A stall is an error only with
  0x8012:0A. `triage.md` asks for the EL70x7 mode.

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
