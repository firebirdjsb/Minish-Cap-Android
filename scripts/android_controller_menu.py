#!/usr/bin/env python3
from pathlib import Path

menu_path = Path("upstream/tmc/port/port_imgui_menu.cpp")
src = menu_path.read_text(encoding="utf-8")

anchor = "static void DrawRibbon(void) {\n"
if anchor not in src:
    raise SystemExit("DrawRibbon anchor not found")

helper = r'''
#ifdef __ANDROID__
static void DrawAndroidControllerRibbon(void) {
    struct Category {
        const char* label;
        void (*draw)();
    };

    static const Category kCategories[] = {
        { "Display",       DrawRibbonDisplayTab },
        { "Controls",      DrawRibbonControlsTab },
        { "Saves",         DrawRibbonSavesTab },
        { "Profiles",      DrawRibbonProfilesTab },
        { "Items",         DrawRibbonItemsTab },
        { "Equip",         DrawRibbonEquipTab },
        { "Warp",          DrawRibbonWarpTab },
        { "Entities",      DrawRibbonEntitiesTab },
        { "Flags",         DrawRibbonFlagsTab },
        { "Memory",        DrawRibbonMemoryTab },
        { "Randomizer",    DrawRibbonRandomizerTab },
        { "Audio",         DrawRibbonAudioTab },
        { "Accessibility", DrawRibbonAccessibilityTab },
        { "Reborn",        DrawRibbonRebornTab },
        { "Practice",      DrawRibbonPracticeTab },
        { "Map Editor",    DrawRibbonMapEditorTab },
    };

    static int category = 0;
    constexpr int kCount = (int)(sizeof(kCategories) / sizeof(kCategories[0]));

    bool categoryChanged = false;
    if (ImGui::IsKeyPressed(ImGuiKey_GamepadL1, false)) {
        category = (category + kCount - 1) % kCount;
        categoryChanged = true;
    }
    if (ImGui::IsKeyPressed(ImGuiKey_GamepadR1, false)) {
        category = (category + 1) % kCount;
        categoryChanged = true;
    }

    const bool popupOpen =
        ImGui::IsPopupOpen("", ImGuiPopupFlags_AnyPopupId | ImGuiPopupFlags_AnyPopupLevel);
    if (!popupOpen && !ImGui::GetIO().WantTextInput &&
        ImGui::IsKeyPressed(ImGuiKey_GamepadFaceRight, false)) {
        Port_DebugMenu_Toggle();
        return;
    }

    ImGuiIO& io = ImGui::GetIO();
    ImGui::SetNextWindowPos(ImVec2(0, 0), ImGuiCond_Always);
    ImGui::SetNextWindowSize(io.DisplaySize, ImGuiCond_Always);
    ImGui::PushStyleVar(ImGuiStyleVar_WindowRounding, 0.0f);
    ImGui::PushStyleVar(ImGuiStyleVar_WindowPadding, ImVec2(14.0f, 14.0f));

    if (ImGui::Begin("##android_controller_menu", nullptr,
                     ImGuiWindowFlags_NoTitleBar | ImGuiWindowFlags_NoResize |
                         ImGuiWindowFlags_NoMove | ImGuiWindowFlags_NoCollapse |
                         ImGuiWindowFlags_NoSavedSettings)) {
        const bool appearing = ImGui::IsWindowAppearing();

        ImGui::TextColored(ImVec4(0.58f, 0.94f, 0.68f, 1.0f), "MINISH CAP ANDROID");
        ImGui::SameLine();
        ImGui::TextDisabled("  L1/R1 category   D-pad navigate   A select   B close");
        ImGui::Separator();

        const float railW = 238.0f;
        if (ImGui::BeginChild("##android_categories", ImVec2(railW, -1), true,
                              ImGuiWindowFlags_NoScrollbar)) {
            for (int i = 0; i < kCount; ++i) {
                ImGui::PushID(i);
                const bool selected = (i == category);
                if (selected) {
                    ImGui::PushStyleColor(ImGuiCol_Header, ImVec4(0.17f, 0.50f, 0.30f, 0.90f));
                    ImGui::PushStyleColor(ImGuiCol_HeaderHovered, ImVec4(0.22f, 0.62f, 0.37f, 1.00f));
                    ImGui::PushStyleColor(ImGuiCol_HeaderActive, ImVec4(0.26f, 0.70f, 0.42f, 1.00f));
                }
                if (ImGui::Selectable(kCategories[i].label, selected, 0, ImVec2(-1.0f, 46.0f))) {
                    if (category != i) {
                        category = i;
                        categoryChanged = true;
                    }
                }
                if (selected) {
                    ImGui::PopStyleColor(3);
                }
                ImGui::PopID();
            }
        }
        ImGui::EndChild();

        ImGui::SameLine();

        if (ImGui::BeginChild("##android_settings", ImVec2(0, -1), true,
                              ImGuiWindowFlags_AlwaysVerticalScrollbar)) {
            ImGui::TextColored(ImVec4(0.82f, 0.96f, 0.85f, 1.0f), "%s", kCategories[category].label);
            ImGui::Separator();
            ImGui::Spacing();

            /* Focus the first real control after entering a category so a
             * controller never has to touch the screen/mouse to get started. */
            if (appearing || categoryChanged) {
                ImGui::SetKeyboardFocusHere(0);
            }

            kCategories[category].draw();
        }
        ImGui::EndChild();
    }
    ImGui::End();
    ImGui::PopStyleVar(2);
}
#endif

'''

src = src.replace(anchor, helper + anchor, 1)
src = src.replace(
"""static void DrawRibbon(void) {
    ImGuiIO& io = ImGui::GetIO();
""",
"""static void DrawRibbon(void) {
#ifdef __ANDROID__
    DrawAndroidControllerRibbon();
    return;
#endif
    ImGuiIO& io = ImGui::GetIO();
""", 1)

menu_path.write_text(src, encoding="utf-8")

controls = Path("upstream/tmc/port/port_imgui_controls_tab.inc")
ctl = controls.read_text(encoding="utf-8")
old = """    if (ImGui::CollapsingHeader("Touch controls", ImGuiTreeNodeFlags_DefaultOpen)) {
        {
            int scheme = (Port_Config_TouchScheme() == PORT_TOUCH_SCHEME_DPAD) ? 1 : 0;
            const char* items[] = { "Joystick (floating)", "D-pad" };
"""
new = """    if (ImGui::CollapsingHeader("Touch controls", ImGuiTreeNodeFlags_DefaultOpen)) {
        {
            bool enabled = Port_Config_TouchEnabled();
            if (ImGui::Checkbox("Show touch controls", &enabled)) {
                Port_Config_SetTouchEnabled(enabled);
            }
            ImGui::SameLine();
            ImGui::TextDisabled("(physical controllers still work when hidden)");
        }
        ImGui::BeginDisabled(!Port_Config_TouchEnabled());
        {
            int scheme = (Port_Config_TouchScheme() == PORT_TOUCH_SCHEME_DPAD) ? 1 : 0;
            const char* items[] = { "Floating joystick", "GBA D-pad" };
"""
if old not in ctl:
    raise SystemExit("Android touch controls UI block not found")
ctl = ctl.replace(old, new, 1)
ctl = ctl.replace(
"""        ImGui::TextDisabled("The R button glows green when it has an action (talk, read, lift...).");
    }
""",
"""        ImGui::TextDisabled("GBA layout: D-pad left, A/B right, L/R shoulders, Start/Select center.");
        ImGui::TextDisabled("The R button glows green when it has an action (talk, read, lift...).");
        ImGui::EndDisabled();
    }
""", 1)
controls.write_text(ctl, encoding="utf-8")

print("Added Android controller-first settings UI and touch-control toggle")
