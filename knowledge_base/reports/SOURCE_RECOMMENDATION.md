# Final Source Recommendations & Executive Decision

This document synthesizes the findings of the source audit and provides a concrete architectural recommendation for building the next-generation CarRec Database Agent.

## Core V1 Sources (Build Adapters Immediately)

1. **91Wheels (Hidden JSON)**
   * *Role:* Core Specifications, Pricing, Variant Ladders, Feature Extraction.
   * *Why:* Intercepting the `v_specs` JSON via `<meta name="variant-data">` provides the highest density of structured data with the lowest parsing risk. It avoids messy HTML DOM scraping and handles almost all 812 variants perfectly (as proven in V4/V5).

2. **V3Cars (HTML Tables)**
   * *Role:* Standard & Battery Warranty Extraction.
   * *Why:* Their `<tr><td>` tables are historically stable and logically separate EV batteries from vehicle warranties. Extremely low maintenance cost.

3. **Global NCAP & Bharat NCAP (Official Fact Sheets)**
   * *Role:* Safety Ratings.
   * *Why:* As proven in V6, blind aggregator scraping leads to generation/powertrain contamination. We *must* strictly map to official PDFs, manually annotating the ~30 applicable cars to ensure 100% safety data integrity.

4. **Team-BHP (vBulletin Forums)**
   * *Role:* Owner Experiential Evidence, Reliability, Real-World Mileage.
   * *Why:* The highest authority for Indian automotive ownership. It is the only source with strict enough moderation to filter out low-quality noise. We will scrape thread text and process it using Aspect-Based Sentiment Analysis (ABSA).

## V2 Sources (Add After Core Pipeline Stabilizes)

1. **Autocar India (Editorial)**
   * *Role:* Professional Driving Dynamics, Tested 0-100 times, Ride/Handling.
   * *Why:* Supplements Team-BHP with standardized professional testing. Required to answer queries like "Which SUV has the best high-speed stability?"

2. **OEM Official Sites (PDF Brochures Only)**
   * *Role:* Fallback Validation.
   * *Why:* Live-scraping OEM websites is a maintenance nightmare due to diverse UI frameworks. Instead, build a pipeline to download OEM PDF brochures and use LLM extraction for ground-truth validation when 91Wheels data is disputed.

## Optional / Tertiary Sources

* **CarWale:** Only use if 91Wheels lacks a specific discontinued model. Do not use as a primary source due to heavy anti-bot protections.

## Rejected Sources

* **CarDekho:** Excellent data, but heavily protected by Cloudflare. High maintenance burden for data that is mostly redundant with 91Wheels.
* **VAHAN / Parivahan:** Useful for RC checks, but lacks variant-level marketing features and pricing. Impossible to reliably access without commercial API wrappers.
* **Random Automotive Blogs / YouTube Transcripts:** Too noisy, unstandardized, and heavily biased by sponsorships. Out of scope for production knowledge.

---

# Final Executive Decision

If we start building the CarRec Database Agent tomorrow, the architecture must center on a **Hybrid Automated + NLP Processing Pipeline**.

**Do not attempt to scrape OEMs directly via the DOM.** The maintenance cost will bankrupt the engineering bandwidth.

Instead, build adapters in this exact order:

1.  **The Structured Baseline (91Wheels JSON + V3Cars Tables):** This provides 90% of the objective facts (Dimensions, Engine, Features, Warranty, Pricing) for 5% of the effort. 
2.  **The Strict Safety Override:** Implement a manual dictionary mapping for BNCAP/GNCAP official PDFs. Never automate safety rating discovery.
3.  **The Experiential NLP Engine (Team-BHP):** Build a scraper for Team-BHP "Official Reviews" and "Long-Term Ownership" threads. Feed this text corpus into an ABSA model (trained on academic concepts from `MuSe-CarASTE`) to extract structured pros/cons (e.g., `(gearbox, jerky, NEGATIVE)`).

This architecture yields the **maximum useful knowledge per unit of effort**, ensuring the Database Agent can answer both factual ("Does it have ventilated seats?") and experiential ("Is the DCT reliable in traffic?") queries accurately.
