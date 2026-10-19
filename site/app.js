(() => {
  "use strict";

  const TYPES = [
    { id: "arthouse", en: "Arthouse", ja: "minishiataa" },
    { id: "repertory", en: "Revival", ja: "meigaza" },
    { id: "community", en: "Community", ja: "chiiki no eigakan" },
    { id: "institution", en: "Institutions", ja: "bunka shisetsu" },
    { id: "multiplex", en: "Multiplex", ja: "shinekon" },
  ];
  const TYPE_ORDER = Object.fromEntries(TYPES.map((t, i) => [t.id, i]));
  // Format labels from eiga.com: [English, romaji]
  const FORMATS = {
    "字幕": ["Subtitled", "jimaku"], "日本語字幕": ["Japanese subtitles", "nihongo jimaku"],
    "英語字幕": ["English subtitles", "eigo jimaku"], "外国語字幕": ["Foreign-language subtitles", "gaikokugo jimaku"], "吹替": ["Dubbed", "fukikae"], "吹き替え": ["Dubbed", "fukikae"],
    "バリアフリー": ["Barrier-free", "bariafurii"], "日本語音声ガイド": ["Audio guide", "nihongo onsei gaido"],
    "極上音響": ["Enhanced sound", "gokujou onkyou"], "轟音": ["Loud sound", "gouon"], "爆音": ["Extra-loud sound", "bakuon"],
    "ドルビーシネマ": ["Dolby Cinema", "dorubii shinema"], "ドルビーアトモス": ["Dolby Atmos", "dorubii atomosu"],
    "応援上映": ["Cheering screening", "ouen jouei"], "発声可能": ["Cheering allowed", "hassei kanou"],
    "デジタル": ["Digital", "dejitaru"], "プレミアムシアター": ["Premium screen", "puremiamu shiataa"],
    "IMAXレーザー": ["IMAX Laser", "IMAX reezaa"],
  };
  const WD = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
  const WD_JA = ["nichi", "getsu", "ka", "sui", "moku", "kin", "do"];
  const SOON_MIN = 90;

  const $ = (s) => document.querySelector(s);
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
  const yen = (n) => "¥" + Number(n).toLocaleString("en-US");
  const mins = (t) => { const [h, m] = t.split(":").map(Number); return h * 60 + m; };

  const store = {
    get(k, d) { try { const v = localStorage.getItem("tc." + k); return v == null ? d : JSON.parse(v); } catch { return d; } },
    set(k, v) { try { localStorage.setItem("tc." + k, JSON.stringify(v)); } catch { /* storage unavailable */ } },
  };

  function nowJST() {
    const p = Object.fromEntries(new Intl.DateTimeFormat("en-CA", {
      timeZone: "Asia/Tokyo", year: "numeric", month: "2-digit", day: "2-digit",
      hour: "2-digit", minute: "2-digit", hourCycle: "h23",
    }).formatToParts(new Date()).map((x) => [x.type, x.value]));
    return { date: `${p.year}-${p.month}-${p.day}`, min: Number(p.hour) * 60 + Number(p.minute) };
  }

  const state = {
    day: null,
    view: store.get("view", "film"),
    q: "",
    area: store.get("area", ""),
    lang: store.get("lang", ""),
    sort: store.get("sort", "next"),
    types: new Set(store.get("types", ["arthouse", "repertory", "community", "institution"])),
  };
  let data = null;
  let theaters = {};
  const expanded = new Set();   // films whose theaters are shown (film view)
  const expandedT = new Set();  // theaters whose films are shown (theater view)

  // Japanese is shown as romaji; the original script stays in the tooltip.
  const JP = /[\u3040-\u30ff\u3400-\u9fff]/;
  const romaji = (s) => (s && JP.test(s) ? ((data && data.romaji && data.romaji[s]) || s) : s);
  const rj = (s) => (s ? `<span class="rj" title="${esc(s)}">${esc(romaji(s))}</span>` : "");

  function fmtLabel(f) {
    if (!f) return "";
    const toks = f.split(" ");
    const en = toks.map((x) => (FORMATS[x] ? FORMATS[x][0] : romaji(x))).join(", ");
    const ro = toks.filter((x) => JP.test(x)).map((x) => (FORMATS[x] ? FORMATS[x][1] : romaji(x))).join(" ");
    return ro && en !== ro ? `${esc(en)} <span class="rj" title="${esc(f)}">${esc(ro)}</span>` : esc(en);
  }

  function filmTitle(m, tag = "h2", href, toggleId) {
    const en = m.en && m.en !== m.ja ? romaji(m.en) : null;
    let ro = romaji(m.ja);
    // "The Ozu Diaries 小津ダイアリー": don't repeat the English part in the romaji line
    if (en && ro && ro.toLowerCase().startsWith(en.toLowerCase())) ro = ro.slice(en.length).trim();
    const main = en || ro;
    const auto = en && m.en_auto ? `<span class="auto" title="Machine-translated title">auto</span>` : "";
    const link = href ? `<a href="${esc(href)}" target="_blank" rel="noopener">${esc(main)}</a>` : esc(main);
    if (toggleId) {
      const open = expanded.has(toggleId);
      return `<${tag}><button type="button" class="film-toggle" aria-expanded="${open}" aria-controls="v${esc(toggleId)}">` +
        `<span class="ft-main">${esc(main)}</span>${auto}${en && ro && ro.toLowerCase() !== en.toLowerCase() ? `<span class="ja rj" title="${esc(m.ja)}">${esc(ro)}</span>` : ""}` +
        `</button></${tag}>`;
    }
    const sub = en && ro && ro.toLowerCase() !== en.toLowerCase() ? `<span class="ja rj" title="${esc(m.ja)}">${esc(ro)}</span>` : "";
    return `<${tag}>${link}${auto}${sub}</${tag}>`;
  }

  function filmMeta(m) {
    const bits = [];
    if (m.year) bits.push(m.year);
    if (m.runtime) bits.push(`${m.runtime} min`);
    if (m.country) bits.push(m.country_en ? `<span title="${esc(m.country)}">${esc(m.country_en)}</span>` : rj(m.country));
    if (m.director) bits.push(`Dir. ${rj(m.director)}`);
    return bits.length ? `<p class="meta">${bits.join("／")}</p>` : "";
  }

  function scoresHTML(m, mid, compact) {
    const sc = m.scores;
    if (!sc) return "";
    const items = [];
    const link = (href, inner, title) =>
      `<a class="score" href="${esc(href)}" target="_blank" rel="noopener" title="${esc(title)}">${inner}</a>`;
    const plain = (inner, title) => `<span class="score" title="${esc(title)}">${inner}</span>`;
    if (sc.rt != null) items.push(plain(`<b>${sc.rt}%</b> Rotten Tomatoes`, "Rotten Tomatoes critics score"));
    if (sc.mc != null) items.push(plain(`<b>${sc.mc}</b> Metacritic`, "Metacritic critics score, out of 100"));
    if (sc.imdb) items.push(m.imdb_id
      ? link(`https://www.imdb.com/title/${m.imdb_id}/`, `<b>${sc.imdb.v.toFixed(1)}</b> IMDb`, `IMDb user rating out of 10, ${sc.imdb.n.toLocaleString("en-US")} votes`)
      : plain(`<b>${sc.imdb.v.toFixed(1)}</b> IMDb`, "IMDb user rating out of 10"));
    if (sc.eiga) items.push(link(`https://eiga.com/movie/${mid}/review/`,
      `<b>★ ${sc.eiga.v.toFixed(1)}</b> eiga.com`, `eiga.com user rating out of 5, ${sc.eiga.n} reviews`));
    if (sc.tmdb) items.push(m.tmdb_id
      ? link(`https://www.themoviedb.org/movie/${m.tmdb_id}`, `<b>${sc.tmdb.v.toFixed(1)}</b> TMDB`, `TMDB user rating out of 10, ${sc.tmdb.n} votes`)
      : plain(`<b>${sc.tmdb.v.toFixed(1)}</b> TMDB`, "TMDB user rating out of 10"));
    if (!items.length) return "";
    return `<p class="scores${compact ? " compact" : ""}">${(compact ? items.slice(0, 2) : items).join("")}</p>`;
  }

  // Format words that only restate language/subtitles; the language line covers them.
  const LANG_WORDS = /(外国語字幕|日本語字幕付?|英語字幕[付版]?|字幕|吹替|吹き替え|原語版|with English subtitles|English Subtitle[sd]?|ENGLISH SUBTITLES|ENG SUB|Eng Sub)/g;

  function langName(code) {
    const n = (data.languages || {})[code];
    return n ? `${esc(n[0])} ${rj(n[1])}` : esc(code);
  }

  function langLine(r) {
    const parts = [];
    if (r.a) parts.push(`<span><b>Audio</b> <span class="rj">onsei</span> ${langName(r.a)}</span>`);
    if (r.sub === "none") parts.push(`<span>No subtitles <span class="rj">jimaku nashi</span></span>`);
    else if (r.sub) parts.push(`<span class="${r.sub === "en" ? "en-subs" : ""}"><b>Subtitles</b> <span class="rj">jimaku</span> ${langName(r.sub)}</span>`);
    if (!parts.length) parts.push(`<span>Language not listed</span>`);
    const extra = (r.f || "").replace(LANG_WORDS, "").trim();
    if (extra) parts.push(`<span>${fmtLabel(extra)}</span>`);
    if (r.guess) parts.push(`<span class="guess" title="Not stated on the listing; inferred from the film's country and Japanese screening conventions">likely</span>`);
    return `<p class="fmt-label">${parts.join("")}</p>`;
  }

  function slotsHTML(rows, isToday, nowMin) {
    // one line per audio/subtitle/format combination, then its times
    const groups = new Map();
    for (const r of rows) {
      const k = [r.f || "", r.a || "", r.sub || "", r.guess ? 1 : 0].join("|");
      if (!groups.has(k)) groups.set(k, []);
      groups.get(k).push(r);
    }
    let html = "";
    for (const list of groups.values()) {
      html += langLine(list[0]);
      html += `<div class="slots">` + list.map((r) => {
        const m = mins(r.s);
        let cls = "slot";
        if (isToday && m < nowMin) cls += " past";
        else if (isToday && m - nowMin <= SOON_MIN) cls += " soon";
        const end = r.e ? `<small>until ${esc(r.e)}</small>` : "";
        const label = `${r.s}${r.e ? ", ends " + r.e : ""}${cls.includes("past") ? ", already started" : ""}`;
        return `<span class="${cls}" aria-label="${esc(label)}">${esc(r.s)}${end}</span>`;
      }).join("") + `</div>`;
    }
    return html;
  }

  function priceHTML(t, compact) {
    const general = t.price_general
      ? `<span class="price" title="General admission">${yen(t.price_general)}</span>`
      : t.price_varies ? `<span class="price varies" title="General admission price depends on the film">Varies by film</span>` : "";
    if (compact) return general;
    const row = (p) =>
      `<li><span>${p.label_en ? esc(p.label_en) + " " : ""}${rj(p.label_ja)}</span><span class="yen">${yen(p.yen)}</span></li>`;
    const prices = (t.prices || []).map(row).join("");
    const disc = (t.discounts || []).map(row).join("");
    if (!prices && !disc) return "";
    const varies = t.price_varies ? `<li class="note"><span>General admission varies by film <span class="rj">sakuhin ni yori kotonaru</span></span><span></span></li>` : "";
    return `<details class="prices"><summary>All ticket prices</summary><ul>${varies}${prices}${disc ? `<li class="sub"><span>Discounts <span class="rj">waribiki</span></span><span></span></li>${disc}` : ""}</ul></details>`;
  }

  function venueName(t) {
    const href = t.official_url || t.eiga;
    return `<a href="${esc(href)}" target="_blank" rel="noopener" title="${esc(t.name_ja)}">${esc(t.name_en)}</a>` +
      `<span class="area" title="${esc(t.area_ja || "")}">${esc(t.area_en || "")}</span>`;
  }

  function matches(s) {
    const t = theaters[s.t];
    if (!t || !state.types.has(t.type)) return false;
    if (state.area && t.area_en !== state.area) return false;
    if (state.lang === "en" && !(s.a === "en" || s.sub === "en")) return false;
    if (state.lang === "ja" && s.a !== "ja") return false;
    if (state.lang === "orig-ja" && !(s.sub === "ja" && s.a && s.a !== "ja" && s.a !== "ja-dub")) return false;
    if (state.lang === "dub" && s.a !== "ja-dub") return false;
    if (!state.q) return true;
    const m = data.movies[s.m] || {};
    const hay = [m.en, m.ja, romaji(m.ja), m.director, romaji(m.director), t.name_en, t.name_ja, t.area_en, t.area_ja]
      .join(" ").toLowerCase();
    return state.q.split(/\s+/).every((w) => hay.includes(w));
  }

  function render() {
    const now = nowJST();
    const isToday = state.day === now.date;
    const rows = data.screenings.filter((s) => s.d === state.day && matches(s));
    const list = $("#list");
    if (!rows.length) {
      const hidden = data.screenings.some((s) => s.d === state.day);
      list.innerHTML = `<div class="empty"><p>${hidden
        ? "Nothing matches these filters on this day."
        : "No listings for this day yet. Theaters usually publish the next week's schedule on Tuesday or Wednesday."}</p>${
        hidden ? `<button type="button" id="reset">Show all theaters</button>` : ""}</div>`;
      const b = $("#reset");
      if (b) b.onclick = () => { state.q = ""; $("#q").value = ""; state.area = ""; $("#area").value = ""; state.lang = ""; $("#lang").value = ""; TYPES.forEach((t) => state.types.add(t.id)); save(); drawTypes(); render(); };
      return;
    }
    const avg = (mid) => ((data.movies[mid] || {}).scores || {}).avg ?? -1;
    const byRating = (a, b) => state.sort === "rating" ? avg(b) - avg(a) : 0;
    const nextKey = (list) => {
      const up = list.filter((r) => !isToday || mins(r.s) >= now.min);
      return up.length ? mins(up[0].s) : 10000 + mins(list[0].s);
    };

    if (state.view === "film") {
      const byFilm = new Map();
      for (const r of rows) {
        if (!byFilm.has(r.m)) byFilm.set(r.m, new Map());
        const v = byFilm.get(r.m);
        if (!v.has(r.t)) v.set(r.t, []);
        v.get(r.t).push(r);
      }
      const films = [...byFilm.entries()].map(([mid, venues]) => ({
        mid, venues, key: nextKey([...venues.values()].flat().sort((a, b) => mins(a.s) - mins(b.s))),
      })).sort((a, b) => byRating(a.mid, b.mid) || a.key - b.key);

      // A single result (e.g. after searching) opens straight away.
      if (films.length === 1) expanded.add(films[0].mid);

      list.innerHTML = films.map(({ mid, venues }) => {
        const m = data.movies[mid] || { ja: "?" };
        const vs = [...venues.entries()].sort((a, b) =>
          (TYPE_ORDER[theaters[a[0]].type] - TYPE_ORDER[theaters[b[0]].type]) || (nextKey(a[1]) - nextKey(b[1])));
        const all = [...venues.values()].flat().sort((a, b) => mins(a.s) - mins(b.s));
        const upcoming = isToday ? all.filter((r) => mins(r.s) >= now.min) : all;
        const next = upcoming[0];
        const enFriendly = all.some((r) => r.a === "en" || r.sub === "en");
        const sum = [
          `${vs.length} ${vs.length === 1 ? "theater" : "theaters"}`,
          next ? `next ${esc(next.s)}` : "no more showings today",
          enFriendly ? `<span class="en-subs">English-friendly</span>` : "",
          m.scores && m.scores.eiga ? `★ ${m.scores.eiga.v.toFixed(1)}` : "",
        ].filter(Boolean).join(" · ");
        const open = expanded.has(mid);
        const poster = m.poster ? `<img class="poster" src="${esc(m.poster)}" alt="" loading="lazy" referrerpolicy="no-referrer" onerror="this.remove()">` : "";
        return `<article class="film${open ? " open" : ""}" data-mid="${esc(mid)}">` +
          `<div class="film-head"><div>${filmTitle(m, "h2", null, mid)}<p class="film-sum">${sum}<span class="chev" aria-hidden="true"></span></p></div>${poster}</div>` +
          `<div class="film-body" id="v${esc(mid)}"${open ? "" : " hidden"}>` +
          `${filmMeta(m)}${scoresHTML(m, mid, false)}` +
          `<p class="film-link"><a href="https://eiga.com/movie/${esc(mid)}/" target="_blank" rel="noopener">Film details on eiga.com</a></p>` +
          (open ? vs.map(([tid, rs]) => {
            const t = theaters[tid];
            return `<div class="venue" style="--tc:var(--t-${esc(t.type)})"><div class="venue-name">${venueName(t)}${priceHTML(t, true)}</div>${slotsHTML(rs, isToday, now.min)}</div>`;
          }).join("") : "") +
          `</div></article>`;
      }).join("");
    } else {
      const byT = new Map();
      for (const r of rows) {
        if (!byT.has(r.t)) byT.set(r.t, new Map());
        const f = byT.get(r.t);
        if (!f.has(r.m)) f.set(r.m, []);
        f.get(r.m).push(r);
      }
      const ts = [...byT.entries()].sort((a, b) =>
        (TYPE_ORDER[theaters[a[0]].type] - TYPE_ORDER[theaters[b[0]].type]) ||
        theaters[a[0]].name_en.localeCompare(theaters[b[0]].name_en));
      if (ts.length === 1) expandedT.add(ts[0][0]);

      list.innerHTML = ts.map(([tid, films]) => {
        const t = theaters[tid];
        const type = TYPES.find((x) => x.id === t.type);
        const fl = [...films.entries()].sort((a, b) => byRating(a[0], b[0]) || nextKey(a[1]) - nextKey(b[1]));
        const all = [...films.values()].flat().sort((a, b) => mins(a.s) - mins(b.s));
        const upcoming = isToday ? all.filter((r) => mins(r.s) >= now.min) : all;
        const enFriendly = all.some((r) => r.a === "en" || r.sub === "en");
        const price = t.price_general ? yen(t.price_general) : t.price_varies ? "price varies" : "";
        const sum = [
          esc(t.area_en || ""),
          type ? esc(type.en) : "",
          price,
          `${fl.length} ${fl.length === 1 ? "film" : "films"}`,
          upcoming[0] ? `next ${esc(upcoming[0].s)}` : "no more showings today",
          enFriendly ? `<span class="en-subs">English-friendly</span>` : "",
        ].filter(Boolean).join(" · ");
        const open = expandedT.has(tid);
        return `<article class="house venue${open ? " open" : ""}" data-tid="${esc(tid)}" style="--tc:var(--t-${esc(t.type)})">` +
          `<div class="house-head"><h2><button type="button" class="film-toggle" aria-expanded="${open}" aria-controls="t${esc(tid)}" title="${esc(t.name_ja)}">${esc(t.name_en)}</button></h2>` +
          `<p class="film-sum">${sum}<span class="chev" aria-hidden="true"></span></p></div>` +
          `<div class="house-body" id="t${esc(tid)}"${open ? "" : " hidden"}>` +
          (open ? `<p class="film-link"><a href="${esc(t.official_url || t.eiga)}" target="_blank" rel="noopener">Theater website</a> · <a href="${esc(t.eiga)}" target="_blank" rel="noopener">eiga.com page</a></p>` +
            priceHTML(t, false) +
            fl.map(([mid, rs]) => {
              const m = data.movies[mid] || { ja: "?" };
              return `<div class="film-line">${filmTitle(m, "h3", `https://eiga.com/movie/${mid}/`)}${scoresHTML(m, mid, true)}${slotsHTML(rs, isToday, now.min)}</div>`;
            }).join("") : "") +
          `</div></article>`;
      }).join("");
    }
  }

  function drawDays() {
    const now = nowJST();
    const dates = [...new Set(data.screenings.map((s) => s.d))].filter((d) => d >= now.date).sort();
    if (!dates.length) dates.push(now.date);
    if (!state.day || !dates.includes(state.day)) state.day = dates[0];
    $("#days").innerHTML = dates.map((d) => {
      const [y, mo, da] = d.split("-").map(Number);
      const wd = new Date(Date.UTC(y, mo - 1, da)).getUTCDay();
      const day = Number(d.slice(8, 10));
      const name = d === now.date ? "Today" : WD[wd];
      return `<button type="button" class="day${wd === 0 ? " sun" : wd === 6 ? " sat" : ""}" data-day="${d}" aria-pressed="${d === state.day}" aria-label="${name} ${Number(d.slice(5, 7))}/${day}"><b>${day}</b><small>${name} <span class="rj">${WD_JA[wd]}</span></small></button>`;
    }).join("");
  }

  function drawTypes() {
    $("#types").innerHTML = TYPES.map((t) =>
      `<button type="button" class="type" style="--c:var(--t-${t.id})" data-type="${t.id}" aria-pressed="${state.types.has(t.id)}">${t.en} <span class="rj">${t.ja}</span></button>`).join("");
  }

  function drawAreas() {
    const areas = [...new Set(Object.values(theaters).map((t) => t.area_en).filter(Boolean))].sort();
    $("#area").innerHTML = `<option value="">All areas</option>` +
      areas.map((a) => `<option value="${esc(a)}">${esc(a)}</option>`).join("");
    if (!areas.includes(state.area)) state.area = "";
    $("#area").value = state.area;
  }

  function drawMeta() {
    const g = new Date(data.generated_at);
    const when = new Intl.DateTimeFormat("en-GB", { timeZone: "Asia/Tokyo", weekday: "short", hour: "2-digit", minute: "2-digit" }).format(g);
    const ok = data.theaters.filter((t) => t.status === "ok").length;
    $("#updated").textContent = `Updated ${when} JST`;
    $("#health").querySelector("summary").textContent = `Scan status: ${ok} of ${data.theaters.length} theaters have listings`;
    const why = { error: "could not be fetched", unparsed: "page not understood", empty: "no screenings listed this week",
      closed: `temporarily closed <span class="rj">rinji kyuukan</span>` };
    $("#health-list").innerHTML = data.theaters.filter((t) => t.status !== "ok").map((t) =>
      `<li class="${["empty", "closed"].includes(t.status) ? "" : "bad"}">${esc(t.name_en)}: ${why[t.status] || esc(t.status)}${t.error ? ` (${esc(t.error)})` : ""}${t.notice ? `<br><small class="rj" title="${esc(t.notice)}">${esc(romaji(t.notice))}</small>` : ""}</li>`).join("") || "<li>All theaters scanned.</li>";
  }

  function save() {
    store.set("view", state.view);
    store.set("area", state.area);
    store.set("lang", state.lang);
    store.set("sort", state.sort);
    store.set("types", [...state.types]);
  }

  function bind() {
    // Film view: tap a film's title (or anywhere on its header) to show/hide its theaters.
    // Theater view: the same with a theater's name.
    $("#list").addEventListener("click", (e) => {
      const head = e.target.closest(".film-head, .house-head");
      if (!head || e.target.closest("a")) return;
      const art = head.closest("article");
      const isFilm = art.classList.contains("film");
      const key = isFilm ? art.dataset.mid : art.dataset.tid;
      const set = isFilm ? expanded : expandedT;
      if (set.has(key)) set.delete(key); else set.add(key);
      render();
      // keep the tapped entry where it was on screen
      const sel = isFilm ? `article.film[data-mid="${CSS.escape(key)}"]` : `article.house[data-tid="${CSS.escape(key)}"]`;
      const again = document.querySelector(sel);
      if (again && again.getBoundingClientRect().top < 120) again.scrollIntoView({ block: "start" });
    });
    $("#days").addEventListener("click", (e) => {
      const b = e.target.closest(".day"); if (!b) return;
      state.day = b.dataset.day;
      document.querySelectorAll(".day").forEach((x) => x.setAttribute("aria-pressed", x === b));
      render();
    });
    $("#types").addEventListener("click", (e) => {
      const b = e.target.closest(".type"); if (!b) return;
      const id = b.dataset.type;
      if (state.types.has(id)) state.types.delete(id); else state.types.add(id);
      b.setAttribute("aria-pressed", state.types.has(id));
      save(); render();
    });
    document.querySelectorAll(".seg button").forEach((b) => b.addEventListener("click", () => {
      state.view = b.dataset.view;
      document.querySelectorAll(".seg button").forEach((x) => x.setAttribute("aria-pressed", x === b));
      save(); render();
    }));
    $("#area").addEventListener("change", (e) => { state.area = e.target.value; save(); render(); });
    $("#sort").value = state.sort;
    $("#sort").addEventListener("change", (e) => { state.sort = e.target.value; save(); render(); });
    $("#lang").value = state.lang;
    $("#lang").addEventListener("change", (e) => { state.lang = e.target.value; save(); render(); });
    let timer;
    $("#q").addEventListener("input", (e) => {
      clearTimeout(timer);
      timer = setTimeout(() => { state.q = e.target.value.trim().toLowerCase(); render(); }, 150);
    });
    // keep "soon" / "past" markers fresh while the page stays open
    setInterval(() => { if (data) render(); }, 60 * 1000);
  }

  // ── loading, offline and staleness ────────────────────
  let lastLoad = 0;

  function fmtWhen(iso) {
    return new Intl.DateTimeFormat("en-GB", { timeZone: "Asia/Tokyo", weekday: "short", hour: "2-digit", minute: "2-digit" })
      .format(new Date(iso));
  }

  // The scan lands a little after 5:00 JST; before ~5:45 yesterday's data is still current.
  function expectedScanDate() {
    const now = nowJST();
    if (now.min >= 5 * 60 + 45) return now.date;
    const [y, m, d] = now.date.split("-").map(Number);
    return new Date(Date.UTC(y, m - 1, d - 1)).toISOString().slice(0, 10);
  }

  function showNotice() {
    const n = $("#notice");
    if (!data) { n.hidden = true; return; }
    const stale = data.today < expectedScanDate();
    const from = fmtWhen(data.generated_at);
    if (!navigator.onLine) {
      n.className = "notice";
      n.innerHTML = `You're offline. Showing listings saved ${esc(from)} JST.`;
      n.hidden = false;
    } else if (stale) {
      n.className = "notice warn";
      n.innerHTML = `Today's update hasn't arrived yet. Showing listings from ${esc(from)} JST. <button type="button" data-act="refresh">Check again</button>`;
      n.hidden = false;
    } else {
      n.hidden = true;
    }
  }

  async function load({ quiet = false } = {}) {
    const btn = $("#updated");
    btn.classList.add("busy");
    try {
      const r = await fetch("data/showtimes.json", { cache: "no-cache" });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const fresh = await r.json();
      const changed = !data || fresh.generated_at !== data.generated_at;
      data = fresh;
      lastLoad = Date.now();
      if (changed) {
        theaters = Object.fromEntries(data.theaters.map((t) => [t.id, t]));
        $("#tmdb-credit").hidden = !Object.values(data.movies).some((m) => m.tmdb_id);
        drawMeta(); drawAreas(); drawDays(); render();
      }
      showNotice();
    } catch (err) {
      if (!data) {
        btn.textContent = "No listings yet";
        $("#list").innerHTML = navigator.onLine
          ? `<div class="empty"><p>Listings haven't been generated yet. Run the “Daily scan” workflow from the repository's Actions tab.</p></div>`
          : `<div class="empty"><p>You're offline and no listings are saved on this phone yet. Open the app once while online.</p></div>`;
      } else if (!quiet) {
        showNotice();
      }
    } finally {
      btn.classList.remove("busy");
    }
  }

  // ── install + updates ─────────────────────────────────
  const IN_ANDROID_APP = /TokyoCinemaAndroid\//.test(navigator.userAgent);

  function setupApp() {
    const standalone = matchMedia("(display-mode: standalone)").matches || IN_ANDROID_APP;
    // Offer the Android app to Android visitors who aren't already in it.
    if (!IN_ANDROID_APP && /Android/.test(navigator.userAgent)) $("#get-android").hidden = false;
    let deferred = null;
    window.addEventListener("beforeinstallprompt", (e) => {
      e.preventDefault();
      deferred = e;
      if (!standalone) $("#install").hidden = false;
    });
    $("#install").addEventListener("click", async () => {
      if (!deferred) return;
      deferred.prompt();
      await deferred.userChoice.catch(() => null);
      deferred = null;
      $("#install").hidden = true;
    });
    window.addEventListener("appinstalled", () => { $("#install").hidden = true; });

    if ("serviceWorker" in navigator) {
      const hadController = !!navigator.serviceWorker.controller;
      navigator.serviceWorker.register("sw.js").catch(() => { /* app still works online */ });
      navigator.serviceWorker.addEventListener("controllerchange", () => {
        if (!hadController) return;
        const n = $("#notice");
        n.className = "notice";
        n.innerHTML = `A new version of the app is ready. <button type="button" data-act="reload">Reload</button>`;
        n.hidden = false;
      });
    }

    $("#notice").addEventListener("click", (e) => {
      const act = e.target.closest("button")?.dataset.act;
      if (act === "reload") location.reload();
      if (act === "refresh") load();
    });
    $("#updated").addEventListener("click", () => load());
    window.addEventListener("online", () => load({ quiet: true }));
    window.addEventListener("offline", showNotice);
    // Coming back to the app after a while: fetch the latest scan, roll "today" forward.
    document.addEventListener("visibilitychange", () => {
      if (document.visibilityState !== "visible" || !data) return;
      if (Date.now() - lastLoad > 20 * 60 * 1000) load({ quiet: true });
      else { drawDays(); render(); }
    });
  }

  function applyUrlParams() {
    const p = new URLSearchParams(location.search);
    if (["en", "ja", "orig-ja", "dub", ""].includes(p.get("lang"))) state.lang = p.get("lang");
    if (["film", "theater"].includes(p.get("view"))) state.view = p.get("view");
  }

  async function init() {
    applyUrlParams();
    document.querySelectorAll(".seg button").forEach((x) => x.setAttribute("aria-pressed", x.dataset.view === state.view));
    drawTypes();
    bind();
    setupApp();
    await load();
  }

  init();
})();
