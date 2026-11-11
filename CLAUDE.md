# CLAUDE.md

bibber renders APA 7 references from biblatex/BibTeX files. It ships as one
module, `bibber.py`, with a bash test suite, `bibber_test.sh`. It moved out of
`krissen/scripts` in 2026-11 with its history intact. Everything up to
`fix(bibber): collect repeated -k options …` (#51) was written there, so the
PR numbers in those commit messages refer to krissen/scripts.

## Environment

The repo has its own venv. Never borrow conda `default`.

```bash
python3 -m venv .venv && .venv/bin/pip install -e .
./bibber_test.sh                       # PASS/FAIL count; exit 0 only when FAIL=0
.venv/bin/ruff check bibber.py         # or plain `ruff check bibber.py`
```

- The live command is the symlink `~/bin/bibber`, which points to
  `~/dev/bibber/.venv/bin/bibber`. That is an editable install, so the main
  checkout on `main` is what runs. Do branch work in a worktree under
  `~/dev/bibber-worktrees/<slug>`, and give each worktree its own `.venv`.
- The default library comes from `$BIBBER_BIB` or
  `~/.config/bibber/default_bib`. Never hard-code a path in the source.

## Conventions

- **Language.** Code comments, docstrings and CLI help are in Swedish, as the
  code was written. README and commit messages are in English. Keep each file
  in one language.
- **Comments carry the rationale and the source.** Every formatting rule names
  the guide it follows, with its vyasa citekey or URL. Examples are Lund
  University Library's APA 7 guides (`LUB2026apa7lagar`, `LUB2026apa7laws`,
  `LUB2026apa7rapporter`), Purdue OWL and Normandale. A rule without a source
  is a proposal. Do not implement it.
- **Tests.** Every rendering change gets a test that fails on `main`. Prove
  that by running the suite against the old file:
  `./bibber_test.sh /path/to/old/bibber.py`.
- **Lint.** Ruff with the default configuration. The remaining `BLE001`/`S110`
  findings are deliberate, because fixing them changes behaviour.

## Data errors are not format errors

Fix a wrong reference where it arises. A wrong field in a library file is fixed
in the library (via vyasa), not by special-casing it in bibber. A missing
rendering rule is fixed here.

## Workflow

The global instructions apply in full. They cover Conventional Commits with a
mandatory scope, labels on every PR, the `/botreview-loop` with a final
Nagelfar round, merging once the conditions are met, and cleaning up after the
merge.
