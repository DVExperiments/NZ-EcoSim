"""
views.py - the bigger windows of Terrarium: the New Island generator and the People & Clans panel,
plus plain-language descriptions of what an animal is doing.
"""
import math
import random

import numpy as np
import pygame

from config import GW, GH, DAY_TICKS, CAL_DAY, YEAR_TICKS, HOUSE, FIELD, RUIN, age_text, bio_age_text, BIO_YEAR
from ui_kit import (PANEL, PANEL2, LINE, TEXT, DIM, ACCENT, SEL, HOVER, GRAPH, TIP, INPUT, GRID, BG,
                    draw_text, wrap, Slider, Button, draw_pie, THEMES)
_THEMED = True
from world import make_terrain, terrain_preview, GEOGRAPHIES, DEFAULT_OPTS
import humans

ROLE_COLORS = {"child": (170, 200, 240), "warrior": (230, 90, 80), "builder": (190, 140, 90), "farmer": (220, 200, 90),
               "hunter": (230, 150, 70), "gatherer": (120, 190, 110), "fisher": (90, 160, 220)}

REGION_TEXT = {
    "north": "Warmer, with kauri forest in the north, plenty of kiwi, tui and kereru, and only small "
             "alpine areas.",
    "south": "Colder, with beech forest, wide tussock high country, snowy peaks, takahe and more kakapo.",
}
GEO_TEXT = {
    "big": "One large island with a mountain range.",
    "archipelago": "A scatter of small islands - like the many offshore islands of Aotearoa.",
    "mountainous": "",
    "mountains": "Rugged ranges and high snowy country.",
    "lowlands": "Low, rolling country with few mountains.",
    "lakes": "An island dotted with inland lakes and wetlands.",
}


def shade(scr, alpha=165):
    s = pygame.Surface(scr.get_size(), pygame.SRCALPHA)
    s.fill((0, 0, 0, alpha))
    scr.blit(s, (0, 0))


# ----------------------------------------------------------------------------
# New island
# ----------------------------------------------------------------------------
class NewWorldView:
    W, H = 900, 620

    def __init__(self, app, first=False):
        self.app = app
        self.first = first
        sw, sh = app.screen.get_size()
        self.rect = pygame.Rect((sw - self.W) // 2, (sh - self.H) // 2, self.W, self.H)
        self.opts = dict(DEFAULT_OPTS)
        self.opts["difficulty"] = getattr(app.world, "difficulty", "realistic") if app.world else "realistic"
        self.seed = random.randrange(1 << 30)
        self.sliders = [
            Slider("land", "Land area", 0.3, 0.75, self.opts["land"], "{:.0%}"),
            Slider("mountains", "Mountains", 0.0, 1.0, self.opts["mountains"], "{:.0%}"),
            Slider("forest", "Starting forest cover", 0.3, 0.95, self.opts["forest"], "{:.0%}"),
            Slider("wetness", "Rainfall", 0.4, 1.6, self.opts["wetness"], "{:.2f}"),
        ]
        self.key = None
        self.preview = None
        self.buttons = []

    def current_key(self):
        for s in self.sliders:
            self.opts[s.key] = s.value
        return (self.seed, self.opts["region"], self.opts["geo"],
                round(self.opts["land"], 2), round(self.opts["mountains"], 2))

    def regen(self):
        h, sea = make_terrain(self.seed, self.opts)
        rgb = terrain_preview(h, sea, self.opts["region"])
        self.preview = pygame.transform.scale(pygame.surfarray.make_surface(rgb), (420, 262))
        self.land = float((~sea).mean())

    def set(self, k, v):
        self.opts[k] = v

    def reroll(self):
        self.seed = random.randrange(1 << 30)

    def start(self):
        for s in self.sliders:
            self.opts[s.key] = s.value
        from world import World
        self.app.set_world(World(self.seed, dict(self.opts)))
        self.app.newworld = None
        self.app.toast("A new island: %s Island, %s." % (self.opts["region"].capitalize(),
                                                          dict(GEOGRAPHIES)[self.opts["geo"]]))
        if self.first:
            self.app.show_help = True

    def draw(self, scr, f, mouse):
        if not any(s.drag for s in self.sliders):
            k = self.current_key()
            if k != self.key:
                self.key = k
                self.regen()
        shade(scr)
        r = self.rect
        pygame.draw.rect(scr, PANEL, r, border_radius=10)
        pygame.draw.rect(scr, LINE, r, 1, border_radius=10)
        draw_text(scr, f, "Create a new island", (r.x + 24, r.y + 18), TEXT, f.l)
        draw_text(scr, f, "Choose where and what kind of land - every island is generated fresh.",
                  (r.x + 24, r.y + 50), DIM)
        px, py = r.x + 24, r.y + 80
        scr.blit(self.preview, (px, py))
        pygame.draw.rect(scr, LINE, (px, py, 420, 262), 1)
        draw_text(scr, f, "Preview  -  seed %d  -  %d%% land" % (self.seed, self.land * 100), (px, py + 268), DIM, f.xs)
        self.buttons = []
        b = Button("New random seed", self.reroll)
        b.draw(scr, f, (px + 280, py + 266, 140, 24), b.rect.collidepoint(mouse), f.xs)
        self.buttons.append(b)
        # region text under the preview
        y = py + 304
        draw_text(scr, f, "%s Island" % self.opts["region"].capitalize(), (px, y), ACCENT, f.b)
        for i, ln in enumerate(wrap(REGION_TEXT[self.opts["region"]], f.s, 420)):
            draw_text(scr, f, ln, (px, y + 20 + i * 17), TEXT)
        y += 20 + 17 * 3 + 6
        for i, ln in enumerate(wrap(GEO_TEXT.get(self.opts["geo"], ""), f.s, 420)):
            draw_text(scr, f, ln, (px, y + i * 17), DIM)
        # right column
        x = r.x + 470
        w = r.right - 24 - x
        y = r.y + 80
        draw_text(scr, f, "REGION", (x, y), ACCENT, f.b)
        y += 22
        for i, (k, lab) in enumerate([("north", "North Island"), ("south", "South Island")]):
            b = Button(lab, lambda k=k: self.set("region", k), lambda k=k: self.opts["region"] == k)
            b.draw(scr, f, (x + i * (w // 2 + 3), y, w // 2 - 3, 28), b.rect.collidepoint(mouse), f.b)
            self.buttons.append(b)
        y += 42
        draw_text(scr, f, "GEOGRAPHY", (x, y), ACCENT, f.b)
        y += 22
        bw = (w - 8) // 3
        for i, (k, lab) in enumerate(GEOGRAPHIES):
            b = Button(lab, lambda k=k: self.set("geo", k), lambda k=k: self.opts["geo"] == k)
            b.draw(scr, f, (x + (i % 3) * (bw + 4), y + (i // 3) * 30, bw, 26), b.rect.collidepoint(mouse), f.s)
            self.buttons.append(b)
        y += 70
        draw_text(scr, f, "TWEAKS", (x, y), ACCENT, f.b)
        y += 24
        for s in self.sliders:
            s.draw(scr, f, x, y, w)
            y += 38
        from config import DIFFICULTIES, DIFFICULTY_ORDER
        draw_text(scr, f, "DIFFICULTY", (x, y), ACCENT, f.b)
        y += 22
        bw = (w - 12) // 3
        self.opts.setdefault("difficulty", getattr(self.app.world, "difficulty", "realistic"))
        for i, k in enumerate(DIFFICULTY_ORDER):
            b = Button(DIFFICULTIES[k]["label"], lambda k=k: self.set("difficulty", k),
                       lambda k=k: self.opts["difficulty"] == k)
            b.draw(scr, f, (x + i * (bw + 6), y, bw, 26), b.rect.collidepoint(mouse))
            self.buttons.append(b)
        y += 32
        for i, ln in enumerate(wrap(DIFFICULTIES[self.opts["difficulty"]]["blurb"], f.xs, w)[:3]):
            draw_text(scr, f, ln, (x, y + i * 14), DIM, f.xs)
        b = Button("Start simulation", self.start)
        b.draw(scr, f, (r.right - 200, r.bottom - 50, 176, 32), b.rect.collidepoint(mouse), f.b)
        self.buttons.append(b)
        if not self.first:
            b = Button("Cancel", lambda: setattr(self.app, "newworld", None))
            b.draw(scr, f, (r.right - 300, r.bottom - 50, 90, 32), b.rect.collidepoint(mouse))
            self.buttons.append(b)
            draw_text(scr, f, "Starting a new island replaces the current one.", (r.x + 24, r.bottom - 42), DIM, f.xs)

    def handle(self, ev, pos):
        if ev.type == pygame.KEYDOWN:
            if ev.key == pygame.K_ESCAPE and not self.first:
                self.app.newworld = None
            elif ev.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self.start()
            return
        for s in self.sliders:
            if s.handle(ev, pos):
                return
        if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            for b in self.buttons:
                if b.handle(ev, pos):
                    return


# ----------------------------------------------------------------------------
# People & clans
# ----------------------------------------------------------------------------
class ClansView:
    W, H = 1060, 640

    def __init__(self, app, tid=None):
        self.app = app
        sw, sh = app.screen.get_size()
        self.rect = pygame.Rect((sw - self.W) // 2, (sh - self.H) // 2, self.W, self.H)
        live = [t for t in app.world.tribes if t.alive]
        self.tid = tid if tid is not None else (live[0].id if live else None)
        self.buttons = []
        self.rows = []

    def minimap(self, scr, x, y, w, h):
        wd = self.app.world
        rgb = np.zeros((GW, GH, 3), np.uint8)
        rgb[...] = (34, 60, 92)
        rgb[wd.land] = (70, 78, 70)
        rgb[wd.land & (wd.height > 0.62)] = (110, 112, 110)
        rgb[(wd.water > 0.2) & wd.land] = (50, 90, 130)
        if wd.sanctuary.any():
            rgb[wd.sanctuary & wd.land] = (60, 110, 100)
        built = (wd.struct == HOUSE) | (wd.struct == FIELD)
        if built.any():
            xs, ys = np.nonzero(built & (wd.owner >= 0))
            for bx, by in zip(xs, ys):
                t = wd.tribes[int(wd.owner[bx, by])]
                c = t.color if wd.struct[bx, by] == HOUSE else tuple(int(v * 0.6) for v in t.color)
                rgb[bx, by] = c
        rgb[wd.struct == RUIN] = (40, 36, 34)
        surf = pygame.transform.scale(pygame.surfarray.make_surface(rgb), (w, h))
        scr.blit(surf, (x, y))
        pygame.draw.rect(scr, LINE, (x, y, w, h), 1)
        sx, sy = w / GW, h / GH
        f = self.app.fonts
        for t in wd.tribes:
            if not t.alive:
                continue
            cx, cy = int(x + t.x * sx), int(y + t.y * sy)
            rad = int(humans.territory_radius(t) * sx)
            pygame.draw.circle(scr, t.color, (cx, cy), max(3, rad), 2 if t.id == self.tid else 1)
            for o in t.war:
                ot = wd.tribes[o]
                if o > t.id:
                    pygame.draw.line(scr, (240, 80, 70), (cx, cy), (int(x + ot.x * sx), int(y + ot.y * sy)), 2)
            draw_text(scr, f, t.name.split()[0], (cx, cy - max(3, rad) - 2), t.color, f.xs, "midbottom")

    def draw(self, scr, f, mouse):
        wd = self.app.world
        shade(scr)
        r = self.rect
        pygame.draw.rect(scr, PANEL, r, border_radius=10)
        pygame.draw.rect(scr, LINE, r, 1, border_radius=10)
        draw_text(scr, f, "People & clans", (r.x + 24, r.y + 16), TEXT, f.l)
        draw_text(scr, f, wd.date, (r.x + 220, r.y + 24), DIM)
        self.buttons = []
        self.rows = []
        b = Button("Close", lambda: setattr(self.app, "clans", None))
        b.draw(scr, f, (r.right - 100, r.y + 16, 76, 26), b.rect.collidepoint(mouse))
        self.buttons.append(b)
        live = [t for t in wd.tribes if t.alive]
        if not live:
            msg = ("No people live on the island yet. Pick Humans in the Add life tab and click the map to land "
                   "a group of settlers. Their clan will appear here.")
            for i, ln in enumerate(wrap(msg, f.m, r.w - 60)):
                draw_text(scr, f, ln, (r.x + 30, r.y + 80 + i * 22), TEXT, f.m)
            gone = [t for t in wd.tribes if not t.alive]
            if gone:
                draw_text(scr, f, "Clans that have disappeared: " + ", ".join(t.name for t in gone),
                          (r.x + 30, r.y + 150), DIM)
            return
        if self.tid is None or not wd.tribes[self.tid].alive:
            self.tid = live[0].id
        # ---------- left column: overview
        x = r.x + 24
        y = r.y + 58
        roles = {}
        for p in wd.people:
            roles[p.role] = roles.get(p.role, 0) + 1
        wars = sum(len(t.war) for t in live) // 2
        draw_text(scr, f, "%d people in %d clans  -  %d war%s" % (len(wd.people), len(live), wars,
                                                                 "" if wars == 1 else "s"),
                  (x, y), TEXT, f.b)
        y += 24
        # tribes pie + roles pie
        tribe_items = sorted([(t.pop, t.color, t.name) for t in live], key=lambda a: -a[0])
        draw_pie(scr, (x + 52, y + 52), 50, [(a[0], a[1]) for a in tribe_items], hole=0.45)
        draw_text(scr, f, "Clans", (x + 52, y + 52), TEXT, f.xs, "center")
        role_items = sorted([(n, ROLE_COLORS.get(k, DIM), k) for k, n in roles.items()], key=lambda a: -a[0])
        draw_pie(scr, (x + 52 + 170, y + 52), 50, [(a[0], a[1]) for a in role_items], hole=0.45)
        draw_text(scr, f, "Jobs", (x + 52 + 170, y + 52), TEXT, f.xs, "center")
        tot = max(1, sum(a[0] for a in tribe_items))
        for i, (n, c, name) in enumerate(tribe_items[:6]):
            pygame.draw.rect(scr, c, (x + 108, y + 4 + i * 15, 8, 8))
            draw_text(scr, f, "%s %d%%" % (name.split()[0], 100 * n / tot), (x + 120, y + i * 15), TEXT, f.xs)
        for i, (n, c, name) in enumerate(role_items[:7]):
            pygame.draw.rect(scr, c, (x + 278, y + 4 + i * 15, 8, 8))
            draw_text(scr, f, "%s %d" % (name, n), (x + 290, y + i * 15), TEXT, f.xs)
        y += 118
        draw_text(scr, f, "Where they have built", (x, y), ACCENT, f.b)
        draw_text(scr, f, "houses bright, fields dim, red lines = war", (x + 360, y + 2), DIM, f.xs, "topright")
        y += 20
        self.minimap(scr, x, y, 360, 225)
        y += 232
        draw_text(scr, f, "Totals: %d houses, %d fields, %d animals hunted, %.0f fish caught" % (
            int((wd.struct == HOUSE).sum()), int((wd.struct == FIELD).sum()), sum(t.kills for t in wd.tribes),
            sum(t.fish_caught for t in wd.tribes)), (x, y), DIM, f.xs)
        draw_text(scr, f, "Deaths: %s" % (", ".join("%s %d" % kv for kv in sorted(wd.human_deaths.items(),
                                                                              key=lambda kv: -kv[1])) or "none"),
                  (x, y + 15), DIM, f.xs, maxw=360)
        # ---------- clan list
        lx = r.x + 410
        lw = r.right - 24 - lx
        y = r.y + 58
        draw_text(scr, f, "CLANS (click one)", (lx, y), ACCENT, f.b)
        y += 20
        for t in sorted(live, key=lambda t: -t.pop)[:7]:
            row = pygame.Rect(lx, y, lw, 22)
            on = t.id == self.tid
            pygame.draw.rect(scr, SEL if on else (PANEL2 if not row.collidepoint(mouse) else HOVER), row,
                             border_radius=4)
            pygame.draw.circle(scr, t.color, (row.x + 11, row.centery), 6)
            draw_text(scr, f, t.name, (row.x + 24, row.centery), TEXT, f.s, "midleft", maxw=220)
            status = ("AT WAR" if t.war else "at peace") + "  -  " + humans.mood_label(t.stress).lower()
            draw_text(scr, f, "%d people  %d house%s  %d fields" % (t.pop, t.houses, "" if t.houses == 1 else "s",
                                                                   t.fields), (row.x + 250, row.centery),
                      DIM, f.xs, "midleft")
            draw_text(scr, f, status, (row.right - 8, row.centery), (240, 100, 90) if t.war else ACCENT, f.xs,
                      "midright")
            self.rows.append((row, t.id))
            y += 25
        # ---------- selected clan
        t = wd.tribes[self.tid]
        y += 8
        pygame.draw.line(scr, LINE, (lx, y), (lx + lw, y))
        y += 8
        draw_text(scr, f, t.name, (lx, y), t.color, f.l, maxw=lw - 150)
        b = Button("Locate on map", lambda t=t: self.app.locate_tribe(t))
        b.draw(scr, f, (r.right - 160, y, 136, 26), b.rect.collidepoint(mouse))
        self.buttons.append(b)
        y += 30
        draw_text(scr, f, "Founded %s  -  %d people (peak %d)  -  food %.0f (%.1f days)  -  wood %.0f  -  hunted %d" % (
            getattr(t, "founded_date", "?"), t.pop, t.peak, t.food, humans.food_days(t), t.wood, t.kills),
            (lx, y), DIM, f.xs, maxw=lw)
        y += 20
        lines, troles = humans.describe_tribe(wd, t)
        half = lw // 2 - 10
        yy = y
        draw_text(scr, f, "What they're doing and why", (lx, yy), ACCENT, f.b)
        yy += 20
        for ln in lines:
            for wl in wrap(ln, f.s, half):
                draw_text(scr, f, wl, (lx, yy), TEXT)
                yy += 16
            yy += 3
        # jobs bar
        bx, by = lx, yy + 4
        total = max(1, sum(troles.values()))
        cur = bx
        for role, n in sorted(troles.items(), key=lambda kv: -kv[1]):
            wpx = int(half * n / total)
            pygame.draw.rect(scr, ROLE_COLORS.get(role, DIM), (cur, by, wpx, 10))
            cur += wpx
        draw_text(scr, f, "  ".join("%s %d" % (k, v) for k, v in sorted(troles.items(), key=lambda kv: -kv[1])),
                  (bx, by + 13), DIM, f.xs, maxw=half)
        # relations
        rx = lx + half + 20
        ry = y
        draw_text(scr, f, "Relations", (rx, ry), ACCENT, f.b)
        ry += 20
        others = [o for o in live if o.id != t.id]
        if not others:
            draw_text(scr, f, "No other clans on the island.", (rx, ry), DIM)
            ry += 18
        for o in others[:8]:
            lab, col = humans.relation(wd, t, o)
            hv = t.hostility.get(o.id, 0.0)
            pygame.draw.circle(scr, o.color, (rx + 6, ry + 8), 5)
            draw_text(scr, f, o.name, (rx + 16, ry), TEXT, f.xs, maxw=150)
            draw_text(scr, f, lab, (rx + 172, ry), col, f.xs)
            bar = pygame.Rect(rx + 232, ry + 4, 80, 7)
            pygame.draw.rect(scr, LINE, bar, border_radius=3)
            fb = bar.copy()
            fb.w = int(bar.w * min(1.0, hv / 1.2))
            pygame.draw.rect(scr, col, fb, border_radius=3)
            d = math.hypot(o.x - t.x, o.y - t.y)
            draw_text(scr, f, "%d cells" % d, (rx + 318, ry), DIM, f.xs)
            ry += 18
        draw_text(scr, f, "bar = tension; above the line they may go to war", (rx, ry + 2), DIM, f.xs)
        ry += 24
        if t.relations_log:
            draw_text(scr, f, "History", (rx, ry), ACCENT, f.b)
            ry += 18
            for d, txt in t.relations_log[-5:][::-1]:
                draw_text(scr, f, "%s  %s" % (d, txt), (rx, ry), DIM, f.xs, maxw=r.right - 24 - rx)
                ry += 15

    def handle(self, ev, pos):
        if ev.type == pygame.KEYDOWN and ev.key in (pygame.K_ESCAPE, pygame.K_c):
            self.app.clans = None
            return
        if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            for b in self.buttons:
                if b.handle(ev, pos):
                    return
            for row, tid in self.rows:
                if row.collidepoint(pos):
                    self.tid = tid
                    return
            if not self.rect.collidepoint(pos):
                self.app.clans = None


# ----------------------------------------------------------------------------
# animals
# ----------------------------------------------------------------------------
def describe_animal(w, a):
    sp = a.sp
    lines = []
    if not a.alive:
        return "Has died", ["Its body returns nutrients to the soil."]
    T = float(w.temp[int(a.x), int(a.y)])
    dt = (T - sp.topt) / sp.trange
    if not a.awake:
        if dt < -1.6:
            head = "Hibernating"
            lines.append("It is %.0f C here - too cold for a %s (it prefers about %.0f C). It rests to save energy "
                         "and ages more slowly until it warms up." % (T, sp.name, sp.topt))
        elif sp.activity == "night":
            head = "Asleep"
            lines.append("%s is nocturnal: it rests by day and comes out at night." % sp.name)
        else:
            head = "Asleep"
            lines.append("%s is active by day and rests at night." % sp.name)
        lines.append("Sleeping animals are much easier for predators to catch.")
    else:
        head = (a.note[0].upper() + a.note[1:]) if a.note else "Wandering"
    if a.young:
        lines.append("Very young (egg, chick or baby): easy prey for nest raiders for about another %s."
                     % bio_age_text(sp.young_ticks - a.age))
    elif a.juvenile:
        lines.append("Not yet adult: old enough to breed in about %s." % bio_age_text(a.maxage * sp.mature_frac - a.age))
    if not sp.native:
        lines.append("Introduced: it has no natural enemies here, and native birds don't recognise it as a threat.")
    elif sp.naive:
        lines.append("Evolved without land mammals, so it doesn't flee from rats, stoats, cats or people.")
    if a.sick:
        lines.append("It is sick: disease spreads fast when animals are crowded.")
    lines.append("Energy %d%%  -  age %s (lives up to ~%s)  -  generation %d" % (
        100 * a.energy / (60 * a.size), bio_age_text(a.age), bio_age_text(a.maxage), a.gen))
    return head, lines


# ----------------------------------------------------------------------------
# settings
# ----------------------------------------------------------------------------
class SettingsView:
    W, H = 660, 560

    def __init__(self, app):
        self.app = app
        sw, sh = app.screen.get_size()
        self.rect = pygame.Rect((sw - self.W) // 2, (sh - self.H) // 2, self.W, self.H)
        st = app.ui
        self.hue = Slider("hue", "Accent colour", 0, 1, st.get("accent") if st.get("accent") is not None
                          else THEMES[st.get("theme", "Dark")]["accent"], "")
        self.buttons = []

    def set(self, k, v):
        self.app.ui[k] = v
        if k == "theme":
            self.app.ui["accent"] = None
            self.hue.value = THEMES[v]["accent"]
        self.app.apply_ui()

    def draw(self, scr, f, mouse):
        import colorsys
        shade(scr)
        r = self.rect
        pygame.draw.rect(scr, PANEL, r, border_radius=10)
        pygame.draw.rect(scr, LINE, r, 1, border_radius=10)
        draw_text(scr, f, "Settings", (r.x + 24, r.y + 18), TEXT, f.l)
        self.buttons = []
        ui = self.app.ui
        x, y = r.x + 24, r.y + 64
        w = r.w - 48

        def row(title, items, key, y, cols=None):
            draw_text(scr, f, title, (x, y), ACCENT, f.b)
            y += 22
            n = cols or len(items)
            bw = (w - (n - 1) * 6) // n
            for i, (val, lab) in enumerate(items):
                b = Button(lab, lambda v=val: self.set(key, v), lambda v=val: ui.get(key) == v)
                b.draw(scr, f, (x + (i % n) * (bw + 6), y + (i // n) * 30, bw, 26), b.rect.collidepoint(mouse))
                self.buttons.append(b)
            return y + ((len(items) - 1) // n + 1) * 30 + 12

        y = row("COLOUR THEME", [(t, t) for t in THEMES], "theme", y)
        old = self.hue.value
        rgb = colorsys.hsv_to_rgb(self.hue.value, 0.5, 0.85)
        self.hue.draw(scr, f, x, y, w - 150, tuple(int(c * 255) for c in rgb))
        b = Button("Theme default", lambda: (self.app.ui.__setitem__("accent", None), self.app.apply_ui(),
                                             setattr(self.hue, "value", THEMES[self.app.ui["theme"]]["accent"])))
        b.draw(scr, f, (x + w - 136, y + 4, 136, 26), b.rect.collidepoint(mouse))
        self.buttons.append(b)
        if self.hue.drag and abs(old - self.hue.value) > 1e-4:
            self.app.ui["accent"] = self.hue.value
            self.app.apply_ui()
        y += 46
        y = row("CONTROL PANEL SIDE", [("right", "Right of the map"), ("left", "Left of the map")], "panel", y)
        y = row("CHARTS & ALERTS BAR", [("bottom", "Below the map"), ("top", "Above the map")], "bar", y)
        import webplatform
        if not webplatform.WEB:
            y = row("WINDOW SIZE", [("fit", "Fit screen"), ("original", "Original (1300 x 780)"),
                                    ("fullscreen", "Fullscreen")], "window", y)
        y = row("DAY / NIGHT DISPLAY", [("shade", "Darken map at night"), ("icon", "Sun & moon icon only"),
                                        ("off", "Hide day / night")], "daynight", y)
        draw_text(scr, f, "The icon and hidden options also turn off lightning flashes (photosensitivity). "
                          "Drag the window edges to resize.", (x, y), DIM, f.xs, maxw=w)
        b = Button("Close", lambda: setattr(self.app, "settings_view", None))
        b.draw(scr, f, (r.right - 110, r.bottom - 44, 86, 28), b.rect.collidepoint(mouse))
        self.buttons.append(b)

    def handle(self, ev, pos):
        if ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE:
            self.app.settings_view = None
            return
        if self.hue.handle(ev, pos):
            if ev.type == pygame.MOUSEBUTTONUP:
                self.app.ui["accent"] = self.hue.value
                self.app.apply_ui()
            return
        if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            for b in self.buttons:
                if b.handle(ev, pos):
                    return


# ----------------------------------------------------------------------------
# ecological history
# ----------------------------------------------------------------------------
CATS = [("all", "Everything"), ("people", "People"), ("war", "Wars & peace"), ("arrival", "New species"),
        ("extinction", "Extinctions"), ("ecosystem", "Ecosystem"), ("recovery", "Recoveries"),
        ("conservation", "Conservation")]
CAT_COLORS = {"people": (235, 200, 160), "war": (240, 100, 90), "arrival": (240, 160, 80),
              "extinction": (240, 90, 80), "ecosystem": (150, 190, 120), "recovery": (126, 206, 146),
              "conservation": (110, 210, 200)}


class HistoryView:
    W, H = 960, 640

    def __init__(self, app):
        self.app = app
        sw, sh = app.screen.get_size()
        self.rect = pygame.Rect((sw - self.W) // 2, (sh - self.H) // 2, self.W, self.H)
        self.cat = "all"
        self.scroll = 0
        self.buttons = []
        self.rows = []

    def draw(self, scr, f, mouse):
        wd = self.app.world
        shade(scr)
        r = self.rect
        pygame.draw.rect(scr, PANEL, r, border_radius=10)
        pygame.draw.rect(scr, LINE, r, 1, border_radius=10)
        draw_text(scr, f, "Ecological history", (r.x + 24, r.y + 16), TEXT, f.l)
        draw_text(scr, f, "The major events of this island, from the beginning to %s" % wd.date, (r.x + 260, r.y + 24), DIM)
        self.buttons = []
        b = Button("Close", lambda: setattr(self.app, "history_view", None))
        b.draw(scr, f, (r.right - 100, r.y + 16, 76, 26), b.rect.collidepoint(mouse))
        self.buttons.append(b)
        ms = wd.milestones
        x, y = r.x + 24, r.y + 64
        for key, lab in CATS:
            n = len(ms) if key == "all" else sum(1 for m in ms if m["cat"] == key)
            b = Button("%s (%d)" % (lab, n), lambda k=key: (setattr(self, "cat", k), setattr(self, "scroll", 0)),
                       lambda k=key: self.cat == k, color=CAT_COLORS.get(key))
            b.draw(scr, f, (x, y, 190, 28), b.rect.collidepoint(mouse))
            self.buttons.append(b)
            y += 34
        y += 10
        stats = [("Began", wd.milestones[0]["date"] if False else "%s" % ("1 Sep Y1")),
                 ("Today", wd.stamp), ("People now / peak", "%d / %d" % (len(wd.people), wd.peak_people)),
                 ("Clans founded", str(len(wd.tribes))),
                 ("Native species alive", "%d of %d" % (getattr(wd, "native_alive", 0), getattr(wd, "native_total", 0)))]
        for k, v in stats:
            draw_text(scr, f, k, (x, y), DIM, f.xs)
            draw_text(scr, f, v, (x + 190, y), TEXT, f.xs, "topright")
            y += 17
        # list
        lx = r.x + 236
        lw = r.right - 24 - lx
        top, bottom = r.y + 64, r.bottom - 20
        items = [m for m in ms if self.cat == "all" or m["cat"] == self.cat]
        pygame.draw.rect(scr, GRAPH, (lx - 8, top - 6, lw + 16, bottom - top + 12), border_radius=6)
        if not items:
            draw_text(scr, f, "Nothing yet - history is being written as the simulation runs.", (lx, top + 6), DIM)
            return
        blocks = []
        year = None
        for m in items:
            if m["year"] != year:
                year = m["year"]
                blocks.append(("year", year))
            blocks.append(("m", m))
        self.scroll = max(0, min(self.scroll, len(blocks) - 1))
        yy = top
        self.rows = []
        for kind, data in blocks[self.scroll:]:
            if yy > bottom - 20:
                break
            if kind == "year":
                draw_text(scr, f, "YEAR %d" % data, (lx, yy), ACCENT, f.b)
                yy += 22
                continue
            m = data
            lines = wrap(m["text"], f.s, lw - 120) if m["text"] else []
            h = 20 + 16 * len(lines) + 6
            rowr = pygame.Rect(lx - 4, yy - 2, lw + 8, h)
            if rowr.collidepoint(mouse) and m.get("pos"):
                pygame.draw.rect(scr, HOVER, rowr, border_radius=4)
            col = CAT_COLORS.get(m["cat"], TEXT)
            pygame.draw.circle(scr, col, (lx + 5, yy + 8), 5)
            draw_text(scr, f, m["date"], (lx + 16, yy + 1), DIM, f.xs)
            draw_text(scr, f, m["title"], (lx + 92, yy), TEXT, f.b, maxw=lw - 100)
            for i, ln in enumerate(lines):
                draw_text(scr, f, ln, (lx + 92, yy + 19 + i * 16), DIM)
            if m.get("pos"):
                draw_text(scr, f, "show", (lx + lw, yy + 1), ACCENT, f.xs, "topright")
                self.rows.append((rowr, m))
            yy += h
        draw_text(scr, f, "scroll for more" if self.scroll + 1 < len(blocks) else "", (lx + lw, bottom - 4), DIM,
                  f.xs, "bottomright")

    def handle(self, ev, pos):
        if ev.type == pygame.KEYDOWN and ev.key in (pygame.K_ESCAPE, pygame.K_y):
            self.app.history_view = None
            return
        if ev.type == pygame.MOUSEWHEEL:
            self.scroll = max(0, self.scroll - ev.y)
            return
        if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            for b in self.buttons:
                if b.handle(ev, pos):
                    return
            for rowr, m in self.rows:
                if rowr.collidepoint(pos):
                    self.app.history_view = None
                    x, y = m["pos"]
                    self.app.highlight = (x, y, 150)
                    self.app.center_on(x, y, 2.0)
                    return


# ----------------------------------------------------------------------------
# lifecycle analysis (shared by the collapse screen and the health drawer)
# ----------------------------------------------------------------------------
CAUSE_GROUPS = [("Introduced predators", (220, 110, 80)), ("Hunted by people", (235, 200, 160)),
                ("Starvation / lost habitat", (200, 170, 100)), ("Native predators", (120, 170, 140)),
                ("Fire", (255, 140, 60)), ("Disease", (170, 220, 90)), ("Cold / heat", (140, 180, 240)),
                ("Old age", (150, 150, 160)), ("Removed by you", (190, 120, 235))]


def native_death_causes(wd):
    groups = {}
    natives = {sp.name for sp in wd.animal_species if sp.native}
    for (name, cause), n in wd.death_totals.items():
        if name not in natives:
            continue
        if cause.startswith("eaten by "):
            pred = wd.species_by_name(cause[9:])
            g = "Native predators" if (pred is not None and pred.native) else "Introduced predators"
        elif cause == "hunted by humans":
            g = "Hunted by people"
        elif cause == "starvation":
            g = "Starvation / lost habitat"
        elif cause == "fire":
            g = "Fire"
        elif cause == "disease":
            g = "Disease"
        elif cause in ("cold", "heat"):
            g = "Cold / heat"
        elif cause == "removed by you":
            g = "Removed by you"
        else:
            g = "Old age"
        groups[g] = groups.get(g, 0) + n
    return groups


def main_cause(wd, name):
    c = {}
    for (n, cause), k in wd.death_totals.items():
        if n == name and cause != "old age":
            c[cause] = c.get(cause, 0) + k
    if not c:
        return "old age"
    return max(c.items(), key=lambda kv: kv[1])[0]


def stages(wd):
    start = wd.start_tick
    def first(pred):
        ts = [m["tick"] for m in wd.milestones if pred(m)]
        return min(ts) if ts else None
    t_people = first(lambda m: m["key"] == "first_people")
    t_arrive = first(lambda m: m["cat"] == "arrival")
    t_ext = first(lambda m: m["cat"] == "extinction" and m["key"] != "collapse")
    t_col = getattr(wd, "collapse_tick", None) if wd.collapsed else None
    marks = [("Untouched", start, (90, 170, 140))]
    t_set = min([t for t in (t_people, t_arrive) if t is not None], default=None)
    if t_set is not None:
        marks.append(("People & new species", t_set, (235, 200, 160)))
    if t_ext is not None:
        marks.append(("Decline", t_ext, (240, 170, 90)))
    if t_col is not None:
        marks.append(("Collapse", t_col, (240, 90, 80)))
    marks.sort(key=lambda m: m[1])
    out = []
    for i, (lab, t0, col) in enumerate(marks):
        t1 = marks[i + 1][1] if i + 1 < len(marks) else wd.tick
        out.append((lab, t0, t1, col))
    return out


def draw_lifecycle_chart(scr, f, wd, rect, show_marks=True):
    pygame.draw.rect(scr, GRAPH, rect, border_radius=6)
    lh = wd.long_history
    if len(lh) < 2:
        draw_text(scr, f, "Not enough history yet", rect.center, DIM, f.s, "center")
        return
    t0, t1 = lh[0]["tick"], max(lh[-1]["tick"], lh[0]["tick"] + 1)
    inner = rect.inflate(-16, -34)
    inner.y = rect.y + 24

    def X(t):
        return inner.x + (t - t0) / (t1 - t0) * inner.w
    # stage bands
    for lab, a, b, col in stages(wd):
        xa, xb = max(inner.x, X(a)), min(inner.right, X(b))
        if xb > xa:
            band = pygame.Surface((xb - xa, inner.h), pygame.SRCALPHA)
            band.fill((*col, 28))
            scr.blit(band, (xa, inner.y))
            draw_text(scr, f, lab, (xa + 3, rect.y + 5), col, f.xs, maxw=max(10, xb - xa - 4))
    series = [("natives", "Native animals", (90, 200, 170)), ("pests", "Introduced animals", (230, 110, 80)),
              ("people", "People", (235, 200, 160)), ("trees", "Forest", (80, 150, 80)),
              ("vitality", "Vitality", TEXT)]
    for key, lab, col in series:
        vals = [h.get(key, 0) for h in lh]
        mx = max(1e-6, max(vals)) if key != "vitality" else 100
        pts = [(X(h["tick"]), inner.bottom - (v / mx) * inner.h) for h, v in zip(lh, vals)]
        if len(pts) > 1:
            pygame.draw.lines(scr, col, False, pts, 2 if key in ("natives", "vitality") else 1)
    if show_marks:
        for m in wd.milestones:
            if m["cat"] in ("extinction", "arrival") or m["key"] in ("first_people", "first_war"):
                x = X(m["tick"])
                if inner.x <= x <= inner.right:
                    pygame.draw.line(scr, CAT_COLORS.get(m["cat"], TEXT), (x, inner.bottom), (x, inner.bottom - 8), 2)
    lx = rect.x + 8
    for key, lab, col in series:
        pygame.draw.rect(scr, col, (lx, rect.bottom - 12, 10, 4))
        draw_text(scr, f, lab, (lx + 14, rect.bottom - 17), DIM, f.xs)
        lx += f.xs.size(lab)[0] + 30


class CollapseView:
    W, H = 1220, 720

    def __init__(self, app):
        self.app = app
        sw, sh = app.screen.get_size()
        self.rect = pygame.Rect((sw - self.W) // 2, (sh - self.H) // 2, self.W, self.H)
        self.buttons = []

    def lessons(self, wd, groups):
        tot = sum(groups.values()) or 1
        top = sorted(groups.items(), key=lambda kv: -kv[1])
        out = []
        main = top[0][0] if top else ""
        if main == "Introduced predators":
            out.append("Introduced mammals did the most damage. Native birds evolved for millions of years with no "
                       "land mammals, so they didn't flee and nested where rats, stoats and cats could reach them.")
        elif main == "Hunted by people":
            out.append("Hunting by people wiped out slow-breeding animals that had never learned to fear humans - "
                       "much as all nine species of moa were hunted to extinction within a few centuries.")
        elif main == "Starvation / lost habitat":
            out.append("Animals starved as forest, wetlands and food plants were cleared, burned or eaten by "
                       "browsing pests. Protecting habitat matters as much as stopping predators.")
        elif main == "Fire":
            out.append("Fire destroyed habitat faster than it could recover. Most native NZ plants are not "
                       "adapted to burning.")
        else:
            out.append("Several pressures combined until the native wildlife could no longer replace itself.")
        missing = []
        keys = wd.milestone_keys
        if "first_trap" not in keys:
            missing.append("no pest traps were ever set")
        if "first_sanct" not in keys:
            missing.append("no predator-proof sanctuary was fenced")
        if wd.settings.get("biosecurity", 0) < 0.6 and any(m["cat"] == "arrival" for m in wd.milestones):
            missing.append("biosecurity stayed low, so ships and settlers kept bringing pests")
        if missing:
            out.append("What might have helped: " + "; ".join(missing) + ".")
        out.append("In real Aotearoa, pest-free islands, fenced sanctuaries, predator control and protecting forest "
                   "and wetlands have saved species like kakapo, takahe and many kiwi populations.")
        return out

    def draw(self, scr, f, mouse):
        wd = self.app.world
        shade(scr, 200)
        r = self.rect
        pygame.draw.rect(scr, PANEL, r, border_radius=10)
        pygame.draw.rect(scr, (240, 90, 80), r, 2, border_radius=10)
        draw_text(scr, f, "Ecological collapse", (r.x + 26, r.y + 16), (240, 110, 100), f.xl)
        lasted = age_text(getattr(wd, "collapse_tick", wd.tick) - wd.start_tick)
        draw_text(scr, f, "%s  -  the island's native land wildlife has been destroyed and cannot return on its own. "
                          "The ecosystem lasted %s." % (wd.date, lasted), (r.x + 28, r.y + 56), TEXT, f.m)
        self.buttons = []
        # lifecycle chart
        chart = pygame.Rect(r.x + 24, r.y + 90, 760, 250)
        draw_text(scr, f, "Lifecycle of the ecosystem", (chart.x, chart.y - 2), ACCENT, f.b)
        chart.y += 20
        draw_lifecycle_chart(scr, f, wd, chart)
        # stages list
        y = chart.bottom + 12
        draw_text(scr, f, "Stages", (chart.x, y), ACCENT, f.b)
        y += 20
        for lab, a, b, col in stages(wd):
            draw_text(scr, f, "%s: %s" % (lab, age_text(b - a)), (chart.x, y), col, f.s)
            y += 17
        # extinction timeline
        y += 8
        draw_text(scr, f, "Extinctions, in order (main cause)", (chart.x, y), ACCENT, f.b)
        y += 20
        exts = [m for m in wd.milestones if m["cat"] == "extinction" and m["key"] != "collapse"]
        colx = chart.x
        for i, m in enumerate(exts[:16]):
            name = m["title"].split(" is extinct")[0]
            txt = "%s  %s - %s" % (m["date"], name, main_cause(wd, name))
            draw_text(scr, f, txt, (colx + (i // 8) * 380, y + (i % 8) * 16), (240, 140, 120), f.xs, maxw=370)
        # right column: causes pie + stats + lessons
        rx = r.x + 810
        rw = r.right - 24 - rx
        groups = native_death_causes(wd)
        draw_text(scr, f, "What killed the native wildlife", (rx, r.y + 88), ACCENT, f.b)
        items = [(groups.get(lab, 0), col, lab) for lab, col in CAUSE_GROUPS if groups.get(lab, 0)]
        tot = sum(i[0] for i in items) or 1
        draw_pie(scr, (rx + 70, r.y + 180), 66, [(i[0], i[1]) for i in items], hole=0.45)
        for k, (n, col, lab) in enumerate(sorted(items, key=lambda a: -a[0])[:8]):
            pygame.draw.rect(scr, col, (rx + 150, r.y + 116 + k * 17, 9, 9))
            draw_text(scr, f, "%s  %d%%" % (lab, 100 * n / tot), (rx + 164, r.y + 112 + k * 17), TEXT, f.xs)
        y = r.y + 270
        lost_pct = 100 * (1 - (wd.long_history[-1]["trees"] / max(1, wd.start_trees or 1))) if wd.long_history else 0
        intro = [m["title"].replace(" arrives", "") for m in wd.milestones if m["cat"] == "arrival"]
        wars = sum(1 for m in wd.milestones if m["key"].startswith("war:"))
        voyages = sum(len(t.voyages) for t in wd.tribes)
        stats = [("Native species lost", "%d of %d" % (len(exts), getattr(wd, "native_total", 0))),
                 ("Forest lost", "%d%%" % max(0, lost_pct)),
                 ("Peak human population", str(wd.peak_people)),
                 ("Clans / wars / voyages", "%d / %d / %d" % (len(wd.tribes), wars, voyages)),
                 ("Animals hunted by people", str(sum(t.kills for t in wd.tribes))),
                 ("Species introduced", ", ".join(intro) or "none")]
        for k, v in stats:
            draw_text(scr, f, k, (rx, y), DIM, f.xs)
            for i, ln in enumerate(wrap(v, f.xs, rw - 150)):
                draw_text(scr, f, ln, (rx + rw, y + i * 14), TEXT, f.xs, "topright")
            y += 16 + 14 * (len(wrap(v, f.xs, rw - 150)) - 1)
        y += 10
        draw_text(scr, f, "What this teaches", (rx, y), ACCENT, f.b)
        y += 20
        for para in self.lessons(wd, groups):
            for ln in wrap(para, f.s, rw):
                if y > r.bottom - 60:
                    break
                draw_text(scr, f, ln, (rx, y), TEXT, f.s)
                y += 16
            y += 6
        for i, (lab, cb) in enumerate([("Start a new island", self.new), ("View full history", self.history),
                                       ("Keep watching", self.close)]):
            b = Button(lab, cb)
            b.draw(scr, f, (r.x + 24 + i * 190, r.bottom - 44, 180, 30), b.rect.collidepoint(mouse), f.b)
            self.buttons.append(b)

    def new(self):
        self.app.collapse_view = None
        self.app.newworld = NewWorldView(self.app)

    def history(self):
        self.app.collapse_view = None
        self.app.history_view = HistoryView(self.app)

    def close(self):
        self.app.collapse_view = None

    def handle(self, ev, pos):
        if ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE:
            self.close()
            return
        if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            for b in self.buttons:
                if b.handle(ev, pos):
                    return


# ----------------------------------------------------------------------------
# ecosystem health drawer (opens from the vitality bar)
# ----------------------------------------------------------------------------
PART_COLORS = {"Lost native species": (240, 90, 80), "Introduced pests": (230, 140, 80), "Deforestation": (200, 170, 110),
               "Drought": (230, 200, 90), "Fire": (255, 120, 60), "Bare land": (180, 150, 110), "Cold": (140, 180, 240),
               "Heat": (250, 120, 90)}


def draw_health_drawer(scr, f, wd, rect, mouse):
    box = pygame.Surface(rect.size, pygame.SRCALPHA)
    box.fill((*PANEL, 248))
    scr.blit(box, rect)
    pygame.draw.rect(scr, ACCENT, rect, 2, border_radius=8)
    v = wd.vitality
    draw_text(scr, f, "Ecosystem health  -  vitality %d (%s)" % (v, wd.mood), (rect.x + 14, rect.y + 10), TEXT, f.b)
    draw_text(scr, f, "click the vitality bar again to close", (rect.right - 12, rect.y + 13), DIM, f.xs, "topright")
    chart = pygame.Rect(rect.x + 12, rect.y + 36, rect.w - 24, 170)
    draw_lifecycle_chart(scr, f, wd, chart, show_marks=True)
    # pie: what's pulling vitality down
    parts = dict(getattr(wd, "vital_parts", {}))
    healthy = max(0.0, 100 - sum(parts.values()))
    items = [(healthy, (110, 200, 140), "Healthy")] + [(min(100, val), PART_COLORS.get(k, DIM), k)
                                                         for k, val in sorted(parts.items(), key=lambda kv: -kv[1])]
    cy = chart.bottom + 70
    draw_pie(scr, (rect.x + 70, cy), 56, [(i[0], i[1]) for i in items], hole=0.45)
    draw_text(scr, f, "%d" % v, (rect.x + 70, cy), TEXT, f.b, "center")
    tot = sum(i[0] for i in items) or 1
    for k, (n, col, lab) in enumerate(items[:7]):
        pygame.draw.rect(scr, col, (rect.x + 140, chart.bottom + 18 + k * 16, 9, 9))
        draw_text(scr, f, "%s %d%%" % (lab, 100 * n / tot), (rect.x + 154, chart.bottom + 14 + k * 16), TEXT, f.xs)
    tx = rect.x + 320
    y = chart.bottom + 12
    draw_text(scr, f, "Right now", (tx, y), ACCENT, f.b)
    y += 18
    nat = sum(wd.counts.get(sp, 0) for sp in wd.animal_species if sp.native)
    pest = sum(wd.counts.get(sp, 0) for sp in wd.animal_species if not sp.native)
    facts = ["Native species alive: %d of %d" % (getattr(wd, "native_alive", 0), getattr(wd, "native_total", 0)),
             "Native animals %d, introduced %d" % (nat, pest),
             "Forest: %d%% of the land" % (100 * getattr(wd, "forest", 0)),
             "People: %d in %d clans" % (len(wd.people), sum(1 for t in wd.tribes if t.alive))]
    needs = [t for t, _ in getattr(wd, "needs", [])]
    if needs:
        facts.append("Needs: " + "; ".join(needs[:2]))
    for ln in facts:
        for wl in wrap(ln, f.xs, rect.right - tx - 12):
            draw_text(scr, f, wl, (tx, y), TEXT, f.xs)
            y += 15
