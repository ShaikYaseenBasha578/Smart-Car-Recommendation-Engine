// ============================================
// CARREC - page scripts (homepage hero, search thread, result cards)
// ============================================
// The /predict response is unchanged; everything buyer-facing (match labels, plain-English
// reasons, price formatting) is a presentation mapping done here.

// --- small helpers ---
function escapeHtml(value) {
    return String(value).replace(/[&<>"']/g, ch => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[ch]));
}

function trimNumber(n, digits = 2) {
    return String(Number(n.toFixed(digits)));
}

// 894000 -> "₹8.94 lakh", 12500000 -> "₹1.25 crore"
function formatPrice(num) {
    if (!num || isNaN(num)) return "Price not listed";
    num = Number(num);
    if (num >= 1e7) return `₹${trimNumber(num / 1e7)} crore`;
    if (num >= 1e5) return `₹${trimNumber(num / 1e5)} lakh`;
    return "₹" + Math.round(num).toLocaleString("en-IN");
}

// short form for sentences: 1200000 -> "₹12L"
function formatBudget(num) {
    num = Number(num);
    if (num >= 1e7) return `₹${trimNumber(num / 1e7)}Cr`;
    return `₹${trimNumber(num / 1e5, 1)}L`;
}

const ICONS = {
    check: '<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4.5 10.5l3.5 3.5 7.5-8"/></svg>',
    star: '<svg viewBox="0 0 20 20" fill="currentColor" aria-hidden="true"><path d="M10 1.8l2.5 5.3 5.7.7-4.2 4 1.1 5.7L10 14.7l-5.1 2.8 1.1-5.7-4.2-4 5.7-.7z"/></svg>',
    info: '<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" aria-hidden="true"><circle cx="10" cy="10" r="7.5"/><path d="M10 9v4.5M10 6.3v.2"/></svg>',
    plus: '<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><path d="M10 4.5v11M4.5 10h11"/></svg>',
    external: '<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M8 4.5H5a1.5 1.5 0 0 0-1.5 1.5v9A1.5 1.5 0 0 0 5 16.5h9a1.5 1.5 0 0 0 1.5-1.5v-3M11.5 3.5h5v5M16.5 3.5L9 11"/></svg>',
    arrow: '<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 10h12M11 5l5 5-5 5"/></svg>',
    alert: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M12 7.5v5.5M12 16.2v.3"/></svg>'
};

// --- match label ---
// r = score / max(top score in this result set, 30), the same normalisation the old % ring used.
// Thresholds picked from the 187 results of the 28 tests/test_predict_kb.py queries:
// r >= 0.90 -> Great (75 results), r >= 0.70 -> Good (81), else Fair (31).
const MATCH_GREAT = 0.9;
const MATCH_GOOD = 0.7;

function matchLevel(score, topScore) {
    const r = (Number(score) || 0) / Math.max(topScore, 30);
    if (r >= MATCH_GREAT) return { key: "great", label: "Great match" };
    if (r >= MATCH_GOOD) return { key: "good", label: "Good match" };
    return { key: "fair", label: "Fair match" };
}

// --- plain-English reasons ---
const FEATURE_LABELS = {
    sunroof: "Sunroof",
    adas: "ADAS",
    camera_360: "360° camera",
    ventilated_seats: "Ventilated seats",
    cruise_control: "Cruise control",
    wireless_charging: "Wireless charging",
    heads_up_display: "Heads-up display",
    android_auto: "Android Auto",
    apple_carplay: "Apple CarPlay"
};
const NO_RATING_LABEL = "No Bharat NCAP rating on record";
const MAX_REASONS = 4;
const FUEL_REASONS = { petrol: "Runs on petrol", diesel: "Diesel engine", cng: "Runs on CNG", electric: "Fully electric", hybrid: "Hybrid engine" };
const VOWEL_BODIES = /^(suv|muv|mpv|suv coupe)$/i;

function mileageText(car) {
    const m = Number(car.ARAI_Certified_Mileage);
    if (!m) return null;
    const unit = /cng/i.test(car.Fuel_Type || "") ? "km/kg" : "kmpl";
    return `${trimNumber(m, 1)} ${unit}`;
}

function budgetReason(intent) {
    const b = intent && intent.budget;
    if (b && b.min && b.max) return `In your ${formatBudget(b.min)}–${formatBudget(b.max).slice(1)} range`;
    if (b && b.max) return `Fits your ${formatBudget(b.max)} budget`;
    return "Within your budget";
}

function safetyReason(car) {
    const s = car.safety;
    if (!s || !s.stars_adult) return null;
    return `${s.stars_adult}★ ${s.testing_body || "crash-test"} safety`;
}

// one raw match_reasons string -> buyer language (null drops it)
function buyerReason(raw, car, intent) {
    const text = String(raw).trim();
    const lower = text.toLowerCase();
    if (lower === "within budget") return budgetReason(intent);
    if (lower === "uses budget well for practical use") return "Good value for the money";
    if (lower === "good mileage" || lower === "fits your mileage preference") {
        const m = mileageText(car);
        return m ? `Good mileage (${m})` : null;  // don't claim it next to "Mileage: Not listed"
    }
    if (lower === "automatic transmission") return `${car.transmission_label || "Automatic"} gearbox`;
    if (lower === "manual transmission") return `${car.transmission_label || "Manual"} gearbox`;
    if (lower === "automatic is easier for parents") return "Automatic, so it's easy to drive";
    if (lower === "airbags for safety" || lower === "has airbags") return "Has airbags";
    if (lower === "abs for safety") return "Has ABS brakes";
    if (lower === "seating capacity" || lower === "extra seating capacity") return "Plenty of seats";
    if (lower === "suitable seating for family") return "Seats the whole family";
    if (lower === "very practical family body type") return "Practical shape for families";
    if (lower === "comfortable family sedan") return "Comfortable family sedan";
    if (lower === "fits your space preference") return "Roomy inside";
    let m = lower.match(/^(\w+) fuel preference$/);
    if (m) return FUEL_REASONS[m[1]] || `Runs on ${m[1]}`;
    m = text.match(/^(.+) body type$/i);
    if (m) {
        const body = /^(suv|muv|mpv)$/i.test(m[1]) ? m[1].toUpperCase() : m[1].toLowerCase();
        return `It's ${VOWEL_BODIES.test(body) ? "an" : "a"} ${body}`;
    }
    m = text.match(/^similar body type, size and price to (.+)$/i);
    if (m) return `Similar size and price to the ${m[1]}`;
    const feature = lower.replace(/^has /, "");
    const key = Object.keys(FEATURE_LABELS).find(k => FEATURE_LABELS[k].toLowerCase() === feature || k === feature);
    if (key) return key === "sunroof" ? "Has a sunroof" : `Has ${FEATURE_LABELS[key]}`;
    return text.charAt(0).toUpperCase() + text.slice(1);
}

function buyerReasons(car, intent) {
    const out = [];
    const add = r => { if (r && !out.some(o => o.toLowerCase() === r.toLowerCase())) out.push(r); };
    const safety = safetyReason(car);
    if (safety && intent && intent.min_safety_stars) add(safety);  // they asked for it: lead with it
    (car.match_reasons || []).forEach(r => add(buyerReason(r, car, intent)));
    if (safety && car.safety.stars_adult >= 4) add(safety);
    return out.slice(0, MAX_REASONS);
}

// --- chips under a card: features / safety / unverified ---
function tag(text, kind, icon = "") {
    return `<li class="tag tag--${kind}">${icon}<span>${escapeHtml(text)}</span></li>`;
}

function buildExtraChips(car) {
    const tags = [];

    (car.matched_features || []).forEach(f => tags.push(tag(FEATURE_LABELS[f] || f, "feature", ICONS.check)));

    if (car.safety) {
        const year = car.safety.year ? ` (${car.safety.year})` : "";
        tags.push(tag(`${car.safety.stars_adult}-star ${car.safety.testing_body}${year}`, "safety", ICONS.star));
    } else if ("safety" in car) {
        tags.push(tag(NO_RATING_LABEL, "unverified", ICONS.info));
    }

    (car.unverified || [])
        .filter(u => !(u === NO_RATING_LABEL && "safety" in car && !car.safety))  // already shown above
        .forEach(u => tags.push(tag(u, "unverified", ICONS.info)));

    if (car.matching_variant_count) {
        const n = car.matching_variant_count;
        tags.push(tag(`${n} matching variant${n === 1 ? "" : "s"}`, "plain"));
    }

    return tags.join("");
}

// --- banners, hints, toolbar ---
function buildUnsupportedBanner(data) {
    if (!data.unsupported_terms || !data.unsupported_terms.length) return "";
    const brands = data.unsupported_terms.join(", ");
    const covered = data.covered_makes || [];
    const coveredText = covered.length
        ? ` Showing the closest matches from the ${covered.length} brands we cover: ${covered.join(", ")}.`
        : "";
    return `<div class="notice" role="status">${ICONS.alert}<div>
        <strong>We don't cover ${escapeHtml(brands)} yet.</strong>
        <p>${escapeHtml(coveredText.trim())}</p>
    </div></div>`;
}

function buildRelaxationHints(hints) {
    if (!hints || !hints.length) return "";
    return `<ul class="hints">` + hints.map(h => {
        const n = h.would_return;
        const examples = h.top_models && h.top_models.length ? `, e.g. ${h.top_models.join(", ")}` : "";
        const detail = `${n} option${n === 1 ? "" : "s"}${escapeHtml(examples)}`;
        if (!h.key) return `<li class="hint-static">Without ${escapeHtml(h.drop)}: ${detail}</li>`;
        // clicking reruns the same query with this constraint dropped
        return `<li><button type="button" data-drop-key="${escapeHtml(h.key)}" class="hint-btn">
            <span><strong>Without ${escapeHtml(h.drop)}</strong><small>${detail}</small></span>${ICONS.arrow}
        </button></li>`;
    }).join("") + `</ul>`;
}

function buildDroppedBanner(data) {
    if (!data.dropped || !data.dropped.length) return "";
    return `<p class="dropped">Showing results without: ${escapeHtml(data.dropped.map(d => d.label).join(", "))}</p>`;
}

function buildDataStamp(data) {
    if (!data.data_as_of) return "";
    const [y, m, d] = String(data.data_as_of.exported).split("-").map(Number);
    const date = y && m && d
        ? new Date(y, m - 1, d).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" })
        : data.data_as_of.exported;
    return `<p class="data-stamp">Car data updated ${escapeHtml(date)} · knowledge base <span class="nowrap">${escapeHtml(data.data_as_of.kb_phase)}</span></p>`;
}

// dropped-constraint banner + data stamp on the left, "Copy link" on the right
function buildResultsToolbar(data, link) {
    return `<div class="toolbar">
        <div class="toolbar-info">${buildDroppedBanner(data)}${buildDataStamp(data)}</div>
        <button type="button" data-copy-link="${escapeHtml(link)}" class="btn btn-quiet">Copy link</button>
    </div>`;
}

// --- result card ---
function buildFacts(car) {
    const isEv = /electric/i.test(car.Fuel_Type || "");
    const mileage = mileageText(car);
    const facts = [
        ["Gearbox", car.transmission_label || car.Transmission || "Not listed"],
        ["Fuel", car.Fuel_Type || "Not listed"],
        isEv ? ["Range", "Not listed"] : ["Mileage", mileage || "Not listed"]
    ];
    return `<dl class="facts">` + facts.map(([k, v]) => `<div><dt>${k}</dt><dd>${escapeHtml(v)}</dd></div>`).join("") + `</dl>`;
}

function buildCarCard(car, index, topScore, intent) {
    const name = `${car.Make} ${car.Model}`;
    const image = car.carImage || "/static/pic.avif";
    const caption = car.imageAttribution
        ? `Image: ${car.imageAttribution}`
        : (/\.svg$/.test(image) ? "Illustration: no photo of this model yet" : "");
    const match = matchLevel(car.ranking_score, topScore);
    const reasons = buyerReasons(car, intent);
    const tags = buildExtraChips(car);
    const link = car.carDekhoLink;
    return `
        <article class="car${index === 0 ? " car--top" : ""}" aria-label="${escapeHtml(name)}">
            <figure class="car-photo">
                ${index === 0 ? '<span class="rank">Top pick</span>' : ""}
                <img src="${escapeHtml(image)}" alt="${escapeHtml(name)}" loading="${index < 2 ? "eager" : "lazy"}" decoding="async">
                ${caption ? `<figcaption>${escapeHtml(caption)}</figcaption>` : ""}
            </figure>
            <div class="car-body">
                <header>
                    <h3 class="car-title">${escapeHtml(name)}</h3>
                    ${car.Variant ? `<p class="car-variant">${escapeHtml(car.Variant)}</p>` : ""}
                    <p class="car-price"><strong>${formatPrice(car["Ex-Showroom_Price"])}</strong><span>ex-showroom</span></p>
                </header>
                ${buildFacts(car)}
                <div class="car-meta"><span class="match match--${match.key}">${match.label}</span></div>
                ${reasons.length ? `<ul class="reasons" aria-label="Why it fits">${reasons.map(r => `<li>${ICONS.check}<span>${escapeHtml(r)}</span></li>`).join("")}</ul>` : ""}
                ${tags ? `<ul class="tags" aria-label="Features and safety">${tags}</ul>` : ""}
                ${link ? `<div class="car-actions">
                    <a class="btn btn-primary" href="${escapeHtml(link)}" target="_blank" rel="noopener noreferrer">Check on-road price ${ICONS.external}<span class="sr-only">(opens CarDekho in a new tab)</span></a>
                </div>` : ""}
            </div>
        </article>`;
}

// 🆕 NEW CARS HANDLER
// Results are a thread of turns: every search (top box, follow-up box, chip or hint) appends a turn
// below the previous ones. v1: each query is independent; nothing carries over between turns.
// The latest search also lives in the URL (?q=<query>&drop=<key>,<key>) for sharing and back/forward.
const MAX_TURNS = 10;
let turnCount = 0;

function searchUrl(q, drop) {
    const params = new URLSearchParams({ q });
    if (drop.length) params.set("drop", drop.join(","));
    return `${location.pathname}?${params}`;
}

function searchFromUrl() {
    const params = new URLSearchParams(location.search);
    const drop = (params.get("drop") || "").split(",").filter(Boolean);
    return { q: params.get("q") || "", drop };
}

function prefersReducedMotion() {
    return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

function scrollToTurn(turn) {
    turn.querySelector("[data-turn-heading]").scrollIntoView({ behavior: prefersReducedMotion() ? "auto" : "smooth", block: "start" });
}

function sendQuery(event) {
    if (event) event.preventDefault();
    return runSearch(document.getElementById("userQuery").value, []);
}

function sendFollowup(event) {
    if (event) event.preventDefault();
    const input = document.getElementById("followupQuery");
    const query = input.value;
    input.value = "";
    return runSearch(query, []);
}

function appendTurn(query, drop) {
    const thread = document.getElementById("results");
    const id = ++turnCount;
    thread.insertAdjacentHTML("beforeend", `
        <section data-turn="${id}" class="turn">
            <h2 data-turn-heading tabindex="-1" class="turn-head"><span class="turn-label">You searched for</span><span class="turn-query">“${escapeHtml(query)}”</span></h2>
            <div data-turn-body class="turn-body"></div>
        </section>`);
    while (thread.children.length > MAX_TURNS) thread.firstElementChild.remove();
    const turn = thread.lastElementChild;
    turn.dataset.q = query;
    turn.dataset.drop = drop.join(",");
    document.getElementById("followup").hidden = false;
    return turn;
}

function clearThread() {
    document.getElementById("results").innerHTML = "";
    document.getElementById("followup").hidden = true;
}

function errorState(message) {
    return `<div class="state state--error" role="alert"><h3>Something went wrong</h3><p>${escapeHtml(message)} Please try again.</p></div>`;
}

// push: add a history entry (a new search) or replace the current one (page load, back/forward)
async function runSearch(query, drop = [], push = true) {
    if (!query.trim()) return;

    const turn = appendTurn(query, drop);
    const url = searchUrl(query, drop);
    const state = { q: query, drop, turn: turn.dataset.turn };
    if (push && url !== location.pathname + location.search) window.history.pushState(state, "", url);
    else window.history.replaceState(state, "", url);
    // the first turn sits right under the top box; later turns are scrolled into view, again once
    // their results are in (the page may be too short to bring the heading up before that)
    const scroll = Boolean(turn.previousElementSibling);

    const box = turn.querySelector("[data-turn-body]");
    box.innerHTML = `<div class="loading" role="status"><span class="spinner" aria-hidden="true"></span>Finding cars that match…</div>`;
    if (scroll) scrollToTurn(turn);

    try {
        const response = await fetch("/predict", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(drop.length ? { query, drop } : { query })
        });

        const data = await response.json();
        if (!turn.isConnected) return;  // thread was cleared meanwhile
        renderResults(box, data, response.ok, location.origin + url);
        if (scroll) scrollToTurn(turn);
    } catch (error) {
        if (!turn.isConnected) return;
        box.innerHTML = errorState("We couldn't reach the server.");
    }
}

function renderResults(box, data, ok, link) {
    box.innerHTML = "";

    if (!ok) {
        box.innerHTML = errorState(data.error || "The search didn't go through.");
        return;
    }

    const banner = buildUnsupportedBanner(data);

    if (data.message && (!data.recommendations || !data.recommendations.length)) {
        const hints = buildRelaxationHints(data.relaxation_hints);
        box.innerHTML = banner + buildResultsToolbar(data, link) + `<div class="state">
            <h3>${escapeHtml(data.message)}</h3>
            <p>${hints ? "Loosen one requirement to see close matches:" : "Try a wider budget or fewer must-haves."}</p>
            ${hints}
        </div>`;
        return;
    }

    const recs = data.recommendations || [];
    const topScore = recs.length ? Math.max(...recs.map(r => Number(r.ranking_score) || 0)) : 0;
    box.innerHTML = banner + buildResultsToolbar(data, link)
        + `<div class="cards">${recs.map((car, i) => buildCarCard(car, i, topScore, data.intent)).join("")}</div>`;
}

async function copyLink(button) {
    try {
        await navigator.clipboard.writeText(button.dataset.copyLink);
        button.textContent = "Link copied";
    } catch (error) {
        window.prompt("Copy this link:", button.dataset.copyLink);
    }
    setTimeout(() => { button.textContent = "Copy link"; }, 2000);
}

// --- suggestion chips ---
const SUGGESTION_COUNT = 5;
const SUGGESTION_MIN_CATEGORIES = 3;
const SUGGESTION_ROTATE_MS = 8000;

function shuffled(items) {
    const out = [...items];
    for (let i = out.length - 1; i > 0; i--) {
        const j = Math.floor(Math.random() * (i + 1));
        [out[i], out[j]] = [out[j], out[i]];
    }
    return out;
}

// `count` random queries from at least SUGGESTION_MIN_CATEGORIES categories (fewer if count is smaller),
// avoiding the set on screen where possible
function pickSuggestions(all, previous = [], count = SUGGESTION_COUNT) {
    const fresh = all.filter(s => !previous.includes(s.query));
    const pool = shuffled(fresh.length >= count ? fresh : all);
    const minCategories = Math.min(SUGGESTION_MIN_CATEGORIES, count);
    const picked = [];
    for (const s of pool) {  // one per category first
        if (picked.length < minCategories && !picked.some(p => p.category === s.category)) picked.push(s);
    }
    for (const s of pool) {
        if (picked.length < count && !picked.includes(s)) picked.push(s);
    }
    return shuffled(picked);
}

// box: the <div data-suggestions> under a query input; onPick(query) runs the search
async function initSuggestions(box, onPick, count = SUGGESTION_COUNT) {
    let all;
    try {
        all = await (await fetch("/static/suggested_queries.json")).json();
    } catch (error) {
        return;  // suggestions are optional
    }
    let shown = [];
    const render = () => {
        shown = pickSuggestions(all, shown, count).map(s => s.query);
        box.innerHTML = shown.map(q => `<button type="button" data-suggestion="${escapeHtml(q)}" title="${escapeHtml(q)}" class="chip-btn">${escapeHtml(q)}</button>`).join("")
            + `<button type="button" data-more-ideas class="chip-btn chip-more">More ideas ↻</button>`;
    };
    render();

    box.addEventListener("click", e => {
        const chipButton = e.target.closest("[data-suggestion]");
        if (chipButton) {
            chipButton.blur();  // the search has started; don't keep rotation paused on focus
            onPick(chipButton.dataset.suggestion);
        }
        else if (e.target.closest("[data-more-ideas]")) render();
    });

    if (prefersReducedMotion()) return;
    let hovered = false;
    box.addEventListener("mouseenter", () => { hovered = true; });
    box.addEventListener("mouseleave", () => { hovered = false; });
    setInterval(() => {
        if (!hovered && !box.contains(document.activeElement)) render();
    }, SUGGESTION_ROTATE_MS);
}

// --- homepage hero mosaic (brochure thumbnails from static/hero_images.json) ---
const HERO_TILES = 24;  // CSS shows 24 / 16 / 12 by viewport; hidden tiles are lazy and never load

async function initHeroMosaic(box) {
    let images;
    try {
        images = await (await fetch("/static/hero_images.json")).json();
    } catch (error) {
        return;  // the hero reads fine on its plain dark background
    }
    box.innerHTML = shuffled(images).slice(0, HERO_TILES)
        .map(img => `<img src="${escapeHtml(img.src)}" alt="${escapeHtml(img.alt)}" width="400" height="300" loading="lazy" decoding="async">`)
        .join("");
}

function initNewCarPage() {
    const thread = document.getElementById("results");
    window.history.scrollRestoration = "manual";  // back/forward scroll to the turn themselves
    thread.addEventListener("click", e => {
        const hint = e.target.closest("[data-drop-key]");
        if (hint) {
            const turn = hint.closest("[data-turn]");
            const drop = turn.dataset.drop ? turn.dataset.drop.split(",") : [];
            runSearch(turn.dataset.q, [...drop, hint.dataset.dropKey]);
        }
        const copy = e.target.closest("[data-copy-link]");
        if (copy) copyLink(copy);
    });

    document.querySelectorAll("[data-suggestions]").forEach(box => {
        const input = box.closest("form").querySelector("input");
        initSuggestions(box, q => {
            input.value = q;
            runSearch(q, []);
            if (input.id === "followupQuery") input.value = "";
        }, Number(box.dataset.count) || SUGGESTION_COUNT);
    });

    document.querySelector("[data-new-search]").addEventListener("click", () => {
        clearThread();
        const input = document.getElementById("userQuery");
        input.value = "";
        window.history.pushState({}, "", location.pathname);
        window.scrollTo({ top: 0, behavior: prefersReducedMotion() ? "auto" : "smooth" });
        input.focus();
    });

    // back/forward: scroll to that search's turn if it is still in the thread, else start over with it
    window.addEventListener("popstate", e => {
        const { q, drop } = searchFromUrl();
        const turn = e.state && e.state.turn && thread.querySelector(`[data-turn="${e.state.turn}"]`);
        document.getElementById("userQuery").value = q;
        if (turn) {
            scrollToTurn(turn);
            return;
        }
        clearThread();
        if (q) runSearch(q, drop, false);
    });

    const fromUrl = searchFromUrl();
    const saved = localStorage.getItem("userQuery");  // handed over by older landing-page links
    if (saved) localStorage.removeItem("userQuery");
    const first = fromUrl.q ? fromUrl : (saved ? { q: saved, drop: [] } : null);
    if (first) {
        document.getElementById("userQuery").value = first.q;
        runSearch(first.q, first.drop, false);
    }
}


// 🚗 USED CARS HANDLER
async function sendUsedQuery(event) {
    if (event) event.preventDefault();
    const queryInput = document.getElementById("usedQuery").value;
    const resultsBox = document.getElementById("results");

    if (!queryInput.trim()) return;

    resultsBox.innerHTML = `
        <div class="w-full h-64 flex flex-col items-center justify-center border border-dashed border-base-800 rounded-2xl">
            <div class="w-8 h-8 rounded-full border-2 border-cyan-500/20 border-t-cyan-500 animate-spin mb-4"></div>
            <p class="font-mono text-cyan-500 text-sm animate-pulse">Running Scrapers...</p>
        </div>
    `;

    try {
        const response = await fetch("/used-cars", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ query: queryInput })
        });
        
        const data = await response.json();
        resultsBox.innerHTML = "";

        if (!response.ok) {
            resultsBox.innerHTML = `<div class="p-4 border border-danger-900 bg-danger-900/10 text-danger-400 rounded-xl font-mono text-sm">Error: ${data.error || "Request failed"}</div>`;
            return;
        }

        // Render Source Errors
        if (data.source_errors && data.source_errors.length > 0) {
            const errorBlock = document.createElement("div");
            errorBlock.className = "w-full mb-6 p-5 border border-danger-900/50 bg-danger-900/10 rounded-2xl";
            errorBlock.innerHTML = `
                <p class="font-mono text-xs text-danger-400 tracking-widest uppercase mb-3">Scraping Warnings</p>
                <div class="flex flex-col gap-2">
                    ${data.source_errors.map(err => `
                        <div class="flex items-center gap-3 text-sm text-danger-200 bg-danger-900/20 p-3 rounded-lg border border-danger-900/30">
                            <span class="px-2 py-1 bg-danger-900/50 text-danger-300 font-mono text-[10px] rounded">${err.source}</span>
                            <span class="truncate">${err.error}</span>
                        </div>
                    `).join('')}
                </div>
            `;
            resultsBox.appendChild(errorBlock);
        }

        if (!data.recommendations || !data.recommendations.length) {
            resultsBox.innerHTML += `<div class="p-6 border border-base-800 bg-base-900 rounded-xl text-center"><p class="font-display text-xl text-base-200">No used cars found for this query.</p></div>`;
            return;
        }

        const grid = document.createElement("div");
        grid.className = "grid grid-cols-1 md:grid-cols-2 gap-5";
        
        data.recommendations.forEach(car => {
            const price = car.price || "N/A";
            const location = car.location || "N/A";
            const source = car.source || "Unknown";
            const image = car.image_url || "/static/pic.avif";
            
            grid.innerHTML += `
                <a href="${car.listing_url || '#'}" target="_blank" class="flex flex-col bg-base-900 border border-base-800 rounded-[20px] overflow-hidden group hover:border-cyan-500/50 transition-colors">
                    <div class="relative h-48 w-full overflow-hidden border-b border-base-800">
                        <img src="${image}" class="absolute inset-0 w-full h-full object-cover transition-transform duration-700 group-hover:scale-105">
                        <div class="absolute top-3 left-3 px-2 py-1 bg-base-950/80 backdrop-blur border border-base-700 rounded text-cyan-400 font-mono text-[10px] tracking-widest uppercase shadow-lg">
                            ${source}
                        </div>
                    </div>
                    <div class="p-5 flex flex-col flex-1">
                        <h3 class="font-display text-xl font-bold text-white mb-3 line-clamp-2 leading-tight">${car.title}</h3>
                        <div class="mt-auto grid grid-cols-2 gap-3">
                            <div class="bg-base-950 rounded-lg p-2.5 border border-base-800">
                                <p class="font-mono text-[9px] text-base-400 uppercase mb-0.5">Price</p>
                                <p class="font-sans font-medium text-white text-sm truncate">${price}</p>
                            </div>
                            <div class="bg-base-950 rounded-lg p-2.5 border border-base-800">
                                <p class="font-mono text-[9px] text-base-400 uppercase mb-0.5">Location</p>
                                <p class="font-sans font-medium text-white text-sm truncate">${location}</p>
                            </div>
                        </div>
                    </div>
                </a>
            `;
        });
        
        resultsBox.appendChild(grid);

    } catch (error) {
        resultsBox.innerHTML = `<div class="p-4 border border-danger-900 bg-danger-900/10 text-danger-400 rounded-xl font-mono text-sm">Frontend Error: ${error.message}</div>`;
    }
}
