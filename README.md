# Tokyo cinema listings 東京の映画館

A phone-friendly page of what's showing in Tokyo, built around the city's mini-theaters
(ミニシアター), revival houses (名画座), community cinemas and cultural institutions, with
the big central multiplexes one tap away. It shows each day's screening times, end times
where known, the **audio language and subtitles** of every showing, format labels (IMAX,
etc.), and each theater's ticket prices. You can filter to English-audio or
English-subtitled showings.

A GitHub Actions job scans every theater once a day at about **5:00 JST** and republishes
the site on GitHub Pages. Nothing runs on your own computer.

## How it works

```
GitHub Actions, 04:50 JST daily
  └─ scraper/run.py
       ├─ fetches each theater's page on eiga.com (映画.com), ~2.5 s apart
       ├─ parses films, dates, times, formats and the 料金 (price) table
       ├─ fetches new films' pages once for English title / year / country / director (cached)
       ├─ optional: looks each new film up on TMDB for its original language (cached)
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
5. Your site is at `https://<your-username>.github.io/tokyo-cinema/`. On iPhone, open it in
   Safari and use *Share → Add to Home Screen* to get an app icon.

### Recommended: TMDB for film languages (free)

Without it, the language is guessed from the production country, which fails for
co-productions and films like Orson Welles' *The Trial* (a French/German/Italian
production in English). Create a free account at <https://www.themoviedb.org>, request
an API key under **Settings → API**, and add it as a repository secret named
`TMDB_API_KEY` (either the "API Key" or the "API Read Access Token" works). TMDB also
supplies English titles for many Japanese films. Each film is looked up once.

### Optional: English titles for Japanese-only films

eiga.com gives an English/original title (原題・英題) for most foreign films, but not for
many Japanese ones, and TMDB won't know every small release. To fill the rest in automatically, add a repository secret named
`ANTHROPIC_API_KEY` (**Settings → Secrets and variables → Actions**). Each title is
translated once and cached; machine-translated titles are marked *auto* on the page.
To fix a title by hand, add it to `config/titles.yaml`.

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
| `scraper/language.py` | Audio/subtitle rules, country → language map, TMDB lookup |
| `scraper/translate.py` | Price-label translations and optional title translation |
| `site/` | The static site (`index.html`, `app.js`, `style.css`, `data/`) |
| `tests/` | Parser and language tests |
