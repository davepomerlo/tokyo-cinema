"""Parsers for eiga.com (映画.com) theater and movie pages.

The parsers deliberately avoid depending on CSS class names, which change
whenever a site is redesigned. Instead they rely on things that are stable
in meaning:

* a film title is a link to /movie/<id>/ inside a heading;
* everything after that heading (in document order) and before the next
  film heading belongs to that film;
* a schedule is either a table whose header cells are dates (M/D) and whose
  body cells hold times (H:MM), a table whose rows start with a date, or a
  plain list of "date → times" text.
"""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass, field

from bs4 import BeautifulSoup, NavigableString, Tag

from .ratings import parse_eiga_rating

MOVIE_HREF = re.compile(r"(?:https?://eiga\.com)?/movie/(\d+)/?(?:[?#].*)?$")
DATE_RE = re.compile(r"(?<![\d:])(\d{1,2})\s*/\s*(\d{1,2})(?![\d:])")
DATA_DATE_RE = re.compile(r"^(20\d{2})-?(\d{2})-?(\d{2})$")
TIME_RANGE_RE = re.compile(r"(\d{1,2}:\d{2})\s*[～~〜\-－–—]\s*(\d{1,2}:\d{2})")
TIME_RE = re.compile(r"(?<![\d/])(\d{1,2}):(\d{2})(?!\d)")
RATING_RE = re.compile(r"^(G|PG-?12|R-?15\+?|R-?18\+?)$")
RUNTIME_RE = re.compile(r"(\d{2,3})\s*分")
YEN_RE = re.compile(
    r"([^\s\d：:¥￥,円（）()／/]{1,24}?)\s*(?:[（(][^）)]{0,20}[）)])?\s*[：:]?\s*[¥￥]?\s*([\d,]{3,6})\s*円"
)

# Words that label a screening format (subtitles, dubbing, premium screens…).
FORMAT_WORDS = [
    "日本語字幕", "英語字幕", "外国語字幕", "字幕", "吹替", "吹き替え",
    "English Subtitles", "English subtitles", "ENGLISH SUBTITLES", "English Subtitled",
    "ENG SUB", "Eng Sub", "with English subtitles", "英語字幕付", "英語字幕版",
    "日本語字幕付", "原語版", "IMAX", "ドルビーシネマ",
    "Dolby Cinema", "DOLBY", "ドルビーアトモス", "Dolby Atmos", "4DX", "MX4D",
    "ScreenX", "SCREENX", "ULTRA 4DX", "3D", "2D", "極上音響", "轟音", "爆音",
    "バリアフリー", "日本語音声ガイド", "35mm", "16mm", "デジタル", "GTテクノロジー",
    "BESTIA", "プレミアムシアター", "IMAXレーザー", "応援上映", "発声可能",
]
FORMAT_RE = re.compile("|".join(re.escape(w) for w in sorted(FORMAT_WORDS, key=len, reverse=True)))


@dataclass
class Screening:
    movie_id: str
    date: str          # YYYY-MM-DD
    start: str         # HH:MM (may be 24:00+ for late-night shows)
    end: str | None    # HH:MM when the page gives it (usually last show only)
    fmt: str | None    # 字幕 / 吹替 / IMAX … or None
    link: str | None   # theater booking/schedule link if present


@dataclass
class MovieStub:
    movie_id: str
    title_ja: str
    runtime: int | None = None
    poster: str | None = None


@dataclass
class TheaterPage:
    movies: dict[str, MovieStub] = field(default_factory=dict)
    screenings: list[Screening] = field(default_factory=list)
    prices: list[dict] = field(default_factory=list)
    official_url: str | None = None
    notice: str | None = None          # e.g. temporary closure message
    price_note: str | None = None      # e.g. "作品によって料金に差異あり"
    discounts: list[dict] = field(default_factory=list)


# ── helpers ────────────────────────────────────────────────────────────────

def clean(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def norm_time(t: str) -> str:
    h, m = t.split(":")
    return f"{int(h):02d}:{m}"


def infer_date(month: int, day: int, today: dt.date) -> str | None:
    """Turn M/D into a full date, choosing the year closest to today."""
    best = None
    for year in (today.year - 1, today.year, today.year + 1):
        try:
            d = dt.date(year, month, day)
        except ValueError:
            continue
        if best is None or abs((d - today).days) < abs((best - today).days):
            best = d
    return best.isoformat() if best else None


def cell_date(cell: Tag, today: dt.date) -> str | None:
    for attr in ("data-date", "data-day", "datetime"):
        v = cell.get(attr)
        if v:
            m = DATA_DATE_RE.match(str(v).strip())
            if m:
                return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    text = clean(cell.get_text(" "))
    if TIME_RE.search(text):
        return None
    m = DATE_RE.search(text)
    if m:
        return infer_date(int(m.group(1)), int(m.group(2)), today)
    return None


def extract_times(text: str) -> list[tuple[str, str | None]]:
    """'9:50 12:15 15:00～17:14' -> [('09:50',None), ('12:15',None), ('15:00','17:14')]"""
    out: list[tuple[str, str | None]] = []
    consumed: list[tuple[int, int]] = []
    for m in TIME_RANGE_RE.finditer(text):
        out.append((m.start(), norm_time(m.group(1)), norm_time(m.group(2))))
        consumed.append((m.start(), m.end()))
    for m in TIME_RE.finditer(text):
        if any(a <= m.start() < b for a, b in consumed):
            continue
        out.append((m.start(), norm_time(m.group(0)), None))
    out.sort()
    return [(s, e) for _, s, e in out]


def external_link(el: Tag) -> str | None:
    for a in el.find_all("a", href=True):
        href = a["href"].strip()
        if href.startswith("http") and "eiga.com" not in href:
            return href
    return None


def find_format(text: str) -> str | None:
    found = FORMAT_RE.findall(text)
    if not found:
        return None
    # keep order, drop duplicates
    seen: list[str] = []
    for f in found:
        if f not in seen:
            seen.append(f)
    return " ".join(seen)


# ── theater page ───────────────────────────────────────────────────────────

def _movie_headings(soup: BeautifulSoup) -> dict[int, tuple[Tag, str, str]]:
    heads: dict[int, tuple[Tag, str, str]] = {}
    for a in soup.find_all("a", href=True):
        m = MOVIE_HREF.match(a["href"].strip())
        if not m:
            continue
        h = a.find_parent(["h1", "h2", "h3", "h4", "h5"])
        if h is None:
            continue
        title = clean(a.get_text(" "))
        if not title or id(h) in heads:
            continue
        heads[id(h)] = (h, m.group(1), title)
    return heads


def _parse_table(table: Tag, today: dt.date) -> list[tuple[str, str, str | None, str | None, str | None]]:
    """Return (date, start, end, row_label, link) tuples found in a schedule table."""
    results = []
    col_dates: list[str | None] | None = None
    for tr in table.find_all("tr"):
        if tr.find_parent("table") is not table:
            continue
        cells = [c for c in tr.find_all(["th", "td"]) if c.find_parent("tr") is tr]
        if not cells:
            continue
        texts = [clean(c.get_text(" ")) for c in cells]
        has_times = any(TIME_RE.search(t) for t in texts)
        dates = [cell_date(c, today) for c in cells]

        # Layout A: a header row of dates (columns = days)
        if not has_times and sum(1 for d in dates if d) >= 1:
            col_dates = dates
            continue

        # Layout B: rows that start with a date, times in the following cell(s)
        first_date = dates[0] if dates else None
        if first_date and has_times and not TIME_RE.search(texts[0]):
            for c in cells[1:]:
                for s, e in extract_times(clean(c.get_text(" "))):
                    results.append((first_date, s, e, None, external_link(c)))
            continue

        # Layout A body row: cells line up with the date header
        if col_dates and has_times:
            offset = len(cells) - len(col_dates)
            row_label = find_format(" ".join(texts[:offset])) if offset > 0 else None
            body = cells[offset:] if offset > 0 else cells
            for i, c in enumerate(body):
                if i >= len(col_dates):
                    break
                d = c.get("data-date") and cell_date(c, today) or col_dates[i]
                if not d:
                    continue
                for s, e in extract_times(clean(c.get_text(" "))):
                    results.append((d, s, e, row_label, external_link(c)))
    return results


def _parse_text_tokens(tokens: list[tuple[str, str | None]], today: dt.date):
    """Fallback for list layouts: a date token followed by time tokens."""
    results = []
    cur_date = None
    cur_fmt = None
    for text, link in tokens:
        fmt = find_format(text) if len(text) <= 30 else None
        times = extract_times(text)
        m = DATE_RE.search(text)
        if m and not times:
            cur_date = infer_date(int(m.group(1)), int(m.group(2)), today)
            continue
        if m and times:
            # "10/17（土） 9:50 12:15"
            cur_date = infer_date(int(m.group(1)), int(m.group(2)), today)
            text = text[m.end():]
            times = extract_times(text)
        if fmt and not times:
            cur_fmt = fmt
            continue
        if cur_date and times:
            for s, e in times:
                results.append((cur_date, s, e, cur_fmt, link))
    return results


def parse_prices(soup: BeautifulSoup) -> list[dict]:
    """Find the 料金 (prices) section and pull out 'label → yen' pairs."""
    anchor = None
    for el in soup.find_all(["h2", "h3", "h4", "h5", "dt", "th", "p", "div", "span"]):
        t = clean(el.get_text(" "))
        if t in ("料金", "料金表", "鑑賞料金", "入場料金", "料金案内") or (
            len(t) <= 12 and "料金" in t and "円" not in t
        ):
            anchor = el
            break
    if anchor is None:
        return []

    # Collect the text of the section: following siblings of the anchor, or
    # climb until the container actually holds yen amounts.
    container = anchor
    text = ""
    for _ in range(4):
        sib_text = []
        for sib in container.next_siblings:
            if isinstance(sib, Tag) and sib.name in ("h2", "h3") and sib is not anchor:
                break
            sib_text.append(sib.get_text("\n") if isinstance(sib, Tag) else str(sib))
        text = "\n".join(sib_text)
        if "円" in text:
            break
        if container.parent is None:
            break
        container = container.parent
    if "円" not in text:
        return []

    # Labels and amounts often sit in separate cells (<th>一般</th><td>2,000円</td>);
    # glue a label-only line onto an amount-only line that follows it.
    raw = [clean(l) for l in text.splitlines() if clean(l)]
    lines: list[str] = []
    for l in raw:
        if lines and "円" not in lines[-1] and re.match(r"^[¥￥]?\s*[\d,]{3,6}\s*円", l):
            lines[-1] = f"{lines[-1]} {l}"
        else:
            lines.append(l)

    prices: list[dict] = []
    seen = set()
    for line in lines:
        if not line or len(line) > 160:
            continue
        for m in YEN_RE.finditer(line):
            label = clean(m.group(1)).strip("・:：-–")
            yen = int(m.group(2).replace(",", ""))
            if not label or yen < 300 or yen > 10000:
                continue
            key = (label, yen)
            if key in seen:
                continue
            seen.add(key)
            prices.append({"label_ja": label, "yen": yen})
    return prices[:20]


# ── eiga.com's own layout (primary) ─────────────────────────────────────────
#
# <section id="m104848"><h2><a href="/movie/104848/">title</a></h2>
#   <div class="movie-image"><img src=…><p class="data"><span>124分</span>…</p></div>
#   <div class="movie-schedule">                       (one per version)
#     <div class="movie-type"><span class="type-subtitled">字幕</span></div>
#     <table class="weekly-schedule"><tr>
#       <td data-date="20261018"><p class="date">10/18（日）</p>
#           <a data-time=…>10:25</a> <a>15:25<small>～17:39</small></a></td> …

CLOSED_RE = re.compile(r"(臨時休館|休館中|閉館|営業を休止|休業)")


def _parse_structured(soup: BeautifulSoup, today: dt.date, page: TheaterPage) -> bool:
    sections = [sec for sec in soup.select("section[id^=m]") if sec.select_one(".movie-schedule, table.weekly-schedule")]
    if not sections:
        return False
    links: list[str] = []
    for sec in sections:
        a = sec.select_one("h2 a[href*='/movie/']") or sec.find("a", href=MOVIE_HREF)
        m = MOVIE_HREF.match(a["href"].strip()) if a else None
        mid = m.group(1) if m else sec["id"][1:]
        if not mid.isdigit():
            continue
        title = clean(a.get_text(" ")) if a else clean(sec.get("data-title", ""))
        stub = page.movies.setdefault(mid, MovieStub(mid, title))
        data_p = sec.select_one(".movie-image .data, p.data")
        if data_p:
            rt = RUNTIME_RE.search(data_p.get_text(" "))
            if rt:
                stub.runtime = int(rt.group(1))
        img = sec.select_one(".movie-image img")
        if img and img.get("src", "").startswith("http"):
            stub.poster = img["src"]

        blocks = sec.select(".movie-schedule") or [sec]
        seen = set()
        for blk in blocks:
            types = [clean(x.get_text(" ")) for x in blk.select(".movie-type span, .movie-type li")]
            fmt = " ".join(t for t in types if t) or None
            for td in blk.select("td[data-date]"):
                d = cell_date(td, today)
                if not d:
                    continue
                for date_p in td.select("p.date"):
                    date_p.extract()
                for s_, e_ in extract_times(clean(td.get_text(" "))):
                    key = (d, s_, fmt)
                    if key in seen:
                        continue
                    seen.add(key)
                    page.screenings.append(Screening(mid, d, s_, e_, fmt, None))
                for lk in td.find_all("a", href=True):
                    h = lk["href"]
                    if h.startswith("http") and "eiga.com" not in h:
                        links.append(h)
    if links and not page.official_url:
        page.official_url = max(set(links), key=links.count)
    return True


def _parse_theater_table(soup: BeautifulSoup, page: TheaterPage) -> bool:
    """Prices, discounts and official site from eiga.com's theater info table."""
    table = soup.select_one("table.theater-table")
    if not table:
        return False
    section = None
    for tr in table.find_all("tr"):
        th = tr.find("th")
        if th:
            section = clean(th.get_text(" "))
        off = tr.select_one("a.official[href], a.icon.official[href]")
        if off and not page.official_url:
            page.official_url = off["href"]
        if section == "基本料金":
            for td in tr.find_all("td"):
                t = clean(td.get_text(" "))
                m = re.match(r"^(.+?)\s*[¥￥]?\s*([\d,]{3,6})\s*円", t)
                if m:
                    page.prices.append({"label_ja": m.group(1).strip(), "yen": int(m.group(2).replace(",", ""))})
                elif "差異" in t or "異なる" in t:
                    page.price_note = t.strip("（）()")
        elif section == "割引情報":
            for li in tr.select("li") or tr.find_all("td"):
                t = clean(li.get_text(" "))
                for m in re.finditer(r"([^/／、。]{1,40}?)\s*([\d,]{3,5})\s*円", t):
                    label = m.group(1).strip(" ・:：")
                    yen = int(m.group(2).replace(",", ""))
                    if not (300 <= yen <= 5000) or len(label) < 2 or re.match(r"^[\d)）\]】]", label):
                        continue
                    if not re.search(r"[\u3040-\u30ff\u3400-\u9fff]", label) or label.endswith(("で", "常時")):
                        continue
                    if len(page.discounts) < 6:
                        page.discounts.append({"label_ja": label, "yen": yen})
    return True


def parse_theater_page(html: str, today: dt.date) -> TheaterPage:
    soup = BeautifulSoup(html, "lxml")
    page = TheaterPage()
    main = soup.find("main") or soup
    for node in main.find_all(string=CLOSED_RE):
        el = node.parent
        if el.name in ("script", "style") or el.find_parent(["section", "table", "nav"]):
            continue
        text = clean(el.get_text(" "))
        if 6 <= len(text) <= 300:
            page.notice = text
            break
    has_table = _parse_theater_table(soup, page)
    if _parse_structured(soup, today, page):
        if not has_table:
            page.prices = parse_prices(soup)
        return page
    page.prices = page.prices or []
    return _parse_generic(soup, today, page, has_table)


def _parse_generic(soup: BeautifulSoup, today: dt.date, page: TheaterPage, has_table: bool) -> TheaterPage:
    """Layout-agnostic fallback, used if eiga.com changes its markup."""
    heads = _movie_headings(soup)
    if not heads:
        if not has_table:
            page.prices = parse_prices(soup)
        return page

    current: str | None = None
    pending_fmt: str | None = None
    tokens: dict[str, list[tuple[str, str | None]]] = {}
    table_hits: dict[str, list] = {}
    seg_text: dict[str, list[str]] = {}
    links: list[str] = []

    for el in soup.descendants:
        if isinstance(el, Tag):
            if id(el) in heads:
                _, mid, title = heads[id(el)]
                current = mid
                pending_fmt = None
                page.movies.setdefault(mid, MovieStub(mid, title))
                tokens.setdefault(mid, [])
                table_hits.setdefault(mid, [])
                seg_text.setdefault(mid, [])
                continue
            if current and el.name == "table" and el.find_parent("table") is None:
                for d, s, e, row_label, link in _parse_table(el, today):
                    table_hits[current].append((d, s, e, row_label or pending_fmt, link))
                    if link:
                        links.append(link)
                pending_fmt = None
            continue

        if not isinstance(el, NavigableString) or current is None:
            continue
        if el.find_parent(["script", "style", "noscript"]) is not None:
            continue
        text = clean(str(el))
        if not text:
            continue
        # skip text that sits inside a film heading
        seg_text[current].append(text)
        if el.find_parent("table") is not None:
            continue
        parent = el.parent
        link = None
        if isinstance(parent, Tag) and parent.name == "a":
            href = (parent.get("href") or "").strip()
            if href.startswith("http") and "eiga.com" not in href:
                link = href
                links.append(href)
        if len(text) <= 30:
            fmt = find_format(text)
            if fmt and not TIME_RE.search(text):
                pending_fmt = fmt
        tokens[current].append((text, link))

    for mid, stub in page.movies.items():
        hits = table_hits.get(mid) or _parse_text_tokens(tokens.get(mid, []), today)
        seen = set()
        for d, s, e, fmt, link in hits:
            key = (d, s, fmt)
            if key in seen:
                continue
            seen.add(key)
            page.screenings.append(Screening(mid, d, s, e, fmt, link))
        rt = RUNTIME_RE.search(" ".join(seg_text.get(mid, [])))
        if rt and 30 <= int(rt.group(1)) <= 400:
            stub.runtime = int(rt.group(1))

    if not has_table:
        page.prices = parse_prices(soup)
    if links:
        page.official_url = max(set(links), key=links.count)
    return page


# ── movie page ─────────────────────────────────────────────────────────────

def parse_movie_page(html: str) -> dict:
    soup = BeautifulSoup(html, "lxml")
    text = soup.get_text("\n")
    lines = [clean(l) for l in text.splitlines() if clean(l)]
    info: dict = {}

    for l in lines:
        m = re.match(r"^原題(?:または英題)?\s*[：:]\s*(.+)$", l)
        if m:
            info["title_en"] = m.group(1).strip()
            break

    for l in lines:
        m = re.search(r"(\d{4})年製作\s*／\s*(?:(\d{2,3})分)?(.*)$", l)
        if m:
            info["year"] = int(m.group(1))
            if m.group(2):
                info["runtime"] = int(m.group(2))
            # Remaining parts are an optional age rating and the country, in that order;
            # films without a rating go straight to the country.
            for part in [x.strip() for x in m.group(3).split("／") if x.strip()]:
                if RATING_RE.match(part):
                    info["rating"] = part
                elif "country" not in info:
                    info["country"] = part
            break

    for i, l in enumerate(lines):
        if l == "監督" and i + 1 < len(lines) and len(lines[i + 1]) < 40:
            info["director"] = lines[i + 1]
            break
        m = re.match(r"^監督\s*[：:]?\s*(\S.{0,38})$", l)
        if m:
            info["director"] = m.group(1).strip()
            break

    rating = parse_eiga_rating(text)
    if rating:
        info["scores_eiga"] = rating

    og = soup.find("meta", attrs={"property": "og:image"})
    if og and og.get("content"):
        info["poster"] = og["content"]
    return info
