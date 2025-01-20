#!/usr/bin/env python
# coding=utf8

import os
import sys

import bibtexparser
import pyperclip
from bibtexparser.bparser import BibTexParser
from fuzzywuzzy import fuzz, process
from prompt_toolkit import prompt
from pylatexenc.latex2text import LatexNodes2Text

# Global variables
bib_data = None  # Holds loaded BibTeX data
search_results = []  # Holds indices of search results in bib_data.entries
DEBUG_MODE = "--debug" in sys.argv  # Check if debug mode is enabled


# Function to convert LaTeX fields to plain text
def detexify(entry):
    """Convert LaTeX-encoded fields to plain text."""
    fields_to_process = [
        "author",
        "title",
        "journaltitle",
        "journal",
        "booktitle",
        "subtitle",
        "series",
    ]
    for field in fields_to_process:
        if field in entry:
            entry[field] = LatexNodes2Text().latex_to_text(entry[field])


# Helper function to sanitize year values
def sanitize_year(value):
    """Extract and sanitize year value, handling non-standard formats."""
    try:
        # Handle formats like '2010:800' by splitting and taking the first part
        if ":" in value:
            value = value.split(":")[0]
        return int(value)  # Convert to integer if valid
    except (ValueError, TypeError):
        return 0  # Default to 0 if not a valid year


# Load BibTeX file
def load_bibtex(file_path):
    """Load a BibTeX file and parse its content."""
    global bib_data
    file_path = os.path.expanduser(file_path)  # Expand '~' to full path

    parser = BibTexParser(common_strings=True)  # Handle LaTeX symbols
    parser.ignore_nonstandard_types = False  # Include non-standard types
    parser.homogenize_fields = False  # Prevent field loss

    try:
        with open(file_path, "r") as bibfile:
            bib_data = bibtexparser.load(bibfile, parser=parser)

        # De-texify entries
        for entry in bib_data.entries:
            detexify(entry)

        if DEBUG_MODE:
            for entry in bib_data.entries:
                entry_type = entry.get("ENTRYTYPE", "unknown")
                print(
                    f"Loaded entry type: {entry_type}, title: {entry.get('title', 'Untitled')}"
                )

        print(f"Loaded {len(bib_data.entries)} entries from {file_path}.")
    except FileNotFoundError:
        print(f"Error: File {file_path} not found.")
    except Exception as e:
        print(f"An error occurred: {e}")


# Search BibTeX entries
def search_entries(query):
    """Search for entries matching a query and display APA-like info."""
    global search_results
    if bib_data is None:
        print("No BibTeX file loaded. Please load a file first.")
        return

    # Split the query into individual terms
    query_terms = query.lower().split()

    # Combine detexified fields for searching
    processed_entries = []
    for idx, entry in enumerate(bib_data.entries):
        combined_fields = " ".join(
            LatexNodes2Text().latex_to_text(entry.get(field, "")).lower()
            for field in ["title", "author", "editor", "journal", "booktitle"]
        )
        processed_entries.append((idx, combined_fields))

    # Calculate scores
    scored_entries = []
    for idx, combined_fields in processed_entries:
        term_matches = sum(1 for term in query_terms if term in combined_fields)
        fuzzy_score = fuzz.partial_ratio(query.lower(), combined_fields)
        total_score = max(fuzzy_score, term_matches * (100 // len(query_terms)))
        scored_entries.append((idx, total_score))

    # Sort by total score (descending) and then by sanitized year (descending)
    scored_entries.sort(
        key=lambda x: (x[1], sanitize_year(bib_data.entries[x[0]].get("year", "0"))),
        reverse=True,
    )

    search_results = [entry[0] for entry in scored_entries[:5]]
    print("\nSearch Results:")
    for i, (entry_index, score) in enumerate(scored_entries[:5]):
        entry = bib_data.entries[entry_index]

        # Format authors
        authors_field = entry.get("author", "Unknown Author")
        authors = LatexNodes2Text().latex_to_text(authors_field)
        author_list = authors.split(" and ")
        if len(author_list) > 2:
            authors = f"{author_list[0]}, {author_list[1]}, et al."
        elif len(author_list) > 1:
            authors = f"{author_list[0]} and {author_list[1]}"

        # Ensure queried author names are included in display
        for term in query_terms:
            if term in authors_field.lower():
                authors = authors_field

        # Use `date` if `year` is missing
        year = entry.get("year", entry.get("date", "n.d."))
        title = LatexNodes2Text().latex_to_text(entry.get("title", "Untitled"))
        source = entry.get("journal", entry.get("booktitle", ""))
        apa_summary = f"{authors} ({year}). {title}. {source}"

        # Break lines without cutting words
        if len(apa_summary) > 80:
            words = apa_summary.split()
            line = ""
            print(f"[{i + 1}] ", end="")
            for word in words:
                if len(line) + len(word) + 1 > 80:
                    print(line)
                    line = " " * 4 + word
                else:
                    line += (" " if line else "") + word
            print(line)  # Print remaining line
        else:
            print(f"[{i + 1}] {apa_summary}")

        # Show match percentage
        print(f"    Match: {score}%")
    print()


def generate_apa(entry):
    """Generate an APA-style reference for a given entry."""
    # Format authors
    authors_field = entry.get("author", "Unknown Author")
    authors = LatexNodes2Text().latex_to_text(authors_field)
    author_list = authors.split(" and ")
    if len(author_list) > 1:
        authors = " & ".join([", ".join(author_list[:-1]), author_list[-1]])
    else:
        authors = authors.strip()

    # Year
    year = entry.get("year", "n.d.")

    # Title
    title = LatexNodes2Text().latex_to_text(entry.get("title", "Untitled"))
    title = title[0].upper() + title[1:]  # Capitalize the first letter

    # Source: Handle booktitle, journal, or other sources
    source = entry.get("booktitle", entry.get("journal", ""))
    source = LatexNodes2Text().latex_to_text(source)
    if source:
        source = f"In *{source}*"

    # Location and URL
    location = entry.get("location", "")  # Custom field if available
    url = entry.get("url", "")

    # Assemble the reference
    apa_reference = f"{authors} ({year}). {title}."
    if source:
        apa_reference += f" {source}"
    if location:
        apa_reference += f", {location}"
    if url:
        apa_reference += f". {url}"
    apa_reference = apa_reference.strip() + "."

    print("\nAPA Reference:")
    print(apa_reference)
    return apa_reference


# Copy reference to clipboard
def copy_to_clipboard(apa_reference):
    """Copy the generated APA reference to the clipboard."""
    pyperclip.copy(apa_reference)
    print("Reference copied to clipboard.")


# Interactive shell
def interactive_shell():
    """Run the interactive shell for managing BibTeX data."""
    global bib_data

    print("BibTeX Interactive Shell")
    print("Commands: load, search, show, format, copy, exit")

    if len(sys.argv) > 1 and not sys.argv[1].startswith("--"):
        initial_file = os.path.expanduser(sys.argv[1])
        if os.path.exists(initial_file):
            load_bibtex(initial_file)
        else:
            print(f"Error: File {initial_file} not found.")

    while True:
        command = prompt("Command > ").strip()
        args = command.split()
        if not args:
            continue

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
        elif cmd == "show":
            if len(args) < 2 or not args[1].isdigit():
                print("Usage: show <index>")
            else:
                index = int(args[1]) - 1
                if 0 <= index < len(search_results):
                    show_entry(search_results[index])
                else:
                    print("Invalid search result index.")
        elif cmd == "format":
            if len(args) < 2 or not args[1].isdigit():
                print("Usage: format <index>")
            else:
                index = int(args[1]) - 1
                if 0 <= index < len(search_results):
                    entry = bib_data.entries[search_results[index]]
                    apa_reference = generate_apa(entry)
                else:
                    print("Invalid search result index.")
        elif cmd == "copy":
            if len(args) < 2 or not args[1].isdigit():
                print("Usage: copy <index>")
            else:
                index = int(args[1]) - 1
                if 0 <= index < len(search_results):
                    entry = bib_data.entries[search_results[index]]
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
    interactive_shell()
