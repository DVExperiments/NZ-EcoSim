"""
species_nz.py - the plants and animals of Terrarium: Aotearoa New Zealand edition.

Sizes, speeds and rates are game values tuned for the simulation, not real
measurements.  Each species carries a short educational blurb.
"""
import random
import colorsys

DAY_TICKS = 720


def hue_color(h, s=0.65, v=0.85):
    r, g, b = colorsys.hsv_to_rgb(h % 1.0, s, v)
    return (int(r * 255), int(g * 255), int(b * 255))


SYL = ["mo", "ka", "zu", "li", "ve", "tor", "ra", "shi", "pel", "dra", "no", "qui",
       "bel", "fen", "gri", "lo", "mi", "sa", "tu", "vor", "ex", "ul", "ny", "ash"]
ANIMAL_SUFFIX = ["", "", " vole", " newt", " moth", " shrew", " hopper", " lynx", " crake", " mite"]
PLANT_SUFFIX = ["", "", " weed", " bloom", " moss", " reed", " thorn", " vine", " cap", " wort"]


def random_name(kind="animal"):
    n = "".join(random.choice(SYL) for _ in range(random.randint(2, 3))).capitalize()
    return n + random.choice(ANIMAL_SUFFIX if kind == "animal" else PLANT_SUFFIX)


TRIBE_ADJ = ["Red", "Grey", "Ember", "Stone", "River", "Ash", "Swift", "Iron", "Moss", "Storm",
             "Salt", "Cloud", "Amber", "Raven", "Willow", "Thorn", "Dawn", "Frost", "Tide", "Copper"]
TRIBE_NOUN = ["Heron", "Hill", "Brook", "Fern", "Stag", "Shore", "Lantern", "Ridge", "Harbour", "Fox",
              "Valley", "Hearth", "Wind", "Crow", "Field", "Oak", "Gate", "Meadow", "Stream", "Bluff"]
TRIBE_KIND = ["Tribe", "Clan", "Folk", "People", "Band"]
TRIBE_COLORS = [(230, 80, 70), (80, 140, 235), (240, 180, 50), (180, 90, 220), (60, 200, 200),
                (240, 120, 180), (150, 210, 80), (250, 140, 60), (120, 120, 250), (210, 210, 210)]


def tribe_name(taken=()):
    used = {t.split()[0] for t in taken}
    for _ in range(80):
        n = "%s %s %s" % (random.choice(TRIBE_ADJ), random.choice(TRIBE_NOUN), random.choice(TRIBE_KIND))
        if n not in taken and n.split()[0] not in used:
            return n
    return n


# ----------------------------------------------------------------------------
class PlantSpecies:
    kind = "plant"

    def __init__(self, name, color, growth, water, light, topt, trange, spread, maxb,
                 edible, flamm, flower=None, aquatic=False, maxw=9.0, native=True,
                 tree=False, pioneer=False, mast=False, fixer=False, english="", latin="", blurb=""):
        self.name, self.color = name, tuple(color)
        self.growth, self.water, self.light = growth, water, light
        self.topt, self.trange, self.spread, self.maxb = topt, trange, spread, maxb
        self.edible, self.flamm = edible, flamm
        self.flower = tuple(flower) if flower else None
        self.aquatic, self.maxw, self.native = aquatic, maxw, native
        self.tree, self.pioneer, self.mast, self.fixer = tree, pioneer, mast, fixer
        self.english, self.latin, self.blurb = english, latin, blurb

    @property
    def origin(self):
        return "native" if self.native else "introduced"


class AnimalSpecies:
    kind = "animal"

    def __init__(self, name, color, diet, size, speed, litter, topt, trange, max_age,
                 metab, vision, flier=False, swimmer=False, activity="day",
                 breeds_in_water=False, native=True, naive=False, prey=None, nest_raider=False,
                 bird=False, climber=False, commensal=False, browser=False, disperser=False,
                 mast_breeder=False, trappable=False, carry=150, marine=False, english="", latin="", blurb="",
                 hides=False):
        self.name, self.color = name, tuple(color)
        self.diet = set(diet)
        self.size, self.speed, self.litter = size, speed, litter
        self.topt, self.trange, self.max_age = topt, trange, max_age
        self.metab, self.vision = metab, vision
        self.flier, self.swimmer, self.activity = flier, swimmer, activity
        self.breeds_in_water, self.native = breeds_in_water, native
        self.naive = naive                  # evolved without mammals: doesn't flee them
        self.prey = set(prey) if prey else None
        self.nest_raider = nest_raider      # eats eggs / chicks of birds
        self.bird, self.climber, self.commensal = bird, climber, commensal
        self.browser, self.disperser, self.mast_breeder = browser, disperser, mast_breeder
        self.trappable = trappable
        self.carry = carry                  # natural carrying capacity (crowding limits breeding)
        self.marine = marine                # lives at sea, comes ashore only on the coast
        self.hides = hides                  # rests hidden in burrows / tree holes
        self.invert_eff = 1.0               # how well it lives on insects and worms
        self.mast_boom = False
        self.english, self.latin, self.blurb = english, latin, blurb
        # life history (overwritten by apply_life_history for species with real data)
        self.mature_frac = 0.2
        self.breed_gap = max_age * 0.13
        self.young_ticks = max_age * 0.2
        self.life = None
        apply_life_history(self)

    @property
    def origin(self):
        return "native" if self.native else "introduced"


# ----------------------------------------------------------------------------
# Real-world life history (typical wild values).
#   life      typical maximum lifespan in the wild (years)
#   mature    age at first breeding (years)
#   broods    breeding attempts per year
#   brood     young per attempt (eggs / litter)
#   young     how long eggs, chicks or young are easy prey for nest raiders (years)
#   survive   share of young that live to adulthood without introduced predators
# Sources: NZ Department of Conservation, Te Ara Encyclopedia of NZ, Landcare Research,
# NZ Birds Online.  Insect values (weta) are for tree weta.
# ----------------------------------------------------------------------------
LIFE = {
    "Wētā":      dict(life=2.0,  mature=0.8,  broods=2.0, brood=100.0, young=0.4, survive=0.06),
    "Kiwi":      dict(life=35.0, mature=3.0,  broods=1.5, brood=1.5, young=0.6, survive=0.50),
    "Kākāpō":    dict(life=75.0, mature=7.0,  broods=1.0, brood=2.5, young=0.5, survive=0.60),
    "Tūī":       dict(life=10.0, mature=1.0,  broods=2.0, brood=3.0, young=0.1, survive=0.35),
    "Kererū":    dict(life=20.0, mature=1.5,  broods=1.5, brood=1.0, young=0.15, survive=0.55),
    "Ruru":      dict(life=12.0, mature=1.5,  broods=1.0, brood=2.5, young=0.15, survive=0.40),
    "Kārearea":  dict(life=12.0, mature=2.0,  broods=1.0, brood=3.0, young=0.15, survive=0.35),
    "Takahē":    dict(life=18.0, mature=2.0,  broods=1.0, brood=2.0, young=0.5, survive=0.50),
    "Kekeno":    dict(life=18.0, mature=4.0,  broods=1.0, brood=1.0, young=0.3, survive=0.60),
    "Kororā":    dict(life=7.0,  mature=2.5,  broods=1.3, brood=2.0, young=0.2, survive=0.45),
    "Ship rat":  dict(life=1.0,  mature=0.25, broods=4.0, brood=6.0, young=0.05, survive=0.30),
    "Possum":    dict(life=10.0, mature=1.5,  broods=1.2, brood=1.0, young=0.3, survive=0.55),
    "Stoat":     dict(life=1.5,  mature=0.5,  broods=1.0, brood=9.0, young=0.1, survive=0.40),
    "Feral cat": dict(life=4.0,  mature=0.8,  broods=1.5, brood=4.0, young=0.15, survive=0.35),
    "Red deer":  dict(life=15.0, mature=2.0,  broods=1.0, brood=1.0, young=0.3, survive=0.70),
    "Rabbit":    dict(life=2.0,  mature=0.3,  broods=5.0, brood=5.0, young=0.05, survive=0.30),
}


def apply_life_history(sp):
    """Turn real-world life history into simulation ticks (same biological clock for everyone).
    Every simulated animal can breed, so the per-individual rate is half the per-female rate,
    and only the young that would survive to independence are simulated."""
    from config import BIO_YEAR
    d = LIFE.get(sp.name)
    if d is None:
        return
    sp.life = d
    sp.max_age = d["life"] * BIO_YEAR
    sp.mature_frac = min(0.6, d["mature"] / d["life"])
    sp.breed_gap = BIO_YEAR / d["broods"]
    sp.litter = d["brood"] * d["survive"] * 0.5          # per individual: half the population is male
    sp.young_ticks = d["young"] * BIO_YEAR
    # rats, stoats and cats eat insects, but can't live on them alone (kiwi and morepork can)
    sp.invert_eff = {"Ship rat": 0.35, "Stoat": 0.3, "Feral cat": 0.3}.get(sp.name, 1.0)
    sp.mast_boom = sp.name in ("Ship rat",)     # rodents boom on mast seed, then crash


class SimpleEntry:
    """Fungi, microbes and humans are not ordinary species."""

    def __init__(self, kind, name, color, blurb=""):
        self.kind, self.name, self.color, self.blurb = kind, name, color, blurb
        self.native = True

    @property
    def origin(self):
        return "native"


# ----------------------------------------------------------------------------
# plants
# ----------------------------------------------------------------------------
def native_plants(region="north"):
    extra = []
    if region == "north":
        extra.append(PlantSpecies("Kauri", (36, 92, 62), .006, .14, .35, 15, 11, .0006, 2.6, .15, .3, tree=True,
                                  english="Kauri", latin="Agathis australis",
                                  blurb="Giant conifer of the northern North Island that can live for well over a "
                                        "thousand years. Now threatened by kauri dieback disease."))
    else:
        extra.append(PlantSpecies("Tawhai", (52, 98, 66), .009, .17, .25, 9, 12, .0009, 2.0, .2, .4, tree=True,
                                  mast=True, english="Southern beech", latin="Nothofagus / Fuscospora",
                                  blurb="Beech forest covers much of the South Island. Heavy beech mast years "
                                        "trigger plagues of rats, mice and stoats."))
    return extra + [
        PlantSpecies("Tussock", (196, 172, 96), .028, .16, .50, 11, 14, .0040, .60, .6, .9, mast=True,
                     english="Tussock grass", latin="Chionochloa / Poa",
                     blurb="Golden bunch grasses of the high country. Snow tussock seeds heavily in mast years."),
        PlantSpecies("Harakeke", (78, 120, 66), .022, .45, .50, 14, 12, .0020, .90, .3, .4,
                     flower=(170, 50, 40), english="NZ flax", latin="Phormium tenax",
                     blurb="Flax of wetland edges. Its nectar-rich flowers feed tui; its fibre was woven for centuries."),
        PlantSpecies("Raupō", (128, 150, 82), .024, .60, .40, 15, 12, .0018, .90, .4, .6, aquatic=True,
                     english="Bulrush", latin="Typha orientalis",
                     blurb="Reedbeds of shallow swamps. Wetlands like these filter water and shelter birds."),
        PlantSpecies("Mānuka", (112, 138, 88), .021, .14, .60, 14, 14, .0035, 1.0, .2, 1.0,
                     flower=(236, 232, 224), pioneer=True,
                     english="Tea tree", latin="Leptospermum scoparium",
                     blurb="Hardy pioneer shrub. It quickly covers bare or burnt land and shelters young forest trees."),
        PlantSpecies("Ponga", (40, 112, 82), .022, .40, .12, 13, 10, .0022, 1.0, .5, .4,
                     english="Silver fern", latin="Alsophila dealbata",
                     blurb="Tree fern of the shady understorey. The silver underside of its fronds is a national symbol."),
        PlantSpecies("Kōwhai", (66, 116, 52), .012, .16, .45, 14, 12, .0013, 1.6, .5, .5,
                     flower=(250, 214, 40), tree=True,
                     english="Kowhai", latin="Sophora spp.",
                     blurb="Small tree with golden spring flowers, a favourite of tui. Possums strip its leaves."),
        PlantSpecies("Rimu", (28, 84, 52), .007, .15, .20, 12, 12, .0008, 2.4, .3, .4, tree=True, mast=True,
                     english="Red pine", latin="Dacrydium cupressinum",
                     blurb="Giant podocarp that can live for centuries. Its fruit crops are irregular - and kakapo only breed when it masts."),
    ]


def introduced_plants():
    return [
        PlantSpecies("Gorse", (150, 150, 60), .030, .10, .65, 14, 15, .0040, 1.0, .05, 1.0,
                     flower=(250, 222, 30), pioneer=True, fixer=True, native=False,
                     english="Gorse", latin="Ulex europaeus",
                     blurb="Spiny European shrub brought as hedging. Invasive and highly flammable - but it can nurse native seedlings."),
        PlantSpecies("Wilding pine", (54, 92, 70), .016, .14, .55, 12, 14, .0026, 1.8, .05, .8, tree=True,
                     native=False, english="Wilding conifer", latin="Pinus contorta / radiata",
                     blurb="Pines that spread from plantations on the wind, smothering tussock grasslands."),
    ]


# ----------------------------------------------------------------------------
# animals
# ----------------------------------------------------------------------------
D = DAY_TICKS
BIRDS = {"Kiwi", "Kākāpō", "Tūī", "Kererū", "Ruru", "Kārearea", "Takahē", "Kororā"}


def native_animals(region="north"):
    extra = []
    if region == "south":
        extra.append(AnimalSpecies("Takahē", (60, 110, 170), ["plant"], 1.5, .07, 1, 8, 14, 20 * D,
                                   .00028, 7, activity="day", naive=True, bird=True, carry=30,
                                   english="Takahe", latin="Porphyrio hochstetteri",
                                   blurb="Large flightless rail of the South Island's alpine tussock. Thought extinct, "
                                         "it was rediscovered in Fiordland in 1948."))
    marine = [
        AnimalSpecies("Kekeno", (96, 82, 70), ["fish"], 1.6, .22, 1, 12, 16, 16 * D,
                      .00034, 12, swimmer=True, marine=True, activity="any", carry=40,
                      english="NZ fur seal", latin="Arctocephalus forsteri",
                      blurb="Fur seals hunt fish and squid at sea and haul out on rocky coasts. Sealers nearly wiped "
                            "them out in the 1800s; protected since, they have recovered."),
        AnimalSpecies("Kororā", (90, 110, 150), ["fish"], .50, .20, 2, 12, 14, 9 * D,
                      .00045, 10, swimmer=True, marine=True, activity="any", naive=True, bird=True, carry=60,
                      english="Little penguin", latin="Eudyptula minor",
                      blurb="The world's smallest penguin. It fishes at sea by day and nests ashore, where dogs, cats "
                            "and stoats kill many."),
    ]
    return extra + marine + [
        AnimalSpecies("Wētā", (150, 96, 54), ["plant", "fungus", "detritus"], .30, .08, 3, 13, 14, 5 * D,
                      .0008, 6, activity="night", naive=True,
                      carry=220, english="Weta", latin="Deinacrida & others", hides=True,
                      blurb="Giant insects that fill the role mice play elsewhere. Some are among the heaviest insects on Earth."),
        AnimalSpecies("Kiwi", (128, 98, 66), ["meat", "invert"], 1.0, .13, 1, 12, 14, 22 * D,
                      .00032, 8, activity="night", naive=True, bird=True, prey=["Wētā"],
                      carry=60, english="Kiwi", latin="Apteryx spp.",
                      blurb="Flightless, nocturnal bird that sniffs out invertebrates with nostrils at the tip of its bill. Chicks are easy prey for stoats and cats."),
        AnimalSpecies("Kākāpō", (122, 170, 70), ["plant", "seed"], 1.4, .06, 2, 12, 14, 150 * D,
                      .00022, 7, activity="night", naive=True, bird=True, mast_breeder=True,
                      carry=30, english="Owl parrot", latin="Strigops habroptilus",
                      blurb="Heaviest parrot in the world, flightless and nocturnal. Critically endangered; it breeds only when rimu masts."),
        AnimalSpecies("Tūī", (60, 70, 110), ["nectar", "plant"], .50, .32, 2, 14, 12, 7 * D,
                      .00048, 14, flier=True, activity="day", naive=True, bird=True, disperser=True,
                      carry=110, english="Tui", latin="Prosthemadera novaeseelandiae",
                      blurb="Honeyeater with a white throat tuft. A key pollinator of kowhai, flax and many native plants."),
        AnimalSpecies("Kererū", (90, 150, 120), ["plant"], .80, .28, 1, 13, 13, 12 * D,
                      .00034, 14, flier=True, activity="day", naive=True, bird=True, disperser=True,
                      carry=60, english="NZ pigeon", latin="Hemiphaga novaeseelandiae",
                      blurb="Big native pigeon - now the main bird able to swallow and spread the large fruits of many native trees."),
        AnimalSpecies("Ruru", (150, 120, 84), ["meat", "invert"], 1.0, .34, 1, 12, 14, 12 * D,
                      .00045, 14, flier=True, activity="night", bird=True,
                      prey=["Wētā", "Ship rat"],
                      carry=24, english="Morepork", latin="Ninox novaeseelandiae",
                      blurb="Small native owl named for its call. Hunts insects like weta, small birds and rodents at night."),
        AnimalSpecies("Kārearea", (110, 96, 120), ["meat"], 1.2, .44, 2, 12, 16, 14 * D,
                      .00042, 18, flier=True, activity="day", bird=True,
                      prey=["Tūī", "Ship rat", "Rabbit", "Wētā"],
                      carry=12, english="NZ falcon", latin="Falco novaeseelandiae",
                      blurb="Fast, fierce native falcon that hunts other birds on the wing."),
    ]


def introduced_animals():
    return [
        AnimalSpecies("Ship rat", (110, 110, 110), ["seed", "meat", "invert"], .45, .20, 3, 15, 16,
                      4 * D, .0007, 9, activity="night", native=False, prey=["Wētā"], nest_raider=True,
                      climber=True, commensal=True, trappable=True,
                      carry=200, english="Ship rat", latin="Rattus rattus",
                      blurb="Climbing rat that arrived on ships. Raids nests, eats seeds, insects and lizards; populations explode in mast years."),
        AnimalSpecies("Possum", (120, 100, 90), ["plant"], 1.0, .14, 1, 13, 15, 12 * D,
                      .0004, 10, activity="night", native=False, nest_raider=True, climber=True,
                      browser=True, trappable=True,
                      carry=200, english="Brushtail possum", latin="Trichosurus vulpecula",
                      blurb="Brought from Australia for fur in the 1800s. Strips forest canopy, eats eggs and chicks, and spreads bovine TB."),
        AnimalSpecies("Stoat", (190, 150, 90), ["meat", "invert"], .70, .32, 3, 12, 16, 6 * D,
                      .0009, 14, activity="any", native=False, nest_raider=True, climber=True, trappable=True,
                      prey=["Ship rat", "Rabbit", "Wētā"],
                      carry=60, english="Stoat", latin="Mustela erminea",
                      blurb="Released in the 1880s to control rabbits. Instead it became the No.1 killer of kiwi chicks."),
        AnimalSpecies("Feral cat", (60, 56, 52), ["meat", "invert"], 1.1, .30, 2, 14, 18, 12 * D,
                      .0006, 15, activity="any", native=False, nest_raider=True, climber=True, trappable=True,
                      prey=["Ship rat", "Rabbit", "Tūī", "Wētā", "Kererū"],
                      carry=40, english="Feral cat", latin="Felis catus",
                      blurb="Pets gone wild. Feral cats hunt birds, lizards, insects and even adult kiwi."),
        AnimalSpecies("Red deer", (170, 100, 60), ["plant"], 2.0, .25, 1, 10, 18, 16 * D,
                      .00035, 14, activity="day", native=False, browser=True,
                      carry=110, english="Red deer", latin="Cervus elaphus",
                      blurb="Released for hunting. With no natural predators, deer browse away the forest understorey."),
        AnimalSpecies("Rabbit", (200, 190, 170), ["plant"], .90, .26, 4, 14, 18, 5 * D,
                      .0006, 10, activity="any", native=False, trappable=True,
                      carry=260, english="European rabbit", latin="Oryctolagus cuniculus",
                      blurb="Released for food and sport, rabbits stripped grasslands bare and led to stoats being introduced."),
    ]
