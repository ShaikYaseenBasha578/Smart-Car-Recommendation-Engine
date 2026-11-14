"""Every tunable constant of the v3 engine, in one place."""

# evidence classes and how they combine into the overall score (plan section 5, decision R7)
CLASS_WEIGHTS = {"spec": 0.60, "expert": 0.25, "owner": 0.15}
# overall = raw x (1 - COVERAGE_PENALTY x share of weight that is unknown)
COVERAGE_PENALTY = 0.15
# weight of one required item (feature / minimum) relative to the whole criterion pool (= 1.0).
# a known-missing required item (only seen when relaxed) counts MISSING_MULTIPLIER times as unknown.
REQUIRED_ITEM_WEIGHT = 0.10
MISSING_MULTIPLIER = 2.0

# criteria.py
MIN_GROUP_SIZE = 5            # fewer rows in a segment -> compare against all candidates instead
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
