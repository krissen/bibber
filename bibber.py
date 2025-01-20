#!/usr/bin/env python
# coding=utf8

import os
import sys

import bibtexparser
import pyperclip
from bibtexparser.bparser import BibTexParser

# from bibtexparser.customization import homogenize_latex
from fuzzywuzzy import process
from prompt_toolkit import prompt

# Global variable to hold BibTeX data
bib_data = None

DEBUG_MODE = "--debug" in sys.argv  # Check if debug mode is enabled


# Load BibTeX file
def load_bibtex(file_path):
    global bib_data
    file_path = os.path.expanduser(file_path)  # Expand '~' to full path

    # Configure parser to include all entry types
    parser = BibTexParser(common_strings=True)  # Handle LaTeX symbols
    parser.ignore_nonstandard_types = False  # Ensure non-standard types are included
    parser.homogenize_fields = False  # Prevent loss of any fields

    try:
        with open(file_path, "r") as bibfile:
            bib_data = bibtexparser.load(bibfile, parser=parser)

        # Log loaded entries if debug mode is enabled
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


# Logga alla inlästa entries
def log_loaded_entries():
    if bib_data is None:
        print("No BibTeX data loaded.")
        return
    print("\nLoaded entries:")
    for i, entry in enumerate(bib_data.entries, start=1):
        print(
            f"[{i}] Type: {entry.get('ENTRYTYPE', 'unknown')}, Title: {entry.get('title', 'Untitled')}"
        )


# Search BibTeX entries
def search_entries(query):
    if bib_data is None:
        print("No BibTeX file loaded. Please load a file first.")
        return []

    titles = [entry.get("title", "Untitled") for entry in bib_data.entries]
    matches = process.extract(query, titles, limit=5)

    print("\nSearch Results:")
    for i, (title, score) in enumerate(matches):
        entry = next((e for e in bib_data.entries if e.get("title") == title), None)
        if entry:
            print(f"[{i+1}] {title} ({entry.get('year', 'n.d.')}) - {score}% match")
    print()
    return matches


# Display details of a specific entry
def show_entry(index):
    if bib_data is None:
        print("No BibTeX file loaded. Please load a file first.")
        return

    try:
        entry = bib_data.entries[index - 1]
        print("\nEntry Details:")
        for key, value in entry.items():
            print(f"{key}: {value}")
        print()
    except IndexError:
        print("Invalid entry index.")


# Generate APA reference with support for non-standard types
# Generate APA reference with full support for all entry types
def generate_apa(entry):
    authors = entry.get("author", "Unknown Author").replace(" and ", ", ")
    year = entry.get("year", "n.d.")
    title = entry.get("title", "Untitled")
    entry_type = entry.get("ENTRYTYPE", "generic").capitalize()
    source = entry.get("journal", entry.get("booktitle", entry.get("howpublished", "")))

    apa = f"{authors} ({year}). {title}."
    if source:
        apa += f" {source}."
    apa += f" [Type: {entry_type}]"

    print("\nAPA Reference:")
    print(apa)
    return apa


# Copy reference to clipboard
def copy_to_clipboard(apa_reference):
    pyperclip.copy(apa_reference)
    print("Reference copied to clipboard.")


def interactive_shell():
    global bib_data

    print("BibTeX Interactive Shell")
    print("Commands: load, search, show, format, copy, exit")

    # Check if a file is passed as an argument
    if len(sys.argv) > 1 and not sys.argv[1].startswith("--"):
        initial_file = os.path.expanduser(sys.argv[1])
        if os.path.exists(initial_file):
            load_bibtex(initial_file)
        else:
            print(f"Error: File {initial_file} not found.")

    while True:
        command = input("Command > ").strip()
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
                show_entry(int(args[1]))
        elif cmd == "format":
            if len(args) < 2 or not args[1].isdigit():
                print("Usage: format <index>")
            else:
                entry = bib_data.entries[int(args[1]) - 1]
                apa_reference = generate_apa(entry)
        elif cmd == "copy":
            if len(args) < 2 or not args[1].isdigit():
                print("Usage: copy <index>")
            else:
                entry = bib_data.entries[int(args[1]) - 1]
                apa_reference = generate_apa(entry)
                copy_to_clipboard(apa_reference)
        elif cmd == "exit":
            print("Exiting...")
            break
        else:
            print("Unknown command.")


if __name__ == "__main__":
    interactive_shell()
