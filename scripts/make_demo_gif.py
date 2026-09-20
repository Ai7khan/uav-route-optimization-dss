"""Render an animated GIF of a live mission: terrain + danger + the route
re-planning through a SAM pop-up, with the route coloured by flight altitude to
show the 3D nap-of-the-earth behaviour. Self-contained (drives the backend).

Run:  python -m scripts.make_demo_gif
Writes docs/demo.gif
"""
from __future__ import annotations

import io
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.collections import LineCollection
from matplotlib.patches import Ellipse
from PIL import Image

from backend.api.session import Mission, _hillshade
from backend.config import GRID, KM_PER_DEG_LAT, KM_PER_DEG_LON
from backend.schemas import Weights
from backend.sim.airdefense import TYPE_RANGE

EXTENT = [GRID.lon_min, GRID.lon_max, GRID.lat_min, GRID.lat_max]
ACC, GREEN, AMBER, RED, BG = "#4da3ff", "#33d171", "#f5b942", "#ff5d5d", "#0b1220"


def render_frame(m: Mission) -> Image.Image:
    st = m.state()
    fig, ax = plt.subplots(figsize=(7.2, 6.6), dpi=110)
    fig.patch.set_facecolor(BG)
    ax.set_facecolor(BG)

    # terrain hillshade
    ax.imshow(_hillshade(m.scenario.terrain), extent=EXTENT, origin="lower",
              cmap="gray", alpha=0.55, zorder=0)
    # danger heatmap: green->amber->red ramp, alpha grows with danger so safe
    # areas stay transparent and terrain shows through.
    danger = np.clip(m.field.danger, 0, 1)
    rgba = plt.cm.RdYlGn_r(danger)
    rgba[..., 3] = np.clip(danger * 1.8, 0, 0.8)
    ax.imshow(rgba, extent=EXTENT, origin="lower", zorder=1)

    # threat rings
    for r in st["threat_rings"]:
        rng = r["range_km"] or TYPE_RANGE[r["ad_type"]]
        col = RED if r["active"] else "#5a6b8a"
        ax.add_patch(Ellipse((r["lon"], r["lat"]),
                             width=2 * rng / KM_PER_DEG_LON, height=2 * rng / KM_PER_DEG_LAT,
                             fill=r["active"], facecolor=col, alpha=0.12 if r["active"] else 0.0,
                             edgecolor=col, lw=1.4, ls="-" if r["active"] else "--", zorder=2))
        ax.plot(r["lon"], r["lat"], "o", color=col, ms=5, zorder=3)

    # alternatives (dashed)
    for a in st["alternatives"]:
        seg = a["segments"]
        ax.plot([s["lon"] for s in seg], [s["lat"] for s in seg],
                ls="--", lw=1.2, color=GREEN if a["label"] == "safest" else AMBER,
                alpha=0.5, zorder=3)

    # optimal route coloured by altitude (low=green NOE, high=red exposed)
    if st["route"]:
        seg = st["route"]["segments"]
        pts = np.array([[s["lon"], s["lat"]] for s in seg])
        alts = np.array([s["alt_agl_m"] for s in seg])
        segs = np.stack([pts[:-1], pts[1:]], axis=1)
        lc = LineCollection(segs, cmap="RdYlGn_r", norm=plt.Normalize(200, 1500), lw=4, zorder=4)
        lc.set_array(alts[:-1])
        ax.add_collection(lc)

    # markers
    ax.plot(st["start"]["lon"], st["start"]["lat"], "o", color=GREEN, ms=9, mec="w", zorder=5)
    ax.plot(st["goal"]["lon"], st["goal"]["lat"], "o", color=ACC, ms=9, mec="w", zorder=5)
    ax.plot(st["uav"]["lon"], st["uav"]["lat"], "^", color="w", ms=11, mec="k", zorder=6)

    # title / metrics banner
    rt = st["route"] or {}
    ps = st["planner_stats"]
    ax.set_title(f"UAV Route DSS — Almaty  ·  t = {st['time_min']:.0f} min",
                 color="w", fontsize=13, fontweight="bold", loc="left")
    txt = (f"P(detected) {rt.get('detection_prob',0)*100:4.0f}%   "
           f"time {rt.get('total_time_min',0):4.0f} min   "
           f"alt {st['route_altitudes'].get('min','?')}–{st['route_altitudes'].get('max','?')} m AGL   "
           f"replan: {ps['strategy']} {ps['ms']:.0f} ms")
    ax.text(0.01, -0.06, txt, transform=ax.transAxes, color="#cbd6e8", fontsize=9, family="monospace")
    for a in st["ad_predictions"]:
        pass
    ax.set_xlim(GRID.lon_min, GRID.lon_max)
    ax.set_ylim(GRID.lat_min, GRID.lat_max)
    ax.set_xticks([]); ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_color("#2a3a5c")
    fig.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format="png", facecolor=BG, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return Image.open(buf).convert("RGB")


def main():
    os.makedirs("data", exist_ok=True)
    m = Mission("sam_popup", GRID.frac_to_latlon(0.05, 0.05),
                GRID.frac_to_latlon(0.95, 0.95), Weights(safety=1.5, time=0.3, fuel=0.2),
                use_forecast=False, robust=False)  # forecast off -> visible reactive replan
    frames = [render_frame(m)]
    for _ in range(13):
        m.step()
        frames.append(render_frame(m))

    # hold the pop-up moment a little longer
    out = os.path.join("docs", "demo.gif")
    durations = [700] * len(frames)
    frames[0].save(out, save_all=True, append_images=frames[1:], duration=durations,
                   loop=0, optimize=True)
    print("WROTE", out, f"({len(frames)} frames)")


if __name__ == "__main__":
    main()
