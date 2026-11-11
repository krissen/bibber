#!/usr/bin/env python3
import argparse
import collections
import collections.abc
import hashlib
import json
import os
import re
import subprocess
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
    from prompt_toolkit.layout.containers import Float as _Float
    from prompt_toolkit.layout.containers import FloatContainer as _FloatContainer
    from prompt_toolkit.layout.containers import Window as _Window
    from prompt_toolkit.layout.controls import (
        FormattedTextControl as _FormattedTextControl,
    )
    from prompt_toolkit.layout.margins import ScrollbarMargin as _ScrollbarMargin
    from prompt_toolkit.widgets import Dialog as _Dialog
    from prompt_toolkit.widgets import Frame as _Frame
    from prompt_toolkit.widgets import TextArea as _TextArea

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


# biblatex-arv vid crossref: förälderns titelfält blir barnets boktitelfält,
# och fält som identifierar själva föräldern (DOI, ISBN, fil, sammanfattning)
# ärvs inte, eftersom kapitlet annars får bokens DOI som egen länk.
CROSSREF_TITLE_MAP = {
    "title": "booktitle",
    "subtitle": "booksubtitle",
    "titleaddon": "booktitleaddon",
}
CROSSREF_CONTAINED_TYPES = {
    "incollection", "inbook", "inproceedings", "bookinbook",
    "suppbook", "suppcollection", "inreference",
}
# Det ett kapitel (eller annan del av en volym) ärver: bara det som behövs för
# att beskriva volymen i kapitlets referens. Fält som beskriver själva boken
# (note, annotate, addendum, isbn, rights …) ärvs inte; annars skrev
# Schweitzer2026 ut förälderns "[Open access … Print-ISBN …]" som sin egen.
# Upplaga ingår, eftersom APA anger den i kapitelreferensen, och author, så att
# ett @inbook i en monografi får bokens författare (biblatex gör likadant).
CROSSREF_CONTAINED_FIELDS = {
    "author", "editor", "editortype", "bookauthor", "publisher", "organization",
    "year", "date", "series", "volume", "edition", "booktitle",
    "booksubtitle", "booktitleaddon", "location", "address", "language",
}
# biblatex-arv periodical -> article/suppperiodical: numrets title är
# tidskriftens namn och blir barnets journaltitle. Bara en vitlista ärvs;
# numrets editor, note, series, file m.m. beskriver numret, inte artikeln,
# och okända fält (t.ex. pdfpageoffset) ska aldrig följa med.
PERIODICAL_TITLE_MAP = {
    "title": "journaltitle",
    "subtitle": "journalsubtitle",
    "titleaddon": "journaltitleaddon",
}
PERIODICAL_CHILD_TYPES = {"article", "suppperiodical"}
PERIODICAL_INHERIT_FIELDS = {
    "year", "date", "month", "volume", "number", "issue", "issn", "language",
    "journal", "journaltitle",
}
CROSSREF_SKIP = {
    "crossref", "xref", "ids", "entrytype", "shorttitle", "shorthand",
    "doi", "isbn", "url", "urldate", "file", "abstract", "keywords",
    "pagetotal", "owner", "timestamp", "modificationdate", "date-added",
    "date-modified", "creationdate", "label", "sortkey",
}


def resolve_crossrefs_dict(entries):
    """Löser crossref på dict-nivå (efter sammanslagning av flera .bib-filer).

    Barnets egna fält vinner alltid. Uppslag av förälderns nyckel är
    skiftlägesokänsligt, som i biber.
    """
    by_lower = {k.lower(): v for k, v in entries.items()}
    for entry in entries.values():
        ref = entry.get("crossref", "").strip("{} ")
        parent = by_lower.get(ref.lower()) if ref else None
        if not parent:
            continue
        # Titelflytten gäller bara delar av en samlingsvolym (som i biblatex);
        # en bok som crossrefar en annan bok ärver titeln som vanligt.
        contained = entry.get("entrytype", "").lower() in CROSSREF_CONTAINED_TYPES
        from_periodical = (
            entry.get("entrytype", "").lower() in PERIODICAL_CHILD_TYPES
            and parent.get("entrytype", "").lower() == "periodical"
        )
        # journal och journaltitle är ett par, som year/date: har barnet ett
        # av dem ärvs varken numrets title (med subtitle/titleaddon) eller
        # förälderns journal/journaltitle, annars skuggar de barnets eget.
        own_journal = bool(entry.get("journal") or entry.get("journaltitle"))
        if from_periodical and not own_journal:
            for src, dst in PERIODICAL_TITLE_MAP.items():
                val = parent.get(src)
                if val and not entry.get(dst):
                    entry[dst] = val
        if contained:
            for src, dst in CROSSREF_TITLE_MAP.items():
                val = parent.get(src)
                if val and not entry.get(dst):
                    entry[dst] = val
        # year och date är ett par: har barnet det ena ärvs inget av dem,
        # annars skuggar förälderns year barnets date.
        own_date = bool(entry.get("year") or entry.get("date"))
        for fkey, val in parent.items():
            if fkey in CROSSREF_SKIP or (contained and fkey in CROSSREF_TITLE_MAP):
                continue
            if from_periodical and (
                fkey not in PERIODICAL_INHERIT_FIELDS
                or (own_journal and fkey in ("journal", "journaltitle"))
            ):
                continue
            if own_date and fkey in ("year", "date"):
                continue
            if fkey.startswith("bdsk-"):
                continue
            if contained and fkey not in CROSSREF_CONTAINED_FIELDS:
                continue
            if val and not entry.get(fkey):
                entry[fkey] = val
    return entries


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

CACHE_DIR = os.path.expanduser(os.environ.get("BIBBER_CACHE_DIR", "~/.cache/bibber/"))
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
# Översatta titlar som inte ska skrivas ut: alla (--no-translation utan
# nycklar) eller bara dessa nycklar, i gemener.
NO_TRANSLATION_ALL = False
NO_TRANSLATION_KEYS = set()
COMPACT_MAX_CHARS = 95  # hård max-längd i kompakt vy
CACHE_KEEP = 5  # antal cachefiler (bib-kombinationer/versioner) som sparas
CACHE_VERSION = "4"  # Bump vid ändringar i cache-format (3: sökindex, 4: crossref-arv)

# -------------------------------------------------
# Argument-parsning
# -------------------------------------------------
def _release_version(root):
    """Versionen i pyproject.toml bredvid källfilen, annars den installerade
    paketversionen. Källträdet går först: en checkout som körs direkt ska ange
    sin egen version, inte den som råkar vara installerad i miljön."""
    try:
        with open(os.path.join(root, "pyproject.toml"), encoding="utf-8") as f:
            in_project = False
            for line in f:
                stripped = line.strip()
                if stripped.startswith("["):
                    in_project = stripped == "[project]"
                elif in_project:
                    m = re.match(r'version\s*=\s*"([^"]+)"', stripped)
                    if m:
                        return m.group(1)
    except OSError:
        pass
    try:
        from importlib.metadata import PackageNotFoundError, version
        try:
            return version("bibber")
        except PackageNotFoundError:
            return ""
    except ImportError:
        return ""


def _git(root, *args):
    try:
        out = subprocess.run(["git", "-C", root, *args], capture_output=True,
                             text=True, timeout=5, check=False)
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout.strip() if out.returncode == 0 else None


def version_string():
    """'0.1.0' när HEAD bär taggen v0.1.0, annars '0.1.0+abc1234'; samma regel
    som bifrost (R/utils_version.R). Git frågas bara i bibbers eget källträd,
    aldrig i arbetskatalogen: där kan en annan checkout ge sin SHA till en
    sträng som påstår sig beskriva bibber. Utan .git (installerat paket) är
    versionen den släppta; med .git men utan svar från git blir den
    '+unknown', så att ett utvecklingsträd aldrig ser ut som en release."""
    root = os.path.dirname(os.path.realpath(__file__))
    release = _release_version(root) or "0.0.0"
    # I en worktree är .git en fil med en gitdir-pekare, inte en katalog.
    if not os.path.exists(os.path.join(root, ".git")):
        return release
    sha = _git(root, "rev-parse", "--short=7", "HEAD")
    if not sha:
        return f"{release}+unknown"
    tags = (_git(root, "tag", "--points-at", "HEAD") or "").split()
    return release if f"v{release}" in tags else f"{release}+{sha}"


class _VersionAction(argparse.Action):
    """--version räknar fram strängen först när flaggan används, så att git
    inte anropas vid varje körning."""
    def __init__(self, option_strings, dest, **kwargs):
        super().__init__(option_strings, dest, nargs=0, **kwargs)

    def __call__(self, parser, namespace, values, option_string=None):
        print(f"bibber {version_string()}")
        parser.exit()


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
    # extend, inte standardvärdet store: annars ersätter varje upprepad -k den
    # förra, och "-k A -k B" skrev tyst bara ut B.
    parser.add_argument("-k", "--key", nargs="+", action="extend", metavar="KEY",
                        help="Hämta en eller flera citation keys direkt; en referens "
                             "per stycke i given ordning. -k kan upprepas")
    parser.add_argument("--keys", metavar="FIL",
                        help="Fil med en citation key per rad (tomma rader och "
                             "#-kommentarer hoppas över); '-' läser stdin")
    parser.add_argument("--lang", choices=["sv", "en"],
                        help="Språk för den här körningen (sparas inte; "
                             "interaktiva 'lang' sparar)")
    # Två flaggor i stället för en med nargs="*": en sådan sväljer söktermer och
    # en positionell .bib-fil som står efter den, och "--no-translation fil.bib"
    # renderade då tyst ur standardbiblioteket.
    parser.add_argument("--no-translation", action="store_true",
                        help="Skriv inte ut översatta titlar (title_translation_<språk>)")
    parser.add_argument("--no-translation-for", action="append", metavar="KEY",
                        help="Skriv inte ut översättningen för den här posten "
                             "(nyckel eller alias i ids); kan upprepas")
    parser.add_argument("-1", "--one", action="store_true",
                        help="Icke-interaktivt: ge första träffen och avsluta (genväg för -n1)")
    parser.add_argument("-n", "--num", type=int, metavar="N",
                        help="Icke-interaktivt: visa N bästa träffar och avsluta")
    parser.add_argument("-V", "--version", action=_VersionAction,
                        help="Visa version och avsluta (x.y.z på en release, "
                             "x.y.z+commit annars)")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="Visa extra information (t.ex. 'Laddar fil...')")
    parser.add_argument("-d", "--debug", action="store_true",
                        help="Debug-läge")
    parser.add_argument("-b", "--bibfile", action="append", metavar="FIL",
                        help=".bib-fil att ladda; upprepa för flera. Vid samma "
                             "nyckel vinner den fil som anges först")
    return parser.parse_args()

# -------------------------------------------------
# 1) Fil & hjälp
# -------------------------------------------------
def save_last_used_file(file_path):
    """Sparar senast använda fil(er); en lista när flera -b angavs."""
    if isinstance(file_path, (list, tuple)) and len(file_path) == 1:
        file_path = file_path[0]
    last_used = os.path.join(CACHE_DIR, "last_used_bibfile.json")
    with open(last_used, "w") as f:
        json.dump({"last_used": file_path}, f)

def default_bib_file():
    """Standardfilen när -b saknas: $BIBBER_BIB, annars första raden som inte
    är tom eller en #-kommentar i $XDG_CONFIG_HOME/bibber/default_bib
    (~/.config/bibber/default_bib).
    Finns ingen av dem används den senast använda filen. Sökvägen låg förut
    hårdkodad i koden, vilket band verktyget till en enda användares bibliotek."""
    env = os.environ.get("BIBBER_BIB", "").strip()
    if env:
        return os.path.expanduser(env)
    conf_dir = os.environ.get("XDG_CONFIG_HOME") or "~/.config"
    conf = os.path.join(os.path.expanduser(conf_dir), "bibber", "default_bib")
    try:
        with open(conf, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    return os.path.expanduser(line)
    except OSError:
        pass
    return ""


def get_last_used_file():
    last_used = os.path.join(CACHE_DIR, "last_used_bibfile.json")
    if os.path.exists(last_used):
        try:
            with open(last_used, "r") as f:
                data=json.load(f)
                return data.get("last_used")
        except (OSError, json.JSONDecodeError):
            pass
    return None

def _script_digest():
    """md5 av bibber.py självt; tom sträng om filen inte går att läsa."""
    try:
        return md5sum(os.path.realpath(__file__))
    except OSError:
        return ""


def _prune_cache(keep):
    """Behåller de `keep` senast använda cachefilerna och tar bort resten.

    Varje ändring av en .bib-fil eller av bibber.py ger en ny cachefil
    (~2,5 MB för kallor.bib); utan gallring växte ~/.cache/bibber till
    52 MB (2026-11-07). Bara filer vars namn är en md5-summa rörs, så
    lang.json och last_used_bibfile.json står kvar.
    """
    try:
        names = [n for n in os.listdir(CACHE_DIR)
                 if re.fullmatch(r"[0-9a-f]{32}\.json", n)]
        paths = sorted((os.path.join(CACHE_DIR, n) for n in names),
                       key=os.path.getmtime, reverse=True)
        for old in paths[keep:]:
            os.remove(old)
    except OSError:
        pass  # gallring är städning, aldrig ett skäl att fallera


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
    except (OSError, json.JSONDecodeError):
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
        except (OSError, json.JSONDecodeError):
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


def load_bibtex(file_paths, verbose=None):
    """
    Laddar en eller flera BibTeX-filer.

    Args:
        file_paths: Sökväg eller lista av sökvägar. Vid samma nyckel i flera
            filer vinner den fil som kommer FÖRST, så en lokal fil med
            anpassade poster läggs före den gemensamma (-b lokal.bib -b kallor.bib).
            Crossref löses över alla filer efter sammanslagningen.
        verbose: Om True, visa laddningsmeddelanden. Om None, använd VERBOSE_MODE.
    """
    global bib_data, processed_entries_cache
    if verbose is None:
        verbose = VERBOSE_MODE

    if isinstance(file_paths, str):
        file_paths = [file_paths]
    file_paths = [os.path.expanduser(f) for f in file_paths]
    try:
        digests = [md5sum(f) for f in file_paths]
    except FileNotFoundError as e:
        print(f"Error loading bib: {e}", file=sys.stderr)
        return
    # Cachen bär färdigresolvad data (crossref-arv), så nyckeln innehåller
    # även skriptets egen hash: en ändrad arvsregel ger då ny cache utan att
    # någon behöver komma ihåg att bumpa CACHE_VERSION.
    cache_id = hashlib.md5("|".join([_script_digest()] + digests).encode()).hexdigest()
    cfile = os.path.join(CACHE_DIR, cache_id + ".json")
    shown = ", ".join(file_paths)

    cached_entries, cached_index = load_from_cache(cfile)
    if cached_entries:
        try:
            os.utime(cfile)  # senast använd, för gallringen i _prune_cache
        except OSError:
            pass
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
                print(f"Laddar senast använda fil: {shown}", file=sys.stderr)
            else:
                print(f"Loading last used file: {shown}", file=sys.stderr)
        save_last_used_file(file_paths)
    else:
        try:
            merged = {}
            seen_lower = set()
            for file_path in file_paths:
                if verbose:
                    if LANGUAGE == "sv":
                        print(f"Laddar fil: {file_path}", file=sys.stderr)
                    else:
                        print(f"Loading file: {file_path}", file=sys.stderr)
                library = bibtexparser.parse_file(file_path)
                if library.failed_blocks:
                    print(f"Varning: {len(library.failed_blocks)} parsningsfel i {file_path}",
                          file=sys.stderr)
                for key, entry in library_to_dict(library).items():
                    if key.lower() in seen_lower:
                        continue  # tidigare fil vinner
                    seen_lower.add(key.lower())
                    merged[key] = entry
            bib_data = resolve_crossrefs_dict(merged)

            # Bygg och cacha sökindex
            search_index = _build_search_index(bib_data)
            processed_entries_cache = [(i, s) for i, s in enumerate(search_index)]

            save_to_cache(bib_data, cfile, search_index)
            _prune_cache(keep=CACHE_KEEP)
            save_last_used_file(file_paths)
        except Exception as e:
            print(f"Error loading bib: {e}", file=sys.stderr)
            return

# -------------------------------------------------
# 4) En förenklad APA, tar hänsyn till LANGUAGE
# -------------------------------------------------
# Språkberoende etiketter för APA 7. Svenska följer de svenska
# APA-anvisningarna (I, Red., s., uppl., u.å.).
APA_LABELS = {
    "sv": {
        "no_date": "u.å.", "ed1": "Red.", "edn": "Red.", "in": "I",
        "page": "s.", "pages": "s.", "edition": "uppl.",
        "phd": "Doktorsavhandling", "lic": "Licentiatuppsats",
        "master": "Masteruppsats", "thesis": "Examensarbete",
        "retrieved": "Hämtad {date} från {url}",
        "report_no": "{label} {number}",
        "resreport": "Forskningsrapport", "techreport": "Teknisk rapport",
        "amended": "ändrad t.o.m. {version}",
    },
    "en": {
        "no_date": "n.d.", "ed1": "Ed.", "edn": "Eds.", "in": "In",
        "page": "p.", "pages": "pp.", "edition": "ed.",
        "phd": "Doctoral dissertation", "lic": "Licentiate thesis",
        "master": "Master's thesis", "thesis": "Thesis",
        "retrieved": "Retrieved {date}, from {url}",
        "report_no": "{label} No. {number}",
        "resreport": "Research report", "techreport": "Technical report",
        "amended": "amended up to and including {version}",
    },
}

# Rapporter (@report, @techreport). APA 7: kursiv titel, därefter rapportens
# beteckning i parentes och utgivaren om den inte är författaren. Formen följer
# Lunds universitetsbiblioteks APA 7-guide (Rapporter, uppdaterad 2026-05-21):
#   Rapportens titel (Rapport 5786). Utgivare. URL
# och på engelska APA:s exempel "(NIH Publication No. 02-2650)" (Normandale
# Community College, Quick Guide to APA References, rev. okt 2025).
# Beteckningen är type eller series följt av number; biblatex typnycklar
# (resreport, techreport) översätts. Utan type och series står numret ensamt:
# en etikett som "Rapport" hittas inte på, eftersom numret ofta är ett
# diarienummer. En serie utan nummer står i parentes som i Lunds mall; en typ
# utan nummer är en beskrivning och står i hakparentes. Finns både serie och
# typ hör numret till serien, och typen blir beskrivningen.
REPORT_TYPES = {"report", "techreport"}
REPORT_TYPE_KEYS = {"resreport": "resreport", "techreport": "techreport"}


def _report_designation(entry):
    """(parentes, hakparentes) för en rapport, t.ex. ('Rapport 5786', '')."""
    lab = _labels()
    raw_type = safe_latex_to_text(entry.get("type", "")).strip()
    key = REPORT_TYPE_KEYS.get(raw_type.lower())
    rtype = lab[key] if key else raw_type
    rtype = rtype[0].upper() + rtype[1:] if rtype else ""
    series = safe_latex_to_text(entry.get("series", "")).strip()
    number = safe_latex_to_text(entry.get("number", "")).strip()
    if series:
        paren = lab["report_no"].format(label=series, number=number) if number else series
        return paren, rtype
    if number:
        if not rtype:
            return number, ""
        return lab["report_no"].format(label=rtype, number=number), ""
    return "", rtype


# biblatex-typnycklar i fältet `type` och vilken etikett de motsvarar.
THESIS_TYPE_KEYS = {
    "phdthesis": "phd", "phd": "phd", "doctoral": "phd",
    "licentiatethesis": "lic", "licthesis": "lic",
    "mathesis": "master", "mastersthesis": "master", "masterthesis": "master",
}


def _labels():
    return APA_LABELS.get(LANGUAGE, APA_LABELS["en"])


def _cap_after_colon(text):
    """APA: versal på första bokstaven efter kolon i titel. Inget annat ändras."""
    return re.sub(r":(\s+)(\W*)(\w)",
                  lambda m: f":{m.group(1)}{m.group(2)}{m.group(3).upper()}", text)


def _join_title(main, sub):
    """Huvudtitel + undertitel med kolon, första bokstaven versal."""
    main = safe_latex_to_text(main or "").strip()
    sub = safe_latex_to_text(sub or "").strip()
    if sub:
        sub = sub[0].upper() + sub[1:]
        if not main:
            main = sub
        elif main.rstrip()[-1] in "?!":
            # APA: en titel som slutar på ? eller ! får inget kolon
            main = f"{main.rstrip()} {sub}"
        else:
            main = f"{main.rstrip(' :')}: {sub}"
    if main:
        main = main[0].upper() + main[1:]
    return _cap_after_colon(main)


def _unbracket(raw):
    """Tar bort hakparenteser som omsluter HELA värdet, så att de inte
    dubbleras när bibber sätter egna: '[Recension]' blir 'Recension', men
    '[A] och [B]' lämnas orört (de yttre klamrarna hör inte ihop)."""
    if not (raw.startswith("[") and raw.endswith("]")):
        return raw
    depth = 0
    for i, ch in enumerate(raw):
        if ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
            if depth == 0 and i < len(raw) - 1:
                return raw
    return raw[1:-1].strip()


def _titleaddon(entry):
    """`titleaddon` som APA-beskrivning i hakparentes direkt efter titeln:
    'Smältdegel och mångkultur? [Recension av …].' (Purdue OWL, APA 7 Review).
    Beskrivningen hör till titelelementet, så punkten står efter hakparentesen,
    också när titeln slutar på ? eller !. Klamrar som redan står i fältet tas
    bort, så att de inte dubbleras."""
    raw = _unbracket(safe_latex_to_text(entry.get("titleaddon", "")).strip())
    return f" [{raw}]" if raw else ""


def _translation(entry, key=None):
    """Översättningen av titeln till målspråket, i hakparentes direkt efter
    originaltiteln: 'Essentialism i religionsundervisningen [Essentialism in
    teaching religion]'. Fältet title_translation_<språk> bär hela den översatta
    titeln (titel och undertitel); syntaxen är biblatex-ms (Kime2023biblatexms40,
    s. 161). Målspråket är utskriftens språk (--lang): APA 7 översätter titeln
    till den citerande textens språk, och titlar på engelska, danska och norska
    översätts inte i svensk text (LUB2026apa7otherlang, LUB2026apa7annatsprak).
    Det senare följer av datat: posten har då inget sv-fält. Hakparentesen är
    inte kursiv, också när originaltiteln är det (biblatex-apa skriver origtitle
    och sedan title i hakparentes, apa.bbx rad 771-792). Samma modell som
    krissen_translation.sty i krissen-tex."""
    if NO_TRANSLATION_ALL:
        return ""
    # Undantaget gäller posten, oavsett om den anges med nyckel eller alias (ids).
    names = {a.strip().lower() for a in entry.get("ids", "").split(",") if a.strip()}
    if key:
        names.add(key.lower())
    if names & NO_TRANSLATION_KEYS:
        return ""
    raw = _unbracket(safe_latex_to_text(entry.get(f"title_translation_{LANGUAGE}", "")).strip())
    return f" [{raw}]" if raw else ""


def _pages(raw):
    """Sidintervall med tankstreck (APA): 75-93 och 75--93 blir 75–93."""
    pp = (raw or "").replace("---", "–").replace("--", "–").strip()
    pp = re.sub(r"(?<=\w)\s*-\s*(?=\w)", "–", pp)
    return pp


def _page_label(pp):
    lab = _labels()
    if re.search(r"[–,]", pp):
        return lab["pages"]
    return lab["page"]


def _edition(raw):
    """'2' → '2 uppl.' / '2nd ed.'; fritext lämnas som den är."""
    raw = safe_latex_to_text(raw or "").strip()
    if not raw:
        return ""
    lab = _labels()
    if raw.isdigit():
        if LANGUAGE == "sv":
            return f"{raw} {lab['edition']}"
        n = int(raw)
        suffix = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
        return f"{n}{suffix} {lab['edition']}"
    if re.search(r"(uppl|ed)\.?$", raw, re.IGNORECASE):
        return raw
    return f"{raw} {lab['edition']}"


def _tidy(text):
    """Städar skiljetecken i referenskroppen (inte i länken).

    - En titel som slutar på ? eller ! får ingen extra punkt, även genom kursiv:
      'religion?.' och '*religion?*.' blir 'religion?' och '*religion?*'.
    - Dubbla punkter slås ihop ('etc..' blir 'etc.'), men en ellips ('...')
      i författarlistan lämnas orörd.
    """
    text = " ".join(text.split())
    text = re.sub(r"([?!])(\*?)\.", r"\1\2", text)
    text = re.sub(r"(?<!\.)\.(\*?)\.(?!\.)", r".\1", text)
    return text


def _split_names(raw):
    """Delar en BibTeX-namnlista vid ' and ' utanför klamrar, före avkodning.

    Klamrarna är det enda som skiljer ett kollektivt namn från en person, och
    LaTeX-avkodningen tar bort dem. Alla som behöver namnen ska gå via denna."""
    raw = raw or ""
    sep = re.compile(r"\s+and\s+")
    parts, depth, start, i = [], 0, 0, 0
    while i < len(raw):
        c = raw[i]
        if c == "\\":  # \{ och \} öppnar eller stänger ingen grupp
            i += 2
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth = max(depth - 1, 0)  # en lös } får inte stänga av delningen
        elif depth == 0:
            m = sep.match(raw, i)
            if m:
                parts.append(raw[start:i])
                i = start = m.end()
                continue
        i += 1
    parts.append(raw[start:])
    return [p.strip() for p in parts if p.strip()]


def _is_literal_name(name):
    """Sant om hela namnet är en enda klammergrupp: {Karlstads universitet, X}.

    '{von Neumann}, John' och '{A} {B}' är personnamn med klamrade delar."""
    if not (name.startswith("{") and name.endswith("}")):
        return False
    depth, i = 0, 0
    while i < len(name):
        c = name[i]
        if c == "\\":
            i += 2
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return i == len(name) - 1
        i += 1
    return False


def _unless_author(value, raw_author):
    """Tom sträng om utgivaren är samma som författaren (APA 7), annars värdet.

    Bara när författarledet är just den utgivaren: är den en av flera
    författare är utgivaren inte densamma som författaren, och står kvar."""
    names = _split_names(raw_author)

    def norm(text):
        return " ".join(text.split()).casefold()

    if len(names) == 1 and norm(safe_latex_to_text(names[0])) == norm(value):
        return ""
    return value


def _person_list(raw, given_first=False):
    """BibTeX-namnlista → APA-namn. Över 20 namn: 19, '...', sista.
    Ett helt klamrat namn är kollektivt och skrivs ut oförändrat."""
    names = []
    for name in _split_names(raw):
        a = safe_latex_to_text(name).strip()
        if _is_literal_name(name):
            names.append(a)
            continue
        parts = a.split(",")
        if len(parts) == 2:
            ln = parts[0].strip()
            initials = []
            for given in parts[1].split():
                # Bindestreckat förnamn: Hans-Günter → H.-G.
                sub = [g for g in given.split("-") if g]
                initials.append("-".join(f"{g[0].upper()}." for g in sub))
            init_str = " ".join(i for i in initials if i)
            if init_str:
                names.append(f"{init_str} {ln}" if given_first else f"{ln}, {init_str}")
            else:
                names.append(ln)
        else:
            names.append(a)
    if len(names) > 20:
        names = names[:19] + ["..."] + [names[-1]]
    return names


def _join_names(names, given_first=False):
    """APA 7: 'A, B., & C, D.' (komma före & även vid två namn i
    efternamn-först-form); förnamn-först (kapitelredaktörer): 'A. B & C. D'
    vid två, 'A, B, & C' vid fler. En ellips ersätter &."""
    if not names:
        return "Unknown"
    if len(names) == 1:
        return names[0]
    if names[-2] == "...":
        return ", ".join(names[:-1]) + " " + names[-1]
    if given_first and len(names) == 2:
        return f"{names[0]} & {names[1]}"
    return ", ".join(names[:-1]) + ", & " + names[-1]


def _thesis_label(entry, et):
    lab = _labels()
    typ = safe_latex_to_text(entry.get("type", "")).strip()
    if typ:
        key = THESIS_TYPE_KEYS.get(typ.lower().replace(" ", "").replace("'", ""))
        return lab[key] if key else typ[0].upper() + typ[1:]
    if et == "phdthesis":
        return lab["phd"]
    if et == "mastersthesis":
        return lab["master"]
    return lab["thesis"] if et == "thesis" else ""


def _thesis_institution(entry):
    """APA 7: lärosätet en gång. Fältet som ser ut som ett lärosäte vinner,
    annars institution före school före publisher."""
    cands = [safe_latex_to_text(entry.get(f, "")).strip()
             for f in ("institution", "school", "publisher")]
    cands = [c for c in cands if c]
    if not cands:
        return ""
    uni = re.compile(r"universit|högskola|hogskola|college|institute of technology|academy",
                     re.IGNORECASE)
    unit = re.compile(r"(fakultet|institution|department|faculty|school of|division|"
                      r"avdelning|enhet|centre|center|the study|studies)", re.IGNORECASE)

    def is_place(seg):
        # Campus/ort efter kommat ("University of California, Berkeley"):
        # kort och bara versala ord. En enhet som "The Study of Religions" eller
        # "Pedagogiskt arbete" har gemena ord och släpps.
        words = seg.split()
        return (0 < len(words) <= 3 and not unit.search(seg)
                and all(w[0].isupper() for w in words))

    for c in cands:
        # Ett fält kan bära "Lärosäte, Enhet"; ta lärosätet och en ev. ort,
        # inte enheten. "Fakulteten för …" är en enhet, inte lärosätet.
        segs = [x.strip() for x in c.split(",") if x.strip()]
        for i, seg in enumerate(segs):
            if uni.search(seg) and not unit.match(seg):
                kept = [seg]
                for nxt in segs[i + 1:]:
                    if not is_place(nxt):
                        break
                    kept.append(nxt)
                return ", ".join(kept)
    return cands[0]


# Författningar (@legislation). APA 7 saknar regler för lagstiftning utanför USA;
# formen följer Lunds universitetsbiblioteks APA 7-guide "Svenska lagar och
# förordningar" (uppdaterad 2026-05-21, vyasa LUB2026apa7lagar):
#   SFS ÅÅÅÅ:Nummer. *Titel*. URL
# Beteckningen står i författarens plats, inget årtal i parentes, ingen
# utgivare eller ort. Lydelsen (`version`) är bibbers tillägg, som guiden inte
# behandlar; formuleringen följer riksdagen.se:s "Ändrad: t.o.m. SFS …".
LEGISLATION_TYPES = {"legislation", "law"}


def _sfs(raw, series):
    """'2010:800' eller 'SFS 2010:800' -> 'SFS 2010:800' (prefix ur `series`)."""
    raw = safe_latex_to_text(raw or "").strip()
    if not raw:
        return ""
    if re.match(r"^\d", raw):
        return f"{series} {raw}"
    return raw


def _legislation_parts(entry):
    """(beteckning, titel, lydelse) för en @legislation-post."""
    series = safe_latex_to_text(entry.get("series", "")).strip() or "SFS"
    number = safe_latex_to_text(entry.get("number", "")).strip()
    designation = _sfs(number, series)
    if not designation and entry.get("author"):
        designation = _join_names(_person_list(entry["author"]))
    title = _join_title(entry.get("title", ""), entry.get("subtitle", ""))
    # Riksdagens titel bär numret ("Skollag (2010:800)"); APA-guiden utelämnar
    # det, eftersom det redan står i beteckningen. Bara exakt samma nummer tas bort.
    if number:
        bare = re.sub(r"^\D+\s*", "", number)
        title = re.sub(r"\s*\(" + re.escape(bare) + r"\)\s*$", "", title)
    version = _sfs(entry.get("version", ""), series)
    return designation, title, version


def generate_apa(entry, key=None):
    """
    APA 7-formatering (svenska eller engelska efter LANGUAGE).
      - Upp till 20 författare/redaktörer, därefter '...' och sista namnet.
      - @book med 'editor' när 'author' saknas: 'Efternamn, F. (Red.).'
      - title + subtitle med kolon och versal efter kolon; titleaddon i hakparentes
        efter titeln (efter upplagan för böcker).
      - Tidskrift: *Tidskrift*, *volym*(nummer), sidor. Utan volym: *Tidskrift*, (nummer).
      - Kapitel: I F. Efternamn (Red.), *Bok* (uppl., s. x–y). Förlag.
      - Avhandling: *Titel* [Doktorsavhandling, Lärosäte]. Fältet `type` styr etiketten.
      - Utgivningsort utelämnas (APA 7), liksom utgivare som är samma som författaren.
      - Författning (@legislation): SFS 2010:800. *Skollag* [ändrad t.o.m. SFS …]. URL
      - title_translation_<språk> för utskriftens språk i hakparentes direkt efter titeln.
      - DOI som https://doi.org/…, annars URL, sist.
    """
    if DEBUG_MODE:
        for fname, val in entry.items():
            print(f"[DEBUG] {fname} : {val}")
    lab = _labels()

    # 1) Författare, eller redaktörer om författare saknas
    raw_author = entry.get("author", "") or entry.get("editor", "")
    is_editor = bool(raw_author and not entry.get("author") and entry.get("editor"))
    names = _person_list(raw_author) if raw_author else ["Unknown"]
    authors_str = _join_names(names)
    if is_editor:
        n_ed = len(_split_names(raw_author))
        authors_str += f" ({lab['ed1'] if n_ed == 1 else lab['edn']})"
    if not authors_str.endswith("."):
        # APA: punkt efter författarledet även för organisationer ("Skolverket.")
        authors_str += "."

    # 2) År
    yr = entry.get("year", "") or entry.get("date", "")[:4] or lab["no_date"]

    # 3) Titel
    title = _join_title(entry.get("title", ""), entry.get("subtitle", "")) or "Untitled"
    addon = _titleaddon(entry)
    tr = _translation(entry, key)

    pp = _pages(entry.get("pages", ""))
    edition = _edition(entry.get("edition", ""))
    # Utgivaren gäller hela verket: i ett kapitel är det redaktören, inte
    # kapitlets författare, som står som verkets upphovsman.
    is_chapter = entry.get("entrytype", "").lower() in ("incollection", "inbook")
    work_author = (entry.get("editor") or raw_author) if is_chapter else raw_author
    pub = _unless_author(safe_latex_to_text(entry.get("publisher", "")).strip(), work_author)

    # 4) Länk
    doi = entry.get("doi", "").strip()
    url = entry.get("url", "").strip()
    if doi:
        if not doi.startswith("http"):
            doi = "https://doi.org/" + doi
        link = doi
    else:
        link = url
    urldate = entry.get("urldate", "").strip()

    et = entry.get("entrytype", "").lower()
    note = entry.get("note") or entry.get("annotate")
    note_str = f" [{safe_latex_to_text(note).strip()}]" if note else ""

    if et in LEGISLATION_TYPES:
        designation, ltitle, version = _legislation_parts(entry)
        body = f"{designation}. " if designation else ""
        body += f"*{ltitle or title}*{tr}{addon}"
        if version:
            body += " [" + lab["amended"].format(version=version) + "]"
        body = _tidy(body + "." + note_str)
        return _tidy_space(f"{body} {link}") if link else _tidy_space(body)

    body = f"{authors_str} ({yr}). "

    # ===== Avhandlingar =====
    # En @misc räknas som avhandling bara när fältet `type` ger en etikett;
    # annars är det t.ex. en lärarhandledning med institution och förlag.
    thesis_types = ("phdthesis", "mastersthesis", "thesis")
    misc_thesis = (et == "misc" and bool(entry.get("institution") or entry.get("school"))
                   and not entry.get("journal") and not entry.get("journaltitle")
                   and bool(entry.get("type", "").strip()))
    if et in thesis_types or misc_thesis:
        label = _thesis_label(entry, et)
        inst = _thesis_institution(entry)
        bracket = ", ".join(x for x in (label, inst) if x)
        if bracket:
            body += f"*{title}*{tr}{addon} [{bracket}]."
        else:
            body += f"*{title}*{tr}{addon}."
        out = _tidy(body + note_str)
        return f"{out} {link}" if link else out

    if et in ("incollection", "inbook"):
        raw_ed = entry.get("editor", "")
        bk = _join_title(entry.get("booktitle", ""), entry.get("booksubtitle", ""))
        body += f"{title}{tr}{addon}. "
        if bk:
            body += f"{lab['in']} "
            if raw_ed and raw_ed != raw_author:
                eds = _person_list(raw_ed, given_first=True)
                n_ed = len(_split_names(raw_ed))
                body += f"{_join_names(eds, given_first=True)} ({lab['ed1'] if n_ed == 1 else lab['edn']}), "
            body += f"*{bk}*"
            paren = [x for x in (edition, f"{_page_label(pp)} {pp}" if pp else "") if x]
            if paren:
                body += f" ({', '.join(paren)})"
            body += "."
        elif pp:
            body += f"{_page_label(pp)} {pp}."
        if pub:
            body += f" {pub}."
    elif et == "article":
        body += f"{title}{tr}{addon}. "
        j = safe_latex_to_text(entry.get("journaltitle", entry.get("journal", ""))).strip()
        vol = entry.get("volume", "").strip()
        num = entry.get("number", "").strip() or entry.get("issue", "").strip()
        if j:
            body += f"*{j}*"
            if vol:
                body += f", *{vol}*"
                if num:
                    body += f"({num})"
            elif num:
                body += f", ({num})"
            if pp:
                body += f", {pp}"
            body += "."
        elif pp:
            body += f"{pp}."
    elif et == "book":
        body += f"*{title}*{tr}"
        if edition:
            body += f" ({edition})"
        body += f"{addon}."
        if pub:
            body += f" {pub}."
    elif et in REPORT_TYPES:
        paren, desc = _report_designation(entry)
        body += f"*{title}*{tr}"
        if paren:
            body += f" ({paren})"
        body += addon
        if desc:
            body += f" [{desc}]"
        body += "."
        inst = _unless_author(
            safe_latex_to_text(entry.get("institution", "")).strip(), raw_author)
        # Utgivaren: institution (biblatex fält för rapporter) och/eller
        # publisher, utan dubbletter och inte om den är författaren.
        names = []
        for name in (inst, pub):
            if name and name not in names:
                names.append(name)
        if names:
            body += " " + ". ".join(names) + "."
        # Sidantalet stod med före den egna rapportgrenen och får stå kvar.
        if pp:
            body += f" {_page_label(pp)} {pp}."
    elif et == "inproceedings":
        bk = _join_title(entry.get("booktitle", ""), entry.get("booksubtitle", ""))
        howp = safe_latex_to_text(entry.get("howpublished", "")).strip()
        body += f"{title}{tr}{addon}."
        if bk:
            body += f" {lab['in']} *{bk}*"
            if pp:
                body += f" ({_page_label(pp)} {pp})"
            body += "."
        if howp:
            body += f" {howp}."
        if pub:
            body += f" {pub}."
    elif et in ("misc", "online", "electronic", "www"):
        body += f"*{title}*{tr}{addon}."
        inst = _unless_author(
            safe_latex_to_text(entry.get("institution", entry.get("organization", ""))).strip(),
            raw_author)
        series = safe_latex_to_text(entry.get("series", "")).strip()
        if inst:
            body += f" {inst}."
        if series:
            body += f" {series}."
        if pub and pub != inst:
            body += f" {pub}."
        if pp:
            body += f" {_page_label(pp)} {pp}."
    else:
        body += f"{title}{tr}{addon}."
        if pub:
            body += f" {pub}."
        if pp:
            body += f" {_page_label(pp)} {pp}."

    # Anmärkning före länken: länken står alltid sist
    body = _tidy(body + note_str)
    if link:
        return _tidy_space(f"{body} {link}")
    if urldate and url:
        return _tidy_space(f"{body} " + lab["retrieved"].format(date=urldate, url=url))
    return _tidy_space(body)


def _tidy_space(text):
    return " ".join(text.split())


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
        return generate_apa(entry, key)


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

    # Alias i fältet ids (biblatex: "An entry may be cited by any of its
    # aliases", Kime2024biblatex320 s. 30). Så fortsätter en gammal nyckel,
    # t.ex. en sammanslagen språkdubblett, att fungera.
    for key, entry in bib_data.items():
        aliases = [a.strip().lower() for a in entry.get("ids", "").split(",")]
        if key_lower in aliases:
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
    if t:
        t= t[0].upper()+ t[1:]
    else:
        t="Untitled"

    et= entry.get("entrytype","").lower()
    if et in LEGISLATION_TYPES:
        designation, ltitle, _ = _legislation_parts(entry)
        return f"{designation}. {ltitle or t}" if designation else (ltitle or t)
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
    out=[]
    for name in _split_names(raw):
        a= safe_latex_to_text(name)
        if _is_literal_name(name):
            out.append(a.strip())
            continue
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
    apa = generate_apa(bib_entry, key)

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
            apa = generate_apa(e, key)
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

# -------------------------------------------------
# 9) main
# -------------------------------------------------
def main():
    global LANGUAGE, DEBUG_MODE, VERBOSE_MODE, NO_TRANSLATION_ALL
    load_language_setting()
    args = parse_args()
    if args.lang:
        LANGUAGE = args.lang

    # Samla nycklar från -k och --keys, i given ordning
    keys = []
    for k in args.key or []:
        # -k tar flera värden och sväljer därför en efterföljande positionell
        # .bib-fil (bibber -k KEY fil.bib); lägg den tillbaka bland query.
        if k.lower().endswith(".bib") and os.path.isfile(os.path.expanduser(k)):
            args.query.append(os.path.expanduser(k))
        else:
            keys.append(k)
    if args.keys:
        try:
            if args.keys == "-":
                key_lines = sys.stdin.read().splitlines()
            else:
                with open(os.path.expanduser(args.keys)) as kf:
                    key_lines = kf.read().splitlines()
            for line in key_lines:
                line = line.split("#", 1)[0].strip()
                if line:
                    keys.extend(line.split())
        except OSError as e:
            if LANGUAGE == "sv":
                print(f"Kan inte läsa nyckelfil: {e}", file=sys.stderr)
            else:
                print(f"Cannot read key file: {e}", file=sys.stderr)
            sys.exit(1)
        if not keys:
            if LANGUAGE == "sv":
                print("Nyckelfilen innehöll inga nycklar.", file=sys.stderr)
            else:
                print("The key file contained no keys.", file=sys.stderr)
            sys.exit(1)
    args.key = keys or None

    # Översatta titlar: --no-translation stänger av alla, --no-translation-for en post.
    NO_TRANSLATION_ALL = args.no_translation
    NO_TRANSLATION_KEYS.update(k.lower() for k in args.no_translation_for or [])

    # Sätt globala flaggor
    DEBUG_MODE = args.debug
    VERBOSE_MODE = args.verbose

    # Bestäm bib-fil
    DEFAULT_BIB = default_bib_file()
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
            # En angiven standardfil som saknas är ett konfigurationsfel; utan
            # varning skulle den senast använda filen, kanske ett annat
            # bibliotek, tyst ta dess plats.
            if DEFAULT_BIB:
                if LANGUAGE == "sv":
                    print(f"Standardfilen finns inte: {DEFAULT_BIB}", file=sys.stderr)
                else:
                    print(f"Default file not found: {DEFAULT_BIB}", file=sys.stderr)
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

    # Auto-fallback: utan TTY skulle prompt_toolkit-TUI:n crasha i asyncio.run.
    if not sys.stdout.isatty() and not args.key and not args.one and args.num is None:
        if LANGUAGE == "sv":
            print("Icke-TTY detekterad; använder -n5. Ange -1 eller -n N för att tysta.",
                  file=sys.stderr)
        else:
            print("Non-TTY detected; using -n5. Pass -1 or -n N to silence.",
                  file=sys.stderr)
        args.num = 5

    # Icke-interaktivt läge: -k (key lookup)
    if args.key:
        if not bib_data:
            if LANGUAGE == "sv":
                print("Ingen data laddad.", file=sys.stderr)
            else:
                print("No data loaded.", file=sys.stderr)
            sys.exit(1)

        outputs = []
        missing = []
        for k in args.key:
            out = get_reference_by_key(k, args.format)
            if out:
                outputs.append(out)
            else:
                missing.append(k)
        if outputs:
            print("\n\n".join(outputs))
        for k in missing:
            if LANGUAGE == "sv":
                print(f"Hittade ingen referens med key '{k}'.", file=sys.stderr)
            else:
                print(f"No reference found with key '{k}'.", file=sys.stderr)
        sys.exit(1 if missing else 0)

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


if __name__ == "__main__":
    main()
