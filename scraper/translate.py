"""Optional: English titles for films eiga.com lists only in Japanese.

Runs only when an ANTHROPIC_API_KEY secret is set in the repository.
Results are cached in movies.json, so each title is translated once.
"""

from __future__ import annotations

import json
import os
import re

import requests

API_URL = "https://api.anthropic.com/v1/messages"
MODEL = os.environ.get("TRANSLATE_MODEL", "claude-haiku-5-5")

PRICE_LABELS = [
    ("大学生・専門学校生", "University/college"), ("大学・専門", "University/college"),
    ("大学生", "University"), ("専門", "Vocational school"), ("高校生", "High school"),
    ("中学生", "Junior high"), ("中・高校生", "Junior/senior high"), ("小学生", "Elementary"),
    ("幼児", "Preschool"), ("小人", "Child"), ("シニア", "Senior"), ("60歳以上", "Senior 60+"),
    ("障がい者", "Disability"), ("障害者", "Disability"), ("一般", "General"),
    ("サービスデー", "Service day"), ("ファーストデー", "First day (1st)"),
    ("レディースデー", "Ladies' day"), ("メンズデー", "Men's day"),
    ("夫婦", "Couple"), ("会員", "Member"), ("年会費", "Annual membership"),
    ("レイト", "Late show"), ("モーニング", "Morning show"), ("火曜", "Tuesday"),
    ("水曜", "Wednesday"), ("月曜", "Monday"), ("木曜", "Thursday"), ("金曜", "Friday"),
    ("2本立て", "Double bill"), ("1本立て", "Single feature"), ("最終回", "Last show"),
    ("前売", "Advance"), ("当日", "Same day"), ("割引", "Discount"),
]


def price_label_en(label_ja: str) -> str | None:
    hits: list[tuple[int, str]] = []
    used: list[str] = []
    # longest Japanese keys first, so 大学生・専門学校生 wins over 大学生
    for ja, en in sorted(PRICE_LABELS, key=lambda x: -len(x[0])):
        if ja in label_ja and not any(ja in u for u in used):
            used.append(ja)
            if en not in [e for _, e in hits]:
                hits.append((label_ja.index(ja), en))
    hits.sort()
    return " · ".join(e for _, e in hits[:3]) or None


def has_japanese(s: str) -> bool:
    return bool(re.search(r"[぀-ヿ㐀-鿿]", s or ""))


def translate_titles(movies: dict, limit: int = 60) -> int:
    """Fill title_en_auto for movies lacking an English title. Returns count."""
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        return 0
    todo = [
        (mid, m["title_ja"]) for mid, m in movies.items()
        if not m.get("title_en") and not m.get("title_en_tmdb") and not m.get("title_en_auto") and has_japanese(m.get("title_ja", ""))
    ][:limit]
    if not todo:
        return 0

    listing = "\n".join(f"{mid}\t{title}" for mid, title in todo)
    prompt = (
        "Translate these Japanese film titles into natural English. If a film has a known "
        "official English title, use it. Keep any part already in English. Reply with JSON only: "
        'an object mapping each id to its English title.\n\n' + listing
    )
    try:
        r = requests.post(
            API_URL,
            headers={
                "x-api-key": key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={"model": MODEL, "max_tokens": 4000,
                  "messages": [{"role": "user", "content": prompt}]},
            timeout=90,
        )
        r.raise_for_status()
        text = "".join(b.get("text", "") for b in r.json().get("content", []))
        m = re.search(r"\{.*\}", text, re.S)
        result = json.loads(m.group(0)) if m else {}
    except Exception as exc:  # translation is a nice-to-have; never fail the run
        print(f"  translation skipped: {exc}")
        return 0

    n = 0
    for mid, en in result.items():
        if mid in movies and isinstance(en, str) and en.strip():
            movies[mid]["title_en_auto"] = en.strip()
            n += 1
    return n
