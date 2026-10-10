"""
foodweb.py - a live food web: who eats whom on the island, drawn from what the simulation
actually records.  Arrows run from the food to the eater (the direction energy flows) and get
thicker as more is eaten.  Dotted lines are links that could happen but haven't recently.
"""
import math

import pygame

from config import BIO_YEAR, CAL_DAY, LIFE_SPEED, bio_age_text
from ui_kit import (PANEL, PANEL2, LINE, TEXT, DIM, ACCENT, GRAPH, HOVER, TIP, draw_text, wrap, Button)
_THEMED = True

RESOURCES = [
    ("Plants", (90, 160, 80), "Leaves, grass and shoots of every plant on the island."),
    ("Fruit & seeds", (200, 150, 70), "Fruit and seed - a flood of it in mast years."),
    ("Nectar", (240, 200, 70), "Flower nectar; the birds that drink it pollinate the plants."),
    ("Fungi", (220, 210, 185), "Mushrooms and mycelium in the soil."),
    ("Insects & worms", (170, 140, 110), "Earthworms, grubs, beetles, moths and spiders in the soil and leaf litter "
                                         "- the main food of kiwi and morepork."),
    ("Dead matter", (150, 110, 70), "Leaf litter, rotting wood and carcasses - recycled by fungi, microbes and "
                                    "weta into soil nutrients."),
    ("Fish", (90, 160, 220), "Fish and shellfish in the sea, which feed on plankton."),
    ("Crops & stores", (220, 200, 110), "People's fields and food stores."),
]
RES_NAMES = [r[0] for r in RESOURCES]
NATIVE_C = (110, 205, 150)
INTRO_C = (235, 120, 90)
PEOPLE_C = (235, 200, 160)


def potential_links(w):
    """Every feeding link the species' diets allow (food, eater)."""
    links = set()
    names = {sp.name for sp in w.animal_species}
    birds = [sp.name for sp in w.animal_species if getattr(sp, "bird", False)]
    for sp in w.animal_species:
        d = sp.diet
        if "plant" in d:
            links.add(("Plants", sp.name))
        if "seed" in d:
            links.add(("Fruit & seeds", sp.name))
        if "nectar" in d:
            links.add(("Nectar", sp.name))
        if "fungus" in d:
            links.add(("Fungi", sp.name))
        if "invert" in d:
            links.add(("Insects & worms", sp.name))
        if "detritus" in d:
            links.add(("Dead matter", sp.name))
        if "fish" in d:
            links.add(("Fish", sp.name))
        if (not sp.native and d & {"plant", "seed"}) or getattr(sp, "commensal", False):
            links.add(("Crops & stores", sp.name))
        if sp.prey:
            for p in sp.prey:
                if p in names and p != sp.name:
                    links.add((p, sp.name))
        elif "meat" in d:
            for o in w.animal_species:
                if o is not sp and sp.size * 0.35 <= o.size <= sp.size * 0.85:
                    links.add((o.name, sp.name))
        if getattr(sp, "nest_raider", False):
            for b in birds:
                if b != sp.name:
                    links.add((b, sp.name))
    if w.people or w.tribes:
        for sp in w.animal_species:
            if sp.size >= 0.3 and not getattr(sp, "marine", False):
                links.add((sp.name, "People"))
        for r in ("Plants", "Fish", "Crops & stores"):
            links.add((r, "People"))
    return links


class FoodWebView:
    W, H = 1240, 720

    def __init__(self, app):
        self.app = app
        sw, sh = app.screen.get_size()
        self.rect = pygame.Rect((sw - self.W) // 2, (sh - self.H) // 2, self.W, self.H)
        self.mode = "recent"
        self.show_possible = True
        self.buttons = []
        self.nodes = {}
        self.hover = None
        self.pinned = None
        self.frame = 0

    # ------------------------------------------------------------------ model
    def flows(self):
        w = self.app.world
        return (w.web, w.web_n) if self.mode == "recent" else (w.web_total, w.web_n_total)

    def build(self, area):
        """Compute nodes (with trophic levels and positions) and edges."""
        w = self.app.world
        flow, nkill = self.flows()
        pot = potential_links(w)
        ever = {k for k, v in w.web_total.items() if v > 0}
        consumers = {}
        for sp in w.animal_species:
            n = w.counts.get(sp, 0)
            seen = any(sp.name in k for k in ever)
            extinct_native = sp.native and n == 0 and (seen or any(
                m["cat"] == "extinction" and m["title"].startswith(sp.name) for m in w.milestones))
            if n > 0 or seen or extinct_native:
                consumers[sp.name] = {"kind": "animal", "sp": sp, "n": n, "native": sp.native}
        if w.people or any(k[1] == "People" for k in ever):
            consumers["People"] = {"kind": "people", "n": len(w.people), "native": None}
        res = {}
        for name, col, blurb in RESOURCES:
            used = any(k[0] == name and k[1] in consumers for k in pot | set(flow))
            if name == "Crops & stores" and not (w.people or w.tribes):
                used = False
            if name == "Fish" and not w.sea.any():
                used = False
            if used:
                res[name] = {"kind": "res", "col": col, "blurb": blurb, "n": None, "native": None}
        nodes = dict(res)
        nodes.update(consumers)
        edges = {}
        for (a, b) in pot | {k for k, v in flow.items() if v > 0.01}:
            if a in nodes and b in nodes and a != b:
                edges[(a, b)] = {"flow": flow.get((a, b), 0.0), "n": nkill.get((a, b), 0.0),
                                 "possible": (a, b) in pot}
        # trophic levels: resources 0 (fish 1); eaters 1 + average level of what they eat
        tl = {k: (1.0 if k in ("Fish", "Insects & worms") else 0.0) for k in res}   # these are animals too
        for k in consumers:
            tl[k] = 1.0
        for _ in range(25):
            for k in consumers:
                foods = [(a, e) for (a, b), e in edges.items() if b == k]
                if not foods:
                    continue
                tot = sum(e["flow"] for _, e in foods)
                if tot > 0.5:
                    tl[k] = 1 + sum(tl[a] * e["flow"] for a, e in foods) / tot
                else:
                    tl[k] = 1 + sum(tl[a] for a, _ in foods) / len(foods)
        # bands (rows)
        for k, nd in nodes.items():
            nd["tl"] = tl[k]
            nd["band"] = 0 if nd["kind"] == "res" else max(1, min(4, int(round(tl[k]))))
        bands = sorted({nd["band"] for nd in nodes.values()})
        nb = max(bands) if bands else 1
        top, bottom = area.y + 40, area.bottom - 46
        rowh = (bottom - top) / max(1, nb)
        # resources spread evenly along the bottom
        rows = {}
        for k, nd in nodes.items():
            rows.setdefault(nd["band"], []).append(k)
        for b in sorted(rows):
            ks = rows[b]
            if b == 0:
                order = [r for r in RES_NAMES if r in ks]
            else:
                def bary(k):
                    foods = [(a, e) for (a, bb), e in edges.items() if bb == k and a in nodes and "x" in nodes[a]]
                    if not foods:
                        return area.centerx
                    wts = [max(0.2, e["flow"]) if e["flow"] > 0 else 0.2 for _, e in foods]
                    return sum(nodes[a]["x"] * wt for (a, _), wt in zip(foods, wts)) / sum(wts)
                order = sorted(ks, key=lambda k: (bary(k), k))
            n = len(order)
            for i, k in enumerate(order):
                nodes[k]["x"] = area.x + 60 + (i + 0.5) * (area.w - 120) / n
                nodes[k]["y"] = bottom - b * rowh + (12 if (b and i % 2) else 0)
        for k, nd in nodes.items():
            if nd["kind"] == "res":
                nd["r"] = 16
            else:
                nd["r"] = 9 + 3.2 * math.log1p(nd["n"]) if nd["n"] else 9
        self.nodes, self.edges = nodes, edges

    # ------------------------------------------------------------ drawing
    def node_color(self, k, nd):
        if nd["kind"] == "res":
            return nd["col"]
        if nd["kind"] == "people":
            return PEOPLE_C
        return NATIVE_C if nd["native"] else INTRO_C

    def edge_color(self, a, b):
        na, nb = self.nodes[a], self.nodes[b]
        if nb["kind"] == "people":
            return PEOPLE_C
        if na["kind"] == "animal" and na["native"] and nb["kind"] == "animal" and not nb["native"]:
            return (240, 90, 70)            # introduced predator eating native wildlife
        if na["kind"] == "res":
            return tuple(int(c * 0.8) for c in na["col"])
        return (150, 200, 170) if nb["native"] else (230, 150, 110)

    def draw(self, scr, f, mouse):
        from views import shade
        w = self.app.world
        self.frame += 1
        shade(scr, 190)
        r = self.rect
        pygame.draw.rect(scr, PANEL, r, border_radius=10)
        pygame.draw.rect(scr, LINE, r, 1, border_radius=10)
        draw_text(scr, f, "Food web", (r.x + 24, r.y + 14), TEXT, f.l)
        draw_text(scr, f, "Who eats whom on the island - live from the simulation.  Arrows run from food to eater "
                          "(the way energy flows); thicker = more eaten.", (r.x + 150, r.y + 22), DIM, f.s)
        self.buttons = []
        for i, (k, lab) in enumerate([("recent", "Last year of life"), ("total", "All time")]):
            b = Button(lab, lambda k=k: setattr(self, "mode", k), lambda k=k: self.mode == k)
            b.draw(scr, f, (r.x + 24 + i * 134, r.y + 50, 128, 24), b.rect.collidepoint(mouse), f.xs)
            self.buttons.append(b)
        b = Button("Show possible links", lambda: setattr(self, "show_possible", not self.show_possible),
                   lambda: self.show_possible)
        b.draw(scr, f, (r.x + 300, r.y + 50, 150, 24), b.rect.collidepoint(mouse), f.xs)
        self.buttons.append(b)
        b = Button("Close", lambda: setattr(self.app, "foodweb_view", None))
        b.draw(scr, f, (r.right - 100, r.y + 14, 76, 26), b.rect.collidepoint(mouse))
        self.buttons.append(b)
        area = pygame.Rect(r.x + 16, r.y + 84, r.w - 360, r.h - 100)
        pygame.draw.rect(scr, GRAPH, area, border_radius=8)
        self.build(area)
        self.draw_graph(scr, f, area, mouse)
        self.draw_side(scr, f, pygame.Rect(area.right + 16, area.y, r.right - area.right - 32, area.h), mouse)

    def draw_graph(self, scr, f, area, mouse, static=False):
        nodes, edges = self.nodes, self.edges
        # row labels
        names = {0: "Food sources", 1: "Eat plants, insects & dead matter", 2: "Predators", 3: "Top predators",
                 4: "Top predators"}
        seen = set()
        for k, nd in nodes.items():
            b = nd["band"]
            if b not in seen:
                seen.add(b)
                draw_text(scr, f, names.get(b, ""), (area.x + 8, nd["y"] - 8 - (0 if b else 24)), DIM, f.xs)
        hov = None
        if not static:
            for k, nd in nodes.items():
                if math.hypot(mouse[0] - nd["x"], mouse[1] - nd["y"]) < nd["r"] + 4:
                    hov = k
        self.hover = hov
        focus = hov or self.pinned
        if focus not in nodes:
            focus = None
        kill_max = max([e["flow"] for (a, b), e in edges.items() if nodes[a]["kind"] != "res"] + [1e-6])
        res_max = max([e["flow"] for (a, b), e in edges.items() if nodes[a]["kind"] == "res"] + [1e-6])
        w = self.app.world
        recent_kills = {(prey, eater) for (t, eater, prey, st, x, y) in w.kill_log if w.tick - t < CAL_DAY // 2}
        layer = pygame.Surface(area.size, pygame.SRCALPHA)
        ox, oy = area.x, area.y
        order = sorted(edges.items(), key=lambda kv: kv[1]["flow"])
        for (a, b), e in order:
            na, nb = nodes[a], nodes[b]
            active = e["flow"] > 0.01
            if not active and not (self.show_possible or static):
                continue
            touches = focus in (a, b) if focus else True
            mx = res_max if na["kind"] == "res" else kill_max
            frac = math.sqrt(e["flow"] / mx) if active else 0
            width = max(1, int(1 + 9 * frac)) if active else 1
            col = self.edge_color(a, b)
            alpha = (230 if touches else 35) if active else (110 if touches else 18)
            x0, y0 = na["x"] - ox, na["y"] - oy
            x1, y1 = nb["x"] - ox, nb["y"] - oy
            dx, dy = x1 - x0, y1 - y0
            d = math.hypot(dx, dy) or 1
            ux, uy = dx / d, dy / d
            sx, sy = x0 + ux * na["r"], y0 + uy * na["r"]
            ex, ey = x1 - ux * (nb["r"] + 3), y1 - uy * (nb["r"] + 3)
            if (a, b) in recent_kills and not static:
                pygame.draw.line(layer, (255, 255, 255, 200 if touches else 60), (sx, sy), (ex, ey), width + 4)
            if active:
                pygame.draw.line(layer, (*col, alpha), (sx, sy), (ex, ey), width)
                ah = 6 + width
                pygame.draw.polygon(layer, (*col, alpha), [(ex, ey), (ex - ux * ah - uy * ah * 0.5, ey - uy * ah + ux * ah * 0.5),
                                                           (ex - ux * ah + uy * ah * 0.5, ey - uy * ah - ux * ah * 0.5)])
                if not static and touches:
                    # energy pulses travelling towards the eater
                    nd = 1 + int(frac * 3)
                    for i in range(nd):
                        ph = ((self.frame * (0.006 + 0.01 * frac)) + i / nd + (hash((a, b)) % 100) / 100) % 1
                        px, py = sx + (ex - sx) * ph, sy + (ey - sy) * ph
                        pygame.draw.circle(layer, (255, 255, 255, 170), (int(px), int(py)), max(2, width // 2 + 1))
            else:
                L = int(d // 9)
                for i in range(0, L, 2):
                    p0 = (sx + (ex - sx) * i / L, sy + (ey - sy) * i / L)
                    p1 = (sx + (ex - sx) * (i + 1) / L, sy + (ey - sy) * (i + 1) / L)
                    pygame.draw.line(layer, (*DIM, alpha), p0, p1, 1)
        scr.blit(layer, area.topleft)
        for k, nd in nodes.items():
            col = self.node_color(k, nd)
            dim = focus is not None and k != focus and (k, focus) not in edges and (focus, k) not in edges
            x, y, rr = int(nd["x"]), int(nd["y"]), int(nd["r"])
            extinct = nd["kind"] == "animal" and nd["n"] == 0
            c = tuple(int(v * (0.35 if dim else 1)) for v in col)
            if nd["kind"] == "res":
                box = pygame.Rect(0, 0, 92, 26)
                box.center = (x, y)
                pygame.draw.rect(scr, c, box, border_radius=8)
                pygame.draw.rect(scr, LINE if k != focus else TEXT, box, 2 if k == focus else 1, border_radius=8)
                draw_text(scr, f, k, box.center, (20, 20, 20), f.xs, "center")
                nd["r"] = 14
                continue
            if extinct:
                pygame.draw.circle(scr, c, (x, y), rr, 2)
                pygame.draw.line(scr, (240, 90, 80), (x - rr, y - rr), (x + rr, y + rr), 2)
            else:
                pygame.draw.circle(scr, c, (x, y), rr)
                pygame.draw.circle(scr, TEXT if k == focus else LINE, (x, y), rr, 2 if k == focus else 1)
            lab = k + (" (extinct)" if extinct else "  %d" % nd["n"])
            draw_text(scr, f, lab, (x, y + rr + 2), TEXT if not dim else DIM, f.xs, "midtop")
        # legend
        lx, ly = area.x + 10, area.bottom - 20
        for col, lab in [(NATIVE_C, "native"), (INTRO_C, "introduced"), (PEOPLE_C, "people"),
                         ((240, 90, 70), "pest eating native wildlife")]:
            pygame.draw.circle(scr, col, (lx + 5, ly + 7), 5)
            draw_text(scr, f, lab, (lx + 14, ly), DIM, f.xs)
            lx += f.xs.size(lab)[0] + 32
        draw_text(scr, f, "size of circle = population   - - - possible but not happening   white flash = just happened",
                  (lx + 6, ly), DIM, f.xs)

    def diet_lines(self, k):
        flow, nkill = self.flows()
        eats = [(a, e["flow"]) for (a, b), e in self.edges.items() if b == k and e["flow"] > 0.01]
        tot = sum(v for _, v in eats) or 1
        eaten = [(b, e["flow"], nkill.get((k, b), 0)) for (a, b), e in self.edges.items() if a == k and e["flow"] > 0.01]
        return sorted(eats, key=lambda kv: -kv[1]), tot, sorted(eaten, key=lambda kv: -kv[2])

    def draw_side(self, scr, f, box, mouse):
        w = self.app.world
        x, y, wd = box.x, box.y, box.w
        k = self.hover or self.pinned
        when = "in the last year of life (~%d calendar days)" % (BIO_YEAR / CAL_DAY) if self.mode == "recent" \
            else "since the island began"
        if k in self.nodes:
            nd = self.nodes[k]
            draw_text(scr, f, k, (x, y), self.node_color(k, nd), f.l)
            y += 30
            if nd["kind"] == "res":
                for ln in wrap(nd["blurb"], f.s, wd):
                    draw_text(scr, f, ln, (x, y), TEXT)
                    y += 17
            else:
                status = ("native" if nd["native"] else "introduced") if nd["kind"] == "animal" else "people"
                draw_text(scr, f, "%s  -  %s" % (status, "%d alive" % nd["n"] if nd["n"] else "none left"), (x, y), DIM)
                y += 20
            eats, tot, eaten = self.diet_lines(k)
            y += 6
            if eats:
                draw_text(scr, f, "Gets its energy from (%s)" % ("recently" if self.mode == "recent" else "all time"),
                          (x, y), ACCENT, f.b)
                y += 20
                for a, v in eats[:7]:
                    share = v / tot
                    pygame.draw.rect(scr, LINE, (x, y + 4, 90, 8), border_radius=3)
                    pygame.draw.rect(scr, self.node_color(a, self.nodes[a]), (x, y + 4, max(2, int(90 * share)), 8),
                                     border_radius=3)
                    draw_text(scr, f, "%s  %d%%" % (a, 100 * share), (x + 98, y), TEXT, f.xs)
                    y += 16
                y += 8
            if eaten:
                draw_text(scr, f, "Eaten by", (x, y), ACCENT, f.b)
                y += 20
                for b, v, n in eaten[:7]:
                    txt = "%s - %d killed" % (b, round(n)) if n >= 0.5 else "%s" % b
                    draw_text(scr, f, txt, (x, y), (240, 130, 110) if (self.nodes[k].get("native") and
                                                                      self.nodes[b].get("native") is False) else TEXT,
                              f.xs)
                    y += 16
                y += 8
            if not eats and not eaten:
                draw_text(scr, f, "No feeding recorded %s." % when, (x, y), DIM, f.xs, maxw=wd)
                y += 18
            if nd["kind"] == "animal" and nd["sp"].blurb:
                for ln in wrap(nd["sp"].blurb, f.xs, wd)[:5]:
                    draw_text(scr, f, ln, (x, y), DIM, f.xs)
                    y += 14
            draw_text(scr, f, "Click a circle to keep it highlighted.", (x, box.bottom - 16), DIM, f.xs)
            return
        draw_text(scr, f, "What's happening", (x, y), ACCENT, f.b)
        y += 22
        for ln in insights(w):
            for wl in wrap(ln, f.s, wd):
                if y > box.bottom - 150:
                    break
                draw_text(scr, f, wl, (x, y), TEXT)
                y += 16
            y += 6
        y = max(y + 4, box.bottom - 140)
        draw_text(scr, f, "Latest kills", (x, y), ACCENT, f.b)
        y += 20
        if not w.kill_log:
            draw_text(scr, f, "None yet.", (x, y), DIM, f.xs)
        for (t, eater, prey, stage, px, py) in w.kill_log[::-1][:6]:
            ago = max(0, (w.tick - t)) / CAL_DAY
            when_s = "today" if ago < 1 else "%d days ago" % ago
            pnode = self.nodes.get(prey, {})
            col = (240, 130, 110) if pnode.get("native") and eater != "People" and \
                not self.nodes.get(eater, {}).get("native", True) else TEXT
            what = ("a %s %s" % (prey, stage)) if stage != "adult" else ("a %s" % prey)
            draw_text(scr, f, "%s ate %s  (%s)" % (eater if eater != "People" else "People", what, when_s),
                      (x, y), col, f.xs, maxw=wd)
            y += 15

    def handle(self, ev, pos):
        if ev.type == pygame.KEYDOWN and ev.key in (pygame.K_ESCAPE, pygame.K_f):
            self.app.foodweb_view = None
            return
        if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            for b in self.buttons:
                if b.handle(ev, pos):
                    return
            for k, nd in self.nodes.items():
                if math.hypot(pos[0] - nd["x"], pos[1] - nd["y"]) < nd["r"] + 4:
                    self.pinned = None if self.pinned == k else k
                    return
            self.pinned = None


def insights(w):
    """Plain-language notes about cascades happening in the food web right now."""
    out = []
    if w.mast > 0:
        out.append("MAST YEAR: the forest is dropping a flood of seed. Rats (and mice) will boom on it within "
                   "months; stoats then boom on the rats. When the seed runs out, the hungry predators turn on "
                   "birds and their nests.")
    lh = w.long_history
    if len(lh) > 6:
        span = BIO_YEAR
        old = None
        for h in reversed(lh):
            if lh[-1]["tick"] - h["tick"] >= span:
                old = h
                break
        if old:
            changes = []
            for name, now in lh[-1]["species"].items():
                was = old["species"].get(name, 0)
                if max(was, now) >= 8:
                    ch = (now - was) / max(1, was)
                    if abs(ch) >= 0.4:
                        changes.append((ch, name, was, now))
            changes.sort(key=lambda c: -abs(c[0]))
            for ch, name, was, now in changes[:3]:
                out.append("%s %s from %d to %d over the last year of life." % (
                    name, "boomed" if ch > 0 else "crashed", was, now))
    # biggest killers of native wildlife recently
    natives = {sp.name for sp in w.animal_species if sp.native}
    intro = {sp.name for sp in w.animal_species if not sp.native}
    kills = sorted([(n, prey, eater) for (prey, eater), n in w.web_n.items()
                    if prey in natives and (eater in intro or eater == "People") and n >= 1], reverse=True)
    for n, prey, eater in kills[:2]:
        who = "People hunted" if eater == "People" else "%ss killed" % eater if not eater.endswith("s") else \
            "%s killed" % eater
        out.append("%s about %d %s recently." % (who, n, prey))
    if kills:
        out.append("Native birds evolved with no land mammals, so they don't recognise rats, stoats and cats as "
                   "danger - and their eggs and chicks are easy prey.")
    if not out:
        out.append("The web is quiet: food flows from plants, seed, nectar and dead matter up to the birds. "
                   "Introduce a species, or wait for a mast year, and watch how the links change.")
    out.append("Biology runs %dx faster than the calendar here: one 'year of life' is about %d calendar days."
               % (LIFE_SPEED, BIO_YEAR / CAL_DAY))
    return out
