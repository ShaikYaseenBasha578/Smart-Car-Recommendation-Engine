# Review page inspection (plan step 1), 2026-11-14

Method: `Fetcher.get_polite` (kbpipe/fetch.py): robots.txt read first and obeyed, cached, 4 s between requests per site, one attempt, no retry on 403/429. 12 network requests in all (6 pages, 1 extra CarWale page for pagination, 2 more for the reviews URL variants, 2 robots files). Pages saved as local-only test fixtures in `kbpipe/tests/fixtures/reviews/` (git-ignored; tests skip when absent). No Team-BHP request was made.

## Autocar India  `/cars/{make}/{model}/expert-reviews`  (Creta, Nexon, Swift)
Server-rendered; the scores are in the fetched HTML. No headless browser needed.
- **Overall score**: JSON-LD `Review.reviewRating` (`ratingValue` "9.0", `bestRating` "10", `worstRating` "1") inside the `ItemList` block, and in markup after the label `Autocar score`. Both agree on the three pages.
- **Review date**: JSON-LD `Review.datePublished` (Creta 2025-10-09, Nexon 2025-07-04, Swift 2025-10-16). The markup also shows `Last Updated on: 13 Nov 2026` (Swift 09 Nov 2026): that is a page-touched date, not the review date. The parser stores `datePublished` as `published_on` and keeps the last-updated date in the row's raw note.
- **Seven aspect scores, out of 10, exact labels in markup (title case)**: `Exterior Design And Engineering`, `Interior Space And Comfort`, `Performance And Refinement`, `Mileage / Range And Efficiency`, `Ride Comfort And Handling`, `Features And Safety`, `Value For Money`. Values appear as "8" or "8.0" (Nexon). Integers 1..10 in practice.
- **Tested variant**: not named anywhere on the three pages. `variant_scope` stays NULL.
- **Text**: pros/cons in `<div id="pros-and-cons">` under headings `We like` / `We don't like` (short phrases). Creta and Nexon also carry one prose paragraph block per aspect (500 to 1,000 characters, in the HTML although visually clamped). Swift carries scores and pros/cons only (no aspect prose). There is no section called verdict.
- **Page identity**: `<h1>` "Hyundai Creta Expert Review", canonical URL, JSON-LD `itemReviewed.name` ("Hyundai Creta"), `<title>`.
- Page size about 1.2 MB each. Related-article lists (other URLs) are on the page and are ignored.

## CarWale  `/{make}-cars/{model}/user-reviews/`  (Creta, Nexon, Swift)
Server-rendered JSON in `<script type="application/json" id="initial-state">` (the same tag kbpipe's carwale adapter already reads, but the key here is `userReviewListing`). No script-loaded endpoint is needed.
- **Overall + count**: `aggregateRating.overallRating` (Creta 4.6, Nexon 4.59, Swift 4.53), `totalRatings` (736 / 1068 / 635) and `reviewCount.total` (written reviews: 203 / 310 / 177). Same overall and review count also in JSON-LD (`aggregateRating.ratingValue`, `ratingCount` = written-review count, not rating count).
- **Aspect ratings, out of 5**: `aggregateRating.reviewParameters[]` (`MinHeading`, `Answer`). Seven rated aspects, not five: `Design and Styling`, `Comfort and Space`, `Performance`, `Fuel Economy`, `Value for Money`, `Features and Technology`, `After Sales Cost and Experience`. The same list holds three non-rating questions (QuestionIds 155, 157, 159: "Would you be interested...", "expected price", "like the design") that must be ignored. After Sales Cost and Experience is useful for the service-cost gap.
- **Written reviews**: 10 per page inside the initial state (`userReviewList.Reviews[]`: Title, Description, UserRating, EntryDate, VehicleInfo with version, Upvotes). Pagination is plain URLs, allowed by robots.txt: `/{make}-cars/{model}/reviews/page/N/` (announced by `rel="next"`). Page 1 of `/user-reviews/` is identical to `/reviews/`. Verified page 2 for Creta (10 more reviews, same totals). So all written reviews are reachable by plain fetches: Creta 203 (21 pages), Nexon 310 (31 pages), Swift 177 (18 pages), at 4 s per page. `userExpectations` holds another 20 older reviews of 30..49 (not used).
- Review dates are relative ("5 months ago") on the list, an absolute timestamp sits in `LastUpdatedOn`.
- **Page identity**: `modelDetails.modelName/makeName`, `aggregateRating.vehicleInfo.ModelId`, JSON-LD product name, `<title>` "Hyundai Creta Reviews - CarWale".
- robots.txt: `/api/*`, `/webapi/*` etc. are disallowed, review pages are not. No crawl delay.

## Decisions taken in the build
- Aspect mapping tables in config cover the 7 + 7 labels above (the plan's draft had 5 CarWale aspects; the two extra are stored too, mapping to features_tech and a new owner after-sales aspect).
- CarWale text sample for themes is capped (config `reviews.carwale.max_text_pages`, default 5 pages = 50 reviews) to keep fetches and LLM calls small; the report lists reviews sampled versus reviews available.
