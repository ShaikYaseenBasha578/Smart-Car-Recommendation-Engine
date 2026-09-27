# API & Open Data Investigation

This document evaluates potential APIs and open data sources for the CarRec Knowledge Base. The focus is on realistic, legally accessible, and technically viable endpoints.

## 1. VAHAN / Parivahan (Government of India)
* **Provider:** Ministry of Road Transport and Highways (MoRTH)
* **Data Provided:** Registration status, ownership details, RC validity, vehicle class, basic make/model, fuel type, engine/chassis numbers.
* **Coverage:** Pan-India.
* **Access/Authentication:** The official API is heavily restricted and requires government authorization and commercial agreements (or accessing via expensive wrappers like AuthBridge/HyperVerge).
* **Variant Granularity:** **Poor**. It rarely records the specific trim/marketing variant accurately.
* **Usefulness for CarRec:** **Low** for building the core specification database. It lacks feature lists, dimensions, and pricing.
* **Conclusion:** Do not attempt to use VAHAN for specification extraction.

## 2. JATO Dynamics / CarWale APIs (Commercial)
* **Provider:** Commercial Automotive Data Providers
* **Data Provided:** Extremely granular, historical, and current specifications, pricing, and variant equipment lists.
* **Access/Authentication:** Enterprise B2B licensing (very high cost).
* **Usefulness for CarRec:** **High (If budgeted)**. This is the industry standard for automotive marketplaces.
* **Conclusion:** Out of scope for a bootstrapped pipeline, but the ultimate upgrade path if commercial funding is secured.

## 3. Hidden Aggregator JSON Endpoints (e.g., 91Wheels / V3Cars)
* **Provider:** Unofficial/Internal frontend APIs driving Next.js/React hydration.
* **Data Provided:** Variant-specific dimensions, features, and pricing.
* **Access/Authentication:** Unauthenticated `GET` requests to static JSON files or intercepting `<script id="__NEXT_DATA__">` / `<meta name="variant-data">`.
* **Usefulness for CarRec:** **Very High**. This is currently our primary source of structured data.
* **Limitations:** The schema can break without warning if they update their frontend framework. Requires ongoing maintenance.
* **Conclusion:** Recommended approach for the V1 Knowledge Base.

## 4. Bureau of Energy Efficiency (BEE) / ARAI
* **Provider:** Government Homologation bodies
* **Data Provided:** Official fuel efficiency (ARAI mileage) and EV range (MIDC).
* **Access/Authentication:** PDFs or searchable public portals (often poorly maintained).
* **Usefulness for CarRec:** **Moderate**. Good for cross-checking OEM mileage claims, but rarely provides easily automated APIs.
* **Conclusion:** Stick to OEMs and structured aggregators for ARAI claims.
