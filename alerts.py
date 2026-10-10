"""
alerts.py - clickable ecological alerts.

Each alert explains WHAT is happening, WHY (using what the simulation actually
recorded: causes of death, plant losses, human activity), HOW the player can
help (with buttons that pick the right tool), and links it to the real
Aotearoa New Zealand.

Action tuples understood by the UI:
    ("tool", name)            select a tool  (trap, sanctuary, water, cloud, fertilize, smite)
    ("species", name)         select a species to place / plant
    ("slider", key, value)    set a physics slider
"""
from collections import Counter

from config import DAY_TICKS, POP_CAP, FIELD, HOUSE

SEV_COLORS = {"good": (126, 206, 146), "info": (130, 180, 240), "warn": (240, 190, 90), "crit": (240, 100, 90)}

FOOD_PLANTS = {
    "Wētā": ["Ponga", "Harakeke"],
    "Kiwi": ["Ponga", "Rimu"],           # forest floor habitat with leaf litter and weta
    "Kākāpō": ["Rimu", "Tussock"],
    "Tūī": ["Kōwhai", "Harakeke"],
    "Kererū": ["Kōwhai", "Rimu"],
    "Ruru": ["Rimu", "Ponga"],
    "Kārearea": ["Tussock", "Mānuka"],
}

TRAP_HELP = ("Set pest traps where it lives (Trap tool) - traps catch rats, stoats, cats, possums and rabbits.",
             ("tool", "trap"))
FENCE_HELP = ("Fence off a predator-free sanctuary (Fence tool). Introduced animals can't get in, "
              "and people won't hunt or build inside.", ("tool", "sanctuary"))
BIO_HELP = ("Raise Biosecurity so settlers are less likely to bring new pests.", ("slider", "biosecurity", 0.9))


def post(w, key, sev, title, what, why, helps, fact, pos=None, cooldown_days=3.0):
    last = w.alert_cool.get(key, -1e9)
    if w.tick - last < cooldown_days * DAY_TICKS:
        return None
    w.alert_cool[key] = w.tick
    a = {"key": key, "sev": sev, "title": title, "what": what, "why": why,
         "help": helps, "fact": fact, "pos": pos, "tick": w.tick, "day": w.day, "date": w.stamp,
         "read": False}
    w.alerts.append(a)
    if len(w.alerts) > 60:
        w.alerts = w.alerts[-60:]
    w.log(("! " if sev in ("warn", "crit") else "") + title, SEV_COLORS[sev])
    w.new_alerts.append(a)
    record_milestone(w, key, sev, title, what, pos)
    return a


MILESTONE_KINDS = [("extinct", "extinction", True), ("free", "conservation", True), ("recover", "recovery", True),
                   ("recol", "recovery", True), ("wildfire", "ecosystem", False), ("mast", "ecosystem", True),
                   ("drained", "ecosystem", False), ("overfish", "ecosystem", False), ("sediment", "ecosystem", False),
                   ("forest", "ecosystem", False), ("plague", "arrival", True), ("peace", "war", True),
                   ("erosion", "ecosystem", False), ("browse", "ecosystem", False), ("pollinator", "ecosystem", False)]


def record_milestone(w, key, sev, title, what, pos):
    for prefix, cat, repeat in MILESTONE_KINDS:
        if key.startswith(prefix):
            mk = "%s:%d" % (key, w.tick) if repeat else "first_" + key
            if prefix == "extinct" and not any(m["cat"] == "extinction" for m in w.milestones):
                title = title + " (first extinction)"
            w.milestone(mk, cat, title, what, SEV_COLORS[sev], pos)
            return


def death_causes(w, name, days=2):
    c = Counter()
    for day in w.death_days[-days:] + [w.deaths]:
        for (n, cause), k in day.items():
            if n == name:
                c[cause] += k
    return c


def plant_losses(w, days=2):
    c = Counter()
    for day in w.ploss_days[-days:] + [w.ploss]:
        c.update(day)
    return c


def species_pos(w, sp):
    xs = [(a.x, a.y) for a in w.animals if a.sp is sp]
    if not xs:
        return None
    return (sum(x for x, _ in xs) / len(xs), sum(y for _, y in xs) / len(xs))


# ----------------------------------------------------------------------------
# explanations of causes
# ----------------------------------------------------------------------------
def explain_causes(w, sp, causes):
    total = sum(causes.values()) or 1
    lines, helps = [], []
    seen_help = set()

    def add_help(h):
        if h[0] not in seen_help:
            seen_help.add(h[0])
            helps.append(h)

    parts = ", ".join("%s (%d)" % (c, k) for c, k in causes.most_common(4))
    if parts:
        lines.append("Recorded deaths over the last few weeks: %s." % parts)
    for cause, k in causes.most_common(3):
        share = k / total
        if share < 0.12:
            continue
        if cause.startswith("eaten by "):
            pred = w.species_by_name(cause[9:])
            if pred is not None and not pred.native:
                lines.append("%s is an introduced predator. Native animals evolved for millions of years "
                             "without ground-hunting mammals, so many don't recognise the danger, nest on "
                             "or near the ground, and young ones are easy to catch." % pred.name)
                add_help(TRAP_HELP)
                add_help(FENCE_HELP)
            else:
                lines.append("%s is a native predator. Natural predation is part of a healthy ecosystem, "
                             "but it hurts when prey numbers are already low." % cause[9:])
        elif cause == "hunted by humans":
            lines.append("People are hunting %s. Animals that never learned to fear humans - especially big, "
                         "flightless birds - are easy to catch." % sp.name)
            add_help(FENCE_HELP)
        elif cause == "starvation":
            foods = FOOD_PLANTS.get(sp.name, [])
            lines.append("%s can't find enough food (it eats %s). Food may have been lost to clearing, fire, "
                         "drought, or eaten by competitors such as possums, deer or rats."
                         % (sp.name, ", ".join(sorted(sp.diet))))
            for f in foods:
                add_help(("Plant %s to restore its food and habitat." % f, ("species", f)))
            add_help(TRAP_HELP)
        elif cause in ("cold", "heat"):
            lines.append("The climate is outside what %s can tolerate (it prefers about %.0f C)." % (sp.name, sp.topt))
            if cause == "cold":
                add_help(("Warm the climate a little (Temperature).", ("slider", "temp", 3.0)))
            else:
                add_help(("Cool the climate a little (Temperature).", ("slider", "temp", -3.0)))
        elif cause == "disease":
            lines.append("Disease spreads quickly when animals are crowded together, and faster where "
                         "microbes are dense.")
        elif cause == "fire":
            lines.append("Animals were caught in fires. Native forests here are not adapted to frequent burning.")
            add_help(("Summon rain over fires (Rain cloud tool).", ("tool", "cloud")))
        elif cause == "old age" and getattr(sp, "mast_breeder", False):
            lines.append("Kakapo live long but breed rarely - only when rimu masts - so old birds aren't "
                         "being replaced fast enough.")
            add_help(("Plant Rimu so more trees can mast.", ("species", "Rimu")))
    if not helps:
        add_help(("Protect its habitat: plant native forest and avoid clearing.", ("species", "Rimu")))
    return " ".join(lines), helps


# ----------------------------------------------------------------------------
# alerts fired directly by events
# ----------------------------------------------------------------------------
def alert_settlers(w, t):
    first = not w.alert_state.get("any_settlers")
    w.alert_state["any_settlers"] = True
    post(w, "settle%d" % t.id, "info", "People have arrived: the %s" % t.name,
         "A group of people has made camp. They will hunt, gather, chop trees for houses, clear land "
         "for fields and grow their numbers. Watch how the land changes around them.",
         "Humans reshape ecosystems faster than any other species: hunting large animals, burning and "
         "clearing forest, draining wetlands - and, often by accident, bringing new species with them.",
         [FENCE_HELP, BIO_HELP],
         "Aotearoa was one of the last large land masses people settled, around 700-800 years ago. "
         "Within a few centuries moa were extinct and much of the eastern lowland forest had burned."
         if first else "Every new settlement adds pressure on nearby habitat.",
         pos=(t.x, t.y), cooldown_days=0)


INTRO_TEXT = {
    "Ship rat": ("Rats came ashore with the %s as stowaways.",
                 "Rats breed fast, climb trees to raid nests, and eat seeds, weta and lizards. In mast years "
                 "their numbers explode.",
                 "Rats were among the first mammals to reach New Zealand with people. Several small "
                 "islands have since been made rat-free - a technique NZ pioneered."),
    "Rabbit": ("The %s released rabbits for food and sport.",
               "With no predators, rabbits breed explosively and strip grasslands bare, exposing soil to erosion.",
               "Rabbit plagues in the 1800s devastated high-country farms - which led to stoats and ferrets "
               "being released to control them."),
    "Feral cat": ("Cats brought by the %s have gone wild.",
                  "Feral cats hunt birds, lizards and insects, and are big enough to kill adult kiwi.",
                  "Feral cats are now found across New Zealand, from farmland to the high country."),
    "Possum": ("The %s released possums to start a fur trade.",
               "Possums eat the leaves of native trees night after night, killing some outright, and raid "
               "nests for eggs and chicks.",
               "Brushtail possums were brought from Australia in 1837. Tens of millions now live in NZ "
               "forests, and they also spread bovine tuberculosis."),
    "Red deer": ("The %s released deer for hunting.",
                 "Deer have no natural predators here. They browse the forest understorey - ferns, seedlings "
                 "and shrubs - so the forest can't regenerate.",
                 "Deer were introduced in the 1800s for sport; by the mid-1900s they were seen as a major "
                 "threat to native forests."),
    "Gorse": ("The %s planted gorse as hedges around their fields.",
              "Gorse escapes hedges and spreads over open land. It is spiny and very flammable - but it also "
              "fixes nitrogen and can shelter native seedlings, which eventually overtop it.",
              "Gorse came from Europe as hedging and is now one of NZ's most widespread weeds. Some "
              "reserves, like Hinewai on Banks Peninsula, let native forest regrow through it."),
    "Wilding pine": ("The %s planted a pine plantation.",
                     "Pine seeds blow far on the wind. Wilding pines invade tussock grassland, shading it out and "
                     "using up water.",
                     "Wilding conifers spread over large areas of NZ's high country, and big control programmes "
                     "now work to remove them."),
    "Stoat": ("The %s released stoats to control the rabbits.",
              "Stoats rarely stop at rabbits. They are agile, climb trees, and kill birds, eggs and chicks.",
              "Stoats and ferrets were released in the 1880s to control rabbits. Stoats are now the biggest "
              "killer of kiwi chicks - in unmanaged areas only about 5% of chicks survive."),
}


def alert_introduction(w, sp, t, reason=None):
    what, why, fact = INTRO_TEXT.get(sp.name, ("The %s introduced " + sp.name + ".", sp.blurb, ""))
    if reason:
        what = reason.replace("%", "%%") + ("" if t.name in reason else " (%s)")
        what = what.replace(t.name, "%s", 1) if t.name in reason else what
    helps = [BIO_HELP]
    if sp.kind == "animal":
        if getattr(sp, "trappable", False):
            helps.insert(0, TRAP_HELP)
        else:
            helps.insert(0, ("Remove them with the Smite tool (culling) before they spread.", ("tool", "smite")))
        helps.insert(1, FENCE_HELP)
    else:
        helps.insert(0, ("Clear the weeds with the Smite tool and replant natives.", ("tool", "smite")))
        helps.insert(1, ("Plant Mānuka - native pioneers can outcompete weeds over time.", ("species", "Mānuka")))
    post(w, "intro%s%d" % (sp.name, t.id), "warn", "New arrival: %s" % sp.name, what % t.name, why, helps, fact,
         pos=(t.x, t.y), cooldown_days=0)


def alert_famine(w, t):
    post(w, "famine%d" % t.id, "warn", "Famine among the %s" % t.name,
         "The %s have run out of food and people are starving." % t.name,
         "Their hunting grounds may be emptied, their fields' soil exhausted, or pests may be eating their "
         "crops. Hungry tribes become hostile towards their neighbours.",
         [("Add compost to their fields to restore the soil.", ("tool", "fertilize")),
          ("Bring rain if the land is dry.", ("tool", "cloud"))],
         "Over-hunting removes the easiest food first. Early hunters moved on to fish, shellfish, birds "
         "and gardening as large game disappeared.",
         pos=(t.x, t.y), cooldown_days=3)


def alert_war(w, a, b):
    post(w, "war%d_%d" % (min(a.id, b.id), max(a.id, b.id)), "warn", "Conflict: %s vs %s" % (a.name, b.name),
         "The %s and the %s are at war. Warriors will fight and raid each other's houses." % (a.name, b.name),
         "Their territories are close and competing for the same land and food. Scarcity and crowding "
         "raise tension; burned houses and lost hunters change how much land each tribe uses.",
         [("Give them more space: settle new groups further apart.", None),
          ("Food shortages fuel conflict - keep their land fertile (Compost).", ("tool", "fertilize"))],
         "Throughout history, competition for resources has been a common driver of conflict between groups.",
         pos=((a.x + b.x) / 2, (a.y + b.y) / 2), cooldown_days=1)


def alert_peace(w, a, b):
    post(w, "peace%d_%d" % (min(a.id, b.id), max(a.id, b.id)), "good", "Peace between %s and %s" % (a.name, b.name),
         "The fighting has stopped.", "Tension eased as the war went on, or one side became too small to fight.",
         [], "", pos=((a.x + b.x) / 2, (a.y + b.y) / 2), cooldown_days=1)


def alert_burning(w, t, x, y):
    post(w, "burn%d" % t.id, "warn", "The %s are burning forest" % t.name,
         "People have set fire to forest near their settlement to open up land.",
         "Fire is a fast way to clear land for hunting, travel and gardens. But native forest recovers slowly, "
         "and the fire can spread far beyond what was intended in dry, windy weather.",
         [("Bring rain to put it out (Rain cloud).", ("tool", "cloud")),
          ("Protect forest inside a sanctuary - people won't burn there.", ("tool", "sanctuary")),
          ("Replant with Mānuka, a pioneer that heals burnt ground.", ("species", "Mānuka"))],
         "Early fires after human arrival destroyed a large share of NZ's forest, especially in the drier east, "
         "where tussock and fern replaced it.",
         pos=(x, y), cooldown_days=3)


# ----------------------------------------------------------------------------
# periodic checks
# ----------------------------------------------------------------------------
def check_alerts(w):
    st = w.alert_state
    hist = w.history
    if len(hist) < 6 or w.elapsed < 4 * DAY_TICKS:
        return
    window = hist[-54:]
    # ---- animal declines, extinctions, recoveries, pest milestones
    for i, sp in enumerate(w.animal_species):
        n = w.counts.get(sp, 0)
        past = [h["animals"][i] for h in window if i < len(h["animals"])]
        peak = max(past) if past else n
        key = sp.name
        if sp.native:
            if peak >= 8 and n <= peak * 0.5 and n > 0:
                causes = death_causes(w, sp.name)
                why, helps = explain_causes(w, sp, causes)
                a = post(w, "decline" + key, "warn", "%s numbers have halved" % sp.name,
                         "%s fell from %d to %d in just %d days." % (sp.name, peak, n, len(window) * 20 // 120),
                         why or "The causes aren't clear yet - watch the Chronicle.",
                         helps, sp.blurb, pos=species_pos(w, sp), cooldown_days=3)
                if a:
                    st["low" + key] = n
            if n == 0 and st.get("had" + key):
                causes = death_causes(w, sp.name, days=3)
                why, helps = explain_causes(w, sp, causes)
                helps = [("Re-introduce %s from the species list - like real translocations to "
                          "predator-free islands." % sp.name, ("species", sp.name))] + helps
                if sp.flier or getattr(sp, "marine", False):
                    back = (" Because %s can fly or swim, a few may one day arrive from another island by "
                            "themselves (see the Native recolonisation slider) - but only if the threats are gone."
                            % sp.name)
                else:
                    back = (" %s can't fly or swim here, so it will NOT come back on its own: on an island, "
                            "extinction is forever unless you reintroduce it." % sp.name)
                post(w, "extinct" + key, "crit", "%s is extinct here" % sp.name,
                     "The last %s in your world has died." % sp.name + back, why, helps,
                     "Since people arrived, Aotearoa has lost around 50 bird species, including all nine moa, "
                     "the huia and Haast's eagle - the largest eagle ever known, which hunted moa.",
                     cooldown_days=2)
                st["had" + key] = False
            if n >= 5:
                st["had" + key] = True
            low = st.get("low" + key)
            if low is not None and n >= max(12, low * 2):
                post(w, "recover" + key, "good", "%s is recovering" % sp.name,
                     "%s has bounced back from %d to %d." % (sp.name, low, n),
                     "Fewer threats and more food let the population grow again.",
                     [], "Intensive predator control and sanctuaries have helped kiwi, kakapo, takahe and many "
                     "other species recover in real NZ.", pos=species_pos(w, sp), cooldown_days=4)
                st.pop("low" + key, None)
        else:
            if n >= 8 and not st.get("est" + key):
                st["est" + key] = True
                helps = [TRAP_HELP if sp.trappable else
                         ("Cull them with the Smite tool.", ("tool", "smite")), FENCE_HELP, BIO_HELP]
                post(w, "est" + key, "warn", "%s is spreading" % sp.name,
                     "There are now %d %s in your world and they are breeding." % (n, sp.name),
                     sp.blurb, helps,
                     "New Zealand's goal Predator Free 2050 aims to eradicate rats, stoats and possums "
                     "from the whole country.", pos=species_pos(w, sp), cooldown_days=0)
            if n > POP_CAP * 0.6:
                post(w, "plague" + key, "crit", "%s plague!" % sp.name,
                     "%s numbers have exploded to %d." % (sp.name, n),
                     sp.blurb + (" A mast year means a huge supply of seed for them." if w.mast > 0 and
                                 "seed" in sp.diet else ""),
                     [TRAP_HELP if sp.trappable else ("Cull them with the Smite tool.", ("tool", "smite")),
                      FENCE_HELP],
                     "After big beech and rimu mast years, NZ's conservation agencies run large predator "
                     "control operations to stop rat and stoat plagues.",
                     pos=species_pos(w, sp), cooldown_days=4)
            if n == 0 and st.get("est" + key):
                st["est" + key] = False
                post(w, "free" + key, "good", "Pest-free: no %s left!" % sp.name,
                     "%s has been eradicated from your world." % sp.name,
                     "Removing an introduced pest lets native species recover - as long as it doesn't come back.",
                     [BIO_HELP],
                     "NZ has eradicated rats and other pests from more than 100 islands, which have become "
                     "safe havens for endangered birds.", cooldown_days=1)

    # ---- forest loss
    trees_now = hist[-1].get("trees", 0)
    trees_then = max(h.get("trees", 0) for h in window)
    if trees_then > 300 and trees_now < trees_then * 0.75:
        pl = plant_losses(w)
        why = []
        if pl.get("fire", 0) > 0.5:
            why.append("Fires burned %.0f units of vegetation." % pl["fire"])
        if pl.get("humans", 0) > 0.5:
            why.append("People cut or cleared %.0f units for wood, houses and fields." % pl["humans"])
        browse = sum(v for k, v in pl.items() if k.startswith("browse:"))
        if browse > 0.5:
            names = [k[7:] for k, v in pl.most_common() if k.startswith("browse:")][:3]
            why.append("Browsing animals (%s) ate %.0f units of leaves." % (", ".join(names), browse))
        if pl.get("drought", 0) > 0.5:
            why.append("Drought and stress killed plants.")
        post(w, "forest", "warn", "Forest is disappearing",
             "Tree cover fell from %d to %d cells." % (trees_then, trees_now),
             " ".join(why) or "Trees are dying faster than they regrow.",
             [("Plant native trees: Rimu and Kōwhai (or Mānuka first on bare land).", ("species", "Rimu")),
              ("Protect forest inside a sanctuary.", ("tool", "sanctuary")),
              TRAP_HELP],
             "Before people arrived, around 80% of New Zealand was forested. Today native forest covers "
             "about a quarter of the land.", cooldown_days=4)

    # ---- wildfire
    fire_n = int((w.fire > 0).sum())
    if fire_n > 150:
        import numpy as np
        xs, ys = np.nonzero(w.fire > 0)
        post(w, "wildfire", "crit", "Wildfire!",
             "%d cells are burning." % fire_n,
             "Dry weather plus flammable plants - manuka, gorse and tussock burn readily - let fire spread, "
             "pushed by the wind. Animals flee or die, and burned land is exposed to erosion.",
             [("Summon rain over the fire (Rain cloud).", ("tool", "cloud")),
              ("Pour water to make a firebreak (Water tool).", ("tool", "water"))],
             "Most native NZ plants are not adapted to fire. After burning, manuka and bracken usually come "
             "back first, and forest can take centuries to return.",
             pos=(float(xs.mean()), float(ys.mean())), cooldown_days=1.5)

    # ---- drought / flood
    land = w.land
    moist = float(w.moist[land].mean())
    if moist < 0.15:
        post(w, "drought", "warn", "Drought",
             "The soil is drying out (average soil water %d%%)." % (moist * 100),
             "Not enough rain, strong sun or high evaporation. Plants wilt and die back, animals go hungry, "
             "and fire risk climbs.",
             [("Increase Rainfall.", ("slider", "rain", 1.6)), ("Reduce Evaporation.", ("slider", "evap", 0.7)),
              ("Summon a rain cloud.", ("tool", "cloud"))],
             "Droughts are becoming more frequent in parts of NZ, especially the east coast.", cooldown_days=4)
    lake = float((w.water[land] > 0.3).mean())
    if lake > 0.3:
        post(w, "flood", "warn", "Flooding",
             "%d%% of the land is under water." % (lake * 100),
             "Heavy rain is falling faster than water can drain away or evaporate. Flooded plants drown.",
             [("Reduce Rainfall.", ("slider", "rain", 0.6)), ("Dry out areas (Dry tool).", ("tool", "dry"))],
             "Forests and wetlands act like sponges that slow floodwater down.", cooldown_days=4)

    # ---- erosion
    if w.erosion_recent > 110:
        post(w, "erosion", "warn", "Soil erosion",
             "Rain is washing soil and nutrients off bare slopes.",
             "Where trees and roots have been removed - by clearing, fire, or grazing animals - nothing holds "
             "the soil when it rains.",
             [("Plant Mānuka on bare ground - fast roots hold soil.", ("species", "Mānuka")),
              ("Add compost to rebuild the soil.", ("tool", "fertilize"))],
             "Erosion is one of New Zealand's biggest land problems; planting trees on steep hill country "
             "is one of the main fixes.", cooldown_days=5)

    # ---- wetlands drained
    if w.drained > 4 and not st.get("drained"):
        st["drained"] = True
        post(w, "drained", "warn", "Wetlands are being drained",
             "Farmers are digging drains to turn swamps into fields.",
             "Wetlands store water, filter it, and are home to raupo, flax, eels and many birds. Draining them "
             "makes farmland but destroys that habitat.",
             [("Protect wetlands inside a sanctuary.", ("tool", "sanctuary")),
              ("Replant Raupō and Harakeke at the water's edge.", ("species", "Raupō"))],
             "About 90% of New Zealand's original wetlands have been drained since people arrived.",
             cooldown_days=0)

    # ---- exhausted fields
    fields = w.struct == FIELD
    if int(fields.sum()) > 15 and float(w.nutr[fields].mean()) < 0.1:
        post(w, "soil", "info", "Farm soil is exhausted",
             "Crops have used up the nutrients in the fields.",
             "Each harvest removes nutrients. Without compost, rest or nitrogen-fixing plants, yields fall and "
             "people go hungry - then clear more land.",
             [("Add compost to the fields.", ("tool", "fertilize"))],
             "Farming in NZ depends heavily on adding fertiliser - which can then wash into rivers and lakes.",
             cooldown_days=5)

    # ---- overbrowsing
    browsers = sum(w.counts.get(sp, 0) for sp in w.animal_species if sp.browser and not sp.native)
    if browsers > 50:
        post(w, "browse", "warn", "The forest understorey is being eaten",
             "%d possums and deer are browsing the forest." % browsers,
             "Possums strip leaves from trees like kowhai; deer eat ferns and seedlings. Without young plants "
             "the forest can't replace old trees, and native birds lose food.",
             [TRAP_HELP, ("Cull deer with the Smite tool.", ("tool", "smite")), FENCE_HELP],
             "Possums and deer are among the main reasons some NZ forests are collapsing.", cooldown_days=4)

    check_ocean(w)

    # ---- pollination / dispersal
    tui = w.species_by_name("Tūī")
    if tui is not None and st.get("hadTūī") is False and w.counts.get(tui, 0) == 0:
        post(w, "pollinator", "warn", "Flowers without pollinators",
             "With no tui left, flowers on kowhai and flax are not being pollinated.",
             "Flowering plants depend on birds and insects to carry pollen. Without them, fewer seeds are set "
             "and those plants slowly decline.",
             [("Re-introduce Tūī.", ("species", "Tūī")), TRAP_HELP],
             "Many NZ plants rely on native birds like tui and bellbirds for pollination.", cooldown_days=6)


def alert_mast(w):
    post(w, "mast", "info", "Mast year: rimu and tussock are seeding heavily",
         "Every few years these plants produce a huge crop of fruit and seed all at once.",
         "Masting floods the forest with food. Kakapo only breed in mast years. But rats also feast and breed "
         "fast - and when the seed runs out, hungry rats and the stoats that eat them turn on birds.",
         [("Set traps ahead of the rat plague.", ("tool", "trap")), FENCE_HELP],
         "Mast years in beech and rimu forests trigger NZ's large predator-control operations, and "
         "kakapo breeding seasons.", cooldown_days=8)


def alert_recolonise(w, sp, pos):
    how = "swam" if getattr(sp, "marine", False) else "flew"
    post(w, "recol" + sp.name, "good", "%s returned from another island" % sp.name,
         "A few %s %s in from beyond the coast and are trying to settle again." % (sp.name, how),
         "Animals that can fly or swim can cross the sea and recolonise an island - but only flightless "
         "ones can't. Whether they survive depends on whether whatever wiped them out is still here.",
         [TRAP_HELP, FENCE_HELP],
         "Some native birds have recolonised places on their own once predators were removed - for example "
         "kaka and tui spreading out from the fenced Zealandia sanctuary into Wellington city.",
         pos=pos, cooldown_days=2)


def check_ocean(w):
    if not w.sea.any() or len(w.history) < 20 or w.elapsed < 4 * DAY_TICKS:
        return
    st = w.alert_state
    window = w.history[-54:]
    fish_now = w.history[-1].get("fish", 0)
    fish_peak = max(h.get("fish", 0) for h in window)
    near = None
    if w.people:
        caught = w.fish_caught_recent
        if fish_peak > 0.1 and fish_now < fish_peak * 0.75 and caught > 5:
            post(w, "overfish", "warn", "Overfishing",
                 "Fish stocks have fallen from %d%% to %d%% as people fish the coast." % (fish_peak * 100, fish_now * 100),
                 "People caught %.0f units of fish in recent weeks - faster than the plankton-fed fish "
                 "population can breed. Seals and penguins that eat fish go hungry too." % caught,
                 [("Make a marine reserve: draw a Fence sanctuary over the sea - no fishing inside.",
                   ("tool", "sanctuary"))],
                 "New Zealand's first marine reserve, near Leigh, was created in 1975. Inside, snapper and "
                 "crayfish became far bigger and more numerous than in fished waters nearby.",
                 pos=near, cooldown_days=4)
    shell = w.history[-1].get("shellfish", 0)
    shell_peak = max(h.get("shellfish", 0) for h in window)
    if shell_peak > 0.2 and shell < shell_peak * 0.7 and float(w.sediment[w.shallow].mean()) > 0.08:
        post(w, "sediment", "warn", "Mud is smothering the shellfish beds",
             "Shellfish in the shallows have fallen from %d%% to %d%%." % (shell_peak * 100, shell * 100),
             "Rain washes soil from bare, cleared land into the sea. The silt clouds the water so plankton "
             "can't grow and smothers shellfish beds.",
             [("Plant Mānuka on bare slopes to stop erosion.", ("species", "Mānuka")),
              ("Protect forest so soil stays on the land.", ("tool", "sanctuary"))],
             "Sediment from land erosion is one of the biggest threats to New Zealand's harbours and "
             "estuaries, smothering shellfish beds such as cockles and pipi.",
             cooldown_days=5)


def alert_voyage(w, t, ship):
    post(w, "voyage%d%s" % (t.id, ship.cargo), "warn", "The %s sent a ship to fetch %s" % (t.name, ship.cargo),
         ship.reason + " The ship will be gone for a couple of weeks.",
         "As settlements grow, people try to fix their problems by bringing in species from elsewhere - "
         "often without knowing the damage those species will do. Ships can also carry stowaway rats.",
         [("Raise Biosecurity - fewer voyages, and fewer stowaways.", ("slider", "biosecurity", 0.95)),
          TRAP_HELP],
         "Many of New Zealand's worst pests were brought in deliberately to solve a problem: possums for fur, "
         "rabbits for food, stoats to control the rabbits, gorse for hedges, pines for timber.",
         pos=(ship.x, ship.y), cooldown_days=0)
