/* Profiles ribbon tab — extracted from port_imgui_menu.cpp. Included into the same
 * translation unit; relies on the declarations already visible there. */

#include <SDL3/SDL_dialog.h>

/* Android/desktop save transfer. SDL3's file-dialog backend returns content://
 * URIs on Android; SDL_LoadFile / SDL_SaveFile route those through the
 * ContentResolver, so this works without broad storage permissions. */
enum ProfileTransferStatus {
    PROFILE_TRANSFER_IDLE = 0,
    PROFILE_TRANSFER_PENDING,
    PROFILE_TRANSFER_SELECTED,
    PROFILE_TRANSFER_CANCELLED,
    PROFILE_TRANSFER_ERROR,
};

static SDL_AtomicInt sProfileImportStatus;
static SDL_AtomicInt sProfileExportStatus;
static char sProfileImportUri[4096] = {};
static char sProfileExportUri[4096] = {};
static unsigned char sProfileExportBytes[0x2000] = {};

static const SDL_DialogFileFilter kProfileSaveFilters[] = {
    { "Minish Cap save", "sav;srm" },
    { "All files", "*" },
};

static void SDLCALL ProfileImportDialogCallback(void*, const char* const* filelist, int) {
    if (!filelist) {
        SDL_SetAtomicInt(&sProfileImportStatus, PROFILE_TRANSFER_ERROR);
        return;
    }
    if (!filelist[0]) {
        SDL_SetAtomicInt(&sProfileImportStatus, PROFILE_TRANSFER_CANCELLED);
        return;
    }
    std::snprintf(sProfileImportUri, sizeof(sProfileImportUri), "%s", filelist[0]);
    SDL_SetAtomicInt(&sProfileImportStatus, PROFILE_TRANSFER_SELECTED);
}

static void SDLCALL ProfileExportDialogCallback(void*, const char* const* filelist, int) {
    if (!filelist) {
        SDL_SetAtomicInt(&sProfileExportStatus, PROFILE_TRANSFER_ERROR);
        return;
    }
    if (!filelist[0]) {
        SDL_SetAtomicInt(&sProfileExportStatus, PROFILE_TRANSFER_CANCELLED);
        return;
    }
    std::snprintf(sProfileExportUri, sizeof(sProfileExportUri), "%s", filelist[0]);
    SDL_SetAtomicInt(&sProfileExportStatus, PROFILE_TRANSFER_SELECTED);
}

static bool ProfileHasKnownSignature(const unsigned char* image) {
    static const char kUsa[] = "AGBZELDA:THE MINISH CAP:ZELDA 5";
    static const char kEuJp[] = "AGBZELDA:THE MINISH CAP:ZELDA 3";
    constexpr size_t kSigLen = sizeof(kUsa) - 1;
    return std::memcmp(image, kUsa, kSigLen) == 0 ||
           std::memcmp(image, kEuJp, kSigLen) == 0 ||
           std::memcmp(image + 0x1000, kUsa, kSigLen) == 0 ||
           std::memcmp(image + 0x1000, kEuJp, kSigLen) == 0;
}

static void ProfileReverseEepromBlocks(unsigned char* image) {
    for (size_t b = 0; b < 0x2000; b += 8) {
        for (size_t i = 0; i < 4; ++i) {
            const unsigned char t = image[b + i];
            image[b + i] = image[b + 7 - i];
            image[b + 7 - i] = t;
        }
    }
}

static bool ProfileValidateImportedSave(const void* bytes, size_t len) {
    if (!bytes || len < 0x2000)
        return false;

    const unsigned char* src = static_cast<const unsigned char*>(bytes);
    for (size_t i = 0x2000; i < len; ++i) {
        if (src[i] != 0xFF)
            return false;
    }

    if (ProfileHasKnownSignature(src))
        return true;

    unsigned char converted[0x2000];
    std::memcpy(converted, src, sizeof(converted));
    ProfileReverseEepromBlocks(converted);
    return ProfileHasKnownSignature(converted);
}

static bool ProfileFindFreeImportName(char out[64]) {
    for (int i = 1; i <= 99; ++i) {
        std::snprintf(out, 64, "tmc_import_%d.sav", i);
        FILE* probe = std::fopen(out, "rb");
        if (!probe)
            return true;
        std::fclose(probe);
    }
    return false;
}

static void ProfileProcessImportResult(void) {
    const int status = SDL_GetAtomicInt(&sProfileImportStatus);
    if (status == PROFILE_TRANSFER_SELECTED) {
        size_t len = 0;
        void* bytes = SDL_LoadFile(sProfileImportUri, &len);
        if (!bytes) {
            Port_DebugMenu_ToastFromExternal("Import failed: could not read selected file");
        } else if (!ProfileValidateImportedSave(bytes, len)) {
            Port_DebugMenu_ToastFromExternal("Import refused: not a valid Minish Cap save");
        } else {
            char name[64];
            if (!ProfileFindFreeImportName(name)) {
                Port_DebugMenu_ToastFromExternal("Import failed: no free import profile slots");
            } else {
                FILE* out = std::fopen(name, "wb");
                const bool ok = out &&
                    std::fwrite(bytes, 1, 0x2000, out) == 0x2000 &&
                    std::fclose(out) == 0;
                if (out && !ok)
                    std::fclose(out);
                if (ok) {
                    char msg[128];
                    std::snprintf(msg, sizeof(msg), "Imported as %s - Activate it, then return to title", name);
                    Port_DebugMenu_ToastFromExternal(msg);
                } else {
                    Port_DebugMenu_ToastFromExternal("Import failed: could not create profile");
                }
            }
        }
        if (bytes)
            SDL_free(bytes);
        SDL_SetAtomicInt(&sProfileImportStatus, PROFILE_TRANSFER_IDLE);
    } else if (status == PROFILE_TRANSFER_CANCELLED) {
        SDL_SetAtomicInt(&sProfileImportStatus, PROFILE_TRANSFER_IDLE);
    } else if (status == PROFILE_TRANSFER_ERROR) {
        Port_DebugMenu_ToastFromExternal("Import dialog failed");
        SDL_SetAtomicInt(&sProfileImportStatus, PROFILE_TRANSFER_IDLE);
    }
}

static bool ProfileSnapshotForExport(void) {
    static const char* kTemp = "tmc_export_tmp.sav";
    if (!Port_Save_SaveAsProfile(kTemp))
        return false;

    FILE* in = std::fopen(kTemp, "rb");
    bool ok = false;
    if (in) {
        ok = std::fread(sProfileExportBytes, 1, sizeof(sProfileExportBytes), in) ==
             sizeof(sProfileExportBytes);
        std::fclose(in);
    }
    std::remove(kTemp);
    return ok;
}

static void ProfileProcessExportResult(void) {
    const int status = SDL_GetAtomicInt(&sProfileExportStatus);
    if (status == PROFILE_TRANSFER_SELECTED) {
        if (SDL_SaveFile(sProfileExportUri, sProfileExportBytes, sizeof(sProfileExportBytes))) {
            Port_DebugMenu_ToastFromExternal("Save exported");
        } else {
            Port_DebugMenu_ToastFromExternal("Export failed: could not write selected file");
        }
        SDL_SetAtomicInt(&sProfileExportStatus, PROFILE_TRANSFER_IDLE);
    } else if (status == PROFILE_TRANSFER_CANCELLED) {
        SDL_SetAtomicInt(&sProfileExportStatus, PROFILE_TRANSFER_IDLE);
    } else if (status == PROFILE_TRANSFER_ERROR) {
        Port_DebugMenu_ToastFromExternal("Export dialog failed");
        SDL_SetAtomicInt(&sProfileExportStatus, PROFILE_TRANSFER_IDLE);
    }
}


static void DrawRibbonProfilesTab(void) {
    ProfileProcessImportResult();
    ProfileProcessExportResult();
    char names[32][64];
    const int n = Port_Save_ListProfiles(names, 32);
    const std::string activeNow = Port_Save_GetActivePath();

    ImGui::Text("Active profile: %s", activeNow.c_str());
    ImGui::Separator();

    /* Rename buffer keyed by index, so each row has its own inline
     * editor that survives across frames while the user is typing. */
    static char sRenameBuf[32][64] = {};
    static int sRenameRow = -1;
    static int sConfirmDeleteRow = -1;

    if (ImGui::BeginTable("##profiles_table", 3, ImGuiTableFlags_SizingFixedFit | ImGuiTableFlags_RowBg)) {
        ImGui::TableSetupColumn("Profile File", ImGuiTableColumnFlags_WidthFixed, 180.0f);
        ImGui::TableSetupColumn("Status", ImGuiTableColumnFlags_WidthFixed, 100.0f);
        ImGui::TableSetupColumn("Actions", ImGuiTableColumnFlags_WidthStretch);

        for (int i = 0; i < n; ++i) {
            ImGui::PushID(i);
            ImGui::TableNextRow();

            // Column 1: Profile Name
            ImGui::TableSetColumnIndex(0);
            ImGui::Text("%s", names[i]);

            // Column 2: Status
            ImGui::TableSetColumnIndex(1);
            bool isActive = (std::string(names[i]) == activeNow);
            if (isActive) {
                ImGui::TextColored(ImVec4(1.0f, 0.94f, 0.25f, 1.0f), "active");
            } else {
                ImGui::TextDisabled("-");
            }

            // Column 3: Actions
            ImGui::TableSetColumnIndex(2);
            if (!isActive) {
                if (ImGui::Button("Activate")) {
                    if (Port_Save_SetActivePath(names[i])) {
                        Port_Config_SetActiveSaveProfile(names[i]);
                        Port_DebugMenu_ToastFromExternal("Profile activated - go to title to load");
                    } else {
                        Port_DebugMenu_ToastFromExternal("Cannot switch profiles: current save could not be written");
                    }
                }
                ImGui::SameLine();
            }
            const bool isDefault = (std::strcmp(names[i], "tmc.sav") == 0);
            if (!isDefault) {
                if (ImGui::Button("Rename")) {
                    sRenameRow = i;
                    snprintf(sRenameBuf[i], sizeof(sRenameBuf[i]), "%s", names[i]);
                }
                ImGui::SameLine();
                if (ImGui::Button("Delete"))
                    sConfirmDeleteRow = i;
            }

            if (sRenameRow == i) {
                ImGui::TableNextRow();
                ImGui::TableSetColumnIndex(0);
                ImGui::PushItemWidth(160);
                ImGui::InputText("##rename", sRenameBuf[i], sizeof(sRenameBuf[i]));
                ImGui::PopItemWidth();
                ImGui::TableSetColumnIndex(2);
                if (ImGui::Button("OK")) {
                    if (Port_Save_RenameProfile(names[i], sRenameBuf[i])) {
                        Port_DebugMenu_ToastFromExternal("Profile renamed");
                    } else {
                        Port_DebugMenu_ToastFromExternal("Rename refused (clash / bad name / default)");
                    }
                    sRenameRow = -1;
                }
                ImGui::SameLine();
                if (ImGui::Button("X"))
                    sRenameRow = -1;
            }
            if (sConfirmDeleteRow == i) {
                ImGui::TableNextRow();
                ImGui::TableSetColumnIndex(0);
                ImGui::TextColored(ImVec4(0.9f, 0.35f, 0.35f, 1.0f), "Delete %s?", names[i]);
                ImGui::TableSetColumnIndex(2);
                if (ImGui::Button("Confirm delete")) {
                    if (Port_Save_DeleteProfile(names[i])) {
                        Port_DebugMenu_ToastFromExternal("Profile deleted");
                    } else {
                        Port_DebugMenu_ToastFromExternal("Delete refused (active / bad name)");
                    }
                    sConfirmDeleteRow = -1;
                    sRenameRow = -1;
                }
                ImGui::SameLine();
                if (ImGui::Button("Cancel"))
                    sConfirmDeleteRow = -1;
            }
            ImGui::PopID();
        }
        ImGui::EndTable();
    }

    ImGui::Separator();
    ImGui::TextUnformatted("Android / emulator save transfer");

    const bool importBusy =
        SDL_GetAtomicInt(&sProfileImportStatus) == PROFILE_TRANSFER_PENDING;
    const bool exportBusy =
        SDL_GetAtomicInt(&sProfileExportStatus) == PROFILE_TRANSFER_PENDING;

    if (importBusy || exportBusy)
        ImGui::BeginDisabled();

    if (ImGui::Button("Import .sav / .srm")) {
        sProfileImportUri[0] = '\0';
        SDL_SetAtomicInt(&sProfileImportStatus, PROFILE_TRANSFER_PENDING);
        SDL_ShowOpenFileDialog(ProfileImportDialogCallback, nullptr, sWindow,
                               kProfileSaveFilters, 2, nullptr, false);
    }
    ImGui::SameLine();
    if (ImGui::Button("Export current save")) {
        if (ProfileSnapshotForExport()) {
            sProfileExportUri[0] = '\0';
            SDL_SetAtomicInt(&sProfileExportStatus, PROFILE_TRANSFER_PENDING);
            SDL_ShowSaveFileDialog(ProfileExportDialogCallback, nullptr, sWindow,
                                   kProfileSaveFilters, 2, "tmc.sav");
        } else {
            Port_DebugMenu_ToastFromExternal("Export failed: could not snapshot current save");
        }
    }

    if (importBusy || exportBusy)
        ImGui::EndDisabled();

    ImGui::TextDisabled("Imports are added as inactive tmc_import_#.sav profiles.");
    ImGui::TextDisabled("Activate the imported profile, then return to title before loading it.");


    ImGui::Separator();
    if (ImGui::Button("+ Save current as new profile")) {
        char name[64];
        int k = 1;
        for (; k <= 99; ++k) {
            std::snprintf(name, sizeof(name), "tmc_%d.sav", k);
            FILE* probe = std::fopen(name, "rb");
            if (!probe)
                break;
            std::fclose(probe);
        }
        if (k > 99)
            Port_DebugMenu_ToastFromExternal("No free profile slots (1-99)");
        else if (Port_Save_SaveAsProfile(name)) {
            char msg[96];
            std::snprintf(msg, sizeof(msg), "Saved current as %s", name);
            Port_DebugMenu_ToastFromExternal(msg);
        } else {
            Port_DebugMenu_ToastFromExternal("Save failed");
        }
    }
}
