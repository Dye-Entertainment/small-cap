#!/usr/bin/env python3
"""Procedurally draws all of Small Cap's original pixel art.

Usage: make_art.py <out_dir>
Writes:
  tiles.png / tileset.json    16x16 tileset (16 columns) + name->id and per-tile properties
  sprites.png / sprites.json  packed sprite atlas with a pivot per sprite
"""
import json
import math
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pixel import Canvas, mix, write_png  # noqa: E402

T = 16
OUT = (28, 20, 36)
WHITE = (255, 255, 255)
BLACK = (20, 14, 26)

# ---------------------------------------------------------------------------------------------
# Palettes
# ---------------------------------------------------------------------------------------------
GRASS = (112, 196, 80)
GRASS_D = (80, 160, 64)
GRASS_DD = (56, 126, 52)
GRASS_L = (160, 220, 104)
DIRT = (220, 184, 120)
DIRT_D = (188, 146, 92)
DIRT_L = (236, 206, 150)
WATER = (72, 144, 232)
WATER_D = (48, 104, 200)
WATER_L = (152, 204, 248)
FOAM = (226, 242, 255)
SAND = (224, 204, 140)
LEAF = (60, 146, 70)
LEAF_D = (36, 100, 52)
LEAF_L = (112, 190, 92)
BARK = (128, 86, 52)
BARK_D = (86, 56, 34)
BARK_L = (164, 118, 76)
STONE = (168, 168, 176)
STONE_D = (110, 110, 126)
STONE_L = (212, 212, 220)
ROOF = (204, 76, 58)
ROOF_D = (148, 50, 42)
ROOF_L = (236, 124, 90)
WALL = (242, 226, 180)
WALL_D = (204, 180, 132)
BEAM = (124, 82, 50)
GLASS = (104, 168, 228)
GLASS_L = (184, 224, 252)
WOOD = (188, 132, 76)
WOOD_D = (126, 84, 50)
WOOD_L = (220, 168, 108)
PLAZA = (206, 196, 178)
PLAZA_D = (164, 154, 140)
PLAZA_L = (228, 220, 204)
SOIL = (172, 124, 78)
SOIL_D = (140, 98, 60)
SOIL_L = (198, 152, 104)
BLADE = (96, 182, 70)
BLADE_D = (60, 132, 52)
BLADE_L = (156, 220, 104)
DFLOOR = (128, 110, 92)
DFLOOR_D = (100, 86, 74)
DFLOOR_L = (152, 134, 112)
DWALL = (92, 74, 66)
DWALL_D = (60, 48, 46)
DWALL_L = (140, 118, 98)
GOLD = (248, 208, 64)
GOLD_D = (196, 140, 36)
GOLD_L = (255, 244, 168)
SKIN = (248, 204, 152)
SKIN_D = (220, 150, 104)
RED = (224, 56, 56)
RED_D = (152, 32, 40)
RED_L = (255, 140, 130)

# ---------------------------------------------------------------------------------------------
# Tiles
# ---------------------------------------------------------------------------------------------
tiles = []          # list of (name, Canvas)
tile_props = {}     # name -> dict


def add_tile(name, canvas, **props):
    tiles.append((name, canvas))
    if props:
        tile_props[name] = props


def noise_rng(name):
    return random.Random(hash(name) & 0xFFFFFFFF)


def grass_tile(seed, flowers=None):
    c = Canvas(T, T)
    c.rect(0, 0, T, T, GRASS)
    r = random.Random(seed)
    for _ in range(9):
        x, y = r.randrange(0, 15), r.randrange(1, 16)
        c.put(x, y, GRASS_D)
        c.put(x + 1, y - 1, GRASS_D)
        c.put(x + 2, y, GRASS_D)
    for _ in range(4):
        c.put(r.randrange(16), r.randrange(16), GRASS_L)
    if flowers:
        for fx, fy in ((3, 3), (11, 5), (6, 11), (13, 13)):
            c.put(fx, fy, flowers)
            c.put(fx - 1, fy, flowers)
            c.put(fx + 1, fy, flowers)
            c.put(fx, fy - 1, flowers)
            c.put(fx, fy + 1, flowers)
            c.put(fx, fy, (255, 240, 120) if flowers != (255, 240, 120) else (240, 140, 60))
            c.put(fx, fy + 2, GRASS_DD)
    return c


def autotile_mask_inside(x, y, mask, border, r=5.0, jitter=None):
    """True if pixel (x,y) is inside the terrain blob for a 4-neighbour mask (N=1,E=2,S=4,W=8)."""
    n, e, s, w = mask & 1, mask & 2, mask & 4, mask & 8
    j = jitter(x, y) if jitter else 0
    b = border + j
    if not n and y < b:
        return False
    if not s and y > 15 - b:
        return False
    if not w and x < b:
        return False
    if not e and x > 15 - b:
        return False
    # Round outer corners.
    for cx_missing, cy_missing, cx, cy in (
        (not w, not n, b + r, b + r), (not e, not n, 15 - b - r, b + r),
        (not w, not s, b + r, 15 - b - r), (not e, not s, 15 - b - r, 15 - b - r)
    ):
        if cx_missing and cy_missing:
            inx = (x < cx) if cx < 8 else (x > cx)
            iny = (y < cy) if cy < 8 else (y > cy)
            if inx and iny and math.hypot(x - cx, y - cy) > r:
                return False
    return True


def terrain_tile(base, mask, fill_fn, edge, border=2, seed=0, r=4.0):
    c = base.copy()
    rr = random.Random(seed * 31 + mask)
    jit = {}

    def jitter(x, y):
        key = (x // 4, y // 4)
        if key not in jit:
            jit[key] = rr.choice((0, 0, 1))
        return jit[key]

    inside = [[autotile_mask_inside(x, y, mask, border, r, jitter) for x in range(T)] for y in range(T)]
    for y in range(T):
        for x in range(T):
            if not inside[y][x]:
                continue
            boundary = False
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                xx, yy = x + dx, y + dy
                if 0 <= xx < T and 0 <= yy < T and not inside[yy][xx]:
                    boundary = True
            c.put(x, y, edge if boundary else fill_fn(x, y))
    return c


def dirt_fill(seed):
    r = random.Random(seed)
    spots = {(r.randrange(16), r.randrange(16)) for _ in range(7)}
    lights = {(r.randrange(16), r.randrange(16)) for _ in range(4)}

    def f(x, y):
        if (x, y) in spots:
            return DIRT_D
        if (x, y) in lights:
            return DIRT_L
        return DIRT
    return f


def water_fill(frame):
    def f(x, y):
        wave = (x + frame * 4 + (y // 4) * 6) % 16
        if y % 4 == 1 and wave in (2, 3, 4):
            return WATER_L
        if y % 4 == 3 and wave in (10, 11):
            return WATER_D
        return WATER
    return f


def soil_tile(seed, pebbles=True):
    c = Canvas(T, T)
    c.rect(0, 0, T, T, SOIL)
    r = random.Random(seed)
    for _ in range(10):
        c.put(r.randrange(16), r.randrange(16), SOIL_D)
    for _ in range(5):
        c.put(r.randrange(16), r.randrange(16), SOIL_L)
    if pebbles:
        for _ in range(2):
            x, y = r.randrange(2, 13), r.randrange(2, 13)
            c.rect(x, y, 2, 2, (196, 188, 172))
            c.put(x + 1, y + 1, (150, 140, 128))
    return c


def make_tiles():
    empty = Canvas(T, T)
    add_tile("empty", empty)

    # -- overworld ground ----------------------------------------------------------------------
    g = [grass_tile(s) for s in (1, 2, 3)]
    add_tile("grass", g[0])
    add_tile("grass2", g[1])
    add_tile("grass3", g[2])
    add_tile("flowers_r", grass_tile(4, (236, 88, 96)))
    add_tile("flowers_y", grass_tile(5, (255, 240, 120)))
    add_tile("flowers_w", grass_tile(6, (250, 250, 250)))

    for m in range(16):
        add_tile("dirt_%d" % m, terrain_tile(g[0], m, dirt_fill(m), DIRT_D, border=2, seed=m))
    for frame in range(2):
        for m in range(16):
            t = terrain_tile(g[m % 3], m, lambda x, y: SAND, SAND, border=1, seed=m + 20, r=3.0)
            t = terrain_tile(t, m, water_fill(frame), (196, 228, 252), border=3, seed=m + 40)
            add_tile("water_%d_%d" % (m, frame), t, solid=True, water=True,
                     anim=("water_%d_1" % m) if frame == 0 else None)

    # plaza stone
    c = Canvas(T, T)
    c.rect(0, 0, T, T, PLAZA)
    for (x, y, w, h) in ((0, 0, 8, 8), (8, 0, 8, 8), (0, 8, 8, 8), (8, 8, 8, 8)):
        c.hline(x, x + w - 1, y + h - 1, PLAZA_D)
        c.vline(x + w - 1, y, y + h - 1, PLAZA_D)
        c.hline(x, x + w - 2, y, PLAZA_L)
    add_tile("plaza", c)

    # big tree: 2x2 (canopy + trunk)
    tree = Canvas(32, 32)
    tree.rect(12, 20, 8, 11, BARK)
    tree.rect(12, 20, 2, 11, BARK_L)
    tree.rect(18, 20, 2, 11, BARK_D)
    tree.hline(10, 21, 30, BARK_D)
    tree.put(10, 29, BARK)
    tree.put(21, 29, BARK)
    tree.ell(16, 13, 15, 12.5, LEAF, LEAF_D, None, shade_at=0.35)
    r = random.Random(7)
    for _ in range(40):
        x, y = r.randrange(3, 29), r.randrange(2, 23)
        if tree.get(x, y) == LEAF:
            tree.put(x, y, LEAF_L if y < 12 else LEAF_D)
    for (cx, cy, rr) in ((9, 9, 4), (20, 7, 4.5), (14, 15, 3.5), (23, 15, 3)):
        tree.ell(cx, cy, rr, rr * 0.8, LEAF, LEAF_D, LEAF_L, shade_at=0.4,
                 light_at=(-0.3, -0.4, 0.35))
    tree.outline(OUT)
    full = Canvas(32, 32)
    full.rect(0, 0, 32, 32, GRASS)
    full.blit(grass_tile(8), 0, 0)
    full.blit(grass_tile(9), 16, 0)
    full.blit(grass_tile(10), 0, 16)
    full.blit(grass_tile(11), 16, 16)
    # shadow under the tree
    full.ell(16, 29, 12, 3, GRASS_DD)
    full.blit(tree, 0, 0)
    for i, n in enumerate(("tree_tl", "tree_tr", "tree_bl", "tree_br")):
        t = Canvas(T, T)
        ox, oy = (i % 2) * 16, (i // 2) * 16
        for y in range(T):
            for x in range(T):
                t.put(x, y, full.get(ox + x, oy + y))
        add_tile(n, t, solid=True)

    # small round bush-tree (1x1 solid shrub, not cuttable)
    c = grass_tile(12)
    s = Canvas(T, T)
    s.ell(8, 8, 7, 6.5, LEAF, LEAF_D, LEAF_L)
    s.outline(OUT)
    c.blit(s, 0, 0)
    add_tile("shrub", c, solid=True)

    # boulder
    c = grass_tile(13)
    s = Canvas(T, T)
    s.ell(8, 9, 7, 6, STONE, STONE_D, STONE_L)
    s.line(5, 8, 8, 10, STONE_D)
    s.outline(OUT)
    c.blit(s, 0, 0)
    add_tile("rock", c, solid=True)

    # fence
    c = grass_tile(14)
    c.rect(0, 5, 16, 3, WOOD)
    c.hline(0, 15, 5, WOOD_L)
    c.hline(0, 15, 8, WOOD_D)
    c.rect(0, 10, 16, 2, WOOD)
    c.hline(0, 15, 12, WOOD_D)
    for px in (2, 12):
        c.rect(px, 2, 3, 12, WOOD)
        c.vline(px, 2, 13, WOOD_L)
        c.vline(px + 2, 2, 13, WOOD_D)
        c.hline(px, px + 2, 14, OUT)
        c.hline(px, px + 2, 1, OUT)
    add_tile("fence", c, solid=True)

    # shrink stump: 2x2 walkable platform
    st = Canvas(32, 32)
    st.blit(grass_tile(15), 0, 0)
    st.blit(grass_tile(16), 16, 0)
    st.blit(grass_tile(17), 0, 16)
    st.blit(grass_tile(18), 16, 16)
    stump = Canvas(32, 32)
    stump.ell(16, 20, 15, 10, BARK, BARK_D)
    stump.rect(1, 16, 30, 6, BARK)
    stump.ell(16, 14, 15, 10, (214, 176, 120), (196, 156, 104))
    for rr in (3, 6, 9, 12):
        stump.ring(16, 14 + 0, rr * 1.15, rr * 1.15 + 0.7, (176, 132, 84))
    # glowing rune
    for (x, y) in ((16, 9), (16, 10), (14, 12), (18, 12), (16, 14), (16, 15), (13, 15), (19, 15)):
        stump.put(x, y, (120, 230, 200))
    stump.outline(OUT)
    st.blit(stump, 0, 0)
    for i, n in enumerate(("stump_tl", "stump_tr", "stump_bl", "stump_br")):
        t = Canvas(T, T)
        ox, oy = (i % 2) * 16, (i // 2) * 16
        for y in range(T):
            for x in range(T):
                t.put(x, y, st.get(ox + x, oy + y))
        add_tile(n, t)

    # fallen log (3 wide), solid
    lg = Canvas(48, 16)
    lg.rect(0, 0, 48, 16, GRASS)
    lg.blit(grass_tile(19), 0, 0)
    lg.blit(grass_tile(20), 16, 0)
    lg.blit(grass_tile(21), 32, 0)
    body = Canvas(48, 16)
    body.rect(4, 3, 40, 10, BARK)
    body.hline(4, 43, 4, BARK_L)
    body.hline(4, 43, 11, BARK_D)
    for x in (12, 22, 33):
        body.vline(x, 5, 10, BARK_D)
    body.ell(5, 8, 3, 5, (214, 176, 120))
    body.ring(5, 8, 1.2, 1.9, (176, 132, 84))
    body.outline(OUT)
    lg.blit(body, 0, 0)
    for i, n in enumerate(("log_l", "log_m", "log_r")):
        t = Canvas(T, T)
        for y in range(T):
            for x in range(T):
                t.put(x, y, lg.get(i * 16 + x, y))
        add_tile(n, t, solid=True)

    # bridge planks (walkable over water)
    c = Canvas(T, T)
    c.rect(0, 0, T, T, WOOD)
    for y in (0, 4, 8, 12):
        c.hline(0, 15, y + 3, WOOD_D)
        c.hline(0, 15, y, WOOD_L)
    c.vline(0, 0, 15, BARK_D)
    c.vline(15, 0, 15, BARK_D)
    add_tile("bridge_v", c)
    add_tile("bridge_h", c.transpose())

    # house pieces
    def roof(kind):
        c = Canvas(T, T)
        c.rect(0, 0, T, T, ROOF_D)
        # scalloped shingles, offset every other row
        for row in range(4):
            y0 = row * 4
            off = 0 if row % 2 == 0 else 4
            for x0 in range(-8 + off, 16, 8):
                for y in range(4):
                    for x in range(8):
                        dx = (x - 3.5) / 4.0
                        if dx * dx + ((y - 4) / 4.5) ** 2 <= 1.0:
                            col = ROOF if y < 3 else ROOF_D
                            if y == 0 or (x < 2 and y < 2):
                                col = ROOF_L
                            c.put(x0 + x, y0 + y, col)
        if kind.endswith("l"):
            c.vline(0, 0, 15, OUT)
            c.vline(1, 0, 15, ROOF_D)
        if kind.endswith("r"):
            c.vline(15, 0, 15, OUT)
            c.vline(14, 0, 15, ROOF_D)
        if kind.startswith("t"):
            c.hline(0, 15, 0, OUT)
            c.hline(0, 15, 1, (150, 60, 50))
        if kind.startswith("b"):
            c.hline(0, 15, 14, (110, 36, 32))
            c.hline(0, 15, 15, OUT)
        return c
    for k in ("tl", "t", "tr", "ml", "m", "mr", "bl", "b", "br"):
        add_tile("roof_" + k, roof(k), solid=True)

    def wall(kind):
        c = Canvas(T, T)
        c.rect(0, 0, T, T, WALL)
        c.hline(0, 15, 0, WALL_D)
        c.hline(0, 15, 1, WALL_D)
        c.hline(0, 15, 14, BEAM)
        c.hline(0, 15, 15, OUT)
        if kind == "l":
            c.rect(0, 0, 3, 16, BEAM)
            c.vline(0, 0, 15, OUT)
        if kind == "r":
            c.rect(13, 0, 3, 16, BEAM)
            c.vline(15, 0, 15, OUT)
        if kind == "window":
            c.rect(3, 3, 10, 8, BEAM)
            c.rect(4, 4, 8, 6, GLASS)
            c.rect(4, 4, 3, 2, GLASS_L)
            c.vline(8, 4, 9, BEAM)
            c.hline(4, 11, 7, BEAM)
            c.rect(2, 11, 12, 2, WOOD)
            c.put(4, 10, (236, 88, 96))
            c.put(7, 10, (255, 240, 120))
            c.put(11, 10, (236, 88, 96))
        if kind == "door":
            c.rect(3, 2, 10, 14, BEAM)
            c.rect(4, 3, 8, 13, WOOD)
            c.vline(8, 3, 15, WOOD_D)
            c.hline(4, 11, 3, WOOD_L)
            c.put(10, 10, GOLD)
            c.put(6, 10, GOLD)
        return c
    for k in ("l", "m", "r", "window", "door"):
        add_tile("wall_" + k, wall(k), solid=True)

    # -- tiny world -----------------------------------------------------------------------------
    s = [soil_tile(s, s != 3) for s in (1, 2, 3)]
    add_tile("soil", s[0])
    add_tile("soil2", s[1])
    add_tile("soil3", s[2])
    c = s[2].copy()
    leaf = Canvas(T, T)
    for (cx, cy) in ((5, 5), (11, 5), (8, 10)):
        leaf.ell(cx, cy, 4, 3.6, (84, 172, 84), (56, 132, 60), (150, 210, 120))
    leaf.vline(8, 10, 15, (56, 132, 60))
    leaf.outline((36, 90, 44))
    c.blit(leaf, 0, 0)
    add_tile("clover", c)

    def blade_pair(seed, lean):
        b = Canvas(T, 32)
        for y in range(32):
            t = y / 31.0
            half = 2 + t * 4
            cx = 8 + (1 - t) ** 2 * lean
            for x in range(T):
                if abs(x + 0.5 - cx) <= half and not (y < 3 and abs(x + 0.5 - cx) > 1):
                    col = BLADE
                    if x + 0.5 > cx + half * 0.3:
                        col = BLADE_D
                    if abs(x + 0.5 - cx) < 0.6:
                        col = BLADE_L
                    b.put(x, y, col)
        b.outline(OUT)
        base = Canvas(T, 32)
        base.blit(soil_tile(seed), 0, 0)
        base.blit(soil_tile(seed + 1), 0, 16)
        base.ell(8, 30, 7, 2, SOIL_D)
        base.blit(b, 0, 0)
        return base
    for name, seed, lean in (("blade", 11, 3), ("blade2", 13, -3)):
        b = blade_pair(seed, lean)
        for i, part in enumerate(("t", "b")):
            t = Canvas(T, T)
            for y in range(T):
                for x in range(T):
                    t.put(x, y, b.get(x, y + i * 16))
            add_tile("%s_%s" % (name, part), t, solid=True)

    def big2x2(prefix, draw, seed):
        base = Canvas(32, 32)
        base.blit(soil_tile(seed), 0, 0)
        base.blit(soil_tile(seed + 1), 16, 0)
        base.blit(soil_tile(seed + 2), 0, 16)
        base.blit(soil_tile(seed + 3), 16, 16)
        obj = Canvas(32, 32)
        draw(obj)
        obj.outline(OUT)
        base.ell(16, 29, 13, 3, SOIL_D)
        base.blit(obj, 0, 0)
        for i, n in enumerate(("tl", "tr", "bl", "br")):
            t = Canvas(T, T)
            ox, oy = (i % 2) * 16, (i // 2) * 16
            for y in range(T):
                for x in range(T):
                    t.put(x, y, base.get(ox + x, oy + y))
            add_tile("%s_%s" % (prefix, n), t, solid=True)

    def draw_pebble(o):
        o.ell(16, 17, 14, 12, (184, 178, 168), (136, 130, 124), (224, 220, 212))
        o.line(10, 14, 15, 19, (136, 130, 124))
    big2x2("pebble", draw_pebble, 21)

    def draw_acorn(o):
        o.ell(16, 20, 11, 10, (196, 128, 64), (150, 92, 44), (232, 176, 112))
        o.ell(16, 10, 14, 7, (140, 98, 58), (104, 70, 40))
        for y in range(4, 16):
            for x in range(2, 30):
                if o.get(x, y) == (140, 98, 58) and (x + y) % 3 == 0:
                    o.put(x, y, (104, 70, 40))
        o.rect(15, 1, 3, 4, BARK_D)
    big2x2("acorn", draw_acorn, 25)

    # root wall: seamless solid bark
    c = Canvas(T, T)
    c.rect(0, 0, T, T, BARK)
    for x in range(0, 16, 5):
        for y in range(T):
            xx = x + int(1.5 * math.sin(y * 0.6 + x))
            c.put(xx, y, BARK_D)
            c.put(xx + 1, y, BARK_L)
    add_tile("root_wall", c, solid=True)
    # root wall bottom edge (meets soil)
    c2 = c.copy()
    c2.hline(0, 15, 14, BARK_D)
    c2.hline(0, 15, 15, OUT)
    add_tile("root_wall_b", c2, solid=True)
    # hollow entrance (2 wide): dark arch, bottom row walkable
    ho = Canvas(32, 32)
    ho.rect(0, 0, 32, 32, BARK)
    for x in range(0, 32, 5):
        for y in range(32):
            xx = x + int(1.5 * math.sin(y * 0.6 + x))
            ho.put(xx, y, BARK_D)
            ho.put(xx + 1, y, BARK_L)
    ho.ell(16, 32, 11, 18, (16, 10, 20))
    ho.ring(16, 32, 11, 12.2, BARK_D)
    for i, n in enumerate(("hollow_tl", "hollow_tr", "hollow_bl", "hollow_br")):
        t = Canvas(T, T)
        ox, oy = (i % 2) * 16, (i // 2) * 16
        for y in range(T):
            for x in range(T):
                t.put(x, y, ho.get(ox + x, oy + y))
        add_tile(n, t, solid=(i < 2))

    # -- dungeon ------------------------------------------------------------------------------
    def dfloor(seed, roots=False):
        c = Canvas(T, T)
        c.rect(0, 0, T, T, DFLOOR)
        c.hline(0, 15, 15, DFLOOR_D)
        c.vline(15, 0, 15, DFLOOR_D)
        c.hline(0, 14, 0, DFLOOR_L)
        c.vline(0, 0, 14, DFLOOR_L)
        r = random.Random(seed)
        for _ in range(3):
            x, y = r.randrange(2, 13), r.randrange(2, 13)
            c.put(x, y, DFLOOR_D)
            c.put(x + 1, y + 1, DFLOOR_D)
        if roots:
            for x in range(T):
                y = int(8 + 3 * math.sin(x * 0.5 + seed))
                c.put(x, y, BARK)
                c.put(x, y + 1, BARK_D)
        return c
    add_tile("dfloor", dfloor(1))
    add_tile("dfloor2", dfloor(2))
    add_tile("dfloor_roots", dfloor(3, True))

    def dwall(kind):
        c = Canvas(T, T)
        c.rect(0, 0, T, T, DWALL)
        # brick pattern
        for y in range(0, 16, 4):
            c.hline(0, 15, y, DWALL_D)
            off = 0 if (y // 4) % 2 == 0 else 4
            for x in range(off, 16, 8):
                c.vline(x, y, y + 3, DWALL_D)
            c.hline(0, 15, y + 1, DWALL_L)
        # inner edge faces the room
        if "t" == kind[0] or kind in ("tl", "tr"):
            pass
        edges = {"t": "s", "b": "n", "l": "e", "r": "w"}
        for k in kind:
            side = edges.get(k)
            if side == "s":
                c.rect(0, 12, 16, 4, DWALL_L)
                c.hline(0, 15, 15, OUT)
            elif side == "n":
                c.rect(0, 0, 16, 3, DWALL_D)
                c.hline(0, 15, 0, OUT)
            elif side == "e":
                c.rect(12, 0, 4, 16, DWALL_L)
                c.vline(15, 0, 15, OUT)
            elif side == "w":
                c.rect(0, 0, 4, 16, DWALL_L)
                c.vline(0, 0, 15, OUT)
        return c
    for k in ("t", "b", "l", "r"):
        add_tile("dwall_" + k, dwall(k), solid=True)
    # Corner pieces: the outside corners of a room carry no inner edge.
    corner = dwall("x")
    add_tile("dwall_c", corner, solid=True)

    # statue / pillar
    c = dfloor(4)
    p = Canvas(T, T)
    p.rect(2, 3, 12, 12, DWALL_L)
    p.rect(2, 3, 12, 3, (176, 156, 132))
    p.rect(3, 6, 10, 8, DWALL)
    p.rect(5, 8, 2, 2, (220, 120, 60))
    p.rect(9, 8, 2, 2, (220, 120, 60))
    p.outline(OUT)
    c.blit(p, 0, 0)
    add_tile("dstatue", c, solid=True)

    c = dfloor(5)
    c.rect(2, 2, 12, 12, (60, 44, 40))
    for i in range(4):
        c.hline(3, 12, 3 + i * 3, DFLOOR_L)
        c.hline(3, 12, 4 + i * 3, DFLOOR_D)
    add_tile("dstairs", c)

    c = dfloor(6)
    c.rect(1, 1, 14, 14, (150, 40, 40))
    c.rect(2, 2, 12, 12, (184, 56, 52))
    for x in range(2, 14, 3):
        c.put(x, 2, GOLD)
        c.put(x, 13, GOLD)
    add_tile("carpet", c)


# ---------------------------------------------------------------------------------------------
# Sprites
# ---------------------------------------------------------------------------------------------
sprites = {}   # name -> (Canvas, pivot_x, pivot_y)


def add_sprite(name, canvas, px=None, py=None):
    if px is None:
        px = canvas.w // 2
    if py is None:
        py = canvas.h - 1
    sprites[name] = (canvas, px, py)


CAP = (184, 124, 62)
CAP_D = (132, 84, 40)
CAP_L = (224, 172, 104)
BRIM = (226, 196, 140)
BRIM_D = (186, 150, 98)
HAIR = (248, 212, 96)
HAIR_D = (204, 160, 56)
TUNIC = (220, 92, 58)
TUNIC_D = (164, 56, 40)
TUNIC_L = (248, 144, 96)
BELT = (104, 66, 36)
BOOT = (96, 60, 36)
EYE = (36, 24, 40)


def draw_cap(c, d, oy=0, eyes=True, colors=(CAP, CAP_D, CAP_L, BRIM, BRIM_D)):
    """Capo, the acorn cap. d in 'down','up','right'."""
    cap, cap_d, cap_l, brim, brim_d = colors
    cx = 7.5 if d != "right" else 7.0
    c.ell(cx, 8.5 + oy, 6.6, 6.0, cap, cap_d, cap_l, clip=lambda x, y: y < 9 + oy,
          light_at=(-0.35, -0.55, 0.3))
    for y in range(2, 9):
        for x in range(16):
            if c.get(x, y + oy) == cap and (x * 2 + y) % 5 == 0:
                c.put(x, y + oy, cap_d)
    # stem
    sx = 7 if d != "right" else 5
    c.rect(sx, 1 + oy, 2, 2, BARK_D)
    # brim
    c.hline(1, 14, 9 + oy, brim)
    c.hline(1, 14, 10 + oy, brim_d)
    if d == "right":
        c.hline(2, 15, 9 + oy, brim)
        c.hline(2, 15, 10 + oy, brim_d)
    if eyes:
        if d == "down":
            for ex in (4, 10):
                c.rect(ex, 5 + oy, 2, 2, WHITE)
                c.put(ex + (1 if ex == 4 else 0), 6 + oy, EYE)
        elif d == "right":
            c.rect(10, 5 + oy, 2, 2, WHITE)
            c.put(11, 6 + oy, EYE)


def person(d, frame, opts):
    """Generic chibi person 16x22, pivot (8,21). opts drives colours/accessories."""
    c = Canvas(16, 22)
    step = frame in (1, 3)
    bob = -1 if step else 0
    skin, skin_d = opts.get("skin", (SKIN, SKIN_D))
    hair, hair_d = opts.get("hair", (HAIR, HAIR_D))
    body, body_d, body_l = opts.get("body", (TUNIC, TUNIC_D, TUNIC_L))
    boots = opts.get("boots", BOOT)
    robe = opts.get("robe", False)

    # feet / legs
    if robe:
        c.rect(4, 17, 8, 3, body_d)
        lf = 1 if frame == 1 else 0
        rf = 1 if frame == 3 else 0
        c.rect(4, 19 - lf, 3, 1, boots)
        c.rect(9, 19 - rf, 3, 1, boots)
    elif d in ("down", "up"):
        lf = 1 if frame == 1 else 0
        rf = 1 if frame == 3 else 0
        c.rect(5, 18 - lf, 2, 2, boots)
        c.rect(9, 18 - rf, 2, 2, boots)
    else:
        if frame == 1:
            c.rect(4, 18, 3, 2, boots)
            c.rect(9, 18, 3, 2, boots)
        elif frame == 3:
            c.rect(6, 18, 4, 2, boots)
        else:
            c.rect(5, 18, 2, 2, boots)
            c.rect(8, 18, 3, 2, boots)

    # torso
    tx0, tx1 = (4, 11) if d != "right" else (5, 10)
    top = 14 + bob
    c.rect(tx0, top, tx1 - tx0 + 1, 5 - bob if not robe else 6, body)
    c.vline(tx1, top, 18, body_d)
    c.hline(tx0, tx1, top, body_l)
    if opts.get("belt", True) and not robe:
        c.hline(tx0, tx1, 17, BELT)
        if d == "down":
            c.rect(7, 17, 2, 1, GOLD)
    # arms
    swing = {0: 0, 1: 1, 2: 0, 3: -1}[frame]
    if d in ("down", "up"):
        c.rect(3, top + 1 + swing, 1, 3, body_d)
        c.put(3, top + 4 + swing, skin)
        c.rect(12, top + 1 - swing, 1, 3, body_d)
        c.put(12, top + 4 - swing, skin)
    else:
        ax = 7 + swing
        c.rect(ax, top + 1, 2, 3, body_d)
        c.put(ax + (1 if swing >= 0 else 0), top + 4, skin)

    # head
    hy = 12.0 + bob
    if d == "right":
        c.ell(8.5, hy, 5, 4.2, skin, skin_d, None, shade_dir=(-0.7, 0.7), shade_at=0.6)
        c.rect(3, int(hy) - 3, 3, 5, hair)
        c.put(3, int(hy) + 2, hair_d)
        c.put(10, int(hy), EYE)
        c.put(10, int(hy) + 1, EYE)
        c.put(13, int(hy) + 1, skin)
    else:
        c.ell(7.5, hy, 5.5, 4.2, skin, skin_d, None, shade_dir=(0.0, 1.0), shade_at=0.75)
        if d == "down":
            c.hline(3, 12, int(hy) - 3, hair)
            c.put(3, int(hy) - 2, hair)
            c.put(12, int(hy) - 2, hair)
            if not opts.get("closed_eyes"):
                c.vline(5, int(hy), int(hy) + 1, EYE)
                c.vline(10, int(hy), int(hy) + 1, EYE)
            else:
                c.hline(4, 5, int(hy) + 1, EYE)
                c.hline(10, 11, int(hy) + 1, EYE)
            c.put(4, int(hy) + 2, (244, 150, 140))
            c.put(11, int(hy) + 2, (244, 150, 140))
        else:
            c.ell(7.5, hy - 0.5, 5.5, 3.8, hair, hair_d, None, shade_dir=(0, 1), shade_at=0.7)

    if opts.get("beard"):
        if d != "up":
            bx = 4 if d == "down" else 7
            c.rect(bx, int(hy) + 2, 8 if d == "down" else 6, 4, (236, 236, 240))
            c.hline(bx, bx + (7 if d == "down" else 5), int(hy) + 5, (196, 196, 208))
    hat = opts.get("hat", "cap")
    if hat == "cap":
        draw_cap(c, d, oy=bob + 1 - 1, eyes=opts.get("cap_eyes", True))
    elif hat == "helmet":
        c.ell(7.5, 9.5 + bob, 6.2, 5.5, STONE, STONE_D, STONE_L, clip=lambda x, y: y < 10 + bob)
        c.hline(1, 14, 9 + bob, STONE_D)
        c.rect(7, 2 + bob, 2, 2, RED)
    elif hat == "thimble":
        c.rect(3, 2 + bob, 10, 8, (200, 204, 214))
        c.hline(2, 13, 9 + bob, (150, 152, 166))
        c.hline(3, 12, 2 + bob, (230, 232, 240))
        for y in range(4, 9, 2):
            for x in range(4 + (y // 2) % 2, 12, 2):
                c.put(x, y + bob, (150, 152, 166))
    elif hat == "bald":
        c.ell(7.5, hy - 1.5, 5.3, 3.2, skin, skin_d, (255, 230, 200), clip=lambda x, y: y < hy - 1)
        c.put(3, int(hy) - 1, (236, 236, 240))
        c.put(12, int(hy) - 1, (236, 236, 240))
    elif hat == "bun":
        c.ell(7.5, hy - 2, 5.8, 3.5, hair, hair_d, None, clip=lambda x, y: y < hy - 1)
        c.ell(7.5, hy - 6, 2.5, 2.2, hair, hair_d)
        c.put(10, int(hy) - 4, (236, 88, 96))
    elif hat == "kid":
        c.ell(7.5, hy - 2, 5.8, 3.5, hair, hair_d, None, clip=lambda x, y: y < hy - 1)
        c.put(9, int(hy) - 6, hair)
        c.put(10, int(hy) - 7, hair)
    if opts.get("staff"):
        c.vline(14, 8 + bob, 20, WOOD_D)
        c.ell(14, 7 + bob, 1.6, 1.6, (120, 230, 200))
    if opts.get("spear"):
        c.vline(14, 2 + bob, 20, WOOD_D)
        c.rect(13, 0, 3, 3, STONE_L)
    c.outline(OUT)
    return c


HERO = {}


def make_people():
    for d in ("down", "up", "right"):
        for f in range(4):
            add_sprite("hero_%s_%d" % (d, f), person(d, f, HERO), 8, 21)
        # attack pose: lean forward, arm out
        a = person(d, 0, HERO)
        add_sprite("hero_atk_%s" % d, a, 8, 21)
    # hold item overhead
    h = person("down", 0, dict(HERO))
    h.rect(2, 9, 2, 5, TUNIC_D)
    h.rect(12, 9, 2, 5, TUNIC_D)
    h.put(2, 8, SKIN)
    h.put(13, 8, SKIN)
    h.outline(OUT)
    add_sprite("hero_hold", h, 8, 21)
    # lying down (fainted)
    lie = person("right", 0, dict(HERO, closed_eyes=True)).transpose().flip_x()
    add_sprite("hero_lie", lie, 11, 15)
    # roll: a tumbling cap-ball
    for f in range(4):
        r = Canvas(16, 16)
        r.ell(7.5, 8.5, 6.5, 6.5, TUNIC, TUNIC_D, TUNIC_L)
        ang = f * math.pi / 2
        for i in range(-6, 7):
            x = 7.5 + math.cos(ang) * i
            y = 8.5 + math.sin(ang) * i
            if abs(i) < 6:
                r.put(x, y, CAP)
        r.ell(7.5 + math.cos(ang + 1.5) * 3, 8.5 + math.sin(ang + 1.5) * 3, 2.2, 2.2, SKIN)
        r.outline(OUT)
        add_sprite("hero_roll_%d" % f, r, 8, 15)

    npcs = {
        "elder": dict(hat="bald", beard=True, robe=True, staff=True,
                      body=((92, 140, 100), (60, 100, 70), (130, 176, 130)), cap_eyes=False),
        "mira": dict(hat="bun", hair=((150, 90, 50), (110, 62, 36)), robe=True,
                     body=((236, 120, 160), (190, 80, 120), (255, 170, 200))),
        "tobi": dict(hat="kid", hair=((236, 130, 60), (190, 90, 40)),
                     body=((80, 150, 230), (50, 100, 180), (140, 190, 250))),
        "guard": dict(hat="helmet", spear=True,
                      body=((70, 100, 180), (44, 66, 130), (110, 140, 220))),
        "thim": dict(hat="thimble", hair=((120, 80, 50), (90, 60, 40)),
                     body=((110, 170, 80), (70, 120, 50), (160, 210, 120))),
        "thim2": dict(hat="thimble", hair=((240, 200, 120), (200, 160, 80)), robe=True,
                      body=((200, 140, 220), (150, 90, 170), (230, 190, 245))),
    }
    for name, o in npcs.items():
        dirs = ("down", "up", "right") if name in ("tobi", "guard") else ("down",)
        for d in dirs:
            for f in range(4):
                spr = person(d, f, o)
                if name == "tobi":
                    spr = spr.shift(0, 1)
                add_sprite("%s_%s_%d" % (name, d, f), spr, 8, 21)


def make_sword():
    s = Canvas(16, 7)
    s.rect(0, 2, 3, 3, BARK)
    s.rect(1, 3, 2, 1, BARK_L)
    s.rect(3, 0, 2, 7, GOLD)
    s.vline(4, 0, 6, GOLD_D)
    for x in range(5, 15):
        s.put(x, 2, (232, 240, 248))
        s.put(x, 3, (200, 212, 228))
        s.put(x, 4, (150, 164, 188))
    s.put(15, 3, (200, 212, 228))
    s.put(14, 2, None)
    s.put(14, 4, None)
    s.outline(OUT)
    # horizontal pointing right, pivot at the hilt
    add_sprite("sword_h", s, 1, 3)
    add_sprite("sword_v", s.transpose(), 3, 1)
    d = Canvas(14, 14)
    for i in range(0, 12):
        d.put(i + 1, i + 1, (232, 240, 248))
        d.put(i + 2, i + 1, (150, 164, 188))
    d.put(0, 2, GOLD)
    d.put(1, 2, GOLD)
    d.put(2, 1, GOLD)
    d.put(2, 0, GOLD)
    d.put(3, 3, GOLD_D)
    d.put(1, 1, BARK)
    d.outline(OUT)
    add_sprite("sword_d", d, 1, 1)
    # item icon
    icon = Canvas(16, 16)
    icon.blit(s.transpose().flip_y(), 4, 0)
    add_sprite("item_sword", icon, 8, 15)


def make_enemies():
    # blob
    for color, pal in (("g", ((96, 200, 72), (52, 140, 48), (200, 244, 160))),
                       ("r", ((232, 84, 72), (160, 44, 48), (255, 180, 160))),
                       ("b", ((96, 140, 240), (52, 84, 180), (190, 214, 255)))):
        for f, (rx, ry, cy) in enumerate(((6.2, 5.2, 10.3), (7.3, 4.0, 11.5), (5.2, 6.3, 9.0))):
            c = Canvas(16, 16)
            c.ell(7.5, cy, rx, ry, pal[0], pal[1], pal[2], light_at=(-0.35, -0.4, 0.28))
            ey = int(cy)
            c.vline(5, ey - 1, ey, EYE)
            c.vline(10, ey - 1, ey, EYE)
            c.outline(OUT)
            add_sprite("blob_%s_%d" % (color, f), c, 8, 15)

    # pod (spitting plant)
    for d in ("down", "up", "right"):
        for f in range(2):
            c = Canvas(16, 16)
            c.ell(4, 14, 4, 2, LEAF, LEAF_D)
            c.ell(11, 14, 4, 2, LEAF, LEAF_D)
            c.ell(7.5, 8.5, 6, 6, (150, 96, 200), (100, 60, 150), (210, 170, 240))
            for y in range(3, 15):
                for x in range(16):
                    if c.get(x, y) == (150, 96, 200) and (x + y) % 4 == 0:
                        c.put(x, y, (124, 76, 176))
            mr = 2.2 if f == 0 else 3.0
            if d == "down":
                c.ell(7.5, 11, mr, mr * 0.8, (50, 20, 40))
                c.put(5, 6, EYE)
                c.put(10, 6, EYE)
            elif d == "up":
                c.ell(7.5, 3.5, mr, mr * 0.7, (50, 20, 40))
            else:
                c.ell(12.5, 9, mr * 0.8, mr, (50, 20, 40))
                c.put(9, 6, EYE)
            c.outline(OUT)
            add_sprite("pod_%s_%d" % (d, f), c, 8, 15)

    # beetle
    for d in ("down", "up", "right"):
        for f in range(2):
            c = Canvas(16, 16)
            legs = (1 if f else 0)
            if d in ("down", "up"):
                for i, y in enumerate((6, 9, 12)):
                    off = legs if i % 2 == 0 else -legs
                    c.hline(1, 3, y + off, OUT)
                    c.hline(12, 14, y - off, OUT)
                c.ell(7.5, 9, 5.5, 6, (60, 92, 176), (36, 56, 120), (140, 170, 240))
                c.vline(7, 4, 14, (36, 56, 120))
                c.vline(8, 4, 14, (36, 56, 120))
                hy = 14 if d == "down" else 2
                c.ell(7.5, hy + 0.5, 3, 2, (40, 36, 52))
                if d == "down":
                    c.put(6, 14, (255, 90, 80))
                    c.put(9, 14, (255, 90, 80))
            else:
                for i, x in enumerate((4, 7, 10)):
                    off = legs if i % 2 == 0 else -legs
                    c.vline(x + off, 12, 14, OUT)
                c.ell(7, 8.5, 6, 5, (60, 92, 176), (36, 56, 120), (140, 170, 240))
                c.hline(2, 12, 8, (36, 56, 120))
                c.ell(13, 9.5, 2, 2.5, (40, 36, 52))
                c.put(14, 9, (255, 90, 80))
            c.outline(OUT)
            add_sprite("beetle_%s_%d" % (d, f), c, 8, 15)

    # bat
    for f in range(2):
        c = Canvas(16, 12)
        c.ell(7.5, 6.5, 3, 3, (110, 70, 140), (70, 40, 96))
        if f == 0:
            for i in range(5):
                c.vline(3 - i // 2, 6 - i, 6, (90, 54, 120))
                c.vline(12 + i // 2, 6 - i, 6, (90, 54, 120))
            c.hline(0, 4, 2, (90, 54, 120))
            c.hline(11, 15, 2, (90, 54, 120))
        else:
            for i in range(5):
                c.vline(3 - i // 2, 6, 6 + i, (90, 54, 120))
                c.vline(12 + i // 2, 6, 6 + i, (90, 54, 120))
        c.put(6, 6, (255, 220, 80))
        c.put(9, 6, (255, 220, 80))
        c.outline(OUT)
        add_sprite("bat_%d" % f, c, 8, 11)

    # ant
    for d in ("down", "up", "right"):
        for f in range(2):
            c = Canvas(16, 16)
            col, col_d, col_l = (196, 70, 48), (140, 40, 32), (240, 130, 100)
            if d in ("down", "up"):
                ys = (4, 8.5, 13) if d == "down" else (12, 7.5, 3)
                for i, y in enumerate((5, 8, 11)):
                    off = f if i % 2 else -f
                    c.hline(2, 4, y + off, OUT)
                    c.hline(11, 13, y - off, OUT)
                c.ell(7.5, ys[0], 3.5, 3, col, col_d, col_l)
                c.ell(7.5, ys[1], 2.5, 2.5, col, col_d, col_l)
                c.ell(7.5, ys[2], 3, 2.6, col, col_d, col_l)
                if d == "down":
                    c.put(6, 13, EYE)
                    c.put(9, 13, EYE)
                    c.put(5, 15, OUT)
                    c.put(10, 15, OUT)
            else:
                for i, x in enumerate((5, 8, 11)):
                    off = f if i % 2 else -f
                    c.vline(x + off, 11, 14, OUT)
                c.ell(3.5, 9, 3, 3, col, col_d, col_l)
                c.ell(8, 9, 2.5, 2.3, col, col_d, col_l)
                c.ell(12, 8.5, 3, 2.6, col, col_d, col_l)
                c.put(13, 8, EYE)
                c.put(15, 5, OUT)
                c.put(14, 6, OUT)
            c.outline(OUT)
            add_sprite("ant_%s_%d" % (d, f), c, 8, 15)

    # seed projectile
    c = Canvas(8, 8)
    c.ell(3.5, 3.5, 2.6, 2.6, (230, 200, 120), (170, 130, 70), WHITE)
    c.outline(OUT)
    add_sprite("seed", c, 4, 4)

    # boss: the Bramble Beetle (32x32)
    shell, shell_d, shell_l = (84, 120, 60), (52, 80, 40), (140, 176, 96)
    thorn = (232, 220, 170)
    for d in ("down", "up", "right"):
        for f in range(2):
            c = Canvas(32, 32)
            if d in ("down", "up"):
                for i, y in enumerate((11, 17, 23)):
                    off = f if i % 2 == 0 else -f
                    c.line(1, y + off - 2, 5, y + off, OUT)
                    c.line(26, y - off, 30, y - off - 2, OUT)
                c.ell(15.5, 17, 11, 12, shell, shell_d, shell_l)
                c.vline(15, 6, 28, shell_d)
                c.vline(16, 6, 28, shell_d)
                for (tx, ty) in ((8, 11), (23, 11), (7, 19), (24, 19), (10, 25), (21, 25)):
                    c.rect(tx, ty, 2, 2, thorn)
                if d == "down":
                    c.ell(15.5, 28.5, 6, 3, (40, 36, 52))
                    c.rect(14, 29, 4, 3, (200, 190, 150))
                    c.put(12, 28, (255, 80, 60))
                    c.put(19, 28, (255, 80, 60))
                else:
                    c.ell(15.5, 4.5, 6, 3, (40, 36, 52))
                    c.rect(14, 0, 4, 3, (200, 190, 150))
            else:
                for i, x in enumerate((9, 15, 21)):
                    off = f if i % 2 == 0 else -f
                    c.line(x + off, 24, x + off - 1, 29, OUT)
                c.ell(14, 17, 12, 10, shell, shell_d, shell_l)
                c.hline(3, 25, 16, shell_d)
                for tx in (7, 13, 19):
                    c.rect(tx, 8, 2, 2, thorn)
                c.ell(27, 18, 4, 5, (40, 36, 52))
                c.rect(29, 14, 3, 3, (200, 190, 150))
                c.put(28, 16, (255, 80, 60))
            c.outline(OUT)
            add_sprite("boss_%s_%d" % (d, f), c, 16, 30)
    for f in range(2):
        c = Canvas(32, 32)
        for i, x in enumerate((8, 13, 18, 23)):
            off = 2 if (i + f) % 2 else 0
            c.vline(x, 4 + off, 9, OUT)
        c.ell(15.5, 18, 12, 11, (226, 206, 160), (184, 160, 116))
        for y in (12, 16, 20, 24):
            c.hline(6, 25, y, (184, 160, 116))
        c.ell(15.5, 28, 6, 3, (40, 36, 52))
        c.put(13, 28, WHITE)
        c.put(18, 28, WHITE)
        c.outline(OUT)
        add_sprite("boss_flip_%d" % f, c, 16, 30)


def make_objects():
    # bush
    b = Canvas(16, 16)
    b.ell(7.5, 9, 7, 6.2, (84, 172, 72), (52, 124, 52), None)
    for (cx, cy) in ((5, 7), (10, 6), (7.5, 11), (11.5, 10.5), (3.5, 11)):
        b.ell(cx, cy, 2.4, 2.0, (84, 172, 72), (52, 124, 52), (150, 214, 110),
              light_at=(-0.3, -0.5, 0.4))
    b.outline(OUT)
    add_sprite("bush", b, 8, 15)
    s = Canvas(16, 16)
    s.ell(7.5, 12, 5, 2.5, (72, 140, 60), (52, 110, 48))
    for x in (4, 7, 10):
        s.vline(x, 10, 12, (52, 110, 48))
    s.outline(OUT)
    add_sprite("bush_stub", s, 8, 15)

    # pot
    p = Canvas(16, 16)
    p.ell(7.5, 10, 6.5, 5.5, (196, 120, 72), (144, 82, 48), (236, 170, 120))
    p.rect(4, 2, 8, 3, (168, 100, 60))
    p.hline(4, 11, 2, (236, 170, 120))
    p.rect(5, 3, 6, 1, (60, 36, 28))
    p.hline(3, 12, 9, (144, 82, 48))
    p.outline(OUT)
    add_sprite("pot", p, 8, 15)

    # chest closed/open
    for state in ("closed", "open"):
        c = Canvas(16, 16)
        c.rect(1, 5, 14, 10, WOOD)
        c.rect(1, 5, 14, 2, WOOD_L)
        c.hline(1, 14, 14, WOOD_D)
        c.vline(4, 5, 14, GOLD_D)
        c.vline(11, 5, 14, GOLD_D)
        if state == "closed":
            c.rect(1, 1, 14, 5, WOOD_D)
            c.hline(1, 14, 1, WOOD)
            c.vline(4, 1, 5, GOLD)
            c.vline(11, 1, 5, GOLD)
            c.rect(6, 5, 4, 3, GOLD)
            c.put(7, 6, OUT)
        else:
            c.rect(2, 4, 12, 3, (40, 26, 20))
            c.rect(1, 0, 14, 3, WOOD_D)
            c.hline(1, 14, 0, WOOD)
        c.outline(OUT)
        add_sprite("chest_" + state, c, 8, 15)

    # push block
    k = Canvas(16, 16)
    k.rect(0, 0, 16, 16, (156, 140, 120))
    k.rect(0, 0, 16, 2, (196, 182, 160))
    k.rect(0, 0, 2, 16, (196, 182, 160))
    k.rect(14, 0, 2, 16, (110, 98, 86))
    k.rect(0, 13, 16, 3, (110, 98, 86))
    k.rect(5, 5, 6, 5, (130, 116, 100))
    k.put(5, 5, (196, 182, 160))
    add_sprite("block", k, 8, 15)

    # floor switch
    for st, h in (("up", 3), ("down", 1)):
        c = Canvas(16, 16)
        c.rect(1, 1, 14, 14, (84, 72, 64))
        c.rect(2, 2, 12, 12, (120, 104, 92))
        c.rect(4, 6 - h + 1, 8, 6 + h - 1, (220, 180, 60) if st == "up" else (150, 120, 50))
        c.hline(4, 11, 6 - h + 1, GOLD_L if st == "up" else GOLD_D)
        add_sprite("switch_" + st, c, 8, 15)

    # sign
    s = Canvas(16, 16)
    s.vline(7, 9, 15, WOOD_D)
    s.vline(8, 9, 15, WOOD_D)
    s.rect(1, 2, 14, 8, WOOD)
    s.hline(1, 14, 2, WOOD_L)
    s.hline(1, 14, 9, WOOD_D)
    for y in (4, 6):
        s.hline(3, 12, y, WOOD_D)
    s.outline(OUT)
    add_sprite("sign", s, 8, 15)

    # torch (brazier) with flame frames
    for f in range(2):
        t = Canvas(16, 20)
        t.rect(4, 13, 8, 6, (96, 84, 80))
        t.hline(3, 12, 13, (140, 124, 116))
        t.hline(4, 11, 18, (60, 52, 50))
        fl = Canvas(16, 20)
        sway = 1 if f else -1
        fl.ell(7.5, 10, 3.5, 3.5, (240, 120, 40))
        fl.ell(7.5 + sway * 0.6, 7.5, 2.5, 3.5, (250, 180, 60))
        fl.ell(7.5 + sway, 5, 1.4, 2.5, (255, 240, 160))
        t.blit(fl, 0, 0)
        t.outline(OUT)
        add_sprite("torch_%d" % f, t, 8, 19)

    # small key
    k = Canvas(8, 15)
    k.ring(3.5, 3.5, 1.4, 3.2, GOLD)
    k.vline(3, 6, 13, GOLD)
    k.vline(4, 6, 13, GOLD_D)
    k.hline(5, 6, 10, GOLD)
    k.hline(5, 6, 12, GOLD)
    k.outline(OUT)
    add_sprite("key", k, 4, 14)
    # big key
    k = Canvas(16, 16)
    k.ell(7.5, 4.5, 4.5, 4, (220, 60, 60), (150, 30, 40), (255, 160, 150))
    k.ell(7.5, 4.5, 1.6, 1.4, GOLD_L)
    k.rect(6, 8, 4, 7, GOLD)
    k.vline(9, 8, 14, GOLD_D)
    k.rect(10, 11, 3, 2, GOLD)
    k.rect(10, 14, 2, 1, GOLD)
    k.outline(OUT)
    add_sprite("bigkey", k, 8, 15)

    # gems (currency)
    for name, (cc, cd, cl) in (("g", ((80, 210, 96), (40, 140, 60), (200, 255, 200))),
                               ("b", ((80, 140, 240), (40, 80, 180), (200, 224, 255))),
                               ("r", ((236, 70, 70), (160, 30, 40), (255, 190, 190)))):
        for f in range(2):
            g = Canvas(8, 14)
            for y in range(12):
                half = min(y + 1, 12 - y, 3.2) if y < 3 or y > 9 else 3.2
                for x in range(8):
                    dx = x + 0.5 - 4
                    if abs(dx) <= half:
                        col = cc
                        if dx > 0.5:
                            col = cd
                        if dx < -0.5 and 2 < y < 9:
                            col = cl if f == 0 or y > 5 else cc
                        g.put(x, y + 1, col)
            if f == 1:
                g.put(2, 3, WHITE)
                g.put(1, 4, WHITE)
            g.outline(OUT)
            add_sprite("gem_%s_%d" % (name, f), g, 4, 13)

    # heart pickup / hud hearts
    def heart(fill_l, fill_r):
        h = Canvas(9, 8)
        rows = [".##.##...", "#######..", "#######..", ".#####...", "..###....", "...#....."]
        for y, row in enumerate(rows):
            for x, ch in enumerate(row[:7]):
                if ch == "#":
                    col = fill_l if x < 3 or (x == 3 and y > 0) else fill_r
                    if x == 3:
                        col = fill_l
                    h.put(x + 1, y + 1, col)
        if fill_l == RED:
            h.put(2, 2, WHITE)
        h.outline(OUT)
        return h
    EMPTY = (72, 52, 60)
    add_sprite("heart", heart(RED, RED), 4, 7)
    add_sprite("hud_heart_full", heart(RED, RED), 0, 0)
    add_sprite("hud_heart_half", heart(RED, EMPTY), 0, 0)
    add_sprite("hud_heart_empty", heart(EMPTY, EMPTY), 0, 0)

    # heart container
    hc = Canvas(16, 16)
    rows = ["..###...###..", ".#####.#####.", "#############", "#############", "#############",
            ".###########.", "..#########..", "...#######...", "....#####....", ".....###.....",
            "......#......"]
    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            if ch == "#":
                hc.put(x + 1, y + 2, RED if x < 7 else RED_D)
    hc.put(3, 4, WHITE)
    hc.put(4, 4, WHITE)
    hc.put(3, 5, WHITE)
    hc.outline(GOLD)
    hc.outline(OUT)
    add_sprite("heart_container", hc, 8, 15)

    # sunstone
    for f in range(2):
        s = Canvas(20, 20)
        for i in range(8):
            a = i * math.pi / 4 + (f * math.pi / 8)
            s.line(9.5 + math.cos(a) * 6, 9.5 + math.sin(a) * 6,
                   9.5 + math.cos(a) * 9, 9.5 + math.sin(a) * 9, GOLD if f == 0 else GOLD_L)
        s.ell(9.5, 9.5, 6, 6, (255, 168, 48), (220, 110, 30), GOLD_L)
        s.ell(9.5, 9.5, 2.6, 2.6, (255, 236, 160))
        s.outline(OUT)
        add_sprite("sunstone_%d" % f, s, 10, 19)

    # doors (horizontal wall passage); vertical variants are transposed
    def door(kind):
        d = Canvas(16, 16)
        if kind == "locked":
            d.rect(0, 0, 16, 16, WOOD_D)
            d.rect(1, 0, 14, 16, WOOD)
            for x in (4, 8, 12):
                d.vline(x, 0, 15, WOOD_D)
            d.hline(1, 14, 3, STONE_D)
            d.hline(1, 14, 12, STONE_D)
            d.rect(5, 5, 6, 6, GOLD)
            d.rect(7, 7, 2, 3, OUT)
        elif kind == "shutter":
            d.rect(0, 0, 16, 16, (70, 64, 72))
            for x in range(1, 16, 3):
                d.vline(x, 0, 15, STONE_L)
                d.vline(x + 1, 0, 15, STONE_D)
        elif kind == "boss":
            d.rect(0, 0, 16, 16, (120, 36, 40))
            d.rect(1, 1, 14, 14, (170, 50, 52))
            d.ring(7.5, 7.5, 3.5, 5.0, GOLD)
            d.rect(6, 6, 4, 4, (220, 60, 60))
            d.put(7, 7, GOLD_L)
            for (x, y) in ((1, 1), (14, 1), (1, 14), (14, 14)):
                d.put(x, y, GOLD)
        return d
    for kind in ("locked", "shutter", "boss"):
        d = door(kind)
        add_sprite("door_%s_h" % kind, d, 8, 15)
        add_sprite("door_%s_v" % kind, d.transpose(), 8, 15)

    # leaf portal (grow back)
    for f in range(4):
        p = Canvas(32, 20)
        p.ell(15.5, 10, 15, 9, (90, 170, 80), (60, 130, 60))
        p.ell(15.5, 10, 11, 6.5, (130, 210, 120))
        a0 = f * math.pi / 8
        for i in range(3):
            a = a0 + i * 2 * math.pi / 3
            for rr in range(2, 10):
                x = 15.5 + math.cos(a + rr * 0.25) * rr * 1.3
                y = 10 + math.sin(a + rr * 0.25) * rr * 0.7
                p.put(x, y, (220, 255, 200))
        p.outline(OUT)
        add_sprite("portal_%d" % f, p, 16, 10)

    # shadows
    sh = Canvas(12, 5)
    sh.ell(6, 2.5, 6, 2.5, (0, 0, 0))
    add_sprite("shadow", sh, 6, 2)
    sh = Canvas(28, 8)
    sh.ell(14, 4, 14, 4, (0, 0, 0))
    add_sprite("shadow_big", sh, 14, 4)

    # Capo, big (title / dialog portrait)
    big = Canvas(48, 40)
    big.ell(23.5, 26, 22, 20, CAP, CAP_D, CAP_L, clip=lambda x, y: y < 27,
            light_at=(-0.4, -0.5, 0.25))
    for y in range(4, 27):
        for x in range(48):
            if big.get(x, y) == CAP and (x + y * 2) % 6 == 0:
                big.put(x, y, CAP_D)
    big.rect(1, 26, 46, 4, BRIM)
    big.rect(1, 29, 46, 3, BRIM_D)
    big.rect(21, 1, 5, 6, BARK_D)
    big.rect(22, 1, 2, 5, BARK)
    for ex in (12, 30):
        big.ell(ex + 3, 17, 5, 5.5, WHITE)
        big.ell(ex + 4, 18, 2.4, 3, EYE)
        big.put(ex + 3, 16, WHITE)
    big.outline(OUT)
    add_sprite("capo_big", big, 24, 39)
    sm = Canvas(16, 14)
    sm.ell(7.5, 10, 7, 7.5, CAP, CAP_D, CAP_L, clip=lambda x, y: y < 10)
    sm.rect(0, 9, 16, 2, BRIM)
    sm.rect(7, 1, 2, 2, BARK_D)
    sm.rect(4, 5, 2, 2, WHITE)
    sm.rect(10, 5, 2, 2, WHITE)
    sm.put(5, 6, EYE)
    sm.put(10, 6, EYE)
    sm.outline(OUT)
    add_sprite("capo_small", sm, 8, 13)


def make_fx():
    for f in range(4):
        c = Canvas(16, 16)
        r = 2 + f * 2
        for i in range(6):
            a = i * math.pi / 3 + f * 0.3
            c.ell(7.5 + math.cos(a) * r, 7.5 + math.sin(a) * r, 3 - f * 0.5, 3 - f * 0.5,
                  (240, 236, 228), (190, 184, 176))
        if f < 3:
            c.outline((120, 112, 120))
        add_sprite("poof_%d" % f, c, 8, 8)
    for f in range(2):
        c = Canvas(6, 6)
        if f == 0:
            c.rect(1, 2, 4, 2, (84, 172, 72))
            c.put(2, 1, (84, 172, 72))
        else:
            c.rect(2, 1, 2, 4, (84, 172, 72))
            c.put(4, 2, (84, 172, 72))
        c.outline((40, 90, 40))
        add_sprite("leaf_%d" % f, c, 3, 3)
    c = Canvas(6, 6)
    c.rect(1, 1, 4, 3, (196, 120, 72))
    c.put(1, 1, (236, 170, 120))
    c.outline(OUT)
    add_sprite("shard", c, 3, 3)
    for f in range(3):
        c = Canvas(9, 9)
        r = (1, 3, 4)[f]
        c.hline(4 - r, 4 + r, 4, WHITE)
        c.vline(4, 4 - r, 4 + r, WHITE)
        if f == 1:
            c.put(3, 3, GOLD_L)
            c.put(5, 5, GOLD_L)
            c.put(3, 5, GOLD_L)
            c.put(5, 3, GOLD_L)
        add_sprite("sparkle_%d" % f, c, 4, 4)
    for f in range(2):
        c = Canvas(16, 16)
        r = 4 if f == 0 else 7
        for i in range(8):
            a = i * math.pi / 4
            c.line(7.5 + math.cos(a) * (r - 3), 7.5 + math.sin(a) * (r - 3),
                   7.5 + math.cos(a) * r, 7.5 + math.sin(a) * r, WHITE if f == 0 else GOLD_L)
        add_sprite("hit_%d" % f, c, 8, 8)
    for f in range(2):
        c = Canvas(8, 8)
        c.ell(3.5, 4, 2.5 + f, 2 + f * 0.5, (220, 210, 190), (180, 170, 150))
        add_sprite("dust_%d" % f, c, 4, 4)


def make_hud():
    white = Canvas(4, 4)
    white.rect(0, 0, 4, 4, WHITE)
    add_sprite("white", white, 0, 0)
    BOX = (36, 40, 88)
    BOX_L = (240, 236, 220)
    BOX_M = (120, 128, 190)
    for name, (x0, y0) in (("tl", (0, 0)), ("t", (1, 0)), ("tr", (2, 0)), ("l", (0, 1)),
                           ("m", (1, 1)), ("r", (2, 1)), ("bl", (0, 2)), ("b", (1, 2)),
                           ("br", (2, 2))):
        c = Canvas(8, 8)
        c.rect(0, 0, 8, 8, BOX)
        if y0 == 0:
            c.hline(0, 7, 0, OUT)
            c.hline(0, 7, 1, BOX_L)
            c.hline(0, 7, 2, BOX_M)
        if y0 == 2:
            c.hline(0, 7, 7, OUT)
            c.hline(0, 7, 6, BOX_L)
            c.hline(0, 7, 5, BOX_M)
        if x0 == 0:
            c.vline(0, 0, 7, OUT)
            c.vline(1, 0, 7, BOX_L)
            c.vline(2, 0, 7, BOX_M)
        if x0 == 2:
            c.vline(7, 0, 7, OUT)
            c.vline(6, 0, 7, BOX_L)
            c.vline(5, 0, 7, BOX_M)
        if (x0, y0) in ((0, 0), (2, 0), (0, 2), (2, 2)):
            cx = 0 if x0 == 0 else 7
            cy = 0 if y0 == 0 else 7
            c.put(cx, cy, None)
            c.put(1 if x0 == 0 else 6, 1 if y0 == 0 else 6, BOX_L)
        add_sprite("box_" + name, c, 0, 0)
    for f in range(2):
        c = Canvas(7, 5)
        rows = ["#####", ".###.", "..#.."]
        for y, row in enumerate(rows):
            for x, ch in enumerate(row):
                if ch == "#":
                    c.put(x + 1, y + 1 + f, GOLD)
        c.outline(OUT)
        add_sprite("arrow_%d" % f, c, 0, 0)
    g = Canvas(8, 9)
    g.blit(sprites["gem_g_0"][0], 0, -3)
    small_gem = Canvas(7, 9)
    rows = ["..#..", ".###.", "#####", "#####", "#####", ".###.", "..#.."]
    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            if ch == "#":
                small_gem.put(x + 1, y + 1, (80, 210, 96) if x < 3 else (40, 140, 60))
    small_gem.put(2, 3, WHITE)
    small_gem.outline(OUT)
    add_sprite("hud_gem", small_gem, 0, 0)
    k = Canvas(6, 10)
    k.ring(2.5, 2.5, 0.9, 2.3, GOLD)
    k.vline(2, 4, 8, GOLD)
    k.hline(3, 4, 7, GOLD)
    k.outline(OUT)
    add_sprite("hud_key", k, 0, 0)
    bk = Canvas(9, 10)
    bk.ell(4, 3, 3, 2.6, (220, 60, 60))
    bk.vline(4, 5, 8, GOLD)
    bk.hline(5, 6, 7, GOLD)
    bk.outline(OUT)
    add_sprite("hud_bigkey", bk, 0, 0)


# ---------------------------------------------------------------------------------------------
# Font: 5x7 glyphs (lowercase descends 2 rows), 6px advance. tools/make_ui.py turns it into
# the UI font (resources/ui/pixel.ttf).
# ---------------------------------------------------------------------------------------------
FONT = {
    "A": [".###.", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"],
    "B": ["####.", "#...#", "#...#", "####.", "#...#", "#...#", "####."],
    "C": [".###.", "#...#", "#....", "#....", "#....", "#...#", ".###."],
    "D": ["####.", "#...#", "#...#", "#...#", "#...#", "#...#", "####."],
    "E": ["#####", "#....", "#....", "####.", "#....", "#....", "#####"],
    "F": ["#####", "#....", "#....", "####.", "#....", "#....", "#...."],
    "G": [".###.", "#...#", "#....", "#.###", "#...#", "#...#", ".####"],
    "H": ["#...#", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"],
    "I": [".###.", "..#..", "..#..", "..#..", "..#..", "..#..", ".###."],
    "J": ["..###", "...#.", "...#.", "...#.", "...#.", "#..#.", ".##.."],
    "K": ["#...#", "#..#.", "#.#..", "##...", "#.#..", "#..#.", "#...#"],
    "L": ["#....", "#....", "#....", "#....", "#....", "#....", "#####"],
    "M": ["#...#", "##.##", "#.#.#", "#.#.#", "#...#", "#...#", "#...#"],
    "N": ["#...#", "#...#", "##..#", "#.#.#", "#..##", "#...#", "#...#"],
    "O": [".###.", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."],
    "P": ["####.", "#...#", "#...#", "####.", "#....", "#....", "#...."],
    "Q": [".###.", "#...#", "#...#", "#...#", "#.#.#", "#..#.", ".##.#"],
    "R": ["####.", "#...#", "#...#", "####.", "#.#..", "#..#.", "#...#"],
    "S": [".####", "#....", "#....", ".###.", "....#", "....#", "####."],
    "T": ["#####", "..#..", "..#..", "..#..", "..#..", "..#..", "..#.."],
    "U": ["#...#", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."],
    "V": ["#...#", "#...#", "#...#", "#...#", "#...#", ".#.#.", "..#.."],
    "W": ["#...#", "#...#", "#...#", "#.#.#", "#.#.#", "#.#.#", ".#.#."],
    "X": ["#...#", "#...#", ".#.#.", "..#..", ".#.#.", "#...#", "#...#"],
    "Y": ["#...#", "#...#", ".#.#.", "..#..", "..#..", "..#..", "..#.."],
    "Z": ["#####", "....#", "...#.", "..#..", ".#...", "#....", "#####"],
    "a": [".....", ".....", ".###.", "....#", ".####", "#...#", ".####"],
    "b": ["#....", "#....", "####.", "#...#", "#...#", "#...#", "####."],
    "c": [".....", ".....", ".###.", "#....", "#....", "#....", ".###."],
    "d": ["....#", "....#", ".####", "#...#", "#...#", "#...#", ".####"],
    "e": [".....", ".....", ".###.", "#...#", "#####", "#....", ".###."],
    "f": ["..##.", ".#...", ".#...", "####.", ".#...", ".#...", ".#..."],
    "g": [".....", ".....", ".####", "#...#", "#...#", "#...#", ".####", "....#", ".###."],
    "h": ["#....", "#....", "####.", "#...#", "#...#", "#...#", "#...#"],
    "i": ["..#..", ".....", ".##..", "..#..", "..#..", "..#..", ".###."],
    "j": ["...#.", ".....", "..##.", "...#.", "...#.", "...#.", "...#.", "#..#.", ".##.."],
    "k": ["#....", "#....", "#..#.", "#.#..", "##...", "#.#..", "#..#."],
    "l": [".##..", "..#..", "..#..", "..#..", "..#..", "..#..", ".###."],
    "m": [".....", ".....", "##.#.", "#.#.#", "#.#.#", "#.#.#", "#...#"],
    "n": [".....", ".....", "####.", "#...#", "#...#", "#...#", "#...#"],
    "o": [".....", ".....", ".###.", "#...#", "#...#", "#...#", ".###."],
    "p": [".....", ".....", "####.", "#...#", "#...#", "#...#", "####.", "#....", "#...."],
    "q": [".....", ".....", ".####", "#...#", "#...#", "#...#", ".####", "....#", "....#"],
    "r": [".....", ".....", "#.##.", "##..#", "#....", "#....", "#...."],
    "s": [".....", ".....", ".####", "#....", ".###.", "....#", "####."],
    "t": [".#...", ".#...", "####.", ".#...", ".#...", ".#..#", "..##."],
    "u": [".....", ".....", "#...#", "#...#", "#...#", "#..##", ".##.#"],
    "v": [".....", ".....", "#...#", "#...#", "#...#", ".#.#.", "..#.."],
    "w": [".....", ".....", "#...#", "#...#", "#.#.#", "#.#.#", ".#.#."],
    "x": [".....", ".....", "#...#", ".#.#.", "..#..", ".#.#.", "#...#"],
    "y": [".....", ".....", "#...#", "#...#", "#...#", "#...#", ".####", "....#", ".###."],
    "z": [".....", ".....", "#####", "...#.", "..#..", ".#...", "#####"],
    "0": [".###.", "#...#", "#..##", "#.#.#", "##..#", "#...#", ".###."],
    "1": ["..#..", ".##..", "..#..", "..#..", "..#..", "..#..", ".###."],
    "2": [".###.", "#...#", "....#", "...#.", "..#..", ".#...", "#####"],
    "3": ["####.", "....#", "....#", ".###.", "....#", "....#", "####."],
    "4": ["...#.", "..##.", ".#.#.", "#..#.", "#####", "...#.", "...#."],
    "5": ["#####", "#....", "####.", "....#", "....#", "#...#", ".###."],
    "6": ["..##.", ".#...", "#....", "####.", "#...#", "#...#", ".###."],
    "7": ["#####", "....#", "...#.", "..#..", ".#...", ".#...", ".#..."],
    "8": [".###.", "#...#", "#...#", ".###.", "#...#", "#...#", ".###."],
    "9": [".###.", "#...#", "#...#", ".####", "....#", "...#.", ".##.."],
    "!": ["..#..", "..#..", "..#..", "..#..", "..#..", ".....", "..#.."],
    "?": [".###.", "#...#", "....#", "...#.", "..#..", ".....", "..#.."],
    ".": [".....", ".....", ".....", ".....", ".....", ".....", "..#.."],
    ",": [".....", ".....", ".....", ".....", ".....", "..#..", "..#..", ".#..."],
    ":": [".....", "..#..", ".....", ".....", ".....", "..#..", "....."],
    ";": [".....", "..#..", ".....", ".....", ".....", "..#..", "..#..", ".#..."],
    "-": [".....", ".....", ".....", ".###.", ".....", ".....", "....."],
    "+": [".....", "..#..", "..#..", "#####", "..#..", "..#..", "....."],
    "'": ["..#..", "..#..", ".#...", ".....", ".....", ".....", "....."],
    '"': [".#.#.", ".#.#.", ".....", ".....", ".....", ".....", "....."],
    "/": ["....#", "...#.", "...#.", "..#..", ".#...", ".#...", "#...."],
    "(": ["...#.", "..#..", ".#...", ".#...", ".#...", "..#..", "...#."],
    ")": [".#...", "..#..", "...#.", "...#.", "...#.", "..#..", ".#..."],
    "*": [".....", "#.#.#", ".###.", "#####", ".###.", "#.#.#", "....."],
    "=": [".....", ".....", "#####", ".....", "#####", ".....", "....."],
    "<": ["...#.", "..#..", ".#...", "#....", ".#...", "..#..", "...#."],
    ">": [".#...", "..#..", "...#.", "....#", "...#.", "..#..", ".#..."],
    "&": [".##..", "#..#.", "#.#..", ".#...", "#.#.#", "#..#.", ".##.#"],
    "_": [".....", ".....", ".....", ".....", ".....", ".....", ".....", "#####"],
    "[": [".###.", ".#...", ".#...", ".#...", ".#...", ".#...", ".###."],
    "]": [".###.", "...#.", "...#.", "...#.", "...#.", "...#.", ".###."],
    "#": [".#.#.", ".#.#.", "#####", ".#.#.", "#####", ".#.#.", ".#.#."],
    "%": ["##..#", "##.#.", "...#.", "..#..", ".#...", ".#.##", "#..##"],
    "~": [".....", ".....", ".#...", "#.#.#", "...#.", ".....", "....."],
    # \x01 = heart glyph, \x02 = button glyph
    "\x01": [".....", ".#.#.", "#####", "#####", ".###.", "..#..", "....."],
}


# ---------------------------------------------------------------------------------------------
# Packing / output
# ---------------------------------------------------------------------------------------------
def write_tileset(out_dir):
    cols = 16
    rows = (len(tiles) + cols - 1) // cols
    w, h = cols * T, rows * T
    px = [[None] * w for _ in range(h)]
    meta = {"tilewidth": T, "tileheight": T, "columns": cols, "tilecount": len(tiles),
            "imagewidth": w, "imageheight": h, "names": {}, "properties": {}}
    for i, (name, c) in enumerate(tiles):
        ox, oy = (i % cols) * T, (i // cols) * T
        for y in range(T):
            for x in range(T):
                v = c.get(x, y)
                if v is not None:
                    px[oy + y][ox + x] = v
        meta["names"][name] = i
    names = meta["names"]
    for name, props in tile_props.items():
        p = {k: v for k, v in props.items() if v not in (None, False)}
        if "anim" in p:
            p["anim"] = names[p["anim"]]
        meta["properties"][str(names[name])] = p
    write_png(os.path.join(out_dir, "tiles.png"), w, h, px)
    with open(os.path.join(out_dir, "tileset.json"), "w") as f:
        json.dump(meta, f, indent=1, sort_keys=True)
    print("tiles: %d (%dx%d)" % (len(tiles), w, h))


def write_atlas(out_dir):
    items = sorted(sprites.items(), key=lambda kv: (-kv[1][0].h, kv[0]))
    width = 512
    x = y = shelf = 0
    placed = {}
    for name, (c, px, py) in items:
        if x + c.w + 1 > width:
            x = 0
            y += shelf + 1
            shelf = 0
        placed[name] = (x, y)
        x += c.w + 1
        shelf = max(shelf, c.h)
    height = y + shelf + 1
    height = 1 << (height - 1).bit_length()
    pix = [[None] * width for _ in range(height)]
    meta = {"width": width, "height": height, "sprites": {}}
    for name, (c, px, py) in items:
        ox, oy = placed[name]
        for yy in range(c.h):
            for xx in range(c.w):
                v = c.get(xx, yy)
                if v is not None:
                    pix[oy + yy][ox + xx] = v
        meta["sprites"][name] = {"x": ox, "y": oy, "w": c.w, "h": c.h, "px": px, "py": py}
    write_png(os.path.join(out_dir, "sprites.png"), width, height, pix)
    with open(os.path.join(out_dir, "sprites.json"), "w") as f:
        json.dump(meta, f, indent=0, sort_keys=True)
    print("sprites: %d (%dx%d)" % (len(sprites), width, height))


def main():
    out_dir = sys.argv[1] if len(sys.argv) > 1 else "resources/textures"
    os.makedirs(out_dir, exist_ok=True)
    make_tiles()
    make_people()
    make_sword()
    make_enemies()
    make_objects()
    make_fx()
    make_hud()
    write_tileset(out_dir)
    write_atlas(out_dir)


if __name__ == "__main__":
    main()
