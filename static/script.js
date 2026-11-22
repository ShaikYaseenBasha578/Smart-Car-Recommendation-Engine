// ============================================
// CARREC - page scripts (homepage hero, search thread, result cards)
// ============================================
// The /predict response is unchanged; everything buyer-facing (match labels, plain-English
// reasons, price formatting) is a presentation mapping done here.

// --- small helpers ---
function escapeHtml(value) {
    return String(value).replace(/[&<>"']/g, ch => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[ch]));
}

// same rule as services.new_car_service.safe_slug: "Maruti Suzuki" -> "maruti-suzuki"
function slug(value) {
    return String(value).toLowerCase().replace(/ /g, "-");
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

// short form for sentences: 310000 -> "₹3.1L"
function formatBudget(num) {
    num = Number(num);
    if (num >= 1e7) return `₹${trimNumber(num / 1e7)}Cr`;
    return `₹${trimNumber(num / 1e5, 1)}L`;
}

const ICONS = {
    check: '<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4.5 10.5l3.5 3.5 7.5-8"/></svg>',
    star: '<svg viewBox="0 0 20 20" fill="currentColor" aria-hidden="true"><path d="M10 1.8l2.5 5.3 5.7.7-4.2 4 1.1 5.7L10 14.7l-5.1 2.8 1.1-5.7-4.2-4 5.7-.7z"/></svg>',
    chevron: '<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M5 8l5 5 5-5"/></svg>',
    info: '<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" aria-hidden="true"><circle cx="10" cy="10" r="7.5"/><path d="M10 9v4.5M10 6.3v.2"/></svg>',
    plus: '<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><path d="M10 4.5v11M4.5 10h11"/></svg>',
    external: '<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M8 4.5H5a1.5 1.5 0 0 0-1.5 1.5v9A1.5 1.5 0 0 0 5 16.5h9a1.5 1.5 0 0 0 1.5-1.5v-3M11.5 3.5h5v5M16.5 3.5L9 11"/></svg>',
    arrow: '<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 10h12M11 5l5 5-5 5"/></svg>',
    close: '<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><path d="M5.5 5.5l9 9M14.5 5.5l-9 9"/></svg>',
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

// --- reasons: only things the card doesn't already say ---
// Priority: budget headroom > standouts within this result set > safety (only when no safety chip)
// > notable extras the user didn't ask for. Never body type, fuel, gearbox or a feature shown as a
// chip; the server's match_reasons mostly echo the query, so they aren't used. No filler.
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
const NO_RATING_LABEL = "No crash-test rating on record";
const MAX_REASONS = 4;
const RIGHT_AT_BUDGET = 25000;   // within ₹25k of the user's max reads as "right at" it
const MIN_FOR_STANDOUTS = 3;     // "…here" comparisons need at least this many results
// values this close to the best count as a tie; 2 tied cars both get the label, 3+ nobody does
const TIE = { price: 10000, kmpl: 0.1, kmkg: 0.1, range: 5, power: 1, boot: 5, airbags: 0 };

function isElectric(car) { return /electric/i.test(car.Fuel_Type || ""); }
function isCng(car) { return /cng/i.test(car.Fuel_Type || ""); }

// The efficiency figure a card shows, in the car's own unit, so comparisons are like with like:
// { kind: "range" | "kmkg" | "kmpl", value, label, text }. A CNG car is only ever shown and compared
// by km/kg: the KB's kmpl cell on CNG rows holds the CNG-cycle figure, so it is never shown as kmpl.
function efficiency(car) {
    if (isElectric(car)) {
        const v = Number(car.ev_range_km) || null;
        return { kind: "range", value: v, label: "Range", text: v ? `${v} km` : null };
    }
    if (isCng(car)) {
        const v = Number(car.mileage_km_per_kg) || null;
        return v
            ? { kind: "kmkg", value: v, label: "Mileage", text: `${trimNumber(v, 1)} km/kg (CNG)` }
            : { kind: "kmkg", value: null, label: "CNG mileage", text: null };
    }
    const v = Number(car.ARAI_Certified_Mileage) || null;
    return { kind: "kmpl", value: v, label: "Mileage", text: v ? `${trimNumber(v, 1)} kmpl` : null };
}

function budgetReason(car, intent) {
    const max = intent && intent.budget && intent.budget.max;
    const price = Number(car["Ex-Showroom_Price"]);
    if (!max || !price) return null;
    const headroom = max - price;
    if (Math.abs(headroom) <= RIGHT_AT_BUDGET) return "Right at your budget";
    if (headroom > 0) return `${formatBudget(headroom)} under your budget`;
    return null;
}

// The cars that lead `recs` on value(car), with ties within `tol`: [] when fewer than 2 cars have a
// value, when 3+ cars tie for the lead, or when every compared car ties (nothing stands out).
function leaders(recs, value, higherIsBetter, tol) {
    const known = recs.filter(r => value(r) != null);
    if (known.length < 2) return [];
    const vals = known.map(value);
    const best = higherIsBetter ? Math.max(...vals) : Math.min(...vals);
    const top = known.filter(r => Math.abs(value(r) - best) <= tol + 1e-9);
    return top.length >= 3 || top.length === known.length ? [] : top;
}

function standoutReasons(car, recs) {
    if (recs.length < MIN_FOR_STANDOUTS) return [];
    const num = key => r => (Number(r[key]) || null);
    const out = [];
    if (leaders(recs, num("Ex-Showroom_Price"), false, TIE.price).includes(car)) out.push("Lowest price here");
    const eff = efficiency(car);
    const sameKind = recs.filter(r => efficiency(r).kind === eff.kind);
    if (leaders(sameKind, r => efficiency(r).value, true, TIE[eff.kind]).includes(car)) {
        out.push(eff.kind === "range" ? `Longest range here (${eff.text})` : `Best mileage here (${eff.text})`);
    }
    const power = r => Number(r.power_bhp ?? r.Power) || null;
    if (leaders(recs, power, true, TIE.power).includes(car)) out.push(`Most powerful here (${Math.round(power(car))} bhp)`);
    if (leaders(recs, num("boot_space_litres"), true, TIE.boot).includes(car)) out.push(`Biggest boot here (${car.boot_space_litres} L)`);
    if (leaders(recs, num("airbags"), true, TIE.airbags).includes(car)) out.push(`Most airbags here (${car.airbags})`);
    return out;
}

// "6 airbags" only when it sets the car apart: it has the highest airbag count here and fewer than
// half of the cards share that count (and the user didn't ask about airbags)
function extraReasons(car, recs, intent, already) {
    const out = [];
    const bags = recs.map(r => Number(r.airbags) || 0);
    const most = Math.max(...bags);
    const sharing = bags.filter(b => b === most).length;
    if (!(intent && intent.min_airbags) && most > 0 && Number(car.airbags) === most && sharing < recs.length / 2
        && !already.some(r => /airbags/i.test(r))) {
        out.push(`${car.airbags} airbags`);
    }
    return out;
}

function buyerReasons(car, recs, intent, chipTexts) {
    const chips = chipTexts.map(t => t.toLowerCase());
    const out = [];
    const add = r => {
        if (!r) return;
        const low = r.toLowerCase();
        if (out.some(o => o.toLowerCase() === low)) return;
        if (chips.some(c => c.includes(low) || low.includes(c))) return;  // the chip already says it
        out.push(r);
    };
    add(budgetReason(car, intent));
    standoutReasons(car, recs).forEach(add);
    if (car.safety && car.safety.stars_adult && !chips.some(c => /ncap|crash/.test(c))) {
        add(`${car.safety.stars_adult}★ ${car.safety.testing_body || "crash-test"}`);
    }
    extraReasons(car, recs, intent, out).forEach(add);
    return out.slice(0, MAX_REASONS);
}

// --- chips under a card: features / safety / unverified ---
function chipList(car) {
    const chips = [];

    (car.matched_features || []).forEach(f => chips.push({ text: FEATURE_LABELS[f] || f, kind: "feature", icon: ICONS.check }));

    if (car.safety) {
        const year = car.safety.year ? ` (${car.safety.year})` : "";
        chips.push({ text: `${car.safety.stars_adult}-star ${car.safety.testing_body}${year}`, kind: "safety", icon: ICONS.star });
    } else if ("safety" in car) {
        chips.push({ text: NO_RATING_LABEL, kind: "unverified", icon: ICONS.info });
    }

    (car.unverified || [])
        .filter(u => !(u === NO_RATING_LABEL && "safety" in car && !car.safety))  // already shown above
        .forEach(u => chips.push({ text: u, kind: "unverified", icon: ICONS.info }));

    if (car.matching_variant_count) {
        const n = car.matching_variant_count;
        chips.push({ text: `${n} matching variant${n === 1 ? "" : "s"}`, kind: "plain", icon: "" });
    }

    return chips;
}

function buildExtraChips(chips) {
    return chips.map(c => `<li class="tag tag--${c.kind}">${c.icon}<span>${escapeHtml(c.text)}</span></li>`).join("");
}

// --- banners, hints, toolbar ---
function buildUnsupportedBanner(data) {
    if (!data.unsupported_terms || !data.unsupported_terms.length) return "";
    const brands = data.unsupported_terms.join(", ");
    if (data.recommendations && data.recommendations.length) {
        // the brand part was ignored and the rest of the search ran: say what the list is based on instead
        const asked = understoodChips(data).chips.filter(c => c.kind === "ask").map(c => c.text);
        let instead = "Showing general picks instead.";
        if (asked.length === 1 && /^(Under|Above) /.test(asked[0])) instead = `Showing cars ${asked[0].charAt(0).toLowerCase()}${asked[0].slice(1)} instead.`;
        else if (asked.length) instead = `Showing cars matching ${asked.join(", ")} instead.`;
        return `<div class="notice" role="status">${ICONS.alert}<div>
        <strong>We don't cover ${escapeHtml(brands)}.</strong>
        <p>${escapeHtml(instead)}</p>
    </div></div>`;
    }
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
    // the pipeline run name is for debugging, not for shoppers: it sits in the tooltip only
    const run = data.data_as_of.kb_phase ? ` title="Data run: ${escapeHtml(data.data_as_of.kb_phase)}"` : "";
    return `<p class="data-stamp"${run}>Prices and specs updated ${escapeHtml(date)}</p>`;
}

// dropped-constraint banner + data stamp on the left; the sort control (v3 results with 2+ cars) and "Copy link" on the right
function buildResultsToolbar(data, link, sortable = false) {
    return `<div class="toolbar">
        <div class="toolbar-info">${buildDroppedBanner(data)}${buildDataStamp(data)}</div>
        <div class="toolbar-actions">${sortable ? buildSortControl() : ""}<button type="button" data-copy-link="${escapeHtml(link)}" class="btn btn-quiet">Copy link</button></div>
        ${sortable ? '<p class="sort-note" data-sort-note hidden></p>' : ""}
    </div>`;
}

// --- result card ---
// facts: electric -> "Range: 465 km"; CNG -> "Mileage: 26.4 km/kg" (never kmpl);
// others -> "Mileage: 19.2 kmpl". "Not listed" only when that value is truly null.
function buildFacts(car) {
    const eff = efficiency(car);
    const facts = [
        ["Gearbox", car.transmission_label || car.Transmission || "Not listed"],
        ["Fuel", car.Fuel_Type || "Not listed"],
        [eff.label, eff.text || (eff.label === "CNG mileage" ? "not listed" : "Not listed")]
    ];
    return `<ul class="facts">` + facts.map(([k, v]) => `<li><span class="fact-k">${k}:</span> <span class="fact-v">${escapeHtml(v)}</span></li>`).join("") + `</ul>`;
}

// the external CarDekho link is a quiet text link under the price; "View details" is the primary action
function buildPriceLink(link) {
    if (!link) return "";
    return `<a class="price-link" href="${escapeHtml(link)}" target="_blank" rel="noopener noreferrer">On-road price on CarDekho ${ICONS.external}<span class="sr-only">(opens in a new tab)</span></a>`;
}

// rank 1 is "Top pick" only when nothing is unmet or unverified; otherwise it is the closest match we found
function rankBadge(car, index) {
    if (index !== 0) return "";
    const clean = !(car.violations || []).length && !(car.not_verified || []).length;
    return clean ? '<span class="rank">Top pick</span>' : '<span class="rank rank--close">Closest match</span>';
}

function buildCarCard(car, index, recs, topScore, intent) {
    const name = `${car.Make} ${car.Model}`;
    const image = car.carImage || "/static/pic.avif";
    const caption = car.imageAttribution
        ? `Image: ${car.imageAttribution}`
        : (/\.svg$/.test(image) ? "Illustration: no photo of this model yet" : "");
    const match = matchLevel(car.ranking_score, topScore);
    const chips = chipList(car);
    const reasons = buyerReasons(car, recs, intent, chips.map(c => c.text));
    const tags = buildExtraChips(chips);
    const link = car.carDekhoLink;
    return `
        <article class="car${index === 0 ? " car--top" : ""}" aria-label="${escapeHtml(name)}" data-make-slug="${escapeHtml(slug(car.Make))}" data-model-slug="${escapeHtml(slug(car.Model))}">
            <figure class="car-photo">
                ${rankBadge(car, index)}
                <img src="${escapeHtml(image)}" alt="${escapeHtml(name)}" loading="${index < 3 ? "eager" : "lazy"}" decoding="async">
                ${caption ? `<figcaption>${escapeHtml(caption)}</figcaption>` : ""}
            </figure>
            <div class="car-body">
                <div class="car-head">
                    <div>
                        <h3 class="car-title"><a href="${escapeHtml(`/car/${encodeURIComponent(slug(car.Make))}/${encodeURIComponent(slug(car.Model))}`)}">${escapeHtml(name)}</a></h3>
                        ${car.Variant ? `<p class="car-variant">${escapeHtml(car.Variant)}</p>` : ""}
                    </div>
                    <p class="car-price"><strong>${formatPrice(car["Ex-Showroom_Price"])}</strong><span>ex-showroom</span>${buildPriceLink(link)}</p>
                </div>
                ${buildFacts(car)}
                <div class="car-fit">
                    <span class="match match--${match.key}">${match.label}</span>
                    ${reasons.length ? `<ul class="reasons" aria-label="Why it stands out">${reasons.map(r => `<li>${ICONS.check}<span>${escapeHtml(r)}</span></li>`).join("")}</ul>` : ""}
                </div>
                <div class="car-foot">
                    ${tags ? `<ul class="tags" aria-label="Features and safety">${tags}</ul>` : ""}
                    <div class="car-actions">
                        <button type="button" class="btn btn-primary" data-detail aria-expanded="false">View details</button>
                    </div>
                </div>
            </div>
        </article>`;
}

// ============================================
// v3 engine results (data.engine === "v3")
// ============================================
// Everything below is only used when the response says engine "v3". With the old engine none of it runs and the
// cards above are built exactly as before. All review text (notes, quotes, labels) goes through escapeHtml; a link
// is only drawn for an http(s) URL.

const FEW_OWNERS_BELOW = 0.15;   // an owner line resting on under 15% of the sampled reviews is labelled "a few owners"
const MAX_V3_REASONS = 4;
const V3_REASONS_SHOWN = 2;      // the collapsed card shows this many "Why this car" lines; the rest sit behind the reviews toggle
const THEME_LABELS = {
    reliability: "Reliability", service_cost: "Service cost", service_experience: "Service experience",
    real_world_mileage: "Real-world mileage", build_issues: "Build issues", recurring_fault: "Reported fault",
    satisfaction: "Overall satisfaction", resale: "Resale value"
};
const MIN_LABELS = {
    min_airbags: v => `${v}+ airbags`, min_boot_space_litres: v => `${v}+ L boot`,
    min_ground_clearance_mm: v => `ground clearance ${v}+ mm`, min_ev_range_km: v => `${v}+ km range`,
    min_mileage_kmpl: v => `${v}+ kmpl`, min_mileage_km_per_kg: v => `${v}+ km/kg`,
    min_safety_stars: v => `${v}+ star safety`
};
function safeUrl(url) {
    try {
        const u = new URL(String(url));
        return u.protocol === "https:" || u.protocol === "http:" ? u.href : "";
    } catch (error) {
        return "";
    }
}

function monthYear(text) {
    const m = /^(\d{4})-(\d{2})/.exec(String(text || ""));
    if (!m) return "";
    const names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
    return m[2] >= "01" && m[2] <= "12" ? `${names[Number(m[2]) - 1]} ${m[1]}` : "";
}

function sentenceCase(text) {
    const t = String(text || "").trim().toLowerCase();
    return t.charAt(0).toUpperCase() + t.slice(1);
}

function upperFirst(text) {
    const t = String(text || "");
    return t.charAt(0).toUpperCase() + t.slice(1);
}

// meta line pieces: each piece keeps its trailing separator, so a wrapped line never starts with a dot
function metaLine(parts, tail = "") {
    const list = parts.filter(Boolean);
    return list.map((t, i) => `<span class="seg${String(t).length <= 28 ? " seg--keep" : ""}">${escapeHtml(t)}${i < list.length - 1 || tail ? " \u00b7" : ""}</span>`).join(" ") + tail;
}

function externalLink(url, text) {
    const href = safeUrl(url);
    if (!href) return "";
    return `<a class="v3-link" href="${escapeHtml(href)}" target="_blank" rel="noopener noreferrer">${escapeHtml(text)} ${ICONS.external}<span class="sr-only">(opens in a new tab)</span></a>`;
}

// --- query echo: what the engine understood ---
// Returns chips { text, kind: "ask" | "soft" | "assumed" | "corrected", dropKey? } and the number of hard requirements.
function understoodChips(data) {
    const it = data.intent || {};
    const chips = [];
    let hard = 0;
    const need = (text) => { hard += 1; chips.push({ text, kind: "ask" }); };
    const b = it.budget || {};
    if (b.min != null && b.max != null) need(`${formatBudget(b.min)} to ${formatBudget(b.max)}`);
    else if (b.max != null) need(`Under ${formatBudget(b.max)}`);
    else if (b.min != null) need(`Above ${formatBudget(b.min)}`);
    (it.body_types || []).forEach(x => need(x.toUpperCase() === "SUV" || x === "mpv" ? x.toUpperCase() : upperFirst(x)));
    (it.fuel_types || []).forEach(x => need(x === "cng" ? "CNG" : upperFirst(x)));
    const t = it.transmission || {};
    if (t.family) need(upperFirst(t.family));
    // gearbox types asked for or ruled out ("DCT", "no CVT"); e-CVT rides along with a CVT exclusion, so it isn't repeated
    const GEARBOX = { manual: "Manual", imt: "iMT", amt: "AMT", dct: "DCT", cvt: "CVT", e_cvt: "e-CVT", torque_converter: "Torque converter", single_speed_ev: "Single-speed EV" };
    (t.include_types || []).forEach(x => need(GEARBOX[x] || x));
    (t.exclude_types || []).filter(x => !(x === "e_cvt" && (t.exclude_types || []).includes("cvt"))).forEach(x => need(`No ${GEARBOX[x] || x}`));
    if (it.seats_min != null) need(`${it.seats_min}+ seats`);
    (it.makes || []).forEach(x => need(x));
    (it.models || []).forEach(x => need(x));
    (it.required_features || []).forEach(x => need(FEATURE_LABELS[x] || x.replace(/_/g, " ")));
    Object.keys(MIN_LABELS).forEach(k => { if (it[k] != null) need(MIN_LABELS[k](it[k])); });
    (it.exclude_makes || []).forEach(x => need(`No ${x}`));
    (it.exclude_features || []).forEach(x => need(`No ${String(FEATURE_LABELS[x] || x.replace(/_/g, " ")).toLowerCase()}`));
    (it.exclude_body_types || []).forEach(x => need(`not ${x}`));
    (it.exclude_fuel_types || []).forEach(x => need(`not ${x}`));
    if (it.use_case) chips.push({ text: `for ${String(it.use_case).replace(/_/g, " ")}`, kind: "soft" });
    (it.soft_preferences || []).forEach(x => chips.push({ text: String(x).replace(/_/g, " "), kind: "soft" }));
    const options = data.assumed_options || [];
    Object.entries(data.assumed || {}).forEach(([kind, values]) => {
        const opt = options.find(o => o.kind === kind);
        (values || []).forEach(v => chips.push({ text: kind === "fuel_types" && v === "cng" ? "CNG" : (v === "suv" || v === "mpv" ? v.toUpperCase() : upperFirst(v)), kind: "assumed", dropKey: opt ? opt.key : "" }));
    });
    (data.corrections || []).forEach(c => chips.push({ text: `${c.from} → ${c.to}`, kind: "corrected" }));
    // attributes the catalogue cannot filter on: shown so the shopper knows they changed nothing
    (data.ignored_terms || []).forEach(x => chips.push({ text: `Didn't use: ${x}`, kind: "ignored" }));
    return { chips, hard };
}

function buildQueryEcho(data) {
    const { chips } = understoodChips(data);
    if (!chips.length) return "";
    const tag = { assumed: "assumed", corrected: "corrected" };
    const items = chips.map(c => {
        const mark = tag[c.kind] ? `<span class="echo-mark">${tag[c.kind]}</span>` : "";
        const off = c.dropKey ? `<button type="button" class="echo-off" data-drop-key="${escapeHtml(c.dropKey)}" aria-label="Remove assumption: ${escapeHtml(c.text)}">Remove</button>` : "";
        const tip = c.kind === "ignored" ? ` title="We can't filter on this yet, so it didn't change the results."` : "";
        return `<li class="echo echo--${c.kind}"${tip}><span>${escapeHtml(c.text)}</span>${mark}${off}</li>`;
    }).join("");
    return `<section class="echo-box" aria-label="What we understood from your search">
        <h3 class="echo-title">What we understood</h3>
        <ul class="echo-list">${items}</ul>
    </section>`;
}

// a vague search ("good car") is not personalised: instead of a paragraph, four ways to narrow it down. Each phrase is added to the
// search and run again; every one is read by the parser (budget, seats and use, gearbox and use, mileage).
const REFINERS = [
    { label: "Under ₹10 lakh", add: "under 10 lakh" },
    { label: "Family / 7 seats", add: "family 7 seater" },
    { label: "City / automatic", add: "city automatic" },
    { label: "Best mileage", add: "best mileage" }
];

function buildVagueNotice() {
    return `<div class="notice notice--vague" role="status">${ICONS.info.replace("<svg ", '<svg style="color:var(--accent-text)" ')}<div>
        <strong>This is a general shortlist, not personalised</strong>
        <p>Tap one to narrow it down:</p>
        <div class="refiners">${REFINERS.map(r => `<button type="button" class="refiner" data-refine="${escapeHtml(r.add)}">${escapeHtml(r.label)}</button>`).join("")}</div>
    </div></div>`;
}

function buildRelaxedNotice(data) {
    if (data.personalised === false && data.recommendations && data.recommendations.length) return buildVagueNotice();
    if (!data.relaxation && !(data.message && data.recommendations && data.recommendations.length)) return "";
    const icon = ICONS.info.replace("<svg ", '<svg style="color:var(--accent-text)" ');
    const rx = data.relaxation;
    if (!rx || !Array.isArray(rx.moves)) {
        // the uncovered-brand banner already says this; don't repeat it in a second notice
        if (!rx && !data.no_confirmed && (data.unsupported_terms || []).length && /isn't in our catalogue/.test(data.message || "")) return "";
        const text = rx ? rx.message : data.message;
        return `<div class="notice" role="status">${icon}<div>
        <strong>${rx ? "Nothing matched every requirement" : (data.no_confirmed ? "Requirements not confirmed" : "Please note")}</strong>
        <p>${escapeHtml(text)}</p>
    </div></div>`;
    }
    const head = rx.far ? "Nothing close exists in our catalogue; these are the nearest cars."
        : "No car matches everything you asked for.";
    const pills = rx.moves.map(m => `<li class="relax-pill">${escapeHtml(m.label)}</li>`).join("");
    const nv = /Not confirmed in our data for the cars shown: (.+?)\.\s*$/.exec(rx.message || "");
    const alts = (rx.alternatives || []).map(a => `<li><button type="button" class="relax-alt" data-drop-key="${escapeHtml(a.key)}">Without ${escapeHtml(a.label)} <span aria-hidden="true">·</span> ${a.models} ${a.models === 1 ? "model" : "models"}</button></li>`).join("");
    return `<div class="notice notice--relaxed" role="status">${icon}<div>
        <strong>${escapeHtml(head)}</strong>
        ${pills ? `<div class="relax-line">We relaxed: <ul class="relax-pills">${pills}</ul></div>` : ""}
        ${nv ? `<p>Not confirmed for the cars shown: ${escapeHtml(nv[1])}.</p>` : ""}
        ${alts ? `<p class="relax-line">Or drop one requirement instead:</p><ul class="relax-alts">${alts}</ul>` : ""}
    </div></div>`;
}

// --- match wording from the data ---
function v3MatchLabel(car, hard, personalised) {
    if (personalised === false) return { key: "neutral", text: car.match_label || "General pick, not personalised", detail: "" };
    // a blank value is not a pass: any unmet or unverified requirement is named on the card and the card never says "meets all"
    const violations = car.violations || [];
    const notVerified = car.not_verified || [];
    const detail = [
        ...violations.map(v => `Not met: ${v.text}`),
        ...notVerified.map(t => `Not verified: ${t.replace(/ not verified$/, "")}`),
    ];
    if (violations.length) {
        const met = Math.max(hard - violations.length - notVerified.length, 0);
        return { key: "near", text: hard ? `Meets ${met} of ${hard} requirements` : "Near match", detail };
    }
    if (notVerified.length) {
        return { key: "near", text: hard ? `Confirmed on ${Math.max(hard - notVerified.length, 0)} of ${hard} requirements` : "Requirements not confirmed", detail };
    }
    if (!hard) return { key: "ok", text: "Ranked on your preferences", detail: "" };
    return { key: "ok", text: hard === 1 ? "Meets your requirement" : "Meets all your requirements", detail: "" };
}

// --- ratings line ---
// One line of real values, no bars: the raw rating and its source, then the standing as words ("above average among SUVs").
// The standing words come from the server's own caption (car.expert_standing / car.owner_standing) and are shown only when the
// server made a standing claim (band top/upper/lower/bottom); a small segment or too few ratings shows the rating alone.
// A part is left out when its data is missing, and the whole line when both are.
const STANDING_BANDS = ["top", "upper", "lower", "bottom"];

// the standing as words: the server's wording for the reviewers ("above average for SUVs"); for owners the average bands alone, since the
// segment was just named on the reviewers' side of the same line
function standingWords(st, withSegment) {
    if (!STANDING_BANDS.includes(st.band)) return "";
    const tail = String(st.caption || "").split(" · ").pop();
    if (!/^(among|above|below) /.test(tail)) return "";
    if (withSegment) return tail.replace(/^(above|below) average among /, "$1 average for ");
    return tail.replace(/^((?:above|below) average)\b.*$/, "$1");
}

function ratingPart(label, value, scale, lead, bracket) {
    const inner = bracket.filter(Boolean).map(escapeHtml).join(", ");
    return `<span class="rating-part">${label}: <strong>${trimNumber(Number(value), 1)}/${trimNumber(Number(scale), 0)}</strong>${lead ? " " + escapeHtml(lead) : ""}${inner ? ` (${inner})` : ""}</span>`;
}

function buildRatingsLine(car) {
    const ex = car.expert_standing, ow = car.owner_standing, parts = [];
    if (ex && typeof ex === "object" && ex.score != null && ex.scale_max != null)
        parts.push(ratingPart("Reviewers", ex.score, ex.scale_max, "", [ex.source, standingWords(ex, true)]));
    if (ow && typeof ow === "object" && ow.rating != null && ow.scale_max != null) {
        const n = ow.rating_count != null && !isNaN(ow.rating_count) ? Number(ow.rating_count).toLocaleString("en-IN") : "";
        const lead = n ? `from ${ow.band === "low_confidence" ? "only " : ""}${n} rating${Number(ow.rating_count) === 1 ? "" : "s"}` : "";
        parts.push(ratingPart("Owners", ow.rating, ow.scale_max, lead, [standingWords(ow, false)]));
    }
    return parts.length ? `<p class="ratings">${parts.join('<span class="rating-sep" aria-hidden="true"> · </span>')}</p>` : "";
}

// --- reviews ---
// The collapsed card shows the one-line ratings summary, at most 2 "why" bullets and one caveat pill. "What reviewers say",
// "What owners say" and the full Caveats sit in one panel (`data-more` + `hidden`) that the card's "Reviews and owner feedback (n)"
// button opens; n counts the items in it.
let reviewsSeq = 0;

function buildExpertBlock(car) {
    const notes = (car.expert_notes || []).slice(0, 2);
    const hasScore = car.scores && car.scores.expert != null;
    let body;
    if (notes.length) {
        body = notes.map(n => {
            const meta = metaLine([n.source, sentenceCase(n.source_aspect),
                `${trimNumber(Number(n.score), 1)}/${trimNumber(Number(n.scale_max), 0)}`, monthYear(n.published_on)]);
            const q = n.quote && n.quote.text
                ? `<blockquote class="v3-quote"><p>“${escapeHtml(n.quote.text)}”</p>${externalLink(n.quote.source_url || n.source_url, "Read the review")}</blockquote>`
                : "";
            return `<li><p class="line-meta">${meta}</p><p class="line-note">${escapeHtml(n.note)}</p>${q}</li>`;
        }).join("");
        body = `<ul class="lines">${body}</ul>`;
    } else if (hasScore) {
        body = `<p class="muted">No review notes to show for this search.</p>`;
    } else {
        body = `<p class="muted">No expert review on file for this model.</p>`;
    }
    return `<section class="evi" aria-label="What reviewers say"><h4>What reviewers say</h4>${body}</section>`;
}

function ownerMeta(n) {
    const name = n.theme === "recurring_fault"
        ? `Reported fault${n.label ? ": " + n.label : ""}`
        : `${THEME_LABELS[n.theme] || upperFirst(String(n.theme || "").replace(/_/g, " "))}${n.label ? " - " + n.label : ""}`;
    const dir = n.theme === "recurring_fault" ? "" : upperFirst(n.direction || "");
    const count = `${Number(n.mentions)} of ${Number(n.posts_sampled)} reviews, ${n.source}`;
    const few = Number(n.share) < FEW_OWNERS_BELOW || (n.share == null && Number(n.mentions) / Number(n.posts_sampled) < FEW_OWNERS_BELOW);
    return { parts: [name, dir, count], few, dir: n.direction };
}

function ownerMetaHtml(n) {
    const m = ownerMeta(n);
    return metaLine(m.parts, m.few ? ' <span class="few">a few owners</span>' : "");
}

// owner lines shown under "What owners say": a theme already listed under Caveats is not repeated here
function ownerNotesShown(car) {
    const key = n => `${n.theme}|${n.label || ""}`;
    const seen = new Set((car.caveats || []).map(key));
    return (car.owner_notes || []).filter(n => !seen.has(key(n))).slice(0, 2);
}

function buildOwnerBlock(car) {
    const notes = ownerNotesShown(car);
    const st = car.owner_standing;
    let body;
    if (notes.length) {
        body = `<ul class="lines">` + notes.map(n => {
            return `<li><p class="line-meta">${ownerMetaHtml(n)}</p>${n.note ? `<p class="line-note">${escapeHtml(n.note)}</p>` : ""}</li>`;
        }).join("") + `</ul>`;
    } else if (st && st.summary) {
        // no theme line has enough verified mentions: the ratings summary instead of an empty block
        body = `<p class="line-note owner-summary">${escapeHtml(st.summary)}</p>`;
    } else if (car.scores && car.scores.owner != null) {
        body = `<p class="muted">No owner review themes to show for this search.</p>`;
    } else {
        body = `<p class="muted">No owner ratings available for this model.</p>`;
    }
    return `<section class="evi" aria-label="What owners say"><h4>What owners say</h4>${body}</section>`;
}

// fact ids the grounded explanation cites, in order of first use (they become the numbered sources)
function ragOrder(rag) {
    const facts = rag.facts || {}, order = [];
    (rag.sentences || []).forEach(s => (s.cites || []).filter(id => facts[id]).forEach(id => { if (!order.includes(id)) order.push(id); }));
    return order;
}

// items behind the "Reviews and owner feedback" toggle; the button is drawn only when this is above 0
function behindCount(car) {
    const reasons = (car.reasons || []).slice(0, MAX_V3_REASONS).length;
    let n = (car.expert_notes || []).slice(0, 2).length + (car.caveats || []).length;
    const ow = ownerNotesShown(car).length;
    n += ow || (car.owner_standing && car.owner_standing.summary ? 1 : 0);
    n += car.explanation_rag ? ragOrder(car.explanation_rag).length + reasons : Math.max(reasons - V3_REASONS_SHOWN, 0);
    return n;
}

// grounded explanation: the sentences with numbered source markers, then the numbered sources (hidden until the card is expanded)
function buildWhyRag(car, reasons, reviewsId) {
    const rag = car.explanation_rag;
    const facts = rag.facts || {};
    const order = ragOrder(rag);           // fact ids in order of first use
    const numberOf = id => order.indexOf(id) + 1;
    const sentences = (rag.sentences || []).map(s => {
        const markers = (s.cites || []).filter(id => facts[id]).map(id => {
            const n = numberOf(id);
            return `<a class="cite" href="#src-${reviewsId}-${n}" data-cite aria-label="${escapeHtml(`Source ${n}: ${facts[id].label || ""}`)}">${n}</a>`;
        }).join("");
        return `${escapeHtml(s.text)}${markers}`;
    }).join(" ");
    const sources = order.map((id, i) => {
        const f = facts[id], n = i + 1;
        const url = String(f.source_url || "");
        const name = f.source ? (/^https?:\/\//i.test(url)
            ? `<a href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(f.source)}<span class="sr-only"> (opens in a new tab)</span></a>`
            : escapeHtml(f.source)) : "";
        const date = monthYear(f.date);
        return `<li id="src-${reviewsId}-${n}" tabindex="-1">${escapeHtml(f.label || "")}${name ? ` · ${name}` : ""}${date ? ` · ${escapeHtml(date)}` : ""}</li>`;
    }).join("");
    const template = reasons.length
        ? `<p class="why-sub" data-more hidden>How the engine scored it</p><ul class="reasons reasons--v3">${reasons.map(r => `<li data-more hidden>${ICONS.check}<span>${escapeHtml(r.text)}</span></li>`).join("")}</ul>` : "";
    return `<section class="why" aria-label="Why this car"><h4>Why this car</h4>
        <p class="why-rag">${sentences}</p>
        <p class="why-rag-note">${ICONS.info}<span>Written by AI from the numbered sources, and checked against them before showing.</span></p>
        ${order.length ? `<ol class="why-sources" data-more hidden>${sources}</ol>` : ""}${template}</section>`;
}

// A citation opens the card to show its source. The clicked citation stays where it is on screen (the source list opens below
// it), focus moves to the source item without the browser's own scroll, and the source is scrolled only as far as needed.
function followCite(link) {
    const card = link.closest(".car--v3");
    const target = card && card.querySelector(`[id="${link.getAttribute("href").slice(1)}"]`);
    if (!card || !target) return;
    const before = link.getBoundingClientRect().top;
    if (card.dataset.reviews === "collapsed") {
        const button = card.querySelector("[data-reviews-toggle]");
        if (button) toggleReviews(button);
    }
    const drift = link.getBoundingClientRect().top - before;
    if (drift) window.scrollBy(0, drift);
    target.focus({ preventScroll: true });
    target.scrollIntoView({ block: "nearest", behavior: prefersReducedMotion() ? "auto" : "smooth" });
    target.classList.add("is-target");
    setTimeout(() => target.classList.remove("is-target"), 1600);
}

function buildReviewsToggle(controlsId, n) {
    return `<button type="button" class="btn btn-quiet btn-reviews" data-reviews-toggle aria-expanded="false" aria-controls="${controlsId}"><span>Reviews and owner feedback (${n})</span>${ICONS.chevron}</button>`;
}

function toggleReviews(button) {
    const card = button.closest(".car--v3");
    if (!card) return;
    const open = button.getAttribute("aria-expanded") !== "true";
    button.setAttribute("aria-expanded", String(open));
    card.dataset.reviews = open ? "expanded" : "collapsed";
    card.querySelectorAll("[data-more]").forEach(el => { el.hidden = !open; });
}

// full list, shown behind the toggle
function buildCaveats(car) {
    const items = car.caveats || [];
    if (!items.length) return "";
    return `<section class="caveats" aria-label="Caveats from owners">
        <h4>${ICONS.info}Caveats</h4>
        <ul class="lines">` + items.map(n => {
            return `<li><p class="line-meta">${ownerMetaHtml(n)}</p>${n.note ? `<p class="line-note">${escapeHtml(n.note)}</p>` : ""}</li>`;
        }).join("") + `</ul></section>`;
}

// collapsed card: the first caveat as one line, the rest (and the notes) behind the toggle
function buildCaveatPill(car) {
    const items = car.caveats || [];
    if (!items.length) return "";
    const c = items[0];
    const what = c.label || THEME_LABELS[c.theme] || String(c.theme || "").replace(/_/g, " ");
    const text = `Owners report: ${what.charAt(0).toLowerCase()}${what.slice(1)}${items.length > 1 ? ` (+${items.length - 1} more)` : ""}`;
    return `<p class="caveat-pill" title="${escapeHtml(text)}">${ICONS.info}<span>${escapeHtml(text)}</span></p>`;
}

// unverified requirements are already named as pills under the match label on personalised cards; repeat them here
// only when no match label lists them (general, non-personalised picks)
function v3Chips(car, personalised) {
    const chips = [];
    (car.matched_features || []).forEach(f => chips.push({ text: FEATURE_LABELS[f] || f, kind: "feature", icon: ICONS.check }));
    const notVerified = car.not_verified || [];
    if (car.safety) {
        const year = car.safety.year ? ` (${car.safety.year})` : "";
        chips.push({ text: `${car.safety.stars_adult}-star ${car.safety.testing_body}${year}`, kind: "safety", icon: ICONS.star });
    } else if (!notVerified.some(t => /crash rating/i.test(t))) {
        chips.push({ text: NO_RATING_LABEL, kind: "unverified", icon: ICONS.info });
    }
    if (personalised === false) notVerified.forEach(t => chips.push({ text: upperFirst(t), kind: "unverified", icon: ICONS.info }));
    if (car.matching_variant_count) {
        const n = car.matching_variant_count;
        chips.push({ text: `${n} matching variant${n === 1 ? "" : "s"}`, kind: "plain", icon: "" });
    }
    return chips;
}

function buildV3Card(car, index, hard, personalised) {
    const name = `${car.Make} ${car.Model}`;
    const image = car.carImage || "/static/pic.avif";
    const caption = car.imageAttribution
        ? `Image: ${car.imageAttribution}`
        : (/\.svg$/.test(image) ? "Illustration: no photo of this model yet" : "");
    const label = v3MatchLabel(car, hard, personalised);
    const reasons = (car.reasons || []).slice(0, MAX_V3_REASONS);
    const link = car.carDekhoLink;
    const also = car.also_available_from;
    const alsoHtml = also && also["Ex-Showroom_Price"]
        ? `<p class="also">Also available from <strong>${formatPrice(also["Ex-Showroom_Price"])}</strong>${also.variant ? ` (${escapeHtml(also.variant)})` : ""}</p>` : "";
    const detail = Array.isArray(label.detail) && label.detail.length
        ? `<ul class="unmet" aria-label="Requirements this car does not meet or could not confirm">${label.detail.map(d => `<li>${escapeHtml(d)}</li>`).join("")}</ul>` : "";
    const chips = v3Chips(car, personalised);
    const behind = behindCount(car);
    const reviewsId = `reviews-${++reviewsSeq}`;
    const why = car.explanation_rag ? buildWhyRag(car, reasons, reviewsId)
        : reasons.length ? `<section class="why" aria-label="Why this car"><h4>Why this car</h4><ul class="reasons reasons--v3">${reasons.map((r, i) => `<li${i >= V3_REASONS_SHOWN ? " data-more hidden" : ""}>${ICONS.check}<span>${escapeHtml(r.text)}</span></li>`).join("")}</ul></section>` : "";
    return `
        <article class="car car--v3${index === 0 ? " car--top" : ""}" data-rank-index="${index}"${behind ? ' data-reviews="collapsed"' : ""} aria-label="${escapeHtml(name)}" data-make-slug="${escapeHtml(slug(car.Make))}" data-model-slug="${escapeHtml(slug(car.Model))}">
            <figure class="car-photo">
                ${rankBadge(car, index)}
                <img src="${escapeHtml(image)}" alt="${escapeHtml(name)}" loading="${index < 3 ? "eager" : "lazy"}" decoding="async">
                ${caption ? `<figcaption>${escapeHtml(caption)}</figcaption>` : ""}
            </figure>
            <div class="car-body">
                <div class="car-head">
                    <div>
                        <h3 class="car-title"><a href="${escapeHtml(`/car/${encodeURIComponent(slug(car.Make))}/${encodeURIComponent(slug(car.Model))}`)}">${escapeHtml(name)}</a></h3>
                        ${car.Variant ? `<p class="car-variant">${escapeHtml(car.Variant)}</p>` : ""}
                    </div>
                    <p class="car-price"><strong>${formatPrice(car["Ex-Showroom_Price"])}</strong><span>ex-showroom</span>${buildPriceLink(link)}</p>
                </div>
                ${alsoHtml}
                ${buildFacts(car)}
                <div class="v3-fit">
                    <p class="fit-label fit-label--${label.key}">${escapeHtml(label.text)}</p>
                    ${detail}
                    ${buildRatingsLine(car)}
                </div>
                ${why}
                ${buildCaveatPill(car)}
                <div class="car-foot">
                    ${chips.length ? `<ul class="tags" aria-label="Features, safety and what is not verified">${buildExtraChips(chips)}</ul>` : ""}
                    <div class="car-actions">
                        <button type="button" class="btn btn-primary" data-detail aria-expanded="false">View details</button>
                        ${buildCompareButton(car)}
                        ${behind ? buildReviewsToggle(reviewsId, behind) : ""}
                    </div>
                </div>
            </div>
            ${behind ? `<div class="v3-more" id="${reviewsId}" data-more hidden>
                <div class="evi-grid">${buildExpertBlock(car)}${buildOwnerBlock(car)}</div>
                ${buildCaveats(car)}
            </div>` : ""}
        </article>`;
}

function buildSourcesFooter(recs, data) {
    const dates = [];
    recs.forEach(c => (c.expert_notes || []).forEach(n => { if (/^\d{4}-\d{2}/.test(n.published_on || "")) dates.push(String(n.published_on).slice(0, 7)); }));
    dates.sort();
    const span = dates.length ? (monthYear(dates[0]) === monthYear(dates[dates.length - 1]) ? monthYear(dates[0]) : `${monthYear(dates[0])} to ${monthYear(dates[dates.length - 1])}`) : "";
    const exported = data.data_as_of && data.data_as_of.exported ? escapeHtml(data.data_as_of.exported) : "";
    return `<p class="sources">Expert scores and notes are from Autocar India${span ? ` (reviews dated ${escapeHtml(span)}, each note shows its own date)` : ""}; owner ratings and themes are from CarWale user reviews${exported ? ` (data exported ${exported})` : ""}. Notes are short summaries, not the original text: use the links to read the originals.</p>`;
}

// ============================================
// Compare (up to 4 cars) and sort
// ============================================
// Selection is page-level and lives in sessionStorage so it survives new searches and the trip to /compare and back.
// Every storage call is in try/catch; without storage the selection still works for the life of the page.
const COMPARE_KEY = "carrec.compare";
const COMPARE_MAX = 4;
let compareMemory = [];

function compareName(item) {
    return `${item.model || item.name} ${item.variant || ""}`.trim();
}

function compareState() {
    try {
        const list = JSON.parse(sessionStorage.getItem(COMPARE_KEY) || "[]");
        if (Array.isArray(list)) {
            compareMemory = list.filter(x => x && Number(x.variant_id) > 0).slice(0, COMPARE_MAX);
        }
    } catch (error) { /* storage blocked or unreadable: keep the in-page copy */ }
    return compareMemory.slice();
}

function saveCompareState(list) {
    compareMemory = list.slice(0, COMPARE_MAX);
    try { sessionStorage.setItem(COMPARE_KEY, JSON.stringify(compareMemory)); } catch (error) { /* in-page copy only */ }
}

// Pure: the list after pressing Compare on `item`. action is "added", "removed" or "full" (a fifth car changes nothing).
function toggleCompare(list, item) {
    const id = Number(item.variant_id);
    if (list.some(x => Number(x.variant_id) === id)) return { list: list.filter(x => Number(x.variant_id) !== id), action: "removed" };
    if (list.length >= COMPARE_MAX) return { list: list.slice(), action: "full" };
    return { list: [...list, { variant_id: id, name: item.name, model: item.model, variant: item.variant }], action: "added" };
}

// /compare?ids=1,2,3&q=...&drop=...&sort=...  (the commas in ids stay readable; sort is left out for best match)
function compareUrl(list, q, drop, sort) {
    const params = new URLSearchParams();
    if (q) params.set("q", q);
    const d = Array.isArray(drop) ? drop.join(",") : (drop || "");
    if (d) params.set("drop", d);
    if (sort && sort !== "best") params.set("sort", sort);
    const rest = params.toString();
    return `/compare?ids=${list.map(x => Number(x.variant_id)).join(",")}${rest ? "&" + rest : ""}`;
}

function buildCompareButton(car) {
    if (car.variant_id == null) return "";
    const name = `${car.Make} ${car.Model}`;
    return `<button type="button" class="btn btn-quiet btn-compare" data-compare="${escapeHtml(car.variant_id)}" data-compare-name="${escapeHtml(name)}" data-compare-model="${escapeHtml(car.Model)}" data-compare-variant="${escapeHtml(car.Variant || "")}" aria-pressed="false"><span class="compare-text" aria-hidden="true">Compare</span><span class="sr-only">Compare ${escapeHtml(`${name} ${car.Variant || ""}`.trim())}</span></button>`;
}

// the inner markup of the tray; "" when nothing is selected. Wide screens list the cars as pills; narrow ones show a count.
function buildCompareTray(list, q, drop, sort) {
    const n = list.length;
    if (!n) return "";
    const pills = list.map(x => `<li class="compare-pill"><span>${escapeHtml(compareName(x))}</span><button type="button" data-compare-remove="${escapeHtml(x.variant_id)}" aria-label="Remove ${escapeHtml(`${x.name} ${x.variant || ""}`.trim())}">${ICONS.close}</button></li>`).join("");
    const go = n < 2
        ? '<span class="btn btn-primary" aria-disabled="true">Compare</span>'
        : `<a class="btn btn-primary" href="${escapeHtml(compareUrl(list, q, drop, sort))}">Compare<span class="compare-more"> ${n} cars</span></a>`;
    return `<div class="wrap">
        <ul class="compare-pills" aria-label="Cars to compare">${pills}</ul>
        ${n < 2 ? '<p class="compare-hint">Pick 1 more car to compare</p>' : `<p class="compare-count">${n} cars selected</p>`}
        <button type="button" class="btn btn-quiet" data-compare-clear aria-label="Clear the comparison">Clear</button>
        ${go}
    </div>`;
}

// the search the tray's link should open the comparison from: the latest turn, else the URL
function compareContext() {
    const turns = document.querySelectorAll("[data-turn]");
    const last = turns[turns.length - 1];
    if (!last) { const u = searchFromUrl(); return { q: u.q, drop: u.drop, sort: u.sort }; }
    const cards = last.querySelector(".cards");
    return { q: last.dataset.q || "", drop: last.dataset.drop || "", sort: cards ? cards.dataset.sort : "" };
}

function renderCompareTray() {
    if (typeof document === "undefined") return;
    const page = document.querySelector(".results-page");
    if (!page) return;
    let tray = document.getElementById("compare-tray");
    if (!tray) {
        tray = document.createElement("div");
        tray.id = "compare-tray";
        tray.className = "compare-tray";
        tray.setAttribute("role", "region");
        tray.setAttribute("aria-label", "Compare cars");
        tray.hidden = true;
        tray.addEventListener("click", e => {
            const remove = e.target.closest("[data-compare-remove]");
            if (remove) changeCompare(list => {
                const item = list.find(x => String(x.variant_id) === remove.dataset.compareRemove);
                return item ? toggleCompare(list, item) : { list, action: "none", item };
            });
            if (e.target.closest("[data-compare-clear]")) {
                saveCompareState([]);
                refreshCompare();
                setSearchStatus("Comparison cleared.");
            }
        });
        page.appendChild(tray);
    }
    const list = compareState();
    const ctx = compareContext();
    tray.innerHTML = buildCompareTray(list, ctx.q, ctx.drop, ctx.sort);
    tray.hidden = list.length === 0;
    document.body.classList.toggle("has-compare-tray", list.length > 0);
}

// every Compare button mirrors the selection; with 4 selected the others stay focusable but are marked aria-disabled
function syncCompareButtons(root) {
    const list = compareState();
    const full = list.length >= COMPARE_MAX;
    (root || document).querySelectorAll("[data-compare]").forEach(btn => {
        const on = list.some(x => String(x.variant_id) === btn.dataset.compare);
        btn.setAttribute("aria-pressed", on ? "true" : "false");
        btn.classList.toggle("is-added", on);
        const text = btn.querySelector(".compare-text");
        if (text) text.textContent = on ? "Added" : "Compare";
        const icon = btn.querySelector("svg");
        if (on && !icon) btn.insertAdjacentHTML("afterbegin", ICONS.check);
        if (!on && icon) icon.remove();
        if (full && !on) { btn.setAttribute("aria-disabled", "true"); btn.title = "You can compare up to 4 cars"; }
        else { btn.removeAttribute("aria-disabled"); btn.removeAttribute("title"); }
    });
}

function refreshCompare() {
    renderCompareTray();
    syncCompareButtons(document);
}

// `change(list)` returns { list, action, item? }; saves, redraws and says what happened in the status line
function changeCompare(change) {
    const before = compareState();
    const result = change(before);
    if (result.action === "full") {
        setSearchStatus("You can compare up to 4 cars. Remove one first.");
        return;
    }
    if (result.action === "none") return;
    saveCompareState(result.list);
    refreshCompare();
    const item = before.concat(result.list).find(x => !(result.action === "added" ? before : result.list).some(y => y.variant_id === x.variant_id));
    const name = item ? compareName(item) : "Car";
    setSearchStatus(result.action === "added"
        ? `${name} added to compare. ${result.list.length} of ${COMPARE_MAX} selected.`
        : `${name} removed from compare. ${result.list.length} of ${COMPARE_MAX} selected.`);
}

function onCompareButton(btn) {
    if (btn.getAttribute("aria-disabled") === "true") {
        setSearchStatus("You can compare up to 4 cars. Remove one first.");
        return;
    }
    changeCompare(list => toggleCompare(list, {
        variant_id: Number(btn.dataset.compare), name: btn.dataset.compareName,
        model: btn.dataset.compareModel, variant: btn.dataset.compareVariant
    }));
}

// --- sort ---
const SORT_OPTIONS = [
    { key: "best", label: "Best match", said: "best match" },
    { key: "price", label: "Price", said: "price, lowest first" },
    { key: "mileage", label: "Mileage", said: "mileage, highest first" },
    { key: "safety", label: "Safety", said: "safety rating, most adult stars first" }
];
const SORT_KEYS = SORT_OPTIONS.map(o => o.key);
const MILEAGE_GROUPS = ["kmpl", "kmkg", "range"];
let sortSeq = 0;
const sortableRecs = new WeakMap();   // the turn's cards in best-match order, keyed by the turn's result box

// New order as an array of indices into recs. Stable: ties keep best-match order. Unknown values go last.
function sortCars(recs, key) {
    const idx = recs.map((_, i) => i);
    const cmpNullLast = (a, b, dir) => (a == null) - (b == null) || (a == null ? 0 : dir * (a - b));
    let cmp;
    if (key === "price") {
        cmp = (a, b) => cmpNullLast(Number(recs[a]["Ex-Showroom_Price"]) || null, Number(recs[b]["Ex-Showroom_Price"]) || null, 1);
    } else if (key === "mileage") {
        // one unit per group, so a litre of petrol is never ranked against a kilogram of CNG or a battery
        cmp = (a, b) => {
            const ea = efficiency(recs[a]), eb = efficiency(recs[b]);
            return (MILEAGE_GROUPS.indexOf(ea.kind) - MILEAGE_GROUPS.indexOf(eb.kind)) || cmpNullLast(ea.value, eb.value, -1);
        };
    } else if (key === "safety") {
        const stars = c => (c.safety && c.safety.stars_adult != null ? Number(c.safety.stars_adult) : null);
        const bags = c => (Number(c.airbags) || 0);
        cmp = (a, b) => cmpNullLast(stars(recs[a]), stars(recs[b]), -1) || (stars(recs[a]) == null ? 0 : bags(recs[b]) - bags(recs[a]));
    } else {
        return idx;
    }
    return idx.sort((a, b) => cmp(a, b) || a - b);
}

// the one-line caveat under the toolbar when a sort mixes things that are not strictly alike
function sortNote(recs, key) {
    if (key === "mileage" && new Set(recs.map(r => efficiency(r).kind)).size > 1) {
        return "Petrol and diesel cars sort by kmpl, CNG by km/kg and electric cars by range, each in its own group.";
    }
    if (key === "safety" && new Set(recs.filter(r => r.safety && r.safety.stars_adult != null).map(r => r.safety.testing_body)).size > 1) {
        return "Global NCAP and Bharat NCAP stars are sorted together, but the tests differ.";
    }
    return "";
}

// segmented control from 600px, select below; both are in the page and drive the same sort
function buildSortControl() {
    const id = ++sortSeq;
    const radios = SORT_OPTIONS.map(o => `<input type="radio" name="sort-${id}" id="sort-${id}-${o.key}" value="${o.key}" data-sort-key${o.key === "best" ? " checked" : ""}><label for="sort-${id}-${o.key}">${o.label}</label>`).join("");
    const options = SORT_OPTIONS.map(o => `<option value="${o.key}">${o.label}</option>`).join("");
    return `<fieldset class="sort-seg"><legend>Sort</legend><div class="sort-opts">${radios}</div></fieldset>`
        + `<label class="sort-select"><span>Sort</span><select data-sort-select>${options}</select></label>`;
}

function applySort(turn, key) {
    if (!SORT_KEYS.includes(key)) return;
    const box = turn.querySelector("[data-turn-body]");
    const recs = box && sortableRecs.get(box);
    const cards = turn.querySelector(".cards");
    if (!recs || !cards) return;
    // move the existing nodes instead of redrawing: open detail panels and expanded reviews stay as they are
    const byIndex = {};
    cards.querySelectorAll(":scope > article.car").forEach(c => { byIndex[c.dataset.rankIndex] = c; });
    sortCars(recs, key).forEach(i => { if (byIndex[i]) cards.appendChild(byIndex[i]); });
    cards.dataset.sort = key;
    turn.querySelectorAll("input[data-sort-key]").forEach(r => { r.checked = r.value === key; });
    turn.querySelectorAll("select[data-sort-select]").forEach(sel => { sel.value = key; });
    const note = turn.querySelector("[data-sort-note]");
    if (note) {
        note.textContent = sortNote(recs, key);
        note.hidden = !note.textContent;
    }
    // the shareable link carries the order; the address bar follows only the latest search
    const suffix = key === "best" ? "" : `&sort=${key}`;
    const copy = turn.querySelector("[data-copy-link]");
    if (copy) copy.dataset.copyLink = location.origin + searchUrl(turn.dataset.q || "", turn.dataset.drop ? turn.dataset.drop.split(",") : []) + suffix;
    const turns = document.querySelectorAll("[data-turn]");
    if (turns[turns.length - 1] === turn) {
        const params = new URLSearchParams(location.search);
        if (key === "best") params.delete("sort"); else params.set("sort", key);
        window.history.replaceState(window.history.state, "", `${location.pathname}?${params}`);
    }
    setSearchStatus(`Sorted by ${SORT_OPTIONS.find(o => o.key === key).said}.`);
    renderCompareTray();
}

function renderV3Results(box, data, banner, link) {
    const recs = data.recommendations || [];
    const { hard } = understoodChips(data);
    const personalised = data.personalised;
    sortableRecs.set(box, recs);
    box.innerHTML = banner + buildRelaxedNotice(data) + buildQueryEcho(data) + buildResultsToolbar(data, link, recs.length >= 2)
        + `<div class="cards" data-sort="best">${recs.map((car, i) => buildV3Card(car, i, hard, personalised)).join("")}</div>`
        + buildSourcesFooter(recs, data);
}

// --- car detail (inline panel under a card, and the /car/<make>/<model> permalink page) ---
// One component: renderDetail() draws GET /api/car/... for both. The inline panel is short: Summary, Key specs and a
// "Full details" link. The car page runs: Summary, (reviewers, owners and caveats when opened from a search),
// Specifications, Safety, Warranty (for the selected variant), then Variants, the data stamp and actions.
const DETAIL_SPEC_GROUPS = ["Engine & performance", "Dimensions & capacity", "Comfort & convenience", "Technology"];

function detailUrl(base, opts) {
    const params = new URLSearchParams();
    if (opts.q) params.set("q", opts.q);
    if (opts.drop && opts.drop.length) params.set("drop", opts.drop.join(","));
    if (opts.variantId) params.set("variant_id", opts.variantId);
    const query = params.toString();
    return `${base}/${encodeURIComponent(opts.make)}/${encodeURIComponent(opts.model)}${query ? "?" + query : ""}`;
}

function specList(items) {
    const shown = items.filter(i => i.status !== "not_applicable" || i.note);
    if (!shown.length) return "";
    return `<dl class="spec-list">` + shown.map(i => `<div><dt>${escapeHtml(i.label)}</dt><dd>${
        i.status === "ok" ? escapeHtml(i.value_display)
            : i.note ? `<span class="not-verified">${escapeHtml(i.note)}</span>`
            : '<span class="not-verified">Not verified</span>'
    }</dd></div>`).join("") + `</dl>`;
}

function variantMileage(v) {
    const m = v.mileage_display;
    return m.value || (m.unit === "km/kg" ? "CNG mileage not listed" : "Not listed");
}

const VARIANT_ROWS_SHOWN = 8;

// With a search, the table opens on the variants the server says match it (matches_query: the same filter /predict used for
// the card's "N matching variants"); without one, on the first rows by price. Either way at most VARIANT_ROWS_SHOWN rows, the
// selected variant always among them, and a button shows or hides the rest in place. All rows are in the HTML; the extra ones are hidden.
function buildVariantsTable(data, hasQuery) {
    const rows = [...data.variants].sort((a, b) =>
        (b.matches_query - a.matches_query) || ((a.price || 0) - (b.price || 0)) || (a.variant_id - b.variant_id));
    const matching = rows.filter(v => v.matches_query).length;
    const matchMode = hasQuery && matching > 0;
    let visible = (matchMode ? rows.filter(v => v.matches_query) : rows).slice(0, VARIANT_ROWS_SHOWN);
    const selectedRow = rows.find(v => v.variant_id === data.selected_variant_id);
    if (selectedRow && !visible.includes(selectedRow)) visible = [...visible.slice(0, VARIANT_ROWS_SHOWN - 1), selectedRow];
    const note = hasQuery
        ? (matching ? `${matching} of ${rows.length} variants match your search.` : `None of the ${rows.length} variants match your search.`)
        : `${rows.length} variants.`;
    const toggle = rows.length > visible.length
        ? `<button type="button" class="btn btn-quiet variants-toggle" data-variants-toggle data-total="${rows.length}" data-match-mode="${matchMode}" aria-expanded="false" aria-controls="variants-table">Show all ${rows.length} variants</button>` : "";
    return `<p class="detail-note">${note} Select a variant to see its specifications.</p>
        <p class="pick-status" id="pick-status" role="status"></p>
        <div class="table-wrap" id="variants-table" tabindex="0" role="region" aria-label="Variants">
        <table class="variants">
            <thead><tr><th scope="col">Variant</th><th scope="col">Price</th><th scope="col">Gearbox</th><th scope="col">Fuel</th><th scope="col">Mileage</th></tr></thead>
            <tbody>${rows.map(v => {
                const selected = v.variant_id === data.selected_variant_id;
                return `<tr data-variant-id="${v.variant_id}" class="${v.matches_query ? "is-match" : ""}${selected ? " is-selected" : ""}"${selected ? ' aria-current="true"' : ""}${visible.includes(v) ? "" : " data-extra hidden"}>
                    <td><button type="button" class="variant-pick" data-variant-id="${v.variant_id}" aria-pressed="${selected}">${escapeHtml(v.variant)}</button>
                        ${v.matches_query ? '<span class="match-badge">Matches your search</span>' : ""}</td>
                    <td>${formatPrice(v.price)}</td>
                    <td>${escapeHtml(v.transmission_label)}</td>
                    <td>${escapeHtml(v.fuel_label)}</td>
                    <td>${escapeHtml(variantMileage(v))}</td>
                </tr>`;
            }).join("")}</tbody>
        </table></div>${toggle}`;
}

function toggleVariants(button) {
    const expand = button.getAttribute("aria-expanded") !== "true";
    const wrap = button.parentElement.querySelector(".table-wrap");
    button.setAttribute("aria-expanded", String(expand));
    wrap.querySelectorAll("tr[data-extra]").forEach(tr => { tr.hidden = !expand; });
    button.textContent = expand ? (button.dataset.matchMode === "true" ? "Show matching only" : `Show first ${VARIANT_ROWS_SHOWN}`)
        : `Show all ${button.dataset.total} variants`;
    if (!expand) wrap.scrollTop = 0;
}

function buildSafetySection(data) {
    const group = data.specs.find(g => g.group === "Safety");
    const s = data.safety;
    const rating = s
        ? `<p class="ncap">${ICONS.star}<span><strong>${s.stars_adult}-star</strong> adult${s.stars_child != null ? ` · <strong>${s.stars_child}-star</strong> child` : ""} · ${escapeHtml(s.testing_body)}${s.year ? ` (${s.year})` : ""}</span></p>`
        : `<p class="ncap ncap--none">${ICONS.info}<span>${NO_RATING_LABEL}</span></p>`;
    return rating + (group ? specList(group.items) : "");
}

// what the inline panel shows of the selected variant
const KEY_SPEC_LABELS = ["Engine", "Power", "Gearbox", "Fuel", "Mileage (ARAI)", "CNG mileage (ARAI)", "Range (claimed)",
    "Seats", "Boot space", "Airbags", "Sunroof", "ADAS"];

function keySpecs(data) {
    const items = data.specs.flatMap(g => g.items)
        .filter(i => i.status !== "not_applicable" && KEY_SPEC_LABELS.includes(i.label))
        .sort((a, b) => KEY_SPEC_LABELS.indexOf(a.label) - KEY_SPEC_LABELS.indexOf(b.label));
    return specList(items);
}

// the selected variant's name and price, as the line above its specs
function selectedNote(data) {
    const selected = data.variants.find(v => v.variant_id === data.selected_variant_id);
    return selected ? `For <strong>${escapeHtml(selected.variant)}</strong> · ${formatPrice(selected.price)}` : "";
}

// Specifications, Safety and Warranty for the selected variant: the part that is redrawn when another variant is picked
function buildSpecRegion(data, sh, sub) {
    const specGroups = data.specs.filter(g => DETAIL_SPEC_GROUPS.includes(g.group))
        .map(g => { const list = specList(g.items); return list ? `<div class="spec-group"><${sub}>${escapeHtml(g.group)}</${sub}>${list}</div>` : ""; })
        .join("");
    const warranty = data.specs.find(g => g.group === "Warranty");
    return `<section class="detail-section"><${sh}>Specifications</${sh}>
            <p class="detail-note">${selectedNote(data)} · <a class="detail-jump" href="#detail-variants">Change variant ↓</a></p>
            <div class="spec-groups">${specGroups}</div></section>
        <section class="detail-section"><${sh}>Safety</${sh}>${buildSafetySection(data)}</section>
        <section class="detail-section"><${sh}>Warranty</${sh}>${warranty ? specList(warranty.items) : ""}
            <p class="detail-note">${warranty && warranty.items.some(i => i.status === "ok")
                ? "From the manufacturer's brochure. Confirm the terms with the dealer."
                : "We couldn't verify this car's warranty from a brochure; check with the dealer."}</p></section>`;
}

// the same blocks as a result card's expanded panel, for a car page opened from a search; its headings sit under the page's h2
function buildReviewsSection(reviews) {
    if (!reviews) return "";
    const h3 = html => html.replace(/<h4>/g, "<h3>").replace(/<\/h4>/g, "</h3>");
    return `<section class="detail-section detail-reviews"><h2>What reviewers and owners say</h2>
        ${buildRatingsLine(reviews)}
        <div class="evi-grid">${h3(buildExpertBlock(reviews))}${h3(buildOwnerBlock(reviews))}</div>
        ${h3(buildCaveats(reviews))}</section>`;
}

function renderDetail(data, opts) {
    const hasQuery = Boolean(opts.q);
    const selectedId = data.selected_variant_id;
    const permalink = location.origin + detailUrl("/car", { ...opts, variantId: selectedId });
    const summary = `<section class="detail-section"><${opts.standalone ? "h2" : "h3"}>Summary</${opts.standalone ? "h2" : "h3"}><p class="detail-summary">${escapeHtml(data.summary)}</p></section>`;
    if (!opts.standalone) {
        // the inline panel: Summary, Key specs and the way to the whole page, carrying this search and variant
        const full = detailUrl("/car", { ...opts, variantId: selectedId });
        return `${summary}
        <section class="detail-section"><h3>Key specs</h3><p class="detail-note">${selectedNote(data)}</p>${keySpecs(data)}</section>
        <footer class="detail-foot">
            ${buildDataStamp(data)}
            <div class="detail-actions"><a class="btn btn-primary detail-full" href="${escapeHtml(full)}">Full details →</a></div>
        </footer>`;
    }
    const range = data.price_range
        ? (data.price_range.min === data.price_range.max ? formatPrice(data.price_range.min)
            : `${formatPrice(data.price_range.min)} – ${formatPrice(data.price_range.max)}`)
        : "";
    const head = `
        <header class="detail-hero">
            <figure class="detail-photo"><img src="${escapeHtml(data.image)}" alt="${escapeHtml(data.make + " " + data.model)}">
                ${data.image_attribution ? `<figcaption>Image: ${escapeHtml(data.image_attribution)}</figcaption>` : ""}</figure>
            <div>
                <h1>${escapeHtml(data.make)} ${escapeHtml(data.model)}</h1>
                ${range ? `<p class="detail-range">${range} <span>ex-showroom</span></p>` : ""}
                ${hasQuery ? `<p class="detail-note">For your search “${escapeHtml(opts.q)}”</p>` : ""}
            </div>
        </header>`;
    return `${head}
        ${summary}
        ${hasQuery ? buildReviewsSection(data.reviews) : ""}
        <div class="detail-specs" id="detail-specs" tabindex="-1">${buildSpecRegion(data, "h2", "h3")}</div>
        <section class="detail-section variants-block" id="detail-variants"><h2>Variants</h2>${buildVariantsTable(data, hasQuery)}</section>
        <footer class="detail-foot">
            ${buildDataStamp(data)}
            <div class="detail-actions">
                <button type="button" class="btn btn-quiet" data-copy-link="${escapeHtml(permalink)}">Copy link</button>
                <a class="btn btn-primary" href="${escapeHtml(data.cardekho_link)}" target="_blank" rel="noopener noreferrer">Check on-road price ${ICONS.external}<span class="sr-only">(opens CarDekho in a new tab)</span></a>
            </div>
        </footer>`;
}

// an unknown make/model: retrying cannot help, so say so and offer a search
function notFoundState(standalone) {
    const h = standalone ? "h1" : "h3";
    return `<div class="state"><${h}>We don't have that car</${h}><p>It may be discontinued or the link is wrong.</p><p><a class="btn btn-primary" href="/recommend">Search cars</a></p></div>`;
}

// fills `body` with the detail for opts {make, model, q, drop, variantId, standalone}
async function loadDetail(body, opts) {
    body.setAttribute("aria-busy", "true");
    if (!body.innerHTML.trim()) body.innerHTML = `<div class="loading" role="status"><span class="spinner" aria-hidden="true"></span>Loading details…</div>`;
    try {
        const response = await fetch(detailUrl("/api/car", opts));
        const data = await response.json();
        if (response.status === 404) {
            body.innerHTML = notFoundState(opts.standalone);
            if (opts.standalone) document.title = "Car not found | CarRec";
            body.removeAttribute("aria-busy");
            return;
        }
        if (!response.ok) throw new Error(data.error || "not found");
        body.innerHTML = renderDetail(data, opts);
        body.dataset.selected = data.selected_variant_id;
        if (opts.standalone) document.title = `${data.make} ${data.model} | CarRec`;
    } catch (error) {
        body.innerHTML = errorState("We couldn't load the details for this car.");
    }
    body.removeAttribute("aria-busy");
}

// Picking a variant on the car page: the row shows it is working at once (aria-busy and a small spinner), only the
// Specifications, Safety and Warranty sections are redrawn, focus stays on the row's button, the URL gains variant_id and one
// status line says what is shown. The latest pick wins; a failure clears the busy state and says so in the status line.
let pickSeq = 0;

function clearPickBusy(body) {
    body.querySelectorAll("tr[aria-busy]").forEach(tr => {
        tr.removeAttribute("aria-busy");
        const spin = tr.querySelector(".spinner"); if (spin) spin.remove();
    });
    const region = body.querySelector("#detail-specs"); if (region) region.removeAttribute("aria-busy");
}

async function pickVariant(body, opts, row) {
    const id = Number(row.dataset.variantId);
    if (String(id) === body.dataset.selected) return;
    const seq = ++pickSeq;
    const control = row.querySelector(".variant-pick");
    const name = control.textContent.trim();
    const status = body.querySelector("#pick-status"), region = body.querySelector("#detail-specs");
    clearPickBusy(body);
    row.setAttribute("aria-busy", "true");
    row.firstElementChild.insertAdjacentHTML("afterbegin", '<span class="spinner spinner--sm" aria-hidden="true"></span>');
    region.setAttribute("aria-busy", "true");
    status.className = "pick-status";
    status.textContent = `Loading specs for ${name}…`;
    control.focus({ preventScroll: true });
    try {
        // the search is left out of the request: the spec sections do not depend on it, and without it the server skips re-running the ranking
        const response = await fetch(detailUrl("/api/car", { make: opts.make, model: opts.model, variantId: id }));
        const data = await response.json();
        if (seq !== pickSeq) return;
        if (!response.ok) throw new Error(data.error || "not found");
        region.innerHTML = buildSpecRegion(data, "h2", "h3");
        body.dataset.selected = data.selected_variant_id;
        body.querySelectorAll("tr[data-variant-id]").forEach(tr => {
            const on = Number(tr.dataset.variantId) === data.selected_variant_id;
            tr.classList.toggle("is-selected", on);
            if (on) tr.setAttribute("aria-current", "true"); else tr.removeAttribute("aria-current");
            tr.querySelector(".variant-pick").setAttribute("aria-pressed", String(on));
        });
        opts.variantId = id;
        try { history.replaceState(history.state, "", detailUrl("/car", opts)); } catch (e) { /* the page still works without it */ }
        status.innerHTML = `Showing specs for ${escapeHtml(name)} <a href="#detail-specs" data-jump-specs>Jump to specs ↓</a>`;
    } catch (error) {
        if (seq !== pickSeq) return;
        status.className = "pick-status pick-status--error";
        status.textContent = `Couldn't load the specs for ${name}. Select it again to retry.`;
    } finally {
        if (seq === pickSeq) {
            clearPickBusy(body);
            control.focus({ preventScroll: true });
        }
    }
}

function bindVariantPicks(body, opts) {
    body.addEventListener("click", e => {
        const toggle = e.target.closest("[data-variants-toggle]");
        if (toggle) return toggleVariants(toggle);
        const jump = e.target.closest("[data-jump-specs]");
        if (jump) {
            e.preventDefault();
            const region = body.querySelector("#detail-specs");
            region.scrollIntoView({ block: "start", behavior: prefersReducedMotion() ? "auto" : "smooth" });
            return region.focus({ preventScroll: true });
        }
        const row = e.target.closest("tr[data-variant-id]");
        if (!row || e.target.closest("a")) return;
        pickVariant(body, opts, row);
    });
}

function toggleDetail(button) {
    const card = button.closest("article.car");
    const turn = card.closest("[data-turn]");
    const open = card.nextElementSibling && card.nextElementSibling.matches(".detail") ? card.nextElementSibling : null;
    const close = (panel, btn) => {
        btn.setAttribute("aria-expanded", "false");
        btn.textContent = "View details";
        panel.classList.remove("open");
        const remove = () => panel.remove();
        if (prefersReducedMotion()) remove(); else setTimeout(remove, 350);
    };
    if (open) return close(open, button);

    // one open panel per turn
    turn.querySelectorAll(".cards > .detail").forEach(p => close(p, p.previousElementSibling.querySelector("[data-detail]")));

    const id = `detail-${turn.dataset.turn}-${[...card.parentElement.children].indexOf(card)}`;
    card.insertAdjacentHTML("afterend", `<section class="detail" id="${id}" aria-label="Details: ${escapeHtml(card.getAttribute("aria-label"))}">
        <div class="detail-clip"><div class="detail-body"></div></div></section>`);
    const panel = card.nextElementSibling;
    button.setAttribute("aria-expanded", "true");
    button.setAttribute("aria-controls", id);
    button.textContent = "Hide details";
    requestAnimationFrame(() => panel.classList.add("open"));
    const opts = {
        make: card.dataset.makeSlug, model: card.dataset.modelSlug,
        q: turn.dataset.q, drop: turn.dataset.drop ? turn.dataset.drop.split(",") : []
    };
    const body = panel.querySelector(".detail-body");
    loadDetail(body, opts);
}

// /car/<make_slug>/<model_slug>?q=&drop=&variant_id=
function initCarPage() {
    const [, , make, model] = location.pathname.split("/");
    const params = new URLSearchParams(location.search);
    const opts = {
        make: decodeURIComponent(make || ""), model: decodeURIComponent(model || ""),
        q: params.get("q") || "", drop: (params.get("drop") || "").split(",").filter(Boolean),
        variantId: Number(params.get("variant_id")) || null, standalone: true
    };
    const body = document.getElementById("car-detail");
    body.addEventListener("click", e => {
        const copy = e.target.closest("[data-copy-link]");
        if (copy) copyLink(copy);
    });
    bindVariantPicks(body, opts);
    loadDetail(body, opts);
}

// 🆕 NEW CARS HANDLER
// Results are a thread of turns: every search (top box, follow-up box, chip or hint) appends a turn
// below the previous ones. v1: each query is independent; nothing carries over between turns.
// The latest search also lives in the URL (?q=<query>&drop=<key>,<key>) for sharing and back/forward.
const MAX_TURNS = 10;
let turnCount = 0;

function searchUrl(q, drop, sort) {
    const params = new URLSearchParams({ q });
    if (drop.length) params.set("drop", drop.join(","));
    if (sort && sort !== "best") params.set("sort", sort);   // only when re-opening a shared link; a new search starts at best match
    return `${location.pathname}?${params}`;
}

function searchFromUrl() {
    const params = new URLSearchParams(location.search);
    const drop = (params.get("drop") || "").split(",").filter(Boolean);
    const sort = params.get("sort") || "";
    return { q: params.get("q") || "", drop, sort: SORT_KEYS.includes(sort) ? sort : "" };   // unknown values are ignored
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
    input.style.height = "";
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
    fitSearchBox(document.getElementById("followupQuery"));
    return turn;
}

function clearThread() {
    document.getElementById("results").innerHTML = "";
    document.getElementById("followup").hidden = true;
}

// One polite sentence per search goes to the visually hidden status line; the results themselves are not a live region.
function setSearchStatus(text) {
    const el = document.getElementById("search-status");
    if (el) el.textContent = text;
}

function searchStatusText(data, ok, query) {
    if (!ok) return "The search didn't go through.";
    const n = (data.recommendations || []).length;
    if (!n) return `No cars found for ${query}.`;
    return `${n} ${n === 1 ? "car" : "cars"} found for ${query}.` + (data.relaxation ? " Nothing matched every requirement." : "");
}

// three skeleton cards and staged copy while /predict runs (3-10 s); the shimmer is off under prefers-reduced-motion (CSS).
// The visible copy is aria-hidden: the status line above announces "Searching…" once instead of every stage.
function showSearchLoading(box) {
    const count = Number(((document.getElementById("results") || {}).dataset || {}).variantCount);
    const checking = count > 0 ? `Checking ${count.toLocaleString("en-IN")} variants…` : "Checking every current variant…";
    const card = `<div class="skeleton"><div class="skeleton-body"><div class="skeleton-line skeleton-line--title"></div><div class="skeleton-line"></div><div class="skeleton-line skeleton-line--short"></div></div></div>`;
    box.innerHTML = `<div class="loading-steps" aria-hidden="true"><p class="loading-status" data-loading-step>Reading your request…</p>${card.repeat(3)}</div>`;
    const label = box.querySelector("[data-loading-step]");
    const timers = [[2000, checking], [6000, "Ranking by reviews and owner feedback…"]]
        .map(([ms, text]) => setTimeout(() => { label.textContent = text; }, ms));
    return () => timers.forEach(clearTimeout);
}

// each card name links to its own page (opens in a new tab, can be shared); the search is added once the turn is known
function linkCarTitles(box, query, drop) {
    box.querySelectorAll("article.car").forEach(card => {
        const a = card.querySelector(".car-title a");
        if (a) a.href = detailUrl("/car", { make: card.dataset.makeSlug, model: card.dataset.modelSlug, q: query, drop });
    });
}

function errorState(message) {
    return `<div class="state state--error" role="alert"><h3>Something went wrong</h3><p>${escapeHtml(message)} Please try again.</p></div>`;
}

// push: add a history entry (a new search) or replace the current one (page load, back/forward)
async function runSearch(query, drop = [], push = true, sort = "") {
    if (!query.trim()) return;

    const turn = appendTurn(query, drop);
    const url = searchUrl(query, drop, sort);
    const state = { q: query, drop, turn: turn.dataset.turn };
    if (push && url !== location.pathname + location.search) window.history.pushState(state, "", url);
    else window.history.replaceState(state, "", url);
    // the first turn sits right under the top box; later turns are scrolled into view, again once
    // their results are in (the page may be too short to bring the heading up before that)
    const scroll = Boolean(turn.previousElementSibling);

    const box = turn.querySelector("[data-turn-body]");
    setSearchStatus("Searching…");
    const stopLoading = showSearchLoading(box);
    if (scroll) scrollToTurn(turn);

    try {
        const response = await fetch("/predict", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(drop.length ? { query, drop } : { query })
        });

        const data = await response.json();
        stopLoading();
        if (!turn.isConnected) return;  // thread was cleared meanwhile
        renderResults(box, data, response.ok, location.origin + url);
        linkCarTitles(box, query, drop);
        if (sort && sort !== "best") applySort(turn, sort);
        syncCompareButtons(box);
        renderCompareTray();   // the tray's link follows the latest search
        setSearchStatus(searchStatusText(data, response.ok, query));
        if (scroll) {
            scrollToTurn(turn);
            turn.querySelector("[data-turn-heading]").focus({ preventScroll: true });  // later searches: keyboard and screen-reader users land on the new results
        }
    } catch (error) {
        stopLoading();
        if (!turn.isConnected) return;
        box.innerHTML = errorState("We couldn't reach the server.");
        setSearchStatus("We couldn't reach the server.");
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

    if (data.engine === "v3" && (data.recommendations || []).length) {
        renderV3Results(box, data, banner, link);
        return;
    }

    const recs = data.recommendations || [];
    const topScore = recs.length ? Math.max(...recs.map(r => Number(r.ranking_score) || 0)) : 0;
    box.innerHTML = banner + buildResultsToolbar(data, link)
        + `<div class="cards">${recs.map((car, i) => buildCarCard(car, i, recs, topScore, data.intent)).join("")}</div>`;
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
const SUGGESTION_MOBILE_MAX_CHARS = 28;

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
    // on a phone the chips are one swipeable row and long ones are cut off: prefer the short ideas (up to 28 characters)
    const phone = window.matchMedia("(max-width: 599px)").matches;
    const short = all.filter(s => s.query.length <= SUGGESTION_MOBILE_MAX_CHARS);
    if (phone && short.length >= count) all = short;
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

    // no auto-rotation: chips only change when the user presses "More ideas" (WCAG 2.2.2)
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
        const refine = e.target.closest("[data-refine]");
        if (refine) {
            const turn = refine.closest("[data-turn]");
            runSearch(`${turn.dataset.q} ${refine.dataset.refine}`, turn.dataset.drop ? turn.dataset.drop.split(",") : []);
        }
        const copy = e.target.closest("[data-copy-link]");
        if (copy) copyLink(copy);
        const details = e.target.closest("[data-detail]");
        if (details) toggleDetail(details);
        const reviews = e.target.closest("[data-reviews-toggle]");
        if (reviews) toggleReviews(reviews);
        const cite = e.target.closest("[data-cite]");
        if (cite) { e.preventDefault(); followCite(cite); }
        const compare = e.target.closest("[data-compare]");
        if (compare) onCompareButton(compare);
    });
    thread.addEventListener("change", e => {
        const control = e.target.closest("input[data-sort-key], select[data-sort-select]");
        if (control) applySort(control.closest("[data-turn]"), control.value);
    });
    refreshCompare();

    document.querySelectorAll("[data-suggestions]").forEach(box => {
        const input = box.closest("form").querySelector("input, textarea");
        initSuggestions(box, q => {
            input.value = q;
            runSearch(q, []);
            if (input.id === "followupQuery") { input.value = ""; input.style.height = ""; }
        }, Number(box.dataset.count) || SUGGESTION_COUNT);
    });

    document.querySelector("[data-new-search]").addEventListener("click", () => {
        clearThread();
        const input = document.getElementById("userQuery");
        input.value = "";
        input.style.height = "";
        window.history.pushState({}, "", location.pathname);
        window.scrollTo({ top: 0, behavior: prefersReducedMotion() ? "auto" : "smooth" });
        input.focus();
    });

    // back/forward: scroll to that search's turn if it is still in the thread, else start over with it
    window.addEventListener("popstate", e => {
        const { q, drop, sort } = searchFromUrl();
        const turn = e.state && e.state.turn && thread.querySelector(`[data-turn="${e.state.turn}"]`);
        document.getElementById("userQuery").value = q;
        if (turn) {
            scrollToTurn(turn);
            return;
        }
        clearThread();
        if (q) runSearch(q, drop, false, sort);
    });

    const fromUrl = searchFromUrl();
    const saved = localStorage.getItem("userQuery");  // handed over by older landing-page links
    if (saved) localStorage.removeItem("userQuery");
    const first = fromUrl.q ? fromUrl : (saved ? { q: saved, drop: [] } : null);
    if (first) {
        document.getElementById("userQuery").value = first.q;
        runSearch(first.q, first.drop, false, first.sort);
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

// --- search box: a textarea that grows to two lines, so a long query stays visible while typing; Enter still searches ---
// fits the box to its text, up to the two lines the CSS allows. A box inside a hidden form has no height to measure
// (the follow-up form starts hidden): sizing it then would set 0px and its one line would overflow, so it waits until shown.
function fitSearchBox(box) {
    if (!box || typeof box.getClientRects !== "function" || !box.getClientRects().length) return;
    box.style.height = "auto";
    box.style.height = box.scrollHeight + "px";
}

function initSearchBoxes() {
    document.querySelectorAll(".search textarea").forEach(box => {
        const fit = () => fitSearchBox(box);
        box.addEventListener("input", fit);
        box.addEventListener("keydown", e => {
            if (e.key === "Enter" && !e.shiftKey && !e.isComposing) {
                e.preventDefault();
                if (box.form) box.form.requestSubmit();
            }
        });
        fit();
    });
}

// --- theme: one control on every page. auto follows the OS; light and dark are set on <html data-theme>.
// The saved choice is applied before first paint by templates/_theme_head.html; this wires the button.
const THEME_KEY = "carrec-theme";
const THEME_MODES = ["auto", "light", "dark"];

function initTheme() {
    const btn = document.getElementById("themebtn");
    let mode = "auto";
    try {
        const saved = localStorage.getItem(THEME_KEY);
        if (THEME_MODES.includes(saved)) mode = saved;
    } catch (e) { /* storage unavailable: stay on auto */ }
    const apply = () => {
        const root = document.documentElement;
        if (mode === "auto") root.removeAttribute("data-theme");
        else root.setAttribute("data-theme", mode);
        const label = btn && btn.querySelector("[data-theme-label]");
        if (label) label.textContent = mode.charAt(0).toUpperCase() + mode.slice(1);
    };
    apply();
    if (!btn) return;
    btn.addEventListener("click", () => {
        mode = THEME_MODES[(THEME_MODES.indexOf(mode) + 1) % THEME_MODES.length];
        apply();
        try { localStorage.setItem(THEME_KEY, mode); } catch (e) { /* not saved */ }
    });
}

if (typeof document !== "undefined") {
    document.addEventListener("DOMContentLoaded", initSearchBoxes);
    document.addEventListener("DOMContentLoaded", initTheme);
}
