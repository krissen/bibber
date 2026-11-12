# bibber and similar tools

How bibber relates to other tools that render references from BibTeX or
biblatex files. It rests on a run made on 2026-11-12 and on the projects'
own documentation as read on that date. Treat it as a snapshot: the other
tools change, and a claim here may go stale.

## In short

No tool we found does all of what bibber does. pandoc and Typst render APA 7
from the same `.bib` files and handle the ordinary entry types well. In our
run neither one produced the Swedish forms or printed translated titles.
Pickers such as fzf-bibtex and citar search a library but do not render APA
text.

bibber does one narrow job: you find a few references by key or fuzzy search
and get finished APA 7 text, in Swedish or English, on stdout or the
clipboard. For a whole manuscript, use pandoc, Typst or biblatex.

## The run

Versions:

- pandoc 3.13 with `--citeproc` and the official `apa.csl`
  (citation-style-language/styles at `af0aea3`), using pandoc's bundled
  `sv-SE` and `en-US` locales
- Typst 0.15.1 with its built-in `apa` style
- bibber 0.1.0+17d5230

All three got the same eight entries, with `lang` set to Swedish and then to
English. In the output below, URLs are left out and long titles are
shortened.

### Swedish statute (`@legislation`, `number = {2010:800}`)

| Tool | Output |
|---|---|
| pandoc, sv | `Skollag (2010:800), Legislation No. 2010:800 (2010).` |
| pandoc, en | `Skollag (2010:800), Pub. L. No. 2010:800 (2010).` |
| Typst, sv | `Skollag (2010:800). (2010, juni 23).` |
| bibber | `SFS 2010:800. *Skollag* [ändrad t.o.m. SFS 2026:1636].` |

`apa.csl` formats every statute the way US law is cited. bibber follows the
form in Lund University Library's APA 7 guide to Swedish statutes. APA 7
itself has no rule for non-US legislation.

### Swedish doctoral thesis (`@phdthesis`)

| Tool | Output |
|---|---|
| pandoc, sv | `… [Phdthesis, Örebro universitet].` |
| pandoc, en | `… [PhD thesis, Örebro universitet].` |
| Typst | `… [Doctoral dissertation].` (the institution is lost) |
| bibber, sv | `… [Doktorsavhandling, Örebro universitet].` |
| bibber, en | `… [Doctoral dissertation, Örebro universitet].` |

### Translated title (`title_translation_en`)

bibber prints the translation in brackets after the original title when it
matches the output language:

`Hylén, T. (2012). Essentialism i religionsundervisningen: Ett
religionsdidaktiskt problem [Essentialism in teaching religion: A problem in
the didactics of religion]. *Nordidactica*, (2), 106–137.`

pandoc and Typst ignore the field. `apa.csl` uses `original-title` only for
the "original work published" note and has no bracketed translation. CSL-M
has `alt-` variables for translations, but we have not tested whether they
can produce this form.

### Other differences in the run

- **Casing.** pandoc lowercased a proper noun in an English title that has
  no `langid` ("*The school education system in india*"). bibber keeps the
  casing in the data.
- **Chapter with `crossref`.** pandoc and bibber agree. Typst printed the
  book title twice. bibber does not inherit the parent's DOI, so a chapter
  does not link to the book's DOI.
- **Order.** pandoc and Typst sort the list. bibber prints the entries in the
  order you ask for them.

## Other tools, from their documentation

| Tool | What it is | Renders APA text? |
|---|---|---|
| biber + biblatex-apa | The LaTeX APA style. It includes Swedish strings (`swedish-apa.lbx`) and is the model bibber follows for descriptions in brackets. | In LaTeX documents only |
| citeproc-js, citeproc-py, Citation.js | CSL processors, so they share `apa.csl` and its statute and translation behaviour | Yes, with CSL (not run by us) |
| Hayagriva | Typst's bibliography library and format | Yes (see Typst above) |
| fzf-bibtex, telescope-bibtex, citar | Pickers: search a `.bib` and insert keys or text from a template | No, according to their documentation |
| betterbib | Cleans and enriches `.bib` files | No; it complements bibber |
| Zotero, JabRef, papis, pubs | Reference managers | Not checked |

## When to use something else

- **A whole document with in-text citations:** pandoc, Typst, or biber with
  biblatex-apa. bibber only produces reference-list entries.
- **A style other than APA 7:** any CSL processor.
- **Cleaning or deduplicating a library:** betterbib, or a reference manager.
- **Managing PDFs and notes:** a reference manager.

## What bibber's forms rest on

- The Swedish forms follow Lund University Library's APA 7 guides, which are
  a library's interpretation, not APA's.
- `title_translation_<lang>` follows the biblatex-ms field syntax. A library
  without the field gets no translations.
