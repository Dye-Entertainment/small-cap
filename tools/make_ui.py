#!/usr/bin/env python3
"""Generates the UI assets:

  pixel.ttf     the game's 5x7 pixel font (from make_art.FONT) as a TrueType font, so the RmlUi
                documents can use it. One font pixel is 100 units on a 1000 unit em, so at a font
                size of 10dp every font pixel lands on one game pixel.
  sprites.rcss  an RmlUi sprite sheet with every sprite of textures/sprites.json

Standard library only, like the other asset scripts.
"""
import json
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from make_art import FONT  # noqa: E402

UNITS = 1000
PIXEL = 100          # font units per font pixel
ASCENT = 7           # rows above the baseline
DESCENT = 3          # rows below it (descenders use two, one is spacing)
ADVANCE = 6          # pixels
FAMILY = "Pixel"
# Characters that make_art stores under control codes.
SPECIAL = {"\x01": 0x2665}  # heart


def rectangles(rows):
    """Covers the '#' pixels with rectangles: runs per row, merged down when identical."""
    runs = []
    for y, row in enumerate(rows):
        x = 0
        while x < len(row):
            if row[x] == "#":
                start = x
                while x < len(row) and row[x] == "#":
                    x += 1
                runs.append([start, y, x, y + 1])
            else:
                x += 1
    merged = []
    for run in runs:
        for rect in merged:
            if rect[0] == run[0] and rect[2] == run[2] and rect[3] == run[1]:
                rect[3] = run[3]
                break
        else:
            merged.append(run)
    return merged


def glyph_data(rows):
    """TrueType simple glyph: one clockwise square contour per rectangle."""
    rects = rectangles(rows) if rows else []
    if not rects:
        return b"", (0, 0, 0, 0)
    points = []
    ends = []
    for x0, y0, x1, y1 in rects:
        left, right = x0 * PIXEL, x1 * PIXEL
        top, bottom = (ASCENT - y0) * PIXEL, (ASCENT - y1) * PIXEL
        points += [(left, bottom), (left, top), (right, top), (right, bottom)]
        ends.append(len(points) - 1)
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    box = (min(xs), min(ys), max(xs), max(ys))
    data = struct.pack(">hhhhh", len(ends), *box)
    data += struct.pack(">%dH" % len(ends), *ends)
    data += struct.pack(">H", 0)  # no instructions
    data += bytes([0x01] * len(points))  # on-curve, 16-bit deltas
    last = 0
    for x in xs:
        data += struct.pack(">h", x - last)
        last = x
    last = 0
    for y in ys:
        data += struct.pack(">h", y - last)
        last = y
    while len(data) % 4:
        data += b"\0"
    return data, box


def checksum(data):
    data += b"\0" * ((4 - len(data) % 4) % 4)
    return sum(struct.unpack(">%dI" % (len(data) // 4), data)) & 0xFFFFFFFF


def build_font():
    chars = sorted((SPECIAL.get(ch, ord(ch)), rows) for ch, rows in FONT.items())
    chars = [(0x20, None)] + [c for c in chars if c[0] != 0x20]
    # Glyph 0 is .notdef: an empty box.
    notdef = ["#####", "#...#", "#...#", "#...#", "#...#", "#...#", "#####"]
    glyphs = [notdef] + [rows for _, rows in chars]
    codes = [code for code, _ in chars]

    glyf = b""
    loca = []
    boxes = []
    max_points = max_contours = 0
    for rows in glyphs:
        loca.append(len(glyf))
        data, box = glyph_data(rows)
        glyf += data
        boxes.append(box)
        if rows:
            rects = rectangles(rows)
            max_points = max(max_points, len(rects) * 4)
            max_contours = max(max_contours, len(rects))
    loca.append(len(glyf))
    count = len(glyphs)
    x_min = min(b[0] for b in boxes)
    y_min = min(b[1] for b in boxes)
    x_max = max(b[2] for b in boxes)
    y_max = max(b[3] for b in boxes)

    head = struct.pack(
        ">IIIIHHqqhhhhHHhhh", 0x00010000, 0x00010000, 0, 0x5F0F3CF5, 0x000B, UNITS, 0, 0,
        x_min, y_min, x_max, y_max, 0, 6, 2, 1, 0)
    hhea = struct.pack(
        ">IhhhHhhhhhhhhhhhH", 0x00010000, ASCENT * PIXEL, -DESCENT * PIXEL, 0, ADVANCE * PIXEL,
        0, 0, x_max, 1, 0, 0, 0, 0, 0, 0, 0, count)
    maxp = struct.pack(">IHHHHHHHHHHHHHH", 0x00010000, count, max_points, max_contours,
                       0, 0, 2, 0, 0, 0, 0, 0, 0, 0, 0)
    hmtx = b"".join(struct.pack(">Hh", ADVANCE * PIXEL, box[0]) for box in boxes)
    loca_table = struct.pack(">%dI" % len(loca), *loca)

    # cmap format 4: one segment per character, then the 0xFFFF terminator.
    segments = [(code, code, (index + 1 - code) & 0xFFFF) for index, code in enumerate(codes)]
    segments.append((0xFFFF, 0xFFFF, 1))
    seg_count = len(segments)
    search = 2 * (1 << (seg_count.bit_length() - 1))
    selector = search.bit_length() - 2
    sub = struct.pack(">HHHHHHH", 4, 0, 0, seg_count * 2, search, selector, seg_count * 2 - search)
    sub += b"".join(struct.pack(">H", s[1]) for s in segments) + b"\0\0"
    sub += b"".join(struct.pack(">H", s[0]) for s in segments)
    sub += b"".join(struct.pack(">H", s[2]) for s in segments)
    sub += b"\0\0" * seg_count
    sub = sub[:2] + struct.pack(">H", len(sub)) + sub[4:]
    cmap = struct.pack(">HHHHI", 0, 1, 3, 1, 12) + sub

    names = {1: FAMILY, 2: "Regular", 3: FAMILY + " Regular", 4: FAMILY, 5: "Version 1.0",
             6: FAMILY}
    strings = b""
    records = b""
    for name_id, text in sorted(names.items()):
        encoded = text.encode("utf-16-be")
        records += struct.pack(">HHHHHH", 3, 1, 0x409, name_id, len(encoded), len(strings))
        strings += encoded
    name = struct.pack(">HHH", 0, len(names), 6 + len(records)) + records + strings

    post = struct.pack(">IIhhIIIII", 0x00030000, 0, -PIXEL, PIXEL, 1, 0, 0, 0, 0)

    os2 = struct.pack(
        ">HhHHHhhhhhhhhhhh10sIIII4sHHHhhhHHII",
        1, ADVANCE * PIXEL, 400, 5, 0, 500, 500, 0, 0, 500, 500, 0, 0, 50, 300, 0,
        b"\0" * 10, 0, 0, 0, 0, b"NONE", 0x40, 0x20, 0x2665, ASCENT * PIXEL, -DESCENT * PIXEL, 0,
        ASCENT * PIXEL, DESCENT * PIXEL, 1, 0)

    tables = {"OS/2": os2, "cmap": cmap, "glyf": glyf, "head": head, "hhea": hhea,
              "hmtx": hmtx, "loca": loca_table, "maxp": maxp, "name": name, "post": post}
    tags = sorted(tables)
    num = len(tags)
    search = 16 * (1 << (num.bit_length() - 1))
    font = struct.pack(">IHHHH", 0x00010000, num, search, search.bit_length() - 5, num * 16 - search)
    offset = 12 + 16 * num
    directory = b""
    body = b""
    head_offset = 0
    for tag in tags:
        data = tables[tag]
        directory += struct.pack(">4sIII", tag.encode("ascii"), checksum(data), offset + len(body),
                                 len(data))
        if tag == "head":
            head_offset = offset + len(body)
        body += data + b"\0" * ((4 - len(data) % 4) % 4)
    font += directory + body
    adjustment = (0xB1B0AFBA - checksum(font)) & 0xFFFFFFFF
    font = font[:head_offset + 8] + struct.pack(">I", adjustment) + font[head_offset + 12:]
    return font


def build_sprite_sheet(atlas_json, image_path):
    with open(atlas_json) as f:
        atlas = json.load(f)
    lines = ["/* Generated by tools/make_ui.py from textures/sprites.json. */",
             "@spritesheet sprites", "{", "    src: %s;" % image_path]
    for name, s in sorted(atlas["sprites"].items()):
        lines.append("    %s: %dpx %dpx %dpx %dpx;" % (name.replace("_", "-"), s["x"], s["y"], s["w"], s["h"]))
    lines.append("}")
    return "\n".join(lines) + "\n"


def main():
    resources = sys.argv[1] if len(sys.argv) > 1 else "resources"
    out_dir = os.path.join(resources, "ui")
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "pixel.ttf"), "wb") as f:
        f.write(build_font())
    sheet = build_sprite_sheet(os.path.join(resources, "textures", "sprites.json"),
                               "../textures/sprites.png")
    with open(os.path.join(out_dir, "sprites.rcss"), "w") as f:
        f.write(sheet)
    print("ui: pixel.ttf (%d glyphs), sprites.rcss" % (len(FONT) + 1))


if __name__ == "__main__":
    main()
