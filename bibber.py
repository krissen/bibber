#!/Users/krisniem/.local/share/miniforge3/envs/default/bin/python
# coding=utf-8
import argparse
import collections
import collections.abc
import hashlib
import json
import os
import sys

import bibtexparser
from fuzzywuzzy import fuzz
from pylatexenc.latex2text import LatexNodes2Text

# Lazy imports för interaktivt läge (prompt_toolkit är tungt)
_interactive_imports_done = False


def _ensure_interactive_imports():
    """Importerar tunga bibliotek för interaktivt läge vid behov."""
    global _interactive_imports_done
    if _interactive_imports_done:
        return

    global pyperclip, PromptSession, Application, get_app
    global StyleAndTextTuples, FileHistory, KeyBindings, Layout
    global Float, FloatContainer, Window, FormattedTextControl
    global ScrollbarMargin, Dialog, Frame, TextArea

    import pyperclip as _pyperclip
    pyperclip = _pyperclip

    from prompt_toolkit import PromptSession as _PromptSession
    from prompt_toolkit.application import Application as _Application
    from prompt_toolkit.application.current import get_app as _get_app
    from prompt_toolkit.formatted_text import StyleAndTextTuples as _StyleAndTextTuples
    from prompt_toolkit.history import FileHistory as _FileHistory
    from prompt_toolkit.key_binding import KeyBindings as _KeyBindings
    from prompt_toolkit.layout import Layout as _Layout
    from prompt_toolkit.layout.containers import Float as _Float, FloatContainer as _FloatContainer, Window as _Window
    from prompt_toolkit.layout.controls import FormattedTextControl as _FormattedTextControl
    from prompt_toolkit.layout.margins import ScrollbarMargin as _ScrollbarMargin
    from prompt_toolkit.widgets import Dialog as _Dialog, Frame as _Frame, TextArea as _TextArea

    PromptSession = _PromptSession
    Application = _Application
    get_app = _get_app
    StyleAndTextTuples = _StyleAndTextTuples
    FileHistory = _FileHistory
    KeyBindings = _KeyBindings
    Layout = _Layout
    Float = _Float
    FloatContainer = _FloatContainer
    Window = _Window
    FormattedTextControl = _FormattedTextControl
    ScrollbarMargin = _ScrollbarMargin
    Dialog = _Dialog
    Frame = _Frame
    TextArea = _TextArea

    _interactive_imports_done = True


def resolve_crossrefs_v2(library):
    """Resolver crossref-fält för bibtexparser v2."""
    entries_by_key = {e.key: e for e in library.entries}

    for entry in library.entries:
        crossref_field = entry.fields_dict.get("crossref")
        if crossref_field:
            ref_key = crossref_field.value.strip("{}")
            ref_entry = entries_by_key.get(ref_key)
            if ref_entry:
                for field_key, field in ref_entry.fields_dict.items():
                    if field_key not in entry.fields_dict and field_key != "crossref":
                        entry.set_field(bibtexparser.model.Field(
                            key=field_key, value=field.value
                        ))
    return library


def library_to_dict(library):
    """Konverterar bibtexparser Library till dict-format."""
    result = {}
    for entry in library.entries:
        entry_dict = {"entrytype": entry.entry_type}
        for field_key, field in entry.fields_dict.items():
            entry_dict[field_key] = field.value
        result[entry.key] = entry_dict  # Original case!
    return result


# -------------------------------------------------
# Globala
# -------------------------------------------------
collections.Iterable = collections.abc.Iterable

CACHE_DIR = os.path.expanduser("~/.cache/bibber/")
os.makedirs(CACHE_DIR, exist_ok=True)

HISTORY_FILE = os.path.join(CACHE_DIR, "history.txt")

DEBUG_MODE = False
VERBOSE_MODE = False

bib_data = None
processed_entries_cache = None
last_shown_results = []
original_results = []  # Håller ursprungliga resultat innan filtrering
text_area = None



LANGUAGE = "en"
COMPACT_MAX_CHARS = 95  # hård max-längd i kompakt vy
CACHE_VERSION = "3"  # Bump vid ändringar i cache-format (3: sökindex)

# -------------------------------------------------
# Argument-parsning
# -------------------------------------------------
def parse_args():
    """Parsar kommandoradsargument med argparse."""
    parser = argparse.ArgumentParser(
        description="Bibber - BibTeX-sökverktyg",
        epilog="""
Interaktiva kommandon:
  ladda <fil>      : Ladda .bib
  sök <termer>     : Standardsökning
  sc <termer> [n]  : Kompakt sökning
  kopiera <index>  : Kopiera referens
  lang <sv|en>     : Byt språk
  hjälp            : Hjälptext
  avsluta          : Avsluta
""",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("query", nargs="*", help="Söktermer")
    parser.add_argument("-f", "--format", choices=["apa", "bib"], default="apa",
                        help="Outputformat (default: apa)")
    parser.add_argument("-k", "--key", help="Hämta specifik citation key direkt")
    parser.add_argument("-1", "--one", action="store_true",
                        help="Icke-interaktivt: ge första träffen och avsluta (genväg för -n1)")
    parser.add_argument("-n", "--num", type=int, metavar="N",
                        help="Icke-interaktivt: visa N bästa träffar och avsluta")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="Visa extra information (t.ex. 'Laddar fil...')")
    parser.add_argument("-d", "--debug", action="store_true",
                        help="Debug-läge")
    parser.add_argument("-b", "--bibfile", help=".bib-fil att ladda")
    return parser.parse_args()

# -------------------------------------------------
# 1) Fil & hjälp
# -------------------------------------------------
def save_last_used_file(file_path):
    last_used = os.path.join(CACHE_DIR, "last_used_bibfile.json")
    with open(last_used, "w") as f:
        json.dump({"last_used": file_path}, f)

def get_last_used_file():
    last_used = os.path.join(CACHE_DIR, "last_used_bibfile.json")
    if os.path.exists(last_used):
        try:
            with open(last_used, "r") as f:
                data=json.load(f)
                return data.get("last_used")
        except (json.JSONDecodeError, IOError):
            pass
    return None

def md5sum(file_path):
    if not os.path.isfile(file_path):
        raise FileNotFoundError(f"Filen finns inte: {file_path}")
    with open(file_path,"rb") as fp:
        return hashlib.md5(fp.read()).hexdigest()

def load_from_cache(cache_file):
    """Laddar cache och returnerar (entries, search_index) eller (None, None)."""
    try:
        with open(cache_file, "r") as f:
            cached = json.load(f)
            if isinstance(cached, dict) and cached.get("version") == CACHE_VERSION:
                return cached["entries"], cached.get("search_index")
            return None, None  # Gammal cache-version
    except (json.JSONDecodeError, IOError):
        return None, None


def save_to_cache(data, cache_file, search_index=None):
    """Sparar bib-data och valfritt sökindex till cache."""
    cache_obj = {"version": CACHE_VERSION, "entries": data}
    if search_index is not None:
        cache_obj["search_index"] = search_index
    with open(cache_file, "w") as f:
        json.dump(cache_obj, f)

# Global instans för LaTeX-konvertering (undvik att skapa ny varje gång)
_latex_converter = LatexNodes2Text()


def safe_latex_to_text(x):
    try:
        return _latex_converter.latex_to_text(x or "")
    except Exception:
        return x or ""

def copy_to_clipboard(txt):
    _ensure_interactive_imports()
    try:
        pyperclip.copy(txt)
    except Exception:
        pass

def debug_log(message):
      if DEBUG_MODE:
            print(f"[DEBUG] {message}")

# -------------------------------------------------
# 2) Språk
# -------------------------------------------------
def load_language_setting():
    global LANGUAGE
    fn= os.path.join(CACHE_DIR,"lang.json")
    if os.path.exists(fn):
        try:
            with open(fn,"r") as f:
                data=json.load(f)
                if "language" in data:
                    LANGUAGE=data["language"]
        except (json.JSONDecodeError, IOError):
            pass

def save_language_setting(lang):
    global LANGUAGE
    LANGUAGE= lang.lower()
    fn= os.path.join(CACHE_DIR,"lang.json")
    with open(fn,"w") as f:
        json.dump({"language":LANGUAGE}, f)

# -------------------------------------------------
# 3) BibTeX-laddning
# -------------------------------------------------
def _build_search_index(entries):
    """Bygger sökindex med normaliserad text (hanterar LaTeX/umlauts)."""
    search_index = []
    for i, e in enumerate(entries.values()):
        t = safe_latex_to_text(e.get("title", ""))
        a = safe_latex_to_text(e.get("author", e.get("editor", "Unknown")))
        j = safe_latex_to_text(e.get("journaltitle", e.get("journal", e.get("booktitle", ""))))
        combined = f"{t} {a} {j}".lower()
        search_index.append(combined)
    return search_index


def load_bibtex(file_path, verbose=None):
    """
    Laddar BibTeX-fil.

    Args:
        file_path: Sökväg till .bib-fil
        verbose: Om True, visa laddningsmeddelanden. Om None, använd VERBOSE_MODE.
    """
    global bib_data, processed_entries_cache
    if verbose is None:
        verbose = VERBOSE_MODE

    file_path = os.path.expanduser(file_path)
    cfile = os.path.join(CACHE_DIR, md5sum(file_path) + ".json")

    cached_entries, cached_index = load_from_cache(cfile)
    if cached_entries:
        if DEBUG_MODE:
            print(f"[DEBUG] Loading from cache: {cfile}")
        bib_data = cached_entries
        # Återställ sökindex från cache
        if cached_index:
            processed_entries_cache = [(i, s) for i, s in enumerate(cached_index)]
        else:
            processed_entries_cache = None
        if verbose:
            if LANGUAGE == "sv":
                print(f"Laddar senast använda fil: {file_path}", file=sys.stderr)
            else:
                print(f"Loading last used file: {file_path}", file=sys.stderr)
        save_last_used_file(file_path)
    else:
        try:
            if verbose:
                if LANGUAGE == "sv":
                    print(f"Laddar fil: {file_path}", file=sys.stderr)
                else:
                    print(f"Loading file: {file_path}", file=sys.stderr)

            library = bibtexparser.parse_file(file_path)
            library = resolve_crossrefs_v2(library)
            bib_data = library_to_dict(library)

            # Logga eventuella parsningsfel
            if library.failed_blocks:
                for block in library.failed_blocks:
                    print(f"Varning: Parsningsfel", file=sys.stderr)

            # Bygg och cacha sökindex
            search_index = _build_search_index(bib_data)
            processed_entries_cache = [(i, s) for i, s in enumerate(search_index)]

            save_to_cache(bib_data, cfile, search_index)
            save_last_used_file(file_path)
        except Exception as e:
            print(f"Error loading bib: {e}", file=sys.stderr)
            return

# -------------------------------------------------
# 4) En förenklad APA, tar hänsyn till LANGUAGE
# -------------------------------------------------
def build_editors_string(raw_editor_string, language="en"):
    """
    Tar en 'raw_editor_string' (ofta något i stil med 'Last, First and Doe, John ...')
    och returnerar en sträng i APA-lik form:
    
      "Last, F. & Doe, J. (Eds.)"   (om engelska och flera editorer)
      "Last, F. (Ed.)"             (om engelska och en editor)
    
    eller om LANGUAGE="sv":
      "Last, F. & Doe, J. (red.)"  (vanligast på svenska)
    
    Hanterar även fler än 20 redaktörer enligt APA7 (för referenslistor):
      - De första 19 namnen
      - "..."
      - Sista namnet
    """
    if not raw_editor_string:
        return "Unknown Editor"

    # Splitta på ' and ' enligt BibTeX-konvention
    splitted_editors = raw_editor_string.split(" and ")

    # Hjälpfunktion för att parsa "Efternamn, Förnamn" => "Efternamn, F."
    def parse_one(raw_name):
        name_clean = safe_latex_to_text(raw_name.strip())
        parts = name_clean.split(",")
        if len(parts) == 2:
            ln = parts[0].strip()
            fn_parts = parts[1].split()
            initials = [f"{p[0].upper()}." for p in fn_parts if p]
            init_str = " ".join(initials)
            if init_str:
                return f"{ln}, {init_str}"
            else:
                return ln
        else:
            # fallback om formateringen inte är "Efternamn, Förnamn"
            return name_clean

    # Bygg en lista av parsade redaktörer
    editors_parsed = [parse_one(ed) for ed in splitted_editors if ed.strip()]

    # APA7: Om fler än 20 => visa de första 19, sedan '...', sedan sista
    if len(editors_parsed) > 20:
        editors_parsed = editors_parsed[:19] + ["..."] + [editors_parsed[-1]]

    # Sätt samman till en kommaseparerad sträng,
    # men ersätt sista kommatecknet med "&" (en enkel variant).
    if len(editors_parsed) > 1:
        *all_but_last, last = editors_parsed
        editors_str = ", ".join(all_but_last) + " & " + last
    else:
        editors_str = editors_parsed[0] if editors_parsed else "Unknown"

    # Lägg till "(Ed.)"/"(Eds.)" eller "(red.)" beroende på språk + antal
    if language.lower() == "en":
        if len(splitted_editors) == 1:
            editors_str += " (Ed.)"
        else:
            editors_str += " (Eds.)"
    else:
        # På svenska kan man välja "(red.)" både för singular och plural
        editors_str += " (red.)"

    return editors_str


def build_editors_string_given_first(raw_editor_string, language="en"):
    """
    APA 7 incollection-format: redaktörer skrivs förnamn-först.
      "F. Last & J. Doe (Eds.)"   (engelska, flera)
      "F. Last (Ed.)"             (engelska, en)
      "F. Last & J. Doe (red.)"   (svenska)
    """
    if not raw_editor_string:
        return "Unknown Editor"

    splitted_editors = raw_editor_string.split(" and ")

    def parse_one_given_first(raw_name):
        name_clean = safe_latex_to_text(raw_name.strip())
        parts = name_clean.split(",")
        if len(parts) == 2:
            ln = parts[0].strip()
            fn_parts = parts[1].split()
            initials = [f"{p[0].upper()}." for p in fn_parts if p]
            init_str = " ".join(initials)
            if init_str:
                return f"{init_str} {ln}"
            else:
                return ln
        else:
            return name_clean

    editors_parsed = [parse_one_given_first(ed) for ed in splitted_editors if ed.strip()]

    if len(editors_parsed) > 20:
        editors_parsed = editors_parsed[:19] + ["..."] + [editors_parsed[-1]]

    if len(editors_parsed) > 1:
        *all_but_last, last = editors_parsed
        editors_str = ", ".join(all_but_last) + " & " + last
    else:
        editors_str = editors_parsed[0] if editors_parsed else "Unknown"

    if language.lower() == "en":
        if len(splitted_editors) == 1:
            editors_str += " (Ed.)"
        else:
            editors_str += " (Eds.)"
    else:
        editors_str += " (red.)"

    return editors_str


def generate_apa(entry):
    """
    APA 7-formatering.
      - Flera författare eller redaktörer (upp till 20 innan '...').
      - @book där 'editor' används om 'author' saknas.
      - Svenska/engelska skillnader i u.å. / n.d., (red.) / (Ed.), etc.
      - Tidskriftsartiklar: *Tidskrift*, *volym*(nummer), sidor.
      - Avhandlingar: *Titel* [Doktorsavhandling, Lärosäte].
      - Incollection: redaktörer i förnamnsordning (F. Efternamn).
      - För @misc: visar DOI om det finns, annars URL, samt note/annotate sist inom hakparentes.
    """
    if DEBUG_MODE:
        for key, val in entry.items():
            print(f"[DEBUG] {key} : {val}")

    if LANGUAGE == "sv":
        no_date       = "u.å."
        single_ed     = " (red.)"
        plural_ed     = " (red.)"
        pages_label   = "ss."
        in_b          = "I"
    else:
        no_date       = "n.d."
        single_ed     = " (Ed.)"
        plural_ed     = " (Eds.)"
        pages_label   = "pp."
        in_b          = "In"

    # 1) Hämta antingen 'author' eller 'editor' om 'author' saknas
    raw_author = entry.get("author", "") or entry.get("editor", "")
    if DEBUG_MODE:
        print(f"[DEBUG] raw_author={raw_author}")
    is_editor = False
    if raw_author and not entry.get("author", "") and entry.get("editor", ""):
        is_editor = True
    if not raw_author:
        raw_author = "Unknown"

    # 2) Författar-/redaktörslistan
    auth_ltx = safe_latex_to_text(raw_author)
    splitted = [a.strip() for a in auth_ltx.split(" and ")]
    authors = []
    for a in splitted:
        parts = a.split(",")
        if len(parts) == 2:
            ln = parts[0].strip()
            fn_parts = parts[1].split()
            initials = []
            for ffn in fn_parts:
                if ffn:
                    initials.append(ffn[0].upper() + ".")
            init_str = " ".join(initials)
            if init_str:
                authors.append(f"{ln}, {init_str}")
            else:
                authors.append(ln)
        else:
            authors.append(a.strip())
    if len(authors) > 20:
        first_19 = authors[:19]
        last_one = authors[-1]
        authors = first_19 + ["..."] + [last_one]
    if is_editor:
        if len(splitted) == 1:
            authors[-1] += single_ed
        else:
            authors[-1] += plural_ed
    if len(authors) > 1:
        authors_str = ", ".join(authors[:-1]) + " & " + authors[-1]
    else:
        authors_str = authors[0]

    # 3) År
    yr = entry.get("year", "")
    if not yr:
        dt = entry.get("date", "")
        if dt:
            yr = dt[:4]
    if not yr:
        yr = no_date

    # 4) Titel – artikeltitel, boktitel, etc.
    title_raw = entry.get("title", "Untitled")
    title = safe_latex_to_text(title_raw).strip()
    if title:
        title = title[0].upper() + title[1:]
    else:
        title = "Untitled"

    # 5) Sidor (raw utan prefix — prefix läggs till per entrytype)
    pp_raw = entry.get("pages", "").replace("--", "–").strip()

    # 6) DOI/URL
    doi = entry.get("doi", "")
    url = entry.get("url", "")
    if doi:
        if not doi.startswith("https://doi.org/"):
            doi = "https://doi.org/" + doi
        link = doi
    elif url:
        link = url
    else:
        link = ""

    # 7) Plats / förlag
    loc = safe_latex_to_text(entry.get("location", "")).strip()
    pub = safe_latex_to_text(entry.get("publisher", "")).strip()

    # 8) Entrytype
    et = entry.get("entrytype", "").lower()

    apa = f"{authors_str} ({yr}). "

    # 9) Upplaga
    edition_raw = safe_latex_to_text(entry.get("edition", "")).strip()
    if edition_raw:
        if LANGUAGE == "sv":
            edition_str = f"({edition_raw} uppl.)"
        else:
            edition_str = f"({edition_raw} ed.)"
    else:
        edition_str = ""

    # 10) Hämtningsdatum för webresurser
    urldate = entry.get("urldate", "").strip()

    # ========================
    # Speciell hantering för thesis/avhandling/examensarbete
    # ========================
    thesis_types = ("phdthesis", "mastersthesis", "thesis")
    if et in thesis_types or (et == "misc" and (entry.get("institution") or entry.get("school")) and not entry.get("journal") and not entry.get("journaltitle")):
        # Bygg ordning institution, school, publisher, endast unika värden
        inst = safe_latex_to_text(entry.get("institution", "")).strip()
        school = safe_latex_to_text(entry.get("school", "")).strip()
        pub_t = safe_latex_to_text(entry.get("publisher", "")).strip()
        org_fields = [inst, school, pub_t]
        seen = set()
        orgs = []
        for val in org_fields:
            if val and val not in seen:
                orgs.append(val)
                seen.add(val)
        # Bestäm typ av arbete (språkanpassat)
        if et == "phdthesis":
            thesis_label = "Doktorsavhandling" if LANGUAGE == "sv" else "Doctoral dissertation"
        elif et == "mastersthesis":
            thesis_label = "Examensarbete" if LANGUAGE == "sv" else "Master's thesis"
        else:
            thesis_label = entry.get("type", "").strip()

        if thesis_label and orgs:
            apa += f"*{title}* [{thesis_label}, {', '.join(orgs)}]."
        elif thesis_label:
            apa += f"*{title}* [{thesis_label}]."
        elif orgs:
            apa += f"*{title}*. {', '.join(orgs)}."
        else:
            apa += f"*{title}*."
        # Lägg till eventuell note/annotate
        note = entry.get("note") or entry.get("annotate")
        if note:
            apa += f" [{safe_latex_to_text(note).strip()}]"
        # Länk sist om finns
        if link:
            apa += f" {link}"
        apa = " ".join(apa.split())
        return apa

    # ============ Resten av typerna ============
    if et == "incollection":
        # Kapitel i redigerad bok – APA 7: redaktörer i förnamnsordning
        chapter_title = title
        raw_ed = entry.get("editor", "")
        bk = safe_latex_to_text(entry.get("booktitle", "")).strip()
        apa += f"{chapter_title}. "
        if bk:
            if raw_ed and raw_ed != raw_author:
                editors_str = build_editors_string_given_first(raw_ed, LANGUAGE)
                apa += f"{in_b} {editors_str}, *{bk}*"
            else:
                apa += f"{in_b} *{bk}*"
            if edition_str:
                apa += f" {edition_str}"
            if pp_raw:
                apa += f" ({pages_label} {pp_raw})"
            apa += "."
        # OBS: Ort utelämnas i strikt APA 7, men vi inkluderar den medvetet.
        if loc and pub:
            apa += f" {loc}: {pub}."
        elif pub:
            apa += f" {pub}."
    elif et == "article":
        # APA 7: Titel. *Tidskrift*, *volym*(nummer), sidor.
        apa += f"{title}. "
        j = safe_latex_to_text(entry.get("journaltitle", entry.get("journal", ""))).strip()
        vol = entry.get("volume", "").strip()
        num = entry.get("number", "").strip()
        if j:
            apa += f"*{j}*"
            if vol:
                apa += f", *{vol}*"
            if num:
                apa += f"({num})"
            if pp_raw:
                apa += f", {pp_raw}"
            apa += "."
        elif pp_raw:
            apa += f"{pp_raw}."
    elif et == "book":
        apa += f"*{title}*"
        if edition_str:
            apa += f" {edition_str}"
        apa += "."
        # OBS: Ort utelämnas i strikt APA 7, men vi inkluderar den medvetet.
        if loc and pub:
            apa += f" {loc}: {pub}."
        elif pub:
            apa += f" {pub}."
    elif et == "inproceedings":
        bk = safe_latex_to_text(entry.get("booktitle", "")).strip()
        howp = safe_latex_to_text(entry.get("howpublished", "")).strip()
        apa += f"{title}."
        if bk:
            apa += f" {in_b} *{bk}*"
            if pp_raw:
                apa += f" ({pages_label} {pp_raw})"
            apa += "."
        if howp:
            apa += f" {howp}."
        # OBS: Ort utelämnas i strikt APA 7, men vi inkluderar den medvetet.
        if loc and pub:
            apa += f" {loc}: {pub}."
        elif pub:
            apa += f" {pub}."
    elif et == "misc":
        apa += f"*{title}*."
        inst = safe_latex_to_text(entry.get("institution", entry.get("organization", ""))).strip()
        series = safe_latex_to_text(entry.get("series", "")).strip()
        if inst:
            apa += f" {inst}."
        if series:
            apa += f" {series}."
        # OBS: Ort utelämnas i strikt APA 7, men vi inkluderar den medvetet.
        if loc and pub:
            apa += f" {loc}: {pub}."
        elif pub:
            apa += f" {pub}."
        if pp_raw:
            apa += f" {pages_label} {pp_raw}."
    else:
        apa += f"{title}."
        # OBS: Ort utelämnas i strikt APA 7, men vi inkluderar den medvetet.
        if loc and pub:
            apa += f" {loc}: {pub}."
        elif pub:
            apa += f" {pub}."
        if pp_raw:
            apa += f" {pages_label} {pp_raw}."

    # Länk och note sist (gemensamt för alla icke-thesis-typer)
    if link:
        apa += f" {link}"
    elif urldate and url:
        # Webresurs utan DOI — visa hämtningsdatum
        if LANGUAGE == "sv":
            apa += f" Hämtad {urldate} från {url}"
        else:
            apa += f" Retrieved {urldate}, from {url}"
    note = entry.get("note") or entry.get("annotate")
    if note:
        apa += f" [{safe_latex_to_text(note).strip()}]"

    apa = " ".join(apa.split())
    return apa


def generate_bib_entry(key, entry):
    """
    Genererar BibTeX-entry som sträng.

    Args:
        key: Citation key (t.ex. 'niemi2024')
        entry: Dict med BibTeX-fält

    Returns:
        BibTeX-formaterad sträng
    """
    entrytype = entry.get('entrytype', 'misc')
    lines = [f"@{entrytype}{{{key},"]

    # Ordning på fält som är vanlig i BibTeX
    field_order = ['author', 'editor', 'title', 'booktitle', 'journal', 'journaltitle',
                   'year', 'date', 'volume', 'number', 'pages', 'publisher', 'location',
                   'address', 'institution', 'school', 'doi', 'url', 'note', 'annotate']

    # Lägg först till fält i preferred order
    added_fields = set()
    for field in field_order:
        if field in entry and field != 'entrytype':
            value = entry[field]
            if value:
                lines.append(f"  {field} = {{{value}}},")
                added_fields.add(field)

    # Lägg till övriga fält
    for field, value in entry.items():
        if field != 'entrytype' and field not in added_fields and value:
            lines.append(f"  {field} = {{{value}}},")

    lines.append("}")
    return "\n".join(lines)


def get_output(key, entry, output_format):
    """
    Returnerar referens i önskat format.

    Args:
        key: Citation key
        entry: BibTeX-entry dict
        output_format: 'apa' eller 'bib'

    Returns:
        Formaterad sträng
    """
    if output_format == "bib":
        return generate_bib_entry(key, entry)
    else:
        return generate_apa(entry)


def get_reference_by_key(citation_key, output_format="apa"):
    """
    Hämtar referens baserat på citation key.

    Args:
        citation_key: Citation key att leta efter (case-insensitive)
        output_format: 'apa' eller 'bib'

    Returns:
        Formaterad referens eller None om ej funnen
    """
    if not bib_data:
        return None

    # Sök case-insensitive
    key_lower = citation_key.lower()
    for key, entry in bib_data.items():
        if key.lower() == key_lower:
            return get_output(key, entry, output_format)

    return None


def get_first_search_result(query_terms, output_format="apa"):
    """
    Kör sökning och returnerar första träffen.
    Wrapper för bakåtkompatibilitet.
    """
    return get_top_search_results(query_terms, output_format, limit=1)


def get_top_search_results(query_terms, output_format="apa", limit=1):
    """
    Kör sökning och returnerar de N bästa träffarna.

    Args:
        query_terms: Lista med söktermer
        output_format: 'apa' eller 'bib'
        limit: Antal träffar att returnera

    Returns:
        Formaterad referens(er) eller None om inga träffar
    """
    if not bib_data:
        return None

    if not query_terms:
        return None

    qterms = [x.lower() for x in query_terms]
    scored = _search_and_score_entries(qterms, limit=limit)

    if not scored:
        return None

    keys = list(bib_data.keys())
    lines = []
    for item in scored:
        key = keys[item["idx"]]
        entry = bib_data[key]
        lines.append(get_output(key, entry, output_format))

    return "\n".join(lines)


# -------------------------------------------------
# 5) Standard-lång vy
# -------------------------------------------------
def build_standard_reference_short(entry):
    authors= parse_authors_for_compact(entry,semicolon=False)
    y= parse_year_4chars(entry)
    if y=="????":
        y= "u.å." if LANGUAGE == "sv" else "n.d."

    t= safe_latex_to_text(entry.get("title","Untitled")).strip()
    if t: t= t[0].upper()+ t[1:]
    else: t="Untitled"

    et= entry.get("entrytype","").lower()
    if et=="article":
        source= safe_latex_to_text(entry.get("journaltitle", entry.get("journal",""))).strip()
    elif et=="incollection":
        source= safe_latex_to_text(entry.get("booktitle","")).strip()
    elif et=="book":
        source=""
    elif et in ("phdthesis", "mastersthesis", "thesis"):
        inst = safe_latex_to_text(entry.get("institution", "") or entry.get("school", "") or entry.get("publisher", "")).strip()
        if et == "phdthesis":
            label = "Avh." if LANGUAGE == "sv" else "PhD Thesis"
        elif et == "mastersthesis":
            label = "Examensarb." if LANGUAGE == "sv" else "Master's Thesis"
        else:
            label = entry.get("type", "Thesis").strip()
        source = f"{label}, {inst}" if inst else label
    else:
        source= safe_latex_to_text(entry.get("journal", entry.get("booktitle",""))).strip()

    line= f"{authors} ({y}). {t}"
    if source:
        line+= f". {source}"
    return line

def search_entries(query):
    global last_shown_results, results
    if not bib_data:
        print("Ingen fil är laddad.")
        return

    qterms = [x.lower() for x in query.split() if x.lower() != "--debug"]

    # Steg 1: Poängsätt alla (snabbt, ingen formatering)
    scored_raw = _score_entries(qterms)

    # Steg 2: Räkna perfekta träffar
    num_perfects = sum(1 for idx, score in scored_raw if score >= 100)

    if num_perfects > 5:
        if LANGUAGE == "sv":
            print(f"\nFler än 5 perfekta träffar ({num_perfects}). Kompakt vy...\n")
        else:
            print(f"\nMore than 5 perfect matches ({num_perfects}). Switching to compact view...\n")
        # Formatera för kompakt vy (behöver fler resultat)
        scored = _format_scored_entries(scored_raw, limit=50)
        results = scored
        interactive_result_view_compact(scored, qterms)
        return

    # Steg 3: Formatera bara top 5 för standardvy
    scored = _format_scored_entries(scored_raw, limit=5)
    results = scored
    last_shown_results = scored
    if LANGUAGE=="sv":
        print("\nSökresultat (standardvy, max 5):\n")
    else:
        print("\nSearch results (standard view, max 5):\n")

    keys = list(bib_data.keys())
    for i, item in enumerate(last_shown_results):
        key = keys[item["idx"]]
        e = bib_data[key]
        ref_s= build_standard_reference_short(e)
        print(f"[{i+1}] {ref_s}")
        print(f"    Score: {item['score']:.1f}%\n")

# -------------------------------------------------
# 6) Kompakt vy
# -------------------------------------------------
def parse_authors_for_compact(entry,semicolon=True):
    raw= entry.get("author","") or entry.get("editor","")
    r= safe_latex_to_text(raw)
    splitted= r.split(" and ")
    out=[]
    for a in splitted:
        parts= a.split(",")
        if len(parts)==2:
            ln= parts[0].strip()
            fn= parts[1].split()
            if fn and fn[0]:
                init= fn[0][0].upper()
                out.append(f"{ln} {init}")
            else:
                out.append(ln)
        else:
            out.append(a.strip())

    if semicolon:
        return "; ".join(out)
    else:
        return ", ".join(out)

def parse_year_4chars(entry):
    y= entry.get("year","")
    if not y:
        d= entry.get("date","")
        if len(d)>=4:
            y=d[:4]
    y= safe_latex_to_text(y).strip()
    if not y:
        y="????"
    return y[:4]

def _prepare_processed_entries():
    """Förbereder sökindex om det inte redan finns i cache."""
    global processed_entries_cache
    if processed_entries_cache is not None:
        return
    # Bygg index on-the-fly (sker bara om cache saknas)
    search_index = _build_search_index(bib_data)
    processed_entries_cache = [(i, s) for i, s in enumerate(search_index)]

def _try_int_year(s):
    """
    Försök tolka 's' som int.
    Om det ej går (ex. '????', 'fort', ''), 
    returnera -999999 (en väldigt låg siffra),
    så hamnar icke-numeriska sist i en fallande sortering.
    """
    try:
        return int(s)
    except ValueError:
        return -999999


def _score_entries(qterms):
    """
    Poängsätter entries utan formatering (snabbt).

    Returns:
        Lista av (idx, score) tupler, sorterade fallande på poäng.
    """
    if not qterms:
        return []
    _prepare_processed_entries()
    arr = list(bib_data.values())

    scored = []
    for (idx, combined_lower) in processed_entries_cache:
        ex = 0
        fuzzies = []
        for term in qterms:
            if term.isdigit():
                y = arr[idx].get("year", "")
                if term == y:
                    ex += 1
                else:
                    fz = fuzz.partial_ratio(term, y) / 100
                    fuzzies.append(fz)
            else:
                if term in combined_lower:
                    ex += 1
                else:
                    fz = fuzz.partial_ratio(term, combined_lower) / 100
                    fuzzies.append(fz)
        e_score = (ex / len(qterms)) * 100
        f_score = (sum(fuzzies) / len(qterms)) * 100 if fuzzies else 0
        total = e_score + f_score
        scored.append((idx, total))

    # Sortera på poäng + år
    scored.sort(key=lambda x: (x[1], _try_int_year(arr[x[0]].get("year", ""))), reverse=True)
    return scored


def _format_scored_entries(scored, limit=None):
    """
    Formaterar poängsatta entries för visning.

    Args:
        scored: Lista av (idx, score) tupler
        limit: Max antal att formatera (None = alla)
    """
    arr = list(bib_data.values())
    if limit is not None:
        scored = scored[:limit]

    out = []
    for idx, total in scored:
        authors_s = parse_authors_for_compact(arr[idx], semicolon=True)
        y_s = parse_year_4chars(arr[idx])
        ti = safe_latex_to_text(arr[idx].get("title", "Untitled")).strip()
        out.append({
            "idx": idx,
            "score": total,
            "authors": authors_s,
            "year": y_s,
            "title": ti
        })
    return out


def _search_and_score_entries(qterms, limit=None):
    """
    Söker, poängsätter och formaterar entries.
    Wrapper för bakåtkompatibilitet.
    """
    scored = _score_entries(qterms)
    return _format_scored_entries(scored, limit)

# *** Här är de nya trunkeringsfunktionerna *** #

def truncate_in_middle_bigstring(line, qterms, max_len):
    """
    EN trunkering för hela kompakt-raden. 
    Bevarar "söktermer" i mitten. 
    Sätter "..." i mitten om för lång.
    """
    orig_len= len(line)
    if orig_len<= max_len:
        if DEBUG_MODE:
            print(f"Debug: no trunk needed => raw_line_len={orig_len} <= {max_len}")
        return line

    # Låt oss välja t.ex. keep_start=40, keep_end=40, men om max_len=95 => 40+40=80 => 
    # kvar 15 tecken för "..." i mitten. 
    # Om max_len <80 => justera.
    keep_start= min(40, max_len//2)
    keep_end=   min(40, max_len//2)

    if DEBUG_MODE:
        print(f"Debug: truncate_in_middle_bigstring => orig_len={orig_len}, max_len={max_len}, keep_start={keep_start}, keep_end={keep_end}")

    # leta söktermer
    positions=[]
    low_line= line.lower()
    for t in qterms:
        start=0
        while True:
            pos= low_line.find(t.lower(), start)
            if pos==-1:
                break
            endp= pos+ len(t)
            positions.append((pos,endp))
            start=endp

    if not positions:
        # ingen sökterm => klipp i mitten
        if max_len<(keep_start+keep_end):
            # klipp i slutet
            truncated= line[:max_len]
            if DEBUG_MODE:
                print(f"Debug: no search terms => direct cut => len={len(truncated)}")
            return truncated
        trunked= line[:keep_start] + "..." + line[-keep_end:]
        if len(trunked)> max_len:
            trunked= trunked[:max_len]
        if DEBUG_MODE:
            print(f"Debug: trunked-len={len(trunked)}")
        return trunked

    # vi har söktermer => bevara mitten
    minpos= min(x[0] for x in positions)
    maxpos= max(x[1] for x in positions)

    left_part= line[:keep_start]
    middle   = line[minpos:maxpos]
    right_part= line[-keep_end:]

    combined= left_part+ middle+ right_part
    if len(combined)<= max_len:
        if DEBUG_MODE:
            print(f"Debug: combined-len={len(combined)} => no further trunk.")
        return combined

    # sätt in "..."
    SEP="..."
    candidate= left_part+ SEP+ middle+ SEP+ right_part
    cand_len= len(candidate)
    if DEBUG_MODE:
        print(f"Debug: candidate-len={cand_len} vs max={max_len}")
    if cand_len<= max_len:
        return candidate

    # klipp mer i left_part / right_part
    over= cand_len- max_len
    half= over//2
    left_part= left_part[: max(0, len(left_part)-half)]
    rest= over- half
    if rest< len(right_part):
        right_part= right_part[rest:]
    else:
        right_part=""

    final= left_part+ SEP+ middle+ SEP+ right_part
    if len(final)> max_len:
        final= final[:max_len]
    if DEBUG_MODE:
        print(f"Debug: final-len={len(final)}. over={over}")
    return final


def trunk_in_middle(text, query_terms, max_len, keep_start=7, keep_end=7):
    """
    Trunkerar 'text' i *mitten* om den överskrider max_len.
    - Bevarar söktermer (om texten innehåller dem).
    - Sätter in "..." i mitten.
    - 'keep_start' tecken i början och 'keep_end' i slutet är minimimått 
      (men om söktermer ligger i de områdena kan det bli lite större).

    Returnerar en trunkerad sträng (eller originalsträngen om len <= max_len).
    """
    txt = text.strip()
    if len(txt) <= max_len:
        if DEBUG_MODE:
            print(f"Debug: trunk_in_middle => no trunk, len={len(txt)} <= {max_len}")
        return txt

    # Hitta positioner för söktermer
    positions = []
    lo_txt = txt.lower()
    for t in query_terms:
        start_i = 0
        t_low = t.lower()
        while True:
            pos = lo_txt.find(t_low, start_i)
            if pos == -1:
                break
            endp = pos + len(t_low)
            positions.append((pos, endp))
            start_i = endp

    if DEBUG_MODE:
        print(f"Debug: trunk_in_middle => len={len(txt)}, max_len={max_len}, #positions={len(positions)}")

    if not positions:
        # Ingen sökterm => enkel klipp
        if max_len < (keep_start + keep_end):
            return txt[:max_len]
        trunked = txt[:keep_start] + "..." + txt[-keep_end:]
        if len(trunked) > max_len:
            trunked = trunked[:max_len]
        return trunked

    # Finns söktermer => bevara området [minpos : maxpos]
    minpos = min(p[0] for p in positions)
    maxpos = max(p[1] for p in positions)

    left_part = txt[:keep_start]
    middle_part = txt[minpos:maxpos]
    right_part = txt[-keep_end:]
    combined = left_part + middle_part + right_part

    if len(combined) <= max_len:
        # Allt får plats
        return combined

    SEP = "..."
    candidate = left_part + SEP + middle_part + SEP + right_part
    if len(candidate) <= max_len:
        return candidate

    # Fortfarande för långt => klipp lite i left_part & right_part
    over = len(candidate) - max_len
    cut_half = over // 2
    left_part = left_part[: max(0, len(left_part) - cut_half)]
    rest = over - cut_half
    if rest < len(right_part):
        right_part = right_part[rest:]
    else:
        right_part = ""
    final = left_part + SEP + middle_part + SEP + right_part
    if len(final) > max_len:
        final = final[:max_len]
    return final



def build_compact_line(index, score, authors, year, title, query_terms, max_len=95):
    """
    Bygger en rad: "[i] score% | authors | year | title".
    Returnerar strängen om len <= max_len, annars anropar 'truncate_line_exact(...)'
    för att få EXAKT max_len tecken och bevara kolumner + söktermer i möjligaste mån.
    """
    prefix = f"[{index}] {score:.1f}%"
    raw_line = f"{prefix} | {authors} | {year} | {title}"

    if len(raw_line) <= max_len:
        # Ingen trunkering behövs
        return raw_line

    # Annars => trunkera i ETT pass => EXACT 'max_len'
    final_line = truncate_line_exact(raw_line, query_terms, max_len)
    return final_line


def truncate_line_exact(line, query_terms, max_len=95, keep_start=10, keep_end=10):
    """
    Försöker bygga en EXAKT max_len-teckens variant av 'line'.
    Metoden:
      1) Om len(line) <= max_len => return direkt.
      2) Skapa 'must_keep'-segment för:
         a) (0..keep_start)
         b) (len(line)-keep_end..len(line))
         c) Alla förekomster av kolumnseparatorn " | "
         d) Alla förekomster av söktermer (ex. "niemi")
      3) Slå ihop överlappande segment -> en 'merged' lista.
      4) Räkna summan av segmentlängder => keepLen
         - Om keepLen >= max_len => klipp i slutet => line[:max_len].
         - Annars => "fyll" text mellan segmenten i ordning tills du nått max_len.
      5) Om vi klipper bort något i mitten => sätt in "..." vid mittklippet
         (eller i slutet, beroende på val). 
      6) Se till att slutlängden blir EXACT max_len (pad med spaces eller klipp i slutet).
    """

    n = len(line)
    if n <= max_len:
        return line

    # 1) Skapa en "måste-ha"-lista
    #    => en samling (start, end) som vi inte vill klippa bort
    must_keep = []

    # a) Början
    must_keep.append((0, keep_start))
    # b) Slut
    must_keep.append((n - keep_end, n))

    # c) Söktermer
    lower_line = line.lower()
    for t in query_terms:
        t_low = t.lower()
        start_i = 0
        while True:
            pos = lower_line.find(t_low, start_i)
            if pos == -1:
                break
            endp = pos + len(t_low)
            must_keep.append((pos, endp))
            start_i = endp

    # d) Kolumnseparatorn " | "
    sep_str = " | "
    start_sep = 0
    while True:
        isep = line.find(sep_str, start_sep)
        if isep == -1:
            break
        must_keep.append((isep, isep + len(sep_str)))  # ex (pos, pos+3)
        start_sep = isep + len(sep_str)

    # Rensa felaktiga segment
    # ex. om keep_start > n
    new_keep = []
    for (s0, e0) in must_keep:
        if e0 > s0 and s0 < n:
            # Kapa segmentet inom [0..n]
            ns = max(0, s0)
            ne = min(n, e0)
            if ne > ns:
                new_keep.append((ns, ne))
    must_keep = new_keep

    # 2) Slå ihop överlapp
    must_keep.sort(key=lambda x: x[0])
    merged = []
    current = None
    for seg in must_keep:
        if current is None:
            current = seg
        else:
            if seg[0] <= current[1]:
                # överlapp => förena
                current = (current[0], max(current[1], seg[1]))
            else:
                merged.append(current)
                current = seg
    if current:
        merged.append(current)

    # 3) Summera "måste-ha"
    keep_len = sum(e0 - s0 for (s0, e0) in merged)

    if DEBUG_MODE:
        print(f"Debug: truncate_line_exact => raw_len={n}, max_len={max_len}, keepLen={keep_len}, segments={merged}")

    # 4) Om keepLen >= max_len => klipp i slutet => line[:max_len]
    if keep_len >= max_len:
        truncated = line[:max_len]
        # Du KAN här lägga in "..." i slutet om du vill markera avklipp
        return truncated

    # 5) Summan < max_len => vi försöker "foga in" text mellan segmenten
    #    i sekvens => Ofta får man "alla" must_keep + "en del" av mittentext
    out = []
    total_used = 0
    last_end = 0
    for (s0, e0) in merged:
        # Först "gap" [last_end..s0] om det ryms
        gap_len = s0 - last_end
        need = total_used + gap_len
        if need >= max_len:
            # => vi tar så mycket av gapen som får plats
            take = max_len - total_used
            out.append(line[last_end : last_end + take])
            total_used += take
            break
        else:
            # hela gap
            out.append(line[last_end : s0])
            total_used += gap_len

        # Sedan segmentet [s0..e0]
        seg_len = e0 - s0
        need2 = total_used + seg_len
        if need2 >= max_len:
            take = max_len - total_used
            out.append(line[s0 : s0 + take])
            total_used += take
            break
        else:
            out.append(line[s0 : e0])
            total_used += seg_len

        last_end = e0
        if total_used >= max_len:
            break

    final = "".join(out)
    if len(final) < n:
        # => vi har klippt bort något
        # Du kan välja att sätta "..." i mitten eller i slutet
        # i en minimal variant => if len(final)==max_len => ersätt sista 3 tecken med "..."
        if len(final) == max_len:
            final = final[:-3] + "..."
        else:
            # om final < max_len => fyll på med blanksteg?
            pass

    # Se till EXACT
    if len(final) > max_len:
        final = final[:max_len]
    elif len(final) < max_len:
        # fyll ut med blanksteg om du vill EXAKT 95
        final += " " * (max_len - len(final))

    return final

# -------------------------------------------------
# 7) Kompaktsök
# -------------------------------------------------
def search_entries_compact(query, max_results=10):
    global last_shown_results, original_results
    if not bib_data:
        print("Ingen fil är laddad.")
        return
    qterms = [x.lower() for x in query.split() if x.lower() != "--debug"]

    scored = _search_and_score_entries(qterms, limit=max_results)
    last_shown_results = scored
    original_results = scored  # Spara ursprungliga resultat


    if LANGUAGE=="sv":
        print(f"\nSökresultat (kompakt vy, {max_results} rader):\n")
    else:
        print(f"\nSearch results (compact view, {max_results} rader):\n")

    for i, s in enumerate(scored):
        line= build_compact_line(
            index= i+1,
            score= s["score"],
            authors= s["authors"],
            year= s["year"],
            title= s["title"],
            query_terms= qterms,
            max_len= COMPACT_MAX_CHARS
        )
        print(line)

# -------------------------------------------------
# 8) Interaktiv
# -------------------------------------------------
def build_compact_tokens(results, query_terms, selected_index):
    """
    Returnerar en lista av (style_str, text)-tupler.
    Varje 'rad' är "[i] score% | authors | year | title", 
    men om i == selected_index -> lägg till 'reverse' i stilen.
    """
    tokens: StyleAndTextTuples = []

    for i, r in enumerate(results):
        # Bygg själva radsträngen (samma som i build_compact_line)
        line = build_compact_line(
            index = i+1,
            score = r["score"],
            authors = r["authors"],
            year = r["year"],
            title = r["title"],
            query_terms = query_terms,
            max_len = COMPACT_MAX_CHARS
        )
        line += "\n"  # radbrytning

        # Om denna rad är 'vald' => style = "reverse"
        style_here = "reverse" if i == selected_index else ""

        # Dela upp radsträngen i ett enda token (eller om du vill finfördela).
        tokens.append( (style_here, line) )

    return tokens

def render_lines_with_highlight(lines, selected_index):
    """
    Returnerar en enda sträng med \n-separerade rader,
    där rad nr `selected_index` har ANSI-escape för 'reverse' (d.v.s. invert).
    """
    out = []
    for i, line in enumerate(lines):
        if i == selected_index:
            # \x1b[7m => Sätt terminalen i 'reverse'
            # \x1b[0m => Återställ stil
            out.append(f"\x1b[7m{line}\x1b[0m")
        else:
            out.append(line)
    return "\n".join(out)

def _do_copy(index):
    """Kopiera referens från den aktuella listan."""
    global last_shown_results, bib_data

    # Debug-info
    debug_log(f"Kopiering: Försöker kopiera index {index} från {len(last_shown_results)} resultat.")

    if index < 0 or index >= len(last_shown_results):
        print("Ogiltigt index.")
        return

    # Hämta sökresultatets "idx" som pekar in i bib_data
    result = last_shown_results[index]
    real_idx = result["idx"]  # den index ni satte i _search_and_score_entries

    # Hämta den riktiga bibposten:
    keys = list(bib_data.keys())
    key = keys[real_idx]
    bib_entry = bib_data[key]

    # Skicka bibposten till generate_apa:
    apa = generate_apa(bib_entry)

    # Output till användaren
    print(f"\n{apa}\n")
    copy_to_clipboard(apa)
    debug_log(f"Referens kopierad: {apa}")

def _print_help():
    if LANGUAGE=="sv":
      print("""
Kommandon:
  ladda <fil>           : Ladda .bib
  sök <termer>          : Standard sök
  sc <termer> [antal]   : Kompakt sök
  kopiera <index>       : Kopiera referens
  lang <sv|en>          : Byt språk
  hjälp                 : Denna hjälp
  avsluta               : Avsluta
""")
    else:
      print("""
Commands:
  load <file>           : Load .bib
  search <terms>        : Standard search
  sc <terms> [n]        : Compact search
  copy <index>          : Copy reference
  lang <sv|en>          : Switch language
  help                  : This help
  exit                  : Quit
""")

def interactive_shell():
    _ensure_interactive_imports()
    load_language_setting()
    session = PromptSession(history=FileHistory(HISTORY_FILE))

    while True:
        try:
            if LANGUAGE=="sv":
                line= session.prompt("\nKommando > ").strip()
            else:
                line= session.prompt("\nCommand > ").strip()

            if not line:
                continue
            args= line.split()
            cmd= args[0].lower()

            if cmd.isdigit():
                _do_copy(int(cmd)-1)
                continue

            if cmd in ["exit","quit","avsluta"]:
                if LANGUAGE=="sv":
                    print("Avslutar...\n")
                else:
                    print("Exiting...\n")
                break

            if cmd in ["help","hjälp"]:
                _print_help()
                continue

            if cmd in ["load","ladda"]:
                if len(args)<2:
                    print("Usage: load <file> / ladda <fil>")
                    continue
                load_bibtex(args[1])
                continue

            if cmd in ["search","sök"]:
                if len(args)<2:
                    print("Usage: search <terms> / sök <termer>")
                    continue
                q= " ".join(args[1:])
                search_entries(q)
                continue

            if cmd in ["sc","sökc","sökcompact","searchcompact"]:
                maxres=10
                try:
                    mi= int(args[-1])
                    q=" ".join(args[1:-1])
                    maxres=mi
                except ValueError:
                    q=" ".join(args[1:])
                if not q:
                    print("Usage: sc <terms> [n] / sökc <termer> [antal]")
                    continue
                search_entries_compact(q,maxres)
                continue

            if cmd in ["copy","kopiera"]:
                if len(args)<2:
                    print("Usage: copy <index> / kopiera <index>")
                    continue
                try:
                    ix= int(args[1])-1
                    _do_copy(ix)
                except ValueError:
                    print("Ange en siffra.\n")
                continue

            if cmd in ["lang","language"]:
                if len(args)<2:
                    print(f"Current language: {LANGUAGE}")
                    continue
                nl= args[1].lower()
                if nl in ["sv","en"]:
                    save_language_setting(nl)
                    if nl=="sv":
                        print("Språk satt till svenska.")
                    else:
                        print("Language set to English.")
                else:
                    print("Invalid language (only 'sv' or 'en').")
                continue

            # Anta att okänt kommando är söktermer
            if bib_data:
                search_entries(line)
            else:
                if LANGUAGE == "sv":
                    print("Ingen fil laddad. Använd 'ladda <fil>' först.")
                else:
                    print("No file loaded. Use 'load <file>' first.")
        except (EOFError,KeyboardInterrupt):
            if LANGUAGE=="sv":
                print("\nAvslutar...\n")
            else:
                print("\nExiting...\n")
            break

# -------------------------------------------------
# Interaktiv kompakt vy
# -------------------------------------------------
def update_text_area_with_results(new_results):
    """
    Uppdaterar 'body_window' (en Window med FormattedTextControl) med nya rader.
    Används ex. vid filtrering, så man bara visar de 'new_results'.
    """
    global body_window
    if not body_window:
        return  # Om body_window inte är definierad, avbryt

    # Bygg tokens (utan highlight här - men ni kan lägga in logik för 'selected_row' osv. om ni vill).
    tokens = []
    for r in new_results:
        line = build_compact_line(
            index=r.get("idx", 9999),  # Ni kan välja hur ni vill hantera index
            score=r["score"],
            authors=r["authors"],
            year=r["year"],
            title=r["title"],
            query_terms=[],            # Valfritt highlight
            max_len=COMPACT_MAX_CHARS
        )
        # Lägg till radbryt
        line += "\n"
        tokens.append(("", line))

    # Sätt 'body_window.content' = en ny FormattedTextControl med dessa tokens
    body_window.content = FormattedTextControl(
        text=tokens,
        focusable=True
    )


def interactive_result_view_compact(results, query_terms):
    """
    Interaktiv kompakt vy baserad på Window+FormattedTextControl i stället för TextArea.
    Fungerar även i äldre prompt_toolkit-versioner.
    Vi använder en scrollbar, highlightar vald rad och kan trycka "enter" etc.

    - global body_window => så att update_text_area_with_results(...) kan referera till den.
    """
    _ensure_interactive_imports()
    global original_results, last_shown_results
    global body_window

    original_results = results
    last_shown_results = results

    # Start med selected_row = 0
    selected_row = 0

    # En liten funktion som bygger tokens-listan (en rad => ev. "reverse")
    def build_tokens_for_current_view():
        return build_compact_tokens(results, query_terms, selected_row)

    # Skapa en FormattedTextControl baserat på tokens
    body_control = FormattedTextControl(
        text=build_tokens_for_current_view(),
        focusable=True,
    )

    # Skapa en Window + scrollbar
    body_window = Window(
        content=body_control,
        right_margins=[ScrollbarMargin()],
        wrap_lines=False,
        dont_extend_height=False,
        dont_extend_width=False,
    )

    kb = KeyBindings()
    floats = []

    @kb.add("q")
    def _(event):
        event.app.exit()

    @kb.add("up")
    def on_up(event):
        nonlocal selected_row
        if selected_row > 0:
            selected_row -= 1
        body_control.text = build_tokens_for_current_view()

    @kb.add("down")
    def on_down(event):
        nonlocal selected_row
        if selected_row < len(results) - 1:
            selected_row += 1
        body_control.text = build_tokens_for_current_view()

    @kb.add("enter")
    def on_enter(event):
        if 0 <= selected_row < len(results):
            actual_idx = results[selected_row]["idx"]
            keys = list(bib_data.keys())
            key = keys[actual_idx]
            e = bib_data[key]
            apa = generate_apa(e)
            copy_to_clipboard(apa)
            show_popup_dialog(apa, floats, body_window)

    @kb.add("/")
    def on_slash(event):
        # Filtreringsdialog
        show_filter_dialog(results, body_window, floats)

    @kb.add("backspace")
    def on_backspace(event):
        """
        Återställ till originalresultat om ingen dialogruta är öppen.
        """
        global last_shown_results
        if not floats:
            debug_log("Backspace trycktes: återställer resultat.")
            last_shown_results = results
            body_control.text = build_tokens_for_current_view()
        else:
            debug_log("Backspace ignorerades: dialogruta är öppen.")

    @kb.add("pageup")
    def page_up(event):
        w = body_window
        info = w.render_info
        if info:
            page_size = info.window_height
            new_val = max(0, w.vertical_scroll - page_size)
            w.vertical_scroll = new_val

    @kb.add("pagedown")
    def page_down(event):
        w = body_window
        info = w.render_info
        if info:
            page_size = info.window_height
            max_scroll = info.content_height - info.window_height
            new_val = min(max_scroll, w.vertical_scroll + page_size)
            w.vertical_scroll = new_val

    frame = Frame(
        body_window,
        title="(Enter=copy, /=filter, PageUp/Down, Up/Down, q=quit)"
    )

    root_container = FloatContainer(content=frame, floats=floats)
    layout = Layout(root_container)

    app = Application(
        layout=layout,
        key_bindings=kb,
        full_screen=True
    )
    app.run()


def show_filter_dialog(results, text_area, floats_list):
    """
    Visar en modal dialog för att filtrera resultat.
    Vid [Enter] kallas apply_filter(). Vid [Escape] stängs rutan.
    När rutan stängs, återställs tangentbindningarna och fokus till 'text_area'.
    """
    input_box = TextArea(
        text="",
        multiline=False,  # Enkelradsinmatning
        wrap_lines=False,
    )

    def apply_filter():
        """Filtrera resultat baserat på sökterm och uppdatera vyn."""
        query = input_box.text.lower().strip()
        debug_log(f"Filtrering: Sökterm är '{query}'.")

        filtered_results = [
            r for r in results
            if query in r["authors"].lower()
            or query in r["title"].lower()
            or query in r["year"].lower()
        ]

        debug_log(f"Filtrering: {len(filtered_results)} resultat matchar.")

        if not filtered_results:
            text_area.text = "Inga träffar för filtret."
            debug_log("Inga träffar för filtret.")
        else:
            # Uppdatera globala last_shown_results
            global last_shown_results
            last_shown_results = filtered_results
            debug_log(f"Filtrering: Uppdaterade last_shown_results med {len(filtered_results)} resultat.")

            # Uppdatera själva text_area (eller Window) med nya rader
            update_text_area_with_results(filtered_results)

        close_dialog()

    def reset_filter():
        """Återställ till den ursprungliga listan och visningen."""
        global last_shown_results
        debug_log("Återställer till ursprungliga resultat.")

        last_shown_results = results
        debug_log(f"Antal resultat i återställd lista: {len(results)}.")

        update_text_area_with_results(results)
        close_dialog()

    def close_dialog():
        """Stänger dialogen, återställer tangentbindningar och fokus."""
        if floats_list:
            floats_list.pop()
        app.key_bindings = old_key_bindings
        get_app().layout.focus(text_area)

    # Lokala tangentbindningar för dialogfönstret
    local_kb = KeyBindings()

    @local_kb.add("enter")
    def _(event):
        apply_filter()

    @local_kb.add("escape")
    def _(event):
        close_dialog()

    # Skapa själv Dialog-objektet
    dlg = Dialog(
        title="Filtrera resultat",
        body=input_box,
        buttons=[],  # Inga knappar
        width=60,
        modal=True,
    )

    # Lägg till dialogen i floats
    app = get_app()
    floats_list.append(Float(content=dlg))

    # Spara de gamla tangentbindningarna och sätt nya
    old_key_bindings = app.key_bindings
    app.key_bindings = local_kb

    # Sätt fokus på inmatningsrutan
    app.layout.focus(input_box)


def show_popup_dialog(apa_text, floats_list, text_area):
    """
    Visar en modal dialog med 'apa_text'.
    Stängs med Enter eller Escape. När den stängs
    återställs tangentbindningar och fokus till 'text_area'.
    """
    text_area_dialog = TextArea(
        text=apa_text,
        read_only=True,
        wrap_lines=True
    )

    # Lokala tangentbindningar för dialogen.
    local_kb = KeyBindings()

    def close_dialog():
        """Ta bort dialogen och återställ fokus + key_bindings."""
        if floats_list:
            floats_list.pop()
        app.key_bindings = old_key_bindings  # Återställ
        get_app().layout.focus(text_area)

    @local_kb.add("enter")
    @local_kb.add("escape")
    def _(event):
        close_dialog()

    dlg = Dialog(
        title="Kopierad!",
        body=text_area_dialog,
        buttons=[],  # Inga knappar
        width=60,
        modal=True
    )

    # Lägg till dialogen som en overlay i floats_list
    app = get_app()
    floats_list.append(Float(content=dlg))

    # Spara gamla tangentbindningar och sätt nya
    old_key_bindings = app.key_bindings
    app.key_bindings = local_kb

    # Sätt fokus på dialogfönstret
    app.layout.focus(dlg)

#  show_popup använder en Dialog i Float, ingen extra .run()
def show_popup(title_text, body_text):
    """
    LÄMNAD tom ifall du använde denna för nåt annat. 
    Men du kan ta bort helt om du vill.
    """
    pass

# -------------------------------------------------
# 9) main
# -------------------------------------------------
if __name__ == "__main__":
    load_language_setting()
    args = parse_args()

    # Sätt globala flaggor
    DEBUG_MODE = args.debug
    VERBOSE_MODE = args.verbose

    # Bestäm bib-fil
    DEFAULT_BIB = os.path.expanduser("~/Documents/lektionsplanering/kallor.bib")
    bib_file = args.bibfile

    # Kolla om query innehåller en fil (bakåtkompatibilitet)
    if not bib_file and args.query:
        for q in args.query:
            if os.path.isfile(q):
                bib_file = q
                args.query.remove(q)
                break

    if not bib_file:
        if os.path.isfile(DEFAULT_BIB):
            bib_file = DEFAULT_BIB
        else:
            bf = get_last_used_file()
            if bf:
                bib_file = bf
            elif args.key or args.one or args.num:
                if LANGUAGE == "sv":
                    print("Ingen .bib-fil specad och ingen senast använd fil funnen.", file=sys.stderr)
                else:
                    print("No .bib file specified and no last used file found.", file=sys.stderr)
                sys.exit(1)

    # Ladda bib-fil
    if bib_file:
        load_bibtex(bib_file, verbose=VERBOSE_MODE)

    # Icke-interaktivt läge: -k (key lookup)
    if args.key:
        if not bib_data:
            if LANGUAGE == "sv":
                print("Ingen data laddad.", file=sys.stderr)
            else:
                print("No data loaded.", file=sys.stderr)
            sys.exit(1)

        output = get_reference_by_key(args.key, args.format)
        if output:
            print(output)
            sys.exit(0)
        else:
            if LANGUAGE == "sv":
                print(f"Hittade ingen referens med key '{args.key}'.", file=sys.stderr)
            else:
                print(f"No reference found with key '{args.key}'.", file=sys.stderr)
            sys.exit(1)

    # Icke-interaktivt läge: -1/--one eller -n N
    num_results = args.num if args.num else (1 if args.one else None)
    if num_results:
        if not bib_data:
            if LANGUAGE == "sv":
                print("Ingen data laddad.", file=sys.stderr)
            else:
                print("No data loaded.", file=sys.stderr)
            sys.exit(1)

        if not args.query:
            if LANGUAGE == "sv":
                print("Inga söktermer angivna.", file=sys.stderr)
            else:
                print("No search terms provided.", file=sys.stderr)
            sys.exit(1)

        output = get_top_search_results(args.query, args.format, limit=num_results)
        if output:
            print(output)
            sys.exit(0)
        else:
            if LANGUAGE == "sv":
                print("Inga träffar.", file=sys.stderr)
            else:
                print("No results found.", file=sys.stderr)
            sys.exit(1)

    # Interaktivt läge (default)
    if args.query and bib_data:
        query = " ".join(args.query)
        search_entries(query)

    interactive_shell()

