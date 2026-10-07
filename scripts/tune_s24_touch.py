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

# Stronger phone contrast: keep the controls translucent, but make their
# shapes and labels obvious over bright Minish Cap scenes.
replace_once(
"""    FillCircle(ren, g.cx, g.cy, g.r, 88, 92, 98, A(95));
    StrokeCircle(ren, g.cx, g.cy, g.r - 0.5f, 118, 122, 130, A(115));
""",
"""    FillCircle(ren, g.cx, g.cy, g.r, 62, 66, 74, A(145));
    StrokeCircle(ren, g.cx, g.cy, g.r - 0.5f, 220, 224, 232, A(210));
""", "settings visibility")

replace_once(
"""    FillCircle(ren, g.cx, g.cy, g.outerR, 88, 92, 98, A(sJoyFloating ? 92 : 78));
    StrokeCircle(ren, g.cx, g.cy, g.outerR - 0.5f, 118, 122, 130, A(sJoyFloating ? 115 : 95));
""",
"""    FillCircle(ren, g.cx, g.cy, g.outerR, 62, 66, 74, A(sJoyFloating ? 155 : 135));
    StrokeCircle(ren, g.cx, g.cy, g.outerR - 0.5f, 220, 224, 232, A(sJoyFloating ? 220 : 195));
""", "joystick ring visibility")

replace_once(
"""    FillCircle(ren, kx, ky, g.knobR, 96, 100, 108, A(deflect ? 125 : 92));
    StrokeCircle(ren, kx, ky, g.knobR - 0.5f, 120, 124, 132, A(deflect ? 105 : 88));
""",
"""    FillCircle(ren, kx, ky, g.knobR, 88, 94, 104, A(deflect ? 190 : 160));
    StrokeCircle(ren, kx, ky, g.knobR - 0.5f, 228, 232, 240, A(deflect ? 225 : 200));
""", "joystick knob visibility")

replace_once(
"""        const Uint8 fillA = held ? 125 : 80;
        SDL_SetRenderDrawBlendMode(ren, SDL_BLENDMODE_BLEND);
        SDL_SetRenderDrawColor(ren, 88, 92, 98, fillA);
        SDL_RenderFillRect(ren, &r);
        const Uint8 strokeA = held ? 110 : 80;
        SDL_SetRenderDrawColor(ren, 118, 122, 130, strokeA);
""",
"""        const Uint8 fillA = held ? 180 : 130;
        SDL_SetRenderDrawBlendMode(ren, SDL_BLENDMODE_BLEND);
        SDL_SetRenderDrawColor(ren, 62, 66, 74, fillA);
        SDL_RenderFillRect(ren, &r);
        const Uint8 strokeA = held ? 225 : 185;
        SDL_SetRenderDrawColor(ren, 220, 224, 232, strokeA);
""", "D-pad visibility")

replace_once(
"""    const Uint8 fillA = A(held ? 125 : (glow ? 110 : 88));
""",
"""    const Uint8 fillA = A(held ? 190 : (glow ? 170 : 140));
""", "face fill visibility")

replace_once(
"""        StrokeCircle(ren, cx, cy, r - 0.5f, 96, 220, 160, A(held ? 160 : 130));
""",
"""        StrokeCircle(ren, cx, cy, r - 0.5f, 120, 245, 185, A(held ? 245 : 220));
""", "glow outline visibility")

replace_once(
"""        FillCircle(ren, cx, cy, r, 88, 92, 98, fillA);
        StrokeCircle(ren, cx, cy, r - 0.5f, 118, 122, 130, A(held ? 105 : 82));
""",
"""        FillCircle(ren, cx, cy, r, 62, 66, 74, fillA);
        StrokeCircle(ren, cx, cy, r - 0.5f, 225, 229, 238, A(held ? 235 : 205));
""", "face outline visibility")

replace_once(
"""    SDL_SetRenderDrawColor(ren, 232, 236, 242, A(held ? 240 : 205));
""",
"""    SDL_SetRenderDrawColor(ren, 248, 250, 252, A(held ? 255 : 245));
""", "face label visibility")

replace_once(
"""    FillStadium(ren, b, 88, 92, 98, A(held ? 120 : 85));
    StrokeStadium(ren, b, 118, 122, 130, A(held ? 102 : 78));
""",
"""    FillStadium(ren, b, 62, 66, 74, A(held ? 185 : 140));
    StrokeStadium(ren, b, 225, 229, 238, A(held ? 230 : 200));
""", "stadium visibility")

# The second label line belongs to stadium controls.
replace_once(
"""    SDL_SetRenderDrawColor(ren, 232, 236, 242, A(held ? 240 : 205));
    SDL_RenderDebugText(ren, b.x + (b.w - textW) * 0.5f, b.y + (b.h - kTh) * 0.5f, z.label);
""",
"""    SDL_SetRenderDrawColor(ren, 248, 250, 252, A(held ? 255 : 245));
    SDL_RenderDebugText(ren, b.x + (b.w - textW) * 0.5f, b.y + (b.h - kTh) * 0.5f, z.label);
""", "stadium label visibility")

path.write_text(src, encoding="utf-8")
print("Applied GBA phone touch layout, high-contrast visibility, and cutout-safe placement")
