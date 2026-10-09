#!/usr/bin/env python3
"""azterm: build and check the Azerbaijani software term base.

terms/*.yaml is the source, one file per English term. This script validates every entry,
writes dist/azterm.json, dist/azterm.csv and dist/azterm.tbx, and refreshes the azterm
section of README.md (between the azterm:start and azterm:end markers).

  python3 tools/azterm.py build     validate, write dist/, refresh README
  python3 tools/azterm.py check     validate only (CI); exit 1 on an error
"""
import csv, io, json, os, re, sys
from xml.sax.saxutils import escape, quoteattr

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TERMS = os.path.join(ROOT, "terms")
DIST = os.path.join(ROOT, "dist")
README = os.path.join(ROOT, "README.md")
START, END = "<!-- azterm:start -->", "<!-- azterm:end -->"
STATUS = {"reviewed", "evidence"}
REF_NAMES = {"oss": "these translations", "firefox": "Firefox", "gnome": "GNOME", "libreoffice": "LibreOffice"}


def slug(en):
    return re.sub(r"[^a-z0-9]+", "-", en.lower()).strip("-")


def load():
    import yaml   # only build/check need it; readme_section() reads dist/azterm.json (bin/update.py runs without PyYAML)
    terms, errors = [], []
    for f in sorted(os.listdir(TERMS)) if os.path.isdir(TERMS) else []:
        if not f.endswith(".yaml"):
            continue
        path = os.path.join(TERMS, f)
        try:
            t = yaml.safe_load(open(path, encoding="utf-8"))
        except yaml.YAMLError as e:
            errors.append(f"{f}: YAML error {e}")
            continue
        for k in ("en", "az", "status", "decided"):
            if not t.get(k):
                errors.append(f"{f}: missing {k}")
        if t.get("status") not in STATUS:
            errors.append(f"{f}: status must be one of {sorted(STATUS)}")
        if t.get("en") and f != slug(t["en"]) + ".yaml":
            errors.append(f"{f}: file name must be {slug(t['en'])}.yaml")
        for a in t.get("avoid") or []:
            if not a.get("form") or not a.get("reason"):
                errors.append(f"{f}: every avoid entry needs form and reason")
            elif a["form"] == t.get("az"):
                errors.append(f"{f}: {a['form']!r} is both the term and an avoided form")
        if "ä" in str(t.get("az", "")) or re.search(r"[\u04d9\u04d8\u01dd\u018e]", str(t.get("az", ""))):
            errors.append(f"{f}: az uses a wrong letter for ə (ä, Cyrillic ә or ǝ)")
        t["_file"] = f
        terms.append(t)
    seen = {}
    for t in terms:
        if t.get("en") in seen:
            errors.append(f"{t['_file']}: duplicate of {seen[t['en']]}")
        seen[t.get("en")] = t["_file"]
    return terms, errors


def clean(t):
    return {k: v for k, v in t.items() if not k.startswith("_")}


def tbx(terms):
    out = ['<?xml version="1.0" encoding="UTF-8"?>',
           '<martif type="TBX" xml:lang="en">',
           ' <martifHeader><fileDesc><sourceDesc><p>azterm: Azerbaijani software terminology, '
           'https://github.com/jamalkamaladdin/azerbaijani-translations (CC BY 4.0)</p></sourceDesc>'
           '</fileDesc></martifHeader>',
           ' <text><body>']
    for t in terms:
        out.append(f'  <termEntry id={quoteattr(slug(t["en"]))}>')
        out.append(f'   <langSet xml:lang="en"><tig><term>{escape(t["en"])}</term></tig></langSet>')
        note = "; ".join(f'avoid "{a["form"]}": {a["reason"]}' for a in t.get("avoid") or [])
        if t.get("note"):
            note = (t["note"] + ("; " + note if note else ""))
        out.append(f'   <langSet xml:lang="az"><tig><term>{escape(t["az"])}</term></tig>'
                   + (f"<note>{escape(note)}</note>" if note else "") + "</langSet>")
        out.append("  </termEntry>")
    out += [" </body></text>", "</martif>", ""]
    return "\n".join(out)


def csv_text(terms):
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(["source", "target", "status", "avoid", "note"])
    for t in terms:
        w.writerow([t["en"], t["az"], t["status"], "|".join(a["form"] for a in t.get("avoid") or []), t.get("note", "")])
    return buf.getvalue()


def readme_section(terms=None):
    if terms is None:
        terms = json.load(open(os.path.join(DIST, "azterm.json"), encoding="utf-8"))
    reviewed = sum(1 for t in terms if t["status"] == "reviewed")
    lines = [
        START,
        "## azterm: Azerbaijani software terminology",
        "",
        "Which Azerbaijani word to use for a common interface term (Close, Status, Delete). Each entry",
        "in `terms/` names the recommended form, forms to avoid with the reason, and the evidence: how",
        "many of the projects above use each form, and what Firefox, GNOME and LibreOffice use.",
        "",
        f"{len(terms)} terms, {reviewed} reviewed by a person, {len(terms) - reviewed} accepted on evidence "
        "(these translations and at least one reference project agree).",
        "",
        "Import into a translation tool: [`dist/azterm.tbx`](dist/azterm.tbx) (Weblate, Crowdin, Lokalise,",
        "Poedit, OmegaT), [`dist/azterm.csv`](dist/azterm.csv), [`dist/azterm.json`](dist/azterm.json).",
        "",
        "The table shows the form each source uses most; a dash means the source has no such string.",
        "",
        "| English | Azerbaijani | Projects above | Firefox | GNOME | LibreOffice |",
        "|---|---|---:|---|---|---|",
    ]
    order = sorted(terms, key=lambda t: (-(t.get("evidence", {}).get("oss", {}).get("repos", 0)), t["en"]))

    def top(ev, k):
        forms = ev.get(k) or {}
        return max(forms, key=forms.get) if forms else "—"

    for t in order[:40]:
        ev = t.get("evidence") or {}
        oss = ev.get("oss") or {}
        n = (oss.get("forms") or {}).get(t["az"], 0)
        share = f"{n} of {oss['repos']}" if oss.get("repos") else "—"
        lines.append(f"| {t['en']} | **{t['az']}** | {share} | {top(ev, 'firefox')} | {top(ev, 'gnome')} | {top(ev, 'libreoffice')} |")
    if len(terms) > 40:
        lines += ["", f"The other {len(terms) - 40} terms are in `terms/` and `dist/`."]
    lines += [
        "",
        "Term entries are licensed CC BY 4.0. Reference counts are derived from the Firefox, GNOME and",
        "LibreOffice Azerbaijani localizations (MPL-2.0 and GPL/LGPL projects); only single terms and counts",
        "are reproduced here.",
        END,
    ]
    return "\n".join(lines)


def refresh_readme(section):
    text = open(README, encoding="utf-8").read()
    if START in text and END in text:
        text = text[:text.index(START)] + section + text[text.index(END) + len(END):]
    else:
        anchor = "## How the list is built"
        text = text.replace(anchor, section + "\n\n" + anchor, 1) if anchor in text else text.rstrip() + "\n\n" + section + "\n"
    with open(README, "w", encoding="utf-8") as fh:
        fh.write(text)


def main(cmd):
    terms, errors = load()
    for e in errors:
        print("error:", e)
    if errors:
        return 1
    if cmd == "check":
        print(f"{len(terms)} terms ok")
        return 0
    terms.sort(key=lambda t: t["en"])
    os.makedirs(DIST, exist_ok=True)
    with open(os.path.join(DIST, "azterm.json"), "w", encoding="utf-8") as fh:
        json.dump([clean(t) for t in terms], fh, ensure_ascii=False, indent=1)
        fh.write("\n")
    with open(os.path.join(DIST, "azterm.csv"), "w", encoding="utf-8") as fh:
        fh.write(csv_text(terms))
    with open(os.path.join(DIST, "azterm.tbx"), "w", encoding="utf-8") as fh:
        fh.write(tbx(terms))
    refresh_readme(readme_section(terms))
    print(f"{len(terms)} terms built")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "build"))
