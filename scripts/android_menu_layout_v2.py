#!/usr/bin/env python3
from pathlib import Path

menu = Path("upstream/tmc/port/port_imgui_menu.cpp")
src = menu.read_text(encoding="utf-8")

# ---------------------------------------------------------------------------
# Main Android settings menu: use phone-relative geometry instead of desktop
# fixed pixel widths that clip category names on high-resolution landscape
# phones.
# ---------------------------------------------------------------------------
old = """        const float railW = 238.0f;
        if (ImGui::BeginChild("##android_categories", ImVec2(railW, -1), true,
                              ImGuiWindowFlags_NoScrollbar)) {
"""
new = """        const float railW = std::clamp(io.DisplaySize.x * 0.22f, 460.0f, 680.0f);
        const float categoryRowH = std::clamp(io.DisplaySize.y * 0.052f, 58.0f, 82.0f);
        if (ImGui::BeginChild("##android_categories", ImVec2(railW, -1), true,
                              ImGuiWindowFlags_AlwaysVerticalScrollbar)) {
"""
if old not in src:
    raise SystemExit("Android category rail geometry anchor not found")
src = src.replace(old, new, 1)
src = src.replace(
    'ImGui::Selectable(kCategories[i].label, selected, 0, ImVec2(-1.0f, 46.0f))',
    'ImGui::Selectable(kCategories[i].label, selected, 0, ImVec2(-1.0f, categoryRowH))',
    1
)

# ---------------------------------------------------------------------------
# Android Port/Randomizer setup: replace the narrow desktop sidebar with a
# full-screen controller-first two-pane layout.
# ---------------------------------------------------------------------------
anchor = "static void DrawRandoFileMenuModal(void) {\n"
if anchor not in src:
    raise SystemExit("DrawRandoFileMenuModal anchor not found")

helper = r'''
#ifdef __ANDROID__
static void DrawAndroidFileSetup(bool forceOpen) {
    static int section = 0;
    static bool wasVisible = false;
    static const char* kSections[] = {
        "Randomizer",
        "Display",
        "Audio",
        "Save Profiles",
        "Accessibility",
    };
    constexpr int kSectionCount = (int)(sizeof(kSections) / sizeof(kSections[0]));

    bool sectionChanged = !wasVisible;
    wasVisible = true;

    if (ImGui::IsKeyPressed(ImGuiKey_GamepadL1, false)) {
        section = (section + kSectionCount - 1) % kSectionCount;
        sectionChanged = true;
    }
    if (ImGui::IsKeyPressed(ImGuiKey_GamepadR1, false)) {
        section = (section + 1) % kSectionCount;
        sectionChanged = true;
    }

    const bool popupOpen =
        ImGui::IsPopupOpen("", ImGuiPopupFlags_AnyPopupId | ImGuiPopupFlags_AnyPopupLevel);

    /* B is a real controller Back action. Do not require "nothing focused":
     * a controller UI always has something focused, which made B appear dead
     * in the old sidebar. Text entry/popups keep ownership while active. */
    if (!popupOpen && !ImGui::GetIO().WantTextInput &&
        ImGui::IsKeyPressed(ImGuiKey_GamepadFaceRight, false)) {
        if (forceOpen) {
            Port_RandoFileMenu_Cancel();
        } else {
            Port_RandoFileMenu_SetSidebarOpen(false);
            Rando_PlayCancelSfx();
        }
        wasVisible = false;
        return;
    }

    const ImGuiViewport* vp = ImGui::GetMainViewport();
    ImGui::SetNextWindowPos(vp->WorkPos, ImGuiCond_Always);
    ImGui::SetNextWindowSize(vp->WorkSize, ImGuiCond_Always);
    ImGui::PushStyleVar(ImGuiStyleVar_WindowRounding, 0.0f);
    ImGui::PushStyleVar(ImGuiStyleVar_WindowPadding, ImVec2(18.0f, 16.0f));

    if (ImGui::Begin("##android_file_setup", nullptr,
                     ImGuiWindowFlags_NoTitleBar | ImGuiWindowFlags_NoResize |
                         ImGuiWindowFlags_NoMove | ImGuiWindowFlags_NoCollapse |
                         ImGuiWindowFlags_NoSavedSettings)) {
        ImGui::TextColored(ImVec4(0.58f, 0.94f, 0.68f, 1.0f),
                           "PORT & RANDOMIZER SETUP");
        ImGui::SameLine();
        ImGui::TextDisabled("  L1/R1 section   D-pad navigate   A select   B back");
        ImGui::Separator();

        const float railW = std::clamp(vp->WorkSize.x * 0.22f, 460.0f, 680.0f);
        const float rowH = std::clamp(vp->WorkSize.y * 0.065f, 66.0f, 92.0f);
        const float footerH = forceOpen ? 112.0f : 92.0f;

        if (ImGui::BeginChild("##file_setup_sections", ImVec2(railW, -1), true,
                              ImGuiWindowFlags_NoScrollbar)) {
            for (int i = 0; i < kSectionCount; ++i) {
                ImGui::PushID(i);
                const bool selected = section == i;
                if (selected) {
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
                if (ImGui::IsItemFocused() && section != i) {
                    section = i;
                    sectionChanged = true;
                }

                if (selected)
                    ImGui::PopStyleColor(3);
                ImGui::PopID();
            }
        }
        ImGui::EndChild();

        ImGui::SameLine();

        ImGui::BeginGroup();
        if (ImGui::BeginChild("##file_setup_content", ImVec2(0, -footerH), true,
                              ImGuiWindowFlags_AlwaysVerticalScrollbar)) {
            ImGui::TextColored(ImVec4(0.82f, 0.96f, 0.85f, 1.0f), "%s", kSections[section]);
            ImGui::Separator();
            ImGui::Spacing();

            if (sectionChanged)
                ImGui::SetKeyboardFocusHere(0);

            switch (section) {
                case 0: {
                    bool randoEnabled = Port_RandoFileMenu_GetRandoOptionEnabled();
                    if (ImGui::Checkbox("Enable Randomizer Mode", &randoEnabled))
                        Port_RandoFileMenu_SetRandoOptionEnabled(randoEnabled);

                    ImGui::TextWrapped(
                        "Off starts a normal vanilla save. On generates a randomized seed "
                        "using the options below.");

                    if (randoEnabled) {
                        ImGui::SeparatorText("Seed & logic");

                        const float contentW = ImGui::GetContentRegionAvail().x;
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

                        ImGui::SeparatorText("World rules");
                        if (ImGui::BeginTable("##rando_phone_rules", 2,
                                              ImGuiTableFlags_SizingStretchSame |
                                                  ImGuiTableFlags_PadOuterX)) {
                            ImGui::TableNextColumn();
                            ImGui::Checkbox("Glitchless logic", Port_RandoFileMenu_GlitchlessLogic());
                            ImGui::TableNextColumn();
                            ImGui::Checkbox("Obscure spots", Port_RandoFileMenu_ObscureLocations());
                            ImGui::TableNextColumn();
                            ImGui::Checkbox("Kinstones", Port_RandoFileMenu_ShuffleKinstones());
                            ImGui::TableNextColumn();
                            ImGui::Checkbox("Entrances", Port_RandoFileMenu_ShuffleEntrances());
                            ImGui::TableNextColumn();
                            ImGui::Checkbox("Dojos", Port_RandoFileMenu_ShuffleDojos());
                            ImGui::TableNextColumn();
                            ImGui::Checkbox("Dungeon items", Port_RandoFileMenu_ShuffleDungeonItems());
                            ImGui::TableNextColumn();
                            ImGui::Checkbox("Open world", Port_RandoFileMenu_OpenWorld());
                            ImGui::TableNextColumn();
                            ImGui::Checkbox("Sleep warp", Port_RandoFileMenu_Homewarp());
                            ImGui::TableNextColumn();
                            ImGui::Checkbox("Start Sword", Port_RandoFileMenu_StartSword());
                            ImGui::TableNextColumn();
                            ImGui::Checkbox("Early Crests", Port_RandoFileMenu_EarlyCrests());
                            ImGui::TableNextColumn();
                            ImGui::Checkbox("Fast Text", Port_RandoFileMenu_InstantText());
                            ImGui::EndTable();
                        }

                        ImGui::SeparatorText("Appearance & accessibility");
                        static const char* kTunicColors[] =
                            { "Green", "Red", "Blue", "Purple", "Orange", "Grey", "Random" };
                        static const char* kHeartColors[] =
                            { "Red", "Blue", "Green", "Yellow", "Purple", "Rainbow", "Random" };

                        ImGui::SetNextItemWidth(contentW * 0.50f);
                        ImGui::Combo("Tunic color", Port_RandoFileMenu_TunicColor(), kTunicColors, 7);
                        ImGui::SetNextItemWidth(contentW * 0.50f);
                        ImGui::Combo("Heart color", Port_RandoFileMenu_HeartColor(), kHeartColors, 7);
                        ImGui::SetNextItemWidth(contentW * 0.50f);
                        ImGui::Combo("Accessibility", Port_RandoFileMenu_Accessibility(),
                                     kRandoAccessCombo, RANDO_ACCESS_COUNT);

                        if (!*Port_RandoFileMenu_GlitchlessLogic()) {
                            ImGui::SeparatorText("Advanced tricks");
                            ImGui::CheckboxFlags(kRandoTrickOcarina, Port_RandoFileMenu_Tricks(),
                                                 RANDO_TRICK_OCARINA_GLITCH);
                            ImGui::CheckboxFlags(kRandoTrickCrenel, Port_RandoFileMenu_Tricks(),
                                                 RANDO_TRICK_CRENEL_CLIP);
                            ImGui::CheckboxFlags(kRandoTrickPjs, Port_RandoFileMenu_Tricks(),
                                                 RANDO_TRICK_PORTAL_JUMP_STORAGE);
                        }

                        const char* status = Port_RandoFileMenu_Status();
                        if (status[0])
                            ImGui::TextColored(ImVec4(1.0f, 0.44f, 0.44f, 1.0f), "%s", status);

                        char sfp[16];
                        std::snprintf(sfp, sizeof(sfp), "%08X", Port_RandoFileMenu_Fingerprint());
                        ImGui::Text("Settings hash: %s", sfp);
                    }
                    break;
                }
                case 1:
                    DrawRibbonDisplayTab();
                    break;
                case 2:
                    DrawRibbonAudioTab();
                    break;
                case 3:
                    DrawRibbonProfilesTab();
                    break;
                case 4:
                    DrawRibbonAccessibilityTab();
                    break;
            }
        }
        ImGui::EndChild();

        ImGui::Separator();

        const float buttonW = (ImGui::GetContentRegionAvail().x - ImGui::GetStyle().ItemSpacing.x) * 0.5f;
        if (forceOpen) {
            if (ImGui::Button("Generate & Start", ImVec2(buttonW, 54.0f)))
                Port_RandoFileMenu_CommitAndStart();
            ImGui::SameLine();
            if (ImGui::Button("Cancel", ImVec2(buttonW, 54.0f)))
                Port_RandoFileMenu_Cancel();
        } else {
            if (ImGui::Button("Close Setup", ImVec2(-1.0f, 54.0f))) {
                Port_RandoFileMenu_SetSidebarOpen(false);
                Rando_PlayCancelSfx();
                wasVisible = false;
            }
        }
        ImGui::EndGroup();
    }
    ImGui::End();
    ImGui::PopStyleVar(2);
}
#endif

'''

src = src.replace(anchor, helper + anchor, 1)
src = src.replace(
"""static void DrawRandoFileMenuModal(void) {
    bool forceOpen = Port_RandoFileMenu_IsModalOpen();
""",
"""static void DrawRandoFileMenuModal(void) {
    bool forceOpen = Port_RandoFileMenu_IsModalOpen();
#ifdef __ANDROID__
    const bool androidShow = forceOpen || (Rando_IsInFileSelect() && Port_RandoFileMenu_IsSidebarOpen());
    if (androidShow) {
        DrawAndroidFileSetup(forceOpen);
        return;
    }
#endif
""", 1)

menu.write_text(src, encoding="utf-8")

# ---------------------------------------------------------------------------
# Display tab: the 150px desktop label column truncates Android labels after
# the larger phone font/style scaling. Use a proportional label column.
# ---------------------------------------------------------------------------
display = Path("upstream/tmc/port/port_imgui_display_tab.inc")
d = display.read_text(encoding="utf-8")
old = """static void DrawRibbonDisplayTab(void) {
    const bool gpuActive = Port_GPU_IsActive();

    if (ImGui::BeginTable("##display_settings_table", 2, ImGuiTableFlags_SizingFixedFit)) {
        ImGui::TableSetupColumn("Label", ImGuiTableColumnFlags_WidthFixed, 150.0f);
"""
new = """static void DrawRibbonDisplayTab(void) {
    const bool gpuActive = Port_GPU_IsActive();
#ifdef __ANDROID__
    const float displayLabelW =
        std::clamp(ImGui::GetContentRegionAvail().x * 0.28f, 300.0f, 440.0f);
#else
    const float displayLabelW = 150.0f;
#endif

    if (ImGui::BeginTable("##display_settings_table", 2, ImGuiTableFlags_SizingFixedFit)) {
        ImGui::TableSetupColumn("Label", ImGuiTableColumnFlags_WidthFixed, displayLabelW);
"""
if old not in d:
    raise SystemExit("Display table label-width anchor not found")
d = d.replace(old, new, 1)
d = d.replace("ImGui::Indent(150.0f);", "ImGui::Indent(displayLabelW);")
d = d.replace("ImGui::Unindent(150.0f);", "ImGui::Unindent(displayLabelW);")
display.write_text(d, encoding="utf-8")

# ---------------------------------------------------------------------------
# Once the Android file setup overlay is open, L1 is now section navigation.
# Do not also interpret it as "close the sidebar". B/Close Setup is the native
# back action. Desktop retains the old second-L toggle behavior.
# ---------------------------------------------------------------------------
bios = Path("upstream/tmc/port/port_bios.c")
b = bios.read_text(encoding="utf-8")
old = """            if (Port_RandoFileMenu_IsSidebarOpen() && !Port_RandoFileMenu_IsModalOpen() &&
                !Port_ImGui_WantsTextInput() && Port_Config_EventIsInputDown(&e, PORT_INPUT_L)) {
                extern void Rando_PlayCancelSfx(void);
                Port_RandoFileMenu_SetSidebarOpen(false);
                Rando_PlayCancelSfx();
            }
"""
new = """#ifndef __ANDROID__
            if (Port_RandoFileMenu_IsSidebarOpen() && !Port_RandoFileMenu_IsModalOpen() &&
                !Port_ImGui_WantsTextInput() && Port_Config_EventIsInputDown(&e, PORT_INPUT_L)) {
                extern void Rando_PlayCancelSfx(void);
                Port_RandoFileMenu_SetSidebarOpen(false);
                Rando_PlayCancelSfx();
            }
#endif
"""
if old not in b:
    raise SystemExit("Randomizer sidebar L-close block not found")
b = b.replace(old, new, 1)
bios.write_text(b, encoding="utf-8")

print("Applied responsive Android settings/randomizer UI and controller navigation fixes")
