# Tokyo cinema listings 東京の映画館

A phone-friendly page of what's showing in Tokyo, built around the city's mini-theaters
(ミニシアター), revival houses (名画座), community cinemas and cultural institutions, with
the big central multiplexes one tap away. It shows each day's screening times, end times
where known, the **audio language and subtitles** of every showing, format labels (IMAX,
etc.), each theater's ticket prices, and each film's scores (eiga.com users, plus IMDb,
Rotten Tomatoes, Metacritic and TMDB when keys are set). You can filter to English-audio
or English-subtitled showings and sort by rating.

It installs on your phone as a standalone app: its own icon, full screen with no browser
bar, and it works offline with the last scan saved on the phone. A GitHub Actions job
scans every theater once a day at about **5:00 JST** and publishes the listings on GitHub
Pages, and the app picks them up the next time you open it. Nothing runs on your own
computer.

## How it works

```
GitHub Actions, 04:50 JST daily
  └─ scraper/run.py
       ├─ fetches each theater's page on eiga.com (映画.com), ~2.5 s apart
       ├─ parses films, dates, times, formats and the 料金 (price) table
       ├─ fetches new films' pages once for English title / year / country / director (cached)
       ├─ optional: TMDB for original language, English title, score, IMDb id
       ├─ optional: OMDb for IMDb, Rotten Tomatoes and Metacritic scores
       │    (film details and scores are refreshed weekly while a film is showing)
       ├─ works out audio + subtitles for every showing (scraper/language.py)
       └─ writes site/data/showtimes.json  → committed, then deployed to Pages
```

**Why eiga.com?** It's the one source with a consistent page for nearly every Tokyo
cinema, from Laputa Asagaya to TOHO Hibiya, covering the full week and listing prices.
Scraping 55 different theater websites would mean 55 parsers that break independently.
eiga.com's robots.txt allows these theater and film pages for general crawlers; the
scraper identifies itself, waits between requests, and makes roughly 60–100 requests a
day. Keep it personal and non-commercial.

**Data sources.** Schedules, times, format labels and prices all come from eiga.com.
Film details come from each film's eiga.com page. TMDB (themoviedb.org) is an optional
second source for each film's original language and English title.

**How audio and subtitles are decided.**

| Listing says | Shown as |
| --- | --- |
| 吹替 (dubbed) | Audio: Japanese dub, no subtitles |
| 英語字幕 / English subtitles | Audio: original language, subtitles: English |
| 字幕 on a foreign film | Audio: original language, subtitles: Japanese |
| 字幕 on a Japanese film | Audio: Japanese, subtitles: Japanese (accessibility captions) |
| nothing, Japanese film | Audio: Japanese, no subtitles |
| nothing, foreign film | Audio: original language, subtitles: Japanese — marked *likely* |

The film's language comes from TMDB when available, otherwise from its production
country on eiga.com. Co-productions without TMDB data show "Original language" rather
than a guess. Anything not stated on the listing is marked *likely*.

**Why 5:00 JST?** Theaters update their listings in the evening (and post the following
week's schedule around Tuesday–Wednesday for Friday changeovers), so an early-morning
scan catches the previous night's changes and is ready before the day's first screenings.
The job is scheduled for 04:50 because GitHub often starts scheduled jobs several
minutes late.

## Setup (about 5 minutes)

1. Create a **public** repository on GitHub (e.g. `tokyo-cinema`). Pages on private repos
   needs a paid plan.
2. Add these files to it (push them, or upload them on github.com).
3. In the repo: **Settings → Pages → Build and deployment → Source: GitHub Actions**.
4. **Actions → Daily scan → Run workflow** for the first scan. It takes 3–5 minutes.
5. Install the app (below). The web address is
   `https://<your-username>.github.io/tokyo-cinema/`.

### Installing the app on Android

1. Open the address above in **Chrome** on your phone.
2. Tap **Install app** at the top of the page (or Chrome's ⋮ menu → **Install app**).
3. Tokyo Cinema appears in your app drawer and home screen like any other app.

Long-press the icon for shortcuts to *English-friendly showings* and *By theater*.
To uninstall, long-press the icon → **Uninstall**. (On iPhone: Safari → Share →
**Add to Home Screen**.)

### How the installed app behaves

- **Opening it** shows the saved listings instantly, then fetches the latest scan.
- **Offline** (subway, plane): you get the last scan and a note saying when it's from.
- **Before about 5:45 JST**, or if a scan failed, a note says today's update hasn't
  arrived and offers *Check again*.
- **Coming back to it** after 20 minutes or more refreshes the listings. Tap
  "Updated …" under the title to refresh at any time.
- **New versions** of the app install themselves; a note offers *Reload* when one is ready.

### Recommended: TMDB for film languages (free)

Without it, the language is guessed from the production country, which fails for
co-productions and films like Orson Welles' *The Trial* (a French/German/Italian
production in English). Create a free account at <https://www.themoviedb.org>, request
an API key under **Settings → API**, and add it as a repository secret named
`TMDB_API_KEY` (either the "API Key" or the "API Read Access Token" works). TMDB also
supplies English titles for many Japanese films. Each film is looked up once.

### Optional: IMDb, Rotten Tomatoes and Metacritic scores (free)

Every film gets its eiga.com user rating (out of 5) without any setup. For critics'
scores, get a free key at <https://www.omdbapi.com/apikey.aspx> (1,000 requests a day is
plenty) and add it as a secret named `OMDB_API_KEY`. OMDb needs the IMDb id that TMDB
provides, so set up TMDB too. Scores with very few votes are hidden. Small Japanese
releases often have only an eiga.com rating.

### Optional: English titles for Japanese-only films

eiga.com gives an English/original title (原題・英題) for most foreign films, but not for
many Japanese ones, and TMDB won't know every small release. To fill the rest in automatically, add a repository secret named
`ANTHROPIC_API_KEY` (**Settings → Secrets and variables → Actions**). Each title is
translated once and cached; machine-translated titles are marked *auto* on the page.
To fix a title by hand, add it to `config/titles.yaml`.

## Running it

The app is a website, so "running" it means letting GitHub do the work:

- **Every day**: nothing to do. The scan runs at 04:50 JST and the site updates itself.
- **On demand**: GitHub → your repo → **Actions → Daily scan → Run workflow**
  (works from the GitHub mobile app too).
- **Using it**: open the Tokyo Cinema app on your phone.

To run it on your own computer instead (Python 3.10+):

```bash
pip install -r requirements.txt
python -m scraper.run                 # scan (about 3–5 minutes)
python -m http.server -d site 8000    # then open http://localhost:8000
```

Set `TMDB_API_KEY`, `OMDB_API_KEY` or `ANTHROPIC_API_KEY` as environment variables to use
those optional sources locally.

## Customising

- **Theaters**: `config/theaters.yaml`. Copy a theater's URL from
  <https://eiga.com/theater/13/>, pick a `type`, and give it English and Japanese names.
  Set `enabled: false` to skip one, or `price_general: 1800` to override its price.
- **Scan time**: the `cron` line in `.github/workflows/daily-scan.yml` (it's in UTC;
  JST = UTC + 9).
- **Default filters**: the page starts with multiplexes hidden; tap *Multiplex* to include
  them. Your choice is remembered on that device.

## When something breaks

- The footer's **Scan status** lists theaters that failed or showed nothing.
  "No screenings this week" is normal for venues with occasional programs (e.g. the
  Institut français).
- Pages that couldn't be parsed are saved for 7 days as the **debug-html** artifact on
  the workflow run.
- If eiga.com changes its layout so that nothing parses, the job fails (GitHub emails you)
  and the site keeps showing the previous day's listings.
- Run the parser tests with `python -m unittest discover tests`. Debug one theater locally
  with `python -m scraper.run --only 3044`.
- GitHub pauses scheduled workflows in repos with no activity for 60 days. The daily data
  commit normally counts as activity; if the schedule ever stops, re-enable it from the
  Actions tab.

## Files

| Path | What it is |
| --- | --- |
| `config/theaters.yaml` | The 55 theaters (54 on by default), with English/Japanese names and types |
| `config/titles.yaml` | Manual English titles |
| `scraper/eiga.py` | Page parsers (layout-tolerant: no reliance on CSS class names) |
| `scraper/run.py` | The daily job |
| `scraper/ratings.py` | Score parsing and TMDB / OMDb lookups |
| `scraper/language.py` | Audio/subtitle rules, country → language map, TMDB lookup |
| `scraper/translate.py` | Price-label translations and optional title translation |
| `site/` | The app (`index.html`, `app.js`, `style.css`, `data/`) |
| `site/manifest.webmanifest`, `site/icons/` | App name, icons and shortcuts for installing |
| `site/sw.js` | Offline support (saves the app and last listings on the phone) |
| `tests/` | Parser, language and score tests |
