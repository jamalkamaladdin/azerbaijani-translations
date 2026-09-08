#!/usr/bin/env python3
"""Rebuild the translation list from merged pull requests on GitHub.

Reads every merged PR by the account, keeps the ones that add an Azerbaijani
locale, then writes data/translations.json and renders README.md from it.
"""
import json, re, subprocess, sys, os
from datetime import datetime, timezone

USER = "jamalkamaladdin"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKIP_OWNERS = {USER.lower(), "runpractice"}

def gh(*args):
    return subprocess.run(["gh", *args], capture_output=True, text=True, check=True).stdout

QUOTED = re.compile(r'"((?:[^"\\]|\\.)*)"|\'((?:[^\'\\]|\\.)*)\'')
NOISE = re.compile(r'\{[^}]*\}|\$\{[^}]*\}|%[0-9$.]*[a-zA-Z]|<[^>]+>|&[a-z]+;|:[a-z_]+')
WORD = re.compile(r'[^\W\d_]+', re.UNICODE)

def words_in_line(line):
    """Count words of translated text on one added diff line."""
    s = line[1:].strip()
    if not s or s.startswith(("//", "/*", "*", "#", "msgid", "msgctxt")):
        return 0
    if s.strip("{}[](),;") == "":
        return 0
    found = [a or b for a, b in QUOTED.findall(s)]
    if found:
        value = found[-1]
    elif ":" in s:
        value = s.split(":", 1)[1]
    elif "=" in s:
        value = s.split("=", 1)[1]
    else:
        value = s
    return len(WORD.findall(NOISE.sub(" ", value)))

def count_words(owner, repo, number):
    patches = gh("api", "--paginate", "repos/%s/%s/pulls/%d/files" % (owner, repo, number),
                 "--jq", ".[] | .patch // empty")
    return sum(words_in_line(ln) for ln in patches.splitlines()
               if ln.startswith("+") and not ln.startswith("+++"))

def is_translation(title):
    t = title.lower()
    if "azerbaijan" in t or "az-az" in t or "az_az" in t:
        return True
    return bool(re.search(r"\baz\b", t)) and bool(re.search(r"locale|i18n|translation|lang", t))

def collect():
    out = gh("api", "-X", "GET", "search/issues",
             "-f", "q=is:pr author:%s is:merged" % USER, "-f", "per_page=100",
             "--jq", ".items[] | {n:.number, t:.title, u:.html_url, r:.repository_url}")
    rows = []
    for line in out.strip().splitlines():
        d = json.loads(line)
        owner, repo = d["r"].split("/")[-2:]
        if owner.lower() in SKIP_OWNERS or not is_translation(d["t"]):
            continue
        rows.append({"owner": owner, "repo": repo, "number": d["n"], "title": d["t"], "url": d["u"]})
    for r in rows:
        meta = json.loads(gh("api", "repos/%s/%s" % (r["owner"], r["repo"]),
                             "--jq", "{stars:.stargazers_count,desc:.description}"))
        r["stars"] = meta["stars"]
        r["description"] = (meta["desc"] or "").strip()
        pr = json.loads(gh("api", "repos/%s/%s/pulls/%d" % (r["owner"], r["repo"], r["number"]),
                           "--jq", "{merged:.merged_at,add:.additions,files:.changed_files}"))
        r["merged_at"] = (pr["merged"] or "")[:10]
        r["additions"] = pr["add"]
        r["files"] = pr["files"]
        r["words"] = count_words(r["owner"], r["repo"], r["number"])
    rows.sort(key=lambda r: (-r["stars"], r["repo"].lower()))
    return rows

def render(rows):
    # one repo can carry more than one merged pull request, so stars are counted once
    total_stars = sum(v["stars"] for v in {(r["owner"], r["repo"]): r for r in rows}.values())
    total_words = sum(r["words"] for r in rows)
    projects = {}
    for r in rows:
        key = (r["owner"], r["repo"])
        if key in projects:
            projects[key]["words"] += r["words"]
        else:
            projects[key] = dict(r)
    head = [
        "# Azerbaijani translations for open source projects",
        "",
        "Azerbaijani (az) locale files I wrote and got merged into open source projects.",
        "",
        "| Project | Stars | Words |",
        "|---|---:|---:|",
    ]
    for r in projects.values():
        head.append("| [%s/%s](https://github.com/%s/%s) | %s | %s |" % (
            r["owner"], r["repo"], r["owner"], r["repo"],
            f'{r["stars"]:,}', f'{r["words"]:,}'))
    head += [
        "",
        "%d merged pull requests into %d projects carrying %s stars in total, %s words of Azerbaijani." % (
            len(rows), len(projects), f"{total_stars:,}", f"{total_words:,}"),
        "",
        "## How the list is built",
        "",
        "`bin/update.py` reads the merged pull requests from the GitHub API, keeps the ones that",
        "add an Azerbaijani locale, writes `data/translations.json` and renders this file from it.",
        "Nothing here is typed by hand, so the numbers stay in step with GitHub.",
        "The word count is taken from the added lines of each merged pull request, counting the",
        "translated text and leaving out keys, placeholders and markup.",
        "",
        "Last updated: %s" % datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "",
    ]
    return "\n".join(head)

def main():
    rows = collect()
    with open(os.path.join(ROOT, "data", "translations.json"), "w", encoding="utf-8") as fh:
        json.dump(rows, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    with open(os.path.join(ROOT, "README.md"), "w", encoding="utf-8") as fh:
        fh.write(render(rows))
    print("%d merged translation PR yazildi" % len(rows))

if __name__ == "__main__":
    main()
