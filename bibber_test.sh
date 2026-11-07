#!/usr/bin/env bash
# Testsvit för bibber.py: APA 7-formatering (sv/en), crossref-arv,
# flera nycklar (-k, --keys) och flera .bib-filer (-b).
#
# Användning: ./bibber_test.sh [sökväg/till/bibber.py]
# Tillstånd isoleras: BIBBER_CACHE_DIR pekar på en mktemp-katalog, så
# cache, lang.json och last_used_bibfile.json i ~/.cache/bibber rörs inte.
set -u

BIBBER="${1:-$(cd "$(dirname "$0")" && pwd)/bibber.py}"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
export BIBBER_CACHE_DIR="$TMP/cache"
mkdir -p "$BIBBER_CACHE_DIR"

PASS=0
FAIL=0

check() { # namn, förväntat, faktiskt
    if [ "$2" = "$3" ]; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        printf 'FAIL %s\n  väntat: %s\n  fick:   %s\n' "$1" "$2" "$3"
    fi
}

contains() { # namn, nål, höstack
    case "$3" in
        *"$2"*) PASS=$((PASS + 1)) ;;
        *) FAIL=$((FAIL + 1)); printf 'FAIL %s\n  saknar: %s\n  i:      %s\n' "$1" "$2" "$3" ;;
    esac
}

lacks() { # namn, nål, höstack
    case "$3" in
        *"$2"*) FAIL=$((FAIL + 1)); printf 'FAIL %s\n  ska sakna: %s\n  i:         %s\n' "$1" "$2" "$3" ;;
        *) PASS=$((PASS + 1)) ;;
    esac
}

cat > "$TMP/main.bib" <<'EOF'
@book{Bok2007,
  editor = {Bakker, Cok and Heimbrock, Hans-Günter},
  title = {Researching RE teachers},
  subtitle = {RE teachers as researchers},
  location = {Münster},
  publisher = {Waxmann},
  doi = {10.1000/bok},
  year = {2007}
}
@incollection{Kap2007,
  author = {Fancourt, Nigel},
  crossref = {Bok2007},
  title = {The dialogical teacher: should teachers express their commitments?},
  pages = {53-67},
  year = {2007}
}
@book{Red2011,
  editor = {Löfstedt, Malin},
  title = {Religionsdidaktik: mångfald, livsfrågor och etik i skolan},
  location = {Lund},
  publisher = {Studentlitteratur},
  edition = {2},
  year = {2011}
}
@incollection{Kap2011,
  author = {Hartman, Sven G.},
  crossref = {red2011},
  pages = {19--34},
  title = {Perspektiv på skolans religionsundervisning},
  year = {2011}
}
@phdthesis{Lic2015,
  author = {Karlsson, Anders},
  institution = {Karlstads universitet},
  school = {Fakulteten för humaniora och samhällsvetenskap, Pedagogiskt arbete},
  location = {Karlstad},
  title = {Vilket religionskunskapsämne? Ämneskonstruktioner i centrum},
  type = {Licentiatuppsats},
  year = {2015}
}
@phdthesis{Dr2021,
  author = {Jahnke, Fredrik},
  school = {Södertörn University, The Study of Religions},
  publisher = {Södertörns högskola},
  title = {Toleransens altare},
  year = {2021}
}
@phdthesis{Campus1999,
  author = {Campus, Carl},
  school = {University of California, Berkeley},
  title = {Om campus},
  year = {1999}
}
@phdthesis{Enhet2010,
  author = {Enhet, Eva},
  school = {Göteborgs universitet, Department of Literature, History of Ideas, and Religion},
  title = {Om enheter},
  year = {2010}
}
@book{Volym2,
  crossref = {Bok2007},
  volume = {2},
  year = {2008}
}
@misc{Handl2017,
  author = {Gunnarsson Payne, Jenny},
  institution = {Södertörn University, Ethnology},
  publisher = {Studentlitteratur},
  location = {Lund},
  title = {Tillämpad kulturteori: lärarhandledning},
  year = {2017}
}
@misc{Uppsats2022,
  author = {Rist, Marcus},
  school = {Uppsala universitet},
  type = {Kandidatuppsats},
  title = {Ett temporärt tempel},
  year = {2022}
}
@incollection{Datum2009,
  author = {Datum, Dan},
  crossref = {Bok2007},
  date = {2009-05-01},
  title = {Senare kapitel},
  year = {}
}
@inproceedings{Konf2025,
  author = {Reimers, Eva},
  booktitle = {Religionsvetarmötet 2025},
  pages = {3-9},
  title = {Mer eller mindre religion?},
  year = {2025}
}
@online{Webb2013,
  author = {Osbeck, Christina},
  organization = {Skolverket},
  title = {Olika didaktiker},
  note = {Arkiverad kopia},
  url = {https://example.org/a},
  urldate = {2021-01-20},
  year = {2013}
}
@article{Utanvol2018,
  author = {Niemi, Kristian},
  journal = {Nordidactica},
  number = {2},
  pages = {1–22},
  title = {Religionsvetenskapliga tröskelbegrepp},
  year = {2018}
}
@article{Amp2026,
  author = {Jahnke, Fredrik},
  journal = {Religion \& Livsfrågor},
  volume = {58},
  number = {2},
  pages = {4--6},
  title = {En ämnesplan blir till},
  subtitle = {om arbetet med Gy25},
  year = {2026}
}
@article{Fraga2016,
  author = {Dalevi, Sören and Niemi, Kristian},
  journal = {Usuteaduslik Ajakiri},
  volume = {69},
  number = {1},
  pages = {62--78},
  title = {RE didactics in Sweden -- defined by the national curriculum?},
  subtitle = {discussing didactics of RE},
  year = {2016}
}
@book{Org2025,
  author = {{Skolverket}},
  title = {Ämnesplan i religionskunskap},
  publisher = {Skolverket},
  location = {Stockholm},
  year = {2025}
}
@book{Delad2000,
  author = {Huvud, Anna},
  title = {Från huvudfilen},
  publisher = {Förlag},
  year = {2000}
}
EOF

cat > "$TMP/lokal.bib" <<'EOF'
@book{Delad2000,
  author = {Huvud, Anna},
  title = {Från lokala filen},
  publisher = {Förlag},
  year = {2000}
}
@incollection{LokalKap,
  author = {Lokal, Lena},
  crossref = {Bok2007},
  title = {Lokalt kapitel},
  pages = {1-2},
  year = {2007}
}
EOF

run() { "$BIBBER" -b "$TMP/main.bib" "$@" 2>/dev/null; }

# --- Kapitel med crossref: arv, ort bort, redaktörer förnamn först, tankstreck
out="$(run --lang sv -k Kap2007)"
check "kapitel sv" \
    "Fancourt, N. (2007). The dialogical teacher: Should teachers express their commitments? I C. Bakker & H.-G. Heimbrock (Red.), *Researching RE teachers: RE teachers as researchers* (s. 53–67). Waxmann." \
    "$out"
lacks "kapitel ärver inte bokens DOI" "doi.org" "$out"
lacks "ingen ort" "Münster" "$out"

out="$(run --lang en -k Kap2007)"
contains "kapitel en" "In C. Bakker & H.-G. Heimbrock (Eds.), *Researching RE teachers: RE teachers as researchers* (pp. 53–67). Waxmann." "$out"

# --- crossref skiftlägesokänslig, upplaga i samma parentes som sidor
out="$(run --lang sv -k Kap2011)"
check "kapitel med upplaga" \
    "Hartman, S. G. (2011). Perspektiv på skolans religionsundervisning. I M. Löfstedt (Red.), *Religionsdidaktik: Mångfald, livsfrågor och etik i skolan* (2 uppl., s. 19–34). Studentlitteratur." \
    "$out"

# --- Bok som crossrefar en bok ärver titeln, flyttar den inte till booktitle
out="$(run --lang sv -k Volym2)"
contains "bok-till-bok ärver titel" "*Researching RE teachers: RE teachers as researchers*" "$out"
lacks "bok-till-bok inte Untitled" "Untitled" "$out"

# --- Redaktör som författare, versal efter kolon, ingen ort
out="$(run --lang sv -k Red2011)"
check "redigerad bok" \
    "Löfstedt, M. (Red.). (2011). *Religionsdidaktik: Mångfald, livsfrågor och etik i skolan* (2 uppl.). Studentlitteratur." \
    "$out"
out="$(run --lang en -k Red2011)"
contains "redigerad bok en" "Löfstedt, M. (Ed.). (2011)." "$out"
contains "upplaga en" "(2nd ed.)" "$out"

# --- Avhandling: type styr, lärosätet en gång, ?-titel utan extra punkt
out="$(run --lang sv -k Lic2015)"
check "licentiatuppsats" \
    "Karlsson, A. (2015). *Vilket religionskunskapsämne? Ämneskonstruktioner i centrum* [Licentiatuppsats, Karlstads universitet]." \
    "$out"
out="$(run --lang sv -k Dr2021)"
check "doktorsavhandling, lärosäte ur kommafält" \
    "Jahnke, F. (2021). *Toleransens altare* [Doktorsavhandling, Södertörn University]." \
    "$out"
out="$(run --lang en -k Dr2021)"
contains "doktorsavhandling en" "[Doctoral dissertation, Södertörn University]" "$out"

out="$(run --lang en -k Campus1999)"
contains "campus behålls" "[Doctoral dissertation, University of California, Berkeley]" "$out"
out="$(run --lang sv -k Enhet2010)"
contains "enhet släpps" "[Doktorsavhandling, Göteborgs universitet]." "$out"

# --- @misc med lärosäte men utan type är ingen avhandling; förlaget står kvar
out="$(run --lang sv -k Handl2017)"
check "misc utan type" \
    "Gunnarsson Payne, J. (2017). *Tillämpad kulturteori: Lärarhandledning*. Södertörn University, Ethnology. Studentlitteratur." \
    "$out"
out="$(run --lang sv -k Uppsats2022)"
check "misc med type" "Rist, M. (2022). *Ett temporärt tempel* [Kandidatuppsats, Uppsala universitet]." "$out"

# --- Barnets date skuggas inte av förälderns year
out="$(run --lang sv -k Datum2009)"
contains "barnets datum" "Datum, D. (2009)." "$out"

# --- inproceedings, ?-titel utan extra punkt
out="$(run --lang sv -k Konf2025)"
check "inproceedings" "Reimers, E. (2025). Mer eller mindre religion? I *Religionsvetarmötet 2025* (s. 3–9)." "$out"

# --- online: anmärkning före länken, länken sist
out="$(run --lang sv -k Webb2013)"
check "online" "Osbeck, C. (2013). *Olika didaktiker*. Skolverket. [Arkiverad kopia] https://example.org/a" "$out"

# --- Tidskrift utan volym
out="$(run --lang sv -k Utanvol2018)"
check "tidskrift utan volym" \
    "Niemi, K. (2018). Religionsvetenskapliga tröskelbegrepp. *Nordidactica*, (2), 1–22." \
    "$out"

# --- \& avkodas, subtitle, versal efter kolon
out="$(run --lang sv -k Amp2026)"
check "ampersand och undertitel" \
    "Jahnke, F. (2026). En ämnesplan blir till: Om arbetet med Gy25. *Religion & Livsfrågor*, *58*(2), 4–6." \
    "$out"

# --- Titel som slutar på ? följs av undertitel utan kolon; två författare med komma före &
out="$(run --lang sv -k Fraga2016)"
check "frågetitel med undertitel" \
    "Dalevi, S., & Niemi, K. (2016). RE didactics in Sweden – defined by the national curriculum? Discussing didactics of RE. *Usuteaduslik Ajakiri*, *69*(1), 62–78." \
    "$out"

# --- Organisation som författare får punkt
out="$(run --lang sv -k Org2025)"
check "organisation" "Skolverket. (2025). *Ämnesplan i religionskunskap*. Skolverket." "$out"

# --- Flera nycklar: given ordning, ett stycke per referens
out="$(run --lang sv -k Org2025 Utanvol2018)"
expected="$(printf '%s\n\n%s' \
    "Skolverket. (2025). *Ämnesplan i religionskunskap*. Skolverket." \
    "Niemi, K. (2018). Religionsvetenskapliga tröskelbegrepp. *Nordidactica*, (2), 1–22.")"
check "flera -k i ordning" "$expected" "$out"

# --- Saknad nyckel: övriga skrivs, exit 1, varning på stderr
"$BIBBER" -b "$TMP/main.bib" --lang sv -k Org2025 Finnsinte >"$TMP/o" 2>"$TMP/e"
rc=$?
check "saknad nyckel exit" "1" "$rc"
check "saknad nyckel stdout" "Skolverket. (2025). *Ämnesplan i religionskunskap*. Skolverket." "$(cat "$TMP/o")"
contains "saknad nyckel stderr" "Finnsinte" "$(cat "$TMP/e")"

# --- --keys: fil med kommentarer och tomma rader; '-' läser stdin
printf '# litteraturlista\nUtanvol2018\n\nOrg2025  # organisation\n' > "$TMP/keys.txt"
out="$(run --lang sv --keys "$TMP/keys.txt")"
expected="$(printf '%s\n\n%s' \
    "Niemi, K. (2018). Religionsvetenskapliga tröskelbegrepp. *Nordidactica*, (2), 1–22." \
    "Skolverket. (2025). *Ämnesplan i religionskunskap*. Skolverket.")"
check "--keys fil" "$expected" "$out"
out="$(printf 'Org2025\n' | "$BIBBER" -b "$TMP/main.bib" --lang sv --keys - 2>/dev/null)"
check "--keys stdin" "Skolverket. (2025). *Ämnesplan i religionskunskap*. Skolverket." "$out"

# --- Flera -b: första filen vinner, crossref över filgränsen
out="$("$BIBBER" -b "$TMP/lokal.bib" -b "$TMP/main.bib" --lang sv -k Delad2000 2>/dev/null)"
contains "lokal fil vinner" "Från lokala filen" "$out"
out="$("$BIBBER" -b "$TMP/main.bib" -b "$TMP/lokal.bib" --lang sv -k Delad2000 2>/dev/null)"
contains "ordningen styr" "Från huvudfilen" "$out"
out="$("$BIBBER" -b "$TMP/lokal.bib" -b "$TMP/main.bib" --lang sv -k LokalKap 2>/dev/null)"
contains "crossref över filer" "I C. Bakker & H.-G. Heimbrock (Red.), *Researching RE teachers: RE teachers as researchers* (s. 1–2). Waxmann." "$out"

# --- Positionell .bib-fil efter -k sväljs inte som nyckel
out="$("$BIBBER" --lang sv -k Org2025 "$TMP/main.bib" 2>/dev/null)"
check "-k KEY fil.bib" "Skolverket. (2025). *Ämnesplan i religionskunskap*. Skolverket." "$out"

# --- Sökning -n1 ger APA-referens
out="$(run --lang sv -n1 Toleransens altare)"
contains "-n1 sökning" "*Toleransens altare* [Doktorsavhandling, Södertörn University]." "$out"

# --- --lang sparas inte
check "--lang sparas inte" "no" "$([ -e "$BIBBER_CACHE_DIR/lang.json" ] && echo yes || echo no)"

# --- -f bib orörd av APA-ändringarna
out="$(run -f bib -k Amp2026)"
contains "bib-format" 'journal = {Religion \& Livsfrågor},' "$out"

printf 'PASS=%d FAIL=%d\n' "$PASS" "$FAIL"
[ "$FAIL" -eq 0 ]
