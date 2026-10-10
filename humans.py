"""
humans.py - people in Terrarium.

Humans are not ordinary animals.  They belong to tribes (fictional groups) that
share food and wood, build houses and fields, hunt, clear and burn forest, and
sometimes go to war with neighbouring tribes.  As settlements grow they bring
new species with them - rats, rabbits, cats, possums, deer, gorse, pines.
"""
import math
import random

import numpy as np

from config import BIO_YEAR, diff
from config import GW, GH, DAY_TICKS, CAL_DAY, YEAR_TICKS, age_text, HUMAN_CAP, NONE, HOUSE, FIELD, TRAP, RUIN, HOUSE_COST
from species_nz import tribe_name, TRIBE_COLORS


class Tribe:
    def __init__(self, tid, name, color, x, y, tick):
        self.id, self.name, self.color = tid, name, color
        self.x, self.y = x, y
        self.food = 45.0
        self.wood = 6.0
        self.pop = 0
        self.houses = 0
        self.fields = 0
        self.hostility = {}
        self.war = set()
        self.alive = True
        self.founded = tick
        self.aggression = random.uniform(0.2, 0.9)
        self.introduced = set()
        self.kills = 0
        self.children = 0
        self.births = 0
        self.peak = 0
        self.hungry = False
        self.relations_log = []      # (day, text)
        self.coastal = False
        self.fish_caught = 0.0
        self.stress = 0.15           # 0 = content, 1 = desperate
        self.stress_causes = []      # [(text, amount)]
        self.grief = 0.0
        self.recent_dead = 0
        self.site_reasons = []
        self.ship_cooldown = 0
        self.voyages = []            # (date, species, reason)


class Person:
    __slots__ = ("tribe", "x", "y", "hx", "hy", "age", "maxage", "role", "mode", "tx", "ty",
                 "target", "think", "alive", "work", "note", "sleeping")

    def __init__(self, tribe, x, y, age=None):
        self.tribe = tribe
        self.x, self.y = x, y
        a = random.random() * math.tau
        self.hx, self.hy = math.cos(a), math.sin(a)
        # adult life expectancy in a pre-industrial society: most adults die between 45 and 75
        self.maxage = random.uniform(45, 75) * BIO_YEAR
        self.age = age if age is not None else random.uniform(16, 40) * BIO_YEAR
        self.role = "gatherer"
        self.mode = None
        self.tx = self.ty = None
        self.target = None
        self.think = random.randint(0, 8)
        self.alive = True
        self.work = 0
        self.note = "just arrived"
        self.sleeping = False


def land_ok(w, x, y):
    return (0 <= x < GW and 0 <= y < GH and not w.sea[x, y] and w.water[x, y] < 0.12
            and not w.sanctuary[x, y])


# ----------------------------------------------------------------------------
def found_tribe(w, x, y, n=6):
    """Player drops people.  Close to an existing tribe = they join it."""
    if len(w.people) >= HUMAN_CAP:
        return None
    x = min(max(x, 1), GW - 2)
    y = min(max(y, 1), GH - 2)
    for t in w.tribes:
        if t.alive and math.hypot(t.x - x, t.y - y) < 10:
            add_people(w, t, x, y, n)
            w.log("%d more people joined the %s." % (n, t.name), t.color)
            return t
    tid = len(w.tribes)
    taken = {t.name for t in w.tribes}
    here, why_here = score_site(w, x, y)
    best = pick_site(w, x, y, 1, 12, tries=30)
    land_x, land_y = x, y
    if best and best[2] > here + 0.5:
        x, y, here, why_here = best
    t = Tribe(tid, tribe_name(taken), TRIBE_COLORS[tid % len(TRIBE_COLORS)], x, y, w.tick)
    t.founded_date = w.stamp
    t.site_reasons = why_here
    w.tribes.append(t)
    add_people(w, t, x, y, n)
    w.log("The %s arrived and made camp near %s." % (t.name, ", ".join(why_here[:3]) or "the shore"), t.color)
    w.milestone("first_people", "people", "First people arrive",
                "The %s land and make camp. People will change this island faster than anything before."
                % t.name, t.color, (x, y))
    w.milestone("clan:%d" % tid, "people", "The %s settle" % t.name,
                "Chose this place for %s." % (", ".join(why_here) or "no particular reason"), t.color, (x, y))
    from alerts import alert_settlers
    alert_settlers(w, t)
    # stowaways
    if random.random() < min(1.0, 0.6 * (1 - w.settings["biosecurity"]) * diff(w, "stowaway")):
        introduce(w, t, "Ship rat", 4)
    return t


def add_people(w, t, x, y, n):
    for _ in range(n):
        if len(w.people) >= HUMAN_CAP:
            break
        px = min(max(x + random.uniform(-2, 2), 0), GW - 0.01)
        py = min(max(y + random.uniform(-2, 2), 0), GH - 0.01)
        w.people.append(Person(t.id, px, py))
    t.pop = sum(1 for p in w.people if p.tribe == t.id and p.alive)


def score_site(w, x, y, exclude=None):
    """How attractive is (x, y) for a settlement?  Returns (score, [reasons])."""
    x, y = int(x), int(y)
    if not (0 <= x < GW and 0 <= y < GH) or not land_ok(w, x, y):
        return -99.0, ["not dry land"]
    s, why = 0.0, []

    def win(r):
        return slice(max(0, x - r), min(GW, x + r + 1)), slice(max(0, y - r), min(GH, y + r + 1))
    sx, sy = win(6)
    if ((w.water[sx, sy] > 0.05) & w.land[sx, sy]).any():
        s += 2
        why.append("fresh water")
    sx, sy = win(8)
    if w.coast_sea[sx, sy].any():
        s += 2
        why.append("the coast for fishing")
    ps = w.pspec[sx, sy]
    trees = int(np.isin(ps, [i for i, p in enumerate(w.plant_species) if p.tree]).sum())
    if trees > 6:
        s += min(2.0, trees / 20)
        why.append("forest for timber")
    sx, sy = win(4)
    if float(w.slope[sx, sy].mean()) < 0.3:
        s += 1
        why.append("flat land")
    if float(w.nutr[sx, sy].mean()) > 0.4:
        s += 1
        why.append("fertile soil")
    if w.height[x, y] > 0.58:
        s -= 3
        why.append("(but high and cold)")
    if x < 5 or y < 5 or x > GW - 6 or y > GH - 6:
        s -= 4                                  # cramped against the edge of the world
    near, nd = None, 999
    for o in w.tribes:
        if o.alive and o.id != exclude:
            d = math.hypot(o.x - x, o.y - y)
            if d < nd:
                near, nd = o, d
    if near is not None:
        if nd < 22:
            s -= (22 - nd) / 3
            why.append("(but close to the %s)" % near.name)
        elif nd < 50:
            s += 0.5
            why.append("space away from neighbours")
    return s, why


def pick_site(w, cx, cy, rmin, rmax, tries=30, exclude=None):
    best = None
    for _ in range(tries):
        a = random.random() * math.tau
        d = random.uniform(rmin, rmax)
        x, y = cx + math.cos(a) * d, cy + math.sin(a) * d
        sc, why = score_site(w, x, y, exclude)
        if sc > -50 and not land_path(w, cx, cy, x, y):
            sc -= 1.0                       # harder to reach overland
        if best is None or sc > best[2]:
            best = (int(x) + 0.5, int(y) + 0.5, sc, why)
    return best


def land_path(w, x0, y0, x1, y1):
    n = int(math.hypot(x1 - x0, y1 - y0)) + 1
    for i in range(n + 1):
        x = int(x0 + (x1 - x0) * i / n)
        y = int(y0 + (y1 - y0) * i / n)
        if 0 <= x < GW and 0 <= y < GH and (w.sea[x, y] or w.water[x, y] > 0.35):
            return False
    return True


def nearest_land(w, x, y, r=8):
    ix, iy = int(min(max(x, 0), GW - 1)), int(min(max(y, 0), GH - 1))
    if w.land[ix, iy] and w.water[ix, iy] < 0.3:
        return x, y
    for rr in range(1, r + 1):
        for _ in range(12):
            a = random.random() * math.tau
            nx, ny = int(ix + math.cos(a) * rr), int(iy + math.sin(a) * rr)
            if 0 <= nx < GW and 0 <= ny < GH and w.land[nx, ny] and w.water[nx, ny] < 0.3:
                return nx + 0.5, ny + 0.5
    return None


def introduce(w, t, name, n, at=None, reason=None):
    from alerts import alert_introduction
    if name in t.introduced:
        return
    t.introduced.add(name)
    sp = w.species_by_name(name)
    if sp is None:
        return
    ax, ay = at if at else (t.x, t.y)
    if sp.kind == "animal":
        for _ in range(n):
            spot = nearest_land(w, ax + random.uniform(-3, 3), ay + random.uniform(-3, 3))
            if spot:
                w.spawn_at(sp, spot[0], spot[1], 1)
    else:
        i = w.plant_species.index(sp)
        placed = 0
        for _ in range(n * 10):
            x = int(t.x + random.uniform(-10, 10))
            y = int(t.y + random.uniform(-10, 10))
            if land_ok(w, x, y) and w.struct[x, y] == NONE:
                w.pspec[x, y] = i
                w.pbio[x, y] = 0.3
                placed += 1
                if placed >= n:
                    break
    w.milestone("arrive:" + name, "arrival", "%s arrives" % name,
                reason or "Brought by the %s." % t.name, sp.color)
    alert_introduction(w, sp, t, reason)


# ----------------------------------------------------------------------------
def update_humans(w):
    if w.ships:
        update_ships(w)
    if not w.people:
        if w.tick % 240 == 0:
            tribe_bookkeeping(w)
        return
    rnd = random.random
    grid = {}
    for p in w.people:
        grid.setdefault((int(p.x) >> 3, int(p.y) >> 3), []).append(p)
    w.pgrid = grid
    night = w.sun_raw < 0.06
    tribes = w.tribes
    for p in w.people:
        if not p.alive:
            continue
        t = tribes[p.tribe]
        p.age += 1
        if p.age > p.maxage:
            kill_person(w, p, "old age")
            continue
        if p.age < ADULT:
            # children stay close to home and play; they work once they turn 16
            p.role = "child"
            p.sleeping = night
            if not night:
                p.think -= 1
                if p.think <= 0:
                    p.think = 20 + int(rnd() * 20)
                    p.tx, p.ty = t.x + random.uniform(-3, 3), t.y + random.uniform(-3, 3)
                    p.note = "playing near home (old enough to work in %d years)" % max(1, (ADULT - p.age) / BIO_YEAR)
                p.mode, p.target = None, None
                act(w, p, t)
            continue
        elif p.role == "child":
            p.role = "gatherer"
            p.think = 0
        if w.fire[int(p.x), int(p.y)] > 0.3 and rnd() < 0.01:
            kill_person(w, p, "fire")
            continue
        if night:
            awake = (p.role == "warrior" and t.war) or (p.role in ("hunter", "fisher") and t.hungry)
            if not awake:
                p.sleeping = True
                continue                     # asleep
        p.sleeping = False
        p.think -= 1
        if p.think <= 0:
            p.think = 8 + int(rnd() * 6)
            decide(w, p, t, grid)
        act(w, p, t)
    w.people = [p for p in w.people if p.alive]
    if w.tick % 60 == 0:
        economy(w)
    if w.tick % 240 == 0:
        tribe_bookkeeping(w)
        diplomacy(w)
        expansion(w)


ADULT = 16 * BIO_YEAR
# Real demography (pre-industrial):  a woman has a child about every 4 years between 16 and 45
# (~6 children), and roughly 40% of children die before adulthood.  With plenty of food this gives
# population growth of about 1-3% a year, as for the first settlers of Aotearoa.
BIRTHS_PER_WOMAN_YEAR = 0.24
CHILD_DEATH_YEAR = 0.032          # => ~40% die before 16


def is_child(p):
    return p.age < ADULT


def kill_person(w, p, cause):
    p.alive = False
    if 0 <= p.tribe < len(w.tribes) and cause != "old age":
        t = w.tribes[p.tribe]
        t.grief = min(1.0, t.grief + 0.08)
        t.recent_dead += 1
    x, y = int(p.x), int(p.y)
    w.detritus[x, y] += 0.4
    w.human_deaths[cause] = w.human_deaths.get(cause, 0) + 1


def house_ring(t):
    """Houses cluster in the village centre; fields ring around them."""
    return 1.5 + math.sqrt(t.houses + 1) * 1.25


def territory_radius(t):
    return 7 + math.sqrt(max(1, t.pop)) * 2.5 + math.sqrt(t.fields + t.houses) * 1.2


def decide(w, p, t, grid):
    p.mode = None
    p.target = None
    p.tx = None
    role = p.role
    R = territory_radius(t)
    if role == "warrior" and t.war:
        best, bd = None, 22 * 22
        for gx in range(int(p.x - 22) >> 3, (int(p.x + 22) >> 3) + 1):
            for gy in range(int(p.y - 22) >> 3, (int(p.y + 22) >> 3) + 1):
                for o in grid.get((gx, gy), ()):
                    if o.alive and o.tribe in t.war:
                        d2 = (o.x - p.x) ** 2 + (o.y - p.y) ** 2
                        if d2 < bd:
                            best, bd = o, d2
        if best is not None:
            p.mode, p.target = "fight", best
            p.note = "attacking a warrior of the %s" % w.tribes[best.tribe].name
            return
        enemy = w.tribes[random.choice(list(t.war))]
        for _ in range(20):
            x = int(enemy.x + random.uniform(-8, 8))
            y = int(enemy.y + random.uniform(-8, 8))
            if 0 <= x < GW and 0 <= y < GH and w.struct[x, y] == HOUSE and w.owner[x, y] == enemy.id:
                p.mode, p.tx, p.ty = "raid", x + 0.5, y + 0.5
                p.note = ("raiding the %s for food" % enemy.name if getattr(t, "scarcity", 0) > 0.4
                          else "raiding a house of the %s" % enemy.name)
                return
        p.mode, p.tx, p.ty = "march", enemy.x + random.uniform(-6, 6), enemy.y + random.uniform(-6, 6)
        p.note = "marching on the %s settlement" % enemy.name
        return
    if role == "hunter" and random.random() < min(1.0, max(0.25, 1.2 - food_days(t) / 8)):
        # hunters go out when the stores are low; with plenty stored they mostly gather instead
        best, bs = None, 0.0
        r = 16
        for gx in range(int(p.x - r) >> 3, (int(p.x + r) >> 3) + 1):
            for gy in range(int(p.y - r) >> 3, (int(p.y + r) >> 3) + 1):
                for a in w.grid.get((gx, gy), ()):
                    if not a.alive or a.esize < 0.3 or w.sanctuary[int(a.x), int(a.y)]:
                        continue
                    if a.sp.flier and a.awake:
                        continue
                    d = math.hypot(a.x - p.x, a.y - p.y)
                    if d < r:
                        sc = a.esize * (1.6 if a.sp.naive else 1.0) / (d + 2)
                        if sc > bs:
                            best, bs = a, sc
        if best is not None:
            p.mode, p.target = "hunt", best
            p.note = "stalking a %s" % best.sp.name
            return
    if role == "fisher":
        best, bv = None, 0.06
        for _ in range(12):
            x = int(p.x + random.uniform(-14, 14))
            y = int(p.y + random.uniform(-14, 14))
            if 0 <= x < GW and 0 <= y < GH and w.coast_sea[x, y] and not w.sanctuary[x, y]:
                v = float(w.fish[x, y]) + float(w.shellfish[x, y]) * 0.5
                if v > bv:
                    best, bv = (x, y), v
        if best:
            p.mode, p.tx, p.ty = "fish", best[0] + 0.5, best[1] + 0.5
            p.note = "fishing and gathering shellfish on the shore"
            return
        p.note = "found no fish nearby"
    if role in ("gatherer", "hunter", "fisher"):
        best, bv = None, 0.08
        for _ in range(8):
            x = int(p.x + random.uniform(-10, 10))
            y = int(p.y + random.uniform(-10, 10))
            if 0 <= x < GW and 0 <= y < GH and not w.sanctuary[x, y]:
                s = w.pspec[x, y]
                if s >= 0:
                    v = min(float(w.pbio[x, y]), 0.6) * w.p_edible[s]
                    if v > bv:
                        best, bv = (x, y), v
        if best:
            p.mode, p.tx, p.ty = "gather", best[0] + 0.5, best[1] + 0.5
            p.note = "gathering %s" % w.plant_species[w.pspec[best]].name
            return
    if role == "builder":
        if t.wood < HOUSE_COST:
            for _ in range(12):
                x = int(p.x + random.uniform(-14, 14))
                y = int(p.y + random.uniform(-14, 14))
                if 0 <= x < GW and 0 <= y < GH and not w.sanctuary[x, y]:
                    s = w.pspec[x, y]
                    if s >= 0 and (w.p_tree[s] or w.pt["maxb"][s] >= 1.0) and w.pbio[x, y] > 0.3:
                        p.mode, p.tx, p.ty = "chop", x + 0.5, y + 0.5
                        p.note = "felling a %s for timber" % w.plant_species[s].name
                        return
        else:
            rr = house_ring(t)
            for _ in range(20):
                a = random.random() * math.tau
                d = random.uniform(0.8, rr)
                x, y = int(t.x + math.cos(a) * d), int(t.y + math.sin(a) * d)
                if land_ok(w, x, y) and (w.struct[x, y] in (NONE, RUIN) or
                                         (w.struct[x, y] == FIELD and w.owner[x, y] == t.id and d < rr * 0.8)):
                    p.mode, p.tx, p.ty = "build", x + 0.5, y + 0.5
                    p.note = "building a new house in the village centre"
                    return
            p.note = "no room left to build near the village"
    if role == "farmer":
        if t.fields < t.pop * 1.3:
            r0 = house_ring(t) + 1.0
            rr = r0 + 1.5 + math.sqrt(t.fields + 1) * 1.6
            for _ in range(15):
                a = random.random() * math.tau
                d = random.uniform(r0, rr)
                x, y = int(t.x + math.cos(a) * d), int(t.y + math.sin(a) * d)
                if land_ok(w, x, y) and w.struct[x, y] == NONE and w.water[x, y] < 0.25 and w.slope[x, y] < 0.6:
                    p.mode, p.tx, p.ty = "field", x + 0.5, y + 0.5
                    p.note = "clearing land for a new field"
                    return
        for _ in range(8):
            x = int(t.x + random.uniform(-R, R))
            y = int(t.y + random.uniform(-R, R))
            if 0 <= x < GW and 0 <= y < GH and w.struct[x, y] == FIELD and w.owner[x, y] == t.id:
                p.mode, p.tx, p.ty = "tend", x + 0.5, y + 0.5
                p.note = "tending the crops"
                return
    # wander near home
    p.mode, p.tx, p.ty = "walk", t.x + random.uniform(-R * 0.6, R * 0.6), t.y + random.uniform(-R * 0.6, R * 0.6)
    if role == "warrior":
        p.note = "guarding the settlement"
    else:
        p.note = "looking for %s near home" % {"hunter": "game", "gatherer": "food plants", "builder": "trees",
                                               "farmer": "land to farm", "fisher": "fish"}.get(role, "work")


def act(w, p, t):
    spd = 0.2
    tx = ty = None
    tgt = p.target
    if tgt is not None:
        if not tgt.alive:
            p.target = None
            p.think = 0
            return
        tx, ty = tgt.x, tgt.y
        spd = 0.24
    elif p.tx is not None:
        tx, ty = p.tx, p.ty
    if tx is None:
        return
    dx, dy = tx - p.x, ty - p.y
    d = math.hypot(dx, dy)
    if d > 0.8:
        step = min(spd, d)
        nx, ny = p.x + dx / d * step, p.y + dy / d * step
        ix, iy = int(min(max(nx, 0), GW - 0.01)), int(min(max(ny, 0), GH - 0.01))
        if (w.water[ix, iy] > 0.35 or w.sea[ix, iy]) and not (p.mode == "fish" and w.coast_sea[ix, iy]):
            # detour
            a = random.random() * math.tau
            nx, ny = p.x + math.cos(a) * spd, p.y + math.sin(a) * spd
            ix, iy = int(min(max(nx, 0), GW - 0.01)), int(min(max(ny, 0), GH - 0.01))
            if w.water[ix, iy] > 0.35 or w.sea[ix, iy]:
                return
        p.x = min(max(nx, 0), GW - 0.01)
        p.y = min(max(ny, 0), GH - 0.01)
        return
    # arrived: do the job
    x, y = int(p.x), int(p.y)
    mode = p.mode
    if mode == "hunt":
        a = tgt
        chance = (0.55 if (a.sp.naive or not a.awake) else 0.25) * diff(w, "hunt")
        # the last few of a species are hard to find
        chance *= min(1.0, max(0.1, w.counts.get(a.sp, 0) / max(1.0, getattr(a.sp, "carry", 150) * 0.3)))
        if random.random() < chance:
            w.kill_animal(a, "hunted by humans")
            t.food += a.esize * 35
            t.kills += 1
        else:
            a.flee = 12
        p.target = None
        p.think = 4
    elif mode == "fight":
        o = tgt
        if random.random() < 0.3:
            kill_person(w, o, "battle")
            w.battle_deaths += 1
        elif random.random() < 0.2:
            kill_person(w, p, "battle")
            w.battle_deaths += 1
        p.target = None
        p.think = 3
    elif mode == "gather":
        s = w.pspec[x, y]
        if s >= 0 and w.pbio[x, y] > 0.02:
            amt = min(float(w.pbio[x, y]), 0.03)
            w.pbio[x, y] -= amt
            t.food += amt * 28 * w.p_edible[s]
            w.feed("Plants", "People", amt * 28 * w.p_edible[s])
            w.ploss["humans"] += amt
            p.work += 1
            if p.work > 12:
                p.work = 0
                p.think = 0
        else:
            p.think = 0
    elif mode == "chop":
        s = w.pspec[x, y]
        if s >= 0 and w.pbio[x, y] > 0.02:
            amt = min(float(w.pbio[x, y]), 0.06)
            w.pbio[x, y] -= amt
            t.wood += amt * 7
            w.ploss["humans"] += amt
            w.detritus[x, y] += amt * 0.2
            if w.pbio[x, y] < 0.02:
                w.pspec[x, y] = -1
                w.pbio[x, y] = 0
                p.think = 0
        else:
            p.think = 0
    elif mode == "build":
        own_field = w.struct[x, y] == FIELD and w.owner[x, y] == t.id
        if (w.struct[x, y] in (NONE, RUIN) or own_field) and t.wood >= HOUSE_COST and land_ok(w, x, y):
            if own_field:
                t.fields = max(0, t.fields - 1)
            w.ploss["humans"] += float(w.pbio[x, y])
            w.struct[x, y] = HOUSE
            w.owner[x, y] = t.id
            w.pspec[x, y] = -1
            w.pbio[x, y] = 0
            t.wood -= HOUSE_COST
            t.houses += 1
            w.cleared_cells += 1
            w.milestone("first_house", "people", "First house built",
                        "The %s build the island's first house from felled trees." % t.name, t.color, (x, y))
        p.mode = None
        p.tx = None
        p.think = 2
    elif mode == "field":
        if w.struct[x, y] == NONE and land_ok(w, x, y):
            w.ploss["humans"] += float(w.pbio[x, y])
            w.struct[x, y] = FIELD
            w.owner[x, y] = t.id
            w.pspec[x, y] = -1
            w.pbio[x, y] = 0
            # draining: neighbouring wet ground is ditched
            x0, x1, y0, y1 = max(0, x - 1), min(GW, x + 2), max(0, y - 1), min(GH, y + 2)
            wet = float(w.water[x0:x1, y0:y1].sum())
            if wet > 0.05:
                w.drained += wet
            w.water[x0:x1, y0:y1] *= 0.3
            w.moist[x, y] = min(w.moist[x, y], 0.6)
            t.fields += 1
            w.cleared_cells += 1
            w.milestone("first_field", "people", "First forest cleared for farming",
                        "The %s clear and plant the first field. Farmland will slowly replace forest." % t.name,
                        t.color, (x, y))
        p.mode = None
        p.tx = None
        p.think = 2
    elif mode == "fish":
        x0, x1, y0, y1 = max(0, x - 1), min(GW, x + 2), max(0, y - 1), min(GH, y + 2)
        fz = w.fish[x0:x1, y0:y1]
        sh = w.shellfish[x0:x1, y0:y1]
        ok = ~w.sanctuary[x0:x1, y0:y1]
        catch = np.minimum(fz, 0.012) * ok
        shell = np.minimum(sh, 0.006) * ok
        fz -= catch
        sh -= shell
        got = float(catch.sum() + shell.sum())
        t.food += got * 30
        w.feed("Fish", "People", got * 30)
        t.fish_caught += got
        w.fish_caught += got
        p.work += 1
        if p.work > 15 or got < 0.002:
            p.work = 0
            p.think = 0
    elif mode == "tend":
        if w.struct[x, y] == FIELD:
            t.food += 0.006
    elif mode == "raid":
        if w.struct[x, y] == HOUSE and w.owner[x, y] in t.war:
            enemy = w.tribes[int(w.owner[x, y])]
            w.struct[x, y] = RUIN
            w.owner[x, y] = -1
            enemy.houses = max(0, enemy.houses - 1)
            loot = min(enemy.food, 12.0)
            enemy.food -= loot
            t.food += loot
            if random.random() < 0.4:
                w.fire[x, y] = 1.0
            w.log("Warriors of the %s burned a house of the %s." % (t.name, enemy.name), (255, 150, 90),
                  key="raid%d%d" % (t.id, enemy.id), cooldown_days=0.5)
        p.mode = None
        p.tx = None
        p.think = 2
    else:
        p.think = min(p.think, 3)


# ----------------------------------------------------------------------------
def economy(w):
    """Every 60 ticks: farming, eating, births, starvation, jobs."""
    tribes = [t for t in w.tribes if t.alive]
    if not tribes:
        return
    fields = (w.struct == FIELD) & (w.owner >= 0)
    if fields.any():
        tf = np.exp(-((w.temp - 16) / 9) ** 2)
        nf = np.clip(w.nutr / 0.35, 0.08, 1)
        wf = np.clip(w.moist / 0.2, 0.2, 1)
        yld = fields * 0.25 * tf * nf * wf
        per = np.bincount(w.owner[fields].astype(np.intp), weights=yld[fields], minlength=len(w.tribes))
        for t in tribes:
            if t.id < len(per):
                t.food += float(per[t.id])
                if per[t.id] > 0:
                    w.feed("Crops & stores", "People", float(per[t.id]))
        w.nutr[fields] = np.maximum(w.nutr[fields] - 0.0025, 0)     # crops mine the soil
    members = {}
    for p in w.people:
        members.setdefault(p.tribe, []).append(p)
    for t in tribes:
        ms = members.get(t.id, [])
        t.pop = len(ms)
        t.peak = max(t.peak, t.pop)
        if t.pop == 0:
            continue
        kids = [p for p in ms if p.age < ADULT]
        t.children = len(kids)
        t.food -= (t.pop - 0.4 * len(kids)) * 0.36          # children eat a bit over half as much
        t.food = min(t.food * 0.997, t.pop * 40 + 40)
        update_stress(w, t)
        cap = t.houses * 5 + 6
        yr = 60 / BIO_YEAR                                  # this check covers 60 ticks of biological time
        # childhood deaths (worse when hungry)
        for k in kids:
            if random.random() < CHILD_DEATH_YEAR * yr * (3 if t.hungry else 1):
                kill_person(w, k, "childhood illness")
        women = sum(1 for p in ms if ADULT <= p.age < 45 * BIO_YEAR) * 0.5
        food_ok = min(1.0, max(0.0, t.food / max(1.0, t.pop * 6)))
        rate = BIRTHS_PER_WOMAN_YEAR * women * yr * food_ok * max(0.0, 1.1 - t.stress) * diff(w, "human_growth")
        if t.pop < cap and len(w.people) < HUMAN_CAP and random.random() < rate:
            p = Person(t.id, t.x + random.uniform(-2, 2), t.y + random.uniform(-2, 2), age=0)
            p.role = "child"
            p.note = "a newborn baby"
            w.people.append(p)
            ms.append(p)
            t.births = getattr(t, "births", 0) + 1
            t.pop = len(ms)
        ms = [p for p in ms if p.alive]
        t.pop = len(ms)
        t.hungry = t.food <= 0
        if t.food <= 0:
            t.food = 0
            if random.random() < 0.3 and ms:
                victim = random.choice(ms)
                kill_person(w, victim, "famine")
                w.milestone("first_famine", "people", "First famine",
                            "The %s run out of food and people starve." % t.name, t.color, (t.x, t.y))
                for o in t.hostility:
                    t.hostility[o] = t.hostility.get(o, 0) + 0.05
                from alerts import alert_famine
                alert_famine(w, t)
        assign_roles(t, [p for p in ms if p.alive and p.age >= ADULT])
    total = len(w.people)
    for n in (50, 100, 200):
        if total >= n:
            w.milestone("pop%d" % n, "people", "%d people live on the island" % n, "", (235, 200, 160))


def update_stress(w, t):
    """Clan wellbeing: war, hunger, winter worries, crowding and grief raise stress."""
    causes = []
    fd = food_days(t)
    if t.hungry:
        causes.append(("starving", 0.45))
    elif fd < 2:
        causes.append(("food running low", 0.2))
    season = w.season
    if season == "Winter" and fd < 6:
        causes.append(("worried about winter supplies", 0.2))
    elif season == "Autumn" and fd < 4:
        causes.append(("anxious to store food before winter", 0.1))
    if t.war:
        causes.append(("at war with the %s" % ", ".join(w.tribes[i].name for i in t.war), 0.3))
    if t.pop > t.houses * 4 + 2:
        causes.append(("overcrowded - not enough houses", 0.1))
    if t.grief > 0.05:
        causes.append(("grieving %d dead" % max(1, t.recent_dead), min(0.3, t.grief)))
    if w.base_temp < 4:
        causes.append(("bitter cold", 0.06))
    if fd > 8 and not t.war:
        causes.append(("well fed", -0.1))
    if t.houses * 4 >= t.pop + 4:
        causes.append(("comfortable homes", -0.05))
    target = min(1.0, max(0.0, 0.12 + sum(a for _, a in causes)))
    t.stress += (target - t.stress) * 0.3
    # scarcity breeds aggression
    scarcity = min(1.0, max(0.0, 1 - fd / 4))
    t.scarcity = scarcity
    t.aggr_now = min(1.0, (t.aggression * 0.6 + 0.5 * scarcity + 0.25 * t.stress) * diff(w, "aggression"))
    t.stress_causes = causes
    t.grief *= 0.92
    if t.grief < 0.03:
        t.recent_dead = 0


def mood_label(stress):
    return ("Content" if stress < 0.2 else "Settled" if stress < 0.4 else "Stressed" if stress < 0.6
            else "Distressed" if stress < 0.8 else "Desperate")


def person_stress(w, p):
    t = w.tribes[p.tribe]
    s = t.stress + ((p.maxage // 7) % 100 / 100 - 0.5) * 0.15
    if p.role == "warrior" and t.war:
        s += 0.15
    if not p.sleeping and w.sun_raw < 0.06:
        s += 0.05
    return min(1.0, max(0.0, s))


def assign_roles(t, ms):
    n = len(ms)
    if n == 0:
        return
    roles = []
    if t.war:
        roles += ["warrior"] * max(1, int(math.ceil(n * 0.35)))
    if t.pop >= t.houses * 4 - 1 or t.wood < HOUSE_COST:
        roles += ["builder"] * max(1, int(round(n * 0.2)))
    if n >= 6:
        roles += ["farmer"] * int(round(n * 0.3))
    rest = n - len(roles)
    if rest > 0 and t.coastal:
        f = int(round(rest * 0.35))
        roles += ["fisher"] * f
        rest -= f
    if rest > 0:
        h = int(round(rest * 0.55))
        roles += ["hunter"] * h + ["gatherer"] * (rest - h)
    roles = roles[:n]
    # keep people in the same job where possible
    want = {}
    for r in roles:
        want[r] = want.get(r, 0) + 1
    unassigned = []
    for p in ms:
        if want.get(p.role, 0) > 0:
            want[p.role] -= 1
        else:
            unassigned.append(p)
    pool = [r for r, k in want.items() for _ in range(k)]
    for p, r in zip(unassigned, pool):
        p.role = r
        p.think = 0


def tribe_bookkeeping(w):
    if not w.tribes:
        return
    w.struct[(w.owner < 0) & (w.struct == FIELD)] = NONE        # orphaned fields go fallow
    w.struct[(w.owner < 0) & (w.struct == HOUSE)] = RUIN        # ownerless houses fall into ruin
    houses = w.struct == HOUSE
    fields = w.struct == FIELD
    hc = np.bincount(w.owner[houses].astype(np.intp), minlength=len(w.tribes)) if houses.any() else None
    fc = np.bincount(w.owner[fields].astype(np.intp), minlength=len(w.tribes)) if fields.any() else None
    counts = {}
    for p in w.people:
        counts[p.tribe] = counts.get(p.tribe, 0) + 1
    for t in w.tribes:
        if not t.alive:
            continue
        t.houses = int(hc[t.id]) if hc is not None and t.id < len(hc) else 0
        t.fields = int(fc[t.id]) if fc is not None and t.id < len(fc) else 0
        t.pop = counts.get(t.id, 0)
        x0, x1 = max(0, int(t.x) - 14), min(GW, int(t.x) + 15)
        y0, y1 = max(0, int(t.y) - 14), min(GH, int(t.y) + 15)
        t.coastal = bool(w.coast_sea[x0:x1, y0:y1].any())
        if t.pop == 0:
            t.alive = False
            mine = w.owner == t.id
            w.struct[mine & (w.struct == HOUSE)] = RUIN
            w.struct[mine & (w.struct == FIELD)] = NONE
            w.owner[mine] = -1
            for o in w.tribes:
                o.war.discard(t.id)
            w.log("The %s are gone. Their abandoned land slowly returns to nature." % t.name, (200, 180, 160))
            w.milestone("gone:%d" % t.id, "people", "The %s disappear" % t.name,
                        "Their last members died or left. Peak population %d." % t.peak, (200, 180, 160))
        else:
            # drift the centre towards the houses
            if houses.any():
                xs, ys = np.nonzero(houses & (w.owner == t.id))
                if len(xs):
                    t.x = t.x * 0.7 + float(xs.mean()) * 0.3
                    t.y = t.y * 0.7 + float(ys.mean()) * 0.3


def diplomacy(w):
    from alerts import alert_war, alert_peace
    live = [t for t in w.tribes if t.alive]
    for i, a in enumerate(live):
        for b in live[i + 1:]:
            d = math.hypot(a.x - b.x, a.y - b.y)
            h = a.hostility.get(b.id, 0.0)
            if d < 55:
                pressure = 1 - d / 55
                sa, sb = getattr(a, "scarcity", 0.0), getattr(b, "scarcity", 0.0)
                aggr = (getattr(a, "aggr_now", a.aggression) + getattr(b, "aggr_now", b.aggression)) / 2
                overlap = d < territory_radius(a) + territory_radius(b)
                crowd = min(1.0, (a.pop + b.pop) / 40)           # small, new settlements rarely fight
                h += 0.012 * pressure * (0.4 + aggr) * crowd
                h -= 0.01                                        # old grudges fade
                h += 0.07 * pressure * (sa + sb)                 # hungry clans fight over resources
                h += 0.035 * overlap * crowd                     # competing for the same land
                if (sa > 0.6 or sb > 0.6) and h > 0.6 and b.id not in a.war:
                    hungry = a if sa >= sb else b
                    other = b if hungry is a else a
                    for tr in (a, b):
                        tr.relations_log.append((w.stamp, "tension rising: the %s are hungry and eye the %s's land"
                                                 % (hungry.name, other.name)))
                        tr.relations_log = tr.relations_log[-12:]
                h += 0.02 * pressure * min(1.0, (a.pop + b.pop) / 40)
                h += 0.03 * pressure * (a.stress + b.stress)
            else:
                h -= 0.03
            at_war = b.id in a.war
            if at_war:
                h -= 0.045
                if h < 0.35 or a.pop < 3 or b.pop < 3:
                    a.war.discard(b.id)
                    b.war.discard(a.id)
                    a.relations_log.append((w.stamp, "made peace with the %s" % b.name))
                    b.relations_log.append((w.stamp, "made peace with the %s" % a.name))
                    alert_peace(w, a, b)
            elif h > 1.15 and a.pop >= 4 and b.pop >= 4:
                a.war.add(b.id)
                b.war.add(a.id)
                why = ("food - hunger drove them to fight" if (getattr(a, "scarcity", 0) > 0.5 or
                                                               getattr(b, "scarcity", 0) > 0.5)
                       else "land - their territories overlap" if d < territory_radius(a) + territory_radius(b)
                       else "rivalry between close neighbours")
                a.relations_log.append((w.stamp, "went to war with the %s (%s)" % (b.name, why)))
                b.relations_log.append((w.stamp, "went to war with the %s (%s)" % (a.name, why)))
                w.milestone("first_war", "war", "First war",
                            "The %s and the %s go to war over %s." % (a.name, b.name, why), (240, 100, 90),
                            ((a.x + b.x) / 2, (a.y + b.y) / 2))
                w.milestone("war:%d:%d:%d" % (a.id, b.id, w.tick), "war", "%s vs %s" % (a.name, b.name),
                            "War breaks out (%s)." % why, (240, 100, 90))
                alert_war(w, a, b)
            h = max(0.0, min(2.0, h))
            a.hostility[b.id] = h
            b.hostility[a.id] = h


def expansion(w):
    """Clearing fires, settlement splits and species introductions."""
    from alerts import alert_burning
    bio = w.settings["biosecurity"]
    risk = 1 - bio
    rnd = random.random
    for t in list(w.tribes):
        if not t.alive or t.pop == 0:
            continue
        # burning forest to open land
        if t.pop >= 12 and t.fields < t.pop * 1.3 and rnd() < 0.12:
            for _ in range(25):
                a = rnd() * math.tau
                d = random.uniform(6, 16)
                x, y = int(t.x + math.cos(a) * d), int(t.y + math.sin(a) * d)
                if 0 <= x < GW and 0 <= y < GH and not w.sanctuary[x, y] and w.pbio[x, y] > 0.5 \
                        and w.moist[x, y] < 0.6 and w.water[x, y] < 0.03:
                    w.fire[x, y] = 1.0
                    alert_burning(w, t, x, y)
                    break
        # a group leaves to found a new settlement - because it's crowded, or to escape stress
        crowded = t.pop > 28
        unhappy = t.stress > 0.55 and t.pop >= 12
        if (crowded and rnd() < 0.25) or (unhappy and rnd() < 0.12):
            best = pick_site(w, t.x, t.y, 22, 50, tries=40, exclude=t.id)
            if best and best[2] > 1.0:
                x, y, sc, why = best
                ms = [p for p in w.people if p.tribe == t.id]
                random.shuffle(ms)
                tid = len(w.tribes)
                nt = Tribe(tid, tribe_name({o.name for o in w.tribes}), TRIBE_COLORS[tid % len(TRIBE_COLORS)],
                           x, y, w.tick)
                nt.food = 30
                nt.founded_date = w.stamp
                nt.introduced = set(t.introduced)
                nt.site_reasons = why
                w.tribes.append(nt)
                for p in ms[:7]:
                    p.tribe = tid
                    p.target = None
                    p.tx = None
                    p.think = 0
                    spot = nearest_land(w, x + random.uniform(-2, 2), y + random.uniform(-2, 2))
                    if spot:
                        p.x, p.y = spot          # they travel to the new site (on foot or by canoe)
                t.food *= 0.8
                nt.hostility[t.id] = t.hostility[tid] = 0.15
                motive = "the village was crowded" if crowded else "life had become too hard (%s)" % (
                    ", ".join(c for c, a in t.stress_causes if a > 0)[:60] or "stress")
                w.log("A group left the %s because %s, and founded the %s." % (t.name, motive, nt.name), nt.color)
                w.milestone("clan:%d" % tid, "people", "The %s split from the %s" % (nt.name, t.name),
                            "They left because %s, choosing a site with %s." % (motive, ", ".join(why[:4])),
                            nt.color, (x, y))
        # sending a ship to fetch new species
        t.ship_cooldown -= 240
        if t.ship_cooldown <= 0 and t.coastal and t.pop >= 12 and not any(s.tribe == t.id for s in w.ships):
            plan = plan_voyage(w, t)
            if plan and rnd() < 0.35 * (1 - 0.8 * bio) * diff(w, "voyages"):
                launch_ship(w, t, *plan)
                t.ship_cooldown = 25 * CAL_DAY


def plan_voyage(w, t):
    """Pick an introduced species that would 'solve' one of the clan's current problems."""
    def count(name):
        sp = w.species_by_name(name)
        return w.counts.get(sp, 0) if sp else 0
    R = territory_radius(t) * 1.5
    rat = w.species_by_name("Ship rat")
    rats_near = sum(1 for a in w.animals if a.sp is rat and abs(a.x - t.x) < R and abs(a.y - t.y) < R) if rat else 0
    game = sum(w.counts.get(sp, 0) for sp in w.animal_species if sp.native and sp.naive and sp.size >= 1.0)
    options = []
    if rats_near > 8:
        options.append(("Feral cat", "Rats were raiding their food stores, so the %s sent a ship to fetch cats to hunt them."))
    if count("Rabbit") > 40:
        options.append(("Stoat", "Rabbits were eating their crops, so the %s fetched stoats to control them."))
    if (t.hungry or food_days(t) < 3) and game < 20:
        options.append(("Rabbit", "Their hunters had emptied the land of big birds, so the %s fetched rabbits - "
                                  "a fast-breeding source of meat."))
        options.append(("Red deer", "Game was scarce, so the %s brought deer to hunt."))
    x0, x1 = max(0, int(t.x) - 14), min(GW, int(t.x) + 15)
    y0, y1 = max(0, int(t.y) - 14), min(GH, int(t.y) + 15)
    trees = int(np.isin(w.pspec[x0:x1, y0:y1], [i for i, p in enumerate(w.plant_species) if p.tree]).sum())
    if t.wood < HOUSE_COST and trees < 40:
        options.append(("Wilding pine", "Nearby forest was running out and they needed timber, so the %s planted "
                                        "fast-growing pines."))
    elif t.pop >= 22:
        options.append(("Wilding pine", "The growing town wanted a steady supply of timber, so the %s started a "
                                        "pine plantation."))
    if t.fields >= 8 or (t.pop >= 16 and t.fields >= 5):
        options.append(("Gorse", "The %s wanted hedges to shelter and fence their growing fields, so they brought gorse."))
    if food_days(t) > 6 and t.pop >= 18 and not t.war:
        options.append(("Possum", "Comfortable and well fed, the %s started a fur trade and brought possums."))
    for name, why in options:
        if name in t.introduced:
            continue
        sp = w.species_by_name(name)
        if sp is None or (sp.kind == "animal" and count(name) > 30):
            continue
        return name, why % t.name
    return None


class Ship:
    __slots__ = ("tribe", "x", "y", "hx", "hy", "state", "timer", "cargo", "reason", "home", "exit")

    def __init__(self, tribe, x, y, cargo, reason):
        self.tribe, self.x, self.y = tribe, x, y
        self.cargo, self.reason = cargo, reason
        self.home = (x, y)
        self.state = "outbound"
        self.timer = 0
        self.exit = None
        self.hx = self.hy = 0.0


def launch_ship(w, t, cargo, reason):
    from alerts import alert_voyage
    xs, ys = np.nonzero(w.coast_sea)
    if not len(xs):
        return
    d = (xs - t.x) ** 2 + (ys - t.y) ** 2
    k = int(np.argmin(d))
    if d[k] > 20 ** 2:
        return
    s = Ship(t.id, xs[k] + 0.5, ys[k] + 0.5, cargo, reason)
    # head for the nearest edge of the map
    edges = [(s.x, (-1, 0)), (GW - s.x, (1, 0)), (s.y, (0, -1)), (GH - s.y, (0, 1))]
    _, (dx, dy) = min(edges, key=lambda e: e[0])
    s.hx, s.hy = dx, dy
    w.ships.append(s)
    t.voyages.append((w.stamp, cargo, reason))
    w.milestone("first_ship", "people", "First voyage off the island",
                "The %s send a ship away to bring back %s." % (t.name, cargo), t.color, (s.x, s.y))
    alert_voyage(w, t, s)


def steer(w, s, tx, ty, spd=0.35):
    dx, dy = tx - s.x, ty - s.y
    d = math.hypot(dx, dy) + 1e-6
    base = math.atan2(dy, dx)
    for off in (0, 0.5, -0.5, 1.0, -1.0, 1.5, -1.5, 2.2, -2.2):
        a = base + off
        nx, ny = s.x + math.cos(a) * spd, s.y + math.sin(a) * spd
        ix, iy = int(nx), int(ny)
        if not (0 <= ix < GW and 0 <= iy < GH) or w.sea[ix, iy] or w.coast_sea[ix, iy]:
            s.x, s.y, s.hx, s.hy = nx, ny, math.cos(a), math.sin(a)
            return d
    return d


def update_ships(w):
    keep = []
    for s in w.ships:
        t = w.tribes[s.tribe]
        if s.state == "outbound":
            tx, ty = s.x + s.hx * 30, s.y + s.hy * 30
            steer(w, s, tx, ty)
            if s.x < -1 or s.x > GW + 1 or s.y < -1 or s.y > GH + 1:
                s.state = "away"
                s.exit = (min(max(s.x, 0.5), GW - 0.5), min(max(s.y, 0.5), GH - 0.5))
                s.timer = random.randint(10, 20) * CAL_DAY
        elif s.state == "away":
            s.timer -= 1
            if s.timer <= 0:
                if not t.alive:
                    continue
                s.state = "returning"
                s.x, s.y = s.exit
        elif s.state == "returning":
            d = steer(w, s, s.home[0], s.home[1])
            if d < 1.2:
                n = {"Wilding pine": 12, "Gorse": 12, "Red deer": 4, "Rabbit": 6, "Feral cat": 3, "Stoat": 4,
                     "Possum": 4}.get(s.cargo, 4)
                bio = w.settings["biosecurity"]
                if random.random() < bio * 0.85:
                    # border biosecurity inspects the ship and refuses to let the species ashore
                    t.introduced.add(s.cargo)
                    w.log("Biosecurity stopped the %s ship: its cargo of %s was not allowed ashore." % (t.name, s.cargo),
                          (120, 220, 200))
                    w.milestone("biosec:%s:%d" % (s.cargo, w.tick), "conservation",
                                "Biosecurity stops %s" % s.cargo,
                                "The %s wanted %s, but border checks kept them out." % (t.name, s.cargo),
                                (120, 220, 200), s.home)
                    continue
                introduce(w, t, s.cargo, n, at=s.home, reason=s.reason)
                if random.random() < 0.5 * (1 - w.settings["biosecurity"]) * diff(w, "stowaway"):
                    rat = w.species_by_name("Ship rat")
                    spot = nearest_land(w, s.home[0], s.home[1])
                    if rat and spot:
                        w.spawn_at(rat, spot[0], spot[1], 3)
                        w.log("Stowaway rats came ashore from the %s ship." % t.name, (180, 180, 180))
                continue
        keep.append(s)
    w.ships = keep


def clear_people(w, cx, cy, r):
    n = 0
    for p in w.people:
        if (p.x - cx) ** 2 + (p.y - cy) ** 2 <= r * r:
            p.alive = False
            n += 1
    if n:
        w.people = [p for p in w.people if p.alive]
        w.log("%d people abandoned the area and left." % n, (200, 190, 180))


# ----------------------------------------------------------------------------
# explanations for the UI
# ----------------------------------------------------------------------------
def relation(w, a, b):
    """(label, colour) for how tribe a sees tribe b."""
    if b.id in a.war:
        return "AT WAR", (240, 100, 90)
    hv = a.hostility.get(b.id, 0.0)
    if hv > 0.7:
        return "Tense", (240, 170, 90)
    if hv > 0.35:
        return "Wary", (230, 210, 120)
    return "At peace", (126, 206, 146)


def food_days(t):
    return t.food / max(0.1, t.pop * 0.36 * 12)


ROLE_WHY = {
    "warrior": "fights for the clan while it is at war",
    "builder": "cuts timber and builds houses so the clan can grow",
    "farmer": "clears and tends fields - steady food, but crops wear out the soil",
    "hunter": "hunts animals for meat - flightless birds that never learned to fear people are easiest",
    "gatherer": "gathers edible plants between hunts",
    "fisher": "fishes and collects shellfish along the coast",
    "child": "too young to work; children are looked after by the clan until they turn 16",
}


def describe_person(w, p):
    """Return (headline, [reason lines]) explaining what a person is doing and why."""
    t = w.tribes[p.tribe]
    night = w.sun_raw < 0.06
    lines = []
    if p.sleeping:
        head = "Asleep"
        lines.append("Most people rest at night. Only warriors of clans at war, and hunters or fishers of "
                     "starving clans, stay up after dark.")
    else:
        head = p.note[0].upper() + p.note[1:] if p.note else "Idle"
        if night:
            if p.role == "warrior":
                lines.append("Awake at night: the %s are at war, so warriors keep watch and raid while their "
                             "enemies sleep." % t.name)
            elif t.hungry:
                lines.append("Working at night: the clan has run out of food, so hunters and fishers keep going "
                             "after dark.")
    ps = person_stress(w, p)
    worries = [c for c, a in t.stress_causes if a > 0]
    lines.append("Wellbeing %d%% (%s)%s." % (100 * (1 - ps), mood_label(ps).lower(),
                                            (" - " + ", ".join(worries[:3])) if worries else ""))
    lines.append("Role: %s - %s." % (p.role, ROLE_WHY.get(p.role, "")))
    if p.role == "warrior" and t.war:
        lines.append("At war with: %s." % ", ".join(w.tribes[i].name for i in t.war))
    elif p.role == "builder":
        lines.append("The clan has %d houses for %d people (room for 4 each) and %.0f wood (a house costs %d)."
                     % (t.houses, t.pop, t.wood, HOUSE_COST))
    elif p.role == "farmer":
        fields = (w.struct == FIELD) & (w.owner == t.id)
        nut = float(w.nutr[fields].mean()) if fields.any() else 0
        lines.append("%d fields for %d people. Average soil nutrients %.2f%s." % (
            t.fields, t.pop, nut, " - worn out" if fields.any() and nut < 0.12 else ""))
    elif p.role in ("hunter", "gatherer", "fisher"):
        lines.append("Clan food store: %.0f (about %.1f days)%s." % (
            t.food, food_days(t), " - STARVING" if t.hungry else ""))
    lines.append("Age %d years%s." % (p.age / BIO_YEAR, " (a child)" if p.age < ADULT else ""))
    return head, lines


def describe_tribe(w, t):
    """Lines summarising a tribe's situation and behaviour."""
    out = []
    ms = [p for p in w.people if p.tribe == t.id]
    roles = {}
    for p in ms:
        roles[p.role] = roles.get(p.role, 0) + 1
    awake = sum(1 for p in ms if not p.sleeping)
    worries = [c for c, a in t.stress_causes if a > 0]
    goods = [c for c, a in t.stress_causes if a < 0]
    out.append("Wellbeing %d%% - %s.%s%s" % (100 * (1 - t.stress), mood_label(t.stress),
                                           (" Worries: " + ", ".join(worries) + ".") if worries else "",
                                           (" Comforts: " + ", ".join(goods) + ".") if goods else ""))
    if t.site_reasons:
        out.append("They settled here for %s." % ", ".join(t.site_reasons))
    ag = getattr(t, "aggr_now", t.aggression)
    out.append("Aggression: %s%s." % ("high" if ag > 0.65 else "moderate" if ag > 0.4 else "low",
                                     " - food is scarce, so they are ready to fight over resources"
                                     if getattr(t, "scarcity", 0) > 0.4 else ""))
    if t.war:
        out.append("At war with %s. A third of the clan are warriors; they stay awake at night to keep watch "
                   "and raid their enemies' stores." % ", ".join(w.tribes[i].name for i in t.war))
    else:
        out.append("At peace with every neighbour.")
    if t.hungry:
        out.append("Starving: no food left. Hunters and fishers work through the night; hunger makes them "
                   "hostile to neighbours.")
    elif food_days(t) < 2:
        out.append("Food is running low (%.1f days left)." % food_days(t))
    else:
        out.append("Well fed: %.1f days of food stored." % food_days(t))
    cap = t.houses * 4 + 6
    if t.pop >= cap - 1:
        out.append("Growth is limited by housing (%d houses). Builders need timber, so they cut down nearby forest."
                   % t.houses)
    else:
        out.append("Growing: room for %d more people." % (cap - t.pop))
    if t.fields:
        fields = (w.struct == FIELD) & (w.owner == t.id)
        nut = float(w.nutr[fields].mean()) if fields.any() else 0
        if nut < 0.12:
            out.append("Their fields' soil is exhausted, so harvests are poor and they clear more land.")
    if t.coastal:
        out.append("Coastal clan: fishers have caught %.0f units of fish and shellfish." % t.fish_caught)
    ship = next((s for s in w.ships if s.tribe == t.id), None)
    if ship:
        out.append("Their ship is %s to fetch %s." % ({"outbound": "sailing away", "away": "overseas",
                                                       "returning": "on its way back"}[ship.state], ship.cargo))
    if t.voyages:
        d, cargo, why = t.voyages[-1]
        out.append("Last voyage (%s): %s" % (d, why))
    if t.introduced:
        out.append("Species they brought with them: %s." % ", ".join(sorted(t.introduced)))
    out.append("%d of %d people are awake right now." % (awake, len(ms)))
    return out, roles
