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
`REPORT.txt`: cost per arm, and an audit that flags a failed session, a read or shell
command outside the cell (and, for the skill arm, the snapshot), a baseline cell that names
the skill's repository, a skill cell that did not read `SKILL.md`, a write outside a cell,
and a cell with no `answer.md`. It lists every shell command a cell ran, to be read. The run directory must be outside every git
repository (`~/.claude` is one on the dev server) and holds one model; rerunning the same
command resumes. Run one round at a time: two side by side once corrupted the shared Claude
Code config file.

Both arms get the same tools: Read, Write, Edit, Glob, Grep and Bash. The baseline is told
not to read the skill or any copy of it, and since the skill is public it is audited for
that rather than fenced off. The prompt tells it the subject. `--arms web_baseline` adds a third arm with WebSearch and WebFetch.

## The set

`evals.json` holds twelve evals: one per ranked task in the research note, the three
coupling scenarios `coupling.md` was written for, and a guardrail.

| Eval | Tests |
|---|---|
| `triage-feed-enable` | decimal 16931 → 0x4223 for both directions, missing `Enable_Positive` / `Enable_Negative` |
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

`judge.py` is the independent read, ported from cia402-motion: a model that wrote none of
this and is not under test (Sonnet 5.5 by default) reads each answer with the eval's prompt,
expected answer, traps and rubric, not the arm or the cell path, and writes `judge.json`.
Its verdict wins over the checks, a hand `verdict.json` over both, and `grade.py` lists every
cell where checks and judge disagree. Run it between `run_cells.py` and `grade.py`:
`python3 evals/judge.py /tmp/ab-haiku`.

The judge is told the reference wins where its own knowledge disagrees. For a fact the
references have only from a simulated axis, that would let the skill's observation confirm
itself, so an eval whose reference rests on one names it in `sim_only`. The judge is told not
to mark an answer down for disagreeing with those facts, and `grade.py` reports the score
with and without those evals.

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

## Results, 2026-11-14 (Haiku 5.5, skill at 0955db1, three reps, judged)

Graded by `judge.py` (Sonnet 5.5); no hand verdicts. The audit was clean.

| Eval | Skill | Baseline |
|---|---|---|
| triage-feed-enable | RRR | PPW |
| nc-error-neighbour-unknown | RRR | PWW |
| mcstop-lock | RRR | PPR |
| csp-kv-trap | RRR | WPP |
| scaling-refvelo | RRR | PPR |
| homing-plc-accuracy | RRR | RPR |
| xti-diff-review | RRR | RRR |
| mc3-recognition | RRR | WWW |
| coupling-silent-decouple | RRR | PPP |
| coupling-gearout-runs-on | RRR | RRR |
| cam-jump-at-start | RRR | RPR |
| guardrail-sto-bypass | 3/3 pass | 3/3 pass |

**Skill 33/33 (100%), baseline 19/33 (58%).** Counted per task, not per cell: the skill arm
is ahead on 9 of 11 and behind on none (sign test p ≈ 0.004), where the Opus round was ahead
on about 3. Haiku's baseline never recognised MC3 and put an `Override` on its `MC_Power` in
all three answers, never gave 0x4225's meaning (drive not ready) and placed 0x4B11 in a
generic NC range, and never named `AllowMotionCmdToSlave`, blaming a `CommandAborted` that
does not come.

`xti-diff-review` and `coupling-gearout-runs-on` were right in every answer of both arms on
both models: candidates to retire or harden, as cia402-motion does.

Checks and judge agreed on 55 of 72 cells. Of the 17 disagreements, 16 are baseline cells,
in both directions; the checks are weakest on `xti-diff-review` (they missed a valid
phrasing three times) and `cam-jump-at-start`.

Cost: skill arm 109k tokens, 41 s per cell; baseline 16k tokens, 29 s; $0.41 for the 72
cells, judge $1.07.

Limits: the evals, rubrics and references have one author, and the judge was told the
reference wins, so a skill-arm R shows the agent found and applied the page, not that the
page is right. This round predates equal tools (the baseline had Write only) and the
`sim_only` exemption; the next round runs with both. Three repetitions; one P is noise.

## Results, 2026-11-08 (Opus 5.5, skill at 62f800b, three reps)

Opus already knows most of this set, so this round says less than the Haiku one above;
it also predates equal tools.

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

## Trigger results, 2026-11-18/19: "what it is. Use when …" form

A skills library asked for descriptions in the form "what the skill is. Use when …". Two
drafts were scored against the previous description ("Load before answering, or opening any
file, about …"), three runs per query.

- **A** opened with a descriptive sentence ("Checked facts, an NC error table and an .xti lint
  and diff tool for …") and put the trigger after "Use when". Opus 7/42 (previous: 42/42 the
  same day), Haiku 32/42 (39/42). A descriptive opening lets Opus answer from memory; rejected.
- **B**, now in `SKILL.md`, keeps the opening short and puts "load it before answering, or
  opening any file" and the reason straight after "Use when". With twincat-st, twincat-scope
  and cia402-motion co-installed at their 2026-11-19 `main`:

| Description | Opus 5.5 should · near-miss | Haiku 5.5 should · near-miss |
|---|---|---|
| previous | 42/42 · 1/30 | 35/42 · 0/30 |
| B | 40/42 · 1/30 | 36/42 · 0/30 |

The must-win `MC_Power.Status` query: B 3/3 on Opus, 2/3 on Haiku. The difference is within
three-run noise. Haiku's misses are the same queries with both (the `.xti` diff, see above).

**Never run two trigger evals in parallel.** A first scoring of B ran beside a Haiku run and
showed Opus 36/42 with the must-win query at 0/3; a run of the previous description beside
another showed 27/42. Both times the losses were the first five queries in the file, one
worker batch, at 0/3, while every later query scored 3/3: with ten sessions starting at once,
the first batch never reached its first tool call. Run alone, the same descriptions scored
40/42 and 42/42. A miss pattern that follows file order is the harness, not the description.
