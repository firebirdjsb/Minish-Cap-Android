#!/usr/bin/env python3
from pathlib import Path

path = Path("upstream/tmc/port/port_touch_controls.cpp")
src = path.read_text(encoding="utf-8")

old = """SettingsBtnGeom BuildSettingsBtnGeom(int w, int h) {
    const float fh = static_cast<float>(std::max(1, h));
    const float unit = LayoutUnit(w, h);
    SettingsBtnGeom g;
    g.r = Clamp(unit * 0.50f, 32.f, 60.f);
    g.cx = g.r + unit * 0.35f;
    g.cy = fh * 0.50f;
    return g;
}
"""

new = """SettingsBtnGeom BuildSettingsBtnGeom(int w, int h) {
    const float fw = static_cast<float>(std::max(1, w));
    const float unit = LayoutUnit(w, h);
    SettingsBtnGeom g;
    g.r = Clamp(unit * 0.46f, 30.f, 56.f);

    /*
     * Phone-safe placement: modern landscape phones (including the Galaxy
     * S24 Ultra) can put the selfie-camera cutout on a short edge. The old
     * left-middle position landed directly in that exclusion zone. Keep the
     * settings control centered along the top instead, clear of both short
     * edges and away from the Start/Select row at the bottom.
     */
    g.cx = fw * 0.50f;
    g.cy = g.r + unit * 0.20f;
    return g;
}
"""

if old not in src:
    raise SystemExit("expected BuildSettingsBtnGeom source block not found")

path.write_text(src.replace(old, new, 1), encoding="utf-8")
print("Applied S24/cutout-safe touch settings placement")
