"""Fetch each school's official roster page and save it as data/rosters/<slug>.csv.

Polite by design: identifies itself, obeys robots.txt, one request per school,
waits between requests, and never tries to get around a block. A school that
blocks us or whose page doesn't parse cleanly is marked in data/status.json and
keeps its last good roster (or a hand-entered file in data/manual/).
"""
import csv
import datetime
import json
import os
import pathlib
import re
import sys
import time
import urllib.robotparser
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from common import class_to_used, slugify, split_positions  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
CONTACT = os.environ.get("CONTACT_EMAIL", "set-CONTACT_EMAIL-in-workflow")
UA = f"RosterGapsBot/1.0 (college soccer recruiting research; contact: {CONTACT})"
DELAY = 2.5

BLOCK_MARKERS = ("captcha", "access denied", "are you a robot", "verify you are human", "cf-challenge")


def _clean(txt):
    txt = re.sub(r"\s+", " ", txt or "").strip()
    return re.sub(r"^(No\.?|Jersey|Name|Pos\.?|Position|Cl\.?|Class|Yr\.?|Academic Year)\s*[:.]?\s*", "", txt, flags=re.I)


def parse_sidearm_list(soup):
    rows = []
    for li in soup.select("li.sidearm-roster-player"):
        def g(sel):
            el = li.select_one(sel)
            return _clean(el.get_text(" ")) if el else ""
        name_el = li.select_one(".sidearm-roster-player-name a") or li.select_one(".sidearm-roster-player-name")
        name = _clean(name_el.get_text(" ")) if name_el else ""
        pos = g(".sidearm-roster-player-position-long-short") or g(".sidearm-roster-player-position")
        pos = re.sub(r"^.*?\b(GK|Goalkeeper|Defender|Midfielder|Forward)\b", r"\1", pos) if pos else pos
        rows.append((g(".sidearm-roster-player-jersey-number"), name, pos, g(".sidearm-roster-player-academic-year")))
    return rows


def parse_table(soup):
    for table in soup.find_all("table"):
        head = [re.sub(r"[^a-z]", "", th.get_text().lower()) for th in table.select("thead th, tr:first-child th")]
        if not head:
            continue
        def col(*names):
            for i, h in enumerate(head):
                if h in names:
                    return i
            return None
        iname, ipos = col("name", "player", "fullname"), col("pos", "position")
        icl, ino = col("cl", "class", "yr", "year", "academicyear", "eligibility"), col("no", "number", "jersey")
        if iname is None or ipos is None or icl is None:
            continue
        out = []
        for tr in table.select("tbody tr") or table.find_all("tr")[1:]:
            cells = tr.find_all(["td", "th"])
            if len(cells) <= max(iname, ipos, icl):
                continue
            nm_a = cells[iname].find("a")
            name = _clean((nm_a or cells[iname]).get_text(" "))
            out.append((_clean(cells[ino].get_text(" ")) if ino is not None and ino < len(cells) else "",
                        name, _clean(cells[ipos].get_text(" ")), _clean(cells[icl].get_text(" "))))
        if out:
            return out
    return []


def parse_roster(html):
    """Return (rows, roster_season). rows = [(jersey, name, pos_raw, class_raw)]."""
    soup = BeautifulSoup(html, "html.parser")
    rows = parse_sidearm_list(soup) or parse_table(soup)
    rows = [r for r in rows if r[1]]
    seen, uniq = set(), []
    for r in rows:  # Sidearm pages often render the same roster twice (list + table)
        k = (r[0], r[1])
        if k not in seen:
            seen.add(k)
            uniq.append(r)
    text = soup.get_text(" ")
    m = re.search(r"(20\d\d)(?:\s*[-–]\s*\d\d)?\s+Women.?s Soccer", text, re.I)
    season = int(m.group(1)) if m else None
    return uniq, season


def validate(rows):
    """Reject pages that parsed into nonsense. Returns an error string or ''."""
    if not 10 <= len(rows) <= 70:
        return f"unexpected player count {len(rows)}"
    ok_cls = sum(class_to_used(r[3])[0] is not None for r in rows)
    ok_pos = sum(bool(split_positions(r[2])[0]) for r in rows)
    if ok_cls < 0.8 * len(rows):
        return "class years not recognized"
    if ok_pos < 0.8 * len(rows):
        return "positions not recognized"
    return ""


def allowed(session_cache, url):
    host = urlparse(url)
    base = f"{host.scheme}://{host.netloc}"
    if base not in session_cache:
        rp = urllib.robotparser.RobotFileParser()
        try:
            r = requests.get(base + "/robots.txt", headers={"User-Agent": UA}, timeout=15)
            rp.parse(r.text.splitlines() if r.status_code == 200 else [])
        except requests.RequestException:
            rp.parse([])
        session_cache[base] = rp
    return session_cache[base].can_fetch(UA, url)


def main():
    status_path = ROOT / "data" / "status.json"
    status = json.loads(status_path.read_text()) if status_path.exists() else {}
    only = set(sys.argv[1:])
    robots = {}
    schools = list(csv.DictReader(open(ROOT / "data" / "schools.csv")))
    for s in schools:
        slug = slugify(s["school"])
        if only and slug not in only:
            continue
        if s.get("source") == "manual" or not s.get("roster_url"):
            continue
        now = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
        rec = {"fetched": now, "url": s["roster_url"]}
        try:
            if not allowed(robots, s["roster_url"]):
                rec.update(status="blocked", error="robots.txt disallows")
            else:
                r = requests.get(s["roster_url"], headers={"User-Agent": UA}, timeout=30)
                low = r.text[:5000].lower()
                if r.status_code in (401, 403, 429) or any(m in low for m in BLOCK_MARKERS):
                    rec.update(status="blocked", error=f"HTTP {r.status_code}")
                elif r.status_code != 200:
                    rec.update(status="failed", error=f"HTTP {r.status_code}")
                else:
                    rows, season = parse_roster(r.text)
                    err = validate(rows)
                    if err:
                        rec.update(status="failed", error=err)
                    else:
                        with open(ROOT / "data" / "rosters" / f"{slug}.csv", "w", newline="") as f:
                            w = csv.writer(f)
                            w.writerow(["school", "jersey", "name", "pos_raw", "class_raw"])
                            for j, n, p, c in rows:
                                w.writerow([s["school"], j, n, p, c])
                        rec.update(status="ok", count=len(rows), roster_season=season)
        except requests.RequestException as e:
            rec.update(status="failed", error=type(e).__name__)
        # keep the last good fetch info when a refresh fails
        prev = status.get(slug, {})
        if rec["status"] != "ok" and prev.get("status") == "ok":
            rec["last_ok"] = prev.get("fetched")
            rec["count"] = prev.get("count")
            rec["roster_season"] = prev.get("roster_season")
            rec["has_old_data"] = True
        elif rec["status"] == "ok":
            rec["last_ok"] = now
        status[slug] = rec
        print(f"{s['school']:32s} {rec['status']:8s} {rec.get('count', '')} {rec.get('error', '')}", flush=True)
        time.sleep(DELAY)
    status_path.write_text(json.dumps(status, indent=1, sort_keys=True))


if __name__ == "__main__":
    main()
