#!/usr/bin/env python3
"""
NZ EcoSim - an ecological simulation of Aotearoa New Zealand
A miniature simulated island that lives in a desktop window.

Weather, native forest and birds, introduced pests, fungi, microbes and people
interact.  Bend its physics, add species, settle tribes, set traps and fence
sanctuaries - or leave it alone and see what happens.  Clickable alerts explain
what is going on and how to help.  The world is saved when you close it and
keeps living (a little) while you're away.

Run:   python nz_ecosim.py          (needs:  pip install pygame numpy)
"""
import json
import math
import os
import pickle
import random
import sys
import time

import numpy as np

try:
    import pygame
except ImportError:
    print("NZ EcoSim needs pygame and numpy.  Install them with:\n\n    pip install pygame numpy\n")
    sys.exit(1)

from config import (GW, GH, DAY_TICKS, CAL_DAY, YEAR_TICKS, POP_CAP, DEFAULT_SETTINGS, NONE, HOUSE, FIELD, TRAP,
                    RUIN, age_text)
from world import World, dilate
from species_nz import AnimalSpecies, PlantSpecies, random_name, hue_color
from alerts import SEV_COLORS
import humans
import views
import webplatform
from webplatform import WEB
import foodweb
import scenarios
import lessons_ui
import report
from config import DIFFICULTIES, DIFFICULTY_ORDER, LIFE_SPEED, BIO_YEAR
from ui_kit import (BG, PANEL, PANEL2, LINE, TEXT, DIM, ACCENT, WARN, SEL, HOVER, BOTTOM, GRAPH, TIP,
                    INPUT, FACT, GRID, Fonts, draw_text, wrap, Slider, Button, draw_pie, apply_theme, THEMES)
_THEMED = True

# ----------------------------------------------------------------------------
# layout
# ----------------------------------------------------------------------------
CELL = 5
ZOOM_MIN = 0.6
VIEW_W, VIEW_H = GW * CELL, GH * CELL          # 1000 x 625
PANEL_W = 300
BOTTOM_H = 155
LW, LH = VIEW_W + PANEL_W, VIEW_H + BOTTOM_H   # 1300 x 780
FPS = 30
SAVE_VERSION = 5

def app_dir():
    if os.environ.get("NZ_ECOSIM_DIR"):
        return os.environ["NZ_ECOSIM_DIR"]
    if WEB:
        return "/home/pyodide"
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


SAVE_FILE = os.path.join(app_dir(), "nz_ecosim_save.pkl")
SETTINGS_FILE = os.path.join(app_dir(), "nz_ecosim_settings.json")
SHOT_DIR = os.path.join(app_dir(), "screenshots")


# ----------------------------------------------------------------------------
# rendering the world to pixels
# ----------------------------------------------------------------------------
def lerp_rgb(a, b, t):
    return a * (1 - t) + b * t


def colormap(v, stops):
    xs = [s[0] for s in stops]
    out = np.empty(v.shape + (3,), np.float32)
    for c in range(3):
        out[..., c] = np.interp(v, xs, [s[1][c] for s in stops])
    return out


SOIL_DRY = np.array([176, 154, 112], np.float32)
SOIL_WET = np.array([88, 70, 52], np.float32)
SAND = np.array([216, 200, 152], np.float32)
ROCK = np.array([138, 134, 130], np.float32)
DETRITUS_C = np.array([72, 52, 34], np.float32)
MYCEL_C = np.array([226, 216, 192], np.float32)
WATER_C = np.array([58, 118, 176], np.float32)
DEEP_C = np.array([28, 64, 120], np.float32)
SEA_SHALLOW = np.array([62, 140, 176], np.float32)
SEA_DEEP = np.array([18, 46, 98], np.float32)
SNOW_C = np.array([240, 244, 250], np.float32)
FIELD_A = np.array([204, 182, 96], np.float32)
FIELD_B = np.array([150, 158, 72], np.float32)
FIELD_POOR = np.array([150, 120, 80], np.float32)
RUIN_C = np.array([82, 74, 66], np.float32)
FENCE_C = np.array([40, 48, 48], np.float32)

_gx, _gy = np.meshgrid(np.arange(GW), np.arange(GH), indexing="ij")
FLOWER_MASK = np.random.default_rng(3).random((GW, GH)) < 0.22
MUSH_MASK = np.random.default_rng(5).random((GW, GH)) < 0.035
SHOAL_MASK = np.random.default_rng(9).random((GW, GH)) < 0.08
NOISE_TEX = (np.random.default_rng(7).random((GW, GH)).astype(np.float32) - 0.5) * 0.08
STRIPES = (_gy % 2 == 0)[..., None]

OVERLAYS = ["Normal", "Moisture", "Nutrients", "Microbe", "Fungi", "Temp", "Detritus", "Ocean"]

# (title, explanation, legend colour stops, low label, high label) for each view
OVERLAY_INFO = [
    ("Normal view", "The island as it looks: forest, tussock, wetlands, farms and the sea. Colours show each plant "
                    "species; flowers appear in spring and summer, mushrooms glow at night.", None, "", ""),
    ("Moisture", "How much water is in the soil and on the surface. Plants need it to grow; too little causes "
                 "drought and fire risk, too much drowns roots. Rivers and lakes show as deep blue.",
     [(0, (120, 80, 40)), (0.35, (200, 190, 120)), (0.6, (90, 170, 200)), (1, (20, 40, 140))], "dry", "flooded"),
    ("Nutrients", "Soil fertility - the food plants take from the soil. It comes from decomposed dead matter and "
                  "nitrogen-fixing plants, and is lost to erosion and farming. Fields turn brown when exhausted.",
     [(0, (15, 15, 20)), (0.4, (90, 110, 40)), (1, (240, 240, 90))], "poor", "fertile"),
    ("Microbes", "Density of soil bacteria. They break dead matter down into nutrients, bloom on carcasses, and "
                 "help disease spread. They like warm, wet ground.",
     [(0, (10, 8, 20)), (0.3, (70, 30, 120)), (0.7, (190, 90, 220)), (1, (255, 200, 255))], "few", "teeming"),
    ("Fungi", "Fungal mycelium threading through the soil. Fungi decompose leaf litter and wood, feed weta and "
              "beetles, and pass nutrients to tree roots. They prefer damp, shady forest.",
     [(0, (12, 12, 14)), (0.3, (80, 70, 60)), (1, (250, 240, 215))], "none", "dense"),
    ("Temperature", "Air temperature right now. Higher ground is colder (snow on the peaks), and it changes with "
                    "the seasons and time of day. Every species has a comfortable range.",
     [(0, (40, 60, 200)), (0.25, (140, 190, 255)), (0.5, (240, 240, 240)), (0.75, (250, 170, 70)), (1, (200, 30, 30))],
     "-10 C", "30 C"),
    ("Detritus", "Dead organic matter: fallen leaves, wood and carcasses. It feeds fungi, microbes and weta, which "
                 "turn it back into soil nutrients. Fire and erosion strip it away.",
     [(0, (12, 10, 8)), (0.4, (110, 70, 30)), (1, (240, 160, 70))], "bare", "thick litter"),
    ("Ocean", "Fish stocks in the sea (blue to white), shellfish beds in the shallows (orange) and mud washed off "
              "the land (brown). Overfishing and erosion both empty the coast.",
     [(0, (10, 20, 50)), (0.3, (30, 80, 150)), (0.7, (80, 200, 230)), (1, (230, 255, 255))], "no fish", "plenty"),
]


class Static:
    """Per-world precomputed layers for drawing."""
    def __init__(self, w):
        depth = np.clip((0.24 - w.height) / 0.24, 0, 1)[..., None]
        self.sea_col = lerp_rgb(SEA_SHALLOW, SEA_DEEP, depth ** 0.6)
        self.sea = w.sea
        self.sea3 = w.sea[..., None]
        self.coast = (w.coast & (w.height < 0.3))[..., None]
        self.rock = np.clip((w.height - 0.72) / 0.15, 0, 1)[..., None]
        self.shade = (0.82 + 0.32 * w.height + NOISE_TEX)[..., None]


def render_world(w, st, overlay, frame, smooth=False):
    if overlay == 0:
        rgb = render_natural(w, st, frame, smooth)
    elif overlay == 7:
        land = colormap(np.clip(w.height, 0, 1), [(0, (40, 44, 40)), (1, (90, 92, 90))])
        fish = colormap(np.clip(w.fish, 0, 1), [(0, (10, 20, 50)), (0.3, (30, 80, 150)), (0.7, (80, 200, 230)),
                                               (1, (230, 255, 255))])
        rgb = np.where(st.sea3, fish, land)
        sh = (w.shallow & (w.shellfish > 0.05))
        rgb[sh] = rgb[sh] * 0.6 + np.stack([w.shellfish[sh] * 240, w.shellfish[sh] * 160, w.shellfish[sh] * 60], -1) * 0.4
        sed = np.clip(w.sediment * 3, 0, 0.8)[..., None]
        rgb = rgb * (1 - sed) + np.array([150, 110, 60]) * sed
    else:
        if overlay == 1:
            rgb = colormap(np.clip(w.moist * 0.7 + w.water * 1.5, 0, 1),
                           [(0, (120, 80, 40)), (0.35, (200, 190, 120)), (0.6, (90, 170, 200)), (1, (20, 40, 140))])
        elif overlay == 2:
            rgb = colormap(np.clip(w.nutr / 1.2, 0, 1), [(0, (15, 15, 20)), (0.4, (90, 110, 40)), (1, (240, 240, 90))])
        elif overlay == 3:
            rgb = colormap(np.clip(w.microbes, 0, 1),
                           [(0, (10, 8, 20)), (0.3, (70, 30, 120)), (0.7, (190, 90, 220)), (1, (255, 200, 255))])
        elif overlay == 4:
            rgb = colormap(np.clip(w.fungus, 0, 1), [(0, (12, 12, 14)), (0.3, (80, 70, 60)), (1, (250, 240, 215))])
        elif overlay == 5:
            rgb = colormap(np.clip((w.temp + 10) / 40, 0, 1),
                           [(0, (40, 60, 200)), (0.25, (140, 190, 255)), (0.5, (240, 240, 240)),
                            (0.75, (250, 170, 70)), (1, (200, 30, 30))])
        else:
            rgb = colormap(np.clip(w.detritus, 0, 1), [(0, (12, 10, 8)), (0.4, (110, 70, 30)), (1, (240, 160, 70))])
        rgb *= (0.85 + 0.25 * w.height)[..., None]
        rgb = np.where(st.sea3, rgb * 0.25 + 10, rgb)
    return np.clip(rgb, 0, 255).astype(np.uint8)


def render_natural(w, st, frame, smooth=False):
    m = np.clip(w.moist, 0, 1)[..., None]
    col = lerp_rgb(SOIL_DRY, SOIL_WET, m)
    col = np.where(st.coast, SAND, col)
    col = lerp_rgb(col, ROCK, st.rock)
    col *= st.shade
    d = np.clip(w.detritus * 0.7, 0, 0.6)[..., None]
    col = lerp_rgb(col, DETRITUS_C, d)
    f = (np.clip(w.fungus, 0, 1) * 0.4)[..., None]
    col = lerp_rgb(col, MYCEL_C, f)

    t = w.pt
    has = w.pspec >= 0
    idx = np.where(has, w.pspec, w.n_plants)
    maxb = t["maxb"][idx]
    cover = np.clip(w.pbio / maxb * 1.3, 0, 1) * has
    pc = t["color"][idx] * (1.08 - 0.28 * cover)[..., None]
    a = (has * (0.35 + 0.65 * cover))[..., None]
    col = lerp_rgb(col, pc, a)
    fl = t["flower"][idx] & (w.pbio > 0.45 * maxb) & FLOWER_MASK & (w.season in ("Spring", "Summer"))
    if fl.any():
        col[fl] = t["fcolor"][idx][fl]

    # human landscape
    s = w.struct
    if s.any():
        fld = s == FIELD
        if fld.any():
            poor = np.clip(1 - w.nutr / 0.25, 0, 1)[..., None]
            fc = np.where(STRIPES, FIELD_A, FIELD_B)
            fc = lerp_rgb(fc, FIELD_POOR, poor)
            col = np.where(fld[..., None], fc * st.shade, col)
        col[s == RUIN] = RUIN_C
        col[s == HOUSE] = col[s == HOUSE] * 0.6

    wa = np.clip(w.water * 2.2, 0, 0.92)[..., None]
    wc = lerp_rgb(WATER_C, DEEP_C, np.clip(w.water - 0.3, 0, 1)[..., None])
    shimmer = 1 + 0.05 * np.sin(frame * 0.08 + _gx * 0.5 + _gy * 0.3)[..., None]
    col = lerp_rgb(col, wc * shimmer, wa)
    seacol = st.sea_col * shimmer + (w.plankton * 18)[..., None] * np.array([-0.4, 1.0, 0.2])
    sed = np.clip(w.sediment * 2.5, 0, 0.7)[..., None]
    seacol = seacol * (1 - sed) + np.array([140, 110, 70]) * sed
    col = np.where(st.sea3, seacol, col)
    sn = np.clip(w.snow * 4, 0, 0.95)[..., None]
    col = lerp_rgb(col, SNOW_C, sn)

    if w.sanctuary.any():
        sa = w.sanctuary
        col[sa] = col[sa] * 0.9 + np.array([0, 22, 18])
        edge = sa & ~(~dilate(~sa))
        col[edge] = FENCE_C

    if w.fire.max() > 0:
        fr = w.fire > 0
        flick = 0.7 + 0.3 * np.random.random(fr.sum())
        col[fr] = np.stack([255 * flick, 120 * flick * w.fire[fr], 30 * flick], axis=-1)

    col *= (1 - 0.28 * w.cover)[..., None]
    light = 0.36 + 0.64 * min(1.0, w.sun_raw * 1.6)
    if smooth:
        light = 0.9                   # at high speed, don't strobe day and night
    tint = np.array([1.0, 1.0, 1.0]) * light + np.array([0.0, 0.03, 0.12]) * (1 - light)
    col *= tint
    if light < 0.75 and w.fungus.max() > 0.5:
        glow = (np.clip(w.fungus - 0.5, 0, 0.5) * MUSH_MASK)[..., None] * (1 - light) * 2
        col += glow * np.array([60, 220, 200], np.float32)
    if 0.02 < w.sun_raw < 0.35 and not smooth:
        col *= np.array([1.08, 0.97, 0.88])
    return col


# ----------------------------------------------------------------------------
# species creator
# ----------------------------------------------------------------------------
class Creator:
    W, H = 560, 520

    def __init__(self, app):
        self.app = app
        self.rect = pygame.Rect((LW - self.W) // 2, (LH - self.H) // 2, self.W, self.H)
        self.kind = "animal"
        self.name = random_name("animal")
        self.name_active = False
        self.diet = {"plant"}
        self.flier = False
        self.swimmer = False
        self.flowering = True
        self.aquatic = False
        self.native = False
        self.activity = "day"
        self.hue = Slider("hue", "Colour", 0, 1, random.random(), "")
        self.a_sliders = [
            Slider("size", "Body size", 0.2, 2.5, 0.9, "{:.2f}"),
            Slider("speed", "Speed", 0.05, 0.5, 0.2, "{:.2f}"),
            Slider("litter", "Young per year (per female)", 1, 30, 4, "{:.0f}", integer=True),
            Slider("topt", "Preferred temperature", -5, 30, 13, "{:.0f} C"),
            Slider("life", "Lifespan (years)", 1, 60, 8, "{:.0f}", integer=True),
        ]
        self.p_sliders = [
            Slider("growth", "Growth rate", 0.005, 0.05, 0.022, "{:.3f}"),
            Slider("water", "Water need", 0.03, 0.7, 0.28, "{:.2f}"),
            Slider("light", "Light need", 0.05, 0.9, 0.4, "{:.2f}"),
            Slider("topt", "Preferred temperature", -5, 30, 13, "{:.0f} C"),
            Slider("spread", "Seed spread", 0.0005, 0.007, 0.0025, "{:.4f}"),
            Slider("maxb", "Mature size", 0.3, 2.5, 0.8, "{:.2f}"),
            Slider("edible", "Tastiness", 0.0, 1.0, 0.6, "{:.2f}"),
            Slider("flamm", "Flammability", 0.0, 1.0, 0.5, "{:.2f}"),
        ]
        self.buttons = []

    def sliders(self):
        return [self.hue] + (self.a_sliders if self.kind == "animal" else self.p_sliders)

    def val(self, key):
        for s in self.sliders():
            if s.key == key:
                return s.value

    def set_kind(self, k):
        self.kind = k
        self.name = random_name(k)

    def toggle_diet(self, d):
        if d in self.diet:
            if len(self.diet) > 1:
                self.diet.discard(d)
        else:
            self.diet.add(d)

    def create(self):
        name = self.name.strip() or random_name(self.kind)
        w = self.app.world
        if w.species_by_name(name):
            name += " II"
        color = hue_color(self.hue.value)
        D = DAY_TICKS
        if self.kind == "animal":
            spd = self.val("speed")
            size = self.val("size")
            metab = (0.00032 + 0.0011 * spd) * (1.25 if self.flier else 1.0)
            if "meat" in self.diet:
                metab *= 1.4
            sp = AnimalSpecies(name, color, sorted(self.diet), size, spd, int(self.val("litter")),
                               self.val("topt"), 16, self.val("life") * BIO_YEAR, metab, 6 + 28 * spd,
                               flier=self.flier, swimmer=self.swimmer, activity=self.activity,
                               breeds_in_water=self.swimmer, native=self.native,
                               trappable=not self.native and size < 1.5, bird=self.flier,
                               blurb="A species you designed.")
            life = self.val("life")
            sp.mature_frac = min(0.4, 1.0 / life)              # breeds from about age 1
            sp.breed_gap = BIO_YEAR                            # one breeding season a year
            sp.litter = self.val("litter") * 0.4 * 0.5         # 40% of young survive; half are female
            sp.young_ticks = 0.1 * BIO_YEAR
            w.add_animal_species(sp)
        else:
            fl = hue_color(self.hue.value + 0.45, 0.6, 0.95) if self.flowering else None
            sp = PlantSpecies(name, hue_color(self.hue.value, 0.55, 0.62), self.val("growth"), self.val("water"),
                              self.val("light"), self.val("topt"), 12, self.val("spread"), self.val("maxb"),
                              self.val("edible"), self.val("flamm"), flower=fl, aquatic=self.aquatic,
                              native=self.native, tree=self.val("maxb") >= 1.4, blurb="A plant you designed.")
            w.add_plant_species(sp)
        self.app.select_species(sp)
        self.app.creator = None
        self.app.panel_tab = "life"
        self.app.toast("Click the map to release your %s" % name)

    def layout_buttons(self):
        r = self.rect
        b = []
        x0 = r.x + 24
        b.append((Button("Animal", lambda: self.set_kind("animal"), lambda: self.kind == "animal"),
                  (x0, r.y + 56, 110, 26)))
        b.append((Button("Plant", lambda: self.set_kind("plant"), lambda: self.kind == "plant"),
                  (x0 + 116, r.y + 56, 110, 26)))
        b.append((Button("Native", lambda: setattr(self, "native", True), lambda: self.native),
                  (r.right - 210, r.y + 56, 90, 26)))
        b.append((Button("Introduced", lambda: setattr(self, "native", False), lambda: not self.native),
                  (r.right - 114, r.y + 56, 90, 26)))
        b.append((Button("Random name", lambda: setattr(self, "name", random_name(self.kind))),
                  (r.right - 140, r.y + 96, 116, 26)))
        if self.kind == "animal":
            y = r.y + 196
            for i, (d, lab) in enumerate([("plant", "Plants"), ("meat", "Meat"), ("fungus", "Fungi"),
                                          ("nectar", "Nectar"), ("detritus", "Detritus")]):
                b.append((Button(lab, lambda d=d: self.toggle_diet(d), lambda d=d: d in self.diet),
                          (x0 + 60 + i * 92, y, 86, 24)))
            y = r.y + 230
            b.append((Button("Flies", lambda: setattr(self, "flier", not self.flier), lambda: self.flier),
                      (x0 + 60, y, 86, 24)))
            b.append((Button("Swims", lambda: setattr(self, "swimmer", not self.swimmer), lambda: self.swimmer),
                      (x0 + 152, y, 86, 24)))
            for i, act in enumerate(["day", "night", "any"]):
                b.append((Button({"day": "Diurnal", "night": "Nocturnal", "any": "Always on"}[act],
                                 lambda act=act: setattr(self, "activity", act),
                                 lambda act=act: self.activity == act), (x0 + 260 + i * 84, y, 80, 24)))
        else:
            y = r.y + 196
            b.append((Button("Flowers", lambda: setattr(self, "flowering", not self.flowering),
                             lambda: self.flowering), (x0 + 60, y, 96, 24)))
            b.append((Button("Aquatic", lambda: setattr(self, "aquatic", not self.aquatic),
                             lambda: self.aquatic), (x0 + 162, y, 96, 24)))
        b.append((Button("Create & place", self.create), (r.right - 170, r.bottom - 46, 146, 30)))
        b.append((Button("Cancel", lambda: setattr(self.app, "creator", None)), (r.right - 270, r.bottom - 46, 92, 30)))
        self.buttons = b

    def draw(self, surf, fonts, mouse):
        self.layout_buttons()
        shade = pygame.Surface((LW, LH), pygame.SRCALPHA)
        shade.fill((0, 0, 0, 150))
        surf.blit(shade, (0, 0))
        r = self.rect
        pygame.draw.rect(surf, PANEL, r, border_radius=10)
        pygame.draw.rect(surf, LINE, r, 1, border_radius=10)
        draw_text(surf, fonts, "Design a new species", (r.x + 24, r.y + 18), TEXT, fonts.l)
        nb = pygame.Rect(r.x + 84, r.y + 96, r.w - 240, 26)
        draw_text(surf, fonts, "Name", (r.x + 24, r.y + 101), DIM)
        pygame.draw.rect(surf, INPUT, nb, border_radius=4)
        pygame.draw.rect(surf, ACCENT if self.name_active else LINE, nb, 1, border_radius=4)
        caret = "|" if self.name_active and (pygame.time.get_ticks() // 500) % 2 else ""
        draw_text(surf, fonts, self.name + caret, (nb.x + 8, nb.centery), TEXT, fonts.m, anchor="midleft")
        self.name_rect = nb
        self.hue.draw(surf, fonts, r.x + 24, r.y + 134, r.w - 110, hue_color(self.hue.value))
        sw = pygame.Rect(r.right - 70, r.y + 136, 46, 26)
        pygame.draw.rect(surf, hue_color(self.hue.value), sw, border_radius=6)
        if self.kind == "animal":
            draw_text(surf, fonts, "Eats", (r.x + 24, r.y + 200), DIM)
            draw_text(surf, fonts, "Traits", (r.x + 24, r.y + 234), DIM)
            sl, y0 = self.a_sliders, r.y + 270
        else:
            draw_text(surf, fonts, "Traits", (r.x + 24, r.y + 200), DIM)
            sl, y0 = self.p_sliders, r.y + 232
        colw = (r.w - 72) // 2
        for i, s in enumerate(sl):
            s.draw(surf, fonts, r.x + 24 + (i % 2) * (colw + 24), y0 + (i // 2) * 40, colw)
        for btn, rect in self.buttons:
            btn.draw(surf, fonts, rect, pygame.Rect(rect).collidepoint(mouse))
        hint = ("Introduced species have no natural enemies here - and native birds don't recognise them."
                if not self.native else "Native species evolved here alongside the others.")
        for i, ln in enumerate(wrap(hint, fonts.s, r.w - 300)):
            draw_text(surf, fonts, ln, (r.x + 24, r.bottom - 50 + i * 16), DIM)

    def handle(self, ev, pos):
        if ev.type == pygame.KEYDOWN:
            if ev.key == pygame.K_ESCAPE:
                self.app.creator = None
            elif self.name_active:
                if ev.key == pygame.K_BACKSPACE:
                    self.name = self.name[:-1]
                elif ev.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_TAB):
                    self.name_active = False
                elif ev.unicode and ev.unicode.isprintable() and len(self.name) < 22:
                    self.name += ev.unicode
            elif ev.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self.create()
            return
        for s in self.sliders():
            if s.handle(ev, pos):
                return
        if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            self.name_active = hasattr(self, "name_rect") and self.name_rect.collidepoint(pos)
            for btn, rect in self.buttons:
                if btn.handle(ev, pos):
                    return


# ----------------------------------------------------------------------------
# alert detail window
# ----------------------------------------------------------------------------
TOOL_NAMES = {"trap": "Trap", "sanctuary": "Fence", "water": "Water", "cloud": "Rain cloud", "fertilize": "Compost",
              "smite": "Smite", "dry": "Dry", "fire": "Fire"}
SLIDER_NAMES = {"rain": "Rainfall", "evap": "Evaporation", "temp": "Temperature", "biosecurity": "Biosecurity"}


class AlertView:
    W = 700

    def __init__(self, app, alert):
        self.app, self.a = app, alert
        alert["read"] = True
        self.buttons = []
        self.layout()

    def layout(self):
        f = self.app.fonts
        a = self.a
        tw = self.W - 56
        self.blocks = []
        y = 0
        self.blocks.append(("what", wrap(a["what"], f.m, tw)))
        if a["why"]:
            self.blocks.append(("why", wrap(a["why"], f.s, tw)))
        hl = []
        for text, action in a["help"]:
            hl.append((wrap(text, f.s, tw - 150), action))
        self.helps = hl
        self.fact = wrap(a["fact"], f.s, tw - 24) if a["fact"] else []
        h = 80
        for kind, lines in self.blocks:
            h += 24 + len(lines) * (19 if kind == "what" else 17) + 8
        if hl:
            h += 26 + sum(max(28, len(l) * 17 + 8) for l, _ in hl)
        if self.fact:
            h += 34 + len(self.fact) * 17
        h += 56
        self.H = min(LH - 20, h)
        self.rect = pygame.Rect((LW - self.W) // 2, (LH - self.H) // 2, self.W, self.H)

    def do(self, action):
        app = self.app
        kind = action[0]
        if kind == "tool":
            app.set_tool(action[1])
            app.toast("%s tool selected - use it on the map." % TOOL_NAMES.get(action[1], action[1]))
        elif kind == "species":
            sp = app.world.species_by_name(action[1])
            if sp:
                app.select_species(sp)
                app.panel_tab = "life"
                app.toast("%s selected - click the map to add it." % sp.name)
        elif kind == "slider":
            s = app.slider(action[1])
            if s:
                s.value = action[2]
                app.toast("%s set to %s." % (s.label, s.fmt.format(s.value)))
        app.alert_view = None

    def draw(self, surf, fonts, mouse):
        shade = pygame.Surface((LW, LH), pygame.SRCALPHA)
        shade.fill((0, 0, 0, 160))
        surf.blit(shade, (0, 0))
        r = self.rect
        a = self.a
        col = SEV_COLORS[a["sev"]]
        pygame.draw.rect(surf, PANEL, r, border_radius=10)
        pygame.draw.rect(surf, col, r, 2, border_radius=10)
        pygame.draw.rect(surf, col, (r.x, r.y, 8, r.h), border_top_left_radius=10, border_bottom_left_radius=10)
        x = r.x + 28
        y = r.y + 16
        label = {"good": "GOOD NEWS", "info": "INFO", "warn": "WARNING", "crit": "CRITICAL"}[a["sev"]]
        draw_text(surf, fonts, "%s  -  %s" % (label, a.get("date", "Day %d" % a["day"])), (x, y), col, fonts.b)
        y += 20
        draw_text(surf, fonts, a["title"], (x, y), TEXT, fonts.l, maxw=r.w - 180)
        self.buttons = []
        if a.get("pos"):
            b = Button("Show on map", self.show)
            b.draw(surf, fonts, (r.right - 140, r.y + 18, 116, 26), b.rect.collidepoint(mouse))
            self.buttons.append(b)
        y += 40
        heads = {"what": "What's happening", "why": "Why"}
        for kind, lines in self.blocks:
            draw_text(surf, fonts, heads[kind], (x, y), ACCENT, fonts.b)
            y += 22
            for ln in lines:
                draw_text(surf, fonts, ln, (x, y), TEXT, fonts.m if kind == "what" else fonts.s)
                y += 19 if kind == "what" else 17
            y += 8
        if self.helps:
            draw_text(surf, fonts, "How you can help", (x, y), ACCENT, fonts.b)
            y += 24
            for lines, action in self.helps:
                rowh = max(28, len(lines) * 17 + 8)
                pygame.draw.circle(surf, col, (x + 4, y + 9), 3)
                for i, ln in enumerate(lines):
                    draw_text(surf, fonts, ln, (x + 16, y + i * 17), TEXT)
                if action:
                    if action[0] == "tool":
                        lab = "Use %s" % TOOL_NAMES.get(action[1], action[1])
                    elif action[0] == "species":
                        lab = "Select %s" % action[1]
                    else:
                        lab = "Set %s" % SLIDER_NAMES.get(action[1], action[1])
                    b = Button(lab, lambda act=action: self.do(act))
                    b.draw(surf, fonts, (r.right - 160, y - 3, 132, 24), b.rect.collidepoint(mouse), fonts.s)
                    self.buttons.append(b)
                y += rowh
        if self.fact:
            box = pygame.Rect(x - 6, y + 4, r.w - 44, len(self.fact) * 17 + 30)
            pygame.draw.rect(surf, FACT, box, border_radius=6)
            draw_text(surf, fonts, "In the real Aotearoa", (x + 6, y + 10), (140, 210, 200), fonts.b)
            for i, ln in enumerate(self.fact):
                draw_text(surf, fonts, ln, (x + 6, y + 28 + i * 17), (200, 220, 215))
            y += box.h + 8
        b = Button("Close", lambda: setattr(self.app, "alert_view", None))
        b.draw(surf, fonts, (r.right - 110, r.bottom - 40, 86, 28), b.rect.collidepoint(mouse))
        self.buttons.append(b)

    def show(self):
        p = self.a["pos"]
        self.app.highlight = (p[0], p[1], FPS * 5)
        if self.app.zoom > 1.01:
            self.app.center_on(p[0], p[1])
        self.app.alert_view = None

    def handle(self, ev, pos):
        if ev.type == pygame.KEYDOWN and ev.key in (pygame.K_ESCAPE, pygame.K_RETURN):
            self.app.alert_view = None
            return
        if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            for b in self.buttons:
                if b.handle(ev, pos):
                    return
            if not self.rect.collidepoint(pos):
                self.app.alert_view = None


# ----------------------------------------------------------------------------
# the app
# ----------------------------------------------------------------------------
TOOLS = [
    ("inspect", "Inspect", "Hover to read a cell, creature or settlement"),
    ("microscope", "Scope", "Microscope: see bacteria and fungal threads"),
    ("water", "Water", "Pour water"),
    ("dry", "Dry", "Evaporate water and dry soil"),
    ("cloud", "Rain", "Summon a rain cloud"),
    ("fertilize", "Compost", "Add nutrients and organic matter"),
    ("fire", "Fire", "Start a fire"),
    ("trap", "Trap", "Set pest traps: catch rats, stoats, cats, possums, rabbits"),
    ("sanctuary", "Fence", "Draw a predator-proof sanctuary (click inside one to erase)"),
    ("smite", "Smite", "Clear everything under the brush"),
]

PHYSICS = [
    ("time", "Time speed", 0, 8, "{:.1f}x", "How fast time passes"),
    ("sun", "Sunlight", 0, 2, "{:.2f}", "Strength of the sun: light and warmth"),
    ("temp", "Temperature shift", -15, 15, "{:+.0f} C", "Shift the whole climate"),
    ("rain", "Rainfall", 0, 3, "{:.2f}", "Moisture blowing in off the sea"),
    ("wind", "Wind", 0, 3, "{:.2f}", "Moves clouds, seeds and fire"),
    ("gravity", "Gravity", 0, 3, "{:.2f}", "Water flow speed and cost of movement"),
    ("evap", "Evaporation", 0, 3, "{:.2f}", "How quickly water returns to the air"),
    ("mutation", "Mutation rate", 0, 4, "{:.2f}", "How much offspring differ from parents"),
    ("decay", "Decay rate", 0, 3, "{:.2f}", "Speed of decomposition by microbes & fungi"),
    ("migration", "Native recolonisation", 0, 1, "{:.2f}", "Chance lost natives return from refuges"),
    ("biosecurity", "Biosecurity", 0, 1, "{:.2f}", "Higher = settlers bring fewer pests"),
]

HELP = [
    ("NZ EcoSim", None),
    ("An island before people. Keep it alive - or don't.", None),
    ("", None),
    ("Add life", "pick a species on the right, then click the map (Shift = a group)"),
    ("Humans", "land settlers on the map; the People button (C) shows every clan"),
    ("Click", "with Inspect, click a person, animal or house to see what it's doing and why"),
    ("Zoom / pan", "mouse wheel to zoom, drag the map or WASD to pan, Z to reset"),
    ("L / F / R", "lessons with goals  /  live food web  /  export a class report (Learn tab)"),
    ("Alerts", "click any alert to learn what's happening, why, and how to help"),
    ("Space / H", "pause  /  this help"),
    ("1-8", "views: normal, moisture, nutrients, microbes, fungi, temperature, detritus, ocean"),
    ("M / I / P", "microscope  /  inspect  /  population make-up"),
    ("N / Y", "new island (North/South, geography)  /  ecological history"),
    ("Vitality bar", "click it to open the ecosystem-health charts; Settings changes colours & layout"),
    ("[ ] / Ctrl+wheel", "brush size        + / -  time speed"),
    ("F5 / F9 / F12", "save / load / screenshot"),
    ("", None),
    ("Life runs 20x faster than the calendar (real lifespans and breeding rates, same pace for all).", None),
    ("The island is saved when you close it and keeps living for a while when you're away.", None),
]

GROUPS = [
    ("NATIVE ANIMALS", lambda w: [s for s in w.animal_species if s.native]),
    ("INTRODUCED ANIMALS", lambda w: [s for s in w.animal_species if not s.native]),
    ("PEOPLE", lambda w: [w.human_entry]),
    ("NATIVE PLANTS", lambda w: [s for s in w.plant_species if s.native]),
    ("INTRODUCED PLANTS", lambda w: [s for s in w.plant_species if not s.native]),
    ("SOIL LIFE", lambda w: [w.fungus_entry, w.microbe_entry]),
]


class App:
    def __init__(self):
        if sys.platform == "win32":
            try:
                import ctypes
                ctypes.windll.shcore.SetProcessDpiAwareness(1)
            except Exception:
                pass
        pygame.init()
        pygame.display.set_caption("NZ EcoSim")
        info = pygame.display.Info()
        sc = min(1.6, (info.current_w * 0.92) / LW, (info.current_h * 0.86) / LH) if info.current_w > 0 else 1.0
        if WEB:
            sc = 1.0                                   # the web page scales the canvas itself
        self.fit_scale = sc
        self.display_ready = False
        self.window = pygame.display.set_mode((int(LW * sc), int(LH * sc)), 0 if WEB else pygame.RESIZABLE)
        self.screen = pygame.Surface((LW, LH))
        self.display = pygame.Surface((LW, LH))
        self.ui = {"theme": "Dark", "accent": None, "panel": "right", "bar": "bottom", "window": "fit",
                   "daynight": "shade"}
        try:
            with open(SETTINGS_FILE) as fh:
                self.ui.update(json.load(fh))
        except Exception:
            pass
        self.applied_window = "fit"
        self.post = []
        self.mouse_disp = (0, 0)
        self.drawer = False
        self.drawer_rect = pygame.Rect(0, 0, 0, 0)
        self.settings_view = None
        self.history_view = None
        self.collapse_view = None
        self.foodweb_view = None
        self.base_dir = app_dir()
        self.report_view = None
        self.lesson_picker = None
        self.lesson_result = None
        self.fonts = Fonts()
        self.clock = pygame.time.Clock()
        self.frame = 0
        self.overlay = 0
        self.tool = "inspect"
        self.selected = None
        self.brush = 3
        self.paused = False
        self.painting = False
        self.sanct_mode = True
        self.show_help = False
        self.creator = None
        self.alert_view = None
        self.makeup_view = False
        self.newworld = None
        self.clans = None
        self.away = None
        self.panel_tab = "life"
        self.bottom_tab = "alerts"
        self.graph_tab = "trends"
        self.list_scroll = 0
        self.log_scroll = 0
        self.toast_msg, self.toast_t = "", 0
        self.banner = None
        self.highlight = None
        self.new_world_armed = 0
        self.tick_acc = 0.0
        self.sim_ms = 0.0
        self.last_autosave = time.time()
        self.mouse = (0, 0)
        self.icon()

        self.world = None
        self.imported = False
        imp = webplatform.imported_world_file()
        if imp:
            try:
                with open(imp, "rb") as fh:
                    data = webplatform.load_blob(fh.read())
                self.set_world(data["world"])
                self.imported = True
            except Exception as e:
                print("Could not import world:", e)
                self.world = None
        if self.world is None and webplatform.query("new") is None and (
                os.path.exists(SAVE_FILE) or webplatform.store_get() is not None):
            try:
                self.load(catch_up=not WEB and not os.environ.get("NZ_ECOSIM_NO_CATCHUP"))
            except Exception as e:
                print("Could not load save:", e)
                self.world = None
        self.first_launch = False
        if self.world is None:
            self.world = World()
            self.first_launch = True
        self.static = Static(self.world)
        self.sliders = [Slider(k, lab, lo, hi, self.world.settings.get(k, DEFAULT_SETTINGS[k]), fmt, tip=tip)
                        for k, lab, lo, hi, fmt, tip in PHYSICS]
        self.tool_buttons = [Button(lab, lambda k=k: self.set_tool(k), lambda k=k: self.tool == k, tip=tip)
                             for k, lab, tip in TOOLS]
        self.overlay_buttons = [Button(n, lambda i=i: setattr(self, "overlay", i),
                                       lambda i=i: self.overlay == i) for i, n in enumerate(OVERLAYS)]
        self.tab_buttons = [Button("Add life", lambda: setattr(self, "panel_tab", "life"),
                                   lambda: self.panel_tab == "life"),
                            Button("Physics", lambda: setattr(self, "panel_tab", "physics"),
                                   lambda: self.panel_tab == "physics"),
                            Button("Learn", lambda: setattr(self, "panel_tab", "learn"),
                                   lambda: self.panel_tab == "learn")]
        self.bottom_buttons = [Button("Alerts", lambda: setattr(self, "bottom_tab", "alerts"),
                                      lambda: self.bottom_tab == "alerts"),
                               Button("Chronicle", lambda: setattr(self, "bottom_tab", "log"),
                                      lambda: self.bottom_tab == "log")]
        self.graph_buttons = [Button("Trends", lambda: setattr(self, "graph_tab", "trends"),
                                     lambda: self.graph_tab == "trends"),
                              Button("Pies", lambda: setattr(self, "graph_tab", "makeup"),
                                     lambda: self.graph_tab == "makeup"),
                              Button("Expand", lambda: setattr(self, "makeup_view", True))]
        self.misc = [Button("+ Design a species", self.open_creator),
                     Button("Pause", lambda: setattr(self, "paused", not self.paused), lambda: self.paused),
                     Button("?", lambda: setattr(self, "show_help", True)),
                     Button("People", lambda: self.open_clans(), tip="People & clans panel (C)"),
                     Button("New", lambda: setattr(self, "newworld", views.NewWorldView(self)),
                            tip="Generate a new island (N)"),
                     Button("History", lambda: setattr(self, "history_view", views.HistoryView(self)),
                            tip="Ecological history: the major events so far (Y)"),
                     Button("Settings", lambda: setattr(self, "settings_view", views.SettingsView(self)),
                            tip="Colours, layout, window size and day/night display")]
        self.lens_mask = pygame.Surface((190, 190), pygame.SRCALPHA)
        pygame.draw.circle(self.lens_mask, (255, 255, 255, 255), (95, 95), 95)
        self.clickables = []          # (rect, callback) rebuilt every frame
        self.apply_ui()
        self.zoom = 1.0
        self.cam_x, self.cam_y = GW / 2, GH / 2
        self.sel = None
        self.follow = False
        self.card_rect = pygame.Rect(0, 0, 0, 0)
        self.clans = None
        self.drag_pan = None
        self.left_press = None
        self.left_dragged = False
        self.small_map = None
        if self.first_launch:
            self.show_help = False
            self.newworld = views.NewWorldView(self, first=True)
        if self.imported:
            self.toast("This is your own copy of the live island - experiment freely, the live one won't change.")

    def icon(self):
        ic = pygame.Surface((32, 32), pygame.SRCALPHA)
        pygame.draw.circle(ic, (40, 100, 160), (16, 16), 15)
        pygame.draw.ellipse(ic, (60, 140, 70), (6, 8, 20, 18))
        pygame.draw.circle(ic, (240, 240, 245), (17, 13), 3)
        pygame.display.set_icon(ic)

    # --------------------------------------------------------------- helpers
    def toast(self, msg):
        self.toast_msg, self.toast_t = msg, FPS * 4

    def set_tool(self, k):
        if scenarios.tool_blocked(self.world, k):
            self.toast("%s is switched off in this lesson - real conservation can't make animals vanish."
                       % dict((a, b) for a, b, _ in TOOLS).get(k, k))
            return
        self.tool = k
        self.selected = None

    def select_species(self, sp):
        self.selected = sp
        self.tool = "species"

    def sync_settings(self):
        for s in self.sliders:
            self.world.settings[s.key] = s.value

    def slider(self, key):
        for s in self.sliders:
            if s.key == key:
                return s

    # ----------------------------------------------------------- ui settings
    def apply_ui(self):
        apply_theme(self.ui.get("theme", "Dark"), self.ui.get("accent"))
        want = self.ui.get("window", "fit")
        if want != self.applied_window and not WEB:
            self.applied_window = want
            if want == "fullscreen":
                self.window = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
            elif want == "original":
                self.window = pygame.display.set_mode((LW, LH), pygame.RESIZABLE)
            else:
                self.window = pygame.display.set_mode((int(LW * self.fit_scale), int(LH * self.fit_scale)),
                                                      pygame.RESIZABLE)
        try:
            with open(SETTINGS_FILE, "w") as fh:
                json.dump(self.ui, fh)
        except Exception:
            pass

    def offsets(self):
        left = self.ui.get("panel") == "left"
        top = self.ui.get("bar") == "top"
        return (PANEL_W if left else 0, BOTTOM_H if top else 0, 0 if top else VIEW_H, 0 if left else VIEW_W)

    def canon_to_disp(self, p):
        mx, my, by, px = self.offsets()
        x, y = p
        if x >= VIEW_W:
            return x - VIEW_W + px, y
        if y >= VIEW_H:
            return x + mx, y - VIEW_H + by
        return x + mx, y + my

    def disp_to_canon(self, p):
        mx, my, by, px = self.offsets()
        x, y = p
        if px <= x < px + PANEL_W:
            return x - px + VIEW_W, y
        x -= mx
        if by <= y < by + BOTTOM_H:
            return x, y - by + VIEW_H
        return x, y - my

    def compose(self):
        mx, my, by, px = self.offsets()
        d = self.display
        if (mx, my, px) == (0, 0, VIEW_W):
            d.blit(self.screen, (0, 0))
            return
        d.blit(self.screen, (mx, my), (0, 0, VIEW_W, VIEW_H))
        d.blit(self.screen, (mx, by), (0, VIEW_H, VIEW_W, BOTTOM_H))
        d.blit(self.screen, (px, 0), (VIEW_W, 0, PANEL_W, LH))

    def to_logical(self, pos):
        ww, wh = self.window.get_size()
        sc = min(ww / LW, wh / LH)
        ox, oy = (ww - LW * sc) / 2, (wh - LH * sc) / 2
        return int((pos[0] - ox) / sc), int((pos[1] - oy) / sc)

    def in_view(self, pos):
        return 0 <= pos[0] < VIEW_W and 0 <= pos[1] < VIEW_H

    def set_world(self, w):
        self.world = w
        self.static = Static(w)
        self.sel = None
        self.follow = False
        self.zoom = 1.0
        self.cam_x, self.cam_y = GW / 2, GH / 2
        self.selected = None
        self.tool = "inspect"
        self.painting = False
        self.alert_view = None
        if hasattr(self, "sliders"):
            for s in self.sliders:
                s.value = w.settings.get(s.key, DEFAULT_SETTINGS[s.key])

    # ------------------------------------------------------------ save/load
    def save(self, quiet=False):
        if WEB:
            try:
                webplatform.store_set(webplatform.dump_world(self.world, SAVE_VERSION))
                if not quiet:
                    self.toast("World saved in this browser.")
            except Exception as e:
                if not quiet:
                    self.toast("Could not save in this browser: %s" % e)
            return
        try:
            tmp = SAVE_FILE + ".tmp"
            with open(tmp, "wb") as f:
                pickle.dump({"version": SAVE_VERSION, "saved_at": time.time(), "world": self.world}, f,
                            protocol=pickle.HIGHEST_PROTOCOL)
            os.replace(tmp, SAVE_FILE)
            if not quiet:
                self.toast("World saved.")
        except Exception as e:
            self.toast("Save failed: %s" % e)

    def load(self, catch_up=False):
        if WEB:
            blob = webplatform.store_get()
            if blob is None:
                raise ValueError("nothing saved in this browser yet")
            data = webplatform.load_blob(blob)
        else:
            with open(SAVE_FILE, "rb") as f:
                data = webplatform.load_blob(f.read())      # plain or compressed saves
        if data.get("version") != SAVE_VERSION:
            raise ValueError("save from an older version of NZ EcoSim")
        self.set_world(data["world"])
        if catch_up:
            hours = max(0.0, (time.time() - data.get("saved_at", time.time())) / 3600)
            ticks = int(min(hours * DAY_TICKS, 4 * DAY_TICKS))
            if ticks > 60:
                self.catch_up(ticks, hours)

    def catch_up(self, ticks, hours):
        w = self.world
        n_alerts = len(w.alerts)
        before = {sp.name: w.counts.get(sp, 0) for sp in w.animal_species}
        people0 = len(w.people)
        vit0 = w.vitality
        t0 = time.time()
        done = 0
        while done < ticks:
            for _ in range(30):
                if done >= ticks:
                    break
                w.step()
                done += 1
            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()
                if ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE:
                    ticks = done
            if time.time() - t0 > 0.05:
                t0 = time.time()
                self.draw_progress(done / max(1, ticks))
        w.new_alerts = []
        after = {sp.name: w.counts.get(sp, 0) for sp in w.animal_species}
        lines = []
        if hours >= 24:
            lines.append("You were away for %.1f days." % (hours / 24))
        elif hours >= 1:
            lines.append("You were away for %.1f hours." % hours)
        else:
            lines.append("You were away for %d minutes." % max(1, hours * 60))
        lines.append("%s passed on the island (now %s)." % (age_text(done), w.date))
        changes = []
        for name in after:
            b, a = before.get(name, 0), after[name]
            if b != a and (b or a):
                changes.append("%s %d->%d" % (name, b, a))
        if len(w.people) != people0:
            changes.append("People %d->%d" % (people0, len(w.people)))
        for i in range(0, len(changes), 4):
            lines.append(",  ".join(changes[i:i + 4]))
        self.away = {"lines": lines, "alerts": w.alerts[n_alerts:][-6:], "vit": (vit0, w.vitality)}

    def draw_progress(self, frac):
        s = self.screen
        s.fill(BG)
        draw_text(s, self.fonts, "While you were away...", (LW // 2, LH // 2 - 40), TEXT, self.fonts.xl, "center")
        r = pygame.Rect(LW // 2 - 200, LH // 2 + 4, 400, 10)
        pygame.draw.rect(s, LINE, r, border_radius=5)
        r2 = r.copy()
        r2.w = int(r.w * frac)
        pygame.draw.rect(s, ACCENT, r2, border_radius=5)
        draw_text(s, self.fonts, "%s  -  %s   (Esc to skip)" % (self.world.date, self.world.season),
                  (LW // 2, LH // 2 + 34), DIM, self.fonts.m, "center")
        self.present()

    # ------------------------------------------------------------ main loop
    def run(self):
        running = True
        while running:
            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:
                    running = False
                elif ev.type == pygame.VIDEORESIZE:
                    self.window = pygame.display.set_mode((max(640, ev.w), max(400, ev.h)), pygame.RESIZABLE)
                else:
                    self.handle(ev)
            self.update()
            self.draw()
            self.present()
            self.clock.tick(FPS)
            self.frame += 1
        self.sync_settings()
        self.save(quiet=True)
        pygame.quit()

    async def run_async(self):
        """Browser main loop: identical to run(), but hands control back to the page every frame."""
        import asyncio
        while True:
            t0 = time.perf_counter()
            for ev in pygame.event.get():
                if ev.type != pygame.QUIT:
                    self.handle(ev)
            self.update()
            self.draw()
            self.present()
            self.frame += 1
            await asyncio.sleep(max(0.0, 1 / FPS - (time.perf_counter() - t0)))

    def present(self):
        ww, wh = self.window.get_size()
        src = self.display if self.display_ready else self.screen
        if (ww, wh) == (LW, LH):
            self.window.blit(src, (0, 0))
        else:
            sc = min(ww / LW, wh / LH)
            size = (max(1, int(LW * sc)), max(1, int(LH * sc)))
            self.window.fill((0, 0, 0))
            self.window.blit(pygame.transform.smoothscale(src, size),
                             ((ww - size[0]) // 2, (wh - size[1]) // 2))
        pygame.display.flip()

    def modal_open(self):
        return (self.creator or self.alert_view or self.away or self.makeup_view or self.show_help or
                self.clans or self.newworld or self.settings_view or self.history_view or self.collapse_view or
                self.foodweb_view or self.report_view or self.lesson_picker or self.lesson_result)

    def update(self):
        self.sync_settings()
        w = self.world
        if self.world.collapsed and not getattr(self.world, "collapse_shown", False):
            self.world.collapse_shown = True
            self.collapse_view = views.CollapseView(self)
        st = getattr(w, "scenario", None)
        if st:
            if st["status"] == "active" and w.tick - st.get("checked", 0) >= 30:
                st["checked"] = w.tick
                scenarios.check(w)
            if st["status"] != "active" and not st.get("shown"):
                st["shown"] = True
                self.lesson_result = lessons_ui.LessonResult(self)
        if not self.paused and not (self.creator or self.alert_view or self.away or self.makeup_view or
                                    self.clans or self.newworld or self.settings_view or self.history_view or
                                    self.collapse_view or self.report_view or self.lesson_picker or
                                    self.lesson_result):
            self.tick_acc += w.settings["time"]
            n = int(self.tick_acc)
            self.tick_acc -= n
            t0 = time.perf_counter()
            for _ in range(min(n, 12)):
                w.step()
                if (time.perf_counter() - t0) > 0.06:
                    break
            if n:
                self.sim_ms = self.sim_ms * 0.9 + (time.perf_counter() - t0) * 1000 * 0.1
        if w.new_alerts:
            serious = [a for a in w.new_alerts if a["sev"] in ("warn", "crit")]
            if serious:
                self.banner = (serious[-1], FPS * 7)
            w.new_alerts = []
        if self.banner:
            a, ttl = self.banner
            self.banner = (a, ttl - 1) if ttl > 1 else None
        if self.highlight:
            x, y, ttl = self.highlight
            self.highlight = (x, y, ttl - 1) if ttl > 1 else None
        if self.sel and self.follow and self.sel_alive() and self.sel["kind"] in ("person", "animal"):
            o = self.sel["obj"]
            self.cam_x += (o.x - self.cam_x) * 0.25
            self.cam_y += (o.y - self.cam_y) * 0.25
        keys = pygame.key.get_pressed()
        step = 1.2 / self.zoom * 3
        if not self.modal_open() and not (self.creator and self.creator.name_active):
            if keys[pygame.K_LEFT] or keys[pygame.K_a]:
                self.cam_x -= step
            if keys[pygame.K_RIGHT] or keys[pygame.K_d]:
                self.cam_x += step
            if keys[pygame.K_UP] or keys[pygame.K_w]:
                self.cam_y -= step
            if keys[pygame.K_DOWN] or keys[pygame.K_s]:
                self.cam_y += step
        if self.painting and self.in_view(self.mouse):
            self.apply_tool(continuous=True)
        if self.toast_t > 0:
            self.toast_t -= 1
        if time.time() - self.last_autosave > 120:
            self.last_autosave = time.time()
            self.save(quiet=True)

    def apply_tool(self, continuous=False, shift=False):
        w = self.world
        cx, cy = self.s2w(*self.mouse)
        t = self.tool
        if t in ("inspect", "microscope"):
            return
        if t == "cloud":
            if not continuous:
                w.spawn_cloud(cx, cy)
                w.actions["Summoned rain"] += 1
            return
        if t == "species" and self.selected is not None:
            sp = self.selected
            ix, iy = int(min(max(cx, 0), GW - 1)), int(min(max(cy, 0), GH - 1))
            if sp.kind == "human":
                if continuous:
                    return
                if not w.land[ix, iy] or w.water[ix, iy] > 0.3:
                    self.toast("People need dry land to settle.")
                    return
                if w.sanctuary[ix, iy]:
                    self.toast("People won't settle inside a sanctuary.")
                    return
                humans.found_tribe(w, cx, cy, 10 if shift else 6)
                w.actions["Landed settlers"] += 1
                return
            if sp.kind == "animal":
                if continuous and self.frame % 6:
                    return
                if getattr(sp, "marine", False):
                    if not (w.sea[ix, iy] or w.coast[ix, iy]):
                        if not continuous:
                            self.toast("%s lives at sea - click on the ocean near the coast." % sp.name)
                        return
                elif not w.land[ix, iy] and not sp.flier:
                    if not continuous:
                        self.toast("%s can't live in the sea." % sp.name)
                    return
                if w.counts.get(sp, 0) >= POP_CAP:
                    self.toast("%s population is at its limit." % sp.name)
                    return
                n = w.spawn_at(sp, cx, cy, 5 if shift else 1)
                if n:
                    w.actions["Released %s (%s)" % (sp.name, sp.origin)] += n
                if not continuous and n:
                    w.log("You released %d %s." % (n, sp.name), sp.color, key="rel" + sp.name, cooldown_days=0.25)
                return
            w.paint("species", cx, cy, self.brush, sp)
            if not continuous:
                w.actions["Planted / added %s" % sp.name] += 1
            return
        if t == "fire" and continuous and self.frame % 4:
            return
        if t == "trap" and continuous and self.frame % 3:
            return
        w.paint(t, cx, cy, self.brush, mode=self.sanct_mode)
        if not continuous:
            label = {"trap": "Set pest traps", "sanctuary": "Drew a fenced sanctuary" if self.sanct_mode else
                     "Removed part of a sanctuary", "water": "Poured water", "dry": "Dried land", "fire": "Started a fire",
                     "fertilize": "Added compost", "smite": "Used Smite (cleared everything)"}.get(t)
            if label:
                w.actions[label] += 1

    # ------------------------------------------------------------- events
    def handle(self, ev):
        modal = self.modal_open()
        if hasattr(ev, "pos"):
            dpos = self.to_logical(ev.pos)
            pos = dpos if modal else self.disp_to_canon(dpos)
            if ev.type == pygame.MOUSEMOTION:
                self.mouse_disp = dpos
                self.mouse = pos
        else:
            pos = self.mouse
        if self.report_view:
            self.report_view.handle(ev, pos)
            return
        if self.lesson_result:
            self.lesson_result.handle(ev, pos)
            return
        if self.lesson_picker:
            self.lesson_picker.handle(ev, pos)
            return
        if self.foodweb_view:
            self.foodweb_view.handle(ev, pos)
            return
        if self.collapse_view:
            self.collapse_view.handle(ev, pos)
            return
        if self.settings_view:
            self.settings_view.handle(ev, pos)
            return
        if self.history_view:
            self.history_view.handle(ev, pos)
            return
        if self.drawer and hasattr(ev, "pos") and ev.type == pygame.MOUSEBUTTONDOWN and \
                self.drawer_rect.collidepoint(self.to_logical(ev.pos)):
            return
        if self.away:
            if ev.type == pygame.MOUSEBUTTONDOWN:
                for r, cb in self.clickables:
                    if r.collidepoint(pos):
                        self.away = None
                        cb()
                        return
                self.away = None
            elif ev.type == pygame.KEYDOWN:
                self.away = None
            return
        if self.creator:
            self.creator.handle(ev, pos)
            return
        if self.alert_view:
            self.alert_view.handle(ev, pos)
            return
        if self.newworld:
            self.newworld.handle(ev, pos)
            return
        if self.clans:
            self.clans.handle(ev, pos)
            return
        if self.makeup_view:
            if ev.type in (pygame.MOUSEBUTTONDOWN, pygame.KEYDOWN):
                self.makeup_view = False
            return
        if self.show_help and ev.type in (pygame.MOUSEBUTTONDOWN, pygame.KEYDOWN):
            self.show_help = False
            return

        if ev.type == pygame.KEYDOWN:
            k = ev.key
            mods = pygame.key.get_mods()
            if k == pygame.K_SPACE:
                self.paused = not self.paused
            elif k == pygame.K_h:
                self.show_help = True
            elif pygame.K_1 <= k <= pygame.K_8:
                self.overlay = k - pygame.K_1
            elif k == pygame.K_c:
                self.open_clans()
            elif k == pygame.K_y:
                self.history_view = views.HistoryView(self)
            elif k == pygame.K_f:
                self.foodweb_view = foodweb.FoodWebView(self)
            elif k == pygame.K_r:
                self.report_view = report.ReportView(self)
            elif k == pygame.K_l:
                self.lesson_picker = lessons_ui.LessonPicker(self)
            elif k == pygame.K_n and not (mods & pygame.KMOD_CTRL):
                self.newworld = views.NewWorldView(self)
            elif k == pygame.K_0:
                self.overlay = 0
            elif k == pygame.K_m:
                self.set_tool("microscope")
            elif k == pygame.K_p:
                self.makeup_view = True
            elif k == pygame.K_ESCAPE:
                if self.sel:
                    self.clear_sel()
                else:
                    self.set_tool("inspect")
            elif k == pygame.K_i:
                self.set_tool("inspect")
            elif k == pygame.K_z:
                self.zoom = 1.0
                self.clamp_cam()
            elif k in (pygame.K_PLUS, pygame.K_EQUALS, pygame.K_KP_PLUS):
                self.slider("time").value = min(8, self.slider("time").value + 0.5)
            elif k in (pygame.K_MINUS, pygame.K_KP_MINUS):
                self.slider("time").value = max(0, self.slider("time").value - 0.5)
            elif k == pygame.K_F5:
                self.sync_settings()
                self.save()
            elif k == pygame.K_F9:
                if os.path.exists(SAVE_FILE) or WEB:
                    try:
                        self.load()
                        self.toast("World loaded.")
                    except Exception as e:
                        self.toast("Could not load: %s" % e)
            elif k == pygame.K_F12:
                self.screenshot()
            elif k == pygame.K_n and (mods & pygame.KMOD_CTRL):
                self.newworld = views.NewWorldView(self)
            elif k == pygame.K_LEFTBRACKET:
                self.brush = max(1, self.brush - 1)
            elif k == pygame.K_RIGHTBRACKET:
                self.brush = min(10, self.brush + 1)
            return

        if ev.type == pygame.MOUSEWHEEL:
            if self.in_view(self.mouse):
                if pygame.key.get_mods() & pygame.KMOD_CTRL:
                    self.brush = int(min(10, max(1, self.brush + ev.y)))
                else:
                    self.follow = False if not self.sel else self.follow
                    self.zoom_at(1.25 ** ev.y, *self.mouse)
            elif self.mouse[0] >= VIEW_W:
                self.list_scroll = max(0, self.list_scroll - ev.y)
            elif self.mouse[1] >= VIEW_H and self.mouse[0] > 630:
                self.log_scroll = max(0, self.log_scroll - ev.y)
            return

        if self.panel_tab == "physics":
            for s in self.sliders:
                r = s.handle(ev, pos)
                if r == "reset":
                    s.value = DEFAULT_SETTINGS[s.key]
                    return
                if r:
                    return
        # panning with the right or middle mouse button
        if ev.type == pygame.MOUSEBUTTONDOWN and ev.button in (2, 3) and self.in_view(pos):
            self.drag_pan = (pos, self.cam_x, self.cam_y)
            return
        if ev.type == pygame.MOUSEBUTTONUP and ev.button in (2, 3):
            self.drag_pan = None
            return
        if ev.type == pygame.MOUSEMOTION and getattr(self, "left_press", None):
            (sx, sy), cx, cy = self.left_press
            if self.left_dragged or abs(pos[0] - sx) + abs(pos[1] - sy) > 5:
                self.left_dragged = True
                self.cam_x = cx - (pos[0] - sx) / self.ppc
                self.cam_y = cy - (pos[1] - sy) / self.ppc
                self.follow = False
                self.clamp_cam()
            return
        if ev.type == pygame.MOUSEBUTTONUP and ev.button == 1 and getattr(self, "left_press", None):
            press = self.left_press
            self.left_press = None
            if not self.left_dragged and self.tool == "inspect":
                picked = self.pick(*press[0])
                self.sel = picked
                self.follow = bool(picked) and picked["kind"] in ("person", "animal") and self.zoom > 1.01
            return
        if ev.type == pygame.MOUSEMOTION and self.drag_pan:
            (sx, sy), cx, cy = self.drag_pan
            self.cam_x = cx - (pos[0] - sx) / self.ppc
            self.cam_y = cy - (pos[1] - sy) / self.ppc
            self.follow = False
            self.clamp_cam()
            return
        if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            for r, cb in self.clickables:
                if r.collidepoint(pos):
                    cb()
                    return
            if self.map_moved() and self.MINI.collidepoint(pos):
                self.cam_x = (pos[0] - self.MINI.x) / self.MINI.w * GW
                self.cam_y = (pos[1] - self.MINI.y) / self.MINI.h * GH
                self.follow = False
                self.clamp_cam()
                return
            if self.sel and self.card_rect.collidepoint(pos):
                return
            for b in (self.tool_buttons + self.overlay_buttons + self.tab_buttons + self.bottom_buttons +
                      self.graph_buttons + self.misc):
                if b.handle(ev, pos):
                    return
            if self.in_view(pos) and self.tool in ("inspect", "microscope"):
                self.left_press = (pos, self.cam_x, self.cam_y)
                self.left_dragged = False
                return
            if self.in_view(pos):
                if self.tool == "sanctuary":
                    wx, wy = self.s2w(*pos)
                    gx, gy = int(min(GW - 1, max(0, wx))), int(min(GH - 1, max(0, wy)))
                    self.sanct_mode = not bool(self.world.sanctuary[gx, gy])
                self.painting = True
                self.apply_tool(shift=bool(pygame.key.get_mods() & pygame.KMOD_SHIFT))
        elif ev.type == pygame.MOUSEBUTTONUP and ev.button == 1:
            self.painting = False

    def open_creator(self):
        self.painting = False
        self.creator = Creator(self)

    def open_alert(self, a):
        self.painting = False
        self.alert_view = AlertView(self, a)

    def screenshot(self):
        if WEB:
            import io
            buf = io.BytesIO()
            pygame.image.save(self.display, buf, "screenshot.png")
            webplatform.download(buf.getvalue(), "nz_ecosim_%s.png" % self.world.stamp.replace(" ", "_"), "image/png")
            self.toast("Screenshot downloaded.")
            return
        os.makedirs(SHOT_DIR, exist_ok=True)
        p = os.path.join(SHOT_DIR, "nz_ecosim_%s_%d.png" % (self.world.stamp.replace(" ", "_"), int(time.time())))
        pygame.image.save(self.screen, p)
        self.toast("Screenshot saved to %s" % p)

    # -------------------------------------------------------------- drawing
    def draw(self):
        s = self.screen
        self.clickables = []
        s.fill(BG)
        self.draw_world(s)
        if not self.modal_open():
            self.goal_rect = lessons_ui.draw_goal_box(self, s, self.mouse)
        self.draw_panel(s)
        self.draw_bottom(s)
        if self.banner and not self.modal_open():
            a, ttl = self.banner
            col = SEV_COLORS[a["sev"]]
            text = "%s   -   click for details" % a["title"]
            w = min(VIEW_W - 40, self.fonts.b.size(text)[0] + 40)
            r = pygame.Rect((VIEW_W - w) // 2, 10, w, 30)
            box = pygame.Surface(r.size, pygame.SRCALPHA)
            box.fill((*TIP, 230))
            s.blit(box, r)
            pygame.draw.rect(s, col, r, 2, border_radius=6)
            draw_text(s, self.fonts, text, r.center, col, self.fonts.b, "center", maxw=w - 20)
            self.clickables.insert(0, (r, lambda a=a: (self.open_alert(a), setattr(self, "banner", None))))
        elif self.toast_t > 0:
            img = self.fonts.render(self.fonts.m, self.toast_msg, TEXT)
            r = img.get_rect(midtop=(VIEW_W // 2, 12)).inflate(24, 12)
            box = pygame.Surface(r.size, pygame.SRCALPHA)
            box.fill((*TIP, 215))
            s.blit(box, r)
            s.blit(img, img.get_rect(center=r.center))
        # rearrange the regions for the chosen layout, then draw floating things on top
        self.compose()
        s = self.display
        self.display_ready = True
        for fn in self.post:
            fn(s)
        self.post = []
        if self.drawer and not self.modal_open():
            self.draw_drawer(s)
        m = self.mouse_disp
        if self.show_help:
            self.draw_help(s)
        if self.makeup_view:
            self.draw_makeup_modal(s)
        if self.clans:
            self.clans.draw(s, self.fonts, m)
        if self.history_view:
            self.history_view.draw(s, self.fonts, m)
        if self.collapse_view:
            self.collapse_view.draw(s, self.fonts, m)
        if self.foodweb_view:
            self.foodweb_view.draw(s, self.fonts, m)
        if self.lesson_picker:
            self.lesson_picker.draw(s, self.fonts, m)
        if self.lesson_result:
            self.lesson_result.draw(s, self.fonts, m)
        if self.report_view:
            self.report_view.draw(s, self.fonts, m)
        if self.newworld:
            self.newworld.draw(s, self.fonts, m)
        if self.settings_view:
            self.settings_view.draw(s, self.fonts, m)
        if self.creator:
            self.creator.draw(s, self.fonts, m)
        if self.alert_view:
            self.alert_view.draw(s, self.fonts, m)
        if self.away:
            self.clickables = []
            self.draw_away(s)

    # ---------------------------------------------------------------- camera
    @property
    def ppc(self):
        return CELL * self.zoom

    def view_cells(self):
        return VIEW_W / self.ppc, VIEW_H / self.ppc

    PAD = 30          # cells of open ocean you can pan past the edge of the world

    def clamp_cam(self):
        vw, vh = self.view_cells()
        for attr, v, size in (("cam_x", vw, GW), ("cam_y", vh, GH)):
            lo, hi = v / 2 - self.PAD, size + self.PAD - v / 2
            c = getattr(self, attr)
            setattr(self, attr, size / 2 if lo > hi else min(max(c, lo), hi))

    def cam_left_top(self):
        vw, vh = self.view_cells()
        return self.cam_x - vw / 2, self.cam_y - vh / 2

    def w2s(self, x, y):
        l, t = self.cam_left_top()
        p = self.ppc
        return (x - l) * p, (y - t) * p

    def s2w(self, px, py):
        l, t = self.cam_left_top()
        p = self.ppc
        return l + px / p, t + py / p

    def zoom_at(self, factor, px, py):
        wx, wy = self.s2w(px, py)
        self.zoom = min(6.0, max(ZOOM_MIN, self.zoom * factor))
        vw, vh = self.view_cells()
        self.cam_x = wx - px / self.ppc + vw / 2
        self.cam_y = wy - py / self.ppc + vh / 2
        self.clamp_cam()

    def center_on(self, x, y, zoom=None):
        if zoom:
            self.zoom = max(self.zoom, zoom)
        self.cam_x, self.cam_y = x, y
        self.clamp_cam()

    def locate_tribe(self, t):
        self.clans = None
        self.sel = {"kind": "tribe", "obj": t}
        self.center_on(t.x, t.y, 2.5)
        self.highlight = (t.x, t.y, FPS * 4)

    # ------------------------------------------------------------- selection
    def pick(self, px, py):
        w = self.world
        wx, wy = self.s2w(px, py)
        r = max(1.2, 7 / self.ppc)
        p = w.person_near(wx, wy, r)
        if p:
            return {"kind": "person", "obj": p}
        a = w.animal_near(wx, wy, r * 1.3)
        if a:
            return {"kind": "animal", "obj": a}
        gx, gy = int(min(max(wx, 0), GW - 1)), int(min(max(wy, 0), GH - 1))
        if w.struct[gx, gy] in (HOUSE, FIELD) and w.owner[gx, gy] >= 0:
            return {"kind": "tribe", "obj": w.tribes[int(w.owner[gx, gy])]}
        return None

    def sel_alive(self):
        if not self.sel:
            return False
        o = self.sel["obj"]
        return o.alive

    def target_of_person(self, p):
        if p.target is not None and p.target.alive:
            return p.target.x, p.target.y
        if p.tx is not None:
            return p.tx, p.ty
        return None

    MODE_COLORS = {"fight": (255, 70, 60), "raid": (255, 70, 60), "march": (255, 110, 80), "hunt": (255, 160, 60),
                   "gather": (130, 220, 120), "fish": (100, 190, 255), "chop": (210, 160, 100),
                   "build": (230, 190, 130), "field": (240, 220, 110), "tend": (240, 220, 110), "walk": (200, 200, 200)}

    def draw_line_to(self, view, a, b, col, width=2, dashed=False):
        (x0, y0), (x1, y1) = self.w2s(*a), self.w2s(*b)
        if dashed:
            d = math.hypot(x1 - x0, y1 - y0)
            n = max(1, int(d / 10))
            for i in range(0, n, 2):
                t0, t1 = i / n, min(1, (i + 1) / n)
                pygame.draw.line(view, col, (x0 + (x1 - x0) * t0, y0 + (y1 - y0) * t0),
                                 (x0 + (x1 - x0) * t1, y0 + (y1 - y0) * t1), width)
        else:
            pygame.draw.line(view, col, (x0, y0), (x1, y1), width)
        pygame.draw.circle(view, col, (int(x1), int(y1)), 4, 1)

    def draw_selection_lines(self, view):
        if not self.sel:
            return
        w = self.world
        k, o = self.sel["kind"], self.sel["obj"]
        if k == "person" and o.alive:
            t = w.tribes[o.tribe]
            tg = self.target_of_person(o)
            if tg and not o.sleeping:
                self.draw_line_to(view, (o.x, o.y), tg, self.MODE_COLORS.get(o.mode, (200, 200, 200)), 2,
                                  dashed=o.mode == "walk")
            for e in t.war:
                et = w.tribes[e]
                self.draw_line_to(view, (o.x, o.y), (et.x, et.y), (255, 80, 70), 1, dashed=True)
            px, py = self.w2s(o.x, o.y)
            pygame.draw.circle(view, (255, 255, 255), (int(px), int(py)), int(6 + self.zoom * 2), 1)
        elif k == "animal" and o.alive:
            if o.prey is not None and o.prey.alive:
                self.draw_line_to(view, (o.x, o.y), (o.prey.x, o.prey.y), (255, 80, 70), 2)
            elif o.tx is not None:
                self.draw_line_to(view, (o.x, o.y), (o.tx, o.ty), (130, 220, 120), 1, dashed=True)
            px, py = self.w2s(o.x, o.y)
            pygame.draw.circle(view, (255, 255, 255), (int(px), int(py)), int(6 + o.esize * 3 * self.zoom), 1)
        elif k == "tribe" and o.alive:
            cx, cy = self.w2s(o.x, o.y)
            pygame.draw.circle(view, o.color, (int(cx), int(cy)), int(humans.territory_radius(o) * self.ppc), 2)
            for p in w.people:
                if p.tribe == o.id and p.role == "warrior" and not p.sleeping:
                    tg = self.target_of_person(p)
                    if tg and p.mode in ("fight", "raid", "march"):
                        self.draw_line_to(view, (p.x, p.y), tg, (255, 70, 60), 1)
            for e in o.war:
                et = w.tribes[e]
                self.draw_line_to(view, (o.x, o.y), (et.x, et.y), (255, 80, 70), 3, dashed=True)
                mx, my = self.w2s((o.x + et.x) / 2, (o.y + et.y) / 2)
                draw_text(view, self.fonts, "WAR", (mx, my), (255, 120, 100), self.fonts.b, "center")

    def draw_world(self, s):
        w = self.world
        self.clamp_cam()
        dn = self.ui.get("daynight", "shade")
        smooth = (w.settings["time"] > 2.5 and not self.paused) or dn != "shade"
        rgb = render_world(w, self.static, self.overlay, self.frame, smooth)
        small = pygame.surfarray.make_surface(rgb)
        self.small_map = small
        view = pygame.Surface((VIEW_W, VIEW_H))
        edge = np.concatenate([rgb[0, :], rgb[-1, :], rgb[:, 0], rgb[:, -1]]).mean(axis=0)
        view.fill(tuple(int(c) for c in edge))           # open ocean beyond the edge of the world
        ppc = self.ppc
        z = self.zoom
        zf = z ** 0.75
        left, top = self.cam_left_top()
        vw, vh = self.view_cells()
        x0, y0 = max(0, int(math.floor(left))), max(0, int(math.floor(top)))
        x1, y1 = min(GW, int(math.ceil(left + vw)) + 1), min(GH, int(math.ceil(top + vh)) + 1)
        sub = small.subsurface((x0, y0, x1 - x0, y1 - y0))
        view.blit(pygame.transform.scale(sub, (int(round((x1 - x0) * ppc)), int(round((y1 - y0) * ppc)))),
                  (int(round((x0 - left) * ppc)), int(round((y0 - top) * ppc))))

        def vis(x, y, m=2):
            return x0 - m <= x <= x1 + m and y0 - m <= y <= y1 + m

        night = w.sun_raw < 0.25 and not smooth
        dimf = 0.45 + 0.55 * min(1.0, w.sun_raw * 1.6) if (self.overlay == 0 and not smooth) else 1.0
        if self.overlay == 0:
            sub_f = w.fungus[x0:x1, y0:y1]
            mx, my = np.nonzero((sub_f > 0.8) & MUSH_MASK[x0:x1, y0:y1] & (w.water[x0:x1, y0:y1] < 0.1) &
                                (w.struct[x0:x1, y0:y1] == NONE))
            cap = (110, 240, 220) if night else (226, 206, 176)
            for x, y in zip(mx[:500], my[:500]):
                px, py = self.w2s(x + x0 + 0.5, y + y0 + 0.4)
                pygame.draw.line(view, (235, 230, 215), (px, py), (px, py + max(2, ppc * 0.4)))
                pygame.draw.circle(view, cap, (int(px), int(py)), max(2, int(ppc * 0.35)))
            # fish shoals glint in the sea
            fx, fy = np.nonzero((w.fish[x0:x1, y0:y1] > 0.45) & SHOAL_MASK[x0:x1, y0:y1])
            ph = self.frame * 0.1
            for x, y in zip(fx[:400], fy[:400]):
                gx, gy = x + x0, y + y0
                px, py = self.w2s(gx + 0.5 + 0.3 * math.sin(ph + gy), gy + 0.5)
                view.set_at((int(px), int(py)), (200, 225, 240))
                if z > 2:
                    view.set_at((int(px) + 1, int(py)), (170, 200, 220))
        # structures
        if w.struct.any():
            hx, hy = np.nonzero(w.struct[x0:x1, y0:y1] == HOUSE)
            for x, y in zip(hx + x0, hy + y0):
                o = int(w.owner[x, y])
                tc = w.tribes[o].color if 0 <= o < len(w.tribes) else (150, 150, 150)
                tc = tuple(int(c * dimf) for c in tc)
                px, py = self.w2s(x, y)
                pygame.draw.rect(view, (int(150 * dimf), int(112 * dimf), int(72 * dimf)),
                                 (px, py + ppc * 0.4, ppc, ppc * 0.6))
                pygame.draw.polygon(view, tc, [(px - ppc * 0.15, py + ppc * 0.42), (px + ppc * 0.5, py - ppc * 0.2),
                                               (px + ppc * 1.15, py + ppc * 0.42)])
                if night and (x + y + self.frame // 20) % 3:
                    pygame.draw.rect(view, (255, 210, 120), (px + ppc * 0.4, py + ppc * 0.6, max(1, ppc * 0.2),
                                                             max(1, ppc * 0.2)))
            tx, ty = np.nonzero(w.struct[x0:x1, y0:y1] == TRAP)
            for x, y in zip(tx + x0, ty + y0):
                px, py = self.w2s(x + 0.2, y + 0.2)
                q = max(3, int(ppc * 0.6))
                pygame.draw.rect(view, (40, 36, 30), (px, py, q, q))
                pygame.draw.rect(view, (240, 130, 40), (px + q // 3, py + q // 3, max(1, q // 3), max(1, q // 3)))
        # animals
        for a in w.animals:
            if not vis(a.x, a.y):
                continue
            px, py = self.w2s(a.x, a.y)
            px, py = int(px), int(py)
            r = max(1, int((1.0 + a.esize * 2.2) * zf))
            c = a.sp.color
            if not a.awake:
                c = (c[0] * 0.55, c[1] * 0.55, c[2] * 0.55)
            c = (int(c[0] * dimf), int(c[1] * dimf), int(c[2] * dimf))
            if a.sp.flier and a.awake:
                wing = r + 2
                flap = 1 if (self.frame + id(a)) % 6 < 3 else -1
                pygame.draw.line(view, (230, 230, 230), (px - wing, py + flap), (px + wing, py + flap), 1)
            pygame.draw.circle(view, c, (px, py), r)
            if r >= 3:
                pygame.draw.circle(view, (20, 20, 20), (px, py), r, 1)
            if not a.sp.native and r >= 2:
                pygame.draw.circle(view, (230, 90, 70), (px, py), r + 1, 1)
            if a.sick:
                pygame.draw.circle(view, (170, 230, 60), (px, py), r + 2, 1)
        # people
        for p in w.people:
            if not vis(p.x, p.y):
                continue
            t = w.tribes[p.tribe]
            px, py = self.w2s(p.x, p.y)
            px, py = int(px), int(py)
            c = tuple(int(v * dimf * (0.6 if p.sleeping else 1)) for v in t.color)
            bw, bh = max(3, int(3 * zf)), max(4, int(4 * zf))
            pygame.draw.rect(view, c, (px - bw // 2, py - bh // 2, bw, bh))
            pygame.draw.circle(view, (int(240 * dimf), int(226 * dimf), int(206 * dimf)),
                               (px, py - bh // 2 - max(1, int(zf))), max(1, int(zf)))
            if p.role == "warrior" and t.war:
                pygame.draw.rect(view, (255, 60, 50), (px - bw // 2 - 1, py - bh // 2 - 1, bw + 2, bh + 2), 1)
        for sh in w.ships:
            if sh.state == "away" or not vis(sh.x, sh.y, 4):
                continue
            t = w.tribes[sh.tribe]
            px, py = self.w2s(sh.x, sh.y)
            k = max(1.0, zf * 1.3)
            ang = math.atan2(sh.hy, sh.hx)
            ca, sa = math.cos(ang), math.sin(ang)

            def P(dx, dy):
                return (px + (dx * ca - dy * sa) * k, py + (dx * sa + dy * ca) * k)
            pygame.draw.polygon(view, (120, 80, 45), [P(6, 0), P(3, 2.5), P(-5, 2.5), P(-6, 0), P(-5, -2.5), P(3, -2.5)])
            pygame.draw.polygon(view, (245, 240, 225), [(px, py - 9 * k), (px + 5 * k, py - 1 * k), (px, py - 1 * k)])
            pygame.draw.line(view, t.color, (px, py - 9 * k), (px, py), max(1, int(k)))
            if self.sel and self.sel.get("kind") == "tribe" and self.sel["obj"] is t:
                draw_text(view, self.fonts, "fetching %s" % sh.cargo, (px, py - 12 * k), (255, 255, 255),
                          self.fonts.xs, "midbottom")
        self.draw_selection_lines(view)
        # clouds & precipitation
        if w.clouds:
            layer = pygame.Surface((VIEW_W, VIEW_H), pygame.SRCALPHA)
            for c in w.clouds:
                fade = min(1.0, c.age / 60.0)
                dens = min(1.0, c.water / 200)
                alpha = int((60 + 110 * dens) * fade / (1 + (z - 1) * 0.25))
                g = int(235 - 120 * dens) if c.raining else 238
                col = (g, g, min(255, g + 8), alpha)
                cx, cy = self.w2s(c.x, c.y)
                rr = c.r * ppc
                if cx + rr * 2 < 0 or cx - rr * 2 > VIEW_W or cy + rr * 2 < 0 or cy - rr * 2 > VIEW_H:
                    continue
                rnd = random.Random(id(c))
                for k in range(5):
                    ox = rnd.uniform(-1.0, 1.0) * rr * 0.9
                    oy = rnd.uniform(-0.5, 0.5) * rr * 0.6
                    ew = rr * rnd.uniform(0.9, 1.4)
                    eh = rr * rnd.uniform(0.55, 0.85)
                    pygame.draw.ellipse(layer, col, (cx + ox - ew / 2, cy + oy - eh / 2, ew, eh))
                if c.raining and fade > 0.5:
                    snowing = w.temp[int(min(max(c.x, 0), GW - 1)), int(min(max(c.y, 0), GH - 1))] < 0
                    for _ in range(int(25 + 50 * dens)):
                        ang = random.random() * math.tau
                        d = math.sqrt(random.random())
                        x = cx + math.cos(ang) * d * rr * 1.3
                        y = cy + math.sin(ang) * d * rr * 0.8
                        if snowing:
                            pygame.draw.circle(layer, (255, 255, 255, 200), (int(x), int(y)), max(1, int(zf)))
                        else:
                            pygame.draw.line(layer, (190, 210, 255, 150), (x, y), (x + w.wind[0] * 3, y + 7 * zf))
            view.blit(layer, (0, 0))
        for lx, ly, ttl in w.lightning:
            if dn == "shade":
                flash = pygame.Surface((VIEW_W, VIEW_H), pygame.SRCALPHA)
                flash.fill((255, 255, 255, int(12 * ttl)))
                view.blit(flash, (0, 0))
            x, yb = self.w2s(lx + 0.5, ly)
            pts = [(x + random.randint(-30, 30), 0)]
            for k in range(1, 9):
                pts.append((x + random.randint(-12, 12) * (1 - k / 8), yb * k / 8))
            pygame.draw.lines(view, (255, 255, 230), False, pts, 2)
        s.blit(view, (0, 0))
        self.view_surf = view
        if self.highlight:
            x, y, ttl = self.highlight
            hx, hy = self.w2s(x, y)
            rr = 18 + 10 * math.sin(self.frame * 0.3)
            pygame.draw.circle(s, (255, 240, 120), (int(hx), int(hy)), int(rr), 3)
            pygame.draw.circle(s, (255, 240, 120), (int(hx), int(hy)), int(rr + 14), 1)
        if dn == "icon":
            cx, cy = VIEW_W - 34, 34
            pygame.draw.circle(s, (*TIP,), (cx, cy), 22)
            if w.sun_raw > 0:
                for k in range(8):
                    a = k * math.pi / 4
                    pygame.draw.line(s, (255, 210, 80), (cx + math.cos(a) * 12, cy + math.sin(a) * 12),
                                     (cx + math.cos(a) * 18, cy + math.sin(a) * 18), 2)
                pygame.draw.circle(s, (255, 214, 90), (cx, cy), 9)
            else:
                pygame.draw.circle(s, (225, 228, 240), (cx, cy), 11)
                pygame.draw.circle(s, TIP, (cx + 5, cy - 3), 10)
            draw_text(s, self.fonts, w.clock, (cx, cy + 26), (240, 240, 240), self.fonts.xs, "midtop")
        if self.map_moved():
            self.draw_minimap(s)
        if self.sel:
            self.draw_sel_card(s)

        if self.in_view(self.mouse) and not self.modal_open() and not self.over_overlay_ui(self.mouse):
            mx, my = self.mouse
            if self.tool == "microscope":
                self.draw_microscope(s, view, mx, my)
            elif self.tool == "inspect":
                if not self.sel or not self.card_rect.collidepoint(self.mouse):
                    self.draw_inspector(s, mx, my)
            elif self.tool == "cloud":
                pygame.draw.circle(s, (220, 230, 255), (mx, my), int(12 * ppc / 2), 1)
            elif self.tool == "species" and self.selected and self.selected.kind in ("animal", "human"):
                pygame.draw.circle(s, self.selected.color, (mx, my), 7, 2)
                draw_text(s, self.fonts, "+ " + self.selected.name, (mx + 12, my - 8), (255, 255, 255))
            else:
                pygame.draw.circle(s, (255, 255, 255), (mx, my), int(self.brush * ppc), 1)
                if self.tool == "species" and self.selected:
                    draw_text(s, self.fonts, "+ " + self.selected.name, (mx + 12, my - 8), (255, 255, 255))
        if self.overlay:
            title, text, stops, lo, hi = OVERLAY_INFO[self.overlay]
            box = pygame.Rect(8, VIEW_H - 78, 220, 52)
            bg = pygame.Surface(box.size, pygame.SRCALPHA)
            bg.fill((*TIP, 210))
            s.blit(bg, box)
            draw_text(s, self.fonts, title + "  (hover the button for details)", (box.x + 8, box.y + 5), TEXT,
                      self.fonts.xs, maxw=box.w - 12)
            if stops:
                self.legend_bar(s, box.x + 8, box.y + 22, box.w - 16, stops, lo, hi)
        hud = "%s view   zoom %.1fx%s" % (OVERLAYS[self.overlay], self.zoom, "   PAUSED" if self.paused else "")
        draw_text(s, self.fonts, hud, (8, VIEW_H - 20), (255, 255, 255) if not self.paused else WARN)
        if self.zoom == 1.0 and self.frame < FPS * 20:
            draw_text(s, self.fonts, "Scroll to zoom in or out, drag the map to move it, click a person, animal or house",
                      (8, VIEW_H - 38), (230, 230, 230), self.fonts.xs)

    MINI = pygame.Rect(VIEW_W - 170, VIEW_H - 112, 160, 100)

    def over_overlay_ui(self, pos):
        if self.map_moved() and self.MINI.collidepoint(pos):
            return True
        return bool(self.sel) and self.card_rect.collidepoint(pos)

    def map_moved(self):
        return abs(self.zoom - 1.0) > 0.01 or abs(self.cam_x - GW / 2) > 0.5 or abs(self.cam_y - GH / 2) > 0.5

    def draw_minimap(self, s):
        r = self.MINI
        img = pygame.transform.smoothscale(self.small_map, (r.w, r.h))
        s.blit(img, r)
        pygame.draw.rect(s, (230, 230, 230), r, 1)
        left, top = self.cam_left_top()
        vw, vh = self.view_cells()
        vr = pygame.Rect(r.x + left / GW * r.w, r.y + top / GH * r.h, vw / GW * r.w, vh / GH * r.h).clip(r)
        pygame.draw.rect(s, (255, 240, 120), vr, 1)

    def draw_sel_card(self, s):
        w = self.world
        f = self.fonts
        k, o = self.sel["kind"], self.sel["obj"]
        W = 340
        lines = []          # (text, colour, font)
        title, tcol = "", TEXT
        buttons = []
        if k == "person":
            t = w.tribes[o.tribe]
            title, tcol = "Person of the %s" % t.name, t.color
            if not o.alive:
                lines.append(("Has died.", (240, 120, 100), f.b))
            else:
                head, why = humans.describe_person(w, o)
                lines.append((head, TEXT, f.b))
                for ln in why:
                    for wl in wrap(ln, f.s, W - 24):
                        lines.append((wl, TEXT, f.s))
            lines.append(("", TEXT, f.xs))
            lines.append(("CLAN STATUS", ACCENT, f.xs))
            others = [x for x in w.tribes if x.alive and x.id != t.id]
            if t.war:
                lines.append(("At war with: " + ", ".join(w.tribes[i].name for i in t.war), (255, 120, 100), f.s))
            for x in others[:5]:
                lab, col = humans.relation(w, t, x)
                if x.id not in t.war:
                    lines.append(("%s: %s" % (x.name, lab), col, f.s))
            if not others:
                lines.append(("The only clan on the island.", DIM, f.s))
            lines.append(("%d people, %d houses, %d fields, food for %.1f days" % (
                t.pop, t.houses, t.fields, humans.food_days(t)), DIM, f.xs))
            buttons.append(("Clan details", lambda t=t: self.open_clans(t.id)))
        elif k == "animal":
            sp = o.sp
            title, tcol = "%s%s" % (sp.name, " (%s)" % sp.english if sp.english and sp.english != sp.name else ""), sp.color
            head, why = views.describe_animal(w, o)
            lines.append((head, TEXT, f.b))
            for ln in why:
                for wl in wrap(ln, f.s, W - 24):
                    lines.append((wl, TEXT, f.s))
        else:
            t = o
            title, tcol = t.name, t.color
            if not t.alive:
                lines.append(("This clan is gone.", (240, 120, 100), f.b))
            else:
                desc, roles = humans.describe_tribe(w, t)
                for ln in desc[:6]:
                    for wl in wrap(ln, f.s, W - 24):
                        lines.append((wl, TEXT, f.s))
                lines.append(("Jobs: " + ", ".join("%s %d" % kv for kv in sorted(roles.items(), key=lambda kv: -kv[1])),
                              DIM, f.xs))
            buttons.append(("Clan details", lambda t=t: self.open_clans(t.id)))
        buttons.append(("Unfollow" if self.follow else "Follow", lambda: setattr(self, "follow", not self.follow)))
        buttons.append(("Close", self.clear_sel))
        h = 34 + sum(fn.get_linesize() for _, _, fn in lines) + 40
        r = pygame.Rect(10, 48, W, min(h, VIEW_H - 60))
        self.card_rect = r
        box = pygame.Surface(r.size, pygame.SRCALPHA)
        box.fill((*TIP, 235))
        s.blit(box, r)
        pygame.draw.rect(s, tcol, r, 2, border_radius=6)
        draw_text(s, f, title, (r.x + 12, r.y + 9), tcol, f.b, maxw=W - 24)
        y = r.y + 32
        for txt, col, fn in lines:
            if y > r.bottom - 50:
                break
            draw_text(s, f, txt, (r.x + 12, y), col, fn, maxw=W - 24)
            y += fn.get_linesize()
        bx = r.x + 12
        for lab, cb in buttons:
            bwid = f.s.size(lab)[0] + 20
            br = pygame.Rect(bx, r.bottom - 34, bwid, 24)
            b = Button(lab, cb)
            b.draw(s, f, br, br.collidepoint(self.mouse), f.s)
            self.clickables.append((br, cb))
            bx += bwid + 6

    def draw_drawer(self, s):
        mx, my, by, px = self.offsets()
        W, H = 600, 330
        x = px - W - 6 if px > 0 else px + PANEL_W + 6
        r = pygame.Rect(x, 104, W, H)
        self.drawer_rect = r
        views.draw_health_drawer(s, self.fonts, self.world, r, self.mouse_disp)

    def clear_sel(self):
        self.sel = None
        self.follow = False

    def open_clans(self, tid=None):
        self.painting = False
        self.clans = views.ClansView(self, tid)

    def draw_microscope(self, s, view, mx, my):
        R, Z = 95, 4
        src = pygame.Rect(mx - R // Z, my - R // Z, 2 * R // Z, 2 * R // Z)
        clip = src.clip(view.get_rect())
        if clip.w <= 0 or clip.h <= 0:
            return
        lens = pygame.Surface((2 * R, 2 * R), pygame.SRCALPHA)
        lens.fill((10, 12, 14, 255))
        sub = pygame.transform.scale(view.subsurface(clip), (clip.w * Z, clip.h * Z))
        lens.blit(sub, ((clip.x - src.x) * Z, (clip.y - src.y) * Z))
        veil = pygame.Surface((2 * R, 2 * R), pygame.SRCALPHA)
        veil.fill((235, 240, 230, 70))
        lens.blit(veil, (0, 0))
        w = self.world
        cs = self.ppc * Z
        x0, y0 = self.s2w(src.x, src.y)
        t = self.frame * 0.06
        for cx in range(int(x0), int(x0 + 2 * R / cs) + 2):
            for cy in range(int(y0), int(y0 + 2 * R / cs) + 2):
                if not (0 <= cx < GW and 0 <= cy < GH):
                    continue
                bx, by = (cx - x0) * cs, (cy - y0) * cs
                rnd = random.Random(cx * 7919 + cy)
                f = float(w.fungus[cx, cy])
                if f > 0.05:
                    for _ in range(int(f * 2.5) + 1):
                        a = rnd.random() * math.pi
                        L = cs * (0.6 + f)
                        ox, oy = bx + rnd.random() * cs, by + rnd.random() * cs
                        pygame.draw.line(lens, (245, 240, 220, 220), (ox, oy),
                                         (ox + math.cos(a) * L, oy + math.sin(a) * L), 1)
                n = int(float(w.microbes[cx, cy]) * 9)
                for k in range(n):
                    px = bx + rnd.random() * cs + math.sin(t * (1 + k % 3) + k) * 2.5
                    py = by + rnd.random() * cs + math.cos(t * 1.3 + k * 2) * 2.5
                    if k % 3 == 0:
                        pygame.draw.circle(lens, (200, 120, 240), (int(px), int(py)), 2)
                    else:
                        ang = rnd.random() * math.pi + t * 0.2
                        dx, dy = math.cos(ang) * 3, math.sin(ang) * 3
                        pygame.draw.line(lens, (120, 230, 150), (px - dx, py - dy), (px + dx, py + dy), 2)
                if w.pollen[cx, cy] > 0.2 and rnd.random() < 0.5:
                    pygame.draw.circle(lens, (250, 220, 80), (int(bx + cs / 2), int(by + cs / 2)), 2)
        lens.blit(self.lens_mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
        s.blit(lens, (mx - R, my - R))
        pygame.draw.circle(s, (200, 205, 215), (mx, my), R, 3)
        pygame.draw.circle(s, (60, 64, 72), (mx, my), R + 3, 2)
        wx, wy = self.s2w(mx, my)
        gx, gy = int(min(GW - 1, max(0, wx))), int(min(GH - 1, max(0, wy)))
        lines = ["x400 microscope",
                 "bacteria %d%%   mycelium %d%%" % (w.microbes[gx, gy] * 100, w.fungus[gx, gy] * 100)]
        box = pygame.Surface((230, 38), pygame.SRCALPHA)
        box.fill((*TIP, 200))
        by = my + R + 6 if my + R + 46 < VIEW_H else my - R - 46
        s.blit(box, (mx - 115, by))
        for i, ln in enumerate(lines):
            draw_text(s, self.fonts, ln, (mx, by + 3 + i * 16), TEXT, anchor="midtop")

    def tooltip_box(self, s, lines, mx, my, width=None):
        f = self.fonts
        widths = [(f.b if b else f.s).size(t)[0] for t, _, b in lines]
        bw = width or (max(widths) + 20)
        bh = len(lines) * 17 + 12
        bx = mx + 18 if mx + 18 + bw < VIEW_W else mx - 18 - bw
        by = min(my + 12, VIEW_H - bh - 4)
        box = pygame.Surface((bw, bh), pygame.SRCALPHA)
        box.fill((*TIP, 230))
        s.blit(box, (bx, by))
        pygame.draw.rect(s, LINE, (bx, by, bw, bh), 1)
        for i, (t, c, b) in enumerate(lines):
            draw_text(s, f, t, (bx + 10, by + 6 + i * 17), c, f.b if b else f.s)

    def draw_inspector(self, s, mx, my):
        w = self.world
        wx, wy = self.s2w(mx, my)
        gx, gy = int(min(GW - 1, max(0, wx))), int(min(GH - 1, max(0, wy)))
        lines = []
        rr = max(1.2, 7 / self.ppc)
        p = w.person_near(wx, wy, rr)
        a = None if p else w.animal_near(wx, wy, rr * 1.3)
        if p:
            t = w.tribes[p.tribe]
            lines.append(("Person of the %s" % t.name, t.color, True))
            head, _ = humans.describe_person(w, p)
            lines.append(("%s - %s" % (p.role, head), TEXT, False))
            lines.append(("tribe: %d people, %d houses, %d fields" % (t.pop, t.houses, t.fields), TEXT, False))
            lines.append(("food %d   wood %d   animals hunted %d" % (t.food, t.wood, t.kills), DIM, False))
            if t.war:
                lines.append(("at war with " + ", ".join(w.tribes[i].name for i in t.war), (255, 120, 100), False))
            lines.append(("", TEXT, False))
        elif a:
            sp = a.sp
            state = ("asleep" if not a.awake else "hunting" if a.prey else "fleeing" if a.flee else
                     "foraging" if a.tx else "wandering")
            lines.append(("%s%s" % (sp.name, "  (%s)" % sp.english if sp.english and sp.english != sp.name else ""),
                          sp.color, True))
            lines.append(("%s, %s%s%s, gen %d" % ("native" if sp.native else "INTRODUCED",
                                                 "juvenile, " if a.juvenile else "", state,
                                                 ", sick" if a.sick else "", a.gen),
                          TEXT if sp.native else (240, 150, 120), False))
            lines.append(("%s   energy %d%%   age %s" % (views.describe_animal(w, a)[0], 100 * a.energy / (60 * a.size),
                                                          age_text(a.age)), TEXT, False))
            lines.append(("size %.2f (%+d%%)   speed %.2f (%+d%%)" % (
                a.size, 100 * (a.size / sp.size - 1), a.speed, 100 * (a.speed / sp.speed - 1)), DIM, False))
            lines.append(("", TEXT, False))
            ax, ay = self.w2s(a.x, a.y)
            pygame.draw.circle(s, (255, 255, 255), (int(ax), int(ay)), int(4 + a.esize * 3 * self.zoom), 1)
        st = w.struct[gx, gy]
        if w.sea[gx, gy]:
            lines.append(("Ocean", (120, 170, 220), True))
        elif st in (HOUSE, FIELD):
            o = int(w.owner[gx, gy])
            t = w.tribes[o] if 0 <= o < len(w.tribes) else None
            lines.append(("%s of the %s" % ("House" if st == HOUSE else "Field", t.name if t else "?"),
                          t.color if t else TEXT, True))
            if st == FIELD:
                lines.append(("soil nutrients %.2f%s" % (w.nutr[gx, gy], "  (exhausted)" if w.nutr[gx, gy] < 0.1 else ""),
                              TEXT, False))
        elif st == RUIN:
            lines.append(("Ruins", (170, 160, 150), True))
        else:
            ps = w.pspec[gx, gy]
            if ps >= 0:
                pl = w.plant_species[ps]
                lines.append(("%s  (biomass %.2f)%s" % (pl.name, w.pbio[gx, gy], "" if pl.native else "  INTRODUCED"),
                              pl.color, True))
            else:
                lines.append(("Bare ground" if w.water[gx, gy] < 0.2 else "Water", TEXT, True))
        if st == TRAP:
            lines.append(("Pest trap", (240, 150, 70), False))
        if w.sanctuary[gx, gy]:
            lines.append(("Inside a predator-free sanctuary", (120, 220, 200), False))
        if not w.sea[gx, gy]:
            lines.append(("%.1f C   soil water %d%%   pond %.2f   altitude %d m" % (
                w.temp[gx, gy], w.moist[gx, gy] * 100, w.water[gx, gy], max(0, (w.height[gx, gy] - 0.24) * 3000)),
                TEXT, False))
            lines.append(("nutrients %.2f   detritus %.2f   microbes %d%%   fungi %d%%" % (
                w.nutr[gx, gy], w.detritus[gx, gy], w.microbes[gx, gy] * 100, w.fungus[gx, gy] * 100), DIM, False))
        if w.snow[gx, gy] > 0.02:
            lines.append(("snow %.2f" % w.snow[gx, gy], (220, 230, 255), False))
        if w.fire[gx, gy] > 0:
            lines.append(("BURNING", (255, 140, 60), True))
        if p or a or st in (HOUSE, FIELD):
            lines.append(("click to select & follow", ACCENT, False))
        self.tooltip_box(s, lines, mx, my)

    # ---------------------------------------------------------------- panel
    def draw_panel(self, s):
        w = self.world
        x0 = VIEW_W
        pygame.draw.rect(s, PANEL, (x0, 0, PANEL_W, LH))
        pygame.draw.line(s, LINE, (x0, 0), (x0, LH))
        px, pw = x0 + 14, PANEL_W - 28
        mouse = self.mouse
        draw_text(s, self.fonts, "NZ EcoSim", (px, 8), TEXT, self.fonts.l)
        mb = self.misc
        mb[1].label = "Resume" if self.paused else "Pause"
        mb[1].draw(s, self.fonts, (x0 + PANEL_W - 104, 10, 62, 24), mb[1].rect.collidepoint(mouse), self.fonts.xs)
        mb[2].draw(s, self.fonts, (x0 + PANEL_W - 38, 10, 24, 24), mb[2].rect.collidepoint(mouse), self.fonts.xs)
        row = [mb[3], mb[5], mb[4], mb[6]]
        bw4 = (pw - 3 * 4) // 4
        for i, b in enumerate(row):
            b.draw(s, self.fonts, (px + i * (bw4 + 4), 40, bw4, 23), b.rect.collidepoint(mouse), self.fonts.xs)
        draw_text(s, self.fonts, "Year %d  -  %s  -  %s  -  %s" % (w.year, w.date.split(",")[0], w.season, w.clock),
                  (px, 70), TEXT, self.fonts.m)
        if w.mast > 0:
            draw_text(s, self.fonts, "MAST YEAR", (px + pw, 72), (230, 200, 120), self.fonts.xs, "topright")
        raining = sum(1 for c in w.clouds if c.raining)
        sky = ("Snow on the tops" if w.base_temp < 4 else "Raining") if raining else (
            "Cloudy" if len(w.clouds) > 4 else "Clear" if w.sun_raw > 0 else "Clear night")
        info = "%.1f C   %s   %s   wind" % (w.base_temp, sky, "day" if w.sun_raw > 0 else "night")
        draw_text(s, self.fonts, info, (px, 90), DIM)
        ax = px + self.fonts.s.size(info)[0] + 16
        ay = 98
        wx, wy = w.wind
        mag = math.hypot(wx, wy)
        if mag > 0.02:
            L = 6 + 6 * min(2, mag)
            ux, uy = wx / mag, wy / mag
            pygame.draw.line(s, TEXT, (ax - ux * L, ay - uy * L), (ax + ux * L, ay + uy * L), 2)
            pygame.draw.polygon(s, TEXT, [(ax + ux * L, ay + uy * L),
                                          (ax + ux * (L - 5) - uy * 4, ay + uy * (L - 5) + ux * 4),
                                          (ax + ux * (L - 5) + uy * 4, ay + uy * (L - 5) - ux * 4)])
        v = w.vitality
        vc = (126, 206, 146) if v > 62 else (230, 200, 90) if v > 40 else (235, 110, 100)
        vr = pygame.Rect(px - 4, 108, pw + 8, 30)
        if vr.collidepoint(mouse) or self.drawer:
            pygame.draw.rect(s, PANEL2, vr, border_radius=5)
        draw_text(s, self.fonts, "Vitality  %s" % ("(click to close)" if self.drawer else "(click for details)"),
                  (px, 112), DIM, self.fonts.xs)
        draw_text(s, self.fonts, "%s  %d" % (w.mood, v), (px + pw, 110), vc, self.fonts.b, anchor="topright")
        bar = pygame.Rect(px, 129, pw, 7)
        pygame.draw.rect(s, LINE, bar, border_radius=4)
        fb = bar.copy()
        fb.w = int(bar.w * v / 100)
        pygame.draw.rect(s, vc, fb, border_radius=4)
        self.clickables.append((vr, lambda: setattr(self, "drawer", not self.drawer)))
        unread = [a for a in w.alerts if not a["read"]][::-1]
        y = 141
        if unread:
            for a in unread[:2]:
                r = pygame.Rect(px - 4, y - 1, pw + 8, 16)
                hov = r.collidepoint(mouse)
                if hov:
                    pygame.draw.rect(s, PANEL2, r, border_radius=4)
                col = SEV_COLORS[a["sev"]]
                pygame.draw.circle(s, col, (px + 4, y + 7), 4)
                draw_text(s, self.fonts, a["title"], (px + 14, y), col if hov else TEXT, self.fonts.xs, maxw=pw - 14)
                self.clickables.append((r, lambda a=a: self.open_alert(a)))
                y += 15
            if len(unread) > 2:
                r = draw_text(s, self.fonts, "+%d more - see Alerts below" % (len(unread) - 2), (px + 14, y), DIM,
                              self.fonts.xs)
                self.clickables.append((r, lambda: setattr(self, "bottom_tab", "alerts")))
        else:
            na, nt = getattr(w, "native_alive", 0), getattr(w, "native_total", 0)
            draw_text(s, self.fonts, "No new alerts.  %d/%d native species alive" % (na, nt), (px, y), DIM,
                      self.fonts.xs, maxw=pw)
            draw_text(s, self.fonts, "Forest %d%%   pests %d%%   people %d" % (
                100 * getattr(w, "forest", 0), 100 * getattr(w, "pest_share", 0), len(w.people)), (px, y + 15), DIM,
                self.fonts.xs)

        # tools
        y = 188
        pygame.draw.line(s, LINE, (px, y - 4), (px + pw, y - 4))
        draw_text(s, self.fonts, "TOOLS", (px, y), ACCENT, self.fonts.b)
        draw_text(s, self.fonts, "brush %d  ([ ] or Ctrl+wheel)" % self.brush, (px + pw, y + 2), DIM, self.fonts.xs,
                  anchor="topright")
        y += 20
        bw = (pw - 4 * 4) // 5
        for i, b in enumerate(self.tool_buttons):
            r = (px + (i % 5) * (bw + 4), y + (i // 5) * 27, bw, 23)
            b.draw(s, self.fonts, r, pygame.Rect(r).collidepoint(mouse), self.fonts.xs)
        y += 2 * 27 + 4
        tw = (pw - 12) // 3
        for i, b in enumerate(self.tab_buttons):
            r = (px + i * (tw + 6), y, tw, 26)
            b.draw(s, self.fonts, r, pygame.Rect(r).collidepoint(mouse), self.fonts.b)
        y += 34
        if self.panel_tab == "learn":
            for sl in self.sliders:
                sl.rect = pygame.Rect(0, 0, 0, 0)
            self.draw_learn(s, px, pw, y)
        elif self.panel_tab == "physics":
            for sl in self.sliders:
                sl.draw(s, self.fonts, px, y, pw)
                y += 30
            draw_text(s, self.fonts, "Right-click a slider to reset it.", (px, y + 4), DIM)
            for sl in self.sliders:
                if sl.rect.inflate(0, 26).move(0, -8).collidepoint(mouse) and sl.tip and not sl.drag:
                    self.tip(s, sl.tip, mouse)
        else:
            for sl in self.sliders:
                sl.rect = pygame.Rect(0, 0, 0, 0)
            self.draw_species_list(s, px, pw, y, LH - 44)
            mb[0].draw(s, self.fonts, (px, LH - 38, pw, 28), mb[0].rect.collidepoint(mouse), self.fonts.b)
        for b in self.tool_buttons + self.misc[3:]:
            if b.rect.collidepoint(mouse) and b.tip:
                self.tip(s, b.tip, mouse)

    def set_difficulty(self, k):
        w = self.world
        if w.difficulty != k:
            w.difficulty = k
            w.log("Difficulty set to %s." % DIFFICULTIES[k]["label"], (160, 200, 220))
            w.actions["Set difficulty to %s" % DIFFICULTIES[k]["label"]] += 1
            self.toast("Difficulty: %s" % DIFFICULTIES[k]["label"])

    def draw_learn(self, s, px, pw, y):
        w = self.world
        f = self.fonts
        mouse = self.mouse

        def button(label, cb, rect, toggled=None, font=None):
            b = Button(label, cb, toggled)
            b.draw(s, f, rect, pygame.Rect(rect).collidepoint(mouse), font or f.xs)
            self.clickables.append((b.rect, cb))

        draw_text(s, f, "LESSON", (px, y), ACCENT, f.b)
        y += 20
        st = getattr(w, "scenario", None)
        if st and st["id"] in scenarios.BY_ID:
            sc = scenarios.BY_ID[st["id"]]
            col = (126, 206, 146) if st["status"] == "won" else (240, 110, 100) if st["status"] == "lost" else TEXT
            draw_text(s, f, sc["title"] + {"won": "  - complete!", "lost": "  - failed"}.get(st["status"], ""),
                      (px, y), col, f.m, maxw=pw)
            y += 22
            for text, prog, state in st.get("goals", []):
                c = (126, 206, 146) if state == "done" else (240, 110, 100) if state == "failed" else TEXT
                for ln in wrap(text, f.xs, pw)[:2]:
                    draw_text(s, f, ln, (px, y), c, f.xs)
                    y += 14
                pygame.draw.rect(s, LINE, (px, y + 1, pw, 5), border_radius=3)
                pygame.draw.rect(s, c if state != "ok" else ACCENT, (px, y + 1, max(2, int(pw * prog)), 5),
                                 border_radius=3)
                y += 11
            y += 4
            if st["status"] != "active":
                button("See result", lambda: setattr(self, "lesson_result", lessons_ui.LessonResult(self)),
                       (px, y, pw // 2 - 3, 24))
                button("Lessons...", lambda: setattr(self, "lesson_picker", lessons_ui.LessonPicker(self)),
                       (px + pw // 2 + 3, y, pw // 2 - 3, 24))
            else:
                tips = sc["tips"]
                tip = tips[(self.frame // (FPS * 12)) % len(tips)]
                for ln in wrap("Tip: " + tip, f.xs, pw)[:3]:
                    draw_text(s, f, ln, (px, y), DIM, f.xs)
                    y += 14
                y += 4
                button("Lessons...", lambda: setattr(self, "lesson_picker", lessons_ui.LessonPicker(self)),
                       (px, y, pw, 24))
            y += 32
        else:
            for ln in wrap("No lesson running (free play). Lessons give you a goal based on a real NZ "
                           "conservation story.", f.xs, pw):
                draw_text(s, f, ln, (px, y), DIM, f.xs)
                y += 14
            y += 4
            button("Choose a lesson...  (L)", lambda: setattr(self, "lesson_picker", lessons_ui.LessonPicker(self)),
                   (px, y, pw, 26), font=f.b)
            y += 36
        pygame.draw.line(s, LINE, (px, y - 4), (px + pw, y - 4))
        draw_text(s, f, "EXPLORE", (px, y + 2), ACCENT, f.b)
        y += 24
        bw = (pw - 6) // 2
        button("Food web  (F)", lambda: setattr(self, "foodweb_view", foodweb.FoodWebView(self)), (px, y, bw, 26),
               font=f.b)
        button("Class report  (R)", lambda: setattr(self, "report_view", report.ReportView(self)),
               (px + bw + 6, y, bw, 26), font=f.b)
        y += 32
        button("History  (Y)", lambda: setattr(self, "history_view", views.HistoryView(self)), (px, y, bw, 24))
        button("Pie charts  (P)", lambda: setattr(self, "makeup_view", True), (px + bw + 6, y, bw, 24))
        y += 34
        pygame.draw.line(s, LINE, (px, y - 4), (px + pw, y - 4))
        draw_text(s, f, "DIFFICULTY", (px, y + 2), ACCENT, f.b)
        y += 24
        bw3 = (pw - 12) // 3
        for i, k in enumerate(DIFFICULTY_ORDER):
            button(DIFFICULTIES[k]["label"], lambda k=k: self.set_difficulty(k), (px + i * (bw3 + 6), y, bw3, 24),
                   toggled=lambda k=k: w.difficulty == k)
        y += 30
        for ln in wrap(DIFFICULTIES[w.difficulty]["blurb"], f.xs, pw):
            draw_text(s, f, ln, (px, y), DIM, f.xs)
            y += 14
        y += 8
        pygame.draw.line(s, LINE, (px, y - 2), (px + pw, y - 2))
        draw_text(s, f, "TIME", (px, y + 4), ACCENT, f.b)
        y += 24
        for ln in wrap("The calendar is real, but life runs %dx faster: each calendar year, every animal and "
                       "person lives about %d years of its life. Lifespans, litter sizes and breeding rates come "
                       "from real NZ data, so species keep their true pace relative to each other."
                       % (LIFE_SPEED, LIFE_SPEED), f.xs, pw):
            if y > LH - 20:
                break
            draw_text(s, f, ln, (px, y), DIM, f.xs)
            y += 14

    def draw_species_list(self, s, px, pw, top, bottom):
        w = self.world
        mouse = self.mouse
        rows = []
        for title, fn in GROUPS:
            items = fn(w)
            if not items:
                continue
            rows.append(("head", title))
            for i in range(0, len(items), 2):
                rows.append(("pair", items[i:i + 2]))
        rh = 22
        vis = (bottom - top) // rh
        self.list_scroll = max(0, min(self.list_scroll, len(rows) - vis))
        colw = (pw - 6) // 2
        hover_sp = None
        y = top
        for kind, data in rows[self.list_scroll:self.list_scroll + vis]:
            if kind == "head":
                draw_text(s, self.fonts, data, (px, y + 6), DIM, self.fonts.xs)
            else:
                for j, sp in enumerate(data):
                    r = pygame.Rect(px + j * (colw + 6), y, colw, rh - 2)
                    on = self.selected is sp
                    hov = r.collidepoint(mouse)
                    pygame.draw.rect(s, SEL if on else (HOVER if hov else PANEL2), r, border_radius=4)
                    if on:
                        pygame.draw.rect(s, ACCENT, r, 1, border_radius=4)
                    pygame.draw.circle(s, sp.color, (r.x + 10, r.centery), 5)
                    cnt, cc = self.count_text(sp)
                    cw = self.fonts.xs.size(cnt)[0]
                    draw_text(s, self.fonts, sp.name, (r.x + 19, r.centery), TEXT, anchor="midleft",
                              maxw=colw - 26 - cw)
                    draw_text(s, self.fonts, cnt, (r.right - 5, r.centery), cc, self.fonts.xs, anchor="midright")
                    self.clickables.append((r, lambda sp=sp: self.toggle_select(sp)))
                    if hov:
                        hover_sp = sp
            y += rh
        if len(rows) > vis:
            draw_text(s, self.fonts, "scroll for more", (px + pw, bottom - 2), DIM, self.fonts.xs, anchor="topright")
        if hover_sp is not None:
            self.draw_species_tip(s, hover_sp, mouse)

    def toggle_select(self, sp):
        if self.selected is sp:
            self.set_tool("inspect")
        else:
            self.select_species(sp)

    def count_text(self, sp):
        w = self.world
        if sp.kind == "animal":
            n = w.counts.get(sp, 0)
            return str(n), DIM if n else (200, 100, 100)
        if sp.kind == "plant":
            i = w.plant_species.index(sp)
            n = int(w.plant_counts[i]) if i < len(w.plant_counts) else 0
            return "%.1f%%" % (100 * n / max(1, int(w.land.sum()))), DIM if n else (200, 100, 100)
        if sp.kind == "fungus":
            return "%d%%" % (100 * (w.fungus[w.land] > 0.1).mean()), DIM
        if sp.kind == "human":
            return str(len(w.people)), DIM
        return "%d%%" % (100 * w.microbes[w.land].mean()), DIM

    def overlay_tip(self, i, rect):
        title, text, stops, lo, hi = OVERLAY_INFO[i]
        anchor = self.canon_to_disp((rect.x, rect.y))
        above = self.ui.get("bar", "bottom") == "bottom"
        self.post.append(lambda surf: self._overlay_tip(surf, title, text, stops, lo, hi, anchor, above, i))

    def _overlay_tip(self, s, title, text, stops, lo, hi, anchor, above, i):
        f = self.fonts
        W = 330
        lines = wrap(text, f.s, W - 20)
        h = 30 + len(lines) * 16 + (34 if stops else 0) + 18
        x = min(max(4, anchor[0] - 20), LW - W - 4)
        y = anchor[1] - h - 6 if above else anchor[1] + 28
        r = pygame.Rect(x, y, W, h)
        pygame.draw.rect(s, TIP, r, border_radius=6)
        pygame.draw.rect(s, ACCENT, r, 1, border_radius=6)
        draw_text(s, f, title, (r.x + 10, r.y + 8), ACCENT, f.b)
        yy = r.y + 28
        for ln in lines:
            draw_text(s, f, ln, (r.x + 10, yy), TEXT)
            yy += 16
        if stops:
            self.legend_bar(s, r.x + 10, yy + 8, W - 20, stops, lo, hi)
            yy += 34
        draw_text(s, f, "Key %d" % (i + 1), (r.right - 10, r.bottom - 16), DIM, f.xs, "topright")

    def legend_bar(self, s, x, y, w, stops, lo, hi):
        for k in range(w):
            t = k / max(1, w - 1)
            for j in range(len(stops) - 1):
                p0, c0 = stops[j]
                p1, c1 = stops[j + 1]
                if p0 <= t <= p1:
                    u = (t - p0) / max(1e-6, p1 - p0)
                    col = tuple(int(c0[c] * (1 - u) + c1[c] * u) for c in range(3))
                    pygame.draw.line(s, col, (x + k, y), (x + k, y + 9))
                    break
        pygame.draw.rect(s, LINE, (x, y, w, 10), 1)
        draw_text(s, self.fonts, lo, (x, y + 12), DIM, self.fonts.xs)
        draw_text(s, self.fonts, hi, (x + w, y + 12), DIM, self.fonts.xs, "topright")

    def tip(self, s, text, mouse):
        dm = self.canon_to_disp(mouse)
        self.post.append(lambda surf: self._tip(surf, text, dm))

    def _tip(self, s, text, mouse):
        img = self.fonts.render(self.fonts.s, text, TEXT)
        r = img.get_rect()
        r.inflate_ip(14, 8)
        r.topright = (mouse[0] - 10, mouse[1] + 14)
        if r.x < 0:
            r.x = 4
        pygame.draw.rect(s, TIP, r, border_radius=4)
        pygame.draw.rect(s, LINE, r, 1, border_radius=4)
        s.blit(img, img.get_rect(center=r.center))

    def draw_species_tip(self, s, sp, mouse):
        dm = self.canon_to_disp(mouse)
        self.post.append(lambda surf: self._species_tip(surf, sp, dm))

    def _species_tip(self, s, sp, mouse):
        w = self.world
        f = self.fonts
        head = sp.name
        sub = ""
        if getattr(sp, "english", "") and sp.english != sp.name:
            sub = sp.english
        if getattr(sp, "latin", ""):
            sub = (sub + "  -  " if sub else "") + sp.latin
        lines = [(head, sp.color, f.b)]
        if sub:
            lines.append((sub, DIM, f.xs))
        if sp.kind in ("animal", "plant"):
            lines.append(("Native to Aotearoa" if sp.native else "Introduced species",
                          (140, 210, 200) if sp.native else (240, 150, 120), f.xs))
        for ln in wrap(getattr(sp, "blurb", ""), f.s, 280):
            lines.append((ln, TEXT, f.s))
        if sp.kind == "animal":
            act = {"day": "active by day", "night": "nocturnal", "any": "active day and night"}[sp.activity]
            lines.append(("eats %s; %s%s" % (", ".join(sorted(sp.diet)), act, ", flies" if sp.flier else ""), DIM, f.xs))
            m = w.species_mean(sp)
            if m:
                lines.append(("avg size %+d%%, speed %+d%%, newest generation %d" % (
                    100 * (m[0] / sp.size - 1), 100 * (m[1] / sp.speed - 1), m[2]), DIM, f.xs))
        lines.append(("Click to select, then click the map to add.", ACCENT, f.xs))
        bw = max(fn.size(t)[0] for t, _, fn in lines) + 20
        bh = sum(fn.get_linesize() for _, _, fn in lines) + 12
        r = pygame.Rect(0, 0, bw, bh)
        if mouse[0] > LW // 2:
            r.topright = (mouse[0] - 14, mouse[1] - 10)
        else:
            r.topleft = (mouse[0] + 14, mouse[1] - 10)
        r.y = max(4, min(r.y, LH - bh - 4))
        r.x = max(4, r.x)
        pygame.draw.rect(s, TIP, r, border_radius=5)
        pygame.draw.rect(s, LINE, r, 1, border_radius=5)
        y = r.y + 6
        for t, c, fn in lines:
            draw_text(s, f, t, (r.x + 10, y), c, fn)
            y += fn.get_linesize()

    # --------------------------------------------------------------- bottom
    def makeup_data(self):
        w = self.world
        animals = [(w.counts.get(sp, 0), sp.color, sp.name, sp.native) for sp in w.animal_species]
        if w.people:
            animals.append((len(w.people), w.human_entry.color, "Humans", None))
        animals = sorted([a for a in animals if a[0] > 0], key=lambda a: -a[0])
        plants = []
        for i, sp in enumerate(w.plant_species):
            n = int(w.plant_counts[i]) if i < len(w.plant_counts) else 0
            if n:
                plants.append((n, sp.color, sp.name, sp.native))
        land = w.land & (w.water < 0.3)
        built = int(((w.struct == HOUSE) | (w.struct == FIELD))[land].sum())
        bare = max(0, int(land.sum()) - sum(p[0] for p in plants) - built)
        plants = sorted(plants, key=lambda a: -a[0])
        if built:
            plants.append((built, (200, 170, 100), "Farms & houses", None))
        plants.append((bare, (110, 96, 80), "Bare ground", None))
        tribes = sorted([(t.pop, t.color, t.name, None) for t in w.tribes if t.alive and t.pop > 0],
                        key=lambda a: -a[0])
        return animals, plants, tribes

    def draw_bottom(self, s):
        w = self.world
        y0 = VIEW_H
        pygame.draw.rect(s, BOTTOM, (0, y0, VIEW_W, BOTTOM_H))
        pygame.draw.line(s, LINE, (0, y0), (VIEW_W, y0))
        bx = 10
        for i, b in enumerate(self.overlay_buttons):
            r = (bx + i * 56, y0 + 5, 54, 21)
            hov = pygame.Rect(r).collidepoint(self.mouse)
            b.draw(s, self.fonts, r, hov, self.fonts.xs)
            if hov and not self.modal_open():
                self.overlay_tip(i, pygame.Rect(r))
        # graph tabs (right of view buttons)
        gx = 10 + 8 * 56 + 3
        for i, b in enumerate(self.graph_buttons):
            r = (gx + i * 53, y0 + 5, 51, 21)
            b.draw(s, self.fonts, r, pygame.Rect(r).collidepoint(self.mouse), self.fonts.xs)
        g = pygame.Rect(10, y0 + 32, 610, BOTTOM_H - 40)
        pygame.draw.rect(s, GRAPH, g, border_radius=4)
        if self.graph_tab == "makeup":
            self.draw_makeup_small(s, g)
        else:
            self.draw_trends(s, g)
        # right column: alerts / chronicle
        lx = 632
        lw = VIEW_W - lx - 10
        unread = sum(1 for a in w.alerts if not a["read"])
        self.bottom_buttons[0].label = "Alerts (%d new)" % unread if unread else "Alerts"
        for i, b in enumerate(self.bottom_buttons):
            r = (lx + i * 104, y0 + 5, 100, 21)
            b.draw(s, self.fonts, r, pygame.Rect(r).collidepoint(self.mouse), self.fonts.xs)
        draw_text(s, self.fonts, "%d animals  %d people" % (len(w.animals), len(w.people)), (lx + lw, y0 + 8),
                  DIM, self.fonts.xs, anchor="topright")
        yy = y0 + 32
        nrows = 7
        if self.bottom_tab == "alerts":
            items = w.alerts[::-1]
            self.log_scroll = max(0, min(self.log_scroll, max(0, len(items) - nrows)))
            if not items:
                draw_text(s, self.fonts, "No alerts yet. They'll appear here when something", (lx, yy), DIM)
                draw_text(s, self.fonts, "important happens to your ecosystem.", (lx, yy + 16), DIM)
            for i, a in enumerate(items[self.log_scroll:self.log_scroll + nrows]):
                r = pygame.Rect(lx - 4, yy + i * 17 - 1, lw + 8, 17)
                hov = r.collidepoint(self.mouse)
                if hov:
                    pygame.draw.rect(s, PANEL2, r, border_radius=3)
                col = SEV_COLORS[a["sev"]]
                pygame.draw.circle(s, col, (lx + 4, r.centery), 4 if not a["read"] else 2)
                draw_text(s, self.fonts, a.get("date", "D%d" % a["day"]), (lx + 12, r.y + 1), DIM, self.fonts.xs)
                draw_text(s, self.fonts, a["title"], (lx + 72, r.y), TEXT if not a["read"] else DIM, maxw=lw - 74)
                self.clickables.append((r, lambda a=a: self.open_alert(a)))
        else:
            evs = w.events[::-1]
            self.log_scroll = max(0, min(self.log_scroll, max(0, len(evs) - nrows)))
            for i, (d, t, c) in enumerate(evs[self.log_scroll:self.log_scroll + nrows]):
                yyy = yy + i * 17
                draw_text(s, self.fonts, d, (lx, yyy), DIM, self.fonts.xs)
                draw_text(s, self.fonts, t, (lx + 64, yyy), c, maxw=lw - 64)

    def draw_trends(self, s, g):
        w = self.world
        hist = w.history
        if len(hist) <= 2:
            draw_text(s, self.fonts, "Population history will appear here...", g.center, DIM, anchor="center")
            return
        N = 360
        step = g.w / (N - 1)
        start = g.x + g.w - (len(hist) - 1) * step
        amax = max(10, max((max(h["animals"]) if h["animals"] else 0) for h in hist),
                   max(h.get("people", 0) for h in hist))
        pmax = max(0.05, max((max(h["plants"]) if h["plants"] else 0) for h in hist))
        for i in range(1, 4):
            yy = g.bottom - g.h * i / 4
            pygame.draw.line(s, GRID, (g.x, yy), (g.right, yy))
        for k, sp in enumerate(w.plant_species):
            pts = [(start + j * step, g.bottom - 2 - (g.h - 6) * (h["plants"][k] / pmax if k < len(h["plants"]) else 0))
                   for j, h in enumerate(hist)]
            pygame.draw.lines(s, tuple(int(v * 0.75) for v in sp.color), False, pts, 1)
        for k, sp in enumerate(w.animal_species):
            if not any((h["animals"][k] if k < len(h["animals"]) else 0) for h in hist):
                continue
            pts = [(start + j * step, g.bottom - 2 - (g.h - 6) * (h["animals"][k] / amax if k < len(h["animals"]) else 0))
                   for j, h in enumerate(hist)]
            pygame.draw.lines(s, sp.color, False, pts, 2 if sp.native else 1)
        fpts = [(start + j * step, g.bottom - 2 - (g.h - 6) * h.get("fish", 0)) for j, h in enumerate(hist)]
        for j in range(0, len(fpts) - 1, 2):
            pygame.draw.line(s, (100, 190, 255), fpts[j], fpts[j + 1], 1)
        if any(h.get("people", 0) for h in hist):
            pts = [(start + j * step, g.bottom - 2 - (g.h - 6) * h.get("people", 0) / amax) for j, h in enumerate(hist)]
            pygame.draw.lines(s, w.human_entry.color, False, pts, 3)
        draw_text(s, self.fonts, "max %d" % amax, (g.x + 4, g.y + 2), DIM, self.fonts.xs)
        draw_text(s, self.fonts, "animals & people (thick), plant cover (thin), fish (dotted blue) - last %s" %
                  age_text(len(hist) * 20), (g.right - 6, g.y + 2), DIM, self.fonts.xs, anchor="topright")

    def legend(self, s, x, y, items, maxrows, total, colw=170):
        f = self.fonts
        rows = items[:maxrows]
        rest = sum(i[0] for i in items[maxrows:])
        for k, it in enumerate(rows):
            n, c, name = it[0], it[1], it[2]
            yy = y + k * 15
            pygame.draw.rect(s, c, (x, yy + 3, 9, 9))
            draw_text(s, f, name, (x + 14, yy), TEXT, f.xs, maxw=colw - 60)
            draw_text(s, f, "%d%%" % round(100 * n / max(1, total)), (x + colw - 6, yy), DIM, f.xs, anchor="topright")
        if rest:
            yy = y + len(rows) * 15
            draw_text(s, f, "+ others %d%%" % round(100 * rest / max(1, total)), (x + 14, yy), DIM, f.xs)

    def draw_makeup_small(self, s, g):
        animals, plants, tribes = self.makeup_data()
        r = (g.h - 14) // 2 - 8
        cy = g.y + 7 + (g.h - 14) // 2
        cols = [("Fauna", animals), ("Land", plants), ("Clans", tribes)]
        cw = g.w // 3
        for i, (lab, items) in enumerate(cols):
            x = g.x + i * cw
            tot = sum(a[0] for a in items)
            if lab == "Clans" and not items:
                draw_pie(s, (x + 10 + r, cy), r, [], hole=0.45)
                draw_text(s, self.fonts, "Clans", (x + 10 + r, cy), DIM, self.fonts.xs, "center")
                draw_text(s, self.fonts, "no people yet", (x + 20 + 2 * r, cy - 6), DIM, self.fonts.xs)
                continue
            draw_pie(s, (x + 10 + r, cy), r, [(a[0], a[1]) for a in items], hole=0.45)
            draw_text(s, self.fonts, lab, (x + 10 + r, cy), TEXT, self.fonts.xs, "center")
            self.legend(s, x + 18 + 2 * r, g.y + 6, [(a[0], a[1], a[2].split()[0] if lab == "Clans" else a[2])
                                                    for a in items], 6, tot, colw=cw - 2 * r - 22)

    def draw_makeup_modal(self, s):
        shade = pygame.Surface((LW, LH), pygame.SRCALPHA)
        shade.fill((0, 0, 0, 170))
        s.blit(shade, (0, 0))
        R = pygame.Rect(0, 0, 1180, 600)
        R.center = (LW // 2, LH // 2)
        pygame.draw.rect(s, PANEL, R, border_radius=10)
        pygame.draw.rect(s, LINE, R, 1, border_radius=10)
        f = self.fonts
        w = self.world
        draw_text(s, f, "Ecosystem make-up  -  %s" % w.date, (R.x + 26, R.y + 18), TEXT, f.l)
        animals, plants, tribes = self.makeup_data()
        r = 105

        def block(cx, items, title, sub, legx, colw, ring):
            c = (cx, R.y + 80 + r)
            if ring:
                draw_pie(s, c, r + 12, ring, hole=0.92)
            draw_pie(s, c, r, [(a[0], a[1]) for a in items], hole=0.42)
            draw_text(s, f, title, c, TEXT, f.b, "center")
            draw_text(s, f, sub, (c[0], c[1] + 18), DIM, f.xs, "center")
            self.legend(s, legx, R.y + 60 + 2 * r + 40, items, 9, sum(a[0] for a in items), colw=colw)

        nat = sum(a[0] for a in animals if a[3] is True)
        intro = sum(a[0] for a in animals if a[3] is False)
        ppl = sum(a[0] for a in animals if a[3] is None)
        block(R.x + 40 + r, animals, "Fauna", "%d animals" % (nat + intro), R.x + 40, 220,
              [(nat, (90, 170, 140)), (intro, (220, 110, 80)), (ppl, (235, 200, 160))])
        pn = sum(p[0] for p in plants if p[3] is True)
        pi = sum(p[0] for p in plants if p[3] is False)
        po = sum(p[0] for p in plants if p[3] is None)
        block(R.x + 330 + r, plants, "Land cover", "", R.x + 330, 220,
              [(pn, (90, 170, 140)), (pi, (220, 110, 80)), (po, (120, 110, 100))])
        if tribes:
            block(R.x + 620 + r, [(a[0], a[1], a[2], None) for a in tribes], "Clans", "%d people" % len(w.people),
                  R.x + 620, 220, None)
        else:
            draw_pie(s, (R.x + 620 + r, R.y + 80 + r), r, [], hole=0.42)
            draw_text(s, f, "No people yet", (R.x + 620 + r, R.y + 80 + r), DIM, f.s, "center")
        # ocean
        ox = R.x + 900
        draw_text(s, f, "Ocean", (ox, R.y + 70), ACCENT, f.l)
        sea = w.sea
        rows = [("Fish stock", float(w.fish[sea].mean()) if sea.any() else 0, (100, 190, 255)),
                ("Shellfish beds", float(w.shellfish[w.shallow].mean()) if w.shallow.any() else 0, (230, 170, 80)),
                ("Plankton", float(w.plankton[sea].mean()) if sea.any() else 0, (120, 220, 150)),
                ("Mud (sediment)", min(1.0, float(w.sediment[w.shallow].mean()) * 5) if w.shallow.any() else 0,
                 (160, 120, 80))]
        y = R.y + 110
        for lab, v, c in rows:
            draw_text(s, f, lab, (ox, y), TEXT)
            draw_text(s, f, "%d%%" % (v * 100), (ox + 240, y), DIM, anchor="topright")
            bar = pygame.Rect(ox, y + 18, 240, 8)
            pygame.draw.rect(s, LINE, bar, border_radius=4)
            fb = bar.copy()
            fb.w = int(bar.w * min(1, v))
            pygame.draw.rect(s, c, fb, border_radius=4)
            y += 42
        sealife = [(w.counts.get(sp, 0), sp.name) for sp in w.animal_species if getattr(sp, "marine", False)]
        for n, name in sealife:
            draw_text(s, f, "%s: %d" % (name, n), (ox, y), TEXT)
            y += 18
        draw_text(s, f, "Fish caught by people recently: %.0f" % w.fish_caught_recent, (ox, y + 6), DIM, f.xs)
        ky = R.bottom - 54
        for i, (lab, c) in enumerate([("native", (90, 170, 140)), ("introduced", (220, 110, 80)),
                                      ("people / built / bare", (235, 200, 160))]):
            pygame.draw.rect(s, c, (R.x + 30 + i * 170, ky + 4, 22, 6))
            draw_text(s, f, "outer ring: " + lab if i == 0 else lab, (R.x + 58 + i * 170, ky), DIM, f.xs)
        tot = nat + intro
        msg = ("Native animals make up %d%% of the fauna." % (100 * nat / tot)) if tot else "No animals left."
        draw_text(s, f, msg, (R.x + 600, ky - 2), TEXT, f.m)
        draw_text(s, f, "click anywhere to close", (R.centerx, R.bottom - 18), DIM, f.xs, "center")

    def draw_help(self, s):
        shade = pygame.Surface((LW, LH), pygame.SRCALPHA)
        shade.fill((0, 0, 0, 170))
        s.blit(shade, (0, 0))
        r = pygame.Rect(0, 0, 720, 500)
        r.center = (LW // 2, LH // 2)
        pygame.draw.rect(s, PANEL, r, border_radius=10)
        pygame.draw.rect(s, LINE, r, 1, border_radius=10)
        y = r.y + 20
        for i, (a, b) in enumerate(HELP):
            if i == 0:
                draw_text(s, self.fonts, a, (r.x + 28, y), TEXT, self.fonts.xl)
                y += 40
                continue
            if b is None:
                draw_text(s, self.fonts, a, (r.x + 28, y), DIM if i > 2 else TEXT, self.fonts.m)
            else:
                draw_text(s, self.fonts, a, (r.x + 28, y), ACCENT, self.fonts.b)
                draw_text(s, self.fonts, b, (r.x + 190, y), TEXT, self.fonts.s)
            y += 22 if b is None else 21
        draw_text(s, self.fonts, "click or press any key to begin", (r.centerx, r.bottom - 22), DIM, anchor="center")

    def draw_away(self, s):
        shade = pygame.Surface((LW, LH), pygame.SRCALPHA)
        shade.fill((0, 0, 0, 170))
        s.blit(shade, (0, 0))
        a = self.away
        n = len(a["lines"]) + len(a["alerts"])
        r = pygame.Rect(0, 0, 600, 160 + n * 20)
        r.center = (LW // 2, LH // 2)
        pygame.draw.rect(s, PANEL, r, border_radius=10)
        pygame.draw.rect(s, LINE, r, 1, border_radius=10)
        draw_text(s, self.fonts, "Welcome back", (r.x + 26, r.y + 18), TEXT, self.fonts.xl)
        y = r.y + 64
        for ln in a["lines"]:
            draw_text(s, self.fonts, ln, (r.x + 26, y), TEXT, self.fonts.m, maxw=r.w - 52)
            y += 20
        v0, v1 = a["vit"]
        draw_text(s, self.fonts, "Vitality %d -> %d  (%s)" % (v0, v1, self.world.mood), (r.x + 26, y),
                  ACCENT if v1 >= v0 else WARN, self.fonts.b)
        y += 26
        for al in a["alerts"]:
            rr = pygame.Rect(r.x + 20, y - 1, r.w - 40, 19)
            if rr.collidepoint(self.mouse):
                pygame.draw.rect(s, PANEL2, rr, border_radius=3)
            col = SEV_COLORS[al["sev"]]
            pygame.draw.circle(s, col, (r.x + 30, y + 8), 4)
            draw_text(s, self.fonts, "%s  %s" % (al.get("date", ""), al["title"]), (r.x + 40, y), col, maxw=r.w - 70)
            self.clickables.append((rr, lambda al=al: self.open_alert(al)))
            y += 20
        draw_text(s, self.fonts, "click an alert to read it, or anywhere to continue", (r.centerx, r.bottom - 22),
                  DIM, anchor="center")


def main():
    App().run()


if __name__ == "__main__":
    main()
