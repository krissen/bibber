# bibber

APA 7 references from biblatex/BibTeX files, in Swedish or English. You can
look entries up by citation key, take the best fuzzy-search match, or browse an
interactive search with clipboard copy.

```console
$ bibber --lang en -k Skollag2010
SFS 2010:800. *Skollag* [amended up to and including SFS 2026:1636]. https://www.riksdagen.se/…
```

Output is Markdown: italics are written as `*…*`.

## Install

```bash
git clone https://github.com/krissen/bibber.git
cd bibber
python3 -m venv .venv
.venv/bin/pip install -e .
ln -s "$PWD/.venv/bin/bibber" ~/bin/bibber   # or any directory on $PATH
```

bibber depends on `bibtexparser` 2 (currently a pre-release), `pylatexenc`,
`fuzzywuzzy` with `python-Levenshtein`, and `prompt_toolkit` and `pyperclip`
for the interactive mode.

## Usage

```bash
bibber -k KEY [KEY …]           # one reference per paragraph, in the order given
bibber -k A -k B                # -k can be repeated
bibber --keys keys.txt          # one key per line; '#' comments; '-' reads stdin
bibber -1 search terms          # best match
bibber -n 5 search terms        # five best matches
bibber search terms             # interactive search (TUI)
bibber -f bib -k KEY            # the BibTeX entry instead of APA
bibber --lang sv -k KEY         # language for this run only
bibber --lang en -k KEY --no-translation   # original titles only
bibber -b local.bib -b main.bib -k KEY   # several files; the first one wins on duplicate keys
```

### Default file

Without `-b`, bibber reads the file named by `$BIBBER_BIB`. If that is unset,
it uses the first non-comment line of `~/.config/bibber/default_bib`
(`$XDG_CONFIG_HOME` is respected). If neither exists, it falls back to the last
file you loaded.

```bash
mkdir -p ~/.config/bibber
echo "~/path/to/library.bib" > ~/.config/bibber/default_bib
```

### Language

The interactive command `lang sv|en` sets the language and saves it. `--lang`
applies to one run only.

## What is rendered

bibber covers the entry types that come up in Swedish humanities and education
research:

- articles
- books and edited volumes
- chapters, with crossref inheritance
- theses, including licentiate theses
- reports
- conference papers
- web pages and miscellaneous entries
- Swedish statutes (`@legislation`)

A few rules that go beyond the obvious:

- **Titles.** `title` and `subtitle` are joined with a colon, and the first
  letter after the colon is capitalised. `titleaddon` follows the title as a
  bracketed description.
- **Reports.** The `type` or `series` and the `number` go in parentheses, as in
  `(Rapport 5786)`, or `(Report No. 5786)` in English. The publisher is left
  out when it is the same as the author.
- **Swedish statutes.** These are rendered as
  `SFS 2010:800. *Skollag* [ändrad t.o.m. SFS …]. URL`, using the fields
  `number`, `series` and `version`.
- **Translated titles.** `title_translation_<lang>` holds a translation of the
  whole title, subtitle included. The field name follows biblatex-ms syntax,
  and `<lang>` is `en` or `sv`. When the field matches the output language,
  the translation is printed in brackets after the original title, outside
  the italics:
  `Hylén, T. (2012). Essentialism i religionsundervisningen: … [Essentialism in teaching religion: …].`
  Without a field for the output language, nothing is added. A Swedish
  text, for example, does not translate English titles.
  `--no-translation KEY …` drops the translation for those entries, and
  `--no-translation` on its own drops it everywhere. The krissen-tex module
  `krissen_translation` does the same in biblatex-apa.
- **Aliases.** `-k` also finds an entry by any key listed in its `ids` field,
  as biblatex does.
- **Crossref.** Chapters inherit their volume's fields the way biblatex does,
  and articles inherit their issue's. Fields that identify the parent itself,
  such as its DOI, ISBN or file, are not inherited.

The APA manual has no rules for Swedish public documents. The Swedish forms
follow the APA 7 guides of Lund University Library. They are named in the code
comments next to each rule.

## Cache

Parsed files are cached in `~/.cache/bibber/` (`$BIBBER_CACHE_DIR`). The cache
key covers the files, their order and the bibber source, so an edited file or a
new version invalidates the cache.

## Tests

```bash
./bibber_test.sh                 # uses .venv/bin/python; BIBBER_PYTHON overrides
```

The suite is self-contained. It writes its fixtures to a temporary directory
and points `BIBBER_CACHE_DIR` there.
