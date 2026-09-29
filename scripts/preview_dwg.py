#!/usr/bin/env python3
"""Render a plan-view overview from the read-only ObjectDBX JSON extract."""
from __future__ import annotations

import json
import math
import argparse
from pathlib import Path
import re

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection


ROOT = Path(__file__).resolve().parents[1]
GEOMETRY = ROOT / "analysis" / "geometry.json"
OUTPUT = ROOT / "analysis" / "plan-overview.png"


def arc_points(center, radius, start, end, steps=28):
    sweep = end - start
    while sweep < 0:
        sweep += math.tau
    if sweep > math.tau:
        sweep = math.tau
    n = max(3, round(steps * sweep / math.tau))
    return [
        [center[0] + radius * math.cos(start + sweep * i / n),
         center[1] + radius * math.sin(start + sweep * i / n)]
        for i in range(n + 1)
    ]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--bbox", nargs=4, type=float, metavar=("XMIN", "XMAX", "YMIN", "YMAX"))
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    data = json.loads(GEOMETRY.read_text(encoding="utf-8-sig"))
    by_layer: dict[str, list[list[list[float]]]] = {}

    def add(layer, points):
        if len(points) > 1:
            by_layer.setdefault(layer or "<none>", []).extend(
                [[points[i], points[i + 1]] for i in range(len(points) - 1)]
            )

    for entity in data["entities"]:
        kind = entity.get("type") or ""
        layer = entity.get("layer") or "<none>"
        if kind == "AcDbLine":
            add(layer, [entity["a"][:2], entity["b"][:2]])
        elif "Polyline" in kind:
            values = entity.get("points", [])
            points = [[values[i], values[i + 1]] for i in range(0, len(values) - 1, 2)]
            if entity.get("closed") and points:
                points.append(points[0])
            add(layer, points)
        elif kind == "AcDbCircle":
            c = entity["center"]
            add(layer, arc_points(c, entity["radius"], 0, math.tau, steps=64))
        elif kind == "AcDbArc":
            add(layer, arc_points(entity["center"], entity["radius"], entity["start"], entity["end"]))

    colors = {
        "Atap": "#315f47",
        "As Atap": "#62856c",
        "dinding baru": "#a34a3a",
        "Pondasi": "#8a6f4d",
        "GR": "#245e9b",
        "TANGGA": "#8a5593",
    }
    fig, ax = plt.subplots(figsize=(22 if not args.bbox else 12, 7 if not args.bbox else 8), dpi=160)
    for layer, segments in by_layer.items():
        ax.add_collection(LineCollection(segments, colors=colors.get(layer, "#777b80"), linewidths=0.23, alpha=0.82))
    if args.bbox:
        xmin, xmax, ymin, ymax = args.bbox
        ax.set_xlim(xmin, xmax)
        ax.set_ylim(ymin, ymax)
        ax.grid(color="#d9dde1", linewidth=0.35)
        ax.tick_params(labelsize=7)
        for entity in data["entities"]:
            if entity.get("type") != "AcDbMText" or not entity.get("position"):
                continue
            raw = str(entity.get("text", "")).replace("\\P", " ").replace("\\L", "").replace("\\l", "")
            raw = re.sub(r"\\px[^;]*;", " ", raw)
            raw = re.sub(r"\\[HCA][^;]*;", " ", raw)
            label = re.sub(r"\{[^;]*;", "", raw).replace("}", "")
            label = re.sub(r"\\[A-Za-z0-9;]+", " ", label)
            label = " ".join(label.split()).strip(" ;|")
            if len(label) < 5 or not any(
                token in label.upper()
                for token in ("LAYOUT PLAN", "RENC.", "TAMPAK", "POTONGAN", "PORTAL")
            ):
                continue
            x, y = entity["position"][:2]
            if xmin <= x <= xmax and ymin <= y <= ymax:
                ax.text(x, y, label[:48], fontsize=5, color="#18212a", ha="left", va="bottom")
    else:
        ax.autoscale()
    ax.set_aspect("equal", adjustable="box")
    if not args.bbox:
        ax.axis("off")
    ax.set_title("Jetis DWG · saved model-space linework overview", loc="left", fontsize=13)
    fig.tight_layout(pad=0.4)
    fig.savefig(args.output, bbox_inches="tight", facecolor="white")
    plt.close(fig)

    print(json.dumps({
        "output": str(args.output),
        "layers_rendered": len(by_layer),
        "line_segments": sum(map(len, by_layer.values())),
        "has_mtext_titles": sum(e.get("type") == "AcDbMText" for e in data["entities"]),
    }))


if __name__ == "__main__":
    main()
