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
const NO_RATING_LABEL = "No Bharat NCAP rating on record";
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
// facts: electric -> "Range: 465 km"; CNG -> "Mileage: 26.4 km/kg" (kmpl if km/kg is missing);
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
                ${index === 0 ? '<span class="rank">Top pick</span>' : ""}
                <img src="${escapeHtml(image)}" alt="${escapeHtml(name)}" loading="${index < 3 ? "eager" : "lazy"}" decoding="async">
                ${caption ? `<figcaption>${escapeHtml(caption)}</figcaption>` : ""}
            </figure>
            <div class="car-body">
                <div class="car-head">
                    <div>
                        <h3 class="car-title">${escapeHtml(name)}</h3>
                        ${car.Variant ? `<p class="car-variant">${escapeHtml(car.Variant)}</p>` : ""}
                    </div>
                    <p class="car-price"><strong>${formatPrice(car["Ex-Showroom_Price"])}</strong><span>ex-showroom</span></p>
                </div>
                ${buildFacts(car)}
                <div class="car-fit">
                    <span class="match match--${match.key}">${match.label}</span>
                    ${reasons.length ? `<ul class="reasons" aria-label="Why it stands out">${reasons.map(r => `<li>${ICONS.check}<span>${escapeHtml(r)}</span></li>`).join("")}</ul>` : ""}
                </div>
                <div class="car-foot">
                    ${tags ? `<ul class="tags" aria-label="Features and safety">${tags}</ul>` : ""}
                    <div class="car-actions">
                        <button type="button" class="btn btn-quiet" data-detail aria-expanded="false">View details</button>
                        ${link ? `<a class="btn btn-primary" href="${escapeHtml(link)}" target="_blank" rel="noopener noreferrer">Check on-road price ${ICONS.external}<span class="sr-only">(opens CarDekho in a new tab)</span></a>` : ""}
                    </div>
                </div>
            </div>
        </article>`;
}

// --- car detail (inline panel under a card, and the /car/<make>/<model> permalink page) ---
// One component: renderDetail() draws GET /api/car/... for both. Sections, in order: Summary,
// Variants, Specifications, Safety, Warranty, then the data stamp and actions.
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
    const shown = items.filter(i => i.status !== "not_applicable");
    if (!shown.length) return "";
    return `<dl class="spec-list">` + shown.map(i => `<div><dt>${escapeHtml(i.label)}</dt><dd>${
        i.status === "ok" ? escapeHtml(i.value_display) : '<span class="not-verified">Not verified</span>'
    }</dd></div>`).join("") + `</dl>`;
}

function variantMileage(v) {
    const m = v.mileage_display;
    return m.value || (m.unit === "km/kg" ? "CNG mileage not listed" : "Not listed");
}

function buildVariantsTable(data, hasQuery) {
    const rows = [...data.variants].sort((a, b) =>
        (b.matches_query - a.matches_query) || ((a.price || 0) - (b.price || 0)) || (a.variant_id - b.variant_id));
    const matching = rows.filter(v => v.matches_query).length;
    const note = hasQuery
        ? (matching ? `${matching} of ${rows.length} variants match your search.` : `None of the ${rows.length} variants match your search; all are listed below.`)
        : `${rows.length} variants.`;
    return `<p class="detail-note">${note} Select a variant to see its specifications.</p>
        <div class="table-wrap" tabindex="0" role="region" aria-label="Variants">
        <table class="variants">
            <thead><tr><th scope="col">Variant</th><th scope="col">Price</th><th scope="col">Gearbox</th><th scope="col">Fuel</th><th scope="col">Mileage</th></tr></thead>
            <tbody>${rows.map(v => {
                const selected = v.variant_id === data.selected_variant_id;
                return `<tr data-variant-id="${v.variant_id}" class="${v.matches_query ? "is-match" : ""}${selected ? " is-selected" : ""}"${selected ? ' aria-current="true"' : ""}>
                    <td><button type="button" class="variant-pick" data-variant-id="${v.variant_id}" aria-pressed="${selected}">${escapeHtml(v.variant)}</button>
                        ${v.matches_query ? '<span class="match-badge">Matches your search</span>' : ""}</td>
                    <td>${formatPrice(v.price)}</td>
                    <td>${escapeHtml(v.transmission_label)}</td>
                    <td>${escapeHtml(v.fuel_label)}</td>
                    <td>${escapeHtml(variantMileage(v))}</td>
                </tr>`;
            }).join("")}</tbody>
        </table></div>`;
}

function buildSafetySection(data) {
    const group = data.specs.find(g => g.group === "Safety");
    const s = data.safety;
    const rating = s
        ? `<p class="ncap">${ICONS.star}<span><strong>${s.stars_adult}-star</strong> adult${s.stars_child != null ? ` · <strong>${s.stars_child}-star</strong> child` : ""} · ${escapeHtml(s.testing_body)}${s.year ? ` (${s.year})` : ""}</span></p>`
        : `<p class="ncap ncap--none">${ICONS.info}<span>${NO_RATING_LABEL}</span></p>`;
    return rating + (group ? specList(group.items) : "");
}

function renderDetail(data, opts) {
    const selected = data.variants.find(v => v.variant_id === data.selected_variant_id);
    const hasQuery = Boolean(opts.q);
    const permalink = location.origin + detailUrl("/car", { ...opts, variantId: data.selected_variant_id });
    const range = data.price_range
        ? (data.price_range.min === data.price_range.max ? formatPrice(data.price_range.min)
            : `${formatPrice(data.price_range.min)} – ${formatPrice(data.price_range.max)}`)
        : "";
    const head = opts.standalone ? `
        <header class="detail-hero">
            <figure class="detail-photo"><img src="${escapeHtml(data.image)}" alt="${escapeHtml(data.make + " " + data.model)}">
                ${data.image_attribution ? `<figcaption>Image: ${escapeHtml(data.image_attribution)}</figcaption>` : ""}</figure>
            <div>
                <h1>${escapeHtml(data.make)} ${escapeHtml(data.model)}</h1>
                ${range ? `<p class="detail-range">${range} <span>ex-showroom</span></p>` : ""}
                ${hasQuery ? `<p class="detail-note">For your search “${escapeHtml(opts.q)}”</p>` : ""}
            </div>
        </header>` : "";
    const specGroups = data.specs.filter(g => DETAIL_SPEC_GROUPS.includes(g.group))
        .map(g => { const list = specList(g.items); return list ? `<div class="spec-group"><h4>${escapeHtml(g.group)}</h4>${list}</div>` : ""; })
        .join("");
    const warranty = data.specs.find(g => g.group === "Warranty");
    return `${head}
        <section class="detail-section"><h3>Summary</h3><p class="detail-summary">${escapeHtml(data.summary)}</p></section>
        <section class="detail-section"><h3>Variants</h3>${buildVariantsTable(data, hasQuery)}</section>
        <section class="detail-section"><h3>Specifications</h3>
            <p class="detail-note">For <strong>${escapeHtml(selected ? selected.variant : "")}</strong>${selected ? ` · ${formatPrice(selected.price)}` : ""}</p>
            <div class="spec-groups">${specGroups}</div></section>
        <section class="detail-section"><h3>Safety</h3>${buildSafetySection(data)}</section>
        <section class="detail-section"><h3>Warranty</h3>${warranty ? specList(warranty.items) : ""}
            <p class="detail-note">Warranty terms aren't in our verified data yet; check with the dealer.</p></section>
        <footer class="detail-foot">
            ${buildDataStamp(data)}
            <div class="detail-actions">
                <button type="button" class="btn btn-quiet" data-copy-link="${escapeHtml(permalink)}">Copy link</button>
                <a class="btn btn-primary" href="${escapeHtml(data.cardekho_link)}" target="_blank" rel="noopener noreferrer">Check on-road price ${ICONS.external}<span class="sr-only">(opens CarDekho in a new tab)</span></a>
            </div>
        </footer>`;
}

// fills `body` with the detail for opts {make, model, q, drop, variantId, standalone}
async function loadDetail(body, opts) {
    body.setAttribute("aria-busy", "true");
    if (!body.innerHTML.trim()) body.innerHTML = `<div class="loading" role="status"><span class="spinner" aria-hidden="true"></span>Loading details…</div>`;
    try {
        const response = await fetch(detailUrl("/api/car", opts));
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || "not found");
        body.innerHTML = renderDetail(data, opts);
        body.dataset.selected = data.selected_variant_id;
        if (opts.standalone) document.title = `${data.make} ${data.model} | CarRec`;
    } catch (error) {
        body.innerHTML = errorState("We couldn't load the details for this car.");
    }
    body.removeAttribute("aria-busy");
}

// variant rows: clicking a row (or its button) reloads the detail for that variant
function bindVariantPicks(body, opts) {
    body.addEventListener("click", e => {
        const row = e.target.closest("tr[data-variant-id]");
        if (!row || e.target.closest("a")) return;
        const variantId = Number(row.dataset.variantId);
        if (String(variantId) === body.dataset.selected) return;
        opts.variantId = variantId;
        loadDetail(body, opts);
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
    bindVariantPicks(body, opts);
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
        const details = e.target.closest("[data-detail]");
        if (details) toggleDetail(details);
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
