#!/usr/bin/env python3
from pathlib import Path

menu = Path("upstream/tmc/port/port_imgui_menu.cpp")
src = menu.read_text(encoding="utf-8")

main_shoulder_marker = """    if (ImGui::IsKeyPressed(ImGuiKey_GamepadR1, false)) {
        category = (category + 1) % kCount;
        categoryChanged = true;
    }

    const bool popupOpen ="""
main_shoulder_replacement = """    if (ImGui::IsKeyPressed(ImGuiKey_GamepadR1, false)) {
        category = (category + 1) % kCount;
        categoryChanged = true;
    }
    const bool categoryChangedByShoulder = categoryChanged;

    const bool popupOpen ="""
if main_shoulder_marker not in src:
    raise SystemExit("main category shoulder-navigation anchor not found")
src = src.replace(main_shoulder_marker, main_shoulder_replacement, 1)

# Guard shoulder-driven section changes from being overwritten by stale ImGui focus.
setup_shoulder_marker = """    if (ImGui::IsKeyPressed(ImGuiKey_GamepadR1, false)) {
        section = (section + 1) % kSectionCount;
        sectionChanged = true;
    }

    const bool popupOpen ="""
setup_shoulder_replacement = """    if (ImGui::IsKeyPressed(ImGuiKey_GamepadR1, false)) {
        section = (section + 1) % kSectionCount;
        sectionChanged = true;
    }
    const bool sectionChangedExplicitly = sectionChanged;

    const bool popupOpen ="""
if setup_shoulder_marker not in src:
    raise SystemExit("file-setup shoulder-navigation anchor not found")
src = src.replace(setup_shoulder_marker, setup_shoulder_replacement, 1)

# ---------------------------------------------------------------------------
# Main Android settings category rail: explicit full-width buttons.
# This avoids Selectable label clipping seen on high-DPI Samsung landscape.
# ---------------------------------------------------------------------------
src = src.replace(
"""        const float railW = std::clamp(io.DisplaySize.x * 0.22f, 460.0f, 680.0f);
        const float categoryRowH = std::clamp(io.DisplaySize.y * 0.052f, 58.0f, 82.0f);
""",
"""        const float railW = std::clamp(io.DisplaySize.x * 0.28f, 300.0f, 440.0f);
        const float categoryRowH = std::clamp(io.DisplaySize.y * 0.072f, 58.0f, 86.0f);
""", 1)

old_main_item = """                if (selected) {
                    ImGui::PushStyleColor(ImGuiCol_Header, ImVec4(0.17f, 0.50f, 0.30f, 0.90f));
                    ImGui::PushStyleColor(ImGuiCol_HeaderHovered, ImVec4(0.22f, 0.62f, 0.37f, 1.00f));
                    ImGui::PushStyleColor(ImGuiCol_HeaderActive, ImVec4(0.26f, 0.70f, 0.42f, 1.00f));
                }
                if (ImGui::Selectable(kCategories[i].label, selected, 0, ImVec2(-1.0f, categoryRowH))) {
                    if (category != i) {
                        category = i;
                        categoryChanged = true;
                    }
                }
                if (selected) {
                    ImGui::PopStyleColor(3);
                }
"""
new_main_item = """                if (selected) {
                    ImGui::PushStyleColor(ImGuiCol_Button, ImVec4(0.17f, 0.50f, 0.30f, 0.95f));
                    ImGui::PushStyleColor(ImGuiCol_ButtonHovered, ImVec4(0.22f, 0.62f, 0.37f, 1.00f));
                    ImGui::PushStyleColor(ImGuiCol_ButtonActive, ImVec4(0.26f, 0.70f, 0.42f, 1.00f));
                }

                const float itemW = ImGui::GetContentRegionAvail().x;
                if (ImGui::Button(kCategories[i].label, ImVec2(itemW, categoryRowH))) {
                    if (category != i) {
                        category = i;
                        categoryChanged = true;
                    }
                }

                /* D-pad/stick focus movement immediately selects the category.
                 * This makes the left rail fully controller-driven without
                 * requiring an extra A press just to reveal a page. */
                if (!categoryChangedByShoulder && ImGui::IsItemFocused() && category != i) {
                    category = i;
                    categoryChanged = true;
                }

                if (selected && (appearing || categoryChanged)) {
                    ImGui::SetItemDefaultFocus();
                    ImGui::SetScrollHereY(0.5f);
                }

                if (selected) {
                    ImGui::PopStyleColor(3);
                }
"""
if old_main_item not in src:
    raise SystemExit("main Android category item block not found")
src = src.replace(old_main_item, new_main_item, 1)

# ---------------------------------------------------------------------------
# L-button Port/Randomizer section rail: same robust full-width button model.
# ---------------------------------------------------------------------------
src = src.replace(
"""        const float railW = std::clamp(vp->WorkSize.x * 0.22f, 460.0f, 680.0f);
        const float rowH = std::clamp(vp->WorkSize.y * 0.065f, 66.0f, 92.0f);
""",
"""        const float railW = std::clamp(vp->WorkSize.x * 0.28f, 300.0f, 440.0f);
        const float rowH = std::clamp(vp->WorkSize.y * 0.085f, 64.0f, 92.0f);
""", 1)

old_setup_item = """                if (selected) {
                    ImGui::PushStyleColor(ImGuiCol_Header, ImVec4(0.17f, 0.50f, 0.30f, 0.90f));
                    ImGui::PushStyleColor(ImGuiCol_HeaderHovered, ImVec4(0.22f, 0.62f, 0.37f, 1.00f));
                    ImGui::PushStyleColor(ImGuiCol_HeaderActive, ImVec4(0.26f, 0.70f, 0.42f, 1.00f));
                }

                if (ImGui::Selectable(kSections[i], selected, 0, ImVec2(-1.0f, rowH))) {
                    if (section != i) {
                        section = i;
                        sectionChanged = true;
                    }
                }

                /* Also make ordinary D-pad navigation on the section rail
                 * immediately switch the right pane, not just move a highlight. */
                if (!sectionChangedExplicitly && ImGui::IsItemFocused() && section != i) {
                    section = i;
                    sectionChanged = true;
                }

                if (selected)
                    ImGui::PopStyleColor(3);
"""
new_setup_item = """                if (selected) {
                    ImGui::PushStyleColor(ImGuiCol_Button, ImVec4(0.17f, 0.50f, 0.30f, 0.95f));
                    ImGui::PushStyleColor(ImGuiCol_ButtonHovered, ImVec4(0.22f, 0.62f, 0.37f, 1.00f));
                    ImGui::PushStyleColor(ImGuiCol_ButtonActive, ImVec4(0.26f, 0.70f, 0.42f, 1.00f));
                }

                const float itemW = ImGui::GetContentRegionAvail().x;
                if (ImGui::Button(kSections[i], ImVec2(itemW, rowH))) {
                    if (section != i) {
                        section = i;
                        sectionChanged = true;
                    }
                }

                if (ImGui::IsItemFocused() && section != i) {
                    section = i;
                    sectionChanged = true;
                }

                if (selected && sectionChanged) {
                    ImGui::SetItemDefaultFocus();
                    ImGui::SetScrollHereY(0.5f);
                }

                if (selected)
                    ImGui::PopStyleColor(3);
"""
if old_setup_item not in src:
    raise SystemExit("Android file-setup rail item block not found")
src = src.replace(old_setup_item, new_setup_item, 1)

# ---------------------------------------------------------------------------
# Randomizer phone fields: stacked labels + full-width controls.
# ---------------------------------------------------------------------------
old_seed = """                        const float contentW = ImGui::GetContentRegionAvail().x;
                        ImGui::SetNextItemWidth(contentW * 0.62f);
                        if (ImGui::InputText("Seed (empty = random)", Port_RandoFileMenu_SeedBuffer(),
                                             RANDO_FILE_MENU_SEED_MAX + 1,
                                             ImGuiInputTextFlags_EnterReturnsTrue)) {
                            Port_RandoFileMenu_SeedEdited();
                        }
                        if (ImGui::IsItemEdited())
                            Port_RandoFileMenu_SeedEdited();

                        ImGui::SameLine();
                        if (ImGui::Button("Randomize", ImVec2(contentW * 0.22f, 0)))
                            Port_RandoFileMenu_RandomizeSeed();

                        int difficulty = Port_RandoFileMenu_Difficulty();
                        ImGui::SetNextItemWidth(contentW * 0.55f);
                        if (ImGui::Combo("Item pool", &difficulty, kRandoPoolCombo, RANDO_ITEM_POOL_COUNT))
                            Port_RandoFileMenu_SetDifficulty(difficulty);
"""
new_seed = """                        const float contentW = ImGui::GetContentRegionAvail().x;

                        ImGui::TextDisabled("Seed (empty = random)");
                        ImGui::SetNextItemWidth(contentW);
                        if (ImGui::InputText("##phone_rando_seed", Port_RandoFileMenu_SeedBuffer(),
                                             RANDO_FILE_MENU_SEED_MAX + 1,
                                             ImGuiInputTextFlags_EnterReturnsTrue)) {
                            Port_RandoFileMenu_SeedEdited();
                        }
                        if (ImGui::IsItemEdited())
                            Port_RandoFileMenu_SeedEdited();

                        if (ImGui::Button("Randomize seed", ImVec2(contentW, 0)))
                            Port_RandoFileMenu_RandomizeSeed();

                        int difficulty = Port_RandoFileMenu_Difficulty();
                        ImGui::TextDisabled("Item pool");
                        ImGui::SetNextItemWidth(contentW);
                        if (ImGui::Combo("##phone_rando_pool", &difficulty, kRandoPoolCombo,
                                         RANDO_ITEM_POOL_COUNT))
                            Port_RandoFileMenu_SetDifficulty(difficulty);
"""
if old_seed not in src:
    raise SystemExit("Android randomizer seed/pool field block not found")
src = src.replace(old_seed, new_seed, 1)

old_appearance = """                        ImGui::SetNextItemWidth(contentW * 0.50f);
                        ImGui::Combo("Tunic color", Port_RandoFileMenu_TunicColor(), kTunicColors, 7);
                        ImGui::SetNextItemWidth(contentW * 0.50f);
                        ImGui::Combo("Heart color", Port_RandoFileMenu_HeartColor(), kHeartColors, 7);
                        ImGui::SetNextItemWidth(contentW * 0.50f);
                        ImGui::Combo("Accessibility", Port_RandoFileMenu_Accessibility(),
                                     kRandoAccessCombo, RANDO_ACCESS_COUNT);
"""
new_appearance = """                        ImGui::TextDisabled("Tunic color");
                        ImGui::SetNextItemWidth(contentW);
                        ImGui::Combo("##phone_tunic_color", Port_RandoFileMenu_TunicColor(), kTunicColors, 7);

                        ImGui::TextDisabled("Heart color");
                        ImGui::SetNextItemWidth(contentW);
                        ImGui::Combo("##phone_heart_color", Port_RandoFileMenu_HeartColor(), kHeartColors, 7);

                        ImGui::TextDisabled("Accessibility");
                        ImGui::SetNextItemWidth(contentW);
                        ImGui::Combo("##phone_rando_access", Port_RandoFileMenu_Accessibility(),
                                     kRandoAccessCombo, RANDO_ACCESS_COUNT);
"""
if old_appearance not in src:
    raise SystemExit("Android randomizer appearance field block not found")
src = src.replace(old_appearance, new_appearance, 1)

# ---------------------------------------------------------------------------
# Prelaunch ROM/language controls: phone-native stacked fields.
# ---------------------------------------------------------------------------
sig = "static bool DrawRegionLanguageControls(bool prelaunch) {\n"
idx = src.find(sig)
if idx < 0:
    raise SystemExit("DrawRegionLanguageControls not found")
insert_at = idx + len(sig)
android_region = r'''
#ifdef __ANDROID__
    {
        bool regionChanged = false;
        ImGui::SeparatorText("ROM Region & Language");

        int preferredRegion = Port_Config_PreferredRegion();
        if (preferredRegion < -1 || preferredRegion > 2)
            preferredRegion = -1;

        const char* regionNames[] = {
            "Auto (use first valid ROM)",
            "USA (baserom.gba)",
            "EU (baserom_eu.gba)",
            "JP (baserom_jp.gba)",
        };
        int regionIdx = preferredRegion + 1;

        ImGui::TextDisabled("Preferred ROM");
        ImGui::SetNextItemWidth(ImGui::GetContentRegionAvail().x);
        if (ImGui::Combo("##android_preferred_rom", &regionIdx, regionNames, 4)) {
            Port_Config_SetPreferredRegion(regionIdx - 1);
            regionChanged = true;
        }
        ImGui::TextWrapped(prelaunch ? "Used when Play starts." : "Restart required after changing ROM region.");

        constexpr int kLanguageCount = 6;
        int preferredLanguage = Port_Config_PreferredLanguage();
        if (preferredLanguage < -1 || preferredLanguage >= kLanguageCount)
            preferredLanguage = -1;

        const char* langNames[] = {
            "Auto (ROM/save default)", "Japanese", "English", "French",
            "German", "Spanish", "Italian",
        };
        int langIdx = preferredLanguage + 1;

        ImGui::TextDisabled("Language");
        ImGui::SetNextItemWidth(ImGui::GetContentRegionAvail().x);
        if (ImGui::BeginCombo("##android_language", langNames[langIdx])) {
            for (int i = 0; i < 7; ++i) {
                bool isSupported = true;
                char label[128];
                std::strcpy(label, langNames[i]);

                if (!prelaunch && i > 0) {
                    const int langVal = i - 1;
                    if (gTranslations[langVal] == nullptr) {
                        isSupported = false;
                        std::strcat(label, " (not supported by loaded ROM)");
                    }
                }

                const bool selected = (i == langIdx);
                if (!isSupported)
                    ImGui::BeginDisabled();
                if (ImGui::Selectable(label, selected)) {
                    Port_Config_SetPreferredLanguage(i - 1);
                    if (!prelaunch)
                        Port_ApplyLanguage();
                }
                if (selected)
                    ImGui::SetItemDefaultFocus();
                if (!isSupported)
                    ImGui::EndDisabled();
            }
            ImGui::EndCombo();
        }

        if (prelaunch)
            ImGui::TextWrapped("Language is applied after the selected ROM loads.");

        return regionChanged;
    }
#endif
'''
src = src[:insert_at] + android_region + src[insert_at:]

# ---------------------------------------------------------------------------
# Prelaunch card: responsive width, no right-aligned overlapping ROM button,
# full-width Play/Select button, and wrapped helper text.
# ---------------------------------------------------------------------------
old_card = """    ImGui::SetNextWindowPos(viewport_center, ImGuiCond_Always, ImVec2(0.5f, 0.5f));
    ImGui::SetNextWindowSize(ImVec2(620, 0), ImGuiCond_Always);
    /* Cap the card's auto-height to the visible work area so a small or
     * default-sized window never pushes the Select ROM / Play buttons
     * off-screen; with the scrollbar enabled (below) they stay reachable
     * without having to resize the window first (v0.6 oversight). */
    ImGui::SetNextWindowSizeConstraints(ImVec2(620, 0.0f), ImVec2(620, vp->WorkSize.y));
"""
new_card = """    ImGui::SetNextWindowPos(viewport_center, ImGuiCond_Always, ImVec2(0.5f, 0.5f));
#ifdef __ANDROID__
    const float prelaunchW = std::clamp(vp->WorkSize.x * 0.72f, 760.0f, 1120.0f);
    ImGui::SetNextWindowSize(ImVec2(prelaunchW, 0), ImGuiCond_Always);
    ImGui::SetNextWindowSizeConstraints(ImVec2(prelaunchW, 0.0f),
                                        ImVec2(prelaunchW, vp->WorkSize.y));
#else
    ImGui::SetNextWindowSize(ImVec2(620, 0), ImGuiCond_Always);
    /* Cap the card's auto-height to the visible work area so a small or
     * default-sized window never pushes the Select ROM / Play buttons
     * off-screen; with the scrollbar enabled (below) they stay reachable
     * without having to resize the window first (v0.6 oversight). */
    ImGui::SetNextWindowSizeConstraints(ImVec2(620, 0.0f), ImVec2(620, vp->WorkSize.y));
#endif
"""
if old_card not in src:
    raise SystemExit("prelaunch card geometry block not found")
src = src.replace(old_card, new_card, 1)

old_rom = """        if (rom_present) {
            ImGui::PushStyleColor(ImGuiCol_Text, subtxt);
            ImGui::TextUnformatted("Version");
            ImGui::PopStyleColor();
            ImGui::SameLine(170.0f);
            ImGui::TextUnformatted(version ? version : "?");

            ImGui::PushStyleColor(ImGuiCol_Text, subtxt);
            ImGui::TextUnformatted("ROM");
            ImGui::PopStyleColor();
            ImGui::SameLine(170.0f);
            ImGui::TextUnformatted(rom_name ? rom_name : "?");
            ImGui::SameLine();
            /* Right-align the Change-ROM button to the edge of the card. */
            {
                const char* lbl = "Change ROM...";
                float bw = ImGui::CalcTextSize(lbl).x + ImGui::GetStyle().FramePadding.x * 2.0f;
                float pad = ImGui::GetStyle().WindowPadding.x;
                ImGui::SameLine(win_w - pad - bw);
                if (ImGui::Button(lbl)) {
                    if (out_change_rom)
                        *out_change_rom = true;
                }
            }
        } else {
"""
new_rom = """        if (rom_present) {
#ifdef __ANDROID__
            ImGui::PushStyleColor(ImGuiCol_Text, subtxt);
            ImGui::TextUnformatted("Version");
            ImGui::PopStyleColor();
            ImGui::SameLine();
            ImGui::TextUnformatted(version ? version : "?");

            ImGui::PushStyleColor(ImGuiCol_Text, subtxt);
            ImGui::TextUnformatted("ROM");
            ImGui::PopStyleColor();
            ImGui::SameLine();
            ImGui::TextWrapped(rom_name ? rom_name : "?");

            if (ImGui::Button("Change ROM...", ImVec2(ImGui::GetContentRegionAvail().x, 56.0f))) {
                if (out_change_rom)
                    *out_change_rom = true;
            }
#else
            ImGui::PushStyleColor(ImGuiCol_Text, subtxt);
            ImGui::TextUnformatted("Version");
            ImGui::PopStyleColor();
            ImGui::SameLine(170.0f);
            ImGui::TextUnformatted(version ? version : "?");

            ImGui::PushStyleColor(ImGuiCol_Text, subtxt);
            ImGui::TextUnformatted("ROM");
            ImGui::PopStyleColor();
            ImGui::SameLine(170.0f);
            ImGui::TextUnformatted(rom_name ? rom_name : "?");
            ImGui::SameLine();
            {
                const char* lbl = "Change ROM...";
                float bw = ImGui::CalcTextSize(lbl).x + ImGui::GetStyle().FramePadding.x * 2.0f;
                float pad = ImGui::GetStyle().WindowPadding.x;
                ImGui::SameLine(win_w - pad - bw);
                if (ImGui::Button(lbl)) {
                    if (out_change_rom)
                        *out_change_rom = true;
                }
            }
#endif
        } else {
"""
if old_rom not in src:
    raise SystemExit("prelaunch ROM info block not found")
src = src.replace(old_rom, new_rom, 1)

old_action = """        {
            const bool is_select = !rom_present;
            const char* lbl = is_select ? "Select ROM..." : "Play";
            const ImVec2 sz(is_select ? 260.0f : 220.0f, 48.0f);
            ImGui::PushStyleVar(ImGuiStyleVar_FrameRounding, 12.0f);
            ImGui::PushStyleColor(ImGuiCol_Button, ImVec4(0.18f, 0.42f, 0.24f, 1.0f));
            ImGui::PushStyleColor(ImGuiCol_ButtonHovered, ImVec4(0.28f, 0.55f, 0.34f, 1.0f));
            ImGui::PushStyleColor(ImGuiCol_ButtonActive, ImVec4(0.40f, 0.72f, 0.46f, 1.0f));
            ImGui::SetCursorPosX((win_w - sz.x) * 0.5f);
            ImGui::SetWindowFontScale(1.4f);
            const bool clicked = ImGui::Button(lbl, sz) ||
                                 ImGui::IsKeyPressed(ImGuiKey_GamepadFaceDown, false) ||
                                 ImGui::IsKeyPressed(ImGuiKey_Enter) ||
                                 ImGui::IsKeyPressed(ImGuiKey_KeypadEnter) ||
                                 ImGui::IsKeyPressed(ImGuiKey_Space);
            if (clicked) {
                if (is_select) {
                    if (out_change_rom)
                        *out_change_rom = true;
                } else {
                    if (out_play)
                        *out_play = true;
                }
            }
            ImGui::SetWindowFontScale(1.0f);
            ImGui::PopStyleColor(3);
            ImGui::PopStyleVar();
        }

        ImGui::Dummy(ImVec2(0, 6));
        ImGui::PushStyleColor(ImGuiCol_Text, subtxt);
        CenteredText(rom_present ? "Press Enter or click Play to start"
                                 : "Press Enter or click to pick your .gba file");
        ImGui::PopStyleColor();
"""
new_action = """        {
            const bool is_select = !rom_present;
            const char* lbl = is_select ? "Select ROM..." : "Play";
#ifdef __ANDROID__
            const ImVec2 sz(ImGui::GetContentRegionAvail().x, 64.0f);
#else
            const ImVec2 sz(is_select ? 260.0f : 220.0f, 48.0f);
#endif
            ImGui::PushStyleVar(ImGuiStyleVar_FrameRounding, 12.0f);
            ImGui::PushStyleColor(ImGuiCol_Button, ImVec4(0.18f, 0.42f, 0.24f, 1.0f));
            ImGui::PushStyleColor(ImGuiCol_ButtonHovered, ImVec4(0.28f, 0.55f, 0.34f, 1.0f));
            ImGui::PushStyleColor(ImGuiCol_ButtonActive, ImVec4(0.40f, 0.72f, 0.46f, 1.0f));
#ifndef __ANDROID__
            ImGui::SetCursorPosX((win_w - sz.x) * 0.5f);
            ImGui::SetWindowFontScale(1.4f);
#endif
            const bool clicked = ImGui::Button(lbl, sz) || ImGui::IsKeyPressed(ImGuiKey_Enter) ||
                                 ImGui::IsKeyPressed(ImGuiKey_KeypadEnter) || ImGui::IsKeyPressed(ImGuiKey_Space);
            if (clicked) {
                if (is_select) {
                    if (out_change_rom)
                        *out_change_rom = true;
                } else {
                    if (out_play)
                        *out_play = true;
                }
            }
#ifndef __ANDROID__
            ImGui::SetWindowFontScale(1.0f);
#endif
            ImGui::PopStyleColor(3);
            ImGui::PopStyleVar();
        }

        ImGui::Dummy(ImVec2(0, 6));
        ImGui::PushStyleColor(ImGuiCol_Text, subtxt);
#ifdef __ANDROID__
        ImGui::TextWrapped(rom_present ? "Press A, Enter, or tap Play to start."
                                       : "Press A, Enter, or tap Select ROM to choose your .gba file.");
#else
        CenteredText(rom_present ? "Press Enter or click Play to start"
                                 : "Press Enter or click to pick your .gba file");
#endif
        ImGui::PopStyleColor();
"""
if old_action not in src:
    raise SystemExit("prelaunch action button block not found")
src = src.replace(old_action, new_action, 1)

menu.write_text(src, encoding="utf-8")
print("Applied Android UI fit v3: full-width rails, fields, and prelaunch controls")
