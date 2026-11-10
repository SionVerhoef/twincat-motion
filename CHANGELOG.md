# Changelog

## Unreleased

- `triage.md`, `axis-parameters.md`: the AX8000 is a CoE (CiA 402) drive, not SoE. `axis-parameters.md` gains AX8000 notes for the NC: position scaling 0x3005:01 must agree with the NC encoder scaling, the 0x605E "NC handling" fault reaction, and no drive homing.
- `nc_error.py`: ten more codes for coupling, superimposed moves and cam tables (0x4216, 0x421B, 0x4243, 0x4245, 0x424A, 0x425A, 0x4261, 0x4296, 0x4A00, 0x4A06). `triage.md`: a coupled slave's move is refused or silently decouples it, depending on an axis parameter.
- `references/coupling.md`: gearing (`MC_GearIn`, `GearInDyn`, `GearInMultiMaster`, flying-saw pointer), phasing, cam plates with `Tc2_MC2_Camming` (tables, coupling without a jump, activation and scaling), `MC_MoveSuperImposed`, touch-probe registration, the external set-point generator, and slave protected mode. Notes that axes created in 4024.55 allow motion commands on a slave, so a stray move silently decouples it.
- `templates/`: `FB_Axis` wrapper on Tc2_MC2 (power, reset, moves and halt behind methods, edge-safe triggering, one error path), `FB_HomePlc` (PLC-based homing; marks homed by own flag or the NC's state) and `FB_HomeNc` (`MC_Home`), with an example program. Reviewed, not run: they pass twincat-st v0.6.0's `tcpou.py check` and `st_review.py --pedantic`, which CI now runs.
- SKILL.md body: scope and safety notice, the rules (no safety logic, never move an axis, no `.xti` edits, look codes up, NC2 only, who closes the loop, triage first), reading table and hand-offs to the sibling skills.
- `references/`: triage for an axis that won't enable or move, axis lifecycle and Tc2_MC2 behaviour, axis parameters with worked scaling and reference-velocity examples, all six homing options, proposing configuration changes (parameter table or Automation Interface script), safety and skill boundaries, and a pointer page for what is out of scope (MC3, NCI/CNC, XTS, XPlanar, kinematics, TF54xx).
- `scripts/axis_xti.py`: shows, lints and diffs TwinCAT NC axis files (`.xti`) without XAE. Lints explicit values only, since a file stores only non-defaults. Tested on four public sample axes, shipped with their licences in `tests/fixtures/xti/`.
- `scripts/nc_error.py`: explains about 60 hand-picked TwinCAT NC error codes, each with what to check and a link to its InfoSys page. Any other code gets its family and that family's page. Exact matches only.
- Repository scaffold: draft SKILL.md, contributor rules, CI frontmatter check.
