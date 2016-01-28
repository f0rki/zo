#!/usr/bin/env python
import fnmatch
import warnings
import argparse
import subprocess
import os
from os import walk, path, getenv, system
import re

import bibtexparser


NOTE_FORMAT = "md"
REFREPO = os.path.join(os.getenv("HOME"), "refs")
DEFAULT_BIBFILE = "refs.bib"

NOTE_FILE_TEMPLATE = """# Notes about {bibnick}
title: {title}
author: {author}
year: {year}

## Summary


## Comments


## Related Work

"""


cites = ['cite', 'fullcite']
citere = '({})'.format('|'.join(['\\\\' + x for x in cites])) + '\{(.*?)\}'
citere = re.compile(citere)


def get_default_bib():
    return os.path.join(REFREPO, DEFAULT_BIBFILE)


def latex_cites(project):
    """Finds the contents of every \cite command in a LaTeX project within
    a directory, searched recursively.

    Parameters:
    ----------
    project : string
        The name of the directory containing the LaTeX project.

    Returns:
    -------
    cites : set of strings
        The contents of all cite commands in the project directory.
    """
    tex_files = set()
    for root, dirnames, filenames in walk(project):
        for filename in fnmatch.filter(filenames, '*.tex'):
            if filename[0] != '.':
                tex_files.add(path.join(root, filename))

    cites = set()
    for tex_file in tex_files:
        with open(tex_file, 'r') as f:
            lines = "".join(line.strip() for line in f)
            for x in re.findall(citere, lines):
                if x[1]:
                    cites |= set([x.strip() for x in x[1].split(',')])
                else:
                    warnings.warn("Empty citation encountered.", Warning)
    return cites


def bib_nicknames(bib):
    """Finds all the nicknames in BibTeX .bib file.

    Parameters:
    -----------
    bib : str
        Name of the .bib file

    Returns:
    --------
    nicknames : set of strings
        All nicknames within the .bib file
    """
    bib_database = None
    with open(bib) as bibtex_file:
        bib_database = bibtexparser.load(bibtex_file)
    if bib_database is None:
        return set([])
    nicknames = set(entry['ID'] for entry in bib_database.entries)
    return nicknames


def bib_nicks_titles(bib):
    #bib_database = None
    #with open(bib) as bibtex_file:
    #    bib_database = bibtexparser.load(bibtex_file)
    #if bib_database is None:
    #    return {}
    #nt = {entry['ID']: entry['title'].replace("\n", "")
    #      for entry in bib_database.entries}
    #return nt
    return bib_lookup_all(bib, "title")


def sanitize(s):
    s = s.replace("\n", "")
    s = s.replace("\t", "")
    s = s.replace("\r", "")
    return s


def bib_lookup(bib, bibnick, what):
    bib_database = None
    with open(bib) as bibtex_file:
        bib_database = bibtexparser.load(bibtex_file)
    if bib_database is not None:
        if bibnick in bib_database.entries_dict:
            entry = bib_database.entries_dict[bibnick]
            if what in entry:
                return sanitize(entry[what])
    return None


def bib_lookup_many(bib, bibnick, what):
    result = {}
    bib_database = None
    with open(bib) as bibtex_file:
        bib_database = bibtexparser.load(bibtex_file)
    if bib_database is not None:
        if bibnick in bib_database.entries_dict:
            entry = bib_database.entries_dict[bibnick]
            for w in what:
                if w in entry:
                    result[w] = sanitize(entry[w])
    for w in what:
        if w not in result:
            result[w] = ""
    return result


def bib_lookup_all(bib, what):
    result = {}
    bib_database = None
    with open(bib) as bibtex_file:
        bib_database = bibtexparser.load(bibtex_file)
    if bib_database is not None:
        for bibnick in bib_database.entries_dict:
            entry = bib_database.entries_dict[bibnick]
            if what in entry:
                result[bibnick] = sanitize(entry[what])
    return result


def bib_strip(parent_bib, entries):
    """Strips a subset of entries from a BibTeX .bib file

    Parameters:
    ----------
    parent_bib : str
        The parent .bib file
    entries : set of strings
        The BibTeX nicknakes of the entries to be stripped out

    Returns:
    --------
    child_bib : str
        The requested entries
    added_entries : set
        The BibTeX nicknames of the files that were successfully added.
    missing_entries : set
        BibTeX nicknames that were not found in parent_bib
    """
    added_entries = set()
    child_bib = ""
    with open(parent_bib, 'r') as f:
        line = f.readline()
        while line != "":
            if line.strip() != "" and line.strip()[0] == '@' \
                    and line.split('{')[1].split(',')[0].strip() in entries:
                entry = line.split('{')[1].split(',')[0].strip()
                entries.remove(entry)
                added_entries.add(entry)
                child_bib += line
                line = f.readline()
                while line.strip() != "" and line.strip()[0] != '@':
                    if line.strip()[0] != '#':
                        child_bib += line
                    line = f.readline()
                child_bib += "\n"
            else:
                line = f.readline()

    missing_entries = entries  # all entries not added
    return child_bib, added_entries, missing_entries


def find_pdfs(directory):
    files = []
    for root, dirnames, filenames in walk(directory):
        for filename in fnmatch.filter(filenames, '*.pdf'):
            files.append(filename.split(".")[0])

    return files


def filename_to_bibnick(filename):
    m = re.search("\[(.+)\]", filename)
    if m:
        return m.groups()[0]
    return filename


def find_pdf_from_bibnick(bibnick, directory):
    for root, dirnames, filenames in walk(directory):
        for filename in filenames:
            if bibnick in filename and filename.endswith(".pdf"):
                return os.path.abspath(os.path.join(root, filename))


def _printer(things, msg):
    out = ""
    if len(things) > 0:
        out += msg + "\n"
        out += "=" * len(msg) + "\n"
        for i, thing in enumerate(sorted(things)):
            out += "{0}. {1}\n".format(i + 1, thing)
    return out


def make(project, parent, child):
    cites = latex_cites(project)
    local_refs = bib_nicknames(child)
    required_refs = cites - local_refs
    append_string, added_refs, missing_refs = bib_strip(parent, required_refs)

    with open(child, 'a') as f:
        f.write(append_string)

    out = _printer(added_refs,
                   "\nThe following refs were added to the local refs.bib:")
    out += _printer(missing_refs,
                    "\nRefs not in parent and NOT added to the local refs.bib:")
    print(out)


def status():
    bib = path.join(REFREPO, DEFAULT_BIBFILE)
    files = set(map(filename_to_bibnick, find_pdfs(REFREPO)))
    refs = bib_nicknames(bib)
    bnt = bib_nicks_titles(bib)
    x = ["[{}] {}".format(nick, bnt[nick])
         for nick in files & refs if nick in bnt]
    out = _printer(x, "Files that are good to go:")
    out += _printer(files - refs, "\nFiles missing .bib entries:")
    out += _printer(refs - files, "\n.bib entries missing files:")
    print(out)


def grep(repo, args):
    for root, dirnames, filenames in walk(repo):
        for filename in fnmatch.filter(filenames, "*.pdf"):
            full_path = path.join(root, filename)
            ps = subprocess.Popen(("pdftotext", full_path, "-"),
                                  stdout=subprocess.PIPE)
            grep_out = None
            try:
                grep_out = subprocess.check_output((["grep"] + args),
                                                   stdin=ps.stdout)
            except subprocess.CalledProcessError:
                pass
            ps.wait()
            if grep_out:
                print(full_path)


def pdfview(nickname):
    pdf = find_pdf_from_bibnick(nickname, REFREPO)
    cmd = 'xdg-open \"{}\" >/dev/null &'.format(pdf)
    system(cmd)


def get_notes_from_bibnick(nickname, refrepo):
    return os.path.join(refrepo, nickname + "_noted.{}".format(NOTE_FORMAT))


def init_notes_file(nickname, notesfile, refrepo):
    bib = os.path.join(refrepo, DEFAULT_BIBFILE)
    data = bib_lookup_many(bib, nickname, ['title', 'year', 'author'])
    data['bibnick'] = nickname
    s = NOTE_FILE_TEMPLATE.format(**data)
    with open(notesfile, "w") as f:
        f.write(s)


def edit_notes(nickname):
    notes = get_notes_from_bibnick(nickname, REFREPO)
    if not os.path.exists(notes):
        init_notes_file(nickname, notes, REFREPO)
    editor = None
    cmd = None
    if os.getenv("GUI_EDITOR"):
        editor = os.getenv("GUI_EDITOR")
        cmd = "{} \"{}\" >/dev/null &".format(editor, notes)
    elif os.getenv("EDITOR"):
        editor = os.getenv("EDITOR")
        cmd = "{} \"{}\"".format(editor, notes)
    else:
        cmd = "xdg-open \"{}\"".format(notes)
    if cmd:
        system(cmd)


def gscholar_view(nickname):
    raise NotImplementedError()


def search_for_filename(searchstring):
    results = set()
    r = re.compile(searchstring, re.IGNORECASE)
    for root, dirnames, filenames in os.walk(REFREPO):
        for filename in filenames:
            if r.search(filename):
                n = filename_to_bibnick(filename)
                results.add(n)
    return results


def search_for(what, searchstring):
    r = re.compile(searchstring, re.IGNORECASE)
    bib = get_default_bib()
    stuff = bib_lookup_all(bib, what)
    results = set()
    for k, v in stuff.iteritems():
        if r.search(v):
            results.add(k)
    return results


def search(searchstring):
    bib = get_default_bib()
    files = search_for_filename(searchstring)
    authors = search_for("author", searchstring)
    titles = search_for("title", searchstring)
    results = files | authors | titles
    bnt = bib_nicks_titles(bib)
    x = ["[{}] {}".format(nick, bnt[nick])
         for nick in results if nick in bnt]
    out = _printer(x, "Search results:")
    print(out)


def main():
    global REFREPO
    parser = argparse.ArgumentParser()
    parser.add_argument("--refrepo", "-r",
                        action="store",
                        default=REFREPO,
                        help="path to repository of papers and references")

    subparsers = parser.add_subparsers(help="Availible zo commands.",
                                       dest='command')

    status_parser = subparsers\
        .add_parser("status",
                    help="Show what .pdfs and citations are availible or missing")
    make_parser = subparsers\
        .add_parser("make",
                    help="Create a child .bib file containing only the needed refs within a project")
    grep_parser = subparsers\
        .add_parser("grep",
                    help="Find the .pdf that contain a grep match")
    view_parser = subparsers.add_parser("view", help="Open a .pdf")
    note_parser = subparsers.add_parser("note",
                                        help="Manage notes")

    search_parser = subparsers\
        .add_parser("search",
                    help="Search for a paper based on title, filename or author.")  # NOQA

    make_parser.add_argument("-j", "--project",
                             action='store',
                             dest='project',
                             default=".",
                             help="The directory contain the LaTeX project")
    make_parser.add_argument("-p", "--parent",
                             action='store',
                             dest='parent',
                             default=path.join("{REFREPO}",
                                               "refs", "refs.bib"),
                             help="A parent .bib file")
    make_parser.add_argument("-c", "--child",
                             action='store',
                             dest='child',
                             default=path.join(".", "refs.bib"),
                             help="The child ref.bib file to be produced")
    view_parser.add_argument("nickname", action='store',
                             help="Name of the .pdf file")

    note_parser.add_argument("nickname",
                             action="store",
                             help="bibnick of the file you want to add a note")

    search_parser.add_argument("searchstring",
                               action="store",
                               help="string you want to search for")

    args, other = parser.parse_known_args()

    REFREPO = args.refrepo
    if args.command == 'status':
        status()
    elif args.command == 'make':
        make(args.project, args.parent.format(REFREPO=REFREPO), args.child)
    elif args.command == 'grep':
        grep(REFREPO, other)
    elif args.command == 'view':
        pdfview(args.nickname)
    elif args.command == "note":
        edit_notes(args.nickname)
    elif args.command == "search":
        search(args.searchstring)
    else:
        raise NotImplementedError("Invalid command '{}'".format(args.command))


if __name__ == '__main__':
    main()
