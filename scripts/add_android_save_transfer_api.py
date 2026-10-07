#!/usr/bin/env python3
from pathlib import Path

path = Path("upstream/tmc/port/port_save.c")
src = path.read_text(encoding="utf-8")

anchor = """int Port_Save_SaveAsProfile(const char* path) {
    if (path == NULL || path[0] == '\\0')
        return 0;
    /* Only allow writing into the managed profile lane so the "save as"
     * UI can't be pointed at an arbitrary host path. */
    if (!IsManagedProfilePath(path))
        return 0;
    /* Ensure EEPROM was loaded at least once so we have meaningful data
     * to copy. (Right after launch, before any read, sEeprom is zeroed.) */
    if (!sEepromInited) {
        LoadEepromFile();
        sEepromInited = 1;
    }
    return WriteEepromAtomic(path);
}
"""

addition = anchor + r'''

/* Import a save image supplied by a platform file picker into a NEW inactive
 * managed profile. This is intentionally byte-buffer based: Android SAF gives
 * SDL a content:// URI that stdio cannot open directly, so the UI reads the
 * bytes with SDL_LoadFile and hands them here for authoritative EEPROM
 * validation.
 *
 * Accepted inputs:
 *   - exact 8 KiB EEPROM images
 *   - emulator .srm images padded beyond 8 KiB with 0xFF
 *   - current mGBA/VBA-M on-disk byte order
 *   - legacy PC-port game-RAM byte order
 *
 * The imported profile is normalized to the current on-disk byte order and is
 * never made active automatically. That prevents a mid-game import from
 * replacing the live EEPROM backing store. Returns 1 on success. */
int Port_Save_ImportProfileBytes(const void* bytes, size_t len, char* outPath, size_t outPathLen) {
    if (bytes == NULL || len < EEPROM_SIZE || outPath == NULL || outPathLen == 0)
        return 0;

    const u8* src = (const u8*)bytes;
    for (size_t i = EEPROM_SIZE; i < len; ++i) {
        if (src[i] != 0xFF)
            return 0;
    }

    u8 image[EEPROM_SIZE];
    memcpy(image, src, EEPROM_SIZE);

    /* ClassifyRamEepromImage expects game-RAM byte order. A direct match means
     * a legacy PC save; otherwise reverse blocks and try normal emulator order. */
    EepromImageClass cls = ClassifyRamEepromImage(image);
    if (cls != EEPROM_IMAGE_ACTIVE_REGION && cls != EEPROM_IMAGE_OTHER_REGION) {
        ReverseEepromBlocks(image);
        cls = ClassifyRamEepromImage(image);
    }
    if (cls != EEPROM_IMAGE_ACTIVE_REGION && cls != EEPROM_IMAGE_OTHER_REGION)
        return 0;

    char name[SAVE_FILENAME_MAX];
    int found = 0;
    for (int i = 1; i <= 99; ++i) {
        snprintf(name, sizeof(name), "tmc_import_%d.sav", i);
        FILE* probe = fopen(name, "rb");
        if (probe == NULL) {
            found = 1;
            break;
        }
        fclose(probe);
    }
    if (!found)
        return 0;

    /* image is now in game-RAM order. Normalize the new profile to mGBA/VBA-M
     * wire order so later loads never need the legacy migration path. */
    ReverseEepromBlocks(image);
    FILE* out = fopen(name, "wb");
    if (out == NULL)
        return 0;
    int ok = fwrite(image, 1, EEPROM_SIZE, out) == EEPROM_SIZE;
    ok = (fclose(out) == 0) && ok;
    if (!ok) {
        remove(name);
        return 0;
    }

    snprintf(outPath, outPathLen, "%s", name);
    return 1;
}

/* Snapshot the currently loaded EEPROM to a caller-owned buffer in the same
 * mGBA/VBA-M byte order used by tmc.sav. This avoids creating a temporary
 * profile just to export through Android SAF. */
int Port_Save_ExportCurrentBytes(void* outBytes, size_t outLen) {
    if (outBytes == NULL || outLen < EEPROM_SIZE)
        return 0;
    if (!sEepromInited) {
        LoadEepromFile();
        sEepromInited = 1;
    }
    memcpy(outBytes, sEeprom, EEPROM_SIZE);
    ReverseEepromBlocks((u8*)outBytes);
    return 1;
}
'''

if anchor not in src:
    raise SystemExit("expected Port_Save_SaveAsProfile block not found")
if "Port_Save_ImportProfileBytes" in src:
    raise SystemExit("save-transfer API already present")

path.write_text(src.replace(anchor, addition, 1), encoding="utf-8")
print("Added authoritative save import/export buffer APIs")
