#!/usr/bin/env bash
# Testsvit för bibber.py: APA 7-formatering (sv/en), crossref-arv, författningar, titleaddon,
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
@book{Volym2026,
  editor = {Aschim, Anders},
  title = {Minorities, migration, and religion},
  publisher = {Waxmann},
  series = {Religious diversity and education in Europe},
  edition = {3},
  note = {Open access, CC BY-NC 4.0},
  addendum = {Bokens tillägg},
  isbn = {978-3-8188-0139-7},
  rights = {CC BY-NC 4.0},
  year = {2026}
}
@incollection{KapUtanNote,
  author = {Schweitzer, Friedrich},
  crossref = {Volym2026},
  title = {Conclusions},
  pages = {357-379}
}
@incollection{KapMedNote,
  author = {Schweitzer, Friedrich},
  crossref = {Volym2026},
  title = {Introduction},
  note = {Kapitlets egen anmärkning},
  pages = {1-5}
}
@book{Mono1986,
  author = {Hartman, Sven G.},
  title = {Barns tankar om livet},
  publisher = {Natur och Kultur},
  note = {Bokens not},
  year = {1986}
}
@inbook{Mono1986kap3,
  crossref = {Mono1986},
  title = {Livsfrågor},
  pages = {40-60}
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
@www{KollKomma,
  author = {{Karlstads universitet, rektorsbeslut}},
  organization = {Karlstads universitet},
  title = {Examensordning},
  year = {2021}
}
@www{KollUtgivare,
  author = {{Karlstads universitet}},
  organization = {Karlstads universitet},
  title = {Examensordning},
  url = {https://example.org/e},
  year = {2021}
}
@www{KollAnnanOrg,
  author = {{Karlstads universitet}},
  organization = {Skolverket},
  title = {Examensordning},
  year = {2021}
}
@misc{KollInst,
  author = {{Skolverket}},
  institution = {Skolverket},
  title = {Rapport},
  year = {2020}
}
@misc{KollMiscUtgivare,
  author = {{Skolverket}},
  publisher = {Skolverket},
  title = {Rapport},
  year = {2020}
}
@book{KollBokAnnan,
  author = {{Skolverket}},
  publisher = {Norstedts},
  title = {Bok},
  year = {2020}
}
@book{KollSkiftlage,
  author = {{Skolverket}},
  publisher = {SKOLVERKET},
  title = {Bok},
  year = {2020}
}
@book{KollOinklamrad,
  author = {Skolverket},
  publisher = {Skolverket},
  title = {Bok},
  year = {2020}
}
@book{KollOch,
  author = {{Svenska kyrkan and Skolverket}},
  publisher = {Verbum},
  title = {Bok},
  year = {2020}
}
@book{KollFlera,
  author = {Niemi, Kristian and {Karlstads universitet, rektorsbeslut} and Hartman, Sven G.},
  publisher = {Karlstads universitet},
  title = {Bok},
  year = {2020}
}
@book{KollPerson,
  author = {Efternamn, Förnamn},
  publisher = {Efternamn, Förnamn},
  title = {Bok},
  year = {2020}
}
@book{KollDelklamrad,
  author = {{von Neumann}, John},
  publisher = {Förlag},
  title = {Bok},
  year = {2020}
}
@book{KollRed,
  editor = {{Skolverket, enheten} and {Karlstads universitet}},
  publisher = {Skolverket, enheten},
  title = {Antologi},
  year = {2020}
}
@book{KollEnRed,
  editor = {{Skolverket}},
  publisher = {Skolverket},
  title = {Antologi},
  year = {2020}
}
@incollection{KollKap,
  author = {{Skolverket}},
  editor = {{Karlstads universitet, rektorsbeslut} and Niemi, Kristian},
  booktitle = {Antologi},
  publisher = {Skolverket},
  title = {Kapitel},
  year = {2020}
}
@incollection{KollKapRedUtg,
  author = {Niemi, Kristian},
  editor = {{Skolverket}},
  booktitle = {Antologi},
  publisher = {Skolverket},
  title = {Kapitel},
  year = {2020}
}
@inbook{KollInbook,
  author = {{Skolverket}},
  booktitle = {Antologi},
  publisher = {Skolverket},
  title = {Kapitel},
  year = {2020}
}
@inproceedings{KollKonf,
  author = {{Skolverket}},
  booktitle = {Konferens},
  publisher = {Skolverket},
  title = {Bidrag},
  year = {2020}
}
@techreport{KollRapport,
  author = {{Skolverket}},
  publisher = {Skolverket},
  title = {Rapport},
  year = {2020}
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

# --- Kapitel ärver inte bokens note/addendum/isbn, men väl år, redaktör, förlag, upplaga
out="$(run --lang sv -k KapUtanNote)"
check "kapitel utan egen note" \
    "Schweitzer, F. (2026). Conclusions. I A. Aschim (Red.), *Minorities, migration, and religion* (3 uppl., s. 357–379). Waxmann." \
    "$out"
out="$(run --lang sv -k KapMedNote)"
contains "kapitlets egen note" "[Kapitlets egen anmärkning]" "$out"
lacks "inte bokens note" "Open access" "$out"
out="$(run -f bib -k KapUtanNote)"
lacks "isbn ärvs inte" "isbn" "$out"
lacks "rights ärvs inte" "rights" "$out"
contains "series ärvs" "series = {Religious diversity and education in Europe}" "$out"

# --- @inbook i en monografi ärver bokens författare, inte dess not
out="$(run --lang sv -k Mono1986kap3)"
check "inbook ärver författare" \
    "Hartman, S. G. (1986). Livsfrågor. I *Barns tankar om livet* (s. 40–60). Natur och Kultur." \
    "$out"

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
check "organisation" "Skolverket. (2025). *Ämnesplan i religionskunskap*." "$out"

# --- Flera nycklar: given ordning, ett stycke per referens
out="$(run --lang sv -k Org2025 Utanvol2018)"
expected="$(printf '%s\n\n%s' \
    "Skolverket. (2025). *Ämnesplan i religionskunskap*." \
    "Niemi, K. (2018). Religionsvetenskapliga tröskelbegrepp. *Nordidactica*, (2), 1–22.")"
check "flera -k i ordning" "$expected" "$out"

# --- Saknad nyckel: övriga skrivs, exit 1, varning på stderr
"$BIBBER" -b "$TMP/main.bib" --lang sv -k Org2025 Finnsinte >"$TMP/o" 2>"$TMP/e"
rc=$?
check "saknad nyckel exit" "1" "$rc"
check "saknad nyckel stdout" "Skolverket. (2025). *Ämnesplan i religionskunskap*." "$(cat "$TMP/o")"
contains "saknad nyckel stderr" "Finnsinte" "$(cat "$TMP/e")"

# --- --keys: fil med kommentarer och tomma rader; '-' läser stdin
printf '# litteraturlista\nUtanvol2018\n\nOrg2025  # organisation\n' > "$TMP/keys.txt"
out="$(run --lang sv --keys "$TMP/keys.txt")"
expected="$(printf '%s\n\n%s' \
    "Niemi, K. (2018). Religionsvetenskapliga tröskelbegrepp. *Nordidactica*, (2), 1–22." \
    "Skolverket. (2025). *Ämnesplan i religionskunskap*.")"
check "--keys fil" "$expected" "$out"
out="$(printf 'Org2025\n' | "$BIBBER" -b "$TMP/main.bib" --lang sv --keys - 2>/dev/null)"
check "--keys stdin" "Skolverket. (2025). *Ämnesplan i religionskunskap*." "$out"

# --- Flera -b: första filen vinner, crossref över filgränsen
out="$("$BIBBER" -b "$TMP/lokal.bib" -b "$TMP/main.bib" --lang sv -k Delad2000 2>/dev/null)"
contains "lokal fil vinner" "Från lokala filen" "$out"
out="$("$BIBBER" -b "$TMP/main.bib" -b "$TMP/lokal.bib" --lang sv -k Delad2000 2>/dev/null)"
contains "ordningen styr" "Från huvudfilen" "$out"
out="$("$BIBBER" -b "$TMP/lokal.bib" -b "$TMP/main.bib" --lang sv -k LokalKap 2>/dev/null)"
contains "crossref över filer" "I C. Bakker & H.-G. Heimbrock (Red.), *Researching RE teachers: RE teachers as researchers* (s. 1–2). Waxmann." "$out"

# --- Positionell .bib-fil efter -k sväljs inte som nyckel
out="$("$BIBBER" --lang sv -k Org2025 "$TMP/main.bib" 2>/dev/null)"
check "-k KEY fil.bib" "Skolverket. (2025). *Ämnesplan i religionskunskap*." "$out"

# --- Sökning -n1 ger APA-referens
out="$(run --lang sv -n1 Toleransens altare)"
contains "-n1 sökning" "*Toleransens altare* [Doktorsavhandling, Södertörn University]." "$out"

# --- Cachen följer skriptet: en ändrad kopia av bibber.py läser inte den gamla cachen
# (egen cachekatalog, så att gallringen inte påverkar räkningen)
mkdir -p "$TMP/cache-script"
cp "$BIBBER" "$TMP/bibber_copy.py"
BIBBER_CACHE_DIR="$TMP/cache-script" "$TMP/bibber_copy.py" -b "$TMP/main.bib" -k Org2025 >/dev/null 2>&1
printf '\n# ändrad\n' >> "$TMP/bibber_copy.py"
BIBBER_CACHE_DIR="$TMP/cache-script" "$TMP/bibber_copy.py" -b "$TMP/main.bib" -k Org2025 >/dev/null 2>&1
n="$(ls "$TMP/cache-script" | grep -cE '^[0-9a-f]{32}\.json$')"
check "ny cache när skriptet ändras" "2" "$n"

# --- Gallring: högst fem cachefiler, lang/last_used står kvar
for i in 1 2 3 4 5 6 7; do
    printf '@book{G%s, title = {T}, year = {2000}}\n' "$i" > "$TMP/g$i.bib"
    "$BIBBER" -b "$TMP/g$i.bib" -k "G$i" >/dev/null 2>&1
done
n="$(ls "$BIBBER_CACHE_DIR" | grep -cE '^[0-9a-f]{32}\.json$')"
check "cache gallras till fem" "5" "$n"
check "last_used står kvar" "yes" "$([ -e "$BIBBER_CACHE_DIR/last_used_bibfile.json" ] && echo yes || echo no)"

# --- --lang sparas inte
check "--lang sparas inte" "no" "$([ -e "$BIBBER_CACHE_DIR/lang.json" ] && echo yes || echo no)"

# --- -f bib orörd av APA-ändringarna
out="$(run -f bib -k Amp2026)"
contains "bib-format" 'journal = {Religion \& Livsfrågor},' "$out"

# --- Kollektiv författare: ett klamrat namn delas inte och initialförkortas inte
out="$(run --lang sv -k KollKomma)"
check "klamrat namn med komma" \
    "Karlstads universitet, rektorsbeslut. (2021). *Examensordning*. Karlstads universitet." \
    "$out"
out="$(run --lang sv -k KollOch)"
check "klamrat namn med and" "Svenska kyrkan and Skolverket. (2020). *Bok*. Verbum." "$out"
out="$(run --lang sv -k KollFlera)"
check "kollektiv bland personer" \
    "Niemi, K., Karlstads universitet, rektorsbeslut, & Hartman, S. G. (2020). *Bok*. Karlstads universitet." \
    "$out"
out="$(run --lang sv -k KollDelklamrad)"
contains "delklamrad person" "von Neumann, J. (2020)." "$out"
out="$(run --lang sv -k Utanvol2018)"
contains "person med komma" "Niemi, K. (2018)." "$out"

# --- Antal redaktörer räknas med klamrarna i behåll
out="$(run --lang sv -k KollRed)"
check "kollektiva redaktörer" \
    "Skolverket, enheten, & Karlstads universitet (Red.). (2020). *Antologi*. Skolverket, enheten." \
    "$out"
out="$(run --lang sv -k KollKap)"
check "kollektiv kapitelredaktör, utgivaren står kvar" \
    "Skolverket. (2020). Kapitel. I Karlstads universitet, rektorsbeslut & K. Niemi (Red.), *Antologi*. Skolverket." \
    "$out"
out="$(run --lang sv -k KollKapRedUtg)"
check "kapitel: redaktör = utgivare" \
    "Niemi, K. (2020). Kapitel. I Skolverket (Red.), *Antologi*." "$out"
out="$(run --lang sv -k KollInbook)"
check "inbook utan redaktör: författare = utgivare" \
    "Skolverket. (2020). Kapitel. I *Antologi*." "$out"

# --- Utgivaren utelämnas när den är författaren, i alla grenar som skriver ut den
out="$(run --lang sv -k KollUtgivare)"
check "organization = författare" \
    "Karlstads universitet. (2021). *Examensordning*. https://example.org/e" "$out"
out="$(run --lang sv -k KollAnnanOrg)"
check "organization ≠ författare" \
    "Karlstads universitet. (2021). *Examensordning*. Skolverket." "$out"
out="$(run --lang sv -k KollInst)"
check "institution = författare" "Skolverket. (2020). *Rapport*." "$out"
out="$(run --lang sv -k KollMiscUtgivare)"
check "misc publisher = författare" "Skolverket. (2020). *Rapport*." "$out"
out="$(run --lang sv -k KollBokAnnan)"
check "publisher ≠ författare" "Skolverket. (2020). *Bok*. Norstedts." "$out"
out="$(run --lang sv -k KollSkiftlage)"
check "jämförelsen skiftlägesokänslig" "Skolverket. (2020). *Bok*." "$out"
out="$(run --lang sv -k KollOinklamrad)"
check "oklamrad organisation = utgivare" "Skolverket. (2020). *Bok*." "$out"
out="$(run --lang sv -k KollEnRed)"
check "redaktör = utgivare" "Skolverket (Red.). (2020). *Antologi*." "$out"
out="$(run --lang sv -k KollKonf)"
check "inproceedings utgivare = författare" "Skolverket. (2020). Bidrag. I *Konferens*." "$out"
out="$(run --lang sv -k KollRapport)"
check "övrig typ utgivare = författare" "Skolverket. (2020). Rapport." "$out"
out="$(run --lang sv -k KollPerson)"
contains "person lika med utgivare: Efternamn, F." "Efternamn, F. (2020). *Bok*." "$out"

# --- Listvyns kortform använder samma namnuppdelning (ingen CLI-väg utan TUI)
out="$("$(head -1 "$BIBBER" | cut -c3-)" - "$BIBBER" <<'PY'
import importlib.machinery, importlib.util, sys
loader = importlib.machinery.SourceFileLoader("bibber", sys.argv[1])
spec = importlib.util.spec_from_loader("bibber", loader)
m = importlib.util.module_from_spec(spec)
loader.exec_module(m)
print(m.parse_authors_for_compact({"author": "{Karlstads universitet, rektorsbeslut} and Niemi, Kristian"}))
print(m._split_names("Foo} and Bar, Baz"))
PY
)"
check "kortform" "$(printf '%s\n%s' "Karlstads universitet, rektorsbeslut; Niemi K" "['Foo}', 'Bar, Baz']")" "$out"

# --- @article med crossref till @periodical: tidskriftsnamn, bara vitlistade fält
cat > "$TMP/period.bib" <<'EOF2'
@periodical{Nr2016,
  title = {Tidskrift för läraryrket},
  subtitle = {Undertitel för numret},
  year = {2016},
  volume = {5},
  number = {2},
  issn = {1234-5678},
  editor = {Åkesson, Östen},
  note = {Anmärkning om numret},
  series = {Serie},
  publisher = {Förlaget},
  keywords = {nyckelord},
  doi = {10.1000/nummer},
  file = {:nr.pdf:PDF},
  pdfpageoffset = {7}
}
@article{BidragA2016,
  author = {Öberg, Åsa},
  title = {Räkna på lärare},
  pages = {12-34},
  crossref = {Nr2016}
}
@article{BidragB2016,
  author = {Ström, Ärlig},
  title = {Skriva för skolan},
  pages = {35-50},
  crossref = {Nr2016}
}
@article{Annat2016,
  author = {Öberg, Åsa},
  title = {Artikel i bok},
  pages = {1-2},
  crossref = {Bok2007}
}
@article{EgenJournal,
  author = {Öberg, Åsa},
  title = {Med eget journal},
  journal = {Egen tidskrift},
  pages = {1-2},
  crossref = {Nr2016}
}
@article{EgenJournaltitle,
  author = {Öberg, Åsa},
  title = {Med eget journaltitle},
  journaltitle = {Egen tidskrift 2},
  pages = {3-4},
  crossref = {Nr2016}
}
EOF2
prun() { "$BIBBER" -b "$TMP/period.bib" -b "$TMP/main.bib" "$@" 2>/dev/null; }
out="$(prun --lang sv -k BidragA2016)"
check "artikel i periodical sv" \
    "Öberg, Å. (2016). Räkna på lärare. *Tidskrift för läraryrket*, *5*(2), 12–34." \
    "$out"
out="$(prun --lang sv -k BidragB2016)"
check "artikel i periodical nr 2" \
    "Ström, Ä. (2016). Skriva för skolan. *Tidskrift för läraryrket*, *5*(2), 35–50." \
    "$out"
out="$(prun --lang sv -k BidragA2016)"
lacks "ingen redaktör" "Red." "$out"
lacks "ingen note" "Anmärkning" "$out"
lacks "ingen doi" "doi.org" "$out"
out="$(prun -f bib -k BidragA2016)"
contains "bib: journaltitle" "journaltitle = {Tidskrift för läraryrket}" "$out"
for f in editor note series publisher keywords doi file pdfpageoffset; do
    lacks "bib: $f ärvs inte" "$f =" "$out"
done
out="$(prun -f bib -k EgenJournal)"
contains "eget journal behålls" "journal = {Egen tidskrift}" "$out"
lacks "eget journal: ingen journaltitle från numret" "journaltitle" "$out"
lacks "eget journal: ingen journalsubtitle" "journalsubtitle" "$out"
out="$(prun --lang sv -k EgenJournal)"
contains "eget journal i apa" "*Egen tidskrift*, *5*(2), 1–2." "$out"
lacks "eget journal: numrets namn syns inte" "läraryrket" "$out"
out="$(prun -f bib -k EgenJournaltitle)"
contains "eget journaltitle behålls" "journaltitle = {Egen tidskrift 2}" "$out"
lacks "eget journaltitle: inget journal från numret" "journal = " "$out"
out="$(prun --lang sv -k EgenJournaltitle)"
contains "eget journaltitle i apa" "*Egen tidskrift 2*, *5*(2), 3–4." "$out"
out="$(prun -f bib -k BidragA2016)"
contains "utan eget: journalsubtitle ärvs" "journalsubtitle = {Undertitel för numret}" "$out"
out="$(prun --lang sv -k Annat2016)"
lacks "article->book oförändrad: ingen journaltitle" "Tidskrift" "$out"
out="$(prun -f bib -k Annat2016)"
lacks "article->book: ingen journaltitle" "journaltitle" "$out"
contains "article->book: ärver som förut (publisher)" "publisher = {Waxmann}" "$out"

# --- @legislation: Lunds APA 7-guide, "SFS ÅÅÅÅ:Nummer. *Titel*. URL"
cat > "$TMP/lag.bib" <<'BIB'
@legislation{Skollag, number = {2010:800}, title = {Skollag}, version = {2026:1636},
  institution = {Utbildningsdepartementet}, year = {2010}, location = {Stockholm},
  url = {https://www.riksdagen.se/sv/dokument-och-lagar/dokument/svensk-forfattningssamling/skollag-2010800_sfs-2010-800/}}
@legislation{HF, number = {SFS 1993:100}, title = {Högskoleförordning (1993:100)}}
@legislation{Annat, number = {2011:144}, series = {SKOLFS}, title = {Föreskrift}}
@law{Alias, number = {1998:808}, title = {Miljöbalk}, note = {Anmärkning}}
@legislation{AnnatNr, number = {1998:808}, title = {Lag (1999:1)}}
@legislation{UtanNr, author = {{Riksdagen}}, title = {Utan nummer}}
@legislation{SerieVersion, number = {2011:144}, series = {SKOLFS}, title = {Föreskrift},
  version = {2020:5}, note = {Anm}}
BIB
lrun() { "$BIBBER" -b "$TMP/lag.bib" "$@" 2>/dev/null; }
PY="$(head -1 "$BIBBER" | /usr/bin/sed "s/^#!//")"  # samma tolk som bibber.py; ord-delas avsiktligt (env-shebang)
check "lag sv: beteckning, kursiv titel, lydelse, url" \
    "SFS 2010:800. *Skollag* [ändrad t.o.m. SFS 2026:1636]. https://www.riksdagen.se/sv/dokument-och-lagar/dokument/svensk-forfattningssamling/skollag-2010800_sfs-2010-800/" \
    "$(lrun --lang sv -k Skollag)"
contains "lag en: lydelse" "*Skollag* [amended up to and including SFS 2026:1636]." "$(lrun --lang en -k Skollag)"
out="$(lrun --lang sv -k Skollag)"
lacks "lag: inget årtal i parentes" "(2010)" "$out"
lacks "lag: inget departement" "Utbildningsdepartementet" "$out"
check "lag: SFS-prefix i numret, titelns nummer stryks" "SFS 1993:100. *Högskoleförordning*." "$(lrun --lang sv -k HF)"
check "lag: annan författningssamling via series" "SKOLFS 2011:144. *Föreskrift*." "$(lrun --lang sv -k Annat)"
check "lag: @law som alias, note före länk" "SFS 1998:808. *Miljöbalk*. [Anmärkning]" "$(lrun --lang sv -k Alias)"
check "lag: annat nummer i titeln står kvar" "SFS 1998:808. *Lag (1999:1)*." "$(lrun --lang sv -k AnnatNr)"
check "lag: utan nummer står författaren som beteckning" "Riksdagen. *Utan nummer*." "$(lrun --lang sv -k UtanNr)"
check "lag: version tar series-prefixet, note efter" \
    "SKOLFS 2011:144. *Föreskrift* [ändrad t.o.m. SKOLFS 2020:5]. [Anm]" "$(lrun --lang sv -k SerieVersion)"
check "lag: kort form" "SFS 1993:100. Högskoleförordning" \
    "$($PY -c 'import sys; sys.path.insert(0, sys.argv[1]); import bibber; print(bibber.build_standard_reference_short({"entrytype": "legislation", "number": "1993:100", "title": "Högskoleförordning (1993:100)"}))' "$(dirname "$BIBBER")" 2>&1)"

# --- titleaddon: APA-beskrivning i hakparentes efter titeln (Purdue OWL, Review)
cat > "$TMP/addon.bib" <<'BIB'
@periodical{Nummer, title = {Religion \& Livsfrågor}, year = {2026}, volume = {58}, number = {3}, titleaddon = {Temanummer}}
@article{Recension, author = {Björlin, Olle}, title = {Smältdegel och mångkultur?}, crossref = {Nummer}, pages = {14},
  titleaddon = {Recension av Simon Sorgenfrei, »Öppna era hjärtan«, Norstedts 2026}}
@article{Utrop, author = {Ek, Anna}, title = {Äntligen!}, journal = {Tidskrift}, volume = {1}, titleaddon = {[Ledare]}}
@book{BokUppl, author = {Basu, Sanjay}, title = {History and civics}, edition = {2}, publisher = {Frank}, year = {2016}, titleaddon = {Class 6}}
@phdthesis{AvhOvers, author = {Ek, Anna}, title = {Titel}, school = {Uppsala universitet}, year = {2020}, titleaddon = {Translated title}}
@incollection{KapAddon, author = {Ek, Anna}, title = {Kapitel}, booktitle = {Bok}, editor = {Ek, Bo}, pages = {1-2}, year = {2020}, titleaddon = {Förord}}
BIB
arun() { "$BIBBER" -b "$TMP/addon.bib" "$@" 2>/dev/null; }
check "titleaddon: recension, frågetecken står kvar, punkt efter hakparentes" \
    "Björlin, O. (2026). Smältdegel och mångkultur? [Recension av Simon Sorgenfrei, »Öppna era hjärtan«, Norstedts 2026]. *Religion & Livsfrågor*, *58*(3), 14." \
    "$(arun --lang sv -k Recension)"
lacks "titleaddon: numrets titleaddon följer inte med" "Temanummer" "$(arun --lang sv -k Recension)"
check "titleaddon: utropstecken, klamrar i fältet dubbleras inte" "Ek, A. (u.å.). Äntligen! [Ledare]. *Tidskrift*, *1*." "$(arun --lang sv -k Utrop)"
check "titleaddon: bok, efter upplagan" "Basu, S. (2016). *History and civics* (2 uppl.) [Class 6]. Frank." "$(arun --lang sv -k BokUppl)"
check "titleaddon: avhandling, före avhandlingsetiketten" "Ek, A. (2020). *Titel* [Translated title] [Doktorsavhandling, Uppsala universitet]." "$(arun --lang sv -k AvhOvers)"
contains "titleaddon: kapitel" "Kapitel [Förord]. I B. Ek (Red.), *Bok*" "$(arun --lang sv -k KapAddon)"

printf 'PASS=%d FAIL=%d\n' "$PASS" "$FAIL"
[ "$FAIL" -eq 0 ]
