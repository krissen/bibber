# bibber and similar tools

How bibber relates to other tools that render references from BibTeX or
biblatex files. It rests on a run made on 2026-11-12 and on the projects'
own documentation as read on that date. Treat it as a snapshot: the other
tools change, and a claim here may go stale.

## In short

No tool we found does all of what bibber does. pandoc and Typst render APA 7
from the same `.bib` files and handle the ordinary entry types well. In our
run neither one produced the Swedish statute or doctoral-thesis forms or
printed translated titles. Of the pickers, fzf-bibtex documents output of keys
and its own pretty-printer, not APA. We did not check whether other pickers can
render APA text through CSL.

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
template in Lund University Library's APA 7 guide to Swedish statutes,
`SFS YYYY:Number. Title. URL`, and adds the amendment in brackets when the entry
has a `version` field. The amendment note is bibber's own addition. According
to the guide, the APA 7 manual has no instructions for official publications
from outside the US.

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
- **Chapter with `crossref`.** pandoc and bibber agree except for the DOI:
  pandoc gives the chapter the book's DOI, and bibber does not inherit it.
  (The book's DOI in our test data was itself malformed, `doi/10.2870/…`.)
  Typst printed the book title twice.
- **Order.** pandoc and Typst sort the list. bibber prints the entries in the
  order you ask for them.

## Other tools, from their documentation

| Tool | What it is | Renders APA text? |
|---|---|---|
| biber + biblatex-apa | The LaTeX APA style. It includes Swedish strings (`swedish-apa.lbx`) and is the model bibber follows for descriptions in brackets. | In LaTeX documents only |
| citeproc-js, citeproc-py, Citation.js | CSL processors that can use styles such as `apa.csl`; citeproc-js also supports CSL-M | Yes, with CSL; output not tested by us |
| Hayagriva | Typst's bibliography library and format | Yes (see Typst above) |
| fzf-bibtex | Picker: searches a `.bib` and outputs keys or its own pretty-printed text | Not according to its documentation |
| citar, telescope-bibtex | Pickers for Emacs and Neovim; citar works with org-cite | Not checked |
| betterbib | Cleans and enriches `.bib` files | Not according to its documentation; it complements bibber |
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
- `title_translation_<lang>` follows the field syntax of biblatex's
  multiscript version, biblatex-ms (its manual, version 4.0, has
  `TITLE_translation_fr = {Titre}` in the `.bib` example). A library without
  the field gets no translations.
- bibber prints what the data says. A `@thesis` without `type` gets the
  generic label (*Examensarbete*, *Thesis*), and `note` is printed as a
  separate bracket.
