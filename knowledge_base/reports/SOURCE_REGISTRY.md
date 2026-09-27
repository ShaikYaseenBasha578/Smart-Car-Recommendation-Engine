# CarRec Knowledge Base — Source Registry

This registry evaluates candidate data sources for the CarRec Knowledge Base. Each source is evaluated on a consistent framework considering extraction difficulty, reliability, granularity, and legal/licensing realities.

## 1. OEM / Manufacturer Sources (e.g., Maruti Suzuki, Hyundai, Tata)
* **Category:** Manufacturer / Official
* **Role:** SPECIFICATION, PRICING, WARRANTY, VALIDATION
* **Information Available:** Ground-truth specifications, variant ladders, official ex-showroom pricing, standard/extended warranty terms, brochures.
* **Granularity:** Excellent. Explicitly variant-level.
* **Access Method:** Direct HTTP requests, hidden JSON configurator endpoints, PDF brochures.
* **Extraction Difficulty:** **Very Difficult**. Every OEM uses a different CMS (Adobe AEM, React, static HTML). Structures change frequently. Brochures are unstructured PDFs.
* **Freshness:** Immediate.
* **Coverage:** 100% of currently sold cars.
* **Historical Coverage:** Poor. Discontinued models are quickly deleted from OEM sites.
* **Reliability:** Highest possible authority.
* **Licensing/Usage:** Automated scraping of OEM sites is generally discouraged in their ToS, though extracting factual dimensions/specs is typically permitted under fair use/factual data doctrines.
* **Recommended Status:** **Optional/Fallback**. Maintain a manual process to download OEM brochure PDFs for OCR/LLM extraction, rather than building fragile live web scrapers.

## 2. 91Wheels
* **Category:** Structured Automotive Database
* **Role:** SPECIFICATION, FEATURE EXTRACTION, PRICING, DISCOVERY
* **Information Available:** Deep variant-level feature lists, engine specs, dimensions, pricing.
* **Granularity:** Excellent (Make > Model > Powertrain > Variant).
* **Access Method:** Intercepting Next.js `v_specs` JSON payload in `<meta name="variant-data">`.
* **Extraction Difficulty:** **Easy to Moderate**. The hidden JSON is highly structured and bypasses the visual DOM entirely.
* **Freshness:** High (updated frequently by editorial team).
* **Coverage:** Near 100% for Indian market (including historical/discontinued).
* **Reliability:** High, though occasional spec errors exist.
* **Recommended Status:** **Core V1 Source**. Best ROI for extraction effort vs data density.

## 3. V3Cars
* **Category:** Structured Automotive Database
* **Role:** WARRANTY, SPECIFICATION, CROSS-CHECK
* **Information Available:** Standard/Battery warranty, variant features.
* **Granularity:** Good.
* **Access Method:** BeautifulSoup (Standard `<tr><td>` HTML tables).
* **Extraction Difficulty:** **Easy**. Consistent legacy HTML table structure.
* **Reliability:** High for warranty extraction (as proven in V6), but can conflate Hybrid/EV battery strings occasionally.
* **Recommended Status:** **Core V1 Source** for Warranty.

## 4. CarWale / CarDekho
* **Category:** Structured Automotive Database
* **Role:** SPECIFICATION, MARKET/LISTINGS, HISTORICAL DATA
* **Information Available:** Deep historical DB, specs, on-road pricing, user reviews.
* **Access Method:** Selenium / BeautifulSoup (Cloudflare protected heavily on CarDekho).
* **Extraction Difficulty:** **Very Difficult**. Aggressive anti-bot measures (Akamai/Cloudflare).
* **Reliability:** High.
* **Recommended Status:** **Reject** (for V1). Too much redundancy with 91Wheels, with a much higher maintenance cost due to bot protection.

## 5. Team-BHP
* **Category:** Owner / Community
* **Role:** OWNER EXPERIENCE, VALIDATION, HISTORICAL DATA
* **Information Available:** Initial ownership reports, long-term reliability, real-world mileage, NVH impressions, recurring defects, service centre experiences.
* **Granularity:** Usually Model/Powertrain. Variant is often mentioned in text.
* **Access Method:** BeautifulSoup on vBulletin forum structure.
* **Extraction Difficulty:** **Moderate**. The DOM is ancient and stable, but extracting *meaning* requires NLP/LLMs to process free-text threads.
* **Reliability:** Highest authority for experiential knowledge and real-world reliability in India. Moderation is extremely strict.
* **Recommended Status:** **Core V1 Source**. The absolute best source for qualitative owner data.

## 6. Autocar India
* **Category:** Professional Automotive Journalism
* **Role:** PROFESSIONAL REVIEW, VALIDATION
* **Information Available:** Road tests, handling/ride quality analysis, verified 0-100 times, actual fuel efficiency runs.
* **Granularity:** Powertrain level (they usually test top-spec).
* **Access Method:** BeautifulSoup / RSS / Site maps.
* **Extraction Difficulty:** **Moderate**. Standard CMS structure, but data is locked in paragraphs.
* **Reliability:** High authority for driving dynamics.
* **Recommended Status:** **V2 Source**. Excellent for filling in "Ride Comfort" and "Handling" matrices.

## 7. Bharat NCAP & Global NCAP
* **Category:** Safety Database
* **Role:** SAFETY
* **Information Available:** Adult/Child occupant stars, body shell integrity, test year, exact tested variant.
* **Access Method:** HTTP Requests -> PDF Downloads.
* **Extraction Difficulty:** **Moderate**. Requires parsing standardized PDFs, but volume is very low (few dozen cars).
* **Reliability:** The only ground truth for crash safety.
* **Recommended Status:** **Core V1 Source**. Must be strictly mapped to prevent generation contamination.
