"""
scenarios.py - teaching mode: ready-made lessons with goals.

Each scenario builds an island in a particular state, gives the student a goal grounded in a real
New Zealand conservation story, tracks progress, and ends with a debrief explaining what happened
and how it compares with the real Aotearoa.
"""
import random

from config import CAL_DAY, BIO_YEAR, LIFE_SPEED, YEAR_TICKS

BIRDS_NOTE = ("Remember: life runs %d times faster than the calendar, so one calendar year here is about %d years "
              "in the lives of the animals." % (LIFE_SPEED, LIFE_SPEED))


def count(w, name):
    sp = w.species_by_name(name)
    return w.counts.get(sp, 0) if sp else 0


def set_count(w, name, n, spread=True, near=None):
    """Make sure exactly n animals of a species exist (removing or adding)."""
    sp = w.species_by_name(name)
    if sp is None:
        return
    have = [a for a in w.animals if a.sp is sp]
    for a in have[n:]:
        a.alive = False
    w.animals = [a for a in w.animals if a.alive]
    extra = n - min(n, len(have))
    if extra > 0:
        if near:
            w.spawn_at(sp, near[0], near[1], extra)
        elif spread:
            groups = max(1, extra // 4)
            for g in range(groups):
                x, y = w.random_land()
                w.spawn_at(sp, x, y, extra // groups + (1 if g < extra % groups else 0))
    w.count_species()


def establish(w, name, n):
    set_count(w, name, n)
    sp = w.species_by_name(name)
    w.milestone("arrive:" + name, "arrival", "%s already established" % name,
                "When the lesson began, %d %s were already living on the island." % (n, name), sp.color)


def native_land_species(w):
    return [sp.name for sp in w.animal_species if sp.native and not getattr(sp, "marine", False)]


def birds_total(w):
    return sum(w.counts.get(sp, 0) for sp in w.animal_species if sp.native and getattr(sp, "bird", False)
               and not getattr(sp, "marine", False))


# ----------------------------------------------------------------------------
# setups
# ----------------------------------------------------------------------------
def setup_kakapo(w):
    set_count(w, "Kākāpō", 0)
    x, y = w.random_land()
    set_count(w, "Kākāpō", 8, near=(x, y))
    for name, n in (("Ship rat", 24), ("Stoat", 8), ("Feral cat", 5)):
        establish(w, name, n)
    w.next_mast = w.tick + int(1.5 * BIO_YEAR)


def setup_predfree(w):
    for name, n in (("Ship rat", 50), ("Stoat", 12), ("Possum", 24), ("Feral cat", 8)):
        establish(w, name, n)


def setup_feed100(w):
    import humans
    sites = []
    for _ in range(3):
        best = None
        for _ in range(200):
            x, y = w.random_land()
            if w.coast[x, y] and all(abs(x - a) + abs(y - b) > 40 for a, b in sites):
                best = (x, y)
                break
        if best is None:
            best = w.random_land()
        sites.append(best)
        humans.found_tribe(w, best[0], best[1], 10)
    w.settings["biosecurity"] = 0.3


def setup_mast(w):
    for name, n in (("Ship rat", 30), ("Stoat", 6)):
        establish(w, name, n)
    w.next_mast = w.tick + int(0.6 * BIO_YEAR)


def setup_rabbits(w):
    import humans
    x, y = w.random_land()
    for _ in range(200):
        x, y = w.random_land()
        if w.coast[x, y]:
            break
    t = humans.found_tribe(w, x, y, 14)
    if t is not None:
        t.food = 120
        t.wood = 30
        t.ship_cooldown = 18 * CAL_DAY          # the settlers' first voyage is a few weeks away
    establish(w, "Rabbit", 70)
    set_count(w, "Stoat", 0)
    set_count(w, "Feral cat", 0)
    w.settings["biosecurity"] = 0.2


# ----------------------------------------------------------------------------
# goal checks: each returns a list of goals (text, progress 0..1, state) where state is
# "ok" (on track / not yet done), "done" or "failed", plus the overall status.
# ----------------------------------------------------------------------------
def elapsed_days(w, st):
    return (w.tick - st["start"]) / CAL_DAY


def time_goal(w, st, days):
    e = elapsed_days(w, st)
    return ("Last %d days (%d years of life)" % (days, days * LIFE_SPEED / 365), min(1.0, e / days),
            "done" if e >= days else "ok")


def check_natives(w, st):
    lost = [n for n in st["natives"] if count(w, n) == 0]
    if lost:
        return ("Lose no native species", 0.0, "failed"), lost
    return ("Lose no native species (%d of %d alive)" % (len(st["natives"]), len(st["natives"])), 1.0, "ok"), []


def eval_kakapo(w, st):
    k = count(w, "Kākāpō")
    st["peak"] = max(st.get("peak", 0), k)
    goals = [time_goal(w, st, 730)]
    grow = ("Grow kākāpō from 8 to 16 (now %d, best %d)" % (k, st["peak"]), min(1.0, k / 16),
            "done" if k >= 16 else "ok")
    goals.append(grow)
    if k == 0:
        goals.append(("Keep kākāpō alive", 0.0, "failed"))
        return goals, "lost", "The last kākāpō died."
    goals.append(("Keep kākāpō alive (%d left)" % k, 1.0, "ok"))
    if goals[0][2] == "done":
        if k >= 16:
            return goals, "won", "Kākāpō numbers doubled and the birds survived two years (%d years of their lives)." \
                % (2 * LIFE_SPEED)
        return goals, "lost", "The kākāpō survived, but there are only %d - not enough to secure the species." % k
    return goals, "active", ""


PESTS = ["Ship rat", "Stoat", "Possum", "Feral cat"]


def eval_predfree(w, st):
    n = {p: count(w, p) for p in PESTS}
    left = sum(n.values())
    st["max_pests"] = max(st.get("max_pests", 0), left)
    goals = []
    nat, lost = check_natives(w, st)
    if left == 0:
        st.setdefault("clear_since", w.tick)
    else:
        st.pop("clear_since", None)
    clear_days = (w.tick - st["clear_since"]) / CAL_DAY if "clear_since" in st else 0
    goals.append(("Remove every rat, stoat, possum and cat (%d left: %s)" % (
        left, ", ".join("%d %s" % (v, k) for k, v in n.items() if v) or "none"),
        1 - left / max(1, st["max_pests"]), "done" if left == 0 else "ok"))
    goals.append(("Stay pest-free for 60 days (%d so far)" % clear_days, min(1.0, clear_days / 60),
                  "done" if clear_days >= 60 else "ok"))
    goals.append(nat)
    e = elapsed_days(w, st)
    goals.append(("Within 3 years (%d days left)" % max(0, 1095 - e), min(1.0, e / 1095), "ok"))
    if lost:
        return goals, "lost", "%s went extinct before the island was cleared of pests." % ", ".join(lost)
    if clear_days >= 60:
        return goals, "won", "The island has been pest-free for 60 days with all its native species - " \
                             "a predator-free island!"
    if e >= 1095:
        return goals, "lost", "Time ran out with %d pests still on the island." % left
    return goals, "active", ""


def eval_feed100(w, st):
    ppl = len(w.people)
    st["peak"] = max(st.get("peak", 0), ppl)
    nat, lost = check_natives(w, st)
    e = elapsed_days(w, st)
    goals = [("Grow to 100 people (now %d, best %d)" % (ppl, st["peak"]), min(1.0, ppl / 100),
              "done" if ppl >= 100 else "ok"), nat,
             ("Within 5 years (%d days left)" % max(0, 1825 - e), min(1.0, e / 1825), "ok")]
    if lost:
        return goals, "lost", "%s went extinct as the settlements grew." % ", ".join(lost)
    if ppl >= 100:
        return goals, "won", "100 people now live on the island and no native species has been lost."
    if not w.people:
        return goals, "lost", "Every settlement has died out."
    if e >= 1825:
        return goals, "lost", "After five years only %d people live on the island." % ppl
    return goals, "active", ""


STOAT_LIMIT = 30


def eval_mast(w, st):
    b = birds_total(w)
    frac = b / max(1, st["birds0"])
    stoats = count(w, "Stoat")
    rats = count(w, "Ship rat")
    st["stoat_peak"] = max(st.get("stoat_peak", 0), stoats)
    st["rat_peak"] = max(st.get("rat_peak", 0), rats)
    nat, lost = check_natives(w, st)
    goals = []
    if st.get("mast_seen") is None and w.mast > 0:
        st["mast_seen"] = w.tick
    if st.get("mast_seen") is None:
        goals.append(("Get ready: the beech is about to seed (mast)", 0.0, "ok"))
        end = None
    else:
        end = st["mast_seen"] + int(3.5 * BIO_YEAR)
        p = min(1.0, (w.tick - st["mast_seen"]) / (end - st["mast_seen"]))
        goals.append(("Get through the mast and the plague after it (%d days left)" % max(0, (end - w.tick) / CAL_DAY),
                      p, "done" if w.tick >= end else "ok"))
    over = st["stoat_peak"] > STOAT_LIMIT
    goals.append(("Never let stoats pass %d (now %d, peak %d; rats now %d)" % (STOAT_LIMIT, stoats, st["stoat_peak"], rats),
                  1.0 if not over else 0.0, "failed" if over else "ok"))
    goals.append(("Keep at least 80%% of native birds (now %d%%)" % (100 * frac), min(1.0, frac / 0.8),
                  "ok" if frac >= 0.8 else "failed"))
    goals.append(nat)
    if lost:
        return goals, "lost", "%s went extinct during the plague." % ", ".join(lost)
    if over:
        return goals, "lost", "The stoat plague got away: %d stoats, fed by a boom of %d rats, are now hunting the " \
                              "forest's birds and their nests." % (st["stoat_peak"], st["rat_peak"])
    if frac < 0.8:
        return goals, "lost", "The rat and stoat plague killed too many native birds."
    if end and w.tick >= end:
        return goals, "won", "You kept the plague in check: stoats never passed %d (rats peaked at %d) and the birds " \
                             "came through." % (STOAT_LIMIT, st["rat_peak"])
    return goals, "active", ""


def eval_rabbits(w, st):
    r = count(w, "Rabbit")
    nat, lost = check_natives(w, st)
    e = elapsed_days(w, st)
    st["peak"] = max(st.get("peak", 0), r)
    arrived = [n for n in ("Stoat", "Feral cat") if "arrive:" + n in w.milestone_keys]
    goals = [("Bring rabbits under 30 (now %d, peak %d)" % (r, st["peak"]), 1.0 if r < 30 else 30 / max(30, r),
              "done" if r < 30 else "ok"), nat,
             ("Keep stoats and cats off the island%s" % (" - %s arrived!" % " and ".join(arrived) if arrived else ""),
              0.0 if arrived else 1.0, "failed" if arrived else "ok"),
             ("Hold for 18 months (%d days left)" % max(0, 545 - e), min(1.0, e / 545), "done" if e >= 545 else "ok")]
    if lost:
        return goals, "lost", "%s went extinct." % ", ".join(lost)
    if e >= 545:
        if r < 30 and not arrived:
            return goals, "won", "Rabbits are under control and no predators were brought in to 'help'."
        why = []
        if r >= 30:
            why.append("there are still %d rabbits" % r)
        if arrived:
            why.append("%s were brought in" % " and ".join(arrived))
        return goals, "lost", "After 18 months %s." % " and ".join(why)
    return goals, "active", ""


# ----------------------------------------------------------------------------
SCENARIOS = [
    {
        "id": "kakapo", "title": "Save the kākāpō", "short": "Protect the last 8 kākāpō and double them.",
        "opts": {"region": "south", "geo": "big", "forest": 0.8},
        "setup": setup_kakapo, "eval": eval_kakapo, "tools_off": [],
        "brief": ["Only 8 kākāpō are left, living in one corner of the island - and ship rats, stoats and feral "
                  "cats are already here.",
                  "Kākāpō are flightless, nocturnal and freeze when danger comes, so predators find them easily. "
                  "They only breed when rimu trees mast, every few years, and lay just 1-4 eggs."],
        "goals": ["Keep kākāpō alive for 2 years (40 years of their lives)", "Grow the population to at least 16"],
        "learn": "Why slow-breeding, ground-nesting birds can't survive introduced predators, and how sanctuaries, "
                 "trapping and patience save them.",
        "tips": ["Fence a predator-proof sanctuary around the kākāpō, then trap the predators inside it.",
                 "Plant rimu: more rimu means more food when it masts.",
                 "Breeding only happens in mast years - watch for the alert."],
        "fact": "In 1995 only 51 kākāpō were left. The Kākāpō Recovery programme moved every bird to "
                "predator-free islands like Whenua Hou, watched every nest and fed the birds. Today there are more "
                "than 240.",
    },
    {
        "id": "predfree", "title": "Predator Free island", "short": "Wipe out rats, stoats, possums and cats.",
        "opts": {"region": "north", "geo": "big", "land": 0.45},
        "setup": setup_predfree, "eval": eval_predfree, "tools_off": ["smite"],
        "brief": ["Rats, stoats, possums and feral cats have spread across the island. Your job: remove every "
                  "last one and keep the island clean - without losing a single native species.",
                  "Smite is switched off: real conservation can't make animals vanish. You have traps, fences "
                  "and biosecurity."],
        "goals": ["Remove every rat, stoat, possum and cat", "Stay pest-free for 60 days", "Lose no native species",
                  "Do it within 3 years"],
        "learn": "How eradication works: cover the whole area, keep going until the last animal is gone, then "
                 "stop them coming back. Even a few survivors breed back fast.",
        "tips": ["Traps only work where you put them: cover the whole island in a grid.",
                 "Fence the most important places first so native birds have a refuge.",
                 "Raise Biosecurity (Physics tab) so nothing new arrives."],
        "fact": "New Zealand aims to be Predator Free by 2050. More than 100 islands have already been cleared - "
                "Rangitoto and Motutapu, Kapiti, Campbell Island (200 km away, the size of a small country) - "
                "and native birds have returned to them.",
    },
    {
        "id": "feed100", "title": "Feed 100 people", "short": "Grow the settlements without losing a native species.",
        "opts": {"region": "north", "geo": "big", "land": 0.6},
        "setup": setup_feed100, "eval": eval_feed100, "tools_off": ["smite"],
        "brief": ["Three canoes have landed with 30 settlers. They need food, timber and land - and the island's "
                  "birds have never seen a hunter.",
                  "Help the settlements reach 100 people while every native species survives."],
        "goals": ["Reach 100 people", "Lose no native species", "Within 5 years (100 years of life)"],
        "learn": "People and nature compete for the same land. Growing a population sustainably means protecting "
                 "habitat, limiting hunting of slow breeders and keeping new pests out.",
        "tips": ["Fenced sanctuaries are off-limits to hunters and builders - protect the slow breeders.",
                 "Biosecurity stops ships bringing pests.",
                 "Hungry clans fight; well-fed clans grow."],
        "fact": "Polynesian settlers reached Aotearoa around 1250-1300 AD. Within about 200 years all nine species "
                "of moa had been hunted to extinction, along with the Haast's eagle that preyed on them.",
    },
    {
        "id": "mast", "title": "Mast year plague", "short": "Get ready before the beech seeds - then hold on.",
        "opts": {"region": "south", "geo": "mountains", "forest": 0.85},
        "setup": setup_mast, "eval": eval_mast, "tools_off": [],
        "brief": ["The beech forest is about to mast: a huge seed crop all at once. Rats will feast and multiply; "
                  "stoats will multiply on the rats. When the seed runs out, the hungry predators turn on birds.",
                  "You have a few weeks before the seed falls. Stop the plague before it starts: keep the stoats "
                  "in check and the birds safe."],
        "goals": ["Get through the mast and the plague that follows", "Never let stoats pass 30",
                  "Keep at least 80% of the native birds", "Lose no native species"],
        "learn": "How one event ripples through a food web: seed -> rats -> stoats -> birds. Acting early beats "
                 "reacting late.",
        "tips": ["Trap before the mast, not after - the plague comes fast.",
                 "Open the Food web (F) to watch the cascade happen.",
                 "Fences protect the birds you can't trap around."],
        "fact": "After heavy beech masts, the Department of Conservation runs 'Tiakina Ngā Manu' (formerly Battle "
                "for our Birds), large predator-control operations timed to stop the rat and stoat plague before "
                "it reaches the birds.",
    },
    {
        "id": "rabbits", "title": "The rabbit problem", "short": "Control rabbits - without the stoat 'solution'.",
        "opts": {"region": "south", "geo": "lowlands", "forest": 0.55},
        "setup": setup_rabbits, "eval": eval_rabbits, "tools_off": ["smite"],
        "brief": ["Rabbits are eating the settlers' crops and the tussock. The settlers think they know the answer: "
                  "ship in stoats and cats to eat the rabbits.",
                  "Bring the rabbits under control yourself, and stop the settlers from bringing predators in."],
        "goals": ["Bring rabbits under 30", "Keep stoats and cats off the island", "Lose no native species",
                  "Hold for 18 months"],
        "learn": "Biological control can backfire badly. A predator brought in to kill one pest will happily eat "
                 "easier prey - like naive native birds.",
        "tips": ["Traps catch rabbits too.",
                 "Raise Biosecurity (Physics tab) soon: it makes voyages rarer and lets border checks stop the "
                 "stoats coming ashore.",
                 "Watch the clan's voyages in the People panel."],
        "fact": "In the 1880s stoats, ferrets and weasels were released to control rabbits, despite warnings from "
                "naturalists. They did little to the rabbits but devastated native birds - stoats are now the "
                "main killer of kiwi chicks.",
    },
]
BY_ID = {s["id"]: s for s in SCENARIOS}


def start(app, sid, difficulty):
    from world import World
    sc = BY_ID[sid]
    opts = dict(sc["opts"])
    opts["difficulty"] = difficulty
    w = World(random.randrange(1 << 30), opts)
    sc["setup"](w)
    w.count_species()
    w.scenario = {"id": sid, "start": w.tick, "status": "active", "message": "", "goals": [],
                  "natives": [n for n in native_land_species(w) if count(w, n) > 0],
                  "birds0": max(1, birds_total(w)), "shown": False}
    w.milestone("scenario", "conservation", "Lesson started: %s" % sc["title"], " ".join(sc["goals"]), (110, 210, 200))
    w.log("Lesson: %s. %s" % (sc["title"], sc["short"]), (110, 210, 200))
    app.set_world(w)
    check(w)


def check(w):
    st = w.scenario
    if not st or st["status"] != "active":
        return
    sc = BY_ID.get(st["id"])
    if sc is None:
        return
    goals, status, msg = sc["eval"](w, st)
    st["goals"] = goals
    if status != "active":
        st["status"] = status
        st["message"] = msg
        st["end"] = w.tick
        st["end_date"] = w.stamp
        w.milestone("scenario_end", "conservation",
                    "Lesson %s: %s" % ("complete" if status == "won" else "failed", sc["title"]), msg,
                    (126, 206, 146) if status == "won" else (240, 110, 100))


def tool_blocked(w, tool):
    st = getattr(w, "scenario", None)
    if not st or st["status"] != "active":
        return False
    return tool in BY_ID.get(st["id"], {}).get("tools_off", [])
