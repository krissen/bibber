#!/usr/bin/env python
# coding=utf8
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
from prompt_toolkit import prompt
from pylatexenc.latex2text import LatexNodes2Text

collections.Iterable = collections.abc.Iterable

# Global variables
bib_data = None
search_results = []
DEBUG_MODE = "--debug" in sys.argv
CACHE_DIR = os.path.expanduser("~/.cache/bibber/")
os.makedirs(CACHE_DIR, exist_ok=True)


def safe_latex_to_text(latex_str):
    """Safely convert LaTeX to text."""
    try:
        return LatexNodes2Text().latex_to_text(latex_str)
    except Exception as e:
        if DEBUG_MODE:
            print(f"Debug: Failed to process LaTeX: {latex_str}. Error: {e}")
        return latex_str or ""


def search_entries(query):
    """Sök efter poster och visa resultat."""
    global search_results
    if not bib_data:
        print("Ingen BibTeX-fil har laddats. Ladda en fil först.")
        return

    query_terms = [term.lower() for term in query.split() if term.lower() != "--debug"]
    if DEBUG_MODE:
        print(f"Debug: Rensade söktermer: {query_terms}")
    scored_entries = []

    # Process entries parallellt
    with ThreadPoolExecutor() as executor:
        processed_entries = list(
            executor.map(
                lambda entry: (
                    entry[0],
                    safe_latex_to_text(entry[1].get("title", "")) + " " +
                    safe_latex_to_text(entry[1].get("author", entry[1].get("editor", "Okänd författare"))) + " " +
                    safe_latex_to_text(entry[1].get("journaltitle", entry[1].get("journal", entry[1].get("booktitle", ""))))
                ),
                enumerate(bib_data.values()),
            )
        )

    for idx, combined_text in processed_entries:
        combined_text_lower = combined_text.lower()

        exact_matches = 0
        fuzzy_scores = []
        for term in query_terms:
            if term.isdigit():  # Hantera årsspecifika termer
                year = bib_data[list(bib_data.keys())[idx]].get("year", "")
                if term == year:
                    exact_matches += 1
                    if DEBUG_MODE:
                        print(f"Debug: Exakt match för år '{term}' i post '{idx}'")
                else:
                    fuzzy_score = fuzz.partial_ratio(term, year) / 100
                    fuzzy_scores.append(fuzzy_score)
                    if DEBUG_MODE:
                        print(f"Debug: Fuzzy träffprocent för år '{term}': {fuzzy_score * 100}")
            elif term in combined_text_lower:
                exact_matches += 1
                if DEBUG_MODE:
                    print(f"Debug: Exakt match för term '{term}'")
            else:
                fuzzy_score = fuzz.partial_ratio(term, combined_text_lower) / 100
                fuzzy_scores.append(fuzzy_score)
                if DEBUG_MODE:
                    print(f"Debug: Fuzzy träffprocent för term '{term}': {fuzzy_score * 100}")

        exact_match_score = (exact_matches / len(query_terms)) * 100
        fuzzy_match_score = (sum(fuzzy_scores) / len(query_terms)) * 100
        total_score = exact_match_score + fuzzy_match_score

        if DEBUG_MODE:
            print(f"Debug: Exakt träffpoäng: {exact_match_score}")
            print(f"Debug: Fuzzy träffpoäng: {fuzzy_match_score}")
            print(f"Debug: Total poäng: {total_score}")

        entry = list(bib_data.values())[idx]
        year = sanitize_year(entry.get("year", "0"))

        # Hantera författare eller redaktör
        authors = safe_latex_to_text(entry.get("author"))
        if not authors:
            editors = safe_latex_to_text(entry.get("editor", "Okänd författare"))
            if " and " in editors:
                authors = f"{editors} (eds.)"
            else:
                authors = f"{editors} (ed.)"

        # Hantera titel baserat på entrytype
        title = safe_latex_to_text(entry.get("title", "Saknar titel"))
        entrytype = entry.get("entrytype", "").lower()
        if entrytype == "book":
            source = ""
        else:
            source = safe_latex_to_text(
                entry.get("journaltitle", entry.get("journal", entry.get("booktitle", "")))
            )

        scored_entries.append(
            {
                "idx": idx,
                "score": total_score,
                "year": year,
                "authors": authors,
                "title": title,
                "source": source,
            }
        )

    # Sortera efter poäng och år
    scored_entries.sort(key=lambda x: (x["score"], x["year"]), reverse=True)

    # Visa resultaten
    search_results = scored_entries[:5]
    print("\nSökresultat:\n")
    for i, result in enumerate(search_results):
        source_display = result["source"]

        # Konstruera referens utan onödiga punkter
        reference = f"[{i + 1}] {result['authors']} ({result['year']}). {result['title']}"
        if source_display:
            reference += f". {source_display}"
        reference += "."  # Slutpunkt endast om värden finns

        # Skriv ut referensen
        print(reference)
        print(f"    Träff: {result['score']:.1f}%\n")


def process_combined_fields(entry):
    """Combine relevant fields for search."""
    fields = ["title", "author", "editor", "journal", "booktitle"]
    combined_text = " ".join(entry.get(field, "").lower() for field in fields)
    return combined_text


def copy_to_clipboard(reference):
    """Copy a reference to the clipboard."""
    try:
        pyperclip.copy(reference)
        print("Reference copied to clipboard.")
    except Exception as e:
        print(f"Error copying to clipboard: {e}")


def sanitize_year(year):
    """Sanitize and return a year as an integer, or 0 if invalid."""
    try:
        if ":" in year:
            year = year.split(":")[0]
        return int(year)
    except (ValueError, TypeError):
        return 0


def md5sum(file_path):
    """Generate MD5 checksum for a file."""
    with open(file_path, "rb") as f:
        return hashlib.md5(f.read()).hexdigest()


def load_from_cache(cache_file):
    """Load cached data if available."""
    try:
        with open(cache_file, "r") as f:
            return json.load(f)
    except Exception:
        return None


def save_to_cache(data, cache_file):
    """Save data to cache."""
    with open(cache_file, "w") as f:
        json.dump(data, f)


def extract_entrytypes(file_path):
    """Extract entry types manually from the BibTeX file."""
    entry_types = {}
    with open(file_path, "r") as file:
        for line in file:
            line = line.strip()
            if line.startswith("@") and "{" in line:
                entry_type, rest = line[1:].split("{", 1)
                key = rest.split(",", 1)[0].strip()
                entry_types[key.lower()] = entry_type.lower()
    return entry_types


def load_bibtex(file_path):
    """Load a BibTeX file and detexify its entries."""
    global bib_data
    file_path = os.path.expanduser(file_path)
    cache_file = os.path.join(CACHE_DIR, f"{md5sum(file_path)}.json")

    cached_data = load_from_cache(cache_file)
    if cached_data:
        if DEBUG_MODE:
            print(f"Debug: Loaded from cache: {cache_file}")
        bib_data = cached_data
        return

    latex_converter = LatexNodes2Text()

    try:
        start_time = time.time()
        with open(file_path, "r") as bibfile:
            parser = biblib.bib.Parser()
            parsed_db = parser.parse(bibfile, log_fp=sys.stderr).get_entries()
            bib_data = biblib.bib.resolve_crossrefs(parsed_db)

        entry_types = extract_entrytypes(file_path)
        for key, entry in bib_data.items():
            if entry.get("entrytype", "unknown") == "unknown":
                entry["entrytype"] = entry_types.get(key.lower(), "unknown")

        save_to_cache(bib_data, cache_file)

        if DEBUG_MODE:
            for key, entry in bib_data.items():
                print(
                    f"Debug: Key: {key}, Entry type: {entry.get('entrytype', 'unknown')}"
                )

        if DEBUG_MODE:
            print(f"Debug: File loading took {time.time() - start_time:.2f} seconds.")
    except Exception as e:
        print(f"An error occurred: {e}")


def generate_apa(entry):
    """Generate APA 7-style reference."""
    latex_converter = LatexNodes2Text()

    # Författare eller redaktörer
    authors_raw = latex_converter.latex_to_text(entry.get("author", ""))
    authors = []
    if not authors_raw:
        authors_raw = latex_converter.latex_to_text(entry.get("editor", "Unknown Editor"))
        is_editor = True
    else:
        is_editor = False

    for author in authors_raw.split(" and "):
        names = author.split(", ")
        if len(names) == 2:
            last_name, first_names = names
            initials = "".join([f"{name[0].upper()}." for name in first_names.split()])
            authors.append(f"{last_name}, {initials}")
    authors = " & ".join(authors)

    # Lägg till (ed.) eller (eds.) för redaktörer
    if is_editor:
        authors += " (ed.)" if len(authors_raw.split(" and ")) == 1 else " (eds.)"

    # År
    year = entry.get("year", "n.d.")

    # Titel
    title = latex_converter.latex_to_text(entry.get("title", "Untitled"))
    title = title[0].upper() + title[1:] if title else "Untitled"

    # Källor och kontext
    entry_type = entry.get("entrytype", "").lower()
    if DEBUG_MODE:
        print(f"Debug: Entry type: {entry_type}")

    source = latex_converter.latex_to_text(
        entry.get("booktitle", entry.get("journaltitle", entry.get("journal", "")))
    )
    editor_raw = latex_converter.latex_to_text(entry.get("editor", ""))
    editors = []
    if editor_raw:
        for editor in editor_raw.split(" and "):
            names = editor.split(", ")
            if len(names) == 2:
                last_name, first_names = names
                initials = "".join([f"{name[0].upper()}." for name in first_names.split()])
                editors.append(f"{last_name}, {initials}")
    if editors:
        editors_text = " (eds.)" if len(editors) > 1 else " (ed.)"
        editors = f"In {', '.join(editors)}{editors_text}"

    # Förlag och ort
    publisher = latex_converter.latex_to_text(entry.get("publisher", ""))
    location = latex_converter.latex_to_text(entry.get("location", ""))

    # Sidor
    pages = entry.get("pages", "").replace("--", "–")
    if pages:
        pages = f"pp. {pages}"

    # DOI
    doi = entry.get("doi", "")
    if doi and not doi.startswith("https://doi.org/"):
        doi = f"https://doi.org/{doi}"

    # Bygg referensen
    apa_reference = f"{authors} ({year})."
    if entry_type == "book":
        # Endast för `@book` entries - kursivera titeln
        apa_reference += f" *{title}*."
        if location and publisher:
            apa_reference += f" {location}: {publisher}."
        elif publisher:
            apa_reference += f" {publisher}."
        elif location:
            apa_reference += f" {location}."
    else:
        # För andra typer av entries
        apa_reference += f" {title}."
        if editors:
            apa_reference += f" {editors}"
        if source:
            apa_reference += f" *{source}*"
        if pages:
            apa_reference += f", {pages}."
        if location and publisher:
            apa_reference += f" {location}: {publisher}."
        elif publisher:
            apa_reference += f" {publisher}."
        elif location:
            apa_reference += f" {location}."
    if doi:
        apa_reference += f" doi: {doi}"

    return " ".join(apa_reference.split())


def interactive_shell():
    """Interaktivt gränssnitt för BibTeX-hantering."""
    print("\nInteraktivt BibTeX-gränssnitt")
    print("Kommandon: ladda, sök, kopiera, avsluta\n")

    while True:
        try:
            command = prompt("Kommando > ").strip()
            if not command:
                continue
            args = command.split()
            cmd = args[0].lower()

            # Om användaren anger bara en siffra efter en sökning, tolka som kopiera
            if cmd.isdigit() and len(search_results) > 0:
                index = int(cmd) - 1
                if 0 <= index < len(search_results):
                    result = search_results[index]
                    entry = list(bib_data.values())[result["idx"]]
                    apa_reference = generate_apa(entry)
                    print(f"\n{apa_reference}\n")
                    copy_to_clipboard(apa_reference)
                    continue
                else:
                    print("Ogiltigt index. Ange en siffra mellan 1 och 5.\n")

            if cmd in ["ladda", "load"]:
                if len(args) < 2:
                    print("Användning: ladda <filväg>\n")
                else:
                    load_bibtex(args[1])

            elif cmd in ["sök", "search"]:
                if len(args) < 2:
                    print("Användning: sök <fråga>\n")
                else:
                    search_entries(" ".join(args[1:]))

            elif cmd in ["kopiera", "copy"]:
                if len(args) < 2 or not args[1].isdigit():
                    print("Användning: kopiera <index>\n")
                else:
                    index = int(args[1]) - 1
                    if 0 <= index < len(search_results):
                        result = search_results[index]
                        entry = list(bib_data.values())[result["idx"]]
                        apa_reference = generate_apa(entry)
                        print(f"\n{apa_reference}\n")
                        copy_to_clipboard(apa_reference)
                    else:
                        print("Ogiltigt index. Ange en siffra mellan 1 och 5.\n")

            elif cmd in ["avsluta", "quit", "exit"]:
                print("Avslutar...\n")
                break

            else:
                print("Okänt kommando.\n")

        except (KeyboardInterrupt, EOFError):
            print("\nAvslutar...\n")
            break


if __name__ == "__main__":
    args = sys.argv[1:]
    bib_file = next((arg for arg in args if os.path.isfile(arg)), None)
    query = " ".join(arg for arg in args if not os.path.isfile(arg))

    if bib_file:
        load_bibtex(bib_file)

    if query and bib_data:
        search_entries(query)

    interactive_shell()
