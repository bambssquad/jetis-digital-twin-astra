"""Generate the Astra scene from source-measured layout geometry.

The DWG supplies the site boundary and phase footprints. Interior use,
structure above the shown outline, landscaping, and equipment are visual
assumptions listed in scene.json and STATE.md.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "analysis" / "geometry.json"
OUT_SCENE = ROOT / "web" / "dist" / "assets" / "scene.json"
OUT_PROJECT = ROOT / "web" / "dist" / "project.json"
OX, OY = 2207.9734130790184, 1532.7302629559754
Z_FLOOR = 0.0
EAVE = 9.0
RIDGE = 13.5
ELEMENTS: list[dict] = []
ID = 0


def add(kind: str, group: str, name: str, mat: str, **data) -> dict:
    global ID
    ID += 1
    e = {"id": f"A-{ID:05d}", "kind": kind, "group": group,
         "name": name, "mat": mat, **data}
    ELEMENTS.append(e)
    return e


def box(group, name, mat, p, s, collision=None, motion=None):
    extra = {}
    if collision:
        extra["collision"] = collision
    if motion:
        extra["motion"] = motion
    return add("box", group, name, mat, p=[round(v, 3) for v in p],
               s=[round(v, 3) for v in s], **extra)


def beam(group, name, mat, a, b, w, h, section="beam", tw=None, tf=None):
    return add(section, group, name, mat,
               a=[round(v, 3) for v in a], b=[round(v, 3) for v in b],
               w=round(w, 4), h=round(h, 4), tw=round(tw or w * .08, 4),
               tf=round(tf or h * .06, 4))


def prism(group, name, mat, points, th, collision=None):
    extra = {"collision": collision} if collision else {}
    return add("prism", group, name, mat,
               points=[[round(v, 3) for v in p] for p in points],
               th=round(th, 3), **extra)


def source_xy(entity: dict) -> list[tuple[float, float]]:
    vals = entity.get("points", [])
    return [(vals[i] - OX, vals[i + 1] - OY)
            for i in range(0, len(vals) - 1, 2)]


def bounds(poly):
    xs, ys = zip(*poly)
    return min(xs), min(ys), max(xs), max(ys)


def polygon_area(poly):
    return sum(poly[i][0] * poly[(i + 1) % len(poly)][1] -
               poly[(i + 1) % len(poly)][0] * poly[i][1]
               for i in range(len(poly))) / 2


def triangles(poly):
    """Ear-clip a simple polygon to support the concave surveyed site edge."""
    poly = list(poly)
    if polygon_area(poly) < 0:
        poly.reverse()

    def cross(a, b, c):
        return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])

    def in_tri(p, a, b, c):
        return (cross(a, b, p) >= -1e-8 and cross(b, c, p) >= -1e-8 and
                cross(c, a, p) >= -1e-8)

    indices = list(range(len(poly)))
    result = []
    while len(indices) > 3:
        found = False
        for k, cur in enumerate(indices):
            prev, nxt = indices[k - 1], indices[(k + 1) % len(indices)]
            a, b, c = poly[prev], poly[cur], poly[nxt]
            if cross(a, b, c) <= 1e-8:
                continue
            if any(in_tri(poly[j], a, b, c)
                   for j in indices if j not in (prev, cur, nxt)):
                continue
            result.append((a, b, c))
            indices.pop(k)
            found = True
            break
        if not found:
            raise ValueError("Site boundary cannot be triangulated without changing its shape")
    result.append(tuple(poly[i] for i in indices))
    return result


def main():
    raw = json.loads(SRC.read_text(encoding="utf-8-sig"))
    if raw["source_sha256"].lower() != "793d4ec07d86248e5912676eea1f0c5720186aceacdef0ef97ef004aa138faf5":
        raise ValueError("Source hash differs from the approved Astra source copy")
    by_handle = {e.get("handle"): e for e in raw["entities"]}
    # The unchanged layout polygons received new DWG handles. The legacy
    # pass keeps unaffected furniture/site IDs; R02 then replaces source scope.
    from revision_scene import HANDLE_MAP, apply_revision
    by_handle.update({old: by_handle[new] for old, new in HANDLE_MAP.items()})

    source_site = source_xy(by_handle["16551"])
    # This open polyline repeats its first vertex as the final one.
    if math.dist(source_site[0], source_site[-1]) < .01:
        source_site.pop()
    if len(source_site) < 6:
        raise ValueError("Source site outline is incomplete")
    if polygon_area(source_site) < 0:
        source_site.reverse()

    source_footprints = {
        "Tahap 1 — Pengolahan utama 78 × 30 m": "165A7",
        "Tahap 1 — Gudang dingin 84 × 30 m": "165AA",
        "Tahap 1 — Sayap layanan 36 × 30 m (sisi atas layout)": "1657E",
        "Tahap 1 — Sayap layanan 36 × 30 m (sisi bawah layout)": "16582",
        "Tahap 2 — Ekspansi 84 × 36 m": "1656E",
    }
    measured = {name: source_xy(by_handle[handle])
                for name, handle in source_footprints.items()}
    specs = []
    for name, handle in source_footprints.items():
        poly = measured[name]
        x0, y0, x1, y1 = bounds(poly)
        specs.append({"name": name, "handle": handle, "poly": poly,
                      "x": x0, "y": y0, "w": x1 - x0, "d": y1 - y0,
                      "phase": 2 if handle == "1656E" else 1})

    materials = {
        "soil": {"color": "#858b72", "roughness": .98},
        "asphalt": {"color": "#414a4c", "roughness": .88, "texture": "Asphalt012", "tile": 4},
        "concrete": {"color": "#b8b9b2", "roughness": .82, "texture": "Concrete034", "tile": 2.2},
        "floor": {"color": "#d7dbd5", "roughness": .72, "texture": "Concrete034", "tile": 1.4},
        "steel": {"color": "#40535b", "roughness": .34, "metalness": .7, "texture": "Metal032", "tile": .9},
        "roof": {"color": "#cbd3d4", "roughness": .38, "metalness": .48, "texture": "Metal032", "tile": 1.3},
        "wall": {"color": "#e8ece8", "roughness": .58, "metalness": .16, "texture": "Metal032", "tile": 1.5},
        "trim": {"color": "#334951", "roughness": .4, "metalness": .6},
        "door": {"color": "#52727a", "roughness": .42, "metalness": .32, "texture": "Metal032", "tile": 1.2},
        "glass": {"color": "#8fc1c6", "roughness": .16, "metalness": .12, "opacity": .42},
        "stainless": {"color": "#bbc6c4", "roughness": .27, "metalness": .82, "texture": "Metal032", "tile": .65},
        "belt": {"color": "#27383a", "roughness": .75},
        "cold": {"color": "#9fb9bd", "roughness": .46, "metalness": .12},
        "wood": {"color": "#9b7752", "roughness": .72, "texture": "Wood049", "tile": 1.3},
        "marking": {"color": "#eadcae", "roughness": .8},
        "water": {"color": "#6babb1", "roughness": .2, "metalness": .14, "opacity": .76},
        "leaf": {"color": "#54704c", "roughness": .92},
        "bark": {"color": "#715b46", "roughness": .95},
        "produce": {"color": "#93a96d", "roughness": .73},
        "light": {"color": "#f2cc83", "roughness": .3, "emissive": "#f1bd68"},
    }

    # Source-measured site surface, triangulated to keep the concave boundary.
    for i, tri in enumerate(triangles(source_site), 1):
        prism("Tapak | tanah", f"Bidang tapak {i:02d}", "soil",
              [[x, y, -.18] for x, y in tri], .18)

    # Buildings are made from the exact five source outlines. Any shell depth
    # or roof profile is a documented visual inference from the section notes.
    motion_specs = []
    door_defs = {s["handle"]: [] for s in specs}
    roof_groups, interior_groups = [], []
    process_names = {
        "165A7": ("Pengolahan dan pembekuan ikan", "Tahap 1"),
        "165AA": ("Gudang dingin dan distribusi", "Tahap 1"),
        "1657E": ("QC, sanitasi dan ruang staf", "Tahap 1"),
        "16582": ("Utilitas dan persiapan bahan", "Tahap 1"),
        "1656E": ("Ekspansi pengolahan", "Tahap 2"),
    }

    def purlin_roof(spec, name):
        x, y, w, d = spec["x"], spec["y"], spec["w"], spec["d"]
        mid = y + d / 2
        for side in (0, 1):
            for j in range(4):
                t = j / 3
                yy = y + (mid - y) * t if side == 0 else mid + (y + d - mid) * t
                zz = EAVE + (RIDGE - EAVE) * (t if side == 0 else 1 - t)
                beam("Struktur | " + name, f"Gording CNP125 {j+1}", "steel",
                     [x, yy, zz], [x + w, yy, zz], .125, .05, "cnp", .005, .006)

    for spec in specs:
        name, handle = spec["name"], spec["handle"]
        x, y, w, d = spec["x"], spec["y"], spec["w"], spec["d"]
        x1, y1 = x + w, y + d
        midy = y + d / 2
        label, phase = process_names[handle]
        phasegroup = "Tahap 2" if spec["phase"] == 2 else "Tahap 1"
        shell = "Selubung | " + name
        structure = "Struktur | " + name
        interior = "Interior | " + name
        roof = "Atap | " + name
        slabgroup = "Lantai | " + name
        interior_groups.append(interior)
        roof_groups.append(roof)

        # Floor slab uses the measured outline, not a guessed rectangular area.
        prism(slabgroup, "Lantai beton 150 mm — " + name, "floor",
              [[px, py, 0.0] for px, py in spec["poly"]], .14, collision="floor")
        box("Fondasi | " + name, "Poer tepi — " + name, "concrete",
            [x, y, -.20], [w, .45, .42])
        # Upper stage-1 footprints share their south wall with the lower row.
        # Put their loading doors on the opposite, open-yard-facing wall.
        door_side = "+Y" if handle in ("165A7", "1657E") else "-Y"
        door_y = y1 if door_side == "+Y" else y
        wall_y = door_y - .14
        door_xs = [x + 21, x + 45, x + 69]
        door_w = 4.8 if w >= 60 else 4.0
        if w < 50:
            door_xs = [x + 15]
        slots = []
        for j, cx in enumerate(door_xs, 1):
            midx = cx - door_w / 2
            motion = f"door_{handle.lower()}_{j}"
            slots.append((midx, midx + door_w, motion))
            door_defs[handle].append(motion)
            motion_specs.append({"id": motion, "label": f"Pintu loading {phasegroup} {j}",
                                 "kind": "roll", "travel": 4.7,
                                 "opening_side": door_side,
                                 "anchor": [round(cx, 3), round(door_y, 3)],
                                 "top": 4.65,
                                 "bounds": [round(midx, 3), round(door_y - .15, 3), .15,
                                            round(door_w, 3), .25, 4.5]})
        cursor = x
        for j, (a, b, motion) in enumerate(slots, 1):
            if a > cursor:
                box(shell, f"Dinding sisi {door_side} {j} — {name}", "wall",
                    [cursor, wall_y, .12], [a - cursor, .28, EAVE - .12], collision="wall")
            box(shell, f"Pintu gulung {j} — {name}", "door",
                [a, door_y - .11, .12], [b - a, .20, 4.5], motion=motion)
            cursor = b
        if cursor < x1:
            box(shell, f"Dinding sisi {door_side} akhir — {name}", "wall",
                [cursor, wall_y, .12], [x1 - cursor, .28, EAVE - .12], collision="wall")
        opposite_side = "-Y" if door_side == "+Y" else "+Y"
        opposite_y = y if door_side == "+Y" else y1
        box(shell, f"Dinding sisi {opposite_side} — {name}", "wall",
            [x, opposite_y - .14, .12], [w, .28, EAVE - .12], collision="wall")
        box(shell, "Dinding ujung barat — " + name, "wall",
            [x - .14, y, .12], [.28, d, EAVE - .12], collision="wall")
        box(shell, "Dinding ujung timur — " + name, "wall",
            [x1 - .14, y, .12], [.28, d, EAVE - .12], collision="wall")

        # Gable panels and two sloped roof planes.
        for endx, direction in ((x, "X−"), (x1 - .15, "X+")):
            prism(shell, f"Dinding gevel {direction} — {name}", "wall",
                  [[endx, y, EAVE], [endx, midy, RIDGE], [endx, y1, EAVE]], .15)
        for side, pts in (
            ("Y−", [[x, y, EAVE], [x1, y, EAVE], [x1, midy, RIDGE], [x, midy, RIDGE]]),
            ("Y+", [[x, midy, RIDGE], [x1, midy, RIDGE], [x1, y1, EAVE], [x, y1, EAVE]]),
        ):
            prism(roof, f"Atap galvalum {side} — {name}", "roof", pts, .12)
        beam(roof, "Nok atap — " + name, "trim",
             [x, midy, RIDGE], [x1, midy, RIDGE], .20, .18)
        for side_y in (y, y1):
            beam(shell, "Talang air — " + name, "trim",
                 [x, side_y, EAVE - .08], [x1, side_y, EAVE - .08], .16, .14)
        for xx in (x + .6, x1 - .6):
            for yy in (y + .6, y1 - .6):
                beam(shell, "Pipa hujan — " + name, "trim",
                     [xx, yy, .12], [xx, yy, EAVE - .15], .11, .09)

        # Six-metre portal frames. The source notes identify WF350 columns,
        # WF300 rafters, and CNP125 purlins; section thickness is visual scale.
        bay_count = max(1, round(w / 6))
        for i in range(bay_count + 1):
            xx = x + w * i / bay_count
            for side_y in (y + .35, y1 - .35):
                beam(structure, "Kolom WF350", "steel",
                     [xx, side_y, .10], [xx, side_y, EAVE], .35, .35, "wf", .012, .020)
                box(structure, "Pelat alas kolom", "steel",
                    [xx - .28, side_y - .28, -.02], [.56, .56, .10])
            beam(structure, "Kuda-kuda WF300 — bawah", "steel",
                 [xx, y + .35, EAVE - .10], [xx, y1 - .35, EAVE - .10], .30, .30, "wf", .011, .018)
            beam(structure, "Kuda-kuda WF300 — lereng selatan", "steel",
                 [xx, y + .35, EAVE], [xx, midy, RIDGE - .10], .30, .30, "wf", .011, .018)
            beam(structure, "Kuda-kuda WF300 — lereng utara", "steel",
                 [xx, midy, RIDGE - .10], [xx, y1 - .35, EAVE], .30, .30, "wf", .011, .018)
            for yy in (y + d * .27, midy, y + d * .73):
                topz = EAVE + (RIDGE - EAVE) * (1 - abs(yy - midy) / (d / 2))
                beam(structure, "Web kuda-kuda", "steel",
                     [xx, yy, EAVE + .08], [xx, yy, topz - .18], .10, .10)
        purlin_roof(spec, name)

        # A measured service label helps keep each phase distinct in both files.
        lx, ly = (x + w / 2, y + d / 2)
        labels = [{"text": label, "p": [round(lx, 2), round(ly, 2), 1.2]},
                  {"text": phasegroup + " · " + name.split("—")[-1].strip(),
                   "p": [round(lx, 2), round(ly, 2), EAVE + .65]}]

        # Inferred food-safe processing, cold storage, QC and staff fit-out.
        if handle == "165A7":
            # Hygienic fish line, stainless tables, wash tanks and packing lane.
            for lane, yy in enumerate((y + 5.5, y + 11.5, y + 17.5, y + 23.5), 1):
                box(interior, f"Conveyor proses {lane}", "belt",
                    [x + 7, yy, .92], [w - 14, .90, .18])
                for xx in range(0, int(w - 13), 6):
                    box(interior, "Dudukan conveyor", "stainless",
                        [x + 8 + xx, yy + .12, .18], [.12, .12, .74])
                for station in range(5):
                    xx = x + 9 + station * (w - 20) / 4
                    box(interior, f"Meja sortir {lane}.{station+1}", "stainless",
                        [xx, yy + 1.4, .86], [2.5, 1.0, .08])
                    for dx in (.12, 2.22):
                        for dy in (.12, .78):
                            box(interior, "Kaki meja food-grade", "stainless",
                                [xx + dx, yy + 1.5 + dy, .12], [.08, .08, .74])
            for j in range(3):
                xx = x + 8 + j * 8
                box(interior, "Bak pencucian ikan", "water",
                    [xx, y + 1.1, .72], [4.4, 2.2, .75])
                box(interior, "Bib stainless bak", "stainless",
                    [xx - .08, y + 1.02, 1.44], [4.56, 2.36, .12])
            for j in range(7):
                xx = x + 11 + j * 8
                box(interior, "Ruang blast freezer", "cold",
                    [xx, y + d - 5.4, .1], [6.2, 4.8, 3.8])
                box(interior, "Panel pintu freezer", "door",
                    [xx + 2.25, y + d - 5.5, .15], [1.7, .14, 3.2])
                box(interior, "Evaporator freezer", "stainless",
                    [xx + 1.9, y + d - 5.0, 3.4], [2.4, .9, .35])
            box(interior, "Dinding higienis zona cuci", "wall",
                [x + 32, y + 2, .1], [.14, d - 4, 3.2])
            box(interior, "Dinding higienis zona kemas", "wall",
                [x + 53, y + 2, .1], [.14, d - 4, 3.2])
            for j in range(12):
                xx = x + 10 + (j % 6) * 10
                yy = y + 7 + (j // 6) * 10
                box(interior, "Pallet ikan dalam cold box", "produce",
                    [xx, yy, .14], [1.2, 1.0, .85])

        elif handle == "165AA":
            # High-bay freezer warehouse. Rack aisles leave a clear forklift loop.
            for row, yy in enumerate((y + 4.5, y + 12.0, y + 19.5, y + 26.0), 1):
                box(interior, f"Rak gudang rel bawah {row}", "steel",
                    [x + 6, yy, .15], [w - 12, .10, 7.0])
                box(interior, f"Rak gudang rel atas {row}", "steel",
                    [x + 6, yy + 1.55, .15], [w - 12, .10, 7.0])
                for bay in range(1, 5):
                    zz = bay * 1.45
                    box(interior, f"Balok rak level {bay}", "steel",
                        [x + 6, yy - .35, zz], [w - 12, .82, .08])
                for j in range(int((w - 12) / 3) + 1):
                    xx = x + 6 + j * 3
                    box(interior, "Tiang rak palet", "steel",
                        [xx, yy - .12, .15], [.10, 1.9, 7.0])
                for j in range(0, int((w - 14) / 6), 2):
                    xx = x + 8 + j * 3
                    box(interior, "Palet produk beku", "cold",
                        [xx, yy + .25, .35], [1.05, .92, 1.15])
            box(interior, "Ruang kontrol temperatur", "cold",
                [x + w - 8, y + 2, .1], [6.5, 4.0, 3.6])

        elif handle == "1657E":
            # The north service wing includes a modest two-level staff / QC bay.
            box(interior, "Partisi ruang QC", "wall",
                [x + 17.8, y + 1.0, .1], [.15, d - 2, 4.1])
            box(interior, "Pelat lantai dua ruang staf", "floor",
                [x + 18, y + 2, 4.45], [17.2, d - 4, .18], collision="floor")
            for i, yy in enumerate((y + 6, y + 14, y + 22), 1):
                box(interior, f"Meja QC {i}", "wood",
                    [x + 3, yy, .82], [4.2, 1.4, .08])
                for xx in (x + 3.2, x + 6.8):
                    box(interior, "Meja kaki QC", "steel",
                        [xx, yy + .2, .12], [.08, .08, .7])
            for j in range(4):
                box(interior, "Ruang ganti staf", "cold",
                    [x + 21 + (j % 2) * 6.5, y + 4 + (j // 2) * 10, 4.66],
                    [5.8, 8.4, 2.7])
            # External strip glazing and a shaded staff entrance.
            for j in range(5):
                box(shell, "Jendela pita ruang staf", "glass",
                    [x + 20 + j * 3.1, y - .16, 5.2], [2.0, .04, 1.15], collision="none")

        elif handle == "16582":
            for j in range(4):
                yy = y + 4 + j * 6
                box(interior, f"Tangki utilitas stainless {j+1}", "stainless",
                    [x + 5, yy, .2], [6.0, 4.0, 2.4])
                box(interior, f"Pipa penghubung utilitas {j+1}", "water",
                    [x + 13, yy + 1.7, 2.3], [13.0, .18, .18])
            box(interior, "Ruang mesin pendingin", "cold",
                [x + 23, y + 7, .1], [10, 15, 4.2])
            for j in range(3):
                box(interior, "Kompresor pendingin", "steel",
                    [x + 24 + j * 2.8, y + 9, .22], [1.9, 2.4, 2.1])

        else:  # source handle 1656E: tahap 2
            # Second-stage line extends the same cold chain with packing and dispatch.
            for lane, yy in enumerate((y + 7, y + 17, y + 27), 1):
                box(interior, f"Jalur kemas ekspansi {lane}", "belt",
                    [x + 7, yy, .94], [w - 14, 1.05, .18])
                for station in range(8):
                    xx = x + 8 + station * 9.5
                    box(interior, "Meja kemas stainless", "stainless",
                        [xx, yy + 1.6, .9], [2.2, 1.1, .09])
                    box(interior, "Karton produk laut", "wood",
                        [xx + .35, yy + 1.9, .99], [.65, .55, .55])
            for j in range(8):
                xx = x + 8 + j * 9
                box(interior, "Unit ruang pembeku modular", "cold",
                    [xx, y + 1.0, .12], [6.8, 3.9, 3.7])
            box(interior, "Partisi sanitasi ekspansi", "wall",
                [x + 28, y + 4.5, .1], [.15, d - 9, 3.4])

        # High-bay linear lighting, roof ventilators and four-way logistics aisle.
        for j in range(max(2, int(w / 18))):
            xx = x + 8 + j * 18
            for yy in (y + d * .36, y + d * .64):
                box(interior, "Lampu high-bay", "light",
                    [xx, yy, 8.25], [1.4, .18, .07])
                # Hanging housings are visual fixtures; dynamic light is viewer-only.
        for yy in (y + 4, y + d - 4):
            add("cylinder", roof, "Ventilator atap", "steel",
                p=[x + w / 2, yy, EAVE + 3.5], r=.40, h=.65)
        labels.extend([])
        if handle == "165A7":
            labels.append({"text": "Penerimaan · sortasi · cuci · pembekuan · kemas",
                           "p": [x + w / 2, y + d / 2, 2.1]})
        if handle == "165AA":
            labels.append({"text": "Penyimpanan rantai dingin",
                           "p": [x + w / 2, y + d / 2, 2.2]})
        if handle == "1656E":
            labels.append({"text": "Perluasan tahap 2 · asumsi fungsi",
                           "p": [x + w / 2, y + d / 2, 2.2]})

        if "ALL_LABELS" not in globals():
            globals()["ALL_LABELS"] = []
        ALL_LABELS.extend(labels)

    # Security gate, guard post, yard and exterior parking are source-labelled.
    # Positions follow label anchors; exact dimensions are visual assumptions.
    gate_x, gate_y = 111.2, .1
    box("Tapak | gerbang", "Tiang gerbang barat", "trim", [gate_x - 4.5, gate_y - .35, 0], [.35, .7, 2.6])
    box("Tapak | gerbang", "Tiang gerbang timur", "trim", [gate_x + 4.15, gate_y - .35, 0], [.35, .7, 2.6])
    gate_motion = "gate_main"
    box("Tapak | gerbang", "Daun gerbang geser", "door",
        [gate_x - 4.1, gate_y - .20, .15], [8.0, .16, 1.8], motion=gate_motion)
    motion_specs.append({"id": gate_motion, "label": "Gerbang utama", "kind": "slide",
                         "travel": 4.3, "delta": [-4.3, 0, 0],
                         "anchor": [gate_x, gate_y],
                         "bounds": [gate_x - 4.1, gate_y - .2, .15, 8.0, .16, 1.8]})
    # Vehicle access from the south boundary to the first warehouse row.
    box("Tapak | sirkulasi", "Jalan masuk utama", "asphalt",
        [gate_x - 6, -17, -.10], [12, 43, .12], collision="floor")
    box("Tapak | sirkulasi", "Apron bongkar muat tahap 1", "concrete",
        [53, 18.8, -.06], [80, 4.2, .08], collision="floor")
    # External car parking marked with the exact source label.
    box("Tapak | parkir", "Pelataran parkir luar", "asphalt",
        [118, 2.5, -.08], [37, 16, .10], collision="floor")
    for i in range(8):
        xx = 121 + i * 4.3
        box("Tapak | parkir", f"Garis parkir {i+1}", "marking",
            [xx, 3.2, .025], [.10, 13.7, .018])
    box("Tapak | parkir", "Garis pembatas parkir", "marking",
        [120.8, 3.0, .025], [34.5, .12, .018])
    # Gatehouse labelled POS, aligned beside the vehicle entrance.
    box("Tapak | pos", "Lantai pos jaga", "concrete", [97.2, 1.3, -.03], [3.5, 4.2, .12])
    box("Tapak | pos", "Dinding pos jaga", "wall", [97.2, 1.3, .09], [3.5, 4.2, 2.75])
    box("Tapak | pos", "Jendela pos jaga", "glass", [100.72, 1.65, 1.0], [.05, 1.65, 1.35])
    box("Tapak | pos", "Atap pos jaga", "roof", [96.8, 1.0, 2.84], [4.3, 4.8, .14])
    box("Tapak | panel", "Pondasi panel listrik", "concrete", [139.0, 103.8, -.1], [2.4, 2.4, .3])
    box("Tapak | panel", "Panel listrik", "steel", [139.2, 104.0, .20], [2.0, 2.0, 2.3])
    ALL_LABELS.extend([
        {"text": "POS / kontrol kendaraan", "p": [99.0, 6.4, 3.2]},
        {"text": "Gerbang masuk kawasan", "p": [gate_x, -3.0, 2.8]},
        {"text": "Parkir luar", "p": [136.5, 10, .6]},
        {"text": "Panel utama", "p": [140.2, 106.6, 2.8]},
    ])

    # Site edge, public road frontage, and restrained planted margins.
    boundary = source_site
    for i, a in enumerate(boundary):
        b = boundary[(i + 1) % len(boundary)]
        beam("Tapak | pagar", f"Pagar batas ruas {i+1}", "trim",
             [a[0], a[1], 1.0], [b[0], b[1], 1.0], .065, 1.8)
        for k in range(max(1, int(math.dist(a, b) / 3))):
            t = k / max(1, int(math.dist(a, b) / 3))
            xx, yy = a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t
            box("Tapak | pagar", "Tiang pagar", "steel",
                [xx - .055, yy - .055, 0], [.11, .11, 1.9])
    # Southern service road is a visual site-context assumption.
    box("Tapak | jalan", "Jalan depan kawasan", "asphalt",
        [65, -17.0, -.13], [100, 7.0, .10], collision="floor")
    box("Tapak | jalan", "Bahu jalan beton", "concrete",
        [65, -9.82, -.12], [100, .65, .08])

    trees = [(7, 18), (9, 40), (7, 66), (12, 91), (15, 117), (18, 137),
             (25, 8), (47, 8), (71, 8), (92, 7), (119, 1), (153, 21),
             (156, 43), (155, 67), (156, 88), (151, 119), (142, 140), (113, 139)]
    for i, (tx, ty) in enumerate(trees, 1):
        add("cylinder", "Tapak | lanskap", f"Batang pohon {i:02d}", "bark",
            p=[tx, ty, 0], r=.20, h=2.5 + (i % 3) * .35)
        add("sphere", "Tapak | lanskap", f"Tajuk pohon {i:02d}", "leaf",
            p=[tx, ty, 3.2 + (i % 3) * .35], s=[1.5, 1.4, 1.45])

    # Local bounds and view targets keep both Astra deliverables in DWG metres.
    center = [79.0, 69.0, 5.3]
    span = 223.0
    views = {
        "overview": {"title": "Kawasan pengolahan Jetis", "detail": "Tapak, akses, parkir dan seluruh tahap berdasarkan layout plan DWG.",
                     "eye": [center[0] + 171, center[1] - 191, 160], "target": center},
        "entry": {"title": "Gerbang dan halaman depan", "detail": "Pos, jalur kendaraan dan parkir luar yang ditandai pada gambar.",
                  "eye": [111, -83, 38], "target": [111, 17, 3.5]},
        "phase1": {"title": "Tahap 1 · proses dan gudang", "detail": "Dua kompleks 30 m, modul struktur 6 m dan sayap layanan.",
                   "eye": [172, 8, 59], "target": [91, 49, 5.5]},
        "process": {"title": "Interior · rantai dingin", "detail": "Alur sortasi, pencucian, pembekuan, kemasan dan rak gudang adalah asumsi visual.",
                    "eye": [118, 28, 31], "target": [72, 53, 2.2], "interior": True},
        "phase2": {"title": "Tahap 2 · ekspansi", "detail": "Footprint 84 × 36 m dibaca dari poligon sumber; atap dan fungsi ruang diinferensikan.",
                   "eye": [176, 144, 55], "target": [96, 123, 5.0]},
        "yard": {"title": "Halaman logistik", "detail": "Area bongkar muat dan pelataran parkir luar.",
                 "eye": [157, -47, 33], "target": [118, 21, 1.5]},
    }
    labels = globals().get("ALL_LABELS", [])
    assumptions = [
        "Satuan meter didukung dimensi tahap 1 tertulis 30×78 m dan 30×84 m yang cocok dengan poligon handle 165A7 dan 165AA; INSUNITS DWG kosong.",
        "Batas tapak dan lima tapak bangunan mengikuti poligon model space handle 16551, 165A7, 165AA, 1657E, 16582, dan 1656E.",
        "Arah utara mengikuti panah simbol U yang menunjuk +X pada layout plan; tanpa koordinat geospasial.",
        "Tinggi eave 9.0 m dan nok 13.5 m diambil dari label elevasi pada potongan; struktur WF350, WF300 dan CNP125 mengikuti catatan sumber.",
        "Rangka portal tiap 6 m mengikuti grid/dimensi tertulis; tebal profil, detail sambungan, pelat dan fondasi adalah visualisasi, bukan desain struktur.",
        "Fungsi tiap ruang, lini ikan, rak dingin, mesin, jendela, akses, lanskap, gerbang, dan parkir yang tidak berdimensi lengkap adalah asumsi visual.",
        "Mezzanine ruang staf pada sayap QC ditempatkan pada +4.5 m sebagai interpretasi label Lantai 2 dan elevasi sumber.",
        "Model tidak memverifikasi kondisi eksisting, elevasi survei, struktur, utilitas, kapasitas proses, atau kelayakan konstruksi.",
    ]

    project = {
        "name": "Pengolahan Hasil Laut Jetis — Astra",
        "slug": "jetis-digital-twin-astra",
        "source_filename": "SEND.Pengolahan Hasil Laut - Jetis.dwg",
        "source_sha256": raw["source_sha256"].lower(),
        "status": "configured",
        "unit_evidence": ["Tahap 1 30×78 m = polyline 165A7 (78×30) in drawing units",
                          "Tahap 1 30×84 m = polyline 165AA (84×30) in drawing units",
                          "6 m repeated structural grid; insunits header is null"],
        "origin_source": [OX, OY],
        "north_source_axis": "+X; inferred from U compass arrow on layout plan",
        "bounds": {"min": [-1.0, -19.0, -.30], "max": [161.0, 145.0, 13.7]},
        "center": center,
        "span": span,
        "ground_height": 0.0,
        "walk_bounds": [-1.0, 161.0, -19.0, 145.0],
        "spawn": [108.0, 8.0, 0.0],
        "views": views,
        "roof_groups": roof_groups,
        "interior_groups": interior_groups,
        "source_footprints": [{"handle": s["handle"], "name": s["name"],
                               "bounds_m": [round(s["x"], 3), round(s["y"], 3),
                                            round(s["w"], 3), round(s["d"], 3)],
                               "vertices_m": [[round(a, 3), round(b, 3)] for a, b in s["poly"]]}
                              for s in specs],
        "status_detail": "Model geometri konseptual diturunkan dari footprint/layout; detail yang tidak berdimensi diberi catatan asumsi.",
        "download": "downloads/model.skp",
    }
    scene = {"units": "metres", "materials": materials, "elements": ELEMENTS,
             "motions": motion_specs, "labels": labels,
             "lights": [{"p": [x + 9, y + 9, 8.2], "intensity": 65, "distance": 28,
                         "color": "#ffe1a9"}
                        for s in specs for x, y in [(s["x"], s["y"])]],
             "footprints": project["source_footprints"], "assumptions": assumptions}
    scene, project = apply_revision(scene, project, raw)
    OUT_SCENE.parent.mkdir(parents=True, exist_ok=True)
    OUT_SCENE.write_text(json.dumps(scene, ensure_ascii=False, indent=2), encoding="utf-8")
    OUT_PROJECT.write_text(json.dumps(project, ensure_ascii=False, indent=2), encoding="utf-8")
    summary = {"elements": len(scene["elements"]), "doors": len(scene["motions"]),
               "labels": len(scene["labels"]), "site_triangles": len(triangles(source_site)),
               "source_sha256": raw["source_sha256"],
               "site_bounds_m": [round(v, 3) for v in bounds(source_site)],
               "footprints": project["source_footprints"],
               "scene_bytes": OUT_SCENE.stat().st_size}
    verify = ROOT / "verification" / "scene-generation.json"
    verify.parent.mkdir(exist_ok=True)
    verify.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
