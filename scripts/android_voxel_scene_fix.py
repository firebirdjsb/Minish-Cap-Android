#!/usr/bin/env python3
"""Final, checked scene transform after the existing Android voxel patches.

Only the pinned upstream is supported. Each replacement must match exactly
once; preparation fails instead of silently applying half of this pass.
"""
from pathlib import Path

root = Path(__file__).resolve().parents[1]
port = root / "upstream/tmc/port"
sources = {}


def replace(path, old, new):
    src = sources.setdefault(path, path.read_text(encoding="utf-8"))
    if src.count(old) != 1:
        raise SystemExit(f"{path.name}: expected one scene-fix anchor: {old[:90]!r}")
    sources[path] = src.replace(old, new, 1)


def region(path, start, end, new):
    src = sources.setdefault(path, path.read_text(encoding="utf-8"))
    if src.count(start) != 1 or src.count(end) != 1:
        raise SystemExit(f"{path.name}: ambiguous scene-fix region {start!r}")
    a, b = src.index(start), src.index(end, src.index(start))
    sources[path] = src[:a] + new + src[b:]


vox = port / "port_voxel.cpp"
replace(vox, '#include "port_voxel.h"', '#include "port_voxel.h"\n#include "port_voxel_scene.h"')
replace(vox, "constexpr float kDistance = 250.0f;", "constexpr float kDistance = 290.0f;")
replace(vox, "constexpr int kGroundMargin = 18;", "constexpr int kGroundMargin = 40;")
replace(vox, "(64 * 64 * 8 + 112 * 112 * 2) * 6", "(64 * 64 * 12 + 144 * 144 * 2) * 6")
replace(vox, "constexpr float kTopLayerLift = 16.0f;", "constexpr float kSurfaceEpsilon = 0.65f;\nconstexpr float kTopLayerLift = 16.0f;")

# One observation per presentation. Geometry, texture decoding and foreground
# composition all read the SAME confirmed layer controls, not live pointers.
region(vox, "bool StableTopMapShown(void) {", "/* Room gameplay with the bottom map", r'''voxel::RoomId CurrentRoomId() {
    return {gRoomControls.area, gRoomControls.room, gRoomControls.origin_x,
            gRoomControls.origin_y, gRoomControls.width, gRoomControls.height};
}
voxel::RoomId sSceneRoom;
voxel::LayerBinding sBottomBinding, sTopBinding;
voxel::MeshGate sMeshGate;
u16 sBottomMapSnapshot[0x4000], sTopMapSnapshot[0x4000];

bool StableTopMapShown(void) { return sTopBinding.bg >= 0; }
int StableBottomLayerBg(void) { return sBottomBinding.bg; }
int StableTopLayerBg(void) { return sTopBinding.bg; }
u16 StableBottomCnt(void) { return sBottomBinding.control; }
u16 StableTopCnt(void) { return sTopBinding.control; }

''')
replace(vox, "static bool sVoxelHeightValid = false;", r'''static bool sVoxelHeightValid = false;
voxel::FrontFace sFrontFaces[64 * 64];
int sFrontCount = 0;

void ObserveRoomScene(void) {
    const auto id = CurrentRoomId();
    if (sSceneRoom != id || gMain.task != TASK_GAME || gMain.state != GAMETASK_MAIN) {
        sSceneRoom = id;
        sBottomBinding = {};
        sTopBinding = {};
        sMeshGate = {};
        sMapVertCount = 0;
        sMapKey = 0;
        sVoxelHeightValid = false;
        sFrontCount = 0;
    }
    sBottomBinding.observe(LayerBg(gMapBottom.bgSettings), LayerCnt(gMapBottom.bgSettings), BottomMapShown());
    sTopBinding.observe(LayerBg(gMapTop.bgSettings), LayerCnt(gMapTop.bgSettings), TopMapShown());
}

bool FrontFaceCurrent(const voxel::FrontFace& f) {
    // SetTile can remove/move a barrier between the renderer and game ticks.
    // Never keep enforcing a cached face after its native tile changed.
    return gMapBottom.collisionData[f.tile] == 0x0f &&
           gMapBottom.mapData[f.tile] == f.mapTile;
}

float PlayerContactDepth(float x, float z, float pitch) {
    float height = 0.0f;
    for (int i = 0; i < sFrontCount; ++i)
        if (FrontFaceCurrent(sFrontFaces[i]))
            height = std::max(height, voxel::frontDepthHeight(sFrontFaces[i], x, z, pitch));
    return height;
}
''')

replace(vox, "    const u16 cb = LayerCnt(gMapBottom.bgSettings), ct = LayerCnt(gMapTop.bgSettings);\n    const bool topStable", "    const u16 cb = StableBottomCnt(), ct = StableTopCnt();\n    const bool topStable")
replace(vox, "    mix(gMapBottom.mapData, sizeof(gMapBottom.mapData)); /* tile types drive overrides */", "    mix(gMapBottom.mapData, sizeof(gMapBottom.mapData)); /* tile types drive overrides */\n    mix(gMapBottom.actTiles, sizeof(gMapBottom.actTiles));")
replace(vox, "    const u16 cb = LayerCnt(gMapBottom.bgSettings);\n    const Uint32 bChar", "    const u16 cb = StableBottomCnt();\n    const Uint32 bChar")
replace(vox, "    const u16 ct = LayerCnt(gMapTop.bgSettings);\n    /* Top map", "    const u16 ct = StableTopCnt();\n    /* Top map")
replace(vox, "    sVoxelHeightValid = false;\n    sBuildShapes = CurrentShapes();", "    sVoxelHeightValid = false;\n    sFrontCount = 0;\n    sBuildShapes = CurrentShapes();")

# Exact occupancy, not a sparse sampling count mislabelled as pixels.
replace(vox, "                for (int i = 0; i < 256; i += 3)\n                    op += TopIndex", "                for (int i = 0; i < 256; ++i)\n                    op += TopIndex")
replace(vox, "cover[t] = op >= 70 ? 2 : op > 0 ? 1 : 0;", "cover[t] = op >= 210 ? 2 : op > 0 ? 1 : 0;")
replace(vox, "    /* Visible art pixel (RGB555, -1 transparent). */", r'''    auto sideFrameArt = [&](int x, int y) {
        if (outdoors || y < 2 || y >= H - 2 || (x >= 2 && x < W - 2) || !Cover(x, y))
            return false;
        // A side-boundary opening, or its immediately adjacent jamb. Solid
        // frame tiles also need this treatment, not only walkable overhang.
        return !solid[y * 64 + x] ||
               !solid[(y - 1) * 64 + x] || !solid[(y + 1) * 64 + x];
    };

    /* Visible art pixel (RGB555, -1 transparent). */''')
replace(vox, "        if (Cover(x, y))\n            flatL(true, x, x, y, h + 0.3f", "        if (Cover(x, y) && !sideFrameArt(x, y))\n            flatL(true, x, x, y, h + kSurfaceEpsilon")
replace(vox, "        if (Cover(x, y)) {\n            float c2[4][3];", "        if (Cover(x, y) && !sideFrameArt(x, y)) {\n            float c2[4][3];")
replace(vox, "if (outdoors && !rn.ledge && yt == yb)", "if (outdoors && !rn.ledge && yt == yb &&\n            !Geom(x - 1, yb) && !Geom(x + 1, yb))")

# Every map quad records its owning 16x16 tile in the unused high char-base
# bits. The fragment shader clamps UVs to it, including reverse side faces.
replace(vox, "    if (n + 6 > cap)\n        return;\n    static const int kIdx", r'''    if (n + 6 > cap)
        return;
    if (p0 == 0u) {
        float u = uv[0][0], v = uv[0][1];
        for (int i = 1; i < 4; ++i) {
            u = std::min(u, uv[i][0]);
            v = std::min(v, uv[i][1]);
        }
        const Uint32 tx = (Uint32)std::clamp((int)std::floor(u / 16.0f), 0, 63);
        const Uint32 ty = (Uint32)std::clamp((int)std::floor(v / 16.0f), 0, 63);
        p2 |= (tx | (ty << 6)) << 16;
    }
    static const int kIdx''')

# Side walls show the facade tile that owns that HEIGHT band, rather than a
# stretched green/black canopy column. Compose partial top art over bottom
# and fill transparency without propagating any prop masks to solid faces.
region(vox, "    /* Box side on plane x = xs", "    /* Vertical lip of a sunk tile", r'''    auto sideV = [&](int x, int y, bool east, float z0, float z1,
                     float h0, float h1, float band0, float bandH, Uint32 fill) {
        const float xs = (x + (east ? 1 : 0)) * 16.0f;
        const float c[4][3] = {{xs, h1, z0}, {xs, h1, z1}, {xs, h0, z0}, {xs, h0, z1}};
        const float u0 = x * 16.0f, u1 = u0 + 16.0f;
        const float v0 = y * 16.0f + (band0 + bandH - h1) * 16.0f / bandH;
        const float v1 = y * 16.0f + (band0 + bandH - h0) * 16.0f / bandH;
        Quad(sMapVerts, kMaxMapVerts, n, c, east ? u0 : u1, v0,
             east ? u1 : u0, v1, 0, 0, bChar, baseParams(0, fill));
        if (Cover(x, y) && !sideFrameArt(x, y)) {
            float overlay[4][3];
            std::memcpy(overlay, c, sizeof(c));
            for (auto& v : overlay)
                v[0] += east ? kSurfaceEpsilon : -kSurfaceEpsilon;
            Quad(sMapVerts, kMaxMapVerts, n, overlay, east ? u0 : u1, v0,
                 east ? u1 : u0, v1, 0, 128, tChar, t8);
        }
    };
    /* Side doorway art has its native X axis running up the wall and its Y
     * axis along the boundary. It must not become a horizontal floating cap. */
    auto sideDoor = [&](int x, int y, bool east) {
        const float xs = (east ? W - 2 : 2) * 16.0f;
        const float z0 = y * 16.0f, z1 = z0 + 16.0f;
        const float c[4][3] = {{xs, 16, z0}, {xs, 16, z1}, {xs, 0, z0}, {xs, 0, z1}};
        const float u0 = x * 16.0f, u1 = u0 + 16.0f;
        const float uv[4][2] = {{east ? u0 : u1, z0}, {east ? u0 : u1, z1},
                              {east ? u1 : u0, z0}, {east ? u1 : u0, z1}};
        QuadUv(sMapVerts, kMaxMapVerts, n, c, uv, 0, 128, tChar, t8);
    };
''')

region(vox, "                if (Cover(x, y)) {\n                    if (outdoors && coverPixels[t] < 24)", "\n            }\n        }\n    for (const Run& rn : runs)", r'''                if (Cover(x, y)) {
                    const bool supported = Cover(x - 1, y) || Cover(x + 1, y) ||
                                           Cover(x, y - 1) || Cover(x, y + 1) ||
                                           Geom(x - 1, y) || Geom(x + 1, y) ||
                                           Geom(x, y - 1) || Geom(x, y + 1);
                    const bool orphan = coverPixels[t] <= 24 && !supported;
                    const bool westDoor = sideFrameArt(x, y) && x < 2;
                    const bool eastDoor = sideFrameArt(x, y) && x >= W - 2;
                    if (orphan) {
                        // Isolated glyph/shadow scraps have no raised owner.
                    } else if (westDoor || eastDoor) {
                        sideDoor(x, y, eastDoor);
                    } else if (!outdoors || coverPixels[t] <= 24) {
                        // Interior details keep native floor placement. Real
                        // furniture/wall tops already belong to solid runs.
                        flatL(true, x, x, y, d + kSurfaceEpsilon,
                              y * 16.0f, y * 16.0f + 16, 0);
                    } else {
                        int clear = 0;
                        for (int i = 0; i < 256; i += 3)
                            clear += BottomPixel(x, y, i & 15, i >> 4, bChar, b8 != 0) < 0;
                        if (clear >= 4)
                            flatL(true, x, x, y, d + kSurfaceEpsilon, y * 16.0f, y * 16.0f + 16, 0);
                        else
                            flatL(true, x, x, y, kTopLayerLift,
                                  y * 16.0f + kTopLayerLift, y * 16.0f + 16 + kTopLayerLift, 0);
                    }
                }''')

region(vox, "        /* Sides wherever the neighbour column", "\n    }\n    if (topBelow)", r'''        /* Register only real, fully blocked native front tiles. Absorbed
         * overhang, door openings, manual block overrides and low ledges
         * never acquire movement collision from visual classification. */
        const int frontTile = yb * 64 + x;
        if (topH >= 16.0f && solid[frontTile] &&
            gMapBottom.collisionData[frontTile] == 0x0f && sFrontCount < 64 * 64) {
            sFrontFaces[sFrontCount++] = {x * 16.0f, (x + 1) * 16.0f, zFace, topH,
                                         frontTile, gMapBottom.mapData[frontTile]};
        }
        // Each side height band uses its own southern facade art. Draw only
        // the exposed height above the neighbour, and close the north end.
        for (int b = thin ? yb : rn.foot; b <= yb; ++b) {
            const float z0 = thin ? zFace - 8.0f : b * 16.0f;
            const float z1 = thin ? zFace : b * 16.0f + 16.0f;
            for (int e = 0; e < 2; ++e) {
                const float neighbour = hAt(x + (e ? 1 : -1), b);
                for (int i = 0; i < face; ++i) {
                    const float h0 = std::max(neighbour, i * rn.faceH);
                    const float h1 = (i + 1) * rn.faceH;
                    if (h0 < h1)
                        sideV(x, yb - i, e != 0, z0, z1, h0, h1,
                              i * rn.faceH, rn.faceH, fillP);
                }
            }
        }
        const int northCell = thin ? yb : rn.foot;
        const float northZ = thin ? zFace - 8.0f : northCell * 16.0f;
        const float northHeight = hAt(x, northCell - 1);
        for (int i = 0; i < face; ++i) {
            const float h0 = std::max(northHeight, i * rn.faceH);
            const float h1 = (i + 1) * rn.faceH;
            if (h0 < h1)
                wallV(x, yb - i, northZ, h0, h1 - h0, 0, fillP);
        }''')
replace(vox, "    if (topBelow) {\n        constexpr float kBelow", r'''    for (int y = 2; y < H - 2; ++y)
        for (int x = 0; x < W; ++x)
            if (kind[y * 64 + x] != 0 && sideFrameArt(x, y))
                sideDoor(x, y, x >= W - 2);
    if (topBelow) {
        constexpr float kBelow''')

replace(vox, "    if (!Port_Config_GetVoxelView() || !SceneApplicable())\n        return false;", "    ObserveRoomScene(); // invalidate even while the new room is still inapplicable\n    if (!Port_Config_GetVoxelView() || !SceneApplicable())\n        return false;")
replace(vox, "    static int camArea = -1, camRoom = -1;", "    static voxel::RoomId cameraRoom;")
replace(vox, "        camArea != gRoomControls.area || camRoom != gRoomControls.room;", "        cameraRoom != CurrentRoomId();")
replace(vox, "        camArea = gRoomControls.area;\n        camRoom = gRoomControls.room;", "        cameraRoom = CurrentRoomId();")
replace(vox, "gMapBottom.bgSettings != nullptr && gRoomControls.width != 0 &&\n        gRoomControls.width <= 1024 && gRoomControls.height <= 1024", "gMapBottom.bgSettings != nullptr && gRoomControls.width >= 16 &&\n        gRoomControls.width <= 1024 && gRoomControls.height >= 16 && gRoomControls.height <= 1024 &&\n        gRoomControls.width % 16 == 0 && gRoomControls.height % 16 == 0")
replace(vox, "    const bool roomMapStable = BottomMapShown();", "    const bool roomMapStable = gMain.substate == GAMEMAIN_UPDATE &&\n        !(gRoomControls.scroll_flags & 1) && BottomMapShown() &&\n        sBottomBinding.agrees(LayerBg(gMapBottom.bgSettings), LayerCnt(gMapBottom.bgSettings)) &&\n        (sTopBinding.bg < 0 || sTopBinding.agrees(LayerBg(gMapTop.bgSettings), LayerCnt(gMapTop.bgSettings)));")
replace(vox, "    static int sSettleFrames = 0;\n", "")
region(vox, "    /*\n     * Never rebuild room geometry", "\n    const float pitch =", r'''    const bool mapDirty = sMeshGate.observe(mapKey, roomMapStable);
    if (mapDirty) {
        BuildMap();
        sMapKey = mapKey;
        std::memcpy(sBottomMapSnapshot, gMapDataBottomSpecial, sizeof(sBottomMapSnapshot));
        std::memcpy(sTopMapSnapshot, gMapDataTopSpecial, sizeof(sTopMapSnapshot));
    }
    if (!sMeshGate.ready)
        return false;
''')
replace(vox, "std::memcpy(dst + kVramBytes, gMapDataBottomSpecial, kMapBytes);", "std::memcpy(dst + kVramBytes, sBottomMapSnapshot, kMapBytes);")
replace(vox, "std::memcpy(dst + kVramBytes + kMapBytes, gMapDataTopSpecial, kMapBytes);", "std::memcpy(dst + kVramBytes + kMapBytes, sTopMapSnapshot, kMapBytes);")

replace(vox, "        const float x0 = o.x + scrollX, x1 = x0 + o.w;", r'''        const bool entity = tag.kind == PORT_VOXEL_OAM_ENTITY;
        const float objectScrollX = entity ? tag.roomX - tag.groundX : rawScrollX;
        const float objectScrollY = entity ? tag.roomZ - tag.groundY : rawScrollY;
        const float x0 = o.x + objectScrollX, x1 = x0 + o.w;''')
replace(vox, "        const float entityFootZ = (float)entityFoot + scrollY;\n        const float entityCenterX = (x0 + x1) * 0.5f;", "        const float entityFootZ = entity ? (float)tag.roomZ : entityFoot + objectScrollY;\n        const float entityCenterX = entity ? (float)tag.roomX : (x0 + x1) * 0.5f;")
replace(vox, "const float y = elev + 0.25f, z0 = sy0 + scrollY, z1 = sy1 + scrollY;", "const float y = elev + kSurfaceEpsilon, z0 = sy0 + objectScrollY, z1 = sy1 + objectScrollY;")
replace(vox, "            const int packedY = std::clamp((int)std::lround(elev + 0.5f), -128, 127) + 128;", r'''            const float depthHeight = (tag.layer & 0x80u) && nativeCollisionLayer != 2
                                          ? std::max(elev, PlayerContactDepth(entityCenterX, entityFootZ, pitch))
                                          : elev;
            const int packedY = std::clamp((int)std::lround(depthHeight), -128, 127) + 128;''')

# Viewport is selected from the user's current aspect mode for all passes;
# projection, backdrop and HUD must use the same effective scene rectangle.
replace(vox, "        /* Backdrop: BG3 stretched over the whole target at the far plane. */\n        SDL_GPUViewport vp = { 0, 0, (float)tw, (float)th, 0, 1 };", r'''        float aspect = (float)tw / th;
        switch (Port_Config_AspectMode()) {
            case PORT_ASPECT_NATIVE_3_2: aspect = 3.0f / 2.0f; break;
            case PORT_ASPECT_WIDESCREEN_16_9: aspect = 16.0f / 9.0f; break;
            case PORT_ASPECT_ULTRAWIDE_21_9: aspect = 21.0f / 9.0f; break;
            case PORT_ASPECT_SUPER_ULTRAWIDE_32_9: aspect = 32.0f / 9.0f; break;
            default: break;
        }
        const auto scene = voxel::fitViewport(tw, th, aspect);
        SDL_GPUViewport vp = {scene.x, scene.y, scene.w, scene.h, 0, 1};
        SDL_Rect scissor = {(int)scene.x, (int)scene.y, (int)scene.w, (int)scene.h};
        SDL_SetGPUScissor(rp, &scissor);''')
replace(vox, "(float)tw / (float)th, 32.0f, 4000.0f", "scene.w / scene.h, 24.0f, 3072.0f")
replace(vox, "            float hw = (float)tw, hh = hw * 160.0f / (float)viewW;\n            if (hh > th) {\n                hh = (float)th;", "            float hw = scene.w, hh = hw * 160.0f / (float)viewW;\n            if (hh > scene.h) {\n                hh = scene.h;")
replace(vox, "SDL_GPUViewport hvp = { (tw - hw) * 0.5f, (th - hh) * 0.5f, hw, hh, 0, 1 };", "SDL_GPUViewport hvp = { scene.x + (scene.w - hw) * 0.5f, scene.y + (scene.h - hh) * 0.5f, hw, hh, 0, 1 };")

# Public C entry point, disabled without GPU or when any native movement
# authority says this isn't an ordinary grounded player walking step.
replace(vox, "#ifndef TMC_GPU_RENDERER\n", "#ifndef TMC_GPU_RENDERER\n\nbool Port_Voxel_AssistPlayerMovement(int32_t, int32_t, int32_t*, int32_t*) { return false; }\n")
replace(vox, "int Port_Voxel_CurrentArea(void) {\n    return SceneApplicable()", r'''bool Port_Voxel_AssistPlayerMovement(int32_t oldX, int32_t oldY, int32_t* newX, int32_t* newY) {
    if (!Port_Config_GetVoxelView() || !sVoxelHeightValid || sSceneRoom != CurrentRoomId() ||
        !SceneApplicable() || gPlayerEntity.base.collisionLayer != 1 ||
        gPlayerEntity.base.z.WORD != 0 || gPlayerState.jump_status ||
        (gPlayerState.flags & PL_MINISH) || (gRoomControls.scroll_flags & 1))
        return false;
    const float ox = oldX / 65536.0f - gRoomControls.origin_x;
    const float oz = oldY / 65536.0f - gRoomControls.origin_y;
    const float nx = *newX / 65536.0f - gRoomControls.origin_x;
    const float nz = *newY / 65536.0f - gRoomControls.origin_y;
    float contact = nz;
    bool blocked = false;
    for (int i = 0; i < sFrontCount; ++i) {
        float hit;
        if (FrontFaceCurrent(sFrontFaces[i]) && voxel::crossFront(sFrontFaces[i], ox, oz, nx, nz, hit)) {
            contact = std::max(contact, hit);
            blocked = true;
        }
    }
    if (blocked)
        *newY = (int32_t)std::lround((contact + gRoomControls.origin_y) * 65536.0f);
    return blocked;
}

int Port_Voxel_CurrentArea(void) {
    return SceneApplicable()''')

header = port / "port_voxel.h"
replace(header, "    int16_t groundY; /* screen Y of the entity's feet (sprite y minus z) */", "    int16_t groundY; /* physical feet in OAM screen coordinates */\n    int16_t groundX, roomX, roomZ; /* stable physical anchor shared by all entity pieces */")
replace(header, "void Port_Voxel_LatchOamTags(void);", "void Port_Voxel_LatchOamTags(void);\nbool Port_Voxel_AssistPlayerMovement(int32_t oldX, int32_t oldY, int32_t* newX, int32_t* newY);")
draw = port / "port_draw.c"
replace(draw, "    sVoxelCtx.groundY = voxelPlayer\n                            ? (s16)(y - entity->z.HALF.HI - entity->spriteOffsetY)\n                            : (s16)(y - entity->z.HALF.HI);", r'''    sVoxelCtx.groundY = (s16)(y - entity->z.HALF.HI - entity->spriteOffsetY);
    sVoxelCtx.groundX = (s16)(x - (s8)entity->spriteOffsetX);
    sVoxelCtx.roomX = (s16)(entity->x.HALF.HI - gRoomControls.origin_x);
    sVoxelCtx.roomZ = (s16)(entity->y.HALF.HI - gRoomControls.origin_y);''')
movement = root / "upstream/tmc/src/movement.c"
replace(movement, 'extern int Port_Debug_NoclipEnabled(void);', 'extern int Port_Debug_NoclipEnabled(void);\n#include "port_voxel.h"')
replace(movement, "    return gDirectionalMovementFunctions[direction](this, radius, direction << 3, collisionType);", r'''#ifdef PC_PORT
    const s32 oldX = this->x.WORD, oldY = this->y.WORD;
#endif
    const bool32 moved = gDirectionalMovementFunctions[direction](this, radius, direction << 3, collisionType);
#ifdef PC_PORT
    /* Native movement runs first. Only a small remaining crossing of a real
     * rendered front face can be shortened; sideways sliding is preserved. */
    if (this == &gPlayerEntity.base && collisionType == 0 && !Port_Debug_NoclipEnabled()) {
        s32 newX = this->x.WORD, newY = this->y.WORD;
        if (Port_Voxel_AssistPlayerMovement(oldX, oldY, &newX, &newY)) {
            this->y.WORD = newY;
            return this->x.WORD != oldX || this->y.WORD != oldY;
        }
    }
#endif
    return moved;''')

frag = port / "shaders/voxel.frag"
replace(frag, "        uint entry = texelFetch(uMaps", "        ivec2 owner = ivec2(int((vParams.z >> 16) & 63u), int((vParams.z >> 22) & 63u)) * 16;\n        p = clamp(p, owner, owner + ivec2(15));\n        uint entry = texelFetch(uMaps")
replace(frag, "idx = bgTexel(entry, vParams.z,", "idx = bgTexel(entry, vParams.z & 65535u,")
vert = port / "shaders/voxel.vert"
region(vert, "        if ((aParams.w & 0x40000000u) != 0u) {", "        vec4 anchor =", "        // CPU chooses depth height only for contact with a real front face.\n")

for path, src in sources.items():
    path.write_text(src, encoding="utf-8")
print("Applied closed side faces, confirmed room materials, doorway planes, front-face contact and aspect viewports")
