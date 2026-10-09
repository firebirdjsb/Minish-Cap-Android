#!/usr/bin/env python3
from pathlib import Path

touch = Path("upstream/tmc/port/port_touch_controls.cpp")
src = touch.read_text(encoding="utf-8")

if '#include <imgui.h>' not in src:
    src = src.replace('#ifdef __ANDROID__\n', '#ifdef __ANDROID__\n#include <imgui.h>\n', 1)

anchor = '''extern "C" void Port_TouchControls_Render(SDL_Renderer* renderer, int windowWidth, int windowHeight) {
'''
idx = src.find(anchor)
if idx < 0:
    raise SystemExit("touch SDL render function not found")

end_anchor = '''extern "C" bool Port_TouchControls_ConsumeSettingsRequest(void) {
'''
end_idx = src.find(end_anchor)
if end_idx < 0:
    raise SystemExit("touch settings function anchor not found")

imgui_fn = r'''
extern "C" void Port_TouchControls_RenderImGui(void) {
    if (!Port_Config_TouchEnabled() || !sVisible) {
        return;
    }

    ImGuiIO& io = ImGui::GetIO();
    const int w = std::max(1, (int)io.DisplaySize.x);
    const int h = std::max(1, (int)io.DisplaySize.y);
    Port_TouchControls_NotifyRenderSize(w, h);
    UpdateHeldState();

    ImDrawList* dl = ImGui::GetForegroundDrawList();
    if (!dl) {
        return;
    }

    auto alpha = [](int base) -> int {
        const float v = (float)base * Port_Config_TouchOpacity();
        return (int)Clamp(v, 0.0f, 255.0f);
    };
    auto col = [&](int r, int g, int b, int a) -> ImU32 {
        return IM_COL32(r, g, b, alpha(a));
    };

    if (IsDpadScheme()) {
        const DpadGeom g = BuildDpadGeom(w, h);
        const float t = g.arm;
        const float half = g.half;
        const float round = t * 0.16f;

        const ImVec2 h0(g.cx - half, g.cy - t * 0.5f);
        const ImVec2 h1(g.cx + half, g.cy + t * 0.5f);
        const ImVec2 v0(g.cx - t * 0.5f, g.cy - half);
        const ImVec2 v1(g.cx + t * 0.5f, g.cy + half);
        dl->AddRectFilled(h0, h1, col(58, 62, 70, 138), round);
        dl->AddRectFilled(v0, v1, col(58, 62, 70, 138), round);
        dl->AddRect(h0, h1, col(226, 230, 238, 205), round, 0, 3.0f);
        dl->AddRect(v0, v1, col(226, 230, 238, 205), round, 0, 3.0f);

        const float textY = g.cy - ImGui::GetFontSize() * 0.5f;
        dl->AddText(ImVec2(g.cx - ImGui::CalcTextSize("U").x * 0.5f, g.cy - half + t * 0.25f),
                    col(250, 252, 255, 245), "U");
        dl->AddText(ImVec2(g.cx - ImGui::CalcTextSize("D").x * 0.5f, g.cy + half - t * 0.70f),
                    col(250, 252, 255, 245), "D");
        dl->AddText(ImVec2(g.cx - half + t * 0.30f, textY), col(250, 252, 255, 245), "L");
        dl->AddText(ImVec2(g.cx + half - t * 0.70f, textY), col(250, 252, 255, 245), "R");
    } else {
        const JoyGeom g = LiveJoyGeom(w, h);
        dl->AddCircleFilled(ImVec2(g.cx, g.cy), g.outerR, col(58, 62, 70, 132), 48);
        dl->AddCircle(ImVec2(g.cx, g.cy), g.outerR, col(226, 230, 238, 195), 48, 3.0f);
        const float kx = g.cx + sJoyKnobDx;
        const float ky = g.cy + sJoyKnobDy;
        dl->AddCircleFilled(ImVec2(kx, ky), g.knobR, col(92, 98, 108, 158), 40);
        dl->AddCircle(ImVec2(kx, ky), g.knobR, col(232, 236, 244, 210), 40, 3.0f);
    }

    const auto zones = BuildButtonZones(w, h);
    for (const TouchZone& z : zones) {
        const bool held = sHeld[z.input];
        const bool glow = (z.input == PORT_INPUT_R) && Port_TouchControls_RActionAvailable();
        const ImU32 fill = glow ? col(48, 145, 90, held ? 205 : 170)
                                : col(58, 62, 70, held ? 205 : 145);
        const ImU32 stroke = glow ? col(120, 245, 185, held ? 245 : 220)
                                  : col(230, 234, 242, held ? 235 : 205);
        if (z.shape == TouchShape::Circle) {
            dl->AddCircleFilled(ImVec2(z.cx, z.cy), z.radius, fill, 48);
            dl->AddCircle(ImVec2(z.cx, z.cy), z.radius, stroke, 48, 3.0f);
            const ImVec2 ts = ImGui::CalcTextSize(z.label);
            dl->AddText(ImVec2(z.cx - ts.x * 0.5f, z.cy - ts.y * 0.5f),
                        col(252, 253, 255, held ? 255 : 248), z.label);
        } else {
            const ImVec2 a(z.bounds.x, z.bounds.y);
            const ImVec2 b(z.bounds.x + z.bounds.w, z.bounds.y + z.bounds.h);
            const float round = z.bounds.h * 0.5f;
            dl->AddRectFilled(a, b, fill, round);
            dl->AddRect(a, b, stroke, round, 0, 3.0f);
            const ImVec2 ts = ImGui::CalcTextSize(z.label);
            dl->AddText(ImVec2(z.bounds.x + (z.bounds.w - ts.x) * 0.5f,
                               z.bounds.y + (z.bounds.h - ts.y) * 0.5f),
                        col(252, 253, 255, held ? 255 : 248), z.label);
        }
    }

    const SettingsBtnGeom sg = BuildSettingsBtnGeom(w, h);
    dl->AddCircleFilled(ImVec2(sg.cx, sg.cy), sg.r, col(52, 56, 64, 145), 40);
    dl->AddCircle(ImVec2(sg.cx, sg.cy), sg.r, col(228, 232, 240, 205), 40, 3.0f);
    const char* menu = "MENU";
    const ImVec2 mts = ImGui::CalcTextSize(menu);
    dl->AddText(ImVec2(sg.cx - mts.x * 0.5f, sg.cy - mts.y * 0.5f),
                col(250, 252, 255, 245), menu);
}

'''

src = src[:end_idx] + imgui_fn + src[end_idx:]

# Non-Android no-op near the existing stubs.
stub_anchor = '''extern "C" void Port_TouchControls_Render(SDL_Renderer*, int, int) {
}
'''
if stub_anchor not in src:
    raise SystemExit("non-Android touch render stub not found")
src = src.replace(stub_anchor, stub_anchor + '''extern "C" void Port_TouchControls_RenderImGui(void) {
}
''', 1)

touch.write_text(src, encoding="utf-8")

hdr = Path("upstream/tmc/port/port_touch_controls.h")
h = hdr.read_text(encoding="utf-8")
if "Port_TouchControls_RenderImGui" not in h:
    h = h.replace(
        "void Port_TouchControls_Render(SDL_Renderer* renderer, int windowWidth, int windowHeight);\n",
        "void Port_TouchControls_Render(SDL_Renderer* renderer, int windowWidth, int windowHeight);\n"
        "void Port_TouchControls_RenderImGui(void);\n",
        1
    )
hdr.write_text(h, encoding="utf-8")

menu = Path("upstream/tmc/port/port_imgui_menu.cpp")
m = menu.read_text(encoding="utf-8")
if '#include "port_touch_controls.h"' not in m:
    m = m.replace('#include "port_runtime_config.h" /* PortInput enum (PORT_INPUT_*) */\n',
                  '#include "port_runtime_config.h" /* PortInput enum (PORT_INPUT_*) */\n'
                  '#include "port_touch_controls.h"\n', 1)

render_anchor = '''#ifdef TMC_RA
    Port_RA_UI_DrawOverlay();
#endif
    ImGui::Render();
'''
render_new = '''#ifdef TMC_RA
    Port_RA_UI_DrawOverlay();
#endif
#ifdef TMC_GPU_RENDERER
    if (gpuBackend) {
        Port_TouchControls_RenderImGui();
    }
#endif
    ImGui::Render();
'''
if render_anchor not in m:
    raise SystemExit("ImGui render tail anchor not found")
m = m.replace(render_anchor, render_new, 1)
menu.write_text(m, encoding="utf-8")

print("Added synchronized ImGui touch overlay for SDL_GPU/Vulkan")
