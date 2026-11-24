import pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent / "scripts"))
from scrape import parse_roster, validate
from common import class_to_used, split_positions

LIST = "<h1>2026 Women's Soccer Roster</h1><ul>" + "".join(
    f'<li class="sidearm-roster-player"><div class="sidearm-roster-player-jersey-number">{i}</div>'
    f'<div class="sidearm-roster-player-name"><a>Player {i}</a></div>'
    f'<div class="sidearm-roster-player-position"><span class="sidearm-roster-player-position-long-short">{"M/F" if i%3 else "GK"}</span></div>'
    f'<div class="sidearm-roster-player-academic-year">{["Fr.","So.","Jr.","Sr.","R-Fr.","Gr."][i%6]}</div></li>' for i in range(20)) + "</ul>"
TABLE = "<table><thead><tr><th>No.</th><th>Name</th><th>Pos.</th><th>Cl.</th></tr></thead><tbody>" + "".join(
    f'<tr><td>{i}</td><td><a>Player {i}</a></td><td>{"Defender" if i%2 else "Midfielder"}</td><td>{["Fr.","So.","Jr.","Sr."][i%4]}</td></tr>' for i in range(18)) + "</tbody></table>"

def test_list():
    rows, season = parse_roster(LIST)
    assert len(rows) == 20 and season == 2026 and validate(rows) == ""

def test_table():
    rows, _ = parse_roster(TABLE)
    assert len(rows) == 18 and validate(rows) == ""

def test_garbage_rejected():
    rows, _ = parse_roster("<html><body>Access page</body></html>")
    assert validate(rows)

def test_classes():
    for raw, want in [("Fr.", 1), ("R-So.", 2), ("RS Jr.", 3), ("Redshirt Senior", 4), ("5th", 4), ("Graduate", 4), ("Sr.", 4)]:
        assert class_to_used(raw)[0] == want, raw
    assert class_to_used("??")[0] is None

def test_positions():
    assert split_positions("M/F") == ("MID", "FWD")
    assert split_positions("Goalkeeper") == ("GK", "")
    assert split_positions("D, M") == ("DEF", "MID")
