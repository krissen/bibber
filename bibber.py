#!/usr/bin/env python
# coding=utf-8
import collections
import collections.abc
import hashlib
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor

import biblib.algo
import biblib.bib
import biblib.messages
import pyperclip
from fuzzywuzzy import fuzz
from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from pylatexenc.latex2text import LatexNodes2Text

# -------------------------------------------------
# Globala
# -------------------------------------------------
collections.Iterable = collections.abc.Iterable

CACHE_DIR = os.path.expanduser("~/.cache/bibber/")
os.makedirs(CACHE_DIR, exist_ok=True)

HISTORY_FILE = os.path.join(CACHE_DIR, "history.txt")

DEBUG_MODE = ("--debug" in sys.argv)

bib_data = None
processed_entries_cache = None
last_shown_results = []

LANGUAGE = "en"
COMPACT_MAX_CHARS = 95  # hård max-längd i kompakt vy

# -------------------------------------------------
# Eget 'help'
# -------------------------------------------------
if "--help" in sys.argv:
    print("""
Usage:
  python bibber.py [options] [file.bib] [search terms]

Options:
  --debug      : debug-läge (mer utskrifter)
  --help       : denna hjälp

Interactive commands (English aliases):
  load <file>    : Load .bib
  search <terms> : Standard search
  sc <terms> [n] : Compact search
  copy <index>   : Copy reference
  lang <sv|en>   : Switch language
  help           : This help
  exit / quit    : Quit

Swedish aliases also available in interactive mode.
""")
    sys.exit(0)

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
        except:
            pass
    return None

def md5sum(file_path):
    with open(file_path,"rb") as fp:
        return hashlib.md5(fp.read()).hexdigest()

def load_from_cache(cache_file):
    try:
        with open(cache_file,"r") as f:
            return json.load(f)
    except:
        return None

def save_to_cache(data, cache_file):
    with open(cache_file,"w") as f:
        json.dump(data,f)

def safe_latex_to_text(x):
    try:
        return LatexNodes2Text().latex_to_text(x or "")
    except:
        return x or ""

def copy_to_clipboard(txt):
    try:
        pyperclip.copy(txt)
        print("Reference copied to clipboard.")
    except:
        pass

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
        except:
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
def extract_entrytypes(file_path):
    out={}
    with open(file_path,"r",encoding="utf-8") as fp:
        for line in fp:
            line=line.strip()
            if line.startswith("@") and "{" in line:
                et, rest=line[1:].split("{",1)
                key= rest.split(",",1)[0].strip()
                out[key.lower()] = et.lower()
    return out

def load_bibtex(file_path):
    global bib_data, processed_entries_cache
    file_path= os.path.expanduser(file_path)
    cfile= os.path.join(CACHE_DIR, md5sum(file_path)+".json")

    cached= load_from_cache(cfile)
    if cached:
        bib_data= cached
        if LANGUAGE=="sv":
            print(f"Laddar senast använda fil: {file_path}")
        else:
            print(f"Loading last used file: {file_path}")
        save_last_used_file(file_path)
    else:
        try:
            if LANGUAGE=="sv":
                print(f"Laddar fil: {file_path}")
            else:
                print(f"Loading file: {file_path}")
            with open(file_path,"r",encoding="utf-8") as bf:
                parser= biblib.bib.Parser()
                parsed_db= parser.parse(bf, log_fp=sys.stderr).get_entries()
                resolved= biblib.bib.resolve_crossrefs(parsed_db)
                bib_data=resolved

            etypes= extract_entrytypes(file_path)
            for k, e in bib_data.items():
                if e.get("entrytype","unknown")=="unknown":
                    e["entrytype"]= etypes.get(k.lower(),"unknown")

            save_to_cache(bib_data, cfile)
            save_last_used_file(file_path)
        except Exception as e:
            print("Error loading bib:", e)
            return
    processed_entries_cache=None

# -------------------------------------------------
# 4) En förenklad APA, tar hänsyn till LANGUAGE
# -------------------------------------------------
def generate_apa(entry):
    from pylatexenc.latex2text import LatexNodes2Text
    conv= LatexNodes2Text()

    if LANGUAGE=="sv":
        no_date="u.å."
        single_ed=" (red.)"
        multi_ed=" (red.)"
        pages_label="s."
        et_al="m.fl."
    else:
        no_date="n.d."
        single_ed=" (ed.)"
        multi_ed=" (eds.)"
        pages_label="pp."
        et_al="et al."

    raw_auth= entry.get("author","")
    is_editor=False
    if not raw_auth:
        raw_auth= entry.get("editor","Unknown Editor")
        is_editor=True
    auth_ltx= conv.latex_to_text(raw_auth)

    splitted= auth_ltx.split(" and ")
    authors=[]
    for a in splitted:
        parts=a.split(",")
        if len(parts)==2:
            ln= parts[0].strip()
            fn= parts[1].split()
            if fn:
                init= fn[0][0].upper()+"."
                authors.append(f"{ln}, {init}")
            else:
                authors.append(ln)
        else:
            authors.append(a.strip())

    if len(authors)>3:
        first=authors[0]
        authors=[first, et_al]

    if is_editor:
        if len(splitted)>1:
            authors[-1]+= multi_ed
        else:
            authors[-1]+= single_ed

    authors_str=", ".join(authors)

    yr= entry.get("year","")
    if not yr:
        dt= entry.get("date","")
        if dt: yr= dt[:4]
    if not yr:
        yr=no_date

    title= conv.latex_to_text(entry.get("title","Untitled")).strip()
    if title:
        title= title[0].upper()+ title[1:]
    else:
        title="Untitled"

    pp= entry.get("pages","").replace("--","–")
    if pp:
        if LANGUAGE=="sv":
            # s. 12–14
            pp=f"s. {pp}"
        else:
            # eng
            if "–" in pp:
                pp=f"{pages_label} {pp}"
            else:
                pp=f"p. {pp}"

    doi= entry.get("doi","")
    if doi and not doi.startswith("https://doi.org/"):
        doi="https://doi.org/"+doi

    et= entry.get("entrytype","").lower()
    loc= conv.latex_to_text(entry.get("location","")).strip()
    pub= conv.latex_to_text(entry.get("publisher","")).strip()

    apa=f"{authors_str} ({yr}). {title}."
    if et=="incollection":
        # bok
        bk= conv.latex_to_text(entry.get("booktitle","")).strip()
        eds_= entry.get("editor","")
        eds_ltx= conv.latex_to_text(eds_)
        splitted_ed= eds_ltx.split(" and ")
        # etc. (se tidigare implementation)

        if eds_ltx==auth_ltx:
            # Samma => skip
            if bk:
                apa+= f" In *{bk}*"
                if pp:
                    apa+= f" ({pp})"
            apa+="."
        else:
            if len(splitted_ed)==1:
                apa+= f" In {splitted_ed[0]}{single_ed}"
            elif len(splitted_ed)>1:
                joined=", ".join(splitted_ed)
                apa+= f" In {joined}{multi_ed}"
            if bk:
                apa+= f", *{bk}*"
            if pp:
                apa+= f" ({pp})"
            apa+="."

        if loc and pub:
            apa+= f" {loc}: {pub}."
        elif pub:
            apa+= f" {pub}."
        elif loc:
            apa+= f" {loc}."
    elif et=="article":
        j= conv.latex_to_text(entry.get("journaltitle", entry.get("journal",""))).strip()
        if j:
            apa+= f" *{j}*."
        if pp:
            apa+= f" {pp}."
        if loc and pub:
            apa+= f" {loc}: {pub}."
        elif pub:
            apa+= f" {pub}."
        elif loc:
            apa+= f" {loc}."
    elif et=="book":
        if loc and pub:
            apa+= f" {loc}: {pub}."
        elif pub:
            apa+= f" {pub}."
        elif loc:
            apa+= f" {loc}."
        if pp:
            apa+= f" {pp}."
    else:
        if loc and pub:
            apa+= f" {loc}: {pub}."
        elif pub:
            apa+= f" {pub}."
        elif loc:
            apa+= f" {loc}."
        if pp:
            apa+= f" {pp}."

    if doi:
        apa+= f" doi: {doi}"
    apa=" ".join(apa.split())
    return apa

# -------------------------------------------------
# 5) Standard-lång vy
# -------------------------------------------------
def build_standard_reference_short(entry):
    authors= parse_authors_for_compact(entry,semicolon=False)
    y= parse_year_4chars(entry)
    if y=="????":
        y="n.d."

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
    elif et=="phdthesis":
        source= "PhD Thesis at "+ safe_latex_to_text(entry.get("publisher",""))
    else:
        source= safe_latex_to_text(entry.get("journal", entry.get("booktitle",""))).strip()

    line= f"{authors} ({y}). {t}"
    if source:
        line+= f". {source}"
    return line

def search_entries(query):
    global last_shown_results
    if not bib_data:
        print("Ingen fil är laddad.")
        return

    qterms= [x.lower() for x in query.split() if x.lower()!="--debug"]
    scored= _search_and_score_entries(qterms)
    perfects= [s for s in scored if s["score"]>=100]
    if len(perfects)>5:
        if LANGUAGE=="sv":
            print(f"\nFler än 5 perfekta träffar ({len(perfects)}). Kompakt vy...\n")
        else:
            print(f"\nMore than 5 perfect matches ({len(perfects)}). Switching to compact view...\n")
        search_entries_compact(query,25)
        return

    last_shown_results= scored[:5]
    if LANGUAGE=="sv":
        print("\nSökresultat (standardvy, max 5):\n")
    else:
        print("\nSearch results (standard view, max 5):\n")

    for i, item in enumerate(last_shown_results):
        e= list(bib_data.values())[item["idx"]]
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
            if fn:
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
    global processed_entries_cache
    if processed_entries_cache is not None:
        return
    arr= list(bib_data.values())

    def combine(e):
        t= safe_latex_to_text(e.get("title",""))
        a= safe_latex_to_text(e.get("author", e.get("editor","Unknown")))
        j= safe_latex_to_text(e.get("journaltitle", e.get("journal", e.get("booktitle",""))))
        return f"{t} {a} {j}"

    with ThreadPoolExecutor() as ex:
        results= list(ex.map(combine, arr))
    processed_entries_cache= [(i, results[i].lower()) for i in range(len(arr))]

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


def _search_and_score_entries(qterms):
    _prepare_processed_entries()
    arr = list(bib_data.values())
    out = []

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

        authors_s = parse_authors_for_compact(arr[idx], semicolon=True)
        y_s = parse_year_4chars(arr[idx])
        ti = safe_latex_to_text(arr[idx].get("title", "Untitled")).strip()

        out.append({
            "idx": idx,
            "score": total,
            "authors": authors_s,
            "year": y_s,   # sträng, ex. "2024", "fort", "????"
            "title": ti
        })

    # Nu sorterar vi fallande på (score, year_int)
    out.sort(key=lambda x: (x["score"], _try_int_year(x["year"])), reverse=True)
    return out

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
    global last_shown_results
    if not bib_data:
        print("Ingen fil är laddad.")
        return
    qterms= [x.lower() for x in query.split() if x.lower()!="--debug"]

    scored= _search_and_score_entries(qterms)
    top= scored[:max_results]
    last_shown_results= top

    if LANGUAGE=="sv":
        print(f"\nSökresultat (kompakt vy, {max_results} rader):\n")
    else:
        print(f"\nSearch results (compact view, {max_results} rader):\n")

    for i, s in enumerate(top):
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
def _do_copy(index):
    if index<0 or index>= len(last_shown_results):
        print("Ogiltigt index.")
        return
    e= list(bib_data.values())[last_shown_results[index]["idx"]]
    apa= generate_apa(e)
    print(f"\n{apa}\n")
    copy_to_clipboard(apa)

def _print_help():
    print("""
Commands (English + Swedish):
  load <file> / ladda <fil>        : Load .bib
  search <terms> / sök <termer>    : Standard search
  sc <terms> [n] / sökc <termer> [antal] : Compact search
  copy <index> / kopiera <index>   : Copy reference
  lang <sv|en>                     : Switch language
  help / hjälp                     : This help
  exit / quit / avsluta            : Quit
""")

def interactive_shell():
    load_language_setting()
    session= PromptSession(history=FileHistory(HISTORY_FILE))

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

            if LANGUAGE=="sv":
                print("Okänt kommando. 'hjälp' för lista.")
            else:
                print("Unknown command. 'help' for list.")
        except (EOFError,KeyboardInterrupt):
            if LANGUAGE=="sv":
                print("\nAvslutar...\n")
            else:
                print("\nExiting...\n")
            break

# -------------------------------------------------
# 9) main
# -------------------------------------------------
if __name__=="__main__":
    load_language_setting()
    args= sys.argv[1:]
    bib_file= next((a for a in args if os.path.isfile(a)), None)
    query= " ".join(a for a in args if not os.path.isfile(a) and not a.startswith("--"))

    if not bib_file:
        bf= get_last_used_file()
        if bf:
            bib_file= bf
        else:
            if LANGUAGE=="sv":
                print("Ingen .bib fil specad och ingen senast använd fil funnen.")
            else:
                print("No .bib file specified and no last used file found.")

    if bib_file:
        load_bibtex(bib_file)

    if query and bib_data:
        search_entries(query)

    interactive_shell()

