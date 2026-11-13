# twincat-motion

An agent skill for Beckhoff TwinCAT 3 classic NC motion (`Tc2_MC2`): NC axis configuration,
MC_ function blocks, homing, gearing and camming, NC error codes, the `.xti` axis files, and
finding out why an axis won't enable or move.

> **Not affiliated with or endorsed by Beckhoff Automation GmbH & Co. KG, PLCopen or the
> EtherCAT Technology Group**, nor by any drive manufacturer named here. Product and standard
> names are used only to describe what this skill works with.
>
> **Safety.** This skill produces engineering suggestions, not validated machine software.
> Motion can crush, cut and kill. Never use its output for safety functions (STO, SS1, SLS,
> safe homing, guard monitoring). Those belong in a certified safety controller configured
> and validated per ISO 13849 / IEC 62061. An NC stop, a software limit or homing is not a
> safety function. Review every line, test with reduced velocity, acceleration and torque
> limits, and verify on the real machine before anyone stands near it. Responsibility for the
> machine stays with whoever commissions it.

**Status: v0.1.0.** Covers classic NC with `Tc2_MC2` on TwinCAT 3.1.4024. Field-tested on
4024.55 with **simulated axes only**; never run against a real drive. What is verified and
what is not: [Status](#status).

**What it has shown so far.** In A/B evals on Claude Opus 5.5 (eleven tasks, three runs
each), the skill scored 33 of 33 and the baseline 30.5. Opus already knows most NC basics.
Where it went wrong without the skill: no baseline could say what NC error 0x4225 means, two
said any motion command on a coupled slave always decouples it (it depends on an axis
parameter), and one gave conditional steps for jumpering STO. Details:
[`evals/README.md`](evals/README.md).

## What is in it

- `SKILL.md`: the rules an agent follows, and where to read next.
- `references/`: triage for an axis that won't enable or move, the axis lifecycle and
  `Tc2_MC2` behaviour, axis parameters with worked scaling and reference-velocity examples,
  all six homing options, gearing, camming, superimposed moves and touch-probe registration,
  how to propose configuration changes, the safety boundary and hand-offs, and a pointer page
  for what is out of scope (MC3, NCI/CNC, XTS, XPlanar, kinematics, the Advanced Motion Pack).
- `scripts/nc_error.py` and `scripts/axis_xti.py`: the tools below.
- `templates/`: `FB_Axis`, an axis wrapper, and two homing blocks (`FB_HomePlc`, PLC-based;
  `FB_HomeNc`, `MC_Home`), as TwinCAT 3 files. Status in `templates/README.md`.
- `evals/`: the A/B and trigger evals, their grader and its self-test, and the field-test
  protocol for one XAE sitting.

## Install

```bash
# Claude Code
git submodule add https://github.com/SionVerhoef/twincat-motion .claude/skills/twincat-motion
```

Pin a release rather than following `main`, and commit the pin:

```bash
git -C .claude/skills/twincat-motion checkout v0.1.0
git add .claude/skills/twincat-motion
```

A plain `git clone` of your repository leaves a submodule folder empty: clone with
`--recurse-submodules`, or run `git submodule update --init`. Without submodules, unpack a
release zip from [Releases](https://github.com/SionVerhoef/twincat-motion/releases) into the
same folder: the zip unpacks as `twincat-motion-<version>/`, so rename that folder to
`twincat-motion` (`SKILL.md` must sit directly in `.claude/skills/twincat-motion/`). Other agents that read skill folders (GitHub Copilot in VS Code from
`.github/skills/`, OpenAI Codex from `.agents/skills/`) should load it the same way; that is
untested.

The skill hands questions at its edges to sibling skills by name: **cia402-motion**,
**ethercat-diagnostics**, **ethercat-esi**, **twincat-st** and **twincat-scope**. None is
required. Without them it says which skill would own the question and answers the NC part.

## The tools

Both need nothing but Python 3.8 or newer (`py -3` on Windows):

```bash
python3 scripts/nc_error.py 0x4357                 # also 17239 or 16#4357
python3 scripts/axis_xti.py show "Axis 1.xti"      # the parameters the axis sets explicitly
python3 scripts/axis_xti.py lint "Axis 1.xti"      # inconsistent parameters
python3 scripts/axis_xti.py diff old.xti new.xti   # what changed, by parameter name
```

- **`nc_error.py`** explains 72 hand-picked NC error codes in its own words, each with what to
  check and a link to its Beckhoff Information System page. Lookup is exact: any other code
  gets its family and that family's page, never the nearest neighbour, because neighbouring
  codes mean different things (0x4357 and 0x4358 are opposite directions). It also explains
  the templates' own error codes (16#0001_xxxx), which are not NC codes.
- **`axis_xti.py`** reads `_Config/NC/Axes/*.xti` files without XAE. A file stores only values
  that differ from the default, so `lint` checks explicit values only. `diff` compares two
  versions by parameter, not by XML line. It never writes an `.xti` file. Exit codes: `lint`
  0 clean, 1 findings; `diff` 0 same, 1 different; 2 unreadable input.

## Status

The line between verified and not verified is the most important fact on this page.

**Verified**

- **Field test on TwinCAT 4024.55, `Tc2_MC2` 3.3.59, simulated axes.** The templates built
  with no errors or warnings and behaved as documented; the references state what that run
  observed and say so. One later change to `FB_HomePlc` (it re-checks the switch after
  moving off it) has not been re-run. Protocol: [`evals/field-test/README.md`](evals/field-test/README.md).
- **The templates pass twincat-st v0.6.0's** `tcpou.py check` and `st_review.py --pedantic`
  with no findings. CI runs both at that pinned tag.
- **`axis_xti.py` is tested on four public sample axes**, shipped with their licences in
  `tests/fixtures/xti/`. The tests pass on Linux and Windows, and on Python 3.8.
- **Agent behaviour in A/B evals** on Opus 5.5: see above.
- **The description fires on NC questions, not on their neighbours.** In trigger evals it
  fired in 42 of 42 runs of queries it should take on Opus 5.5 and 37 of 42 on Haiku 5.5, and
  in none of 30 near-miss runs on either. Haiku's misses are mostly runs where it explores the
  project before loading any skill: [`evals/README.md`](evals/README.md).

**Not verified**

- **No real drive.** Nothing here has moved a real axis. Untested on hardware: NC retain with
  real retain storage and an absolute encoder, `FB_HomeNc`'s timeout path (a simulated
  encoder always finds the sync pulse), which code a direction enable dropping during a move
  gives, and the Automation Interface apply script against a real project. The protocol for
  that run is ready (sections F and G of the field test).
- **Other TwinCAT builds.** Only 4024.55 was run. 4026 differences are named only where known.
- **The A/B was run on Opus only.** A Haiku round would show more of the skill's effect.
- **Drive-specific notes** (AX5000, AX8000) come from the vendor documentation, not from a
  drive on a bench.

## Tests

```bash
python3 -m unittest discover -s tests -v
```

CI also runs `scripts/check_skill.py` on the frontmatter, `scripts/check_private.py` (no real
AMS NetId, IP or MAC address may be committed), twincat-st's file checker and reviewer on
`templates/`, and `evals/selftest.py`, which checks that the eval grader tells a good answer
from a trapped one.

## Contributing

Read [CLAUDE.md](CLAUDE.md) first, human or agent. This repository is public, and anything
from a real machine (axis names, NetIDs, tuning values, `.tsproj` / `.xti` exports, scope
recordings) is treated as confidential: anonymise by substitution or leave it out.

## Licence

MIT — see [LICENSE](LICENSE). Sources and trademarks: [ATTRIBUTIONS.md](ATTRIBUTIONS.md).
