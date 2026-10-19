"""Film scores from several places, each kept separately.

* eiga.com     — average user rating out of 5 and review count (always; read from
                 the film page the scan already fetches)
* TMDB         — vote average out of 10 (needs TMDB_API_KEY); also gives the IMDb id
* OMDb         — IMDb rating, Rotten Tomatoes (critics) and Metacritic (needs
                 OMDB_API_KEY, free at omdbapi.com; uses the IMDb id from TMDB)

Scores are refreshed weekly while a film is showing.
"""

from __future__ import annotations

import os
import re

import requests

EIGA_RATING_RE = re.compile(r"(\d\.\d)\s*全\s*([\d,]+)\s*件")

# Below these vote counts a score is too noisy to show.
MIN_VOTES = {"eiga": 3, "tmdb": 20, "imdb": 50}


def parse_eiga_rating(text: str) -> dict | None:
    """'3.8全35件' -> {'v': 3.8, 'n': 35}"""
    m = EIGA_RATING_RE.search(re.sub(r"\s+", " ", text))
    if not m:
        return None
    v, n = float(m.group(1)), int(m.group(2).replace(",", ""))
    if n == 0 or v == 0:
        return None
    return {"v": v, "n": n}


def _tmdb_request(session: requests.Session, path: str, params: dict | None = None) -> dict:
    key = os.environ["TMDB_API_KEY"]
    params = dict(params or {})
    headers = {}
    if len(key) > 40:            # v4 "API Read Access Token"
        headers["Authorization"] = f"Bearer {key}"
    else:                        # v3 "API Key"
        params["api_key"] = key
    r = session.get(f"https://api.themoviedb.org/3{path}", params=params, headers=headers, timeout=20)
    r.raise_for_status()
    return r.json()


def tmdb_details(session: requests.Session, tmdb_id: int) -> dict | None:
    """Language, vote average/count, IMDb id and English title for a TMDB film."""
    if not os.environ.get("TMDB_API_KEY") or not tmdb_id:
        return None
    try:
        d = _tmdb_request(session, f"/movie/{tmdb_id}", {"language": "en-US"})
    except Exception as exc:
        print(f"  TMDb details failed for {tmdb_id}: {exc}")
        return None
    out = {
        "lang": d.get("original_language"),
        "imdb_id": d.get("imdb_id") or None,
        "tmdb_title": d.get("title"),
        "genre_ids": [g.get("id") for g in d.get("genres", []) if g.get("id")],
    }
    if d.get("vote_count"):
        out["tmdb"] = {"v": round(float(d.get("vote_average") or 0), 1), "n": int(d["vote_count"])}
    return out


def omdb_scores(session: requests.Session, imdb_id: str) -> dict | None:
    """IMDb / Rotten Tomatoes / Metacritic via OMDb."""
    key = os.environ.get("OMDB_API_KEY")
    if not key or not imdb_id:
        return None
    try:
        r = session.get("https://www.omdbapi.com/", params={"i": imdb_id, "apikey": key}, timeout=20)
        r.raise_for_status()
        d = r.json()
    except Exception as exc:
        print(f"  OMDb failed for {imdb_id}: {exc}")
        return None
    if d.get("Response") != "True":
        return None
    out: dict = {}
    try:
        votes = int(str(d.get("imdbVotes", "0")).replace(",", "") or 0)
        if d.get("imdbRating") not in (None, "N/A"):
            out["imdb"] = {"v": float(d["imdbRating"]), "n": votes}
    except ValueError:
        pass
    for src in d.get("Ratings", []):
        name, val = src.get("Source"), str(src.get("Value", ""))
        if name == "Rotten Tomatoes" and val.endswith("%"):
            out["rt"] = int(val[:-1])
        elif name == "Metacritic" and "/" in val:
            out["mc"] = int(val.split("/")[0])
    if "mc" not in out and str(d.get("Metascore", "")).isdigit():
        out["mc"] = int(d["Metascore"])
    return out


def public_scores(scores: dict) -> dict:
    """Drop scores with too few votes; add 'avg' (0–100) used only for sorting."""
    out = {}
    for k in ("eiga", "tmdb", "imdb"):
        s = scores.get(k)
        if s and s.get("n", 0) >= MIN_VOTES[k]:
            out[k] = s
    for k in ("rt", "mc"):
        if scores.get(k) is not None:
            out[k] = scores[k]
    norm = []
    if "eiga" in out:
        norm.append(out["eiga"]["v"] * 20)
    if "tmdb" in out:
        norm.append(out["tmdb"]["v"] * 10)
    if "imdb" in out:
        norm.append(out["imdb"]["v"] * 10)
    if "rt" in out:
        norm.append(out["rt"])
    if "mc" in out:
        norm.append(out["mc"])
    if norm:
        out["avg"] = round(sum(norm) / len(norm))
    return out
