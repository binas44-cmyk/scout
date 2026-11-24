# Roster Gaps

Women's college soccer roster gap finder. Starts with NCAA Division II (255 programs).
A GitHub job refreshes rosters every Monday and the site rebuilds itself.

## Put it online (about 10 minutes, free)
1. Create a new GitHub repository (public is simplest) and upload everything in this folder, keeping the folder structure. The hidden `.github` folder must come with it.
2. Repo **Settings → Pages**: Source "Deploy from a branch", branch `main`, folder `/docs`. Your site address appears there.
3. Repo **Settings → Secrets and variables → Actions → Variables**: add `CONTACT_EMAIL` with an address schools can reach you at. It goes in the scraper's user agent.
4. Repo **Actions → Refresh rosters → Run workflow** to do the first fill-in now instead of waiting for Monday.

## What runs
- `scripts/scrape.py` reads each school's official roster page (one request per school, obeys robots.txt, identifies itself). Schools that block bots or return a page it can't read are flagged in `data/status.json` and keep their last good roster.
- `scripts/build.py` turns rosters into `docs/data.json` and `docs/rosters.csv`.
- `docs/index.html` is the dashboard. It reads `data.json`.

## Maintaining it
- **Add a school:** add a row to `data/schools.csv`.
- **A school blocks bots:** set `source` to `manual` in `schools.csv`, put its roster in `data/manual/<school-slug>.csv` (columns: school,jersey,name,pos_raw,class_raw) and fill `manual_season` and `manual_date`. Ferris State is set up this way.
- **Check coverage:** open `data/status.json`, or look at the Actions log after each run. Statuses: `ok`, `blocked`, `failed`.
- **New season:** when schools post new rosters (usually August) the weekly refresh picks them up. Everyone's class years roll forward automatically.
- **Other divisions:** add rows to `schools.csv` with a different conference.

## Known limits
- Positions are only D, M, F, GK because that is what school sites list.
- Eligibility is estimated from class year. Transfers, extra COVID years and unlisted recruits are not modeled.
- The scraper reads the standard Sidearm Sports roster markup (list and table views). I could not test it against live school sites from where I built it, so expect some schools to need attention after the first run. Several use different roster paths (notes in `schools.csv`).
- Watchlist, commitments and depth targets are saved in each visitor's own browser. Sharing them between recruiters needs a database and logins.
