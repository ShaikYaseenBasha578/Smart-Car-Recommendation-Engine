"""Every tunable constant of the v3 engine, in one place."""

# evidence classes and how they combine into the overall score (plan section 5, decision R7)
CLASS_WEIGHTS = {"spec": 0.60, "expert": 0.25, "owner": 0.15}
# overall = raw x (1 - COVERAGE_PENALTY x share of weight that is unknown)
COVERAGE_PENALTY = 0.15
# thin evidence counts for less: a car's expert / owner class weight is multiplied by a scale in [0, 1] and the freed
# weight returns to the spec class (a class with no evidence for the car is redistributed as before).
#   expert scale = (aspects covered / aspects relevant to the query) x n_sources / (n_sources + EXPERT_SOURCE_K)
#   owner  scale = count / (count + OWNER_SAMPLE_K), count = posts sampled (rating_count if that is what the file has);
#                  OWNER_NO_COUNT_SCALE when no count is available
EXPERT_SOURCE_K = 1.0
OWNER_SAMPLE_K = 50
OWNER_NO_COUNT_SCALE = 0.5
# a model with no expert aspect rows but an overall score uses the overall for every expert criterion, and its expert
# class weight is multiplied by this (on top of the source-count factor)
OVERALL_FALLBACK_SCALE = 0.3
# an owner rating is pulled toward the segment mean: w x value + (1 - w) x segment mean, w = count / (count +
# OWNER_SAMPLE_K) (the same constant as the class scale above)

# a blank field inside a criterion is valued at a conservative prior, never left out of the criterion's mean
# (criterion value = sum of weight x (known value or prior) / total weight). The prior is never shown as a fact; the
# unknown share still feeds the coverage factor.
#   "segment": percentile / ordinal fields: (segment median of the known values) - BLANK_PRIOR_MARGIN, clipped to
#              [0, 1]; yes/no features: (segment share of True among the known cells) x BLANK_PRIOR_BOOL_FACTOR
#   "flat":    BLANK_PRIOR_FLAT for every blank field
BLANK_PRIOR_MODE = "segment"
BLANK_PRIOR_MARGIN = 0.15
BLANK_PRIOR_BOOL_FACTOR = 0.7
BLANK_PRIOR_FLAT = 0.35

# weight of one required item (feature / minimum) relative to the whole criterion pool (= 1.0).
# a known-missing required item (only seen when relaxed) counts MISSING_MULTIPLIER times as unknown.
REQUIRED_ITEM_WEIGHT = 0.10
MISSING_MULTIPLIER = 2.0

# unknown crash rating: the safety criterion uses a prior of (segment median of known ratings - this many stars),
# never below the floor; the field still counts as unknown for coverage and is never shown as a rating
CRASH_PRIOR_STARS_BELOW_MEDIAN = 1.0
CRASH_PRIOR_FLOOR_STARS = 3.0

# price criterion (value = 1 - price percentile inside the car's segment; lower price is better), weight as a share of
# the spec class. No budget in the query: PRICE_DEFAULT_WEIGHT. Cheap / value wording ("cheapest", "paisa vasool"):
# PRICE_CHEAP_WEIGHT. A stated budget without cheap wording: 0 (value_for_budget already scores price vs the budget).
# Corrected 2026-11-15 (docs/V3_REVIEW_2026-11-14.md): a model is scored from its best-scoring variant, price included.
PRICE_DEFAULT_WEIGHT = 0.08
PRICE_CHEAP_WEIGHT = 0.65

# criteria.py
MIN_SEGMENT_MODELS = 8        # a segment with fewer models than this (with a known value) -> compare against the whole catalogue
MIN_FEATURE_KNOWN_SHARE = 0.5  # features-per-rupee needs at least this share of feature cells known
BUDGET_FULL_FIT_FROM = 0.70    # price/max >= this uses the budget fully (fit 1.0)
BUDGET_FIT_FLOOR = 0.50        # fit of a car priced at ~0 of the budget (not rewarded for being cheap)
BUDGET_OVER_SLOPE = 2.0        # fit lost per 100% over budget (only relaxed results are over budget)

# evidence.py
OWNER_MIN_POSTS = 30           # posts_sampled below this -> owner theme ignored
OWNER_SATURATION_SHARE = 0.25  # share of posts mentioning a theme at which its signal is full strength

# diversify.py
MAX_MODELS = 8
MMR_LAMBDA = 0.75
SIM_WEIGHTS = {"make": 0.4, "body": 0.3, "price": 0.3}
PRICE_DISTANCE_CAP_LOG = 0.6931471805599453  # ln 2: prices a factor of 2 apart are maximally distant
USE_TWINS = True

# relax.py
BUDGET_STEPS = (0.05, 0.10, 0.20)
MIN_MODELS_FOR_RELAXATION = 3  # prefer a relaxation that returns at least this many models
RELAX_COST_TIE = 0.5           # costs closer than this are a tie (then prefer >= MIN_MODELS_FOR_RELAXATION models)
FAR_CONSTRAINTS = 3            # cumulative fallback relaxing more constraints than this is flagged far
MAX_NEAREST_VARIANTS = 400

# api.py
ASSUMED_BOOST = 0.03           # added to the overall score (0-1) of a car matching an ML-assumed body/fuel; never filters

# explain.py
MAX_REASONS = 4
# percentile-based spec scores centre near 0.5-0.65, so the bars sit above that
MATCH_LEVELS = [(0.75, "Strong match"), (0.65, "Good match"), (0.55, "Fair match")]
MATCH_FLOOR_LABEL = "Partial match"
