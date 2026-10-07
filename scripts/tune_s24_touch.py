#!/usr/bin/env python3
from pathlib import Path

path = Path("upstream/tmc/port/port_touch_controls.cpp")
src = path.read_text(encoding="utf-8")

def replace_once(old: str, new: str, label: str):
    global src
    if old not in src:
        raise SystemExit(f"expected {label} source block not found")
    src = src.replace(old, new, 1)

replace_once(
"""JoyGeom BuildJoyGeom(int w, int h) {
    const float fw = static_cast<float>(std::max(1, w));
    const float fh = static_cast<float>(std::max(1, h));
    const float unit = LayoutUnit(w, h);
    JoyGeom g;
    g.cx = fw * 0.19f;
    g.cy = fh * 0.76f;
    g.outerR = Clamp(unit * 1.05f, 70.0f, 138.0f);
    g.knobR = Clamp(unit * 0.33f, 24.0f, 46.0f);
    return g;
}
""",
"""JoyGeom BuildJoyGeom(int w, int h) {
    const float fw = static_cast<float>(std::max(1, w));
    const float fh = static_cast<float>(std::max(1, h));
    const float unit = LayoutUnit(w, h);
    JoyGeom g;
    g.cx = fw * 0.155f;
    g.cy = fh * 0.70f;
    g.outerR = Clamp(unit * 1.02f, 70.0f, 136.0f);
    g.knobR = Clamp(unit * 0.33f, 24.0f, 46.0f);
    return g;
}
""", "joystick geometry")

replace_once(
"""SettingsBtnGeom BuildSettingsBtnGeom(int w, int h) {
    const float fh = static_cast<float>(std::max(1, h));
    const float unit = LayoutUnit(w, h);
    SettingsBtnGeom g;
    g.r = Clamp(unit * 0.50f, 32.f, 60.f);
    g.cx = g.r + unit * 0.35f;
    g.cy = fh * 0.50f;
    return g;
}
""",
"""SettingsBtnGeom BuildSettingsBtnGeom(int w, int h) {
    const float fw = static_cast<float>(std::max(1, w));
    const float unit = LayoutUnit(w, h);
    SettingsBtnGeom g;
    g.r = Clamp(unit * 0.42f, 28.f, 52.f);

    /* Keep settings away from either short-edge camera/cutout in landscape. */
    g.cx = fw * 0.50f;
    g.cy = g.r + unit * 0.18f;
    return g;
}
""", "settings geometry")

replace_once(
"""DpadGeom BuildDpadGeom(int w, int h) {
    const float fw = static_cast<float>(std::max(1, w));
    const float fh = static_cast<float>(std::max(1, h));
    const float unit = LayoutUnit(w, h);
    DpadGeom g;
    g.cx = fw * 0.19f;
    g.cy = fh * 0.76f;
    g.half = Clamp(unit * 1.20f, 80.0f, 160.0f);
    g.arm = g.half * 0.62f;
    return g;
}
""",
"""DpadGeom BuildDpadGeom(int w, int h) {
    const float fw = static_cast<float>(std::max(1, w));
    const float fh = static_cast<float>(std::max(1, h));
    const float unit = LayoutUnit(w, h);
    DpadGeom g;
    g.cx = fw * 0.155f;
    g.cy = fh * 0.70f;
    g.half = Clamp(unit * 1.13f, 78.0f, 154.0f);
    g.arm = g.half * 0.60f;
    return g;
}
""", "D-pad geometry")

replace_once(
"""std::array<TouchZone, 6> BuildButtonZones(int w, int h) {
    const float fw = static_cast<float>(std::max(1, w));
    const float fh = static_cast<float>(std::max(1, h));
    const float unit = LayoutUnit(w, h);
    const float gap = unit * 0.98f;
    const float faceR = unit * 0.53f;
    const float faceX = fw * 0.83f;
    const float faceY = fh * 0.72f;
    const float smallH = unit * 0.70f;
    const float smallW = unit * 1.42f;
    const float selW = unit * 1.95f;
    const float staW = unit * 1.55f;

    return { {
        { PORT_INPUT_B, TouchShape::Circle, faceX - gap * 0.62f, faceY + gap * 0.42f, faceR, {}, "B" },
        { PORT_INPUT_A, TouchShape::Circle, faceX + gap * 0.45f, faceY - gap * 0.10f, faceR, {}, "A" },
        { PORT_INPUT_R, TouchShape::Circle, faceX - gap * 0.42f, faceY - gap * 0.62f, faceR, {}, "R" },
        { PORT_INPUT_SELECT, TouchShape::Stadium, 0, 0, 0, MakeCentered(fw * 0.40f, fh * 0.90f, selW, smallH),
          "Select" },
        { PORT_INPUT_START, TouchShape::Stadium, 0, 0, 0, MakeCentered(fw * 0.58f, fh * 0.90f, staW, smallH), "Start" },
        { PORT_INPUT_L, TouchShape::Stadium, 0, 0, 0, MakeCentered(fw * 0.16f, fh * 0.10f, smallW, smallH), "L" },
    } };
}
""",
"""std::array<TouchZone, 6> BuildButtonZones(int w, int h) {
    const float fw = static_cast<float>(std::max(1, w));
    const float fh = static_cast<float>(std::max(1, h));
    const float unit = LayoutUnit(w, h);

    /*
     * GBA-style phone layout:
     *   L shoulder                                   R shoulder
     *
     *      fixed D-pad                         B          A
     *
     *                       Select   Start
     *
     * Face buttons are separated enough for two-thumb play; shoulders sit
     * along the upper corners and the system/camera cutout stays clear.
     */
    const float faceR = unit * 0.55f;
    const float smallH = unit * 0.62f;
    const float shoulderW = unit * 1.75f;
    const float centerW = unit * 1.60f;
    const float faceY = fh * 0.71f;

    return { {
        { PORT_INPUT_B, TouchShape::Circle, fw * 0.80f, faceY + unit * 0.28f, faceR, {}, "B" },
        { PORT_INPUT_A, TouchShape::Circle, fw * 0.89f, faceY - unit * 0.18f, faceR, {}, "A" },
        { PORT_INPUT_R, TouchShape::Stadium, 0, 0, 0,
          MakeCentered(fw * 0.88f, fh * 0.095f, shoulderW, smallH), "R" },
        { PORT_INPUT_SELECT, TouchShape::Stadium, 0, 0, 0,
          MakeCentered(fw * 0.445f, fh * 0.90f, centerW, smallH), "Select" },
        { PORT_INPUT_START, TouchShape::Stadium, 0, 0, 0,
          MakeCentered(fw * 0.555f, fh * 0.90f, centerW, smallH), "Start" },
        { PORT_INPUT_L, TouchShape::Stadium, 0, 0, 0,
          MakeCentered(fw * 0.12f, fh * 0.095f, shoulderW, smallH), "L" },
    } };
}
""", "button geometry")

replace_once(
"""extern "C" void Port_TouchControls_HandleEvent(const SDL_Event* event) {
    if (event == nullptr) {
        return;
    }
""",
"""extern "C" void Port_TouchControls_HandleEvent(const SDL_Event* event) {
    if (event == nullptr || !Port_Config_TouchEnabled()) {
        return;
    }
""", "touch event gate")

replace_once(
"""extern "C" void Port_TouchControls_Render(SDL_Renderer* renderer, int windowWidth, int windowHeight) {
    Port_TouchControls_NotifyRenderSize(windowWidth, windowHeight);
    UpdateHeldState();
    if (!renderer || !sVisible) {
        return;
    }
""",
"""extern "C" void Port_TouchControls_Render(SDL_Renderer* renderer, int windowWidth, int windowHeight) {
    Port_TouchControls_NotifyRenderSize(windowWidth, windowHeight);
    if (!Port_Config_TouchEnabled()) {
        sTouches.clear();
        sHeld.fill(false);
        ClearJoystick();
        return;
    }
    UpdateHeldState();
    if (!renderer || !sVisible) {
        return;
    }
""", "touch render gate")

path.write_text(src, encoding="utf-8")
print("Applied GBA phone touch layout, toggle gate, and cutout-safe placement")
