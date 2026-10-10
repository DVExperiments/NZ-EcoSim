"""
world.py - the simulation core of Terrarium: Aotearoa New Zealand edition.

The world is an island on a grid.  Each cell holds layers of state:

    height     terrain elevation (static) - coast, lowland, and a snowy alpine spine
    sea        ocean mask (static)
    water      standing surface water (rivers, lakes, swamps - flows downhill)
    moist      soil moisture          snow       snow cover
    nutr       soil nutrients         detritus   dead organic matter
    microbes   bacteria (0..1)        fungus     mycelium (0..1)
    pspec      plant species (-1 bare) pbio      plant biomass
    fire       burning intensity      pollen     pollination / seed dispersal by birds
    struct     human structures (houses, fields, ruins) and player traps
    owner      tribe owning a structure
    sanctuary  predator-proof fenced area drawn by the player

Animals are individual agents with heritable genes (size, speed) that grow up
from vulnerable juveniles.  People (humans.py) live in tribes.
"""
import math
import random
from collections import Counter

import numpy as np

from config import BIO_YEAR, LIFE_SPEED, diff, DIFFICULTIES
from config import (GW, GH, DAY_TICKS, CAL_DAY, YEAR_TICKS, MONTHS, MONTH_DAYS, MONTH_SEASON, YEAR_DAYS, POP_CAP, TOTAL_CAP, SEA_LEVEL, SEASONS,
                    DEFAULT_SETTINGS, NONE, HOUSE, FIELD, TRAP, RUIN)
from species_nz import (PlantSpecies, AnimalSpecies, SimpleEntry, native_plants, introduced_plants,
                        native_animals, introduced_animals, hue_color, random_name)
import humans
import alerts


# ----------------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------------
def value_noise(w, h, scale, rng):
    gw, gh = w // scale + 3, h // scale + 3
    g = rng.random((gw, gh))
    xs = np.arange(w) / scale
    ys = np.arange(h) / scale
    x0 = xs.astype(int)
    y0 = ys.astype(int)
    fx = xs - x0
    fy = ys - y0
    fx = fx * fx * (3 - 2 * fx)
    fy = fy * fy * (3 - 2 * fy)
    a = g[x0][:, y0]
    b = g[x0 + 1][:, y0]
    c = g[x0][:, y0 + 1]
    d = g[x0 + 1][:, y0 + 1]
    fx = fx[:, None]
    fy = fy[None, :]
    return (a * (1 - fx) + b * fx) * (1 - fy) + (c * (1 - fx) + d * fx) * fy


def neigh_mean(a):
    p = np.pad(a, 1, mode="edge")
    return (p[2:, 1:-1] + p[:-2, 1:-1] + p[1:-1, 2:] + p[1:-1, :-2]) * 0.25


def dilate(mask, r=1):
    m = mask.copy()
    for _ in range(r):
        p = np.pad(m, 1)
        m = m | p[2:, 1:-1] | p[:-2, 1:-1] | p[1:-1, 2:] | p[1:-1, :-2]
    return m


DEFAULT_OPTS = {"region": "north", "geo": "big", "land": 0.55, "mountains": 0.5, "forest": 0.7, "wetness": 1.0, "difficulty": "realistic"}
GEOGRAPHIES = [("big", "Big island"), ("archipelago", "Small islands"), ("mountains", "Mountainous"),
               ("lowlands", "Lowlands"), ("lakes", "Lakes & wetlands")]


def make_terrain(seed, opts):
    """Generate (height, sea) for a seed and map options."""
    rng = np.random.default_rng(seed)
    X, Y = np.meshgrid(np.arange(GW, dtype=np.float32), np.arange(GH, dtype=np.float32), indexing="ij")
    geo = opts.get("geo", "big")
    land = opts.get("land", 0.55)
    m = opts.get("mountains", 0.5)
    dx = (X - GW / 2) / (GW * 0.5)
    dy = (Y - GH / 2) / (GH * 0.5)
    coast = value_noise(GW, GH, 18, rng)
    base = (value_noise(GW, GH, 40, rng) * 0.5 + value_noise(GW, GH, 14, rng) * 0.3
            + value_noise(GW, GH, 5, rng) * 0.2)
    ridge = 1 - np.abs(2 * value_noise(GW, GH, 26, rng) - 1)
    if geo == "archipelago":
        mask = np.zeros((GW, GH), np.float32)
        for _ in range(int(rng.integers(6, 11))):
            cx, cy = rng.uniform(0.1, 0.9) * GW, rng.uniform(0.12, 0.88) * GH
            rad = rng.uniform(0.06, 0.16) * GW
            mask = np.maximum(mask, np.clip(1 - np.hypot(X - cx, (Y - cy) * 1.25) / rad, 0, 1))
        island = np.clip(mask * 1.3 + (coast - 0.5) * 0.45, 0, 1)
        spine = island ** 2
        land = land * 0.6
    else:
        r = np.sqrt(dx * dx + dy * dy)
        island = np.clip(1.3 - r * 0.95 + (coast - 0.5) * 0.6, 0, 1)
        ang = rng.random() * math.pi
        axis = dx * math.cos(ang) + dy * math.sin(ang) * 1.3 + rng.uniform(-0.2, 0.2)
        width = 0.6 if geo == "mountains" else 0.45
        spine = np.clip(1 - np.abs(axis) / width, 0, 1) ** 1.5
    if geo == "mountains":
        m = 0.65 + 0.35 * m
        ridge = np.maximum(ridge, 1 - np.abs(2 * value_noise(GW, GH, 12, rng) - 1) * 1.1)
    elif geo == "lowlands":
        m = m * 0.35
        base = base * 0.5
    h = island * (0.30 + 0.32 * base + 1.1 * m * ridge ** 2 * spine)
    if geo == "lakes":
        for _ in range(int(rng.integers(4, 8))):
            cx, cy = rng.uniform(0.25, 0.75) * GW, rng.uniform(0.25, 0.75) * GH
            rad = rng.uniform(0.04, 0.09) * GW
            h -= np.clip(1 - np.hypot(X - cx, Y - cy) / rad, 0, 1) ** 0.7 * 0.3 * island
        h = np.maximum(h, 0)
    # set the sea level so that the requested share of the map is land
    q = float(np.quantile(h, 1 - land))
    top = max(q + 0.05, 1.0)
    out = np.where(h < q, h / max(q, 1e-6) * SEA_LEVEL,
                   SEA_LEVEL + (h - q) / (top - q) * (1 - SEA_LEVEL))
    # keep a ring of open ocean around the whole map so every coast is surrounded by sea
    d = np.minimum(np.minimum(X, GW - 1 - X), np.minimum(Y, GH - 1 - Y))
    cap = 0.01 + (1 - 0.01) * np.clip((d - 1) / 16, 0, 1) ** 1.3      # deepening ocean towards the edge
    out = np.minimum(out, cap)
    out = np.clip(out, 0, 1).astype(np.float32)
    low = out < SEA_LEVEL
    edge = np.zeros((GW, GH), bool)
    edge[0, :] = edge[-1, :] = True
    edge[:, 0] = edge[:, -1] = True
    sea = low & edge
    for _ in range(500):
        ns = low & dilate(sea)
        if (ns == sea).all():
            break
        sea = ns
    return out, sea


def terrain_preview(h, sea, region="north"):
    """Small RGB preview (GW, GH, 3) of a terrain."""
    t = np.clip((h - SEA_LEVEL) / (1 - SEA_LEVEL), 0, 1)[..., None]
    lowc = np.array([70, 130, 70], np.float32)
    midc = np.array([40, 95, 55], np.float32)
    highc = np.array([150, 140, 120], np.float32)
    col = np.where(t < 0.45, lowc * (1 - t / 0.45) + midc * (t / 0.45),
                   midc * (1 - (t - 0.45) / 0.55) + highc * ((t - 0.45) / 0.55))
    snowline = 0.62 if region == "south" else 0.78
    col = np.where((t > snowline), np.array([240, 242, 248], np.float32), col)
    lake = (h < SEA_LEVEL) & ~sea
    col = np.where(lake[..., None], np.array([60, 120, 180], np.float32), col)
    depth = np.clip((SEA_LEVEL - h) / SEA_LEVEL, 0, 1)[..., None]
    seac = np.array([62, 140, 176], np.float32) * (1 - depth ** 0.6) + np.array([18, 46, 98], np.float32) * depth ** 0.6
    col = np.where(sea[..., None], seac, col)
    return np.clip(col, 0, 255).astype(np.uint8)


KILL_FOOD = 2.5

# ----------------------------------------------------------------------------
# agents
# ----------------------------------------------------------------------------
class Animal:
    __slots__ = ("sp", "x", "y", "hx", "hy", "energy", "age", "size", "speed", "maxage",
                 "gen", "sick", "tx", "ty", "prey", "think", "flee", "alive", "awake", "cool", "esize", "note")

    def __init__(self, sp, x, y, size=None, speed=None, gen=0, energy_frac=0.6, adult=True):
        self.sp = sp
        self.x, self.y = x, y
        a = random.random() * math.tau
        self.hx, self.hy = math.cos(a), math.sin(a)
        self.size = size if size is not None else sp.size * random.uniform(0.92, 1.08)
        self.speed = speed if speed is not None else sp.speed * random.uniform(0.92, 1.08)
        self.energy = 60 * self.size * energy_frac
        self.maxage = sp.max_age * random.uniform(0.8, 1.2)
        mf = sp.mature_frac
        self.age = self.maxage * random.uniform(mf, max(mf + 0.05, 0.5)) if adult else 0
        self.gen = gen
        self.sick = False
        self.tx = self.ty = None
        self.prey = None
        self.think = random.randint(0, 6)
        self.flee = 0
        self.alive = True
        self.awake = True
        # adults arrive part-way through their breeding cycle (so they don't all breed at once)
        self.cool = random.uniform(0, sp.breed_gap) if adult else 0
        self.esize = self.size if adult else self.size * 0.35
        self.note = "just arrived" if adult else "newborn"

    @property
    def juvenile(self):
        """Not yet old enough to breed."""
        return self.age < self.maxage * self.sp.mature_frac

    @property
    def young(self):
        """An egg, chick or baby: easy prey for nest raiders."""
        return self.age < self.sp.young_ticks


class Cloud:
    __slots__ = ("x", "y", "r", "water", "raining", "age")

    def __init__(self, x, y, r, water):
        self.x, self.y, self.r, self.water = x, y, r, water
        self.raining = False
        self.age = 0


# ----------------------------------------------------------------------------
# world
# ----------------------------------------------------------------------------
class World:
    VERSION = 5

    def __init__(self, seed=None, opts=None):
        self.version = self.VERSION
        self.seed = seed if seed is not None else random.randrange(1 << 30)
        self.opts = dict(DEFAULT_OPTS)
        if opts:
            self.opts.update(opts)
        self.region = self.opts["region"]
        self.region_temp = 1.5 if self.region == "north" else -2.5
        rng = np.random.default_rng(self.seed)
        random.seed(self.seed)
        self.rng = rng
        self.settings = dict(DEFAULT_SETTINGS)
        self.settings["rain"] = float(self.opts.get("wetness", 1.0))
        self.start_tick = 243 * CAL_DAY + CAL_DAY // 4     # 1 September, Year 1, early morning
        self.tick = self.start_tick
        self.make_grids()

        # ---------------- terrain (see make_terrain)
        X, Y = self.X, self.Y
        h, sea = make_terrain(self.seed, self.opts)
        self.height = h
        self.sea = sea
        self.land = ~sea
        self.coast = dilate(sea, 2) & ~sea
        p = np.pad(self.height, 1, mode="edge")
        slope = np.abs(p[2:, 1:-1] - p[:-2, 1:-1]) + np.abs(p[1:-1, 2:] - p[1:-1, :-2])
        self.slope = np.clip(slope / max(1e-6, float(slope.max())) * 2.5, 0, 1).astype(np.float32)

        f32 = lambda v=0.0: np.full((GW, GH), v, np.float32)
        self.water = np.clip(SEA_LEVEL + 0.02 - self.height, 0, None).astype(np.float32)
        wet = float(self.opts.get("wetness", 1.0))
        self.moist = np.clip((0.9 - self.height * 0.8) * (0.6 + 0.4 * wet) + rng.random((GW, GH)) * 0.1,
                             0.05, 1).astype(np.float32)
        self.snow = f32()
        self.nutr = (0.25 + value_noise(GW, GH, 10, rng) * 0.35).astype(np.float32)
        self.detritus = (0.1 + value_noise(GW, GH, 12, rng) * 0.25).astype(np.float32)
        self.microbes = (0.15 + rng.random((GW, GH)) * 0.1).astype(np.float32)
        self.fungus = f32()
        self.pollen = f32()
        self.fire = f32()
        self.pspec = np.full((GW, GH), -1, np.int16)
        self.pbio = f32()
        self.temp = f32(15)
        self.light = f32(1)
        self.cover = f32()
        self.rain_now = f32()
        self.struct = np.zeros((GW, GH), np.int8)
        self.owner = np.full((GW, GH), -1, np.int16)
        self.sanctuary = np.zeros((GW, GH), bool)
        self.trapzone = np.zeros((GW, GH), bool)
        # ocean
        self.shallow = sea & dilate(~sea, 3)
        self.coast_sea = sea & dilate(~sea, 1)
        self.plankton = np.where(sea, 0.3, 0).astype(np.float32)
        self.fish = np.where(sea, 0.5, 0).astype(np.float32)
        self.shellfish = np.where(self.shallow, 0.6, 0).astype(np.float32)
        self.sediment = f32()

        self.plant_species = native_plants(self.region) + introduced_plants()
        self.animal_species = native_animals(self.region) + introduced_animals()
        self.fungus_entry = SimpleEntry("fungus", "Fungi", (232, 222, 196),
                                        "Mycelium threads through the soil, decomposing dead matter and feeding "
                                        "plant roots. Mushrooms glow at night.")
        self.microbe_entry = SimpleEntry("microbe", "Microbes", (190, 120, 235),
                                         "Soil bacteria recycle dead matter into nutrients, bloom on corpses, "
                                         "and make disease spread faster.")
        self.human_entry = SimpleEntry("human", "Humans", (235, 200, 160),
                                       "Click the world to bring a group of settlers. They live in tribes "
                                       "that build, farm, hunt, clear land - and fight.")
        self.rebuild_tables()

        # ---------------- vegetation: pre-human Aotearoa, mostly forest
        n1 = value_noise(GW, GH, 14, rng)
        n2 = value_noise(GW, GH, 9, rng)
        rr = rng.random((GW, GH))
        ix = {p.name: i for i, p in enumerate(self.plant_species)}
        H = self.height
        sp = np.full((GW, GH), ix["Rimu"], np.int16)
        sp[n2 > 0.55] = ix["Kōwhai"]
        sp[(self.moist > 0.55) & (n1 < 0.45)] = ix["Ponga"]
        if self.region == "north":
            sp[(n2 > 0.68) & (H < 0.5)] = ix["Kauri"]
            alpine = H > 0.72
        else:
            sp[(H > 0.38) & (H <= 0.6) & (n1 > 0.3)] = ix["Tawhai"]
            alpine = H > 0.56
        sp[(n1 > 0.72)] = ix["Mānuka"]
        sp[alpine] = ix["Tussock"]
        sp[self.coast & (n2 < 0.5)] = ix["Harakeke"]
        swamp = (self.water > 0.01) & (self.water < 0.15) & ~sea
        sp[swamp] = ix["Raupō"]
        wet_edge = dilate(self.water > 0.02) & ~swamp & ~sea & (n1 < 0.6)
        sp[wet_edge] = ix["Harakeke"]
        cover = float(self.opts.get("forest", 0.7))
        plant_here = (rr < cover) & self.land & ((self.water < 0.2) | swamp) & (H < 0.9)
        self.pspec[plant_here] = sp[plant_here]
        maxb = self.pt["maxb"][np.where(self.pspec >= 0, self.pspec, self.n_plants)]
        self.pbio[plant_here] = (maxb[plant_here] * (0.3 + rng.random(plant_here.sum()) * 0.5)).astype(np.float32)

        fpatch = (value_noise(GW, GH, 10, rng) > 0.58) & (self.moist > 0.35) & self.land
        self.fungus[fpatch] = 0.3

        # ---------------- weather
        self.wind_angle = rng.random() * math.tau
        self.wind_mag = 0.5
        self.wind = (0.0, 0.0)
        self.vapor = 2500.0
        self.clouds = []
        self.sun = 1.0
        self.sun_raw = 1.0
        self.base_temp = 15.0
        self.season_val = 0.0
        self.lightning = []
        self.mast = 0
        self.mast_count = 0
        self.next_mast = self.tick + int(random.uniform(1, 3) * BIO_YEAR)
        self.last_season = None
        self.difficulty = self.opts.get("difficulty", "realistic")
        if self.difficulty not in DIFFICULTIES:
            self.difficulty = "realistic"
        self.scenario = None
        self.actions = Counter()          # what the player did (for the class report)
        self.web = Counter()              # recent energy flow (food, consumer) -> amount (decays)
        self.web_total = Counter()        # all-time energy flow
        self.kill_log = []                # recent predation events for the food-web view
        self.web_n = Counter()            # recent number of animals killed (prey, eater)
        self.web_n_total = Counter()

        # ---------------- life
        self.animals = []
        if self.region == "north":
            start = {"Wētā": 50, "Kiwi": 26, "Kākāpō": 6, "Tūī": 32, "Kererū": 20, "Ruru": 8, "Kārearea": 2}
        else:
            start = {"Wētā": 45, "Kiwi": 18, "Kākāpō": 12, "Tūī": 22, "Kererū": 14, "Ruru": 6, "Kārearea": 5,
                     "Takahē": 10}
        scale = max(0.4, float(self.land.mean()) / 0.55)
        start = {k: max(2, int(v * scale)) for k, v in start.items()}
        for spc in self.animal_species:
            for _ in range(start.get(spc.name, 0)):
                self.spawn_random(spc)
        self.tribes = []
        self.ships = []
        self.milestones = []
        self.milestone_keys = set()
        self.long_history = []
        self.death_totals = Counter()
        self.start_trees = None
        self.vital_parts = {}
        self.collapsed = False
        self.no_native_since = None
        self.peak_people = 0
        self.people = []
        self.pgrid = {}
        self.grid = {}
        self.counts = {}
        self.plant_counts = np.zeros(len(self.plant_species), np.int64)
        self.history = []
        self.events = []
        self.prev_counts = {}
        self.prev_plant = {}
        self.event_cooldown = {}
        # tracking for alerts
        self.alerts = []
        self.new_alerts = []
        self.alert_cool = {}
        self.alert_state = {}
        self.deaths = Counter()
        self.death_days = []
        self.ploss = Counter()
        self.ploss_days = []
        self.human_deaths = {}
        self.battle_deaths = 0
        self.drained = 0.0
        self.fish_caught = 0.0
        self.fish_days = []
        self.fish_caught_recent = 0.0
        self.cleared_cells = 0
        self.erosion = 0.0
        self.erosion_recent = 0.0
        self.erosion_days = []
        self.vitality = 75.0
        self.mood = "Settling in"
        self.needs = []
        self.count_species()
        self.log("Aotearoa before people: %s Island, %s. Seed %d." % (
            self.region.capitalize(), dict(GEOGRAPHIES).get(self.opts["geo"], ""), self.seed), (150, 220, 160))
        self.log("Time is compressed: each calendar year, animals and people live about %d years of their lives "
                 "(the same for every species), so you can watch generations come and go." % LIFE_SPEED,
                 (160, 170, 185))

    def make_grids(self):
        X, Y = np.meshgrid(np.arange(GW, dtype=np.float32), np.arange(GH, dtype=np.float32), indexing="ij")
        self.X, self.Y = X, Y

    # ------------------------------------------------------------------ utils
    @property
    def day(self):
        """Calendar days since the simulation began."""
        return (self.tick - self.start_tick) // CAL_DAY + 1

    @property
    def year(self):
        return self.tick // YEAR_TICKS + 1

    @property
    def year_frac(self):
        return (self.tick % YEAR_TICKS) / YEAR_TICKS

    def month_day(self):
        doy = (self.tick % YEAR_TICKS) // CAL_DAY
        for m, n in enumerate(MONTH_DAYS):
            if doy < n:
                return m, doy + 1
            doy -= n
        return 11, 31

    @property
    def season(self):
        return MONTH_SEASON[self.month_day()[0]]

    @property
    def date(self):
        m, d = self.month_day()
        return "%d %s, Year %d" % (d, MONTHS[m], self.year)

    @property
    def stamp(self):
        m, d = self.month_day()
        return "%d %s Y%d" % (d, MONTHS[m], self.year)

    @property
    def elapsed(self):
        return self.tick - self.start_tick

    @property
    def clock(self):
        frac = (self.tick % CAL_DAY) / CAL_DAY
        hours = (6 + frac * 24) % 24
        return "%02d:%02d" % (int(hours), int((hours % 1) * 60))

    def log(self, text, color=(220, 222, 228), key=None, cooldown_days=0.0):
        if key is not None:
            last = self.event_cooldown.get(key, -1e9)
            if self.tick - last < cooldown_days * DAY_TICKS:
                return
            self.event_cooldown[key] = self.tick
        self.events.append((self.stamp, text, color))
        if len(self.events) > 100:
            self.events = self.events[-100:]

    def species_by_name(self, name):
        for s in self.animal_species + self.plant_species:
            if s.name == name:
                return s
        return None

    def rebuild_tables(self):
        P = self.plant_species
        n = len(P) + 1

        def tbl(attr, dummy, dtype=np.float32):
            return np.array([getattr(p, attr) for p in P] + [dummy], dtype=dtype)
        self.pt = {
            "growth": tbl("growth", 0.0), "water": tbl("water", 1.0), "light": tbl("light", 1.0),
            "topt": tbl("topt", 0.0), "trange": tbl("trange", 1.0), "spread": tbl("spread", 0.0),
            "maxb": tbl("maxb", 1.0), "edible": tbl("edible", 0.0), "flamm": tbl("flamm", 0.0),
            "maxw": tbl("maxw", 9.0),
            "aquatic": np.array([p.aquatic for p in P] + [False]),
            "flower": np.array([p.flower is not None for p in P] + [False]),
            "tree": np.array([p.tree for p in P] + [False]),
            "pioneer": np.array([p.pioneer for p in P] + [False]),
            "mast": np.array([p.mast for p in P] + [False]),
            "fixer": np.array([p.fixer for p in P] + [False]),
            "native": np.array([p.native for p in P] + [True]),
            "color": np.array([p.color for p in P] + [(0, 0, 0)], np.float32),
            "fcolor": np.array([(p.flower or p.color) for p in P] + [(0, 0, 0)], np.float32),
        }
        self.p_edible = [p.edible for p in P]
        self.p_flower = [p.flower is not None for p in P]
        self.p_tree = [p.tree for p in P]
        self.p_mast = [p.mast for p in P]
        self.n_plants = n - 1

    def add_plant_species(self, sp):
        self.plant_species.append(sp)
        self.rebuild_tables()
        self.plant_counts = np.zeros(len(self.plant_species), np.int64)
        self.log("New plant species designed: %s" % sp.name, sp.color)

    def add_animal_species(self, sp):
        self.animal_species.append(sp)
        self.counts[sp] = 0
        self.log("New animal species designed: %s" % sp.name, sp.color)

    def spawn_random(self, sp, n=1):
        for _ in range(n):
            for _ in range(60):
                x = random.uniform(0, GW - 0.01)
                y = random.uniform(0, GH - 0.01)
                if getattr(sp, "marine", False):
                    if self.coast_sea[int(x), int(y)]:
                        break
                elif self.land[int(x), int(y)] and (sp.swimmer or self.water[int(x), int(y)] < 0.3):
                    break
            self.animals.append(Animal(sp, x, y, energy_frac=random.uniform(0.5, 0.8)))

    def spawn_at(self, sp, x, y, n=1):
        added = 0
        for _ in range(n):
            if len(self.animals) >= TOTAL_CAP:
                break
            ax = min(max(x + random.uniform(-1.5, 1.5), 0), GW - 0.01)
            ay = min(max(y + random.uniform(-1.5, 1.5), 0), GH - 0.01)
            if not sp.flier and not getattr(sp, "marine", False) and not sp.swimmer:
                if self.sea[int(ax), int(ay)] or self.water[int(ax), int(ay)] > 0.3:
                    ax, ay = min(max(x, 0), GW - 0.01), min(max(y, 0), GH - 0.01)
                    if self.sea[int(ax), int(ay)] or self.water[int(ax), int(ay)] > 0.3:
                        continue
            self.animals.append(Animal(sp, ax, ay, energy_frac=0.75))
            added += 1
        self.counts[sp] = self.counts.get(sp, 0) + added
        return added

    def disc(self, cx, cy, r):
        x0, x1 = max(0, int(cx - r)), min(GW, int(cx + r) + 1)
        y0, y1 = max(0, int(cy - r)), min(GH, int(cy + r) + 1)
        if x0 >= x1 or y0 >= y1:
            return None
        X = self.X[x0:x1, y0:y1]
        Y = self.Y[x0:x1, y0:y1]
        m = (X + 0.5 - cx) ** 2 + (Y + 0.5 - cy) ** 2 <= r * r
        return (slice(x0, x1), slice(y0, y1)), m

    def note_death(self, sp, cause):
        self.deaths[(sp.name, cause)] += 1
        self.death_totals[(sp.name, cause)] += 1

    def milestone(self, key, cat, title, text="", color=(220, 222, 228), pos=None):
        """Record a major event in the island's ecological history (once per key)."""
        if key in self.milestone_keys:
            return False
        self.milestone_keys.add(key)
        self.milestones.append({"key": key, "cat": cat, "title": title, "text": text, "color": color,
                                "pos": pos, "date": self.stamp, "tick": self.tick, "year": self.year})
        return True

    def feed(self, food, consumer, amt):
        """Food-web bookkeeping: energy flowing from `food` to `consumer`."""
        k = (food, consumer)
        self.web[k] += amt
        self.web_total[k] += amt

    def kill_animal(self, a, cause):
        if cause.startswith("eaten by ") or cause == "hunted by humans":
            eater = "People" if cause == "hunted by humans" else cause[9:]
            self.feed(a.sp.name, eater, a.esize * 36)
            self.web_n[(a.sp.name, eater)] += 1
            self.web_n_total[(a.sp.name, eater)] += 1
            stage = ("chick" if a.sp.bird else "young") if a.young else ("young" if a.juvenile else "adult")
            self.kill_log.append((self.tick, eater, a.sp.name, stage, a.x, a.y))
            if len(self.kill_log) > 60:
                del self.kill_log[:20]
        if not a.alive:
            return
        a.alive = False
        self.note_death(a.sp, cause)
        x, y = int(a.x), int(a.y)
        self.detritus[x, y] += a.esize * 0.3

    # ---------------------------------------------------------------- weather
    def update_weather(self):
        s = self.settings
        self.tick += 1
        frac = (self.tick % CAL_DAY) / CAL_DAY
        self.sun_raw = max(0.0, math.sin(frac * math.tau))
        doy = self.year_frac * YEAR_DAYS
        self.season_val = math.cos((doy - 25) / YEAR_DAYS * math.tau)   # +1 late January, -1 late July
        self.sun = (self.sun_raw ** 0.7) * (0.78 + 0.22 * self.season_val) * s["sun"]
        self.base_temp = (13 + 5 * self.season_val + 5 * (self.sun_raw - 0.4) + self.region_temp
                          + s["temp"] + (s["sun"] - 1) * 5)

        # mast years begin at the start of summer
        season = self.season
        if season != self.last_season:
            self.last_season = season
        # mast years: every 2-5 years (biological time) rimu, beech and tussock seed heavily
        if self.tick >= getattr(self, "next_mast", 0):
            if getattr(self, "next_mast", 0):
                self.mast = int(BIO_YEAR * 0.8)
                self.mast_count = getattr(self, "mast_count", 0) + 1
                alerts.alert_mast(self)
            self.next_mast = self.tick + int(random.uniform(2, 5) * BIO_YEAR)
        if self.mast > 0:
            self.mast -= 1

        self.wind_angle += random.gauss(0, 0.012)
        self.wind_mag = min(1.0, max(0.15, self.wind_mag + random.uniform(-0.01, 0.01)))
        wm = self.wind_mag * s["wind"]
        wx, wy = math.cos(self.wind_angle) * wm, math.sin(self.wind_angle) * wm
        self.wind = (wx, wy)

        if (len(self.clouds) < 11 and self.vapor > 200 and
                random.random() < 0.0045 * s["rain"] * min(3.0, self.vapor / 1500)):
            r = random.uniform(8, 17)
            w = min(self.vapor * 0.3, random.uniform(90, 260))
            self.vapor -= w
            if random.random() < 0.7:
                cx, cy = self.random_land()
            else:
                cx, cy = random.uniform(0, GW), random.uniform(0, GH)
            self.clouds.append(Cloud(cx, cy, r, w))

        cover = np.zeros((GW, GH), np.float32)
        rain_add = np.zeros((GW, GH), np.float32)
        keep = []
        X, Y = self.X, self.Y
        for c in self.clouds:
            c.age += 1
            c.x += wx * 0.09
            c.y += wy * 0.09
            grab = self.vapor * 0.0004
            c.water += grab
            self.vapor -= grab
            if c.water < 4 or c.x < -c.r * 2 or c.x > GW + c.r * 2 or c.y < -c.r * 2 or c.y > GH + c.r * 2:
                self.vapor += max(c.water, 0) * 0.7
                continue
            keep.append(c)
            rx, ry = c.r * 1.5, c.r
            sl = self.disc(c.x, c.y, rx)
            if sl is None:
                continue
            (sx, sy), _ = sl
            d2 = ((X[sx, sy] - c.x) / rx) ** 2 + ((Y[sx, sy] - c.y) / ry) ** 2
            blob = np.clip(1 - d2, 0, 1)
            fade = min(1.0, c.age / 60.0)
            cover[sx, sy] += blob * min(1.0, c.water / 120) * fade
            # mountains squeeze rain out of clouds
            if not c.raining and c.water > 70 and random.random() < 0.01 * s["rain"]:
                c.raining = True
            if c.raining:
                if c.water < 12:
                    c.raining = False
                else:
                    rm = (blob > 0.25)
                    amt = 0.0028 * min(1.0, c.water / 100) * math.sqrt(max(s["rain"], 0.05))
                    oro = 1 + self.height[sx, sy]
                    n = float((rm * oro).sum())
                    rain_add[sx, sy] += rm * amt * oro
                    c.water -= amt * n
                    if c.water > 150 and random.random() < 0.0012 * s["rain"]:
                        self.strike(c.x + random.uniform(-rx, rx) * 0.6, c.y + random.uniform(-ry, ry) * 0.6)
        self.clouds = keep
        self.cover = np.clip(cover, 0, 1)
        self.light = self.sun * (1 - 0.65 * self.cover)
        self.temp = (self.base_temp + 3 - self.height * 16 - self.cover * 2.0
                     - np.minimum(self.water, 1) * 1.0).astype(np.float32)
        self.rain_now = rain_add
        if rain_add.any():
            freezing = self.temp < 0
            self.snow += rain_add * freezing
            self.water += rain_add * ~freezing
        self.vapor += 1.3 * s["rain"]
        self.vapor *= 0.9996
        for l in self.lightning:
            l[2] -= 1
        self.lightning = [l for l in self.lightning if l[2] > 0]

    def strike(self, x, y):
        x, y = int(min(max(x, 0), GW - 1)), int(min(max(y, 0), GH - 1))
        self.lightning.append([x, y, 6])
        if self.pbio[x, y] > 0.15 and self.moist[x, y] < 0.55 and self.water[x, y] < 0.05:
            self.fire[x, y] = 1.0
            self.log("Lightning set the vegetation ablaze!", (255, 170, 70), key="lfire", cooldown_days=0.5)
        else:
            self.log("Thunderstorm overhead.", (190, 200, 255), key="thunder", cooldown_days=1)

    # ------------------------------------------------------------------ water
    def update_water(self):
        s = self.settings
        w = self.water
        if s["gravity"] > 0.001:
            total = self.height + w
            p = np.pad(total, 1, mode="edge")
            k = min(0.24, 0.12 * s["gravity"])
            fr = np.maximum(total - p[2:, 1:-1], 0) * k
            fl = np.maximum(total - p[:-2, 1:-1], 0) * k
            fd = np.maximum(total - p[1:-1, 2:], 0) * k
            fu = np.maximum(total - p[1:-1, :-2], 0) * k
            out = fr + fl + fd + fu
            scale = np.where(out > w, w / (out + 1e-9), 1.0).astype(np.float32)
            fr *= scale; fl *= scale; fd *= scale; fu *= scale
            inflow = np.zeros_like(w)
            inflow[1:, :] += fr[:-1, :]
            inflow[:-1, :] += fl[1:, :]
            inflow[:, 1:] += fd[:, :-1]
            inflow[:, :-1] += fu[:, 1:]
            w += inflow - (fr + fl + fd + fu)
        # the ocean holds its level: rivers drain into it
        w[self.sea] = SEA_LEVEL - self.height[self.sea]
        land = self.land
        inf = np.minimum(w, np.maximum(0, 1 - self.moist) * 0.012) * land
        w -= inf
        self.moist += inf
        self.moist += 0.04 * (neigh_mean(self.moist) - self.moist)
        # Aotearoa's maritime climate: drizzle, fog and dew keep the soil from drying out completely
        self.moist += 0.0002 * s["rain"] * (0.6 + self.height) * land * (self.moist < 0.32)
        tf = np.clip(1 + self.temp / 25, 0.1, 3) * (0.35 + self.sun)
        cover = (self.pspec >= 0) * 0.4
        ev_w = w * 0.00022 * s["evap"] * tf * land
        ev_m = self.moist * 0.00007 * s["evap"] * tf * (1 - cover)
        w -= ev_w
        self.moist -= ev_m
        self.vapor += float(ev_w.sum() + ev_m.sum())
        melt = np.minimum(self.snow, np.maximum(self.temp, 0) * 0.0015)
        self.snow -= melt
        w += melt
        self.snow[self.sea] = 0
        np.maximum(w, 0, out=w)
        np.clip(self.moist, 0, 1.2, out=self.moist)
        # erosion: rain on bare slopes washes soil away
        if self.rain_now.any():
            bare = (self.pspec < 0) & land & (self.struct != HOUSE) & (self.height < 0.8)
            loss = self.rain_now * bare * self.slope * 6
            loss = np.minimum(loss, self.nutr * 0.5)
            self.nutr -= loss
            self.detritus -= np.minimum(self.detritus, loss * 0.5)
            self.erosion += float(loss.sum())
            if loss.any():
                spread = loss
                for _ in range(3):
                    spread = np.maximum(spread, neigh_mean(spread) * 0.9)
                self.sediment += spread * self.sea * 3

    # ----------------------------------------------------------------- plants
    def update_plants(self):
        rng = self.rng
        t = self.pt
        P = self.n_plants
        ps = self.pspec
        has = ps >= 0
        idx = np.where(has, ps, P)
        b = self.pbio
        aq = t["aquatic"][idx]
        lf = np.clip(self.light / t["light"][idx], 0, 1) * (self.snow < 0.1)
        wet = np.where(aq, self.moist + self.water * 2, self.moist)
        wf = np.clip(wet / t["water"][idx], 0, 1)
        tf = np.exp(-((self.temp - t["topt"][idx]) / t["trange"][idx]) ** 2)
        nf = 0.35 + 0.65 * np.clip(self.nutr / 0.4, 0, 1)
        myc = 1 + 0.35 * np.clip(self.fungus * 3, 0, 1)
        maxb = t["maxb"][idx]
        g = t["growth"][idx] * lf * wf * tf * nf * myc
        grow = (g * b * np.clip(1 - b / maxb, 0, 1) + g * 0.003) * has
        b += grow
        use = np.minimum(grow * 0.3, self.moist)
        self.moist -= use
        self.vapor += float(use.sum())
        self.nutr -= grow * 0.25
        self.nutr += grow * 0.35 * t["fixer"][idx]           # gorse fixes nitrogen
        np.maximum(self.nutr, 0, out=self.nutr)
        flood = ((self.water > 0.3) & ~aq) | (aq & (self.water > 0.6)) | self.sea
        topt = t["topt"][idx]
        heat = (tf < 0.1) & (self.temp > topt)
        frost = self.temp < topt - 2.2 * t["trange"][idx]
        dry = wf < np.where(t["tree"][idx], 0.06, 0.12)
        stress = has & (dry | heat | frost | flood | (self.moist > t["maxw"][idx]))
        loss = (b * 0.012 * stress / np.maximum(1.0, maxb) + b * 0.0003) * has
        b -= loss
        self.detritus += loss
        self.ploss["drought"] += float((loss * stress).sum()) * 0.3
        blocked = (self.struct == HOUSE) | (self.struct == FIELD)
        dead = has & ((b < 0.01) | blocked)
        ps[dead] = -1
        b[dead] = 0

        # seeding: flowers need pollinators, trees need seed-dispersing birds
        flower = t["flower"][idx]
        tree = t["tree"][idx]
        mult = np.where(flower | tree, 0.25 + 3.0 * self.pollen, 1.0)
        if self.mast > 0:
            mult = mult * np.where(t["mast"][idx], 3.0, 1.0)
        mature = has & (b > 0.4 * maxb)
        prob = t["spread"][idx] * mult * mature
        sx, sy = np.nonzero(rng.random((GW, GH)) < prob)
        if len(sx):
            wx, wy = self.wind
            far = np.where(t["tree"][ps[sx, sy]] & ~t["native"][ps[sx, sy]], 3, 1)   # pine seed flies far
            dx = (rng.integers(-2, 3, len(sx)) + np.round(wx * rng.random(len(sx)) * 2.5)).astype(int) * far
            dy = (rng.integers(-2, 3, len(sx)) + np.round(wy * rng.random(len(sx)) * 2.5)).astype(int) * far
            tx = np.clip(sx + dx, 0, GW - 1)
            ty = np.clip(sy + dy, 0, GH - 1)
            src = ps[sx, sy]
            tgt = ps[tx, ty]
            src_aq = t["aquatic"][src]
            wet_ok = np.where(src_aq, (self.water[tx, ty] > 0.03) & (self.water[tx, ty] < 0.5),
                              self.water[tx, ty] < 0.2)
            empty = tgt < 0
            tgt_idx = np.where(empty, P, tgt)
            rr = rng.random(len(sx))
            weak = (~empty) & (t["maxb"][tgt_idx] < t["maxb"][src] * 0.6) & (b[tx, ty] < 0.25) & (rr < 0.25)
            # succession: shade-tolerant forest grows up through pioneer scrub
            nursery = (~empty) & t["pioneer"][tgt_idx] & (t["light"][src] <= 0.3) & \
                      (b[tx, ty] > 0.5 * t["maxb"][tgt_idx]) & (rr < 0.15)
            st = self.struct[tx, ty]
            ok = (empty | weak | nursery) & wet_ok & (self.fire[tx, ty] == 0) & (self.snow[tx, ty] < 0.1) & \
                 ~self.sea[tx, ty] & ((st == NONE) | (st == RUIN) | (st == TRAP))
            ps[tx[ok], ty[ok]] = src[ok]
            b[tx[ok], ty[ok]] = 0.03
        self.pollen *= 0.995

    # ------------------------------------------------------- fungi & microbes
    def update_decomposers(self):
        s = self.settings
        rng = self.rng
        T = self.temp
        d = self.detritus
        dec = s["decay"]
        f = self.fungus
        ff = np.clip(self.moist / 0.4, 0, 1) * self.land
        tff = np.exp(-((T - 14) / 10) ** 2)
        dark = 1 - 0.5 * np.clip(self.light, 0, 1)
        food = d / (d + 0.1)
        fg = 0.04 * f * food * ff * tff * dark * (1 - f)
        f += fg
        eat = 0.03 * f * d * ff * tff * dec
        d -= eat
        self.nutr += eat * 0.95
        fdie = f * (0.0015 + 0.008 * (d < 0.02) + 0.01 * (self.moist < 0.08))
        f -= fdie
        self.nutr += fdie * 0.5
        f += 0.03 * (neigh_mean(f) - f) * ff
        if random.random() < 0.05:
            spores = (rng.random((GW, GH)) < 0.00015) & (d > 0.25) & (self.moist > 0.5)
            f[spores] = np.maximum(f[spores], 0.08)
        np.clip(f, 0, 1, out=f)

        m = self.microbes
        mf = np.clip(self.moist / 0.3, 0, 1)
        tfm = np.exp(-((T - 22) / 15) ** 2)
        mg = 0.05 * m * (d / (d + 0.2)) * mf * tfm * (1 - m) + 0.0004 * mf
        m += mg
        eat = 0.02 * m * d * mf * tfm * dec
        d -= eat
        self.nutr += eat * 0.9
        mdie = m * 0.003 * (1 + 5 * (self.moist < 0.05) + 3 * (T < 0))
        m -= mdie
        d += mdie * 0.1
        m += (0.04 + 0.2 * np.minimum(self.water, 0.5)) * (neigh_mean(m) - m)
        self.nutr += 0.00004 * m
        np.clip(m, 0, 1, out=m)
        m[self.sea] = 0.1

        ab = d * 0.0003 * dec
        d -= ab
        self.nutr += ab
        np.maximum(d, 0, out=d)
        self.nutr += 0.01 * (neigh_mean(self.nutr) - self.nutr)
        self.nutr *= 0.99985
        np.clip(self.nutr, 0, 2, out=self.nutr)
        np.minimum(d, 3, out=d)
        d[self.sea] = 0

    # ------------------------------------------------------------------ ocean
    def update_ocean(self):
        """Plankton -> fish -> seals, penguins and people.  Shellfish filter plankton in the shallows."""
        sea = self.sea
        p, f, sh, sed = self.plankton, self.fish, self.shellfish, self.sediment
        light = min(1.0, self.sun) * (1 - np.clip(sed, 0, 0.8))
        n = self.nutr
        pg = 0.04 * p * light * (n / (n + 0.15)) * (1 - p) * sea + 0.0005 * sea
        p += pg
        n -= np.minimum(n, pg * 0.2)
        n += 0.0006 * sea                                     # upwelling from the deep ocean
        eat = 0.02 * f * p
        p -= eat
        f += (0.004 * f * (p / (p + 0.2)) * (1 - f) - 0.0012 * f) * sea
        f += 0.05 * (neigh_mean(f) - f) * sea
        edge = np.zeros_like(sea)
        edge[0, :] = edge[-1, :] = edge[:, 0] = edge[:, -1] = True
        f[edge & sea] = np.maximum(f[edge & sea], 0.5)        # the open ocean restocks the edges
        filt = 0.01 * sh * p * self.shallow
        p -= filt
        sh += (0.05 * filt * (1 - sh) - 0.0004 * sh - 0.004 * sh * np.clip(sed - 0.1, 0, 1)) * self.shallow
        sed *= 0.997
        np.clip(p, 0, 1, out=p)
        np.clip(f, 0, 1, out=f)
        np.clip(sh, 0, 1, out=sh)

    # ------------------------------------------------------------------- fire
    def update_fire(self):
        f = self.fire
        if f.max() <= 0:
            return
        rng = self.rng
        burning = f > 0
        burn = np.minimum(self.pbio, 0.04 * f) * burning
        self.pbio -= burn
        self.ploss["fire"] += float(burn.sum())
        self.nutr += burn * 0.5
        self.fungus[burning] *= 0.95
        self.microbes[burning] *= 0.98
        f *= 0.985
        f[burning & (self.pbio < 0.02)] *= 0.8
        f[(self.water > 0.03) | (self.moist > 0.8) | (self.snow > 0.05)] = 0
        # houses burn too
        hb = burning & (self.struct == HOUSE) & (f > 0.5)
        if hb.any():
            self.struct[hb] = RUIN
            self.owner[hb] = -1
        p = np.pad(f, 1)
        nb = p[2:, 1:-1] + p[:-2, 1:-1] + p[1:-1, 2:] + p[1:-1, :-2]
        wx, wy = self.wind
        if wx > 0: nb += p[:-2, 1:-1] * wx
        else: nb += p[2:, 1:-1] * -wx
        if wy > 0: nb += p[1:-1, :-2] * wy
        else: nb += p[1:-1, 2:] * -wy
        idx = np.where(self.pspec >= 0, self.pspec, self.n_plants)
        flam = self.pt["flamm"][idx]
        flam = np.where(self.struct == HOUSE, 0.6, flam)
        dry = np.clip(1 - self.moist * 1.6, 0, 1)
        fuel = (self.pbio > 0.08) | (self.struct == HOUSE)
        pr = nb * 0.09 * flam * dry * fuel
        ign = (f == 0) & (rng.random((GW, GH)) < pr)
        f[ign] = 0.9
        f[f < 0.05] = 0

    # ---------------------------------------------------------------- animals
    def count_species(self):
        c = {sp: 0 for sp in self.animal_species}
        for a in self.animals:
            c[a.sp] = c.get(a.sp, 0) + 1
        self.counts = c

    def rebuild_traps(self):
        self.trapzone = dilate(self.struct == TRAP, 3)

    def update_animals(self):
        s = self.settings
        animals = self.animals
        grid = {}
        for a in animals:
            grid.setdefault((int(a.x) >> 3, int(a.y) >> 3), []).append(a)
        self.grid = grid
        night = self.sun_raw < 0.1
        dusk = self.sun_raw < 0.25
        temp, water, snow, fire = self.temp, self.water, self.snow, self.fire
        struct, sanct, trapz = self.struct, self.sanctuary, self.trapzone
        grav = s["gravity"]
        births = []
        counts = self.counts
        total = len(animals)
        self.meat_eaters = any(("meat" in sp.diet or sp.nest_raider) and counts.get(sp, 0)
                               for sp in self.animal_species)
        self.any_people = bool(self.people)
        rnd = random.random
        # competition for food: above the land's carrying capacity, finding enough to eat costs more.
        # Mast-dependent rodents can only reach high numbers while seed is falling.
        crowd = {}
        for csp, n in counts.items():
            if getattr(csp, "kind", "") != "animal":
                continue
            ce = csp.carry * (1.0 if csp.native else diff(self, "pest_carry"))
            if getattr(csp, "mast_boom", False) and self.mast <= 0:
                ce *= 0.35
            if n > ce:
                crowd[csp] = 1 + (n / ce - 1) * 1.5

        for a in animals:
            if not a.alive:
                continue
            sp = a.sp
            a.age += 1
            a.cool -= 1
            mat = min(a.maxage * sp.mature_frac, sp.young_ticks * 3 + 1)
            a.esize = a.size * (0.35 + 0.65 * a.age / mat) if a.age < mat else a.size
            cx, cy = int(a.x), int(a.y)
            cap = 60.0 * a.size
            T = float(temp[cx, cy])
            dt = (T - sp.topt) / sp.trange
            tstress = 1 + dt * dt
            if dt < -2.2:
                tstress += 3
            act = sp.activity
            torpor = dt < -1.6
            if torpor:
                tstress = 1.0
                a.age -= 0.75
            a.awake = (not torpor) and ((act == "any") or (act == "day" and not night) or
                                        (act == "night" and dusk))
            mv = 0.0
            if a.awake:
                a.think -= 1
                if a.think <= 0:
                    a.think = 6 + int(rnd() * 4)
                    kids = self.think(a, cap, grid, counts, total + len(births))
                    if kids:
                        births.extend(kids)
                spd = a.speed
                prey = a.prey
                if prey is not None:
                    if prey.alive:
                        dx, dy = prey.x - a.x, prey.y - a.y
                        d = math.hypot(dx, dy) + 1e-6
                        if d < 0.7 + 0.35 * (a.esize + prey.esize):
                            ratio = prey.esize / max(0.05, a.esize)
                            if prey.young:
                                chance = 0.6            # eggs, chicks and babies
                            elif not prey.awake:
                                # roosting birds high in trees are hard to reach; sleeping ground animals easy
                                chance = 0.07 if prey.sp.flier else 0.55
                            else:
                                chance = min(0.7, max(0.1, 0.15 + 0.55 * (1 - ratio)))
                            if prey.sp.hides and not prey.awake:
                                chance *= 0.3           # resting hidden in a burrow or tree hole
                            big = ratio > 0.7 and not prey.young
                            if big:
                                chance *= 0.35          # adult prey nearly as big as the predator fights back
                            if prey.sp.naive and not sp.native and (prey.awake or not prey.sp.flier):
                                # never learned to fear mammals
                                chance += diff(self, "naive_bonus") * (0.35 if big else 1.0)
                            elif sp.native and prey.sp.native:
                                chance *= 0.6           # co-evolved prey have defences
                            # rare prey are hard to find: the last few hide in the safest spots, and
                            # predators switch to commoner food (a "type III" functional response)
                            pc = max(1.0, getattr(prey.sp, "carry", 150) * 0.3)
                            chance *= min(1.0, max(0.05, counts.get(prey.sp, 0) / pc))
                            chance = min(chance, 0.85)
                            if rnd() < chance:
                                self.kill_animal(prey, "eaten by " + sp.name)
                                # each simulated prey animal stands for several real ones (real prey vastly
                                # outnumber their predators), so one kill feeds a predator for longer
                                a.energy = min(cap, a.energy + prey.esize * 60 * 0.6 * KILL_FOOD)
                            else:
                                prey.flee = 12
                                a.think = 20
                            a.prey = None
                        else:
                            a.hx, a.hy = dx / d, dy / d
                            spd *= 1.18
                    else:
                        a.prey = None
                elif a.tx is not None:
                    dx, dy = a.tx - a.x, a.ty - a.y
                    d = math.hypot(dx, dy)
                    if d < 0.5:
                        a.tx = None
                        spd *= 0.2
                    else:
                        a.hx, a.hy = dx / d, dy / d
                        spd = min(spd, d)
                else:
                    a.hx += random.gauss(0, 0.35)
                    a.hy += random.gauss(0, 0.35)
                    n = math.hypot(a.hx, a.hy) + 1e-6
                    a.hx /= n
                    a.hy /= n
                    spd *= 0.55
                if a.flee > 0:
                    a.flee -= 1
                    spd = a.speed * 1.25
                if a.young:
                    spd *= 0.7
                if not sp.flier and snow[cx, cy] > 0.2:
                    spd *= 0.5
                if sp.swimmer and water[cx, cy] > 0.2:
                    spd *= 1.2
                nx, ny = a.x + a.hx * spd, a.y + a.hy * spd
                if nx < 0 or nx >= GW:
                    a.hx = -a.hx
                    nx = a.x
                    a.tx = None
                if ny < 0 or ny >= GH:
                    a.hy = -a.hy
                    ny = a.y
                    a.tx = None
                ix, iy = int(nx), int(ny)
                blocked = False
                if not sp.flier:
                    if not sp.swimmer:
                        here_wet = self.sea[cx, cy] or water[cx, cy] > 0.3
                        there_wet = self.sea[ix, iy] or water[ix, iy] > 0.3
                        if there_wet and not here_wet:
                            blocked = True                   # land animals don't walk into the sea or lakes
                        elif here_wet:
                            # washed into water: struggle back towards dry land
                            a.energy -= cap * 0.01
                            if there_wet and water[ix, iy] >= water[cx, cy]:
                                for k in range(8):
                                    ang = k * math.pi / 4
                                    jx, jy = int(a.x + math.cos(ang) * 2), int(a.y + math.sin(ang) * 2)
                                    if 0 <= jx < GW and 0 <= jy < GH and not self.sea[jx, jy] and water[jx, jy] <= 0.3:
                                        a.hx, a.hy = math.cos(ang), math.sin(ang)
                                        nx, ny = a.x + a.hx * spd, a.y + a.hy * spd
                                        break
                    if not blocked and struct[ix, iy] == HOUSE and not sp.commensal:
                        blocked = True
                if not sp.native and sanct[ix, iy] and not sanct[cx, cy]:
                    blocked = True                       # predator-proof fence
                if sp.marine and not (self.sea[ix, iy] or self.coast[ix, iy]):
                    blocked = True                       # sea creatures stay at the coast
                if blocked:
                    if rnd() < 0.5:
                        a.hx, a.hy = -a.hy, a.hx
                    else:
                        a.hx, a.hy = a.hy, -a.hx
                    a.tx = None
                    a.prey = None
                    nx, ny = a.x, a.y
                a.x, a.y = nx, ny
                r = spd / sp.speed
                mv = r * r
                if a.energy < cap * 0.95:
                    self.graze(a, cap, int(nx), int(ny))
                move_cost = (0.3 + 0.7 * mv * (grav if sp.flier else grav ** 0.5))
            else:
                move_cost = 0.22 if torpor else 0.3
            cost = sp.metab * 1.5 * cap * tstress * move_cost * crowd.get(sp, 1.0)
            if a.sick:
                cost *= 2.2
                if rnd() < 0.0015:
                    a.sick = False
                elif rnd() < 0.0004:
                    self.kill_animal(a, "disease")
                    continue
            a.energy -= cost
            if fire[cx, cy] > 0.2 and not sp.flier:
                a.energy -= cap * 0.04
                a.flee = 6
                if a.energy <= 0:
                    self.kill_animal(a, "fire")
                    continue
            if sp.trappable and trapz[cx, cy] and rnd() < 0.006:
                self.kill_animal(a, "trapped")
                continue
            if a.energy <= 0:
                self.kill_animal(a, ("cold" if dt < 0 else "heat") if tstress > 2.5 else "starvation")
            elif a.age > a.maxage:
                self.kill_animal(a, "old age")
            if not a.alive:
                self.detritus[cx, cy] += a.esize * 0.3
                self.microbes[cx, cy] = min(1.0, self.microbes[cx, cy] + 0.15)

        self.animals = [a for a in animals if a.alive] + births
        self.count_species()

    def food_value(self, sp, x, y):
        v = 0.0
        diet = sp.diet
        s = self.pspec[x, y]
        if "plant" in diet and s >= 0:
            e = self.p_edible[s]
            if sp.browser and self.p_tree[s]:
                v += min(float(self.pbio[x, y]), 1.5) * max(e, 0.45)
            else:
                v += min(float(self.pbio[x, y]), 0.6) * e
        if "seed" in diet and s >= 0 and self.p_mast[s]:
            v += 1.0 if self.mast > 0 else 0.08
        if "fungus" in diet:
            v += self.fungus[x, y]
        if "fish" in diet:
            v += self.fish[x, y] * 1.5
        if "detritus" in diet:
            v += self.detritus[x, y] * 0.4
        if "invert" in diet and not self.sea[x, y]:
            v += min(1.0, float(self.detritus[x, y]) * 1.5 + float(self.moist[x, y]) * 0.4) * 0.5
        if "nectar" in diet and s >= 0 and self.p_flower[s] and self.pbio[x, y] > 0.25:
            v += 1.0
        if (sp.diet & {"plant", "seed"}) and self.struct[x, y] == FIELD and not sp.native:
            v += 0.8                                       # crops!
        if sp.commensal and self.struct[x, y] == HOUSE:
            v += 0.8
        if not sp.flier and not sp.swimmer and self.water[x, y] > 0.3:
            return 0.0
        return v

    def graze(self, a, cap, cx, cy):
        sp = a.sp
        diet = sp.diet
        gain = 0.0
        bite = 0.02 * a.esize
        s = self.pspec[cx, cy]
        if "plant" in diet and s >= 0:
            e = self.p_edible[s]
            tree = self.p_tree[s]
            if sp.browser and tree:
                e = max(e, 0.45)
            if e > 0.05:
                amt = min(float(self.pbio[cx, cy]), bite)
                self.pbio[cx, cy] -= amt
                gain += amt * e * 55
                self.feed("Plants", sp.name, amt * e * 55)
                if not sp.native:
                    self.ploss["browse:" + sp.name] += amt
                if sp.disperser and (tree or self.p_flower[s]):
                    self.pollen[cx, cy] = min(1.0, self.pollen[cx, cy] + 0.25)
        if "seed" in diet and s >= 0 and self.p_mast[s]:
            g = bite * (40 if self.mast > 0 else 4)
            gain += g
            self.feed("Fruit & seeds", sp.name, g)
        if "fish" in diet:
            fv = float(self.fish[cx, cy])
            if fv > 0.03:
                amt = min(fv, bite * 0.6)
                self.fish[cx, cy] -= amt
                gain += amt * 60
                self.feed("Fish", sp.name, amt * 60)
        if "fungus" in diet:
            f = float(self.fungus[cx, cy])
            if f > 0.02:
                amt = min(f, bite)
                self.fungus[cx, cy] -= amt
                gain += amt * 12
                self.feed("Fungi", sp.name, amt * 12)
        if "detritus" in diet:
            d = float(self.detritus[cx, cy])
            if d > 0.05:
                amt = min(d, bite)
                self.detritus[cx, cy] -= amt
                self.nutr[cx, cy] += amt * 0.3
                gain += amt * 7
                self.feed("Dead matter", sp.name, amt * 7)
        if "invert" in diet and not self.sea[cx, cy]:
            # worms, grubs, beetles and spiders: plentiful in moist soil with leaf litter
            g = bite * 22 * sp.invert_eff * min(1.0, float(self.detritus[cx, cy]) * 1.5 + float(self.moist[cx, cy]) * 0.4)
            gain += g
            self.feed("Insects & worms", sp.name, g)
        if "nectar" in diet and s >= 0 and self.p_flower[s] and self.pbio[cx, cy] > 0.25:
            gain += bite * 30
            self.feed("Nectar", sp.name, bite * 30)
            self.pollen[cx, cy] = min(1.0, self.pollen[cx, cy] + 0.3)
        st = self.struct[cx, cy]
        if st != NONE and not sp.native:
            if st == FIELD and diet & {"plant", "seed"}:
                gain += bite * 30
                self.feed("Crops & stores", sp.name, bite * 30)
                o = self.owner[cx, cy]
                if o >= 0:
                    self.tribes[o].food -= bite * 2           # pests eat the crops
            elif st == HOUSE and sp.commensal:
                gain += bite * 25
                self.feed("Crops & stores", sp.name, bite * 25)
                o = self.owner[cx, cy]
                if o >= 0:
                    self.tribes[o].food -= bite * 2
        if gain:
            a.energy = min(cap, a.energy + gain)
            self.nutr[cx, cy] += gain * 0.0004

    def neighbours(self, a, r, grid):
        gx0, gx1 = int(a.x - r) >> 3, int(a.x + r) >> 3
        gy0, gy1 = int(a.y - r) >> 3, int(a.y + r) >> 3
        for gx in range(gx0, gx1 + 1):
            for gy in range(gy0, gy1 + 1):
                lst = grid.get((gx, gy))
                if lst:
                    yield from lst

    def can_catch(self, pred, prey):
        if prey.sp is pred.sp or not prey.alive:
            return False
        psp = pred.sp
        juv = prey.young
        nest = psp.nest_raider and prey.sp.bird and juv
        if psp.prey is not None:
            if not (prey.sp.name in psp.prey or nest):
                return False
        elif "meat" in psp.diet:
            if not (pred.esize * 0.35 <= prey.esize <= pred.esize * 0.85 or nest):
                return False
        elif not nest:
            return False
        if prey.sp.flier and not psp.flier and not (psp.climber and (juv or not prey.awake)):
            return False
        if not psp.swimmer and not psp.flier and self.water[int(prey.x), int(prey.y)] > 0.3:
            return False
        if not psp.native and self.sanctuary[int(prey.x), int(prey.y)]:
            return False
        return True

    def think(self, a, cap, grid, counts, total):
        sp = a.sp
        water = self.water
        cx, cy = int(a.x), int(a.y)
        # 1. danger?
        if self.meat_eaters:
            r = sp.vision * 0.6
            best, bd = None, r * r
            for o in self.neighbours(a, r, grid):
                if o.awake and o.sp is not sp and self.can_catch(o, a):
                    if sp.naive and not o.sp.native:
                        continue                      # doesn't recognise mammals as danger
                    d2 = (o.x - a.x) ** 2 + (o.y - a.y) ** 2
                    if d2 < bd:
                        best, bd = o, d2
            if best is not None:
                dx, dy = a.x - best.x, a.y - best.y
                d = math.hypot(dx, dy) + 1e-6
                a.hx, a.hy = dx / d, dy / d
                a.tx = None
                a.prey = None
                a.flee = 8
                a.note = "fleeing from a %s!" % best.sp.name
                return None
        if self.any_people and not sp.naive:
            r = sp.vision * 0.5
            for gx in range(int(a.x - r) >> 3, (int(a.x + r) >> 3) + 1):
                for gy in range(int(a.y - r) >> 3, (int(a.y + r) >> 3) + 1):
                    for p in self.pgrid.get((gx, gy), ()):
                        dx, dy = a.x - p.x, a.y - p.y
                        if dx * dx + dy * dy < r * r:
                            d = math.hypot(dx, dy) + 1e-6
                            a.hx, a.hy = dx / d, dy / d
                            a.tx = None
                            a.flee = 8
                            a.note = "fleeing from people"
                            return None
        # 2. disease
        if a.sick:
            p = 0.12 * (1 + float(self.microbes[cx, cy]))
            for o in grid.get((cx >> 3, cy >> 3), ()):
                if o.sp is sp and not o.sick and random.random() < p:
                    if (o.x - a.x) ** 2 + (o.y - a.y) ** 2 < 4:
                        o.sick = True
        # 3. eat
        if a.energy < cap * 0.75:
            if "meat" in sp.diet or sp.nest_raider:
                r = sp.vision
                best, bs = None, 0.0
                for o in self.neighbours(a, r, grid):
                    if self.can_catch(a, o):
                        d = math.hypot(o.x - a.x, o.y - a.y)
                        if d < r:
                            sc = o.esize / (d + 1.0)
                            if sc > bs:
                                best, bs = o, sc
                if best is not None:
                    a.prey = best
                    a.tx = None
                    a.note = ("raiding a %s nest" % best.sp.name if best.young and best.sp.bird
                              and best.sp.name not in (sp.prey or ()) else "hunting a %s" % best.sp.name)
                    return None
            if sp.diet - {"meat"}:
                best, bv = None, max(0.05, self.food_value(sp, cx, cy) * 1.1)
                if bv > 0.06:
                    a.tx = None
                    a.note = "feeding"
                    return None
                vis = sp.vision
                for _ in range(7):
                    ang = random.random() * math.tau
                    rr = random.random() * vis
                    x = int(a.x + math.cos(ang) * rr)
                    y = int(a.y + math.sin(ang) * rr)
                    if 0 <= x < GW and 0 <= y < GH:
                        v = self.food_value(sp, x, y)
                        if v > bv:
                            best, bv = (x + 0.5, y + 0.5), v
                if best is not None:
                    a.tx, a.ty = best
                    a.prey = None
                    a.note = "heading for food"
                    return None
            a.note = "hungry - searching for food"
            return None
        a.prey = None
        a.note = "well fed - wandering"
        if a.tx is not None and random.random() < 0.3:
            a.tx = None
        # 4. breed
        if (a.cool <= 0 and a.energy > cap * 0.82 and not a.juvenile and
                counts.get(sp, 0) < POP_CAP and total < TOTAL_CAP):
            if sp.mast_breeder and self.mast <= 0:
                a.note = "ready to breed, but waiting for a mast year"
                return None
            carry = max(1, getattr(sp, "carry", 150)) * (1.0 if sp.native else diff(self, "pest_carry"))
            if getattr(sp, "mast_boom", False) and self.mast <= 0:
                carry *= 0.35
            if random.random() < counts.get(sp, 0) / carry:
                a.cool = sp.breed_gap * 0.5      # too crowded to breed right now
                a.note = "too crowded to breed (%d here, room for about %d)" % (counts.get(sp, 0), carry)
                return None
            if sp.breeds_in_water and water[cx, cy] < 0.02 and self.moist[cx, cy] < 0.9:
                for _ in range(6):
                    x = int(a.x + random.uniform(-sp.vision, sp.vision))
                    y = int(a.y + random.uniform(-sp.vision, sp.vision))
                    if 0 <= x < GW and 0 <= y < GH and water[x, y] > 0.05:
                        a.tx, a.ty = x + 0.5, y + 0.5
                        break
                a.note = "heading to water to breed"
                return None
            mut = 0.05 * self.settings["mutation"]
            kids = []
            a.cool = sp.breed_gap * random.uniform(0.85, 1.15)
            if sp.mast_breeder:
                a.cool = max(a.cool, self.mast + 10)           # one breeding attempt per mast
            x = sp.litter * random.uniform(0.7, 1.3) * diff(self, "native_breed" if sp.native else "pest_breed")
            n = int(x) + (1 if random.random() < x - int(x) else 0)
            if n == 0:
                a.energy -= cap * 0.15
                a.note = "bred, but no young survived (eggs failed or young died)"
                return None
            share = cap * 0.45
            a.energy -= share
            for _ in range(n):
                size = min(max(a.size * (1 + random.gauss(0, mut)), sp.size * 0.35), sp.size * 3)
                speed = min(max(a.speed * (1 + random.gauss(0, mut)), sp.speed * 0.35), sp.speed * 3)
                k = Animal(sp, min(max(a.x + random.uniform(-1, 1), 0), GW - 0.01),
                           min(max(a.y + random.uniform(-1, 1), 0), GH - 0.01),
                           size=size, speed=speed, gen=a.gen + 1, energy_frac=0, adult=False)
                k.energy = min(share / n * 1.1, 60 * size * 0.7)
                kids.append(k)
            counts[sp] = counts.get(sp, 0) + n
            a.note = "just had %d young" % n
            return kids
        return None

    # ------------------------------------------------------------ bookkeeping
    def step(self):
        self.update_weather()
        self.update_water()
        self.update_plants()
        self.update_decomposers()
        self.update_fire()
        if self.tick % 2 == 0:
            self.update_ocean()
        humans.update_humans(self)
        self.update_animals()
        if self.tick % 20 == 0:
            self.record()
        if self.tick % 240 == 0:
            self.migrate()
            self.diseases()
            k = math.exp(-240 / BIO_YEAR)          # the "recent" food web covers about one biological year
            for c in (self.web, self.web_n):
                for key in list(c):
                    v = c[key] * k
                    if v < 0.05:
                        del c[key]
                    else:
                        c[key] = v
        if self.tick % 60 == 0:
            self.assess()
        if self.tick % 120 == 0:
            alerts.check_alerts(self)
        if self.tick % DAY_TICKS == 0:
            self.death_days = (self.death_days + [self.deaths])[-3:]
            self.deaths = Counter()
            self.ploss_days = (self.ploss_days + [self.ploss])[-3:]
            self.ploss = Counter()
            self.erosion_days = (self.erosion_days + [self.erosion])[-2:]
            self.fish_days = (self.fish_days + [self.fish_caught])[-2:]
            self.fish_caught_recent = sum(self.fish_days)
            self.fish_caught = 0.0
            self.erosion_recent = sum(self.erosion_days)
            self.erosion = 0.0

    def record(self):
        self.plant_counts = np.bincount(self.pspec[self.pspec >= 0].astype(np.intp),
                                        minlength=len(self.plant_species))
        cells = GW * GH
        trees = int(sum(int(self.plant_counts[i]) for i, p in enumerate(self.plant_species) if p.tree))
        rec = {
            "animals": [self.counts.get(sp, 0) for sp in self.animal_species],
            "plants": [c / cells for c in self.plant_counts],
            "fungus": float((self.fungus > 0.1).mean()),
            "microbes": float(self.microbes.mean()),
            "temp": self.base_temp,
            "people": len(self.people),
            "fish": float(self.fish[self.sea].mean()) if self.sea.any() else 0.0,
            "shellfish": float(self.shellfish[self.shallow].mean()) if self.shallow.any() else 0.0,
            "trees": trees,
            "vitality": self.vitality,
            "pest_share": getattr(self, "pest_share", 0.0),
            "native_alive": getattr(self, "native_alive", 0),
        }
        if self.start_trees is None and trees:
            self.start_trees = trees
        self.history.append(rec)
        if self.tick % (CAL_DAY * 2) < 20:
            nat = sum(self.counts.get(sp, 0) for sp in self.animal_species if sp.native)
            pest = sum(self.counts.get(sp, 0) for sp in self.animal_species if not sp.native)
            self.long_history.append({"tick": self.tick, "date": self.stamp, "vitality": self.vitality,
                                      "natives": nat, "pests": pest, "people": len(self.people), "trees": trees,
                                      "fish": rec["fish"], "native_alive": rec["native_alive"],
                                      "species": {sp.name: self.counts.get(sp, 0) for sp in self.animal_species}})
            if len(self.long_history) > 3000:
                self.long_history = self.long_history[::2]
        self.peak_people = max(self.peak_people, len(self.people))
        if self.start_trees:
            for frac, lab in ((0.5, "half"), (0.25, "three-quarters")):
                if trees < self.start_trees * frac:
                    self.milestone("forest%s" % lab, "ecosystem", "%s of the forest is gone" % lab.capitalize(),
                                   "Tree cover has fallen to %d%% of what it was when the simulation began."
                                   % (100 * trees / self.start_trees), (200, 170, 120))
        if len(self.history) > 360:
            self.history = self.history[-360:]
        for sp in self.animal_species:
            n = self.counts.get(sp, 0)
            p = self.prev_counts.get(sp, 0)
            if p > 0 and n == 0:
                self.log("%s has died out." % sp.name, (255, 110, 110))
            self.prev_counts[sp] = n
        for i, sp in enumerate(self.plant_species):
            n = int(self.plant_counts[i])
            p = self.prev_plant.get(sp, 0)
            if p > 0 and n == 0:
                self.log("The last %s is gone." % sp.name, (255, 140, 110))
            self.prev_plant[sp] = n

    def random_land(self):
        for _ in range(100):
            x, y = random.randrange(GW), random.randrange(GH)
            if self.land[x, y] and self.water[x, y] < 0.2:
                return x, y
        return GW // 2, GH // 2

    def migrate(self):
        """Lost native species can only come back by themselves if they can fly or swim here
        from another island.  Flightless species (kiwi, kakapo, weta, takahe) are gone for good
        unless the player reintroduces them."""
        m = self.settings["migration"]
        if m <= 0:
            return
        for sp in self.animal_species:
            if not sp.native or self.counts.get(sp, 0) > 0 or not (sp.flier or sp.marine):
                continue
            if random.random() < 0.15 * m:
                if sp.marine:
                    xs, ys = np.nonzero(self.coast_sea)
                    if not len(xs):
                        continue
                    k = random.randrange(len(xs))
                    x, y = xs[k] + 0.5, ys[k] + 0.5
                else:
                    x, y = self.random_land()
                n = 2 if sp.size >= 1.0 else random.randint(3, 4)
                self.spawn_at(sp, x, y, n)
                alerts.alert_recolonise(self, sp, (x, y))
        for i, sp in enumerate(self.plant_species):
            if sp.native and i < len(self.plant_counts) and self.plant_counts[i] == 0 and random.random() < 0.4 * m:
                for _ in range(8):
                    x, y = self.random_land()
                    if self.pspec[x, y] < 0 and self.struct[x, y] == NONE:
                        self.pspec[x, y] = i
                        self.pbio[x, y] = 0.05
                self.log("Birds and wind carried %s seeds back in." % sp.name, sp.color)
        if self.fungus.sum() < 2:
            for _ in range(15):
                x, y = self.random_land()
                self.fungus[x, y] = 0.1

    def diseases(self):
        for sp in self.animal_species:
            n = self.counts.get(sp, 0)
            if n > POP_CAP * 0.55 and random.random() < 0.35:
                members = [a for a in self.animals if a.sp is sp]
                for a in random.sample(members, min(4, len(members))):
                    a.sick = True
                self.log("Disease is spreading through the crowded %s population." % sp.name,
                         (200, 230, 120), key="dis" + sp.name, cooldown_days=2)

    def assess(self):
        """The 'tamagotchi' layer: how is the world feeling?"""
        needs = []
        land = self.land & (self.water < 0.2)
        moist = float(self.moist[land].mean()) if land.any() else 0.5
        veg = float((self.pspec[self.land] >= 0).mean())
        fire = int((self.fire > 0).sum())
        T = self.base_temp
        natives = [sp for sp in self.animal_species + self.plant_species if sp.native]
        def alive(sp):
            if sp.kind == "animal":
                return self.counts.get(sp, 0) > 0
            i = self.plant_species.index(sp)
            return i < len(self.plant_counts) and self.plant_counts[i] > 0
        native_alive = sum(1 for sp in natives if alive(sp))
        pests = sum(self.counts.get(sp, 0) for sp in self.animal_species if not sp.native)
        nat_animals = sum(self.counts.get(sp, 0) for sp in self.animal_species if sp.native)
        pest_share = pests / max(1, pests + nat_animals)
        trees = sum(int(self.plant_counts[i]) for i, p in enumerate(self.plant_species)
                    if p.tree and i < len(self.plant_counts))
        forest = trees / max(1, int(self.land.sum()))

        parts = {}
        if moist < 0.17:
            needs.append(("Thirsty - the soil is drying out", (240, 190, 90))); parts["Drought"] = 15
        if fire > 80:
            needs.append(("On fire!", (255, 110, 60))); parts["Fire"] = 20
        if veg < 0.3:
            needs.append(("Barren - very little vegetation", (220, 180, 120))); parts["Bare land"] = 15
        if pest_share > 0.3:
            needs.append(("Overrun by introduced pests", (240, 150, 100)))
        if pest_share > 0.005:
            parts["Introduced pests"] = 50 * pest_share
        if forest < 0.15:
            needs.append(("Deforested", (200, 170, 120))); parts["Deforestation"] = 12
        if T < -3:
            needs.append(("Freezing", (160, 200, 255))); parts["Cold"] = 12
        if T > 30:
            needs.append(("Heatwave", (255, 130, 80))); parts["Heat"] = 12
        lost = (1 - native_alive / max(1, len(natives))) * 140
        if lost > 0:
            parts["Lost native species"] = lost
        score = max(0.0, min(100.0, 100.0 - sum(parts.values())))
        self.vital_parts = parts
        self.vitality += (score - self.vitality) * 0.15
        v = self.vitality
        self.mood = ("Flourishing" if v > 80 else "Content" if v > 62 else "Uneasy" if v > 45
                     else "Struggling" if v > 25 else "Dying")
        self.needs = needs
        self.native_alive = native_alive
        self.native_total = len(natives)
        self.forest = forest
        self.pest_share = pest_share
        # ecological collapse: no native animals left for 20 days, or the native land is gone
        native_cover = sum(int(self.plant_counts[i]) for i, p in enumerate(self.plant_species)
                           if p.native and i < len(self.plant_counts)) / max(1, int(self.land.sum()))
        land_nat = sum(self.counts.get(sp, 0) for sp in self.animal_species
                       if sp.native and not getattr(sp, "marine", False))
        flightless = [sp for sp in self.animal_species
                      if sp.native and not sp.flier and not getattr(sp, "marine", False)]
        flightless_gone = all(self.counts.get(sp, 0) == 0 for sp in flightless)
        if land_nat == 0:
            if self.no_native_since is None:
                self.no_native_since = self.tick
        else:
            self.no_native_since = None
        if not self.collapsed and self.elapsed > 10 * CAL_DAY and (
                (self.no_native_since is not None and self.tick - self.no_native_since > 20 * CAL_DAY) or
                (flightless_gone and native_cover < 0.15) or
                (native_cover < 0.02 and land_nat < 3)):
            self.collapsed = True
            self.collapse_tick = self.tick
            self.milestone("collapse", "extinction", "Ecological collapse",
                           "The native land wildlife is gone (or every flightless native species is extinct and "
                           "the native forest destroyed), and the ecosystem cannot recover on its own.", (240, 90, 80))

    # ---------------------------------------------------------- user actions
    def paint(self, tool, cx, cy, r, sel=None, mode=True):
        res = self.disc(cx, cy, r)
        if res is None:
            return
        (sx, sy), m = res
        m = m & self.land[sx, sy] if tool not in ("smite", "sanctuary") else m
        if tool == "water":
            self.water[sx, sy] += m * 0.25
        elif tool == "dry":
            self.water[sx, sy] *= np.where(m, 0.5, 1)
            self.moist[sx, sy] *= np.where(m, 0.85, 1)
            self.snow[sx, sy] *= np.where(m, 0.5, 1)
        elif tool == "fire":
            fz = self.fire[sx, sy]
            fz[m & (self.pbio[sx, sy] > 0.02)] = 1.0
            self.log("You started a fire.", (255, 160, 80), key="ufire", cooldown_days=0.5)
        elif tool == "fertilize":
            self.nutr[sx, sy] += m * 0.15
            self.detritus[sx, sy] += m * 0.1
        elif tool == "smite":
            self.pspec[sx, sy][m] = -1
            self.pbio[sx, sy][m] = 0
            self.fungus[sx, sy][m] = 0
            stv = self.struct[sx, sy]
            had_trap = (stv[m] == TRAP).any()
            stv[m] = NONE
            self.owner[sx, sy][m] = -1
            if had_trap:
                self.rebuild_traps()
            for a in self.animals:
                if (a.x - cx) ** 2 + (a.y - cy) ** 2 <= r * r:
                    self.kill_animal(a, "removed by you")
            self.animals = [a for a in self.animals if a.alive]
            humans.clear_people(self, cx, cy, r)
            self.count_species()
        elif tool == "trap":
            stv = self.struct[sx, sy]
            grid = ((self.X[sx, sy].astype(int) + self.Y[sx, sy].astype(int) * 3) % 4 == 0)
            place = m & grid & (stv == NONE) & (self.water[sx, sy] < 0.2)
            if place.any():
                stv[place] = TRAP
                self.rebuild_traps()
                self.milestone("first_trap", "conservation", "First pest traps set",
                               "Trapping introduced predators gives native wildlife a chance.", (240, 160, 80),
                               (cx, cy))
                self.log("You set pest traps.", (230, 160, 90), key="utrap", cooldown_days=0.5)
        elif tool == "sanctuary":
            sv = self.sanctuary[sx, sy]
            sv[m] = mode
            if mode:
                # people inside a new sanctuary move out, pests are swept out
                st = self.struct[sx, sy]
                st[m & ((st == HOUSE) | (st == FIELD) | (st == RUIN))] = NONE
                self.owner[sx, sy][m & (self.struct[sx, sy] == NONE)] = -1
                self.log("You fenced a predator-free sanctuary.", (120, 220, 200), key="usanct", cooldown_days=0.5)
                if (m & self.sea[sx, sy]).any():
                    self.milestone("first_marine", "conservation", "First marine reserve",
                                   "No fishing inside: fish and shellfish can recover.", (100, 190, 255), (cx, cy))
                if (m & self.land[sx, sy]).any():
                    self.milestone("first_sanct", "conservation", "First predator-proof sanctuary",
                                   "Introduced animals can't get in and people won't hunt or build inside.",
                                   (120, 220, 200), (cx, cy))
        elif tool == "species" and sel is not None:
            if sel.kind == "plant":
                i = self.plant_species.index(sel)
                ps = self.pspec[sx, sy]
                pb = self.pbio[sx, sy]
                st = self.struct[sx, sy]
                ok = m & (np.random.random(m.shape) < 0.5) & ((st == NONE) | (st == RUIN) | (st == TRAP))
                ps[ok] = i
                pb[ok] = np.maximum(pb[ok], 0.12)
            elif sel.kind == "fungus":
                f = self.fungus[sx, sy]
                f[m] = np.maximum(f[m], 0.4)
                self.detritus[sx, sy] += m * 0.05
            elif sel.kind == "microbe":
                mm = self.microbes[sx, sy]
                mm[m] = np.minimum(1, mm[m] + 0.3)

    def spawn_cloud(self, x, y):
        c = Cloud(x, y, random.uniform(10, 15), 260)
        c.age = 60
        c.raining = True
        self.clouds.append(c)
        self.log("You summoned a rain cloud.", (170, 200, 240), key="ucloud", cooldown_days=0.3)

    def animal_near(self, x, y, r=2.0):
        best, bd = None, r * r
        for a in self.animals:
            d = (a.x - x) ** 2 + (a.y - y) ** 2
            if d < bd:
                best, bd = a, d
        return best

    def person_near(self, x, y, r=2.0):
        best, bd = None, r * r
        for p in self.people:
            d = (p.x - x) ** 2 + (p.y - y) ** 2
            if d < bd:
                best, bd = p, d
        return best

    def species_mean(self, sp):
        xs = [(a.size, a.speed, a.gen) for a in self.animals if a.sp is sp]
        if not xs:
            return None
        n = len(xs)
        return (sum(x[0] for x in xs) / n, sum(x[1] for x in xs) / n, max(x[2] for x in xs))

    # ------------------------------------------------------------- saving
    def __getstate__(self):
        d = self.__dict__.copy()
        for k in ("grid", "pgrid", "X", "Y", "rng", "new_alerts"):
            d.pop(k, None)
        d["rng_state"] = self.rng.bit_generator.state
        return d

    def __setstate__(self, d):
        st = d.pop("rng_state", None)
        self.__dict__.update(d)
        self.rng = np.random.default_rng()
        if st:
            self.rng.bit_generator.state = st
        self.make_grids()
        self.grid = {}
        self.pgrid = {}
        self.new_alerts = []
        self.rebuild_tables()
