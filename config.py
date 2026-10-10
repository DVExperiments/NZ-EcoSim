"""Shared constants for Terrarium."""
GW, GH = 200, 125          # grid size in cells
DAY_TICKS = 720            # "ecological day": unit for lifespans, breeding, alerts (time is compressed)
CAL_DAY = 120              # ticks per calendar day (one day/night cycle)
YEAR_DAYS = 365            # calendar days per year
YEAR_TICKS = CAL_DAY * YEAR_DAYS
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
MONTH_DAYS = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
# Southern hemisphere seasons by month
MONTH_SEASON = ["Summer", "Summer", "Autumn", "Autumn", "Autumn", "Winter",
                "Winter", "Winter", "Spring", "Spring", "Spring", "Summer"]


def age_text(ticks):
    """Human-readable calendar duration for a number of ticks."""
    days = ticks / CAL_DAY
    if days < 60:
        return "%d days" % days
    if days < 730:
        return "%d months" % (days / 30.4)
    return "%.0f years" % (days / 365)
POP_CAP = 260              # per-species animal cap
TOTAL_CAP = 950            # total animal cap
HUMAN_CAP = 300            # total people
SEA_LEVEL = 0.24

# structures (World.struct)
NONE, HOUSE, FIELD, TRAP, RUIN = 0, 1, 2, 3, 4
HOUSE_COST = 6.0

SEASONS = ["Winter", "Spring", "Summer", "Autumn"]

DEFAULT_SETTINGS = {
    "time": 1.0, "sun": 1.0, "temp": 0.0, "rain": 1.0, "wind": 1.0,
    "gravity": 1.0, "evap": 1.0, "mutation": 1.0, "decay": 1.0, "migration": 0.3,
    "biosecurity": 0.3,
}

# ----------------------------------------------------------------------------
# Biological time.  The calendar is real (365-day years), but life runs faster
# than the calendar so that generations can be watched: every animal and
# person lives LIFE_SPEED biological years per calendar year.  All species use
# the SAME factor, so their lifespans, breeding rates and growth stay in true
# proportion to each other (a rat still lives ~1/35th as long as a kiwi).
# ----------------------------------------------------------------------------
LIFE_SPEED = 20
BIO_YEAR = YEAR_TICKS / LIFE_SPEED     # ticks in one biological year (~18 calendar days)


def bio_years(ticks):
    return ticks / BIO_YEAR


# Difficulty presets.  "realistic" uses real-world life-history data unchanged.
DIFFICULTIES = {
    "gentle": {
        "label": "Gentle",
        "blurb": "Slower pests and settlers, hardier native birds and fewer voyages. Cause and effect "
                 "play out slowly and clearly - good for younger students.",
        "pest_breed": 0.55, "pest_carry": 0.7, "human_growth": 0.6, "voyages": 0.5, "stowaway": 0.5,
        "naive_bonus": 0.10, "aggression": 0.7, "hunt": 0.7, "native_breed": 1.15,
    },
    "realistic": {
        "label": "Realistic",
        "blurb": "Real lifespans, litter sizes and breeding rates for every species, real human population "
                 "growth (about 1-3% a year in good times) and realistic predator success on naive birds.",
        "pest_breed": 1.0, "pest_carry": 1.0, "human_growth": 1.0, "voyages": 1.0, "stowaway": 1.0,
        "naive_bonus": 0.25, "aggression": 1.0, "hunt": 1.0, "native_breed": 1.0,
    },
    "harsh": {
        "label": "Harsh",
        "blurb": "A worst case: pests breed at the top of their natural range, more ships and stowaways, "
                 "hungrier and more warlike clans.",
        "pest_breed": 1.35, "pest_carry": 1.25, "human_growth": 1.3, "voyages": 1.6, "stowaway": 1.6,
        "naive_bonus": 0.32, "aggression": 1.3, "hunt": 1.2, "native_breed": 0.9,
    },
}
DIFFICULTY_ORDER = ["gentle", "realistic", "harsh"]


def diff(w, key):
    return DIFFICULTIES[getattr(w, "difficulty", "realistic")][key]


def bio_age_text(ticks):
    """An age in biological time (what the animal or person experiences)."""
    y = ticks / BIO_YEAR
    if y < 1 / 12:
        return "%d weeks" % max(1, y * 52)
    if y < 2:
        return "%d months" % max(1, y * 12)
    return "%d years" % y
