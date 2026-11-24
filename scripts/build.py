"""Combine rosters into docs/data.json and docs/rosters.csv for the website."""
import collections
import csv
import datetime
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from common import class_to_used, current_season, slugify, split_positions  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent


def read(path):
    return list(csv.DictReader(open(path))) if path.exists() else []


def main():
    schools = read(ROOT / "data" / "schools.csv")
    status = json.loads((ROOT / "data" / "status.json").read_text()) if (ROOT / "data" / "status.json").exists() else {}

    detected = collections.Counter(
        v.get("roster_season") for v in status.values() if v.get("status") == "ok" and v.get("roster_season"))
    season = current_season()
    if detected and detected.most_common(1)[0][0] > season:
        season = detected.most_common(1)[0][0]

    players, meta, export = [], [], []
    for s in schools:
        slug = slugify(s["school"])
        st = status.get(slug, {})
        auto = ROOT / "data" / "rosters" / f"{slug}.csv"
        manual = ROOT / "data" / "manual" / f"{slug}.csv"
        if s.get("source") == "manual" and manual.exists():
            rows, kind, rs, updated = read(manual), "manual", int(s.get("manual_season") or season), s.get("manual_date", "")
        elif auto.exists():
            rows, kind = read(auto), ("ok" if st.get("status") == "ok" else "stale")
            rs = st.get("roster_season") or season
            updated = (st.get("last_ok") or st.get("fetched") or "")[:10]
        elif manual.exists():
            rows, kind, rs, updated = read(manual), "manual", int(s.get("manual_season") or season), s.get("manual_date", "")
        else:
            meta.append({"name": s["school"], "conf": s["conference"], "state": s["state"], "status": st.get("status", "pending"), "n": 0})
            continue
        shift = max(0, season - int(rs))  # an old roster means everyone is further along
        n = 0
        for r in rows:
            used, conf = class_to_used(r["class_raw"])
            pos, pos2 = split_positions(r["pos_raw"])
            if used is None or not pos:
                continue
            used = min(used + shift, 5)
            players.append([s["school"], r["jersey"], r["name"], pos, pos2, r["class_raw"], used])
            export.append([s["school"], s["conference"], r["jersey"], r["name"], r["pos_raw"], pos, pos2, r["class_raw"], used, conf])
            n += 1
        meta.append({"name": s["school"], "conf": s["conference"], "state": s["state"], "status": kind,
                     "season": int(rs), "updated": updated, "n": n})

    out = {"season": season, "built": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d"),
           "schools": meta, "players": players}
    (ROOT / "docs").mkdir(exist_ok=True)
    (ROOT / "docs" / "data.json").write_text(json.dumps(out, separators=(",", ":")))
    with open(ROOT / "docs" / "rosters.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["school", "conference", "jersey", "name", "pos_raw", "pos_primary", "pos_secondary", "class_raw", "seasons_used", "eligibility_confidence"])
        w.writerows(export)
    ok = sum(m["status"] in ("ok", "manual", "stale") for m in meta)
    print(f"season {season}: {ok}/{len(meta)} schools with rosters, {len(players)} players")


if __name__ == "__main__":
    main()
