# Changelog

## Unreleased

- `scripts/axis_xti.py`: shows, lints and diffs TwinCAT NC axis files (`.xti`) without XAE. Lints explicit values only, since a file stores only non-defaults. Tested on four public sample axes, shipped with their licences in `tests/fixtures/xti/`.
- `scripts/nc_error.py`: explains about 60 hand-picked TwinCAT NC error codes, each with what to check and a link to its InfoSys page. Any other code gets its family and that family's page. Exact matches only.
- Repository scaffold: draft SKILL.md, contributor rules, CI frontmatter check.
