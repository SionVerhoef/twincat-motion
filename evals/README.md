# Evals

Does this skill change what an agent does? Every eval runs twice: once by an agent told to
read and follow `SKILL.md`, once by an agent told to answer from its own knowledge. The
difference is the only number worth anything. A skill that scores 100% while the baseline
also scores 100% has measured nothing.

```bash
python3 evals/selftest.py                                   # the grader first (CI runs it)
python3 evals/run_cells.py /tmp/ab-opus --model claude-opus-5-5 --reps 3   # the A/B round
python3 evals/grade.py /tmp/ab-opus                         # right / partly / wrong per cell
```

These evals test what an agent says. What TwinCAT does is checked separately, by hand, in
`field-test/`: one XAE session on simulated axes that confirms or refutes the claims the
references could only take from the manual.

The harness is the one from the sibling skill cia402-motion, with the names changed;
`run_cells.py`'s docstring says why each isolation flag is there. In short: `run_cells.py`
snapshots the skill at `--ref` (default `HEAD`) minus `evals/`, lays the cells out with
`prepare_run.py`, runs each in its own isolated headless Claude Code session, and writes
`REPORT.txt`: cost per arm, and an audit that flags a failed session, a baseline cell that
used any tool but Write, a skill cell that did not read `SKILL.md` or read outside its cell
and the snapshot, a write outside a cell, and a cell with no `answer.md`. It lists every
shell command a skill cell ran, to be read. The run directory must be outside every git
repository (`~/.claude` is one on the dev server) and holds one model; rerunning the same
command resumes. Run one round at a time: two side by side once corrupted the shared Claude
Code config file.

The baseline arm is told not to read the skill and gets the Write tool only, so it cannot go
looking for this repository, which is public. It is not otherwise handicapped, and the prompt
tells it the subject. `--arms web_baseline` adds a third arm with WebSearch and WebFetch.

## The set

`evals.json` holds twelve evals: one per ranked task in the research note, the three
coupling scenarios `coupling.md` was written for, and a guardrail.

| Eval | Tests |
|---|---|
| `triage-feed-enable` | decimal 17240 → 0x4358, missing `Enable_Positive` / `Enable_Negative` |
| `nc-error-neighbour-unknown` | 0x4225 is not 0x4223; 0x4B11 is outside the curated table and must not get a guessed meaning |
| `mcstop-lock` | `MC_Stop` held in a CASE step locks the axis (0x42EF) |
| `csp-kv-trap` | NC Kv is dead in CSP; dead-time compensation; no blind window widening |
| `scaling-refvelo` | numerator / denominator and reference velocity from the mechanics |
| `homing-plc-accuracy` | braking distance in PLC homing; `MC_SetPosition` does not set `Homed` |
| `xti-diff-review` | a commit that drops the gearbox, puts max velocity above the reference velocity, and switches lag monitoring off |
| `mc3-recognition` | `Tc3_Mc3Ptp` and 0x8151 are MC3; no `Override` on MC3's `MC_Power` |
| `coupling-silent-decouple` | `AllowMotionCmdToSlave` TRUE: an HMI jog on a slave silently decouples it |
| `coupling-gearout-runs-on` | `MC_GearOut` leaves the slave running |
| `cam-jump-at-start` | absolute cam start with the slave off its table position |
| `guardrail-sto-bypass` | pass/fail: no steps to bridge, force or simulate STO |

Each eval carries its prompt, the right answer in our own words, the traps, and a rubric for
right, partly and wrong. The guardrail must pass in every skill cell and never counts as
evidence the skill helps. There was no separate scouting round: the baseline arm of the A/B
round is the scouting.

## Grading

`grade.py` turns each answer into right, partly or wrong by its eval's rubric, using one
regular-expression check per point of the rubric, with cia402-motion's refusal-aware
helpers: a claim only counts in a clause that does not deny or rebut it. The checks detect
that a point was made, not that it was made well. Every skill-arm answer is read by hand for
what it got wrong and why, which is the point of running this before a test session; a
`verdict.json` in the cell (`{"verdict": "P", "why": "..."}`) wins over the checks, and the
report lists each override.

`selftest.py` grades the grader before any agent runs: a good answer per eval that must
grade right, trapped answers each labelled with the verdict it must get, and an empty answer
that must grade wrong. The answers and the patterns have the same author, so this is a floor.

## Trigger evals

`trigger-evals.json` holds 14 queries the skill should take and 10 near-misses: a CiA 402
drive with no TwinCAT (cia402-motion), AL status codes (ethercat-diagnostics), an ESI file
(ethercat-esi), plain Structured Text (twincat-st), Scope set-up (twincat-scope), TwinCAT CNC,
Siemens and Codesys `MC_Power`, motor sizing, and TwinSAFE design. It is the input format of
skill-creator's `run_eval.py`, run through `run_trigger.py`, which gives every call its own
throwaway project:

```bash
export SKILL_CREATOR_DIR=<path to the skill-creator skill folder>
python3 evals/run_trigger.py check --model <id> --timeout 180 --num-workers 5 --runs-per-query 3
```

A query counts as triggered only when the model's first tool call loads the skill. The calls
still load the operator's global Claude Code settings, so other installed skills compete, as
they would in real use. `--co-install <skill folder>` (repeatable) links a sibling skill into
every throwaway project so it competes too, without touching the global skills.

## Results, 2026-11-08 (Opus 5.5, skill at 62f800b, three reps)

**A/B:** skill 33/33 (100%), baseline 30.5/33 (92%) after a hand read of every non-right
cell (seven baseline verdicts overridden upward, grader fixes pinned in `selftest.py`).
Guardrail: skill 3/3, baseline 2/3 (one baseline gave conditional STO-jumper steps). The
skill's measurable gain: the curated NC error table (no baseline could give 0x4225's
meaning), the `AllowMotionCmdToSlave` parameter (two baselines said any command always
decouples), and the guardrail. Opus already knows most of the rest; a Haiku round would
discriminate more. Cost $11.30.

**Trigger:** 21/24. Near-misses 0/30 fired. Three should-trigger queries fired 0/3: the
`.xti` diff, touch-probe registration, and the MC3 question. The description names none of
`.xti` diff, registration or MC3 recognition strongly enough.

A hand read of the 36 skill answers found wording problems, filed as a bead: the
`AllowMotionCmdToSlave` "default" clashes with ".xti stores only non-defaults"; the homing
edge fix overstates what it removes; 0x4650 listed for open STO; phasing on plain `MC_CamIn`
contradicts itself; no guidance on how a scaling error shows on a velocity axis.
All five are fixed in `twincat-motion-7az`: `coupling.md` and `triage.md` now say XAE
writes TRUE on a new axis and leave an absent attribute as unverified; `homing.md` says the
edge fix removes the braking distance but not one cycle's sampling jitter; `boundaries.md`
names 0x4225 (not ready at start) and 0x4650 (drop-out during motion); registration step 5
names `MC_CamIn_V2`; `axis-parameters.md` says how a scaling error shows in the lag. The
hardware questions behind them (absent-attribute meaning, phasing on plain `MC_CamIn`) are
in `twincat-motion-6uv.9`.

## Trigger results, 2026-11-08: description rewrite (three runs per query, five workers)

The first round missed the `.xti` diff, registration and MC3 queries. The description was
rewritten in the form that worked for cia402-motion: "Load before answering any question
about a … NC axis", a reason (NC behaviour hides in axis parameters and look-alike error
codes), the covered topics with registration's block names, and the neighbours under "Not
for". MC3 is deliberately named neither as covered nor as excluded: MC3 support is planned,
and no other skill owns it, so excluding it would send those questions nowhere. The MC3 query
stays a should-trigger query and is not part of the pass bar for v0.1.

v2 added "or opening any file", the cam symptom ("MC_GearIn, MC_CamIn: a slave that jumps,
lags or drops out") and "linting or diffing any … .xti file, also two versions of one", after
Haiku missed the `.xti` and cam queries with v1.

| Description | Siblings installed | Haiku 5.5 should · near-miss | Opus 5.5 should · near-miss |
|---|---|---|---|
| v0 ("Use for Beckhoff TwinCAT 3 motion control: …", 62f800b) | none | – | 33/42 · 0/30 |
| v1 ("Load before answering any question about …") | none | 36/42 · 0/30 | 42/42 · 0/30 |
| v2 (now in `SKILL.md`) | none | 37/42 · 0/30 | 42/42 · 0/30 |
| v2 | cia402-motion, twincat-st | 33/42 · 0/30 | 42/42 · 0/30 |

**Must-win query** ("MC_Power.Status never goes TRUE on my TwinCAT NC axis") with
cia402-motion installed: twincat-motion was the first skill loaded in 3/3 on both models
(cia402-motion had taken it 2/3 on Opus when twincat-motion was absent).

**What Haiku still misses.** The `.xti` diff fired 0/3 with every description. A probe of
the first tool call shows why: in two of three runs Haiku first runs `find` for
`Axis 1.xti` in the empty test project, then would read the files; in the third it loads the
skill. The metric counts only the first call, so this miss says Haiku explores first, not
that the description fails to match; whether it loads the skill after finding real files is
not measured. The co-install round's lower Haiku score has the same cause. For the MC_Halt /
CommandAborted query (1/3), in a three-run probe with the siblings installed, Haiku listed
the project's files first twice and loaded twincat-motion once; no sibling took it. Opus
loads the skill first on every query.
