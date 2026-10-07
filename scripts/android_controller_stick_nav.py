#!/usr/bin/env python3
from pathlib import Path

cfg = Path("upstream/tmc/port/port_runtime_config.cpp")
src = cfg.read_text(encoding="utf-8")

anchor = """extern "C" bool Port_Config_GetLeftStick(float* outX, float* outY) {
    if (sPads.empty()) {
        return false;
    }
    SDL_Gamepad* pad = sPads.front();
    /* SDL axis values are int16 -32768..32767. Normalise to [-1, 1].
     * +y on SDL = stick down = positive screen-y in TMC (top-left
     * origin), so no sign flip is required despite intuition. */
    const int16_t rawX = SDL_GetGamepadAxis(pad, SDL_GAMEPAD_AXIS_LEFTX);
    const int16_t rawY = SDL_GetGamepadAxis(pad, SDL_GAMEPAD_AXIS_LEFTY);
    if (outX)
        *outX = (float)rawX / 32767.0f;
    if (outY)
        *outY = (float)rawY / 32767.0f;
    return true;
}
"""

addition = anchor + r'''

/* Menu-navigation stick: use whichever physical stick is being pushed more
 * strongly. This gives controller users both left-stick and right-stick
 * navigation without changing gameplay bindings. ImGui receives this only
 * while a port/menu overlay is open. */
extern "C" bool Port_Config_GetMenuStick(float* outX, float* outY) {
    if (sPads.empty()) {
        return false;
    }

    SDL_Gamepad* pad = sPads.front();
    const float lx = (float)SDL_GetGamepadAxis(pad, SDL_GAMEPAD_AXIS_LEFTX) / 32767.0f;
    const float ly = (float)SDL_GetGamepadAxis(pad, SDL_GAMEPAD_AXIS_LEFTY) / 32767.0f;
    const float rx = (float)SDL_GetGamepadAxis(pad, SDL_GAMEPAD_AXIS_RIGHTX) / 32767.0f;
    const float ry = (float)SDL_GetGamepadAxis(pad, SDL_GAMEPAD_AXIS_RIGHTY) / 32767.0f;

    const float lmag2 = lx * lx + ly * ly;
    const float rmag2 = rx * rx + ry * ry;
    const float x = (rmag2 > lmag2) ? rx : lx;
    const float y = (rmag2 > lmag2) ? ry : ly;

    if (outX)
        *outX = x;
    if (outY)
        *outY = y;
    return true;
}
'''

if anchor not in src:
    raise SystemExit("Port_Config_GetLeftStick anchor not found")
if "Port_Config_GetMenuStick" not in src:
    src = src.replace(anchor, addition, 1)

cfg.write_text(src, encoding="utf-8")

hdr = Path("upstream/tmc/port/port_runtime_config.h")
h = hdr.read_text(encoding="utf-8")
if "Port_Config_GetMenuStick" not in h:
    h = h.replace(
        "bool Port_Config_GetLeftStick(float* outX, float* outY);\n",
        "bool Port_Config_GetLeftStick(float* outX, float* outY);\n"
        "bool Port_Config_GetMenuStick(float* outX, float* outY);\n",
        1
    )
hdr.write_text(h, encoding="utf-8")

menu = Path("upstream/tmc/port/port_imgui_menu.cpp")
m = menu.read_text(encoding="utf-8")

helper_anchor = """static bool sImGuiInited = false;
"""
helper = r'''static bool sImGuiInited = false;

#ifdef __ANDROID__
static void Port_ImGui_FeedMenuStick(bool enabled) {
    ImGuiIO& io = ImGui::GetIO();
    float x = 0.0f, y = 0.0f;
    if (!enabled || !Port_Config_GetMenuStick(&x, &y)) {
        io.AddKeyAnalogEvent(ImGuiKey_GamepadLStickLeft, false, 0.0f);
        io.AddKeyAnalogEvent(ImGuiKey_GamepadLStickRight, false, 0.0f);
        io.AddKeyAnalogEvent(ImGuiKey_GamepadLStickUp, false, 0.0f);
        io.AddKeyAnalogEvent(ImGuiKey_GamepadLStickDown, false, 0.0f);
        return;
    }

    constexpr float deadzone = 0.30f;
    auto norm = [](float v) -> float {
        constexpr float dz = 0.30f;
        const float a = v < 0.0f ? -v : v;
        if (a <= dz)
            return 0.0f;
        const float scaled = (a - dz) / (1.0f - dz);
        return scaled > 1.0f ? 1.0f : scaled;
    };

    const float left = x < -deadzone ? norm(x) : 0.0f;
    const float right = x > deadzone ? norm(x) : 0.0f;
    const float up = y < -deadzone ? norm(y) : 0.0f;
    const float down = y > deadzone ? norm(y) : 0.0f;

    io.AddKeyAnalogEvent(ImGuiKey_GamepadLStickLeft, left > 0.0f, left);
    io.AddKeyAnalogEvent(ImGuiKey_GamepadLStickRight, right > 0.0f, right);
    io.AddKeyAnalogEvent(ImGuiKey_GamepadLStickUp, up > 0.0f, up);
    io.AddKeyAnalogEvent(ImGuiKey_GamepadLStickDown, down > 0.0f, down);
}
#endif
'''
if helper_anchor not in m:
    raise SystemExit("sImGuiInited anchor not found")
m = m.replace(helper_anchor, helper, 1)

# Regular in-game/debug menu path: backend NewFrame -> feed stick -> ImGui::NewFrame.
regular_anchor = """    ImGui_ImplSDL3_NewFrame();
    ImGui::NewFrame();
"""
regular_repl = """    ImGui_ImplSDL3_NewFrame();
#ifdef __ANDROID__
    Port_ImGui_FeedMenuStick(navWanted);
#endif
    ImGui::NewFrame();
"""
if regular_anchor not in m:
    raise SystemExit("regular ImGui NewFrame anchor not found")
m = m.replace(regular_anchor, regular_repl, 1)

# Prelaunch ROM launcher should also accept either joystick.
pre_anchor = """    ImGui_ImplSDL3_NewFrame();
    ImGui::NewFrame();

    const ImGuiViewport* vp = ImGui::GetMainViewport();
"""
pre_repl = """    ImGui_ImplSDL3_NewFrame();
#ifdef __ANDROID__
    Port_ImGui_FeedMenuStick(true);
#endif
    ImGui::NewFrame();

    const ImGuiViewport* vp = ImGui::GetMainViewport();
"""
if pre_anchor not in m:
    raise SystemExit("prelaunch ImGui NewFrame anchor not found")
m = m.replace(pre_anchor, pre_repl, 1)

menu.write_text(m, encoding="utf-8")
print("Added direct left/right-stick ImGui navigation for Android menus")
