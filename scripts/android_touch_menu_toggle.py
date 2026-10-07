#!/usr/bin/env python3
from pathlib import Path

touch = Path("upstream/tmc/port/port_touch_controls.cpp")
src = touch.read_text(encoding="utf-8")

if '#include "port_debug_menu.h"' not in src:
    src = src.replace(
        '#include "port_runtime_config.h"\n',
        '#include "port_runtime_config.h"\n#include "port_debug_menu.h"\n',
        1
    )

# While the main Android settings menu is open, only MENU remains an active
# touch-control zone. ImGui itself handles tap, drag, scrolling and widgets.
held_old = """void UpdateHeldState() {
    /* Slide-off hysteresis: remember what was held last frame; a zone a
     * finger is already holding keeps a 1.35x-radius grace hitbox so a
     * small thumb slide doesn't drop the press mid-action. */
    std::array<bool, PORT_INPUT_COUNT> prevHeld = sHeld;
    sHeld.fill(false);
    if (!sVisible || sLastWindowW <= 0 || sLastWindowH <= 0) {
        return;
    }
"""
held_new = """void UpdateHeldState() {
    /* Slide-off hysteresis: remember what was held last frame; a zone a
     * finger is already holding keeps a 1.35x-radius grace hitbox so a
     * small thumb slide doesn't drop the press mid-action. */
    std::array<bool, PORT_INPUT_COUNT> prevHeld = sHeld;
    sHeld.fill(false);
    if (!sVisible || sLastWindowW <= 0 || sLastWindowH <= 0) {
        return;
    }

#ifdef __ANDROID__
    /* Direct touchscreen interaction owns menu navigation. Do not convert
     * touches on the gameplay overlay into A/B/D-pad/etc while the settings
     * menu is open; only the dedicated MENU circle is handled separately by
     * TryTriggerSettings(). */
    if (Port_DebugMenu_IsOpen()) {
        ClearJoystick();
        return;
    }
#endif
"""
if held_old not in src:
    raise SystemExit("UpdateHeldState anchor not found")
src = src.replace(held_old, held_new, 1)

render_old = """    if (IsDpadScheme()) {
        DrawDpad(renderer, windowWidth, windowHeight);
    } else {
        DrawJoystick(renderer, windowWidth, windowHeight);
    }
    for (const TouchZone& z : BuildButtonZones(windowWidth, windowHeight)) {
        DrawButtonZone(renderer, z);
    }
    DrawSettingsButton(renderer, windowWidth, windowHeight);
"""
render_new = """#ifdef __ANDROID__
    if (Port_DebugMenu_IsOpen()) {
        /* Menu content is already touch-native. Keep one obvious close button
         * and remove the gameplay overlay until the menu closes. */
        DrawSettingsButton(renderer, windowWidth, windowHeight);
        return;
    }
#endif

    if (IsDpadScheme()) {
        DrawDpad(renderer, windowWidth, windowHeight);
    } else {
        DrawJoystick(renderer, windowWidth, windowHeight);
    }
    for (const TouchZone& z : BuildButtonZones(windowWidth, windowHeight)) {
        DrawButtonZone(renderer, z);
    }
    DrawSettingsButton(renderer, windowWidth, windowHeight);
"""
if render_old not in src:
    raise SystemExit("SDL touch render block not found")
src = src.replace(render_old, render_new, 1)

touch.write_text(src, encoding="utf-8")

# Touch MENU should be a true toggle for the main Android settings menu.
bios = Path("upstream/tmc/port/port_bios.c")
b = bios.read_text(encoding="utf-8")
old = """    if (Port_TouchControls_ConsumeSettingsRequest()) {
        if (!Port_DebugMenu_IsOpen() && !Port_SoftSlots_ConfigIsOpen() && !Port_InGameSettingsModalIsOpen()) {
            Port_OpenInGameSettingsModal();
        }
    }
"""
new = """    if (Port_TouchControls_ConsumeSettingsRequest()) {
#ifdef __ANDROID__
        if (Port_DebugMenu_IsOpen()) {
            Port_DebugMenu_Toggle();
        } else if (!Port_SoftSlots_ConfigIsOpen() && !Port_InGameSettingsModalIsOpen() &&
                   !Port_RandoFileMenu_IsOpen() && !Port_LevelEditor_IsOpen()) {
            /* The on-screen MENU button opens the same controller/touch-friendly
             * settings overlay that F8 / Select+Start opens. */
            Port_DebugMenu_Toggle();
        }
#else
        if (!Port_DebugMenu_IsOpen() && !Port_SoftSlots_ConfigIsOpen() && !Port_InGameSettingsModalIsOpen()) {
            Port_OpenInGameSettingsModal();
        }
#endif
    }
"""
if old not in b:
    raise SystemExit("touch settings request block not found")
b = b.replace(old, new, 1)
bios.write_text(b, encoding="utf-8")

print("Made Android touch MENU a true open/close toggle; gameplay overlay hides inside menu")
