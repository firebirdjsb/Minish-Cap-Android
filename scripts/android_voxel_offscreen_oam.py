#!/usr/bin/env python3
"""Backport tmc PR #219 offscreen OAM world-entity rendering to Android.

Runs after the pinned upstream Android viewport/voxel patch chain. Changes
drawing only: gameplay CheckOnScreen remains native, and the normal 2D
RenderSpritePieces path is unchanged. Follow the PR's 256px top/side margin,
parking unrepresentable OAM pieces with true coordinates per VBlank-latched tag.

The Android 576px viewport requires a stricter round-trip OAM check than PR
#219: an encoded 9-bit x coordinate that aliases a different world x is parked.
"""
from pathlib import Path

root = Path(__file__).resolve().parents[1]
port = root / "upstream/tmc/port"


def checked_replace(source, old, new, name):
    count = source.count(old)
    if count != 1:
        raise SystemExit(f"{name}: expected 1 patch anchor, found {count}: {old[:130]!r}")
    return source.replace(old, new, 1)


header = port / "port_voxel.h"
src = header.read_text(encoding="utf-8")
src = checked_replace(src,
    "/* Per-OAM-slot anchor recorded by port_draw.c while it builds OAM",
    """/* Draw-only margins for characters seen by a tilted 3D camera. */
#define PORT_VOXEL_DRAW_TOP_MARGIN 256
#define PORT_VOXEL_DRAW_SIDE_MARGIN 256
#define PORT_VOXEL_OAM_MIN_Y (-96)
#define PORT_VOXEL_OAM_PARK_Y 160

/* Pure placement rules exercised by the native/widescreen scene tests.
 * OAM attr1 stores x modulo 512. DecodeObj subtracts 512 only if the
 * encoded x is >= viewW; 576-wide Android views must park negative or
 * >=512 coordinates rather than letting them alias another position. */
static inline bool Port_Voxel_PieceVisible3D(int32_t x, int32_t y,
                                             int32_t width, int32_t viewW) {
    return y < 160 && y >= -PORT_VOXEL_DRAW_TOP_MARGIN &&
           x < viewW + PORT_VOXEL_DRAW_SIDE_MARGIN &&
           x + width > -PORT_VOXEL_DRAW_SIDE_MARGIN;
}
static inline bool Port_Voxel_PieceNeedsParking(int32_t x, int32_t y,
                                                int32_t viewW) {
    int32_t decodedX = x & 511;
    if (decodedX >= viewW)
        decodedX -= 512;
    return y < PORT_VOXEL_OAM_MIN_Y || decodedX != x;
}

/* Per-OAM-slot anchor recorded by port_draw.c while it builds OAM""", "voxel.h")
src = checked_replace(src,
    "    int16_t groundX, roomX, roomZ; /* stable physical anchor shared by all entity pieces */",
    """    int16_t groundX, roomX, roomZ; /* stable physical anchor shared by all entity pieces */
    int16_t trueX, trueY; /* full sprite-piece screen coordinates if parked */
    uint8_t parked; /* safe y=160 in OAM, decode from trueX/trueY in 3D */""", "voxel.h")
src = checked_replace(src,
    "void Port_Voxel_LatchOamTags(void);",
    """void Port_Voxel_LatchOamTags(void);
/* Previous presentation actually drew 3D, not merely a configured toggle.
 * Draw-only expansion never changes native scripts/AI visibility. */
bool Port_Voxel_IsDrawing(void);""", "voxel.h")
header.write_text(src, encoding="utf-8")

draw = port / "port_draw.c"
src = draw.read_text(encoding="utf-8")
src = checked_replace(src,
    "    u8* ip = oamBase + updated * 8;",
    """    u8* ip = oamBase + updated * 8;
    const bool voxelView = Port_Voxel_IsDrawing();""", "port_draw.c")
src = checked_replace(src,
    """        if (y + (s32)se[3] <= 0) {
            continue;
        }

        x -= (s32)se[0]; /* subtract x anchor */
        if (x >= Port_Widescreen_EffectiveViewWidth()) {
            continue;
        }
        if (x + (s32)se[2] <= 0) {
            continue;
        }""",
    """        x -= (s32)se[0]; /* subtract x anchor */
        const s32 viewW = Port_Widescreen_EffectiveViewWidth();
        bool parked = false;
        if (voxelView) {
            /* Keep the actual 3D-visible margin rather than GBA clipping.
             * Out-of-range OAM pieces park at y=160 (invisible to the 2D PPU)
             * and get their real x/y from the matching latched voxel tag. */
            if (!Port_Voxel_PieceVisible3D(x, y, (s32)se[2], viewW))
                continue;
            parked = Port_Voxel_PieceNeedsParking(x, y, viewW);
            /* Parking must not wrap a tall sprite onto the top of the 2D PPU. */
            if (parked && PORT_VOXEL_OAM_PARK_Y + (s32)se[3] > 256)
                continue;
        } else {
            /* Original 2D code path and OAM clipping: unchanged. */
            if (y + (s32)se[3] <= 0 || x >= viewW || x + (s32)se[2] <= 0)
                continue;
        }""", "port_draw.c")
src = checked_replace(src,
    "u32 oamWord = (u32)(y & 0xFF);            /* y position */",
    """u32 oamWord = (u32)((parked ? PORT_VOXEL_OAM_PARK_Y : y) & 0xFF); /* y */""", "port_draw.c")
src = checked_replace(src,
    "        gPortVoxelOamTagsBuild[updated & 0x7F] = sVoxelCtx;",
    """        gPortVoxelOamTagsBuild[updated & 0x7F] = sVoxelCtx;
        gPortVoxelOamTagsBuild[updated & 0x7F].trueX = (s16)x;
        gPortVoxelOamTagsBuild[updated & 0x7F].trueY = (s16)y;
        gPortVoxelOamTagsBuild[updated & 0x7F].parked = parked;""", "port_draw.c")
src = checked_replace(src,
    "/* ---- DrawEntity (port of ASM at 0x0800404C) ----",
    """/* Draw-only visibility. Keep CheckOnScreen exactly as originally used by
 * AI and scripts. No extra entities or OAM while not actually presenting 3D. */
static u32 CheckOnScreenForDraw(Entity* entity) {
    if (CheckOnScreen(entity))
        return 1;
    if (!Port_Voxel_IsDrawing())
        return 0;
    const s32 x = (s32)entity->x.HALF.HI - (s32)gRoomControls.scroll_x;
    const s32 y = (s32)entity->y.HALF.HI - (s32)gRoomControls.scroll_y +
                  (s32)entity->z.HALF.HI;
    const s32 viewW = Port_Widescreen_EffectiveViewWidth();
    return x >= -(PORT_VOXEL_DRAW_SIDE_MARGIN + 0x3F) &&
           x < viewW + PORT_VOXEL_DRAW_SIDE_MARGIN + 0x3F &&
           y >= -(PORT_VOXEL_DRAW_TOP_MARGIN + 0x3F) && y < 160 + 0x3F;
}

/* ---- DrawEntity (port of ASM at 0x0800404C) ----""", "port_draw.c")
src = checked_replace(src,
    "            if (!CheckOnScreen(entity)) {",
    "            if (!CheckOnScreenForDraw(entity)) {", "port_draw.c")
draw.write_text(src, encoding="utf-8")

voxel = port / "port_voxel.cpp"
src = voxel.read_text(encoding="utf-8")
src = checked_replace(src,
    """bool Port_Voxel_Present(SDL_GPUCommandBuffer*, SDL_GPUTexture*, int, int) {
    return false;
}""",
    """bool Port_Voxel_Present(SDL_GPUCommandBuffer*, SDL_GPUTexture*, int, int) {
    return false;
}
bool Port_Voxel_IsDrawing(void) {
    return false; /* software / non-GPU builds remain native 2D */
}""", "port_voxel.cpp")
src = checked_replace(src,
    "        const bool entity = tag.kind == PORT_VOXEL_OAM_ENTITY;",
    """        if (tag.parked) {
            // The OAM position is a 2D-safe placeholder. Recover the true
            // piece coordinate, preserving the existing Android entity-feet
            // anchors and physical-layer sprite-depth pipeline.
            o.x = tag.trueX;
            o.y = tag.trueY;
        }
        const bool entity = tag.kind == PORT_VOXEL_OAM_ENTITY;""", "port_voxel.cpp")
src = checked_replace(src,
    "bool Port_Voxel_Present(SDL_GPUCommandBuffer* cmd, SDL_GPUTexture* swap, int swapW, int swapH) {",
    """static bool Port_Voxel_PresentImpl(SDL_GPUCommandBuffer* cmd, SDL_GPUTexture* swap, int swapW, int swapH) {""", "port_voxel.cpp")
src = checked_replace(src,
    "void Port_Voxel_Shutdown(void) {\n    if (!sDev)",
    """/* The next game update may only spend OAM slots on off-screen entities
 * if the previous frame actually displayed 3D. Reset on every 2D fallback. */
static bool sDrewVoxelLastFrame = false;
bool Port_Voxel_Present(SDL_GPUCommandBuffer* cmd, SDL_GPUTexture* swap, int swapW, int swapH) {
    sDrewVoxelLastFrame = Port_Voxel_PresentImpl(cmd, swap, swapW, swapH);
    return sDrewVoxelLastFrame;
}
bool Port_Voxel_IsDrawing(void) {
    return sDrewVoxelLastFrame && Port_Config_GetVoxelView();
}

void Port_Voxel_Shutdown(void) {
    sDrewVoxelLastFrame = false;
    if (!sDev)""", "port_voxel.cpp")
voxel.write_text(src, encoding="utf-8")
print("Backported upstream PR #219 3D-only OAM margins with Android-wide coordinate round-trip and native 2D invariants")
