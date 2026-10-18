"""Daily scan: fetch every theater page, build site/data/showtimes.json.

    python -m scraper.run                 # full scan
    python -m scraper.run --only 3044     # one theater (eiga id), handy for debugging
    python -m scraper.run --from-dir debug/  # parse saved HTML instead of fetching
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import random
import re
import sys
import time
from pathlib import Path
from zoneinfo import ZoneInfo

import requests
import yaml

from .eiga import RATING_RE, parse_movie_page, parse_theater_page
from .romaji import JP_RE, country_en, latin_part, name_romaji, to_romaji
from .ratings import omdb_scores, public_scores, tmdb_details
from .language import LANG_NAMES, audio_subs, film_language, tmdb_lookup
from .translate import has_japanese, price_label_en, translate_titles

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config" / "theaters.yaml"
TITLES = ROOT / "config" / "titles.yaml"
DATA_DIR = ROOT / "site" / "data"
DEBUG_DIR = ROOT / "debug"
JST = ZoneInfo("Asia/Tokyo")

DELAY = float(os.environ.get("SCRAPE_DELAY", "2.5"))     # seconds between requests
MAX_NEW_MOVIES = int(os.environ.get("MAX_NEW_MOVIES", "350"))
REFRESH_DAYS = 7   # re-check scores of films still showing this often
DAYS_AHEAD = 7


def theater_id(url: str) -> str:
    m = re.search(r"/theater/\d+/\d+/(\d+)/?", url)
    return m.group(1) if m else url


class Fetcher:
    def __init__(self) -> None:
        repo = os.environ.get("GITHUB_REPOSITORY", "personal project")
        self.s = requests.Session()
        self.s.headers.update({
            "User-Agent": f"tokyo-cinema-listings/1.0 (personal, non-commercial; {repo})",
            "Accept-Language": "ja,en;q=0.8",
        })
        self.last = 0.0

    def get(self, url: str) -> str:
        for attempt in range(3):
            wait = DELAY + random.uniform(0, 1) - (time.time() - self.last)
            if wait > 0:
                time.sleep(wait)
            self.last = time.time()
            try:
                r = self.s.get(url, timeout=30)
                if r.status_code == 200:
                    if not r.encoding or r.encoding.lower() == "iso-8859-1":
                        r.encoding = r.apparent_encoding or "utf-8"
                    return r.text
                if r.status_code in (403, 404):
                    raise RuntimeError(f"HTTP {r.status_code}")
                err = f"HTTP {r.status_code}"
            except requests.RequestException as exc:
                err = str(exc)
            time.sleep(5 * (attempt + 1))
        raise RuntimeError(err)


def load_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="comma-separated eiga theater ids")
    ap.add_argument("--from-dir", help="parse saved <id>.html files instead of fetching")
    ap.add_argument("--no-movies", action="store_true", help="skip fetching film pages")
    args = ap.parse_args()

    now = dt.datetime.now(JST)
    today = now.date()
    last_day = today + dt.timedelta(days=DAYS_AHEAD - 1)
    cfg = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    title_overrides = {}
    if TITLES.exists():
        title_overrides = {str(k): v for k, v in (yaml.safe_load(TITLES.read_text(encoding="utf-8")) or {}).items()}

    theaters = [t for t in cfg["theaters"] if t.get("enabled", True)]
    if args.only:
        wanted = set(args.only.split(","))
        theaters = [t for t in theaters if theater_id(t["eiga"]) in wanted]

    fetcher = Fetcher()
    DEBUG_DIR.mkdir(exist_ok=True)
    movies: dict = load_json(DATA_DIR / "movies.json", {})
    # Repair records saved before the rating/country fix (country stored as rating).
    for m in movies.values():
        r = m.get("rating")
        if r and not RATING_RE.match(r):
            m.setdefault("country", r)
            del m["rating"]
    out_theaters, screenings = [], []
    seen_movie_ids: set[str] = set()

    for t in theaters:
        tid = theater_id(t["eiga"])
        entry = {
            "id": tid,
            "name_en": t["name_en"], "name_ja": t["name_ja"],
            "area_en": t.get("area_en"), "area_ja": t.get("area_ja"),
            "type": t.get("type", "arthouse"),
            "eiga": t["eiga"],
        }
        print(f"[{tid}] {t['name_en']} … ", end="", flush=True)
        try:
            if args.from_dir:
                html = (Path(args.from_dir) / f"{tid}.html").read_text(encoding="utf-8")
            else:
                html = fetcher.get(t["eiga"])
            page = parse_theater_page(html, today)
        except Exception as exc:
            entry.update(status="error", error=str(exc)[:200])
            out_theaters.append(entry)
            print(f"ERROR {exc}")
            continue

        prices = [dict(p, label_en=price_label_en(p["label_ja"])) for p in page.prices]
        discounts = [dict(p, label_en=price_label_en(p["label_ja"])) for p in page.discounts]
        general = t.get("price_general") or next(
            (p["yen"] for p in prices if p["label_ja"].startswith("一般")), None) or next(
            (p["yen"] for p in prices if "一般" in p["label_ja"]), None)
        entry.update(prices=prices, discounts=discounts, price_general=general,
                     price_varies=bool(page.price_note and not general),
                     official_url=t.get("official_url") or page.official_url)
        if page.notice:
            entry["notice"] = page.notice

        n = 0
        for s in page.screenings:
            if not (today.isoformat() <= s.date <= last_day.isoformat()):
                continue
            screenings.append({"t": tid, "m": s.movie_id, "d": s.date, "s": s.start,
                               "e": s.end, "f": s.fmt})
            n += 1
        showing = {sc["m"] for sc in screenings if sc["t"] == tid}
        for mid, stub in page.movies.items():
            if mid not in showing:      # upcoming films with no showings this week
                continue
            seen_movie_ids.add(mid)
            m = movies.setdefault(mid, {"title_ja": stub.title_ja})
            m["title_ja"] = stub.title_ja
            if stub.runtime and not m.get("runtime"):
                m["runtime"] = stub.runtime
            if stub.poster:
                m["poster_small"] = stub.poster

        if n == 0 and page.notice:
            entry["status"] = "closed"
        elif n == 0:
            entry["status"] = "empty" if page.movies or page.prices else "unparsed"
            (DEBUG_DIR / f"{tid}.html").write_text(html, encoding="utf-8")
        else:
            entry["status"] = "ok"
        entry["count"] = n
        out_theaters.append(entry)
        print(f"{len(page.movies)} films, {n} screenings")

    # Film details (English title, year, director, eiga.com rating). New films first,
    # then a weekly refresh of films still showing so their ratings stay current.
    week_ago = (today - dt.timedelta(days=REFRESH_DAYS)).isoformat()

    def due(field: str) -> list[str]:
        new = [mid for mid in seen_movie_ids if not movies[mid].get(field)]
        stale = sorted((mid for mid in seen_movie_ids
                        if movies[mid].get(field) and movies[mid][field] <= week_ago),
                       key=lambda mid: movies[mid][field])
        return (new + stale)[:MAX_NEW_MOVIES]

    if not args.no_movies and not args.from_dir:
        todo = due("fetched")
        print(f"Fetching {len(todo)} film pages")
        for mid in todo:
            try:
                info = parse_movie_page(fetcher.get(f"https://eiga.com/movie/{mid}/"))
                rating = info.pop("scores_eiga", None)
                movies[mid].update(info)
                scores = movies[mid].setdefault("scores", {})
                if rating:
                    scores["eiga"] = rating
                movies[mid]["fetched"] = today.isoformat()
            except Exception as exc:
                print(f"  film {mid}: {exc}")

    # TMDB: original language, English title, vote average, IMDb id (needs TMDB_API_KEY).
    # OMDb: IMDb rating, Rotten Tomatoes, Metacritic (needs OMDB_API_KEY + the IMDb id).
    if os.environ.get("TMDB_API_KEY") and not args.from_dir:
        todo = due("tmdb_checked")
        print(f"Checking {len(todo)} films on TMDB")
        for mid in todo:
            m = movies[mid]
            if not m.get("tmdb_id"):
                hit = tmdb_lookup(fetcher.s, m.get("title_ja"), m.get("title_en"), m.get("year"))
                time.sleep(0.25)
                if hit:
                    m["tmdb_id"] = hit["tmdb_id"]
                    m["lang"] = hit["lang"]
            m["tmdb_checked"] = today.isoformat()
            if not m.get("tmdb_id"):
                continue
            d = tmdb_details(fetcher.s, m["tmdb_id"])
            time.sleep(0.25)
            if not d:
                continue
            if d.get("lang"):
                m["lang"] = d["lang"]
            if d.get("imdb_id"):
                m["imdb_id"] = d["imdb_id"]
            t = d.get("tmdb_title")
            if t and not has_japanese(t) and t != m.get("title_ja"):
                m["title_en_tmdb"] = t
            if d.get("tmdb"):
                m.setdefault("scores", {})["tmdb"] = d["tmdb"]

    if os.environ.get("OMDB_API_KEY") and not args.from_dir:
        todo = [mid for mid in due("omdb_checked") if movies[mid].get("imdb_id")]
        print(f"Checking {len(todo)} films on OMDb")
        for mid in todo:
            m = movies[mid]
            got = omdb_scores(fetcher.s, m["imdb_id"])
            time.sleep(0.25)
            m["omdb_checked"] = today.isoformat()
            if got:
                sc = m.setdefault("scores", {})
                for k in ("imdb", "rt", "mc"):
                    sc.pop(k, None)
                sc.update(got)

    n_tr = translate_titles({k: movies[k] for k in seen_movie_ids})
    if n_tr:
        print(f"Translated {n_tr} titles")
    for mid, en in title_overrides.items():
        if mid in movies:
            movies[mid]["title_en_override"] = en
    for mid in seen_movie_ids:
        movies[mid]["last_seen"] = today.isoformat()

    ok = sum(1 for t in out_theaters if t["status"] == "ok")
    print(f"\n{ok}/{len(out_theaters)} theaters parsed, {len(screenings)} screenings")
    if not screenings:
        print("No screenings parsed at all — keeping yesterday's data. "
              "Check the debug-html artifact; eiga.com may have changed its layout.")
        return 1

    # Drop films not seen for 60 days to keep the cache small.
    cutoff = (today - dt.timedelta(days=60)).isoformat()
    movies = {k: v for k, v in movies.items() if v.get("last_seen", today.isoformat()) >= cutoff}

    # Audio language + subtitles for every screening.
    for sc in screenings:
        lang, sure = film_language(movies[sc["m"]])
        info = audio_subs(sc["f"], lang, sure)
        sc["a"], sc["sub"] = info["a"], info["sub"]
        if not info["sure"]:
            sc["guess"] = 1

    screenings.sort(key=lambda s: (s["d"], s["s"], s["t"]))
    public_movies = {k: _public_movie(movies[k]) for k in seen_movie_ids}

    # Romaji for every Japanese string the app shows: {japanese: romaji}.
    jp_strings: set[str] = set()
    names: set[str] = set()
    for m in public_movies.values():
        jp_strings.update(x for x in (m.get("ja"), m.get("en")) if x)
        if m.get("director"):
            names.add(m["director"])
    for t in out_theaters:
        jp_strings.update(x for x in (t.get("name_ja"), t.get("area_ja"), t.get("notice")) if x)
        for p in t.get("prices", []) + t.get("discounts", []):
            jp_strings.add(p["label_ja"])
    for sc in screenings:
        if sc.get("f"):
            jp_strings.update(sc["f"].split(" "))
    romaji = {x: to_romaji(x) for x in sorted(jp_strings) if JP_RE.search(x)}
    romaji.update({x: name_romaji(x) for x in sorted(names) if JP_RE.search(x)})
    # Language names are single words in lower case: 英語 -> eigo, イタリア語 -> itariago
    romaji.update({ja: (to_romaji(ja) or ja).replace(" ", "").lower() for _, ja in LANG_NAMES.values()})
    romaji.update({"日本語吹替": "nihongo fukikae", "台詞なし": "serifu nashi"})

    data = {
        "generated_at": now.isoformat(timespec="minutes"),
        "today": today.isoformat(),
        "theaters": out_theaters,
        "movies": public_movies,
        "romaji": romaji,
        "languages": LANG_NAMES,
        "screenings": screenings,
    }
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not args.only:
        (DATA_DIR / "showtimes.json").write_text(
            json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    else:
        print(json.dumps(data, ensure_ascii=False, indent=1)[:4000])
    (DATA_DIR / "movies.json").write_text(
        json.dumps(movies, ensure_ascii=False, indent=0, sort_keys=True), encoding="utf-8")
    return 0


def _public_movie(m: dict) -> dict:
    human = m.get("title_en_override") or latin_part(m.get("title_en")) or m.get("title_en_tmdb")
    title_en = human or m.get("title_en_auto")
    out = {"ja": m.get("title_ja"), "en": title_en, "en_auto": bool(not human and title_en)}
    for k in ("year", "runtime", "country", "director", "rating", "lang", "tmdb_id", "imdb_id"):
        if m.get(k):
            out[k] = m[k]
    if m.get("country"):
        out["country_en"] = country_en(m["country"])
    if m.get("poster_small") or m.get("poster"):
        out["poster"] = m.get("poster_small") or m.get("poster")
    scores = public_scores(m.get("scores") or {})
    if scores:
        out["scores"] = scores
    return out


if __name__ == "__main__":
    sys.exit(main())
