# Working on this repository

These rules apply to anyone — human or agent — **editing this repository**. They are not
instructions for using the skill on your own projects, where your code is your own.

## This repository is public

`github.com/SionVerhoef/twincat-motion` is world-readable, mirrored by anyone who clones it,
and installed into other people's setups. Assume every commit is permanent and already read
by a stranger.

## Treat real machine data as if it were under NDA

Axis configurations, motion code, drive parameters and traces come from real machines
belonging to real customers. Handle all of it as confidential by default — not only what
someone explicitly marked as such.

**Never commit anything that identifies a customer, a site, a machine or a controller.**
That includes, in files *and* in commit messages, changelog entries, eval transcripts and
issue text:

- **Customer, site or end-user names**, machine and serial numbers, project codes —
  including inside axis names, NC task names, POU and variable names, comments and file paths
- **AMS NetIDs, IP addresses, MAC addresses, hostnames, credentials, licence keys**
- **`.tsproj` / `.xti` exports** — they carry NetIDs, serial numbers, MAC addresses and the
  I/O tree of one machine. Never commit them raw.
- **Tuning and process data** — position and velocity loop gains, acceleration and jerk
  limits, cam tables, gear ratios, setpoints, cycle times. Commercially sensitive.
- **Safety logic tied to one installation** — STO/SS1 chains, interlocks, override paths
- **Scope recordings and screenshots** of a real axis, which carry all of the above in their
  channel names, legends and title bars

## Anonymise by substitution, not by deletion

The point is to remove identity while keeping the teaching value. Renaming a customer to
`Customer_A`, a machine to `Line1` and an axis to `Axis_X` costs nothing and keeps every
signal that matters — how the axis is configured, how the MC_ blocks are sequenced, how a
fault propagates.

**Names are stand-ins; structure is real.** If a pattern only makes sense with the original
names in place, describe it in prose instead. Naming a *product* is fine and often
necessary: "TwinCAT 4024", "Tc2_MC2", "AX8000", "AM8000" describe things anyone can buy or
download. Naming *whose* machine it is, is not.

**Use placeholders that identify nothing:** AMS NetId `1.2.3.4.1.1`, IP addresses from
`192.0.2.0/24`, MAC addresses from `00:00:5E:00:53:xx`. CI runs `scripts/check_private.py`
and fails on any other NetId, IP or MAC it finds. It cannot recognise a customer name — that
part is on you.

## What you may use, and what you may not

**Research is not redistribution.** Read any source you lawfully can — Beckhoff InfoSys, the
PLCopen Motion Control specification, drive manuals, vendor sample projects. Copyright
protects expression, not facts, rules, procedures or APIs: state that `MC_MoveAbsolute`
must see a rising edge on `Execute`; do not paste the documentation's paragraph about it.

- **Permissive** (MIT, BSD, Apache-2, 0BSD) — may ship. Copy the upstream `LICENSE` next to
  it and record the source in the same commit.
- **Copyleft** (GPL/LGPL) — do not vendor; it would relicense this skill. Ask first.
- **Proprietary** (InfoSys, vendor manuals, forums) — research only. Cite and link; reproduce
  no passages, tables, diagrams or screenshots.
- **Specs and standards** (PLCopen, IEC) — the technical rule can be stated independently;
  the document's own text, tables, diagrams and examples cannot.

Read the licence from the upstream `LICENSE` file, never a GitHub badge — `NOASSERTION`
across Beckhoff's GitHub estate generally resolves to Zero-Clause BSD. A citation is not
permission. Manuals, specs and real projects stay in `research/` (gitignored) or outside the
repo.

## Everything here must apply to everybody

This is a general-purpose skill, and its users work in shops that do not share one house
style. Rules and examples must make sense to a reader with no connection to the project they
came from. Don't promote one employer's axis-naming or homing convention to the only correct
answer, and don't write a preference as a rule without saying so.

## If something private has already been committed

**Stop and tell the maintainer.** Do not quietly delete it in a follow-up commit: on a public
repo the old blob stays reachable in history on every clone and fork. Removing it needs a
history rewrite and a force-push, which is the maintainer's decision.
