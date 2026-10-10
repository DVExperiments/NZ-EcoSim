"""ui_kit.py - small pygame UI helpers and colour themes shared by NZ EcoSim's windows."""
import colorsys
import math
import sys

import pygame

BG = (20, 22, 26)
PANEL = (30, 33, 39)
PANEL2 = (38, 42, 50)
LINE = (55, 60, 70)
TEXT = (222, 224, 230)
DIM = (140, 146, 158)
ACCENT = (126, 206, 146)
WARN = (240, 170, 90)
SEL = (64, 110, 82)
HOVER = (52, 57, 67)
BOTTOM = (25, 27, 32)
GRAPH = (19, 21, 25)
TIP = (16, 18, 22)
INPUT = (24, 26, 31)
FACT = (36, 44, 46)
GRID = (32, 35, 41)

THEMES = {
    "Dark": dict(BG=(20, 22, 26), PANEL=(30, 33, 39), PANEL2=(38, 42, 50), LINE=(55, 60, 70), TEXT=(222, 224, 230),
                 DIM=(140, 146, 158), HOVER=(52, 57, 67), BOTTOM=(25, 27, 32), GRAPH=(19, 21, 25), TIP=(16, 18, 22),
                 INPUT=(24, 26, 31), FACT=(36, 44, 46), GRID=(32, 35, 41), accent=0.38),
    "Light": dict(BG=(228, 231, 236), PANEL=(244, 245, 247), PANEL2=(224, 228, 234), LINE=(196, 201, 210),
                  TEXT=(28, 30, 36), DIM=(96, 102, 114), HOVER=(210, 216, 225), BOTTOM=(236, 238, 242),
                  GRAPH=(250, 251, 252), TIP=(252, 252, 253), INPUT=(255, 255, 255), FACT=(222, 236, 234),
                  GRID=(225, 228, 233), accent=0.38),
    "Ocean": dict(BG=(10, 20, 34), PANEL=(16, 30, 48), PANEL2=(24, 42, 64), LINE=(42, 64, 90), TEXT=(220, 232, 245),
                  DIM=(128, 150, 176), HOVER=(32, 54, 80), BOTTOM=(13, 25, 40), GRAPH=(9, 18, 30), TIP=(9, 18, 30),
                  INPUT=(10, 20, 34), FACT=(18, 42, 54), GRID=(22, 38, 56), accent=0.53),
    "Forest": dict(BG=(16, 24, 18), PANEL=(24, 36, 28), PANEL2=(32, 48, 37), LINE=(52, 72, 56), TEXT=(226, 234, 222),
                   DIM=(140, 160, 140), HOVER=(42, 62, 47), BOTTOM=(20, 30, 23), GRAPH=(14, 22, 16), TIP=(14, 22, 16),
                   INPUT=(16, 24, 18), FACT=(30, 50, 40), GRID=(28, 42, 31), accent=0.27),
    "High contrast": dict(BG=(0, 0, 0), PANEL=(10, 10, 10), PANEL2=(36, 36, 36), LINE=(140, 140, 140),
                          TEXT=(255, 255, 255), DIM=(205, 205, 205), HOVER=(70, 70, 70), BOTTOM=(0, 0, 0),
                          GRAPH=(0, 0, 0), TIP=(0, 0, 0), INPUT=(0, 0, 0), FACT=(20, 30, 30), GRID=(40, 40, 40),
                          accent=0.14),
}


def apply_theme(name="Dark", accent_hue=None):
    """Swap the colour palette in every module that imported it."""
    th = THEMES.get(name, THEMES["Dark"])
    h = th["accent"] if accent_hue is None else accent_hue
    light = name == "Light"
    acc = colorsys.hsv_to_rgb(h, 0.55 if light else 0.42, 0.62 if light else 0.82)
    sel = colorsys.hsv_to_rgb(h, 0.35 if light else 0.45, 0.88 if light else 0.44)
    vals = dict(th)
    vals.pop("accent")
    vals["ACCENT"] = tuple(int(c * 255) for c in acc)
    vals["SEL"] = tuple(int(c * 255) for c in sel)
    for mod in list(sys.modules.values()):
        if mod is None:
            continue
        d = getattr(mod, "__dict__", None)
        if not d or not d.get("_THEMED"):
            continue
        for k, v in vals.items():
            if k in d:
                d[k] = v


_THEMED = True


# ----------------------------------------------------------------------------
# small UI kit
# ----------------------------------------------------------------------------
class Fonts:
    def __init__(self):
        names = "segoeui,helveticaneue,arial,dejavusans"
        self.xs = pygame.font.SysFont(names, 12)
        self.s = pygame.font.SysFont(names, 13)
        self.m = pygame.font.SysFont(names, 15)
        self.b = pygame.font.SysFont(names, 14, bold=True)
        self.l = pygame.font.SysFont(names, 22, bold=True)
        self.xl = pygame.font.SysFont(names, 28, bold=True)
        self.cache = {}

    def render(self, font, text, color):
        key = (id(font), text, color)
        surf = self.cache.get(key)
        if surf is None:
            if len(self.cache) > 4000:
                self.cache.clear()
            surf = font.render(text, True, color)
            self.cache[key] = surf
        return surf


def draw_text(surf, fonts, text, pos, color=TEXT, font=None, anchor="topleft", maxw=None):
    font = font or fonts.s
    if maxw is not None and font.size(text)[0] > maxw:
        while len(text) > 1 and font.size(text + "...")[0] > maxw:
            text = text[:-1]
        text = text.rstrip() + "..."
    img = fonts.render(font, text, color)
    r = img.get_rect(**{anchor: pos})
    surf.blit(img, r)
    return r


def wrap(text, font, width):
    lines = []
    for para in text.split("\n"):
        words = para.split(" ")
        cur = ""
        for wd in words:
            t = (cur + " " + wd).strip()
            if font.size(t)[0] <= width:
                cur = t
            else:
                if cur:
                    lines.append(cur)
                cur = wd
        lines.append(cur)
    return lines


class Slider:
    def __init__(self, key, label, lo, hi, val, fmt="{:.2f}", integer=False, tip=""):
        self.key, self.label, self.lo, self.hi = key, label, lo, hi
        self.value, self.fmt, self.integer, self.tip = val, fmt, integer, tip
        self.rect = pygame.Rect(0, 0, 0, 0)
        self.drag = False

    def set_from_x(self, x):
        t = (x - self.rect.x) / max(1, self.rect.w)
        t = min(1, max(0, t))
        v = self.lo + t * (self.hi - self.lo)
        if self.integer:
            v = round(v)
        self.value = v

    def handle(self, ev, pos):
        if self.rect.w == 0:
            return False
        if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1 and self.rect.inflate(0, 12).collidepoint(pos):
            self.drag = True
            self.set_from_x(pos[0])
            return True
        if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 3 and self.rect.inflate(0, 12).collidepoint(pos):
            return "reset"
        if ev.type == pygame.MOUSEMOTION and self.drag:
            self.set_from_x(pos[0])
            return True
        if ev.type == pygame.MOUSEBUTTONUP and ev.button == 1 and self.drag:
            self.drag = False
            return True
        return False

    def draw(self, surf, fonts, x, y, w, color=None):
        color = color or ACCENT
        draw_text(surf, fonts, self.label, (x, y), DIM)
        draw_text(surf, fonts, self.fmt.format(self.value), (x + w, y), TEXT, anchor="topright")
        self.rect = pygame.Rect(x, y + 17, w, 5)
        pygame.draw.rect(surf, LINE, self.rect, border_radius=3)
        t = (self.value - self.lo) / (self.hi - self.lo)
        fill = self.rect.copy()
        fill.w = int(self.rect.w * t)
        pygame.draw.rect(surf, color, fill, border_radius=3)
        pygame.draw.circle(surf, TEXT, (self.rect.x + fill.w, self.rect.centery), 6)


class Button:
    def __init__(self, label, action, toggled=None, color=None, tip=""):
        self.label, self.action, self.toggled, self.color, self.tip = label, action, toggled, color, tip
        self.rect = pygame.Rect(0, 0, 0, 0)

    def draw(self, surf, fonts, rect, hover=False, font=None, bg=None):
        self.rect = pygame.Rect(rect)
        on = self.toggled() if self.toggled else False
        c = SEL if on else (bg or (PANEL2 if not hover else HOVER))
        if hover and on:
            c = SEL
        pygame.draw.rect(surf, c, self.rect, border_radius=5)
        if on:
            pygame.draw.rect(surf, ACCENT, self.rect, 1, border_radius=5)
        if self.color:
            pygame.draw.circle(surf, self.color, (self.rect.x + 10, self.rect.centery), 5)
            draw_text(surf, fonts, self.label, (self.rect.x + 20, self.rect.centery), TEXT, font=font,
                      anchor="midleft", maxw=self.rect.w - 24)
        else:
            draw_text(surf, fonts, self.label, self.rect.center, TEXT, font=font, anchor="center",
                      maxw=self.rect.w - 8)

    def handle(self, ev, pos):
        if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1 and self.rect.collidepoint(pos):
            if self.action:
                self.action()
            return True
        return False


def draw_pie(surf, center, r, items, hole=0.0, start=-math.pi / 2):
    total = sum(v for v, _ in items)
    if total <= 0:
        pygame.draw.circle(surf, LINE, center, r, 2)
        return
    cx, cy = center
    a0 = start
    for v, col in items:
        if v <= 0:
            continue
        a1 = a0 + v / total * math.tau
        steps = max(2, int((a1 - a0) / 0.08))
        pts = [(cx, cy)] if hole <= 0 else []
        outer = [(cx + math.cos(a0 + (a1 - a0) * i / steps) * r, cy + math.sin(a0 + (a1 - a0) * i / steps) * r)
                 for i in range(steps + 1)]
        if hole > 0:
            inner = [(cx + math.cos(a1 - (a1 - a0) * i / steps) * r * hole,
                      cy + math.sin(a1 - (a1 - a0) * i / steps) * r * hole) for i in range(steps + 1)]
            pts = outer + inner
        else:
            pts += outer
        if len(pts) >= 3:
            pygame.draw.polygon(surf, col, pts)
        a0 = a1


