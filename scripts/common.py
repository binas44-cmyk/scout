"""Shared helpers: class-year and position normalization, season rule."""
import datetime
import re

# Seasons of eligibility already used, counted through the roster's season.
_BASE = {
    "fr": 1, "freshman": 1, "fy": 1, "1st": 1, "first": 1,
    "so": 2, "sophomore": 2, "2nd": 2, "second": 2,
    "jr": 3, "junior": 3, "3rd": 3, "third": 3,
    "sr": 4, "senior": 4, "4th": 4, "fourth": 4,
}
_GRAD = {"gr", "grad", "graduate", "gs", "5th", "fifth", "5thyear", "fifthyear", "6th", "sixth"}


def class_to_used(cls):
    """Return (seasons_used, confidence) or (None, None) if unrecognized."""
    c = re.sub(r"[^a-z0-9]", "", (cls or "").lower())
    if not c:
        return None, None
    if c in _GRAD:
        return 4, "low"
    for prefix in ("", "redshirt", "rs", "r"):
        if c.startswith(prefix):
            rest = c[len(prefix):]
            if rest in _BASE:
                u = _BASE[rest]
                conf = "medium" if (prefix or u == 4) else "high"
                return u, conf
            if rest in _GRAD and prefix:
                return 4, "low"
    return None, None


_POS = {
    "gk": "GK", "g": "GK", "goalkeeper": "GK", "keeper": "GK", "goalie": "GK",
    "d": "DEF", "def": "DEF", "defender": "DEF", "defense": "DEF", "back": "DEF",
    "fullback": "DEF", "centerback": "DEF", "cb": "DEF", "fb": "DEF",
    "m": "MID", "mf": "MID", "mid": "MID", "midfielder": "MID", "midfield": "MID",
    "f": "FWD", "fw": "FWD", "fwd": "FWD", "forward": "FWD", "striker": "FWD",
    "winger": "FWD", "att": "FWD", "attacker": "FWD",
}


def split_positions(raw):
    """Return (primary, secondary) position groups, '' when missing/unknown."""
    toks = [t for t in re.split(r"[/,\-\s]+", (raw or "").strip()) if t]
    out = []
    for t in toks:
        g = _POS.get(re.sub(r"[^a-z]", "", t.lower()))
        if g and g not in out:
            out.append(g)
    return (out[0] if out else ""), (out[1] if len(out) > 1 else "")


def current_season(today=None):
    """The season whose rosters are 'current': new rosters go up around August."""
    today = today or datetime.date.today()
    return today.year if today.month >= 8 else today.year - 1


def slugify(name):
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
