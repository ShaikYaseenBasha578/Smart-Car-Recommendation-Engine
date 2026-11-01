
// ============================================
// CARREC - AI BENTO RENDERING ENGINE
// ============================================

// Formatting utility
function formatPrice(num) {
    if (!num || isNaN(num)) return "N/A";
    return "₹ " + Number(Math.round(num)).toLocaleString("en-IN");
}

function normalizeScore(score, maxScore) {
    // Relative confidence mapping based on max score in result set
    // Clamp top value at 98% and bottom at 15%
    if (!score || isNaN(score)) return 0;
    const safeMax = Math.max(maxScore, 30); 
    let conf = Math.round((score / safeMax) * 98);
    return Math.max(15, Math.min(98, conf));
}

function createRing(percentage) {
    // 36px viewBox ring
    const dash = `${percentage}, 100`;
    const color = percentage > 80 ? 'text-cyan-400' : (percentage > 50 ? 'text-cyan-600' : 'text-base-600');
    return `
        <div class="relative flex items-center justify-center">
            <svg viewBox="0 0 36 36" class="w-20 h-20 md:w-24 md:h-24 transform -rotate-90">
                <path class="text-base-800 stroke-current" stroke-width="3" fill="none" d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831" />
                <path class="${color} stroke-current transition-all duration-1000 ease-out" stroke-dasharray="${dash}" stroke-width="3" stroke-linecap="round" fill="none" d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831" />
            </svg>
            <div class="absolute inset-0 flex flex-col items-center justify-center">
                <span class="font-display text-xl md:text-2xl font-bold text-white">${percentage}%</span>
            </div>
        </div>
    `;
}

function buildReasonsList(reasons) {
    if (!reasons || !reasons.length) return '<p class="text-xs text-base-500 font-mono">No specific reasons generated.</p>';
    return '<ul class="flex flex-col gap-2.5 mt-3">' + reasons.map(r => 
        `<li class="flex items-start gap-2">
            <svg class="w-4 h-4 text-cyan-500 shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path></svg>
            <span class="text-sm text-base-200 leading-snug">${r}</span>
        </li>`
    ).join('') + '</ul>';
}

function buildSpecTile(label, value, wrap = false) {
    return `
        <div class="flex-1 min-w-[110px] bg-base-950 border border-base-800 rounded-lg p-3">
            <p class="font-mono text-[10px] tracking-wider text-base-400 uppercase mb-1">${label}</p>
            <p class="font-sans font-medium text-white text-sm md:text-base ${wrap ? "break-words" : "whitespace-nowrap"}">${value}</p>
        </div>
    `;
}

// KB result extras (absent on the legacy data path, so every helper tolerates missing fields)
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

function escapeHtml(value) {
    return String(value).replace(/[&<>"']/g, ch => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[ch]));
}

function chip(text, kind) {
    const styles = {
        accent: "bg-cyan-500/10 border-cyan-500/30 text-cyan-400",
        plain: "bg-base-950 border-base-700 text-base-200",
        muted: "bg-base-950 border-base-800 text-base-300 border-dashed"
    };
    const icon = kind === "muted"
        ? '<svg aria-hidden="true" class="w-3.5 h-3.5 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><circle cx="12" cy="12" r="9" stroke-width="2"></circle><path stroke-linecap="round" stroke-width="2" d="M12 8v5m0 3h.01"></path></svg>'
        : "";
    return `<span class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md border font-mono text-[11px] leading-tight ${styles[kind]}">${icon}<span>${escapeHtml(text)}</span></span>`;
}

function buildExtraChips(car) {
    const chips = [];

    (car.matched_features || []).forEach(f => chips.push(chip(FEATURE_LABELS[f] || f, "accent")));

    if (car.safety) {
        const year = car.safety.year ? ` (${car.safety.year})` : "";
        chips.push(chip(`★ ${car.safety.stars_adult} ${car.safety.testing_body}${year}`, "accent"));
    } else if ("safety" in car) {
        chips.push(chip(NO_RATING_LABEL, "muted"));
    }

    (car.unverified || [])
        .filter(u => !(u === NO_RATING_LABEL && "safety" in car && !car.safety))  // already shown above
        .forEach(u => chips.push(chip(u, "muted")));

    if (car.matching_variant_count) {
        const n = car.matching_variant_count;
        chips.push(chip(`${n} matching variant${n === 1 ? "" : "s"}`, "plain"));
    }

    return chips.join("");
}

function buildUnsupportedBanner(data) {
    if (!data.unsupported_terms || !data.unsupported_terms.length) return "";
    const brands = data.unsupported_terms.join(", ");
    const covered = data.covered_makes || [];
    const coveredText = covered.length
        ? ` Showing the closest matches from the ${covered.length} brands we cover: ${covered.join(", ")}.`
        : "";
    return `<div class="w-full p-4 md:p-5 border border-cyan-500/30 bg-cyan-500/5 rounded-xl text-sm text-base-200 leading-relaxed">
        <span class="font-mono text-[10px] tracking-widest text-cyan-400 uppercase block mb-1">Not covered</span>
        We don't cover ${escapeHtml(brands)} yet.${escapeHtml(coveredText)}
    </div>`;
}

function buildRelaxationHints(hints) {
    if (!hints || !hints.length) return "";
    return `<ul class="mt-4 flex flex-col gap-2 text-left max-w-xl mx-auto">` + hints.map(h => {
        const examples = h.top_models && h.top_models.length ? ` (e.g. ${h.top_models.join(", ")})` : "";
        return `<li class="text-sm text-base-300 font-mono">Without ${escapeHtml(h.drop)}: ${h.would_return} option${h.would_return === 1 ? "" : "s"}${escapeHtml(examples)}</li>`;
    }).join("") + `</ul>`;
}

function buildDataStamp(data) {
    if (!data.data_as_of) return "";
    return `<p class="font-mono text-[11px] text-base-300 opacity-70">Data: ${escapeHtml(data.data_as_of.exported)} · KB ${escapeHtml(data.data_as_of.kb_phase)}</p>`;
}

// 🆕 NEW CARS HANDLER
async function sendQuery(event) {
    if (event) event.preventDefault();
    const queryInput = document.getElementById("userQuery").value;
    const resultsBox = document.getElementById("results");

    if (!queryInput.trim()) return;

    resultsBox.innerHTML = `
        <div class="w-full h-64 flex flex-col items-center justify-center border border-dashed border-base-800 rounded-2xl">
            <div class="w-8 h-8 rounded-full border-2 border-cyan-500/20 border-t-cyan-500 animate-spin mb-4"></div>
            <p class="font-mono text-cyan-500 text-sm animate-pulse">Running ML Intent Parser...</p>
        </div>
    `;

    try {
        const response = await fetch("/predict", {
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
        
        const banner = buildUnsupportedBanner(data);

        if (data.message && (!data.recommendations || !data.recommendations.length)) {
            resultsBox.innerHTML = banner + `<div class="p-6 border border-base-800 bg-base-900 rounded-xl text-center"><p class="font-display text-xl text-base-200">${data.message}</p>${buildRelaxationHints(data.relaxation_hints)}</div>` + buildDataStamp(data);
            return;
        }

        const recs = data.recommendations;
        if (banner) resultsBox.insertAdjacentHTML("beforeend", banner);
        const stamp = buildDataStamp(data);
        if (stamp) resultsBox.insertAdjacentHTML("beforeend", stamp);
        const maxScore = recs.length > 0 ? Math.max(recs[0].ranking_score, 30) : 30;

        recs.forEach((car, index) => {
            const isHero = index === 0;
            const price = formatPrice(car["Ex-Showroom_Price"]);
            const mileage = car["ARAI_Certified_Mileage"] ? Number(car["ARAI_Certified_Mileage"]).toFixed(1) + " kmpl" : "N/A";
            // KB path: specific gearbox ("Automatic (DCT)"); legacy path: Transmission only
            const trans = car.transmission_label ? escapeHtml(car.transmission_label) : (car.Transmission || "N/A");
            const fuel = car.Fuel_Type || "N/A";
            const confidence = normalizeScore(car.ranking_score, maxScore);
            const image = car.carImage || "/static/pic.avif";
            const extraChips = buildExtraChips(car);
            
            const bentoHTML = `
                <div class="w-full grid grid-cols-1 ${isHero ? 'md:grid-cols-3' : 'md:grid-cols-4'} gap-4 p-4 md:p-5 bg-base-900 border ${isHero ? 'border-cyan-500/30 shadow-[0_0_30px_rgba(6,182,212,0.05)]' : 'border-base-800'} rounded-[24px]">
                    
                    <!-- Hero Image -->
                    <div class="${isHero ? 'col-span-1 md:col-span-2 row-span-2' : 'col-span-1 md:col-span-1'} relative rounded-[16px] overflow-hidden border border-base-800 min-h-[220px] md:min-h-[100%] group">
                        <img src="${image}" class="absolute inset-0 w-full h-full object-cover transition-transform duration-1000 group-hover:scale-105">
                        <div class="absolute inset-0 bg-gradient-to-t from-base-950 via-base-950/20 to-transparent"></div>
                        <div class="absolute bottom-0 left-0 p-5 md:p-6 w-full">
                            ${isHero ? '<div class="mb-3"><span class="px-2 py-1 rounded bg-cyan-500 text-base-950 font-bold font-mono text-[10px] tracking-widest uppercase">Top Match</span></div>' : ''}
                            <h2 class="font-display ${isHero ? 'text-3xl md:text-4xl' : 'text-2xl'} font-bold text-white leading-tight mb-1">${car.Make} ${car.Model}</h2>
                            <p class="text-base-300 font-mono text-sm">${car.Variant || ''}</p>
                            ${car.imageAttribution ? `<p class="mt-2 text-base-400 font-mono text-[10px]">Image: ${car.imageAttribution}</p>` : ''}
                        </div>
                    </div>

                    <!-- Confidence -->
                    <div class="col-span-1 bg-base-950 border border-base-800 rounded-[16px] p-5 flex flex-col items-center justify-center">
                        ${createRing(confidence)}
                        <p class="mt-3 font-mono text-[10px] tracking-widest text-base-400 uppercase">Confidence</p>
                    </div>

                    <!-- Reasons -->
                    <div class="${isHero ? 'col-span-1 row-span-2' : 'col-span-1 md:col-span-2'} bg-base-950 border border-base-800 rounded-[16px] p-5 flex flex-col">
                        <p class="font-mono text-[10px] tracking-widest text-base-400 uppercase">Ranking Logic</p>
                        <div class="mt-1 flex-1 overflow-y-auto">
                            ${buildReasonsList(car.match_reasons)}
                        </div>
                    </div>

                    <!-- Specs -->
                    <div class="${isHero ? 'md:col-span-2' : 'md:col-span-4'} flex flex-wrap gap-3 mt-1 md:mt-0">
                        ${buildSpecTile("PRICE", price)}
                        ${buildSpecTile("MILEAGE", mileage)}
                        ${buildSpecTile("FUEL", fuel)}
                        ${buildSpecTile("TRANS", trans, true)}
                    </div>
                    
                    <!-- Actions -->
                    <div class="${isHero ? 'md:col-span-1' : 'md:col-span-4'} flex flex-col justify-end gap-3 mt-1 md:mt-0">
                         <a href="${car.carDekhoLink || '#'}" target="_blank" class="w-full text-center py-3 bg-base-800 hover:bg-base-700 text-white font-mono text-sm rounded-[10px] transition-colors border border-base-700">CarDekho</a>
                    </div>

                    ${extraChips ? `
                    <!-- KB details -->
                    <div class="${isHero ? 'md:col-span-3' : 'md:col-span-4'} flex flex-wrap gap-2">
                        ${extraChips}
                    </div>` : ''}
                </div>
            `;
            
            const wrapper = document.createElement("div");
            wrapper.innerHTML = bentoHTML;
            resultsBox.appendChild(wrapper.firstElementChild);
        });

    } catch (error) {
        resultsBox.innerHTML = `<div class="p-4 border border-danger-900 bg-danger-900/10 text-danger-400 rounded-xl font-mono text-sm">Frontend Error: ${error.message}</div>`;
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
