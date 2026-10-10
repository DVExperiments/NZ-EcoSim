"""
report.py - export a class report: a printable PDF (written without any extra libraries) plus
CSV files of the raw data, so students can hand in what they saw and what they changed.
"""
import csv
import datetime
import os
import re
import subprocess
import sys
import zlib

import pygame

from config import (CAL_DAY, BIO_YEAR, LIFE_SPEED, YEAR_TICKS, DIFFICULTIES, DEFAULT_SETTINGS, age_text)
import ui_kit
from ui_kit import draw_text, wrap, Button, draw_pie
_THEMED = True
from ui_kit import PANEL, PANEL2, LINE, TEXT, DIM, ACCENT, INPUT, GRAPH

PAGE_W, PAGE_H = 1240, 1754          # A4 at 150 dpi
MARGIN = 90
INK = (25, 28, 34)
SOFT = (95, 102, 114)
RULE = (205, 210, 218)
HEAD = (40, 110, 80)
GOOD = (40, 150, 90)
BAD = (200, 70, 60)


class PageFonts:
    """Bigger fonts for printing (same attribute names as ui_kit.Fonts)."""

    def __init__(self, scale=1.0):
        names = "segoeui,helveticaneue,arial,dejavusans"
        k = scale
        self.xs = pygame.font.SysFont(names, int(17 * k))
        self.s = pygame.font.SysFont(names, int(19 * k))
        self.m = pygame.font.SysFont(names, int(21 * k))
        self.b = pygame.font.SysFont(names, int(20 * k), bold=True)
        self.l = pygame.font.SysFont(names, int(30 * k), bold=True)
        self.xl = pygame.font.SysFont(names, int(44 * k), bold=True)
        self.cache = {}

    def render(self, font, text, color):
        return font.render(text, True, color)


# ----------------------------------------------------------------------------
# minimal PDF writer: each page is one image (Flate-compressed RGB)
# ----------------------------------------------------------------------------
def write_pdf(path, pages, title="NZ EcoSim report"):
    objs = []

    def add(b):
        objs.append(b)
        return len(objs)

    cat = add(None)
    pages_id = add(None)
    kids = []
    for surf in pages:
        w, h = surf.get_size()
        raw = getattr(pygame.image, "tobytes", pygame.image.tostring)(surf, "RGB")
        data = zlib.compress(raw, 6)
        img = add(b"<< /Type /XObject /Subtype /Image /Width %d /Height %d /ColorSpace /DeviceRGB "
                  b"/BitsPerComponent 8 /Filter /FlateDecode /Length %d >>\nstream\n" % (w, h, len(data))
                  + data + b"\nendstream")
        content = b"q 595.28 0 0 841.89 0 0 cm /Im0 Do Q"
        cs = add(b"<< /Length %d >>\nstream\n" % len(content) + content + b"\nendstream")
        pg = add(b"<< /Type /Page /Parent %d 0 R /MediaBox [0 0 595.28 841.89] /Resources << /XObject << /Im0 %d 0 R >> "
                 b">> /Contents %d 0 R >>" % (pages_id, img, cs))
        kids.append(pg)
    objs[cat - 1] = b"<< /Type /Catalog /Pages %d 0 R >>" % pages_id
    objs[pages_id - 1] = b"<< /Type /Pages /Kids [%s] /Count %d >>" % (
        b" ".join(b"%d 0 R" % k for k in kids), len(kids))
    safe = re.sub(r"[^A-Za-z0-9 .,:-]", "", title).encode()
    info = add(b"<< /Title (%s) /Producer (NZ EcoSim) >>" % safe)
    out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = []
    for i, o in enumerate(objs, 1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % i + o + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1)
    for off in offsets:
        out += b"%010d 00000 n \n" % off
    out += b"trailer\n<< /Size %d /Root %d 0 R /Info %d 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (
        len(objs) + 1, cat, info, xref)
    with open(path, "wb") as fh:
        fh.write(out)


# ----------------------------------------------------------------------------
# page layout helper
# ----------------------------------------------------------------------------
class Doc:
    def __init__(self, f, title, subtitle):
        self.f = f
        self.title, self.subtitle = title, subtitle
        self.pages = []
        self.new_page()

    def new_page(self):
        self.page = pygame.Surface((PAGE_W, PAGE_H))
        self.page.fill((255, 255, 255))
        self.pages.append(self.page)
        pygame.draw.rect(self.page, HEAD, (0, 0, PAGE_W, 14))
        draw_text(self.page, self.f, self.title, (MARGIN, 34), SOFT, self.f.xs)
        draw_text(self.page, self.f, "page %d" % len(self.pages), (PAGE_W - MARGIN, 34), SOFT, self.f.xs, "topright")
        self.y = 80

    def need(self, h):
        if self.y + h > PAGE_H - 70:
            self.new_page()

    def heading(self, text, keep=120):
        self.need(70 + keep)
        self.y += 10
        draw_text(self.page, self.f, text, (MARGIN, self.y), HEAD, self.f.l)
        self.y += 42
        pygame.draw.line(self.page, RULE, (MARGIN, self.y - 6), (PAGE_W - MARGIN, self.y - 6), 2)

    def sub(self, text, color=INK):
        self.need(40)
        draw_text(self.page, self.f, text, (MARGIN, self.y), color, self.f.b)
        self.y += 30

    def para(self, text, color=INK, font=None, indent=0, gap=8):
        font = font or self.f.s
        lh = font.get_linesize() + 2
        for ln in wrap(text, font, PAGE_W - 2 * MARGIN - indent):
            self.need(lh)
            draw_text(self.page, self.f, ln, (MARGIN + indent, self.y), color, font)
            self.y += lh
        self.y += gap

    def bullet(self, text, color=INK, mark="-", mark_color=None):
        font = self.f.s
        lh = font.get_linesize() + 2
        lines = wrap(text, font, PAGE_W - 2 * MARGIN - 30)
        self.need(lh * min(2, len(lines)))
        draw_text(self.page, self.f, mark, (MARGIN + 4, self.y), mark_color or color, self.f.b)
        for ln in lines:
            self.need(lh)
            draw_text(self.page, self.f, ln, (MARGIN + 30, self.y), color, font)
            self.y += lh
        self.y += 3

    def table(self, rows, widths, header=None):
        font = self.f.xs
        lh = font.get_linesize() + 6
        x0 = MARGIN
        if header:
            self.need(lh * 2)
            pygame.draw.rect(self.page, (232, 240, 236), (x0, self.y - 3, sum(widths), lh))
            x = x0
            for c, wdt in zip(header, widths):
                draw_text(self.page, self.f, c, (x + 6, self.y), HEAD, font, maxw=wdt - 10)
                x += wdt
            self.y += lh
        for i, row in enumerate(rows):
            cells = [wrap(str(c), font, wdt - 12) for c, wdt in zip(row, widths)]
            h = max(len(c) for c in cells) * (font.get_linesize()) + 6
            self.need(h)
            if i % 2:
                pygame.draw.rect(self.page, (246, 247, 249), (x0, self.y - 3, sum(widths), h))
            x = x0
            for lines, wdt in zip(cells, widths):
                for k, ln in enumerate(lines):
                    draw_text(self.page, self.f, ln, (x + 6, self.y + k * font.get_linesize()), INK, font)
                x += wdt
            self.y += h
        self.y += 10

    def image(self, surf, caption=None):
        w = PAGE_W - 2 * MARGIN
        h = int(surf.get_height() * w / surf.get_width())
        self.need(h + 40)
        self.page.blit(pygame.transform.smoothscale(surf, (w, h)), (MARGIN, self.y))
        pygame.draw.rect(self.page, RULE, (MARGIN, self.y, w, h), 1)
        self.y += h + 8
        if caption:
            self.para(caption, SOFT, self.f.xs)


# ----------------------------------------------------------------------------
# content
# ----------------------------------------------------------------------------
def bio_years_since_start(w):
    return (w.tick - w.start_tick) / BIO_YEAR


def key_stats(w):
    import views
    exts = [m for m in w.milestones if m["cat"] == "extinction" and m["key"] != "collapse"]
    lh = w.long_history
    lost = 100 * (1 - lh[-1]["trees"] / max(1, w.start_trees or 1)) if (lh and w.start_trees) else 0
    intro = [m["title"].replace(" arrives", "").replace(" already established", "") for m in w.milestones
             if m["cat"] == "arrival"]
    nat = sum(w.counts.get(sp, 0) for sp in w.animal_species if sp.native)
    pest = sum(w.counts.get(sp, 0) for sp in w.animal_species if not sp.native)
    return [
        ("Native species alive", "%d of %d" % (getattr(w, "native_alive", 0), getattr(w, "native_total", 0))),
        ("Native animals / introduced animals now", "%d / %d" % (nat, pest)),
        ("Extinctions", ", ".join(m["title"].split(" is extinct")[0] for m in exts) or "none"),
        ("Forest lost since the start", "%d%%" % max(0, lost)),
        ("People now / at peak", "%d / %d" % (len(w.people), w.peak_people)),
        ("Clans founded / wars", "%d / %d" % (len(w.tribes), sum(1 for m in w.milestones if m["key"].startswith("war:")))),
        ("Species introduced", ", ".join(intro) or "none"),
        ("Mast years", str(getattr(w, "mast_count", 0))),
        ("Ecosystem vitality now", "%d (%s)" % (w.vitality, w.mood)),
        ("Ecological collapse", "yes, on %s" % next((m["date"] for m in w.milestones if m["key"] == "collapse"), "?")
         if w.collapsed else "no"),
    ]


def what_you_changed(w):
    out = []
    for k, n in sorted(getattr(w, "actions", {}).items(), key=lambda kv: -kv[1]):
        out.append("%s  (x%d)" % (k, n))
    for k, v in w.settings.items():
        d = DEFAULT_SETTINGS.get(k)
        if k in ("time",) or d is None:
            continue
        if abs(v - d) > 1e-3 and not (k == "rain" and abs(v - w.opts.get("wetness", 1.0)) < 1e-3):
            out.append("Changed %s from %.2f to %.2f" % (k, d, v))
    for m in w.milestones:
        if m["cat"] == "conservation" and m["key"].startswith("first_"):
            out.append("%s - %s" % (m["date"], m["title"]))
    return out


def reflection_questions(w):
    import views
    qs = []
    exts = [m["title"].split(" is extinct")[0] for m in w.milestones if m["cat"] == "extinction" and m["key"] != "collapse"]
    if exts:
        name = exts[0]
        qs.append("%s was the first species to go extinct (main cause: %s). What could have been done, and when, "
                  "to save it?" % (name, views.main_cause(w, name)))
    if any(m["cat"] == "arrival" for m in w.milestones):
        qs.append("Which introduced species did the most damage? Use the food web to explain how it affected "
                  "other species, not just its own prey.")
    if getattr(w, "mast_count", 0):
        qs.append("Describe what happened after a mast year. Which populations rose first, which followed, and why?")
    if w.people:
        qs.append("How did the needs of people (food, timber, land) conflict with protecting native species? "
                  "Was there a way to meet both?")
    st = getattr(w, "scenario", None)
    if st:
        qs.append("Which of your actions made the biggest difference to the lesson goal? What would you do "
                  "differently if you tried again?")
    qs.append("Which real New Zealand conservation story does your island remind you of?")
    return qs


def lifecycle_image(w):
    import views
    s = pygame.Surface((760, 300))
    s.fill(ui_kit.GRAPH)
    f = ui_kit.Fonts()
    views.draw_lifecycle_chart(s, f, w, pygame.Rect(0, 0, 760, 300))
    return s


def species_image(w, native=True):
    """Line chart of each native (or introduced) species over the whole history."""
    f = ui_kit.Fonts()
    s = pygame.Surface((760, 280))
    s.fill(ui_kit.GRAPH)
    lh = w.long_history
    sps = [sp for sp in w.animal_species if sp.native == native and not getattr(sp, "marine", False)]
    sps = [sp for sp in sps if any(h["species"].get(sp.name, 0) for h in lh)]
    draw_text(s, f, ("Native" if native else "Introduced") + " animals, number alive over time", (10, 6), ui_kit.TEXT, f.b)
    if len(lh) < 2 or not sps:
        draw_text(s, f, "No data yet", (380, 140), ui_kit.DIM, f.s, "center")
        return s
    inner = pygame.Rect(40, 30, 560, 220)
    t0, t1 = lh[0]["tick"], max(lh[-1]["tick"], lh[0]["tick"] + 1)
    mx = max(1, max(h["species"].get(sp.name, 0) for h in lh for sp in sps))
    pygame.draw.line(s, ui_kit.LINE, inner.bottomleft, inner.bottomright)
    pygame.draw.line(s, ui_kit.LINE, inner.bottomleft, inner.topleft)
    draw_text(s, f, str(mx), (inner.x - 4, inner.y), ui_kit.DIM, f.xs, "topright")
    draw_text(s, f, "0", (inner.x - 4, inner.bottom), ui_kit.DIM, f.xs, "bottomright")
    draw_text(s, f, lh[0]["date"], (inner.x, inner.bottom + 4), ui_kit.DIM, f.xs)
    draw_text(s, f, lh[-1]["date"], (inner.right, inner.bottom + 4), ui_kit.DIM, f.xs, "topright")
    for i, sp in enumerate(sps):
        pts = [(inner.x + (h["tick"] - t0) / (t1 - t0) * inner.w,
                inner.bottom - h["species"].get(sp.name, 0) / mx * inner.h) for h in lh]
        col = sp.color if sum(sp.color) > 200 else tuple(min(255, c + 80) for c in sp.color)
        pygame.draw.lines(s, col, False, pts, 2)
        ly = 34 + i * 18
        pygame.draw.rect(s, col, (620, ly + 4, 14, 6))
        draw_text(s, f, "%s (%d)" % (sp.name, w.counts.get(sp, 0)), (640, ly), ui_kit.TEXT, f.xs)
    return s


def foodweb_image(app):
    import foodweb
    f = ui_kit.Fonts()
    s = pygame.Surface((900, 560))
    s.fill(ui_kit.GRAPH)
    fw = foodweb.FoodWebView(app)
    fw.mode = "total"
    fw.show_possible = False
    area = pygame.Rect(0, 0, 900, 560)
    fw.build(area)
    fw.draw_graph(s, f, area, (-999, -999), static=True)
    return s, fw


def pies_image(w):
    import views
    f = ui_kit.Fonts()
    s = pygame.Surface((760, 220))
    s.fill(ui_kit.GRAPH)
    fauna = [(w.counts.get(sp, 0), sp.color, sp.name) for sp in w.animal_species if w.counts.get(sp, 0)]
    if w.people:
        fauna.append((len(w.people), (235, 200, 160), "People"))
    fauna.sort(key=lambda a: -a[0])
    groups = views.native_death_causes(w)
    causes = [(groups.get(lab, 0), col, lab) for lab, col in views.CAUSE_GROUPS if groups.get(lab, 0)]
    for cx, items, title in ((110, fauna, "Animals alive now"), (490, causes, "What killed native animals")):
        draw_text(s, f, title, (cx - 100, 8), ui_kit.TEXT, f.b)
        if not items:
            draw_text(s, f, "nothing yet", (cx, 120), ui_kit.DIM, f.s, "center")
            continue
        draw_pie(s, (cx, 120), 80, [(a[0], a[1]) for a in items], hole=0.45)
        tot = sum(a[0] for a in items) or 1
        for k, (n, col, lab) in enumerate(items[:10]):
            pygame.draw.rect(s, col, (cx + 95, 38 + k * 17, 10, 10))
            draw_text(s, f, "%s %d%%" % (lab, 100 * n / tot), (cx + 110, 34 + k * 17), ui_kit.TEXT, f.xs)
    return s


def build_pages(app, name, klass, notes):
    import views
    import scenarios
    w = app.world
    old_theme = (app.ui.get("theme", "Dark"), app.ui.get("accent"))
    ui_kit.apply_theme("Light", None)
    try:
        f = PageFonts()
        doc = Doc(f, "NZ EcoSim class report  -  %s" % (name or "student"), "")
        p = doc.page
        draw_text(p, f, "NZ EcoSim", (MARGIN, 80), HEAD, f.xl)
        draw_text(p, f, "Class report", (MARGIN + f.xl.size("NZ EcoSim ")[0] + 6, 92), SOFT, f.l)
        doc.y = 150
        rows = [("Student", name or "-"), ("Class", klass or "-"),
                ("Exported", datetime.datetime.now().strftime("%d %B %Y, %H:%M")),
                ("Island", "%s Island, %s (seed %d)" % (w.region.capitalize(),
                                                         dict(__import__("world").GEOGRAPHIES).get(w.opts.get("geo"), ""),
                                                         w.seed)),
                ("Simulated time", "1 Sep, Year 1 to %s: %s of calendar time = about %.1f years in the lives of the "
                 "animals and people (life runs %dx faster than the calendar)" % (
                     w.stamp, age_text(w.tick - w.start_tick), bio_years_since_start(w), LIFE_SPEED)),
                ("Difficulty", DIFFICULTIES[getattr(w, "difficulty", "realistic")]["label"])]
        doc.table(rows, [260, PAGE_W - 2 * MARGIN - 260])
        st = getattr(w, "scenario", None)
        if st:
            sc = scenarios.BY_ID.get(st["id"], {})
            doc.heading("Lesson: %s" % sc.get("title", st["id"]))
            res = {"won": ("GOAL ACHIEVED", GOOD), "lost": ("GOAL NOT ACHIEVED", BAD),
                   "active": ("STILL IN PROGRESS", SOFT)}[st["status"]]
            doc.sub(res[0], res[1])
            if st.get("message"):
                doc.para(st["message"])
            for text, prog, state in st.get("goals", []):
                mark, col = {"done": ("v", GOOD), "failed": ("x", BAD)}.get(state, ("-", SOFT))
                doc.bullet("%s  (%d%%)" % (text, 100 * prog), mark=mark, mark_color=col)
            if sc.get("fact"):
                doc.para("In the real Aotearoa: " + sc["fact"], SOFT, f.s)
        doc.heading("Key statistics")
        doc.table(key_stats(w), [420, PAGE_W - 2 * MARGIN - 420])
        doc.heading("My observations")
        if notes.strip():
            for para in notes.split("\n"):
                doc.para(para)
        else:
            doc.para("(no notes written)", SOFT)
        # charts
        doc.heading("How the ecosystem changed", keep=500)
        doc.image(lifecycle_image(w), "Lifecycle of the ecosystem: native animals, introduced animals, people, forest "
                                      "and vitality. Shaded bands show the stages.")
        for lab, a, b, col in views.stages(w):
            if b - a < CAL_DAY:
                continue
            doc.bullet("%s - lasted %s (%.1f years of life)" % (lab, age_text(b - a), (b - a) / BIO_YEAR))
        doc.image(species_image(w, True))
        doc.image(species_image(w, False))
        doc.image(pies_image(w))
        # food web
        doc.heading("Food web (whole history)", keep=700)
        img, fw = foodweb_image(app)
        doc.image(img, "Arrows run from food to eater; thicker arrows = more energy flowed along that link. "
                       "Red arrows: introduced predators eating native wildlife.")
        rows = []
        flows = sorted(w.web_total.items(), key=lambda kv: -kv[1])
        eat_tot = {}
        for (a, b), v in flows:
            eat_tot[b] = eat_tot.get(b, 0) + v
        for (a, b), v in flows[:16]:
            rows.append((b, a, "%d%%" % (100 * v / max(1e-6, eat_tot[b])), "%d" % w.web_n_total.get((a, b), 0) or ""))
        if rows:
            doc.table(rows, [270, 270, 250, PAGE_W - 2 * MARGIN - 790],
                      header=["Eater", "Food", "Share of its diet", "Animals killed"])
        # extinctions & causes
        exts = [m for m in w.milestones if m["cat"] == "extinction" and m["key"] != "collapse"]
        if exts:
            doc.heading("Extinctions")
            doc.table([(m["date"], m["title"].split(" is extinct")[0], views.main_cause(w, m["title"].split(" is extinct")[0]))
                       for m in exts], [240, 330, PAGE_W - 2 * MARGIN - 570], header=["Date", "Species", "Main cause"])
        if w.collapsed:
            doc.heading("Ecological collapse")
            cv = views.CollapseView.__new__(views.CollapseView)
            for para in cv.lessons(w, views.native_death_causes(w)):
                doc.para(para)
        doc.heading("What I changed")
        ch = what_you_changed(w)
        if ch:
            for c in ch:
                doc.bullet(c)
        else:
            doc.para("Nothing - the island was left to run on its own.", SOFT)
        doc.heading("Timeline of major events")
        ms = w.milestones
        if ms:
            doc.table([(m["date"], m["title"], m["text"]) for m in ms],
                      [190, 330, PAGE_W - 2 * MARGIN - 520], header=["Date", "Event", "Details"])
        else:
            doc.para("No major events yet.", SOFT)
        doc.heading("Questions to think about")
        for i, q in enumerate(reflection_questions(w), 1):
            doc.bullet(q, mark="%d." % i)
            doc.y += 40          # space to write
        return doc.pages
    finally:
        ui_kit.apply_theme(*old_theme)


def write_csvs(w, folder):
    lh = w.long_history
    names = [sp.name for sp in w.animal_species]
    with open(os.path.join(folder, "population_history.csv"), "w", newline="", encoding="utf-8-sig") as fh:
        cw = csv.writer(fh)
        cw.writerow(["date", "calendar_day", "years_of_life", "vitality", "native_animals", "introduced_animals",
                     "people", "forest_cells", "fish", "native_species_alive"] + names)
        for h in lh:
            cw.writerow([h["date"], round((h["tick"] - w.start_tick) / CAL_DAY, 1),
                         round((h["tick"] - w.start_tick) / BIO_YEAR, 2), round(h["vitality"], 1), h["natives"],
                         h["pests"], h["people"], h["trees"], round(h["fish"], 2), h["native_alive"]]
                        + [h["species"].get(n, 0) for n in names])
    with open(os.path.join(folder, "events.csv"), "w", newline="", encoding="utf-8-sig") as fh:
        cw = csv.writer(fh)
        cw.writerow(["date", "year", "category", "event", "details"])
        for m in w.milestones:
            cw.writerow([m["date"], m["year"], m["cat"], m["title"], m["text"]])
    origin = {sp.name: ("native" if sp.native else "introduced") for sp in w.animal_species}
    with open(os.path.join(folder, "deaths.csv"), "w", newline="", encoding="utf-8-sig") as fh:
        cw = csv.writer(fh)
        cw.writerow(["species", "origin", "cause_of_death", "number"])
        for (n, cause), k in sorted(w.death_totals.items(), key=lambda kv: (kv[0][0], -kv[1])):
            cw.writerow([n, origin.get(n, ""), cause, k])
    with open(os.path.join(folder, "food_web.csv"), "w", newline="", encoding="utf-8-sig") as fh:
        cw = csv.writer(fh)
        cw.writerow(["eater", "food", "energy_all_time", "animals_killed_all_time", "energy_last_year_of_life"])
        for (a, b), v in sorted(w.web_total.items(), key=lambda kv: -kv[1]):
            cw.writerow([b, a, round(v, 1), w.web_n_total.get((a, b), 0), round(w.web.get((a, b), 0), 1)])
    with open(os.path.join(folder, "my_actions.csv"), "w", newline="", encoding="utf-8-sig") as fh:
        cw = csv.writer(fh)
        cw.writerow(["what I did"])
        for c in what_you_changed(w):
            cw.writerow([c])


def export(app, name, klass, notes, base_dir):
    w = app.world
    stamp = datetime.datetime.now().strftime("%Y-%m-%d_%H%M")
    who = re.sub(r"[^A-Za-z0-9_-]+", "_", name.strip())[:30] or "report"
    folder = os.path.join(base_dir, "NZ EcoSim reports", "%s_%s" % (who, stamp))
    os.makedirs(folder, exist_ok=True)
    pages = build_pages(app, name, klass, notes)
    safe = re.sub(r'[\\/:*?"<>|]+', "", name).strip().rstrip(".") or "student"
    pdf = os.path.join(folder, "NZ EcoSim report - %s.pdf" % safe)
    write_pdf(pdf, pages, "NZ EcoSim report %s" % name)
    write_csvs(w, folder)
    if notes.strip():
        with open(os.path.join(folder, "my_observations.txt"), "w", encoding="utf-8") as fh:
            fh.write(notes)
    w.actions["Exported a class report"] += 1
    return folder, pdf, len(pages)


def zip_folder(folder):
    import io
    import zipfile
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for name in sorted(os.listdir(folder)):
            z.write(os.path.join(folder, name), name)
    return buf.getvalue()


def open_folder(path):
    try:
        if sys.platform == "win32":
            os.startfile(path)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])
    except Exception:
        pass


# ----------------------------------------------------------------------------
# dialog
# ----------------------------------------------------------------------------
class TextBox:
    def __init__(self, label, multiline=False, limit=60):
        self.label, self.multiline, self.limit = label, multiline, limit
        self.text = ""
        self.active = False
        self.rect = pygame.Rect(0, 0, 0, 0)

    def draw(self, scr, f, rect):
        self.rect = pygame.Rect(rect)
        draw_text(scr, f, self.label, (self.rect.x, self.rect.y - 20), DIM, f.s)
        pygame.draw.rect(scr, INPUT, self.rect, border_radius=5)
        pygame.draw.rect(scr, ACCENT if self.active else LINE, self.rect, 1, border_radius=5)
        caret = "|" if self.active and (pygame.time.get_ticks() // 500) % 2 else ""
        if self.multiline:
            lines = wrap(self.text + caret, f.m, self.rect.w - 16)
            lh = 19
            maxl = (self.rect.h - 10) // lh
            for i, ln in enumerate(lines[-maxl:]):
                draw_text(scr, f, ln, (self.rect.x + 8, self.rect.y + 6 + i * lh), TEXT, f.m)
            if not self.text and not self.active:
                draw_text(scr, f, "What did you notice? What did you change, and what happened?",
                          (self.rect.x + 8, self.rect.y + 6), DIM, f.s)
        else:
            draw_text(scr, f, self.text + caret, (self.rect.x + 8, self.rect.centery), TEXT, f.m, "midleft",
                      maxw=self.rect.w - 16)

    def key(self, ev):
        if ev.type == pygame.KEYDOWN:
            if ev.key == pygame.K_BACKSPACE:
                self.text = self.text[:-1]
            elif ev.key in (pygame.K_RETURN, pygame.K_KP_ENTER) and self.multiline:
                self.text += "\n"
            elif ev.unicode and ev.unicode.isprintable() and len(self.text) < self.limit and \
                    not getattr(pygame, "TEXTINPUT", None):
                self.text += ev.unicode
        elif ev.type == getattr(pygame, "TEXTINPUT", -1):
            if len(self.text) + len(ev.text) <= self.limit:
                self.text += ev.text


class ReportView:
    W, H = 760, 600

    def __init__(self, app):
        self.app = app
        sw, sh = app.screen.get_size()
        self.rect = pygame.Rect((sw - self.W) // 2, (sh - self.H) // 2, self.W, self.H)
        prev = getattr(app, "report_fields", ("", "", ""))
        self.name = TextBox("Student name(s)", limit=60)
        self.klass = TextBox("Class / group", limit=40)
        self.notes = TextBox("My observations (included in the report)", multiline=True, limit=2000)
        self.name.text, self.klass.text, self.notes.text = prev
        self.name.active = True
        self.boxes = [self.name, self.klass, self.notes]
        self.buttons = []
        self.result = None
        self.error = None

    def remember(self):
        self.app.report_fields = (self.name.text, self.klass.text, self.notes.text)

    def do_export(self):
        self.remember()
        base = getattr(self.app, "base_dir", None) or os.getcwd()
        try:
            folder, pdf, n = export(self.app, self.name.text, self.klass.text, self.notes.text, base)
            self.result = (folder, pdf, n)
            self.error = None
            import webplatform
            if webplatform.WEB:
                webplatform.download(zip_folder(folder), "NZ EcoSim report - %s.zip" % (
                    self.name.text.strip() or "student"), "application/zip")
        except Exception as e:
            self.error = "Export failed: %s" % e

    def close(self):
        self.remember()
        self.app.report_view = None

    def draw(self, scr, f, mouse):
        from views import shade
        shade(scr)
        r = self.rect
        pygame.draw.rect(scr, PANEL, r, border_radius=10)
        pygame.draw.rect(scr, LINE, r, 1, border_radius=10)
        draw_text(scr, f, "Class report", (r.x + 24, r.y + 16), TEXT, f.l)
        draw_text(scr, f, "Save a printable PDF of this island's story - charts, food web, timeline, what you "
                          "changed - plus spreadsheet (CSV) files of the raw data.", (r.x + 24, r.y + 50), DIM, f.s,
                  maxw=r.w - 48)
        x, w = r.x + 24, r.w - 48
        self.name.draw(scr, f, (x, r.y + 104, w // 2 - 8, 30))
        self.klass.draw(scr, f, (x + w // 2 + 8, r.y + 104, w // 2 - 8, 30))
        self.notes.draw(scr, f, (x, r.y + 172, w, 230))
        self.buttons = []
        y = r.y + 420
        wd = self.app.world
        draw_text(scr, f, "The report covers %s to %s (%d years of life), %d events, %d species." % (
            "1 Sep Y1", wd.stamp, bio_years_since_start(wd), len(wd.milestones), len(wd.animal_species)),
                  (x, y), DIM, f.xs)
        if self.result:
            folder, pdf, n = self.result
            import webplatform
            if webplatform.WEB:
                draw_text(scr, f, "Downloaded a zip with a %d-page PDF and 5 CSV files - check your Downloads." % n,
                          (x, y + 26), (126, 206, 146), f.b, maxw=w)
            else:
                draw_text(scr, f, "Saved a %d-page PDF and 5 CSV files to:" % n, (x, y + 26), (126, 206, 146), f.b)
                draw_text(scr, f, folder, (x, y + 48), TEXT, f.xs, maxw=w)
                b = Button("Open folder", lambda: open_folder(folder))
                b.draw(scr, f, (x, r.bottom - 50, 140, 32), b.rect.collidepoint(mouse), f.b)
                self.buttons.append(b)
        if self.error:
            draw_text(scr, f, self.error, (x, y + 26), (240, 110, 100), f.s, maxw=w)
        b = Button("Export PDF + CSV", self.do_export)
        b.draw(scr, f, (r.right - 360, r.bottom - 50, 200, 32), b.rect.collidepoint(mouse), f.b)
        self.buttons.append(b)
        b = Button("Close", self.close)
        b.draw(scr, f, (r.right - 144, r.bottom - 50, 120, 32), b.rect.collidepoint(mouse), f.b)
        self.buttons.append(b)

    def handle(self, ev, pos):
        if ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE:
            self.close()
            return
        if ev.type == pygame.KEYDOWN and ev.key == pygame.K_TAB:
            i = next((k for k, b in enumerate(self.boxes) if b.active), -1)
            for b in self.boxes:
                b.active = False
            self.boxes[(i + 1) % len(self.boxes)].active = True
            return
        if ev.type in (pygame.KEYDOWN, getattr(pygame, "TEXTINPUT", -1)):
            for b in self.boxes:
                if b.active:
                    b.key(ev)
                    if ev.type == pygame.KEYDOWN and ev.key in (pygame.K_RETURN, pygame.K_KP_ENTER) \
                            and not b.multiline:
                        b.active = False
                        nxt = self.boxes[(self.boxes.index(b) + 1) % len(self.boxes)]
                        nxt.active = True
                    return
            return
        if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            for b in self.buttons:
                if b.handle(ev, pos):
                    return
            for b in self.boxes:
                b.active = b.rect.collidepoint(pos)
