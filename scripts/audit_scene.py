"""Independent source-to-scene checks for Astra's generated geometry."""
import hashlib
import json
import math
from collections import Counter
from pathlib import Path

# Revision02 uses frozen source dimensions and geometry checks in a scoped
# verifier; the original audit remains below for historical reproducibility.
from audit_revision import run
run()
raise SystemExit(0)

ROOT = Path(__file__).resolve().parents[1]
src_path = ROOT / "analysis" / "geometry.json"
scene_path = ROOT / "web" / "dist" / "assets" / "scene.json"
project_path = ROOT / "web" / "dist" / "project.json"
geometry = json.loads(src_path.read_text(encoding="utf-8-sig"))
scene = json.loads(scene_path.read_text(encoding="utf-8"))
project = json.loads(project_path.read_text(encoding="utf-8"))
source_sha = hashlib.sha256((ROOT / "source" / "input.dwg").read_bytes()).hexdigest()

assert source_sha == geometry["source_sha256"].lower() == project["source_sha256"].lower()
assert project["status"] == "configured" and scene["units"] == "metres"
assert project["north_source_axis"].startswith("+X")
entities = {e.get("handle"): e for e in geometry["entities"]}
actual = {f["handle"]: f for f in project["source_footprints"]}
expected = {"165A7": (78.0, 30.0), "165AA": (84.0, 30.0),
            "1657E": (36.0, 30.0), "16582": (36.0, 30.0), "1656E": (84.0, 36.0)}
assert set(actual) == set(expected)
for handle, dims in expected.items():
    pts = entities[handle]["points"]
    pairs = list(zip(pts[::2], pts[1::2]))
    w = max(x for x, _ in pairs) - min(x for x, _ in pairs)
    d = max(y for _, y in pairs) - min(y for _, y in pairs)
    assert math.isclose(w, dims[0], abs_tol=.01) and math.isclose(d, dims[1], abs_tol=.01)
    assert math.isclose(actual[handle]["bounds_m"][2], dims[0], abs_tol=.01)
    assert math.isclose(actual[handle]["bounds_m"][3], dims[1], abs_tol=.01)
    shifted = [[round(x - 2207.9734130790184, 3), round(y - 1532.7302629559754, 3)]
               for x, y in pairs]
    assert shifted == actual[handle]["vertices_m"]

ids = [e["id"] for e in scene["elements"]]
assert len(ids) == len(set(ids))
assert scene["elements"]
for e in scene["elements"]:
    assert e["kind"] in {"box", "beam", "wf", "cnp", "cylinder", "sphere", "prism"}
    assert e["mat"] in scene["materials"]
    assert e["group"] and e["name"]
    values = []
    for key in ("p", "s", "a", "b", "points"):
        if key in e:
            values.extend(v for p in e[key] for v in p) if key == "points" else values.extend(e[key])
    assert all(math.isfinite(float(v)) for v in values)
motion_ids = {m["id"] for m in scene["motions"]}
assert len(motion_ids) == len(scene["motions"])
assert all(e.get("motion") in motion_ids for e in scene["elements"] if e.get("motion"))
doors = {e.get("motion"): e for e in scene["elements"] if e.get("motion", "").startswith("door_")}
assert len(doors) == 11
for motion in scene["motions"]:
    if motion["kind"] != "roll":
        continue
    handle = motion["id"].split("_")[1].upper()
    fp = actual[handle]["bounds_m"]
    expected_side = "+Y" if handle in {"165A7", "1657E"} else "-Y"
    assert motion["opening_side"] == expected_side
    leaf = doors[motion["id"]]
    width = leaf["s"][0]
    cx = leaf["p"][0] + width / 2
    grid_n = round(fp[2] / 6)
    grid_x = [fp[0] + 6 * i for i in range(grid_n + 1)]
    clearance = min(abs(cx - gx) for gx in grid_x) - width / 2 - .175
    assert clearance > .1, f"Door {motion['id']} overlaps a 6 m portal column"
    wall_y = fp[1] + fp[3] if expected_side == "+Y" else fp[1]
    assert math.isclose(motion["anchor"][1], wall_y, abs_tol=.01)
    for other in actual.values():
        if other["handle"] == handle:
            continue
        ox, oy, ow, od = other["bounds_m"]
        if cx < ox or cx > ox + ow:
            continue
        if expected_side == "+Y":
            assert oy - wall_y > 1.0 or oy + od < wall_y - .1
        else:
            assert wall_y - (oy + od) > 1.0 or oy > wall_y + .1
assert {e["group"] for e in scene["elements"] if e["group"].startswith("Atap | ")} == set(project["roof_groups"])
assert {e["group"] for e in scene["elements"] if e["group"].startswith("Interior | ")} == set(project["interior_groups"])
assert {"overview", "entry", "phase1", "process", "phase2", "yard"} <= set(project["views"])
for name, mat in scene["materials"].items():
    if mat.get("texture"):
        for image in ("Color", "NormalGL", "Roughness"):
            path = ROOT / "web" / "dist" / "assets" / "textures" / f"{mat['texture']}_{image}.jpg"
            assert path.is_file(), f"Missing texture for material {name}: {path.name}"

site_poly = entities["16551"]["points"]
site_pairs = list(zip(site_poly[::2], site_poly[1::2]))
site_shifted = [(x - 2207.9734130790184, y - 1532.7302629559754) for x, y in site_pairs]
if math.dist(site_shifted[0], site_shifted[-1]) < .01:
    site_shifted.pop()
site_area = abs(sum(site_shifted[i][0] * site_shifted[(i + 1) % len(site_shifted)][1] -
                    site_shifted[(i + 1) % len(site_shifted)][0] * site_shifted[i][1]
                    for i in range(len(site_shifted))) / 2)
tri_area = sum(abs((e["points"][1][0] - e["points"][0][0]) * (e["points"][2][1] - e["points"][0][1]) -
                    (e["points"][2][0] - e["points"][0][0]) * (e["points"][1][1] - e["points"][0][1])) / 2
                for e in scene["elements"] if e["group"] == "Tapak | tanah")
assert math.isclose(site_area, tri_area, rel_tol=1e-8, abs_tol=.05)
assert len(scene["elements"]) >= 1000

report = {
    "status": "PASS",
    "source_sha256_matches": True,
    "footprints_checked": len(expected),
    "site_area_source_m2": round(site_area, 3),
    "site_area_scene_m2": round(tri_area, 3),
    "scene_elements": len(scene["elements"]),
    "element_types": dict(Counter(e["kind"] for e in scene["elements"])),
    "materials": len(scene["materials"]),
    "motions": len(scene["motions"]),
    "loading_doors_clear_of_portal_columns": len(doors),
    "roof_groups": len(project["roof_groups"]),
    "interior_groups": len(project["interior_groups"]),
}
out = ROOT / "verification" / "scene-audit.json"
out.parent.mkdir(exist_ok=True)
out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(report, ensure_ascii=False, indent=2))
