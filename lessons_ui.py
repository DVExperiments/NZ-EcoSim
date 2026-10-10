"""
lessons_ui.py - windows for teaching mode: choosing a lesson (scenario), and the result screen.
"""
import pygame

from config import DIFFICULTIES, DIFFICULTY_ORDER, LIFE_SPEED, CAL_DAY, BIO_YEAR, age_text
from ui_kit import (PANEL, PANEL2, LINE, TEXT, DIM, ACCENT, SEL, HOVER, GRAPH, FACT, draw_text, wrap, Button)
_THEMED = True
import scenarios

GOOD = (126, 206, 146)
BAD = (240, 110, 100)


def shade(scr, alpha=170):
    s = pygame.Surface(scr.get_size(), pygame.SRCALPHA)
    s.fill((0, 0, 0, alpha))
    scr.blit(s, (0, 0))


def paragraph(scr, f, text, x, y, w, color=TEXT, font=None, lh=17):
    font = font or f.s
    for ln in wrap(text, font, w):
        draw_text(scr, f, ln, (x, y), color, font)
        y += lh
    return y


class LessonPicker:
    W, H = 1080, 660

    def __init__(self, app):
        self.app = app
        sw, sh = app.screen.get_size()
        self.rect = pygame.Rect((sw - self.W) // 2, (sh - self.H) // 2, self.W, self.H)
        self.sel = scenarios.SCENARIOS[0]["id"]
        self.difficulty = getattr(app.world, "difficulty", "realistic")
        self.buttons = []

    def start(self):
        if self.sel == "free":
            from views import NewWorldView
            self.app.lesson_picker = None
            nv = NewWorldView(self.app)
            nv.opts["difficulty"] = self.difficulty
            self.app.newworld = nv
            return
        self.app.lesson_picker = None
        scenarios.start(self.app, self.sel, self.difficulty)
        sc = scenarios.BY_ID[self.sel]
        self.app.toast("Lesson started: %s" % sc["title"])
        self.app.panel_tab = "learn"

    def draw(self, scr, f, mouse):
        shade(scr)
        r = self.rect
        pygame.draw.rect(scr, PANEL, r, border_radius=10)
        pygame.draw.rect(scr, LINE, r, 1, border_radius=10)
        draw_text(scr, f, "Lessons", (r.x + 24, r.y + 16), TEXT, f.l)
        draw_text(scr, f, "Ready-made challenges based on real New Zealand conservation stories. Each one builds a "
                          "new island.", (r.x + 130, r.y + 24), DIM)
        self.buttons = []
        b = Button("Close", lambda: setattr(self.app, "lesson_picker", None))
        b.draw(scr, f, (r.right - 100, r.y + 16, 76, 26), b.rect.collidepoint(mouse))
        self.buttons.append(b)
        # list
        x, y = r.x + 24, r.y + 64
        items = [(s["id"], s["title"], s["short"]) for s in scenarios.SCENARIOS] + \
                [("free", "Free play", "Build your own island and experiment.")]
        for sid, title, short in items:
            rr = pygame.Rect(x, y, 300, 62)
            on = sid == self.sel
            pygame.draw.rect(scr, SEL if on else (HOVER if rr.collidepoint(mouse) else PANEL2), rr, border_radius=8)
            draw_text(scr, f, title, (rr.x + 12, rr.y + 9), TEXT, f.b)
            draw_text(scr, f, short, (rr.x + 12, rr.y + 32), DIM if not on else TEXT, f.xs, maxw=rr.w - 20)
            b = Button("", lambda k=sid: setattr(self, "sel", k))
            b.rect = rr
            self.buttons.append(b)
            y += 68
        # detail
        dx = r.x + 350
        dw = r.right - 24 - dx
        y = r.y + 64
        if self.sel == "free":
            draw_text(scr, f, "Free play", (dx, y), ACCENT, f.l)
            y = paragraph(scr, f, "Generate any island you like and do whatever you want: land settlers, introduce "
                                  "species, set traps, change the physics. Export a class report at any time from "
                                  "the Learn tab.", dx, y + 36, dw)
        else:
            sc = scenarios.BY_ID[self.sel]
            draw_text(scr, f, sc["title"], (dx, y), ACCENT, f.l)
            y += 36
            for para in sc["brief"]:
                y = paragraph(scr, f, para, dx, y, dw, TEXT, f.m, 19) + 6
            draw_text(scr, f, "Goals", (dx, y + 4), ACCENT, f.b)
            y += 26
            for g in sc["goals"]:
                pygame.draw.circle(scr, ACCENT, (dx + 6, y + 8), 3)
                y = paragraph(scr, f, g, dx + 18, y, dw - 18)
            draw_text(scr, f, "Tips", (dx, y + 6), ACCENT, f.b)
            y += 28
            for t in sc["tips"]:
                pygame.draw.circle(scr, DIM, (dx + 6, y + 8), 3)
                y = paragraph(scr, f, t, dx + 18, y, dw - 18, DIM)
            draw_text(scr, f, "What you'll learn", (dx, y + 6), ACCENT, f.b)
            y = paragraph(scr, f, sc["learn"], dx, y + 28, dw)
        # difficulty
        y = r.bottom - 150
        draw_text(scr, f, "DIFFICULTY", (dx, y), ACCENT, f.b)
        bw = (dw - 12) // 3
        for i, k in enumerate(DIFFICULTY_ORDER):
            b = Button(DIFFICULTIES[k]["label"], lambda k=k: setattr(self, "difficulty", k),
                       lambda k=k: self.difficulty == k)
            b.draw(scr, f, (dx + i * (bw + 6), y + 22, bw, 26), b.rect.collidepoint(mouse))
            self.buttons.append(b)
        paragraph(scr, f, DIFFICULTIES[self.difficulty]["blurb"], dx, y + 56, dw, DIM, f.xs, 15)
        b = Button("Start lesson" if self.sel != "free" else "Choose an island...", self.start)
        b.draw(scr, f, (r.right - 220, r.bottom - 48, 196, 32), b.rect.collidepoint(mouse), f.b)
        self.buttons.append(b)
        draw_text(scr, f, "Starting replaces the current island.", (dx, r.bottom - 40), DIM, f.xs)

    def handle(self, ev, pos):
        if ev.type == pygame.KEYDOWN:
            if ev.key == pygame.K_ESCAPE:
                self.app.lesson_picker = None
            elif ev.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self.start()
            return
        if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            for b in self.buttons:
                if b.rect.collidepoint(pos):
                    b.action()
                    return


class LessonResult:
    W, H = 880, 520

    def __init__(self, app):
        self.app = app
        sw, sh = app.screen.get_size()
        self.rect = pygame.Rect((sw - self.W) // 2, (sh - self.H) // 2, self.W, self.H)
        self.buttons = []

    def close(self):
        self.app.lesson_result = None

    def again(self):
        w = self.app.world
        sid, diff = w.scenario["id"], w.difficulty
        self.app.lesson_result = None
        scenarios.start(self.app, sid, diff)

    def report(self):
        import report
        self.app.lesson_result = None
        self.app.report_view = report.ReportView(self.app)

    def others(self):
        self.app.lesson_result = None
        self.app.lesson_picker = LessonPicker(self.app)

    def draw(self, scr, f, mouse):
        import views
        w = self.app.world
        st = w.scenario
        sc = scenarios.BY_ID[st["id"]]
        won = st["status"] == "won"
        col = GOOD if won else BAD
        shade(scr, 190)
        r = self.rect
        pygame.draw.rect(scr, PANEL, r, border_radius=10)
        pygame.draw.rect(scr, col, r, 2, border_radius=10)
        draw_text(scr, f, ("Lesson complete!" if won else "Lesson failed") + "   -   " + sc["title"],
                  (r.x + 24, r.y + 16), col, f.xl)
        took = st.get("end", w.tick) - st["start"]
        draw_text(scr, f, "%s  -  after %s (%.1f years of life), on %s difficulty" % (
            st.get("end_date", w.stamp), age_text(took), took / BIO_YEAR, DIFFICULTIES[w.difficulty]["label"]),
                  (r.x + 26, r.y + 58), DIM)
        x, wd = r.x + 24, r.w - 48
        y = paragraph(scr, f, st["message"], x, r.y + 86, wd, TEXT, f.m, 20) + 8
        for text, prog, state in st.get("goals", []):
            c = GOOD if state == "done" else BAD if state == "failed" else DIM
            mark = {"done": "done", "failed": "failed"}.get(state, "%d%%" % (100 * prog))
            pygame.draw.rect(scr, PANEL2, (x, y + 3, 120, 10), border_radius=4)
            pygame.draw.rect(scr, c, (x, y + 3, max(3, int(120 * prog)), 10), border_radius=4)
            draw_text(scr, f, mark, (x + 128, y), c, f.xs)
            draw_text(scr, f, text, (x + 180, y), TEXT, f.s, maxw=wd - 180)
            y += 20
        y += 10
        # why: main causes of native deaths
        groups = views.native_death_causes(w)
        tot = sum(groups.values())
        if tot:
            top = sorted(groups.items(), key=lambda kv: -kv[1])[:3]
            draw_text(scr, f, "What killed native wildlife during the lesson", (x, y), ACCENT, f.b)
            y += 22
            draw_text(scr, f, ",   ".join("%s %d%%" % (k, 100 * v / tot) for k, v in top), (x, y), TEXT)
            y += 24
        did = __import__("report").what_you_changed(w)
        draw_text(scr, f, "What you did", (x, y), ACCENT, f.b)
        y += 22
        y = paragraph(scr, f, "; ".join(did[:8]) if did else "Nothing - you watched.", x, y, wd, TEXT) + 8
        box = pygame.Rect(x, y, wd, 0)
        lines = wrap("In the real Aotearoa: " + sc["fact"], f.s, wd - 24)
        box.h = 16 * len(lines) + 20
        pygame.draw.rect(scr, FACT, box, border_radius=8)
        for i, ln in enumerate(lines):
            draw_text(scr, f, ln, (box.x + 12, box.y + 10 + i * 16), TEXT)
        self.buttons = []
        for i, (lab, cb) in enumerate([("Export class report", self.report), ("Try again", self.again),
                                       ("Other lessons", self.others), ("Keep watching", self.close)]):
            b = Button(lab, cb)
            b.draw(scr, f, (r.x + 24 + i * 206, r.bottom - 48, 196, 32), b.rect.collidepoint(mouse), f.b)
            self.buttons.append(b)

    def handle(self, ev, pos):
        if ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE:
            self.close()
            return
        if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            for b in self.buttons:
                if b.handle(ev, pos):
                    return


def draw_goal_box(app, s, mouse):
    """Small lesson tracker on the map (top left)."""
    w = app.world
    st = getattr(w, "scenario", None)
    if not st:
        return None
    sc = scenarios.BY_ID.get(st["id"])
    if not sc:
        return None
    f = app.fonts
    goals = st.get("goals", [])
    h = 30 + 30 * len(goals)
    from config import GW
    r = pygame.Rect(GW * 5 - 310, 48, 300, h)
    box = pygame.Surface(r.size, pygame.SRCALPHA)
    from ui_kit import TIP
    box.fill((*TIP, 215))
    s.blit(box, r)
    status = st["status"]
    col = GOOD if status == "won" else BAD if status == "lost" else ACCENT
    pygame.draw.rect(s, col, r, 1, border_radius=6)
    draw_text(s, f, "LESSON: %s" % sc["title"] + ("  -  complete" if status == "won" else "  -  failed"
                                                   if status == "lost" else ""), (r.x + 10, r.y + 7), col, f.b,
              maxw=r.w - 20)
    y = r.y + 30
    for text, prog, state in goals:
        c = GOOD if state == "done" else BAD if state == "failed" else TEXT
        draw_text(s, f, text, (r.x + 10, y), c, f.xs, maxw=r.w - 20)
        pygame.draw.rect(s, LINE, (r.x + 10, y + 16, r.w - 20, 5), border_radius=3)
        pygame.draw.rect(s, GOOD if state == "done" else BAD if state == "failed" else ACCENT,
                         (r.x + 10, y + 16, max(2, int((r.w - 20) * prog)), 5), border_radius=3)
        y += 30
    return r
