#!/usr/bin/env python
# coding=utf8

import collections
import collections.abc

collections.Iterable = collections.abc.Iterable

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

# Global variables
bib_data = None  # BibTeX data
search_results = []  # Latest search results
DEBUG_MODE = "--debug" in sys.argv  # Debug flag


def load_bibtex(file_path):
    """Load and detexify a BibTeX file."""
    global bib_data
    file_path = os.path.expanduser(file_path)
    latex_converter = LatexNodes2Text()

    try:
        start_time = time.time()

        with open(file_path, "r") as bibfile:
            # Parse the BibTeX file
            parser = biblib.bib.Parser()
            parsed_db = parser.parse(bibfile, log_fp=sys.stderr).get_entries()
            bib_data = biblib.bib.resolve_crossrefs(parsed_db)

        print(f"File loading took {time.time() - start_time:.2f} seconds.")

        # Fields to detexify
        fields_to_process = ["title", "author", "editor", "journal", "booktitle"]

        def detexify_entry(entry):
            """Detexify specific fields of a single BibTeX entry."""
            for field in fields_to_process:
                if field in entry:
                    try:
                        entry[field] = biblib.algo.tex_to_unicode(entry[field])
                    except biblib.messages.InputError:
                        entry[field] = latex_converter.latex_to_text(entry[field])
            return entry

        # Parallel detexify all entries
        with ThreadPoolExecutor() as executor:
            bib_data = dict(
                zip(
                    bib_data.keys(),
                    executor.map(detexify_entry, bib_data.values()),
                )
            )

        print(f"Loaded {len(bib_data)} entries from {file_path}.")
    except FileNotFoundError:
        print(f"Error: File {file_path} not found.")
    except biblib.messages.InputError as e:
        print(f"BibTeX parsing error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")


def sanitize_year(year):
    """Sanitize and return a year as an integer, or 0 if invalid."""
    try:
        if ":" in year:
            year = year.split(":")[0]
        return int(year)
    except (ValueError, TypeError):
        return 0


def process_combined_fields(entry):
    """Combine fields for search."""
    fields = ["title", "author", "editor", "journal", "booktitle"]
    combined_text = " ".join(entry.get(field, "").lower() for field in fields)
    return combined_text


def search_entries(query):
    """Search for entries and display results."""
    global search_results
    if not bib_data:
        print("No BibTeX file loaded. Please load a file first.")
        return

    query_terms = query.lower().split()
    scored_entries = []

    # Process entries in parallel
    with ThreadPoolExecutor() as executor:
        processed_entries = list(
            executor.map(
                lambda entry: (entry[0], process_combined_fields(entry[1])),
                enumerate(bib_data.values()),
            )
        )

    # Calculate scores and collect results
    for idx, combined_text in processed_entries:
        term_matches = sum(1 for term in query_terms if term in combined_text)
        fuzzy_score = fuzz.partial_ratio(query.lower(), combined_text)
        total_score = max(fuzzy_score, term_matches * (100 // len(query_terms)))

        # Collect details for output
        entry = list(bib_data.values())[idx]
        year = entry.get("year", "n.d.")
        authors = entry.get("author", "Unknown Author")
        title = entry.get("title", "Untitled")
        source = entry.get("journal", entry.get("booktitle", "Unknown source"))

        scored_entries.append(
            {
                "idx": idx,
                "score": total_score,
                "authors": authors,
                "year": year,
                "title": title,
                "source": source,
            }
        )

    # Sort by score and year
    scored_entries.sort(
        key=lambda x: (x["score"], sanitize_year(x["year"])), reverse=True
    )

    # Display results
    search_results = scored_entries[:5]
    print("\nSearch Results:")
    for i, result in enumerate(search_results):
        print(
            f"[{i + 1}] {result['authors']} ({result['year']}). {result['title']}. {result['source']}"
        )
        print(f"    Match: {result['score']}%")


def generate_apa(entry):
    """Generate APA-style reference."""
    latex_converter = LatexNodes2Text()
    authors = latex_converter.latex_to_text(entry.get("author", "Unknown Author"))
    year = entry.get("year", "n.d.")
    title = latex_converter.latex_to_text(entry.get("title", "Untitled"))
    source = latex_converter.latex_to_text(
        entry.get("booktitle", entry.get("journal", "Unknown source"))
    )
    apa_reference = f"{authors} ({year}). {title}."
    if source:
        apa_reference += f" {source}"
    print("\nAPA Reference:")
    print(apa_reference)
    return apa_reference


def copy_to_clipboard(reference):
    """Copy a reference to the clipboard."""
    pyperclip.copy(reference)
    print("Reference copied to clipboard.")


def interactive_shell():
    """Start an interactive shell for BibTeX management."""
    print("BibTeX Interactive Shell")
    print("Commands: load, search, copy, exit")
    while True:
        command = prompt("Command > ").strip()
        if not command:
            continue
        args = command.split()
        cmd = args[0].lower()

        if cmd == "load":
            if len(args) < 2:
                print("Usage: load <file_path>")
            else:
                load_bibtex(args[1])

        elif cmd == "search":
            if len(args) < 2:
                print("Usage: search <query>")
            else:
                search_entries(" ".join(args[1:]))

        elif cmd == "copy":
            if len(args) < 2 or not args[1].isdigit():
                print("Usage: copy <index>")
            else:
                index = int(args[1]) - 1
                if 0 <= index < len(search_results):
                    result = search_results[index]
                    entry = list(bib_data.values())[result["idx"]]
                    apa_reference = generate_apa(entry)
                    copy_to_clipboard(apa_reference)
                else:
                    print("Invalid search result index.")

        elif cmd == "exit":
            print("Exiting...")
            break

        else:
            print("Unknown command.")


if __name__ == "__main__":
    # Parse arguments
    args = sys.argv[1:]
    bib_file = next((arg for arg in args if os.path.isfile(arg)), None)
    query = " ".join(arg for arg in args if not os.path.isfile(arg))

    # Load BibTeX file
    if bib_file:
        load_bibtex(bib_file)

    # Perform search if a query is provided
    if query and bib_data:
        search_entries(query)

    # Start interactive shell
    interactive_shell()
