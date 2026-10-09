// ROM-free synthetic scenes exercise the actual prepared BuildMap function.
// Unused GPU functions are discarded by --gc-sections; no SDL device needed.
#include "../upstream/tmc/port/port_voxel.cpp"
#include <cassert>
#include <iostream>

extern "C" {
RoomControls gRoomControls;
MapLayer gMapBottom, gMapTop;
Area gArea;
Main gMain;
Screen gScreen;
PlayerEntity gPlayerEntity;
PlayerState gPlayerState;
u16 gMapDataBottomSpecial[0x4000], gMapDataTopSpecial[0x4000];
u16 gBgPltt[256], gObjPltt[256], gOamMem[512];
u8 gVram[0x18000], gIoMem[0x400];
bool voxelEnabled = true;
bool Port_Config_GetVoxelView(void) { return voxelEnabled; }
}

static void resetScene(bool outdoors, int w = 8, int h = 8) {
    std::memset(&gMapBottom, 0, sizeof(gMapBottom));
    std::memset(&gMapTop, 0, sizeof(gMapTop));
    std::memset(gMapDataTopSpecial, 0, sizeof(gMapDataTopSpecial));
    std::memset(gIoMem, 0, sizeof(gIoMem));
    gRoomControls = {};
    gRoomControls.width = w * 16;
    gRoomControls.height = h * 16;
    gArea.areaMetadata = outdoors ? AR_IS_OVERWORLD : 0;
    gMapBottom.bgSettings = &gScreen.bg1;
    gMapTop.bgSettings = reinterpret_cast<BgSettings*>(&gScreen.bg2);
    sBottomBinding = {};
    sBottomBinding.bg = 1;
    sTopBinding = {};
    sTopBinding.bg = 2;
    sTopBinding.control = 4;
    sShapesLoaded = true;
    sShapes.clear();
    gBgPltt[1] = 5 | (24 << 5) | (4 << 10);
    gBgPltt[2] = 20 | (12 << 5) | (5 << 10);
    std::memset(gVram, 0, sizeof(gVram));
    std::memset(gVram + 32, 0x11, 32); // solid green floor tile
    std::memset(gVram + 64, 0x22, 32); // brown facade tile
    std::memset(gVram + 0x4000 + 64, 0x22, 32);
    std::fill(std::begin(gMapDataBottomSpecial), std::end(gMapDataBottomSpecial), 1);
}

static void tile(u16* map, int x, int y, u16 art) {
    const int t = y * 256 + x * 2;
    map[t] = map[t + 1] = map[t + 128] = map[t + 129] = art;
}
static void block(int x, int y) {
    gMapBottom.collisionData[y * 64 + x] = 0x0f;
    tile(gMapDataBottomSpecial, x, y, 2);
}

static void outdoorRuns() {
    resetScene(true);
    for (int x = 2; x <= 4; ++x) {
        block(x, 2);
        block(x, 3);
        tile(gMapDataTopSpecial, x, 2, 2);
    }
    BuildMap();
    assert(sMapVertCount > 0 && sFrontCount == 3);
    bool texturedSide = false, closedNorth = false;
    for (int i = 0; i < sMapVertCount; i += 6) {
        const auto& a = sMapVerts[i];
        const auto& b = sMapVerts[i + 2];
        const auto& c = sMapVerts[i + 1];
        if (a.pos[1] == c.pos[1])
            continue;
        if (a.pos[0] == b.pos[0] && a.pos[0] == c.pos[0]) {
            // Connected foliage/cliffs must never carry a prop mask.
            assert(((a.p[3] >> 8) & 511u) == 0);
            if (a.p[1] == 0) {
                assert(std::abs(a.uv[0] - b.uv[0]) == 16.0f);
                // Side facade owns row 3, not the green canopy's row 2.
                assert(((a.p[2] >> 22) & 63u) == 3);
                assert(a.p[3] & 2u); // opaque transparent-texel fallback
                texturedSide = true;
            }
        }
        if (a.pos[2] == 48 && b.pos[2] == 48 && c.pos[2] == 48)
            closedNorth = true;
    }
    assert(texturedSide && closedNorth);
    // Skirt tiles extend the view without cloning any raised scenery.
    for (int i = 0; i < sMapVertCount; ++i)
        if (sMapVerts[i].pos[0] < 0 || sMapVerts[i].pos[0] > 128 ||
            sMapVerts[i].pos[2] < 0 || sMapVerts[i].pos[2] > 128)
            assert(sMapVerts[i].pos[1] == 0);
}

static void indoorDoorsAndScraps() {
    resetScene(false);
    // Side opening with native wall support and top frame art.
    block(0, 1);
    block(0, 3);
    block(1, 1);
    block(1, 3);
    tile(gMapDataTopSpecial, 0, 2, 2);
    tile(gMapDataTopSpecial, 1, 2, 2);
    // An isolated 4-pixel overlay must not become a raised glyph.
    gVram[0x4000 + 96] = 0x22;
    gVram[0x4000 + 97] = 0x22;
    gMapDataTopSpecial[5 * 256 + 5 * 2] = 3;
    BuildMap();
    int westDoorBands[2] = {};
    for (int i = 0; i < sMapVertCount; i += 6) {
        const auto& a = sMapVerts[i];
        const auto& b = sMapVerts[i + 2];
        const auto& c = sMapVerts[i + 1];
        if (a.p[0] != 0 || a.p[1] != 128)
            continue;
        const int tx = (a.p[2] >> 16) & 63, ty = (a.p[2] >> 22) & 63;
        assert(!(tx == 5 && ty == 5));
        if (tx < 2 && ty == 2) {
            assert(a.pos[0] == b.pos[0] && a.pos[0] == c.pos[0]);
            assert(a.pos[1] != c.pos[1]);
            float low = sMapVerts[i].pos[1], high = low;
            for (int j = 1; j < 6; ++j) {
                low = std::min(low, sMapVerts[i + j].pos[1]);
                high = std::max(high, sMapVerts[i + j].pos[1]);
            }
            assert(low == tx * 16.0f && high == low + 16.0f);
            ++westDoorBands[tx];
        }
    }
    assert(westDoorBands[0] == 1 && westDoorBands[1] == 1);
    for (int i = 0; i < sFrontCount; ++i)
        assert(sFrontFaces[i].tile != 2 * 64); // doorway never blocks movement

    resetScene(false);
    block(6, 1);
    block(6, 3);
    block(7, 1);
    block(7, 3);
    tile(gMapDataTopSpecial, 6, 2, 2);
    tile(gMapDataTopSpecial, 7, 2, 2);
    BuildMap();
    int eastDoorBands[2] = {};
    for (int i = 0; i < sMapVertCount; i += 6) {
        const auto& a = sMapVerts[i];
        const auto& b = sMapVerts[i + 2];
        const auto& c = sMapVerts[i + 1];
        const int tx = (a.p[2] >> 16) & 63, ty = (a.p[2] >> 22) & 63;
        if (a.p[1] == 128 && tx >= 6 && ty == 2) {
            assert(a.pos[0] == 96 && a.pos[0] == b.pos[0] && a.pos[0] == c.pos[0]);
            assert(a.pos[1] != c.pos[1]);
            float low = sMapVerts[i].pos[1], high = low;
            for (int j = 1; j < 6; ++j) {
                low = std::min(low, sMapVerts[i + j].pos[1]);
                high = std::max(high, sMapVerts[i + j].pos[1]);
            }
            assert(low == (7 - tx) * 16.0f && high == low + 16.0f);
            ++eastDoorBands[tx - 6];
        }
    }
    assert(eastDoorBands[0] == 1 && eastDoorBands[1] == 1);
}

static void longIndoorSideWall() {
    resetScene(false, 8, 10);
    for (int y = 0; y < 10; ++y)
        if (y != 5) {
            block(0, y);
            block(1, y);
            block(6, y);
            block(7, y);
        }
    // Native side-door collision (0x23) appears in both two-column openings.
    for (int x : {0, 1, 6, 7}) {
        gMapBottom.collisionData[5 * 64 + x] = 0x23;
        tile(gMapDataBottomSpecial, x, 5, 2);
    }
    BuildMap();

    int doorwayBands[4] = {};
    bool rowTwoSide[2] = {};
    for (int i = 0; i < sMapVertCount; i += 6) {
        const auto& a = sMapVerts[i];
        const auto& b = sMapVerts[i + 2];
        const auto& c = sMapVerts[i + 1];
        if (a.p[0] != 0 || a.p[1] != 0)
            continue;
        const int tx = (a.p[2] >> 16) & 63, ty = (a.p[2] >> 22) & 63;
        if (ty == 5 && (tx < 2 || tx >= 6)) {
            const float plane = tx < 2 ? 32.0f : 96.0f;
            assert(a.pos[0] == plane && b.pos[0] == plane && c.pos[0] == plane);
            ++doorwayBands[tx < 2 ? tx : tx - 4];
        }
        if (ty == 2 && (tx == 1 || tx == 6)) {
            const float plane = tx == 1 ? 32.0f : 96.0f;
            if (a.pos[0] == plane && b.pos[0] == plane && c.pos[0] == plane &&
                a.pos[2] >= 32 && b.pos[2] <= 48)
                rowTwoSide[tx == 1 ? 0 : 1] = true;
        }
    }
    for (int count : doorwayBands) assert(count == 1);
    assert(rowTwoSide[0] && rowTwoSide[1]); // long walls sample their current row
}

static void twoRowDoorframes() {
    resetScene(false, 8, 10);
    for (int x = 2; x <= 4; ++x)
        for (int y = 0; y <= 1; ++y)
            block(x, y);
    gMapBottom.mapData[3] = 0x3da;
    gMapBottom.mapData[64 + 3] = 0x91;
    BuildMap();
    int north[3][2] = {};
    for (int i = 0; i < sMapVertCount; i += 6) {
        const auto& a = sMapVerts[i];
        const auto& b = sMapVerts[i + 1];
        const auto& c = sMapVerts[i + 2];
        const int tx = (a.p[2] >> 16) & 63, ty = (a.p[2] >> 22) & 63;
        if (a.p[0] == 0 && a.p[1] == 0 && tx >= 2 && tx <= 4 && ty <= 1 &&
            a.pos[2] == 32 && b.pos[2] == 32 && c.pos[2] == 32) {
            assert(a.pos[1] == (2 - ty) * 16.0f && b.pos[1] == (1 - ty) * 16.0f);
            ++north[tx - 2][ty];
        }
    }
    for (const auto& col : north)
        for (int count : col) assert(count == 1);

    resetScene(false, 8, 10);
    for (int x : {2, 4})
        for (int y : {8, 9}) block(x, y);
    gMapBottom.collisionData[8 * 64 + 3] = 0x27;
    gMapBottom.collisionData[9 * 64 + 3] = 0x27;
    BuildMap();
    int south[3][2] = {};
    for (int i = 0; i < sMapVertCount; i += 6) {
        const auto& a = sMapVerts[i];
        const auto& b = sMapVerts[i + 1];
        const auto& c = sMapVerts[i + 2];
        const int tx = (a.p[2] >> 16) & 63, ty = (a.p[2] >> 22) & 63;
        if (a.p[0] == 0 && a.p[1] == 0 && tx >= 2 && tx <= 4 && ty >= 8 && ty <= 9 &&
            a.pos[2] == 160 && b.pos[2] == 160 && c.pos[2] == 160) {
            assert(a.pos[1] == (10 - ty) * 16.0f && b.pos[1] == (9 - ty) * 16.0f);
            ++south[tx - 2][ty - 8];
        }
    }
    assert(south[0][0] == 1 && south[0][1] == 1);
    assert(south[1][0] == 1 && south[1][1] == 0); // centre passage stays open
    assert(south[2][0] == 1 && south[2][1] == 1);
}

static void ledgeAndCapacity() {
    resetScene(true);
    block(2, 2);
    block(2, 3);
    block(3, 3); // neighbouring low ledge, 8 pixels high
    BuildMap();
    bool exposedBand = false;
    for (int i = 0; i < sMapVertCount; i += 6) {
        const auto& a = sMapVerts[i];
        const auto& b = sMapVerts[i + 2];
        const auto& c = sMapVerts[i + 1];
        if (a.pos[0] == 48 && b.pos[0] == 48 && c.pos[0] == 48 &&
            a.pos[1] > c.pos[1] && a.pos[2] >= 48 && b.pos[2] <= 64) {
            assert(c.pos[1] >= 8); // no full-height internal duplicate wall
            exposedBand = true;
        }
    }
    assert(exposedBand);
    resetScene(true, 64, 64);
    for (int y = 0; y < 64; ++y)
        for (int x = 0; x < 64; ++x)
            if ((x + y) & 1) block(x, y);
    BuildMap();
    assert(sMapVertCount > 0 && sMapVertCount < kMaxMapVerts - 6);
}

static void transitionsAndBindings() {
    voxel::LayerBinding b;
    b.observe(1, 4, true);
    b.observe(1, 4, true);
    assert(b.bg == -1);
    b.observe(1, 4, true);
    assert(b.bg == 1);
    b.observe(2, 8, true);
    b.observe(1, 0xc004, true); // screen block change, same material
    assert(b.bg == 1 && b.control == 4);
    for (int i = 0; i < 5; ++i) b.observe(2, 8, true);
    assert(b.bg == 2 && b.control == 8);

    voxel::MeshGate g;
    assert(!g.observe(1, true));
    assert(!g.observe(1, false));
    assert(!g.observe(1, true));
    assert(!g.observe(2, true));
    assert(!g.observe(2, true));
    assert(g.observe(2, true));
    assert(!g.observe(3, true) && g.accepted == 2);
    assert(!g.observe(3, false));
    assert(!g.observe(3, true));
    assert(!g.observe(3, true));
    assert(g.observe(3, true));

    resetScene(false);
    sSceneRoom = CurrentRoomId();
    sMapVertCount = 6;
    sVoxelHeightValid = true;
    sFrontCount = 1;
    gRoomControls.room++;
    ObserveRoomScene();
    assert(sMapVertCount == 0 && !sVoxelHeightValid && sFrontCount == 0);
    assert(!sMeshGate.ready);
}

static void movementAndOcclusion() {
    const voxel::FrontFace f{16, 32, 48, 16, 0, 0};
    float contact = 0;
    assert(voxel::crossFront(f, 24, 52, 25, 50, contact) && contact == 51);
    assert(!voxel::crossFront(f, 24, 50, 24, 48, contact)); // overlap never teleports out
    assert(!voxel::crossFront(f, 24, 50, 24, 54, contact)); // leaving remains free
    assert(!voxel::crossFront(f, 40, 52, 40, 50, contact)); // only local face span
    assert(!voxel::crossFront(f, 24, 100, 24, 40, contact)); // teleport
    const float pitch = 60.0f * 3.14159265f / 180.0f;
    assert(voxel::frontDepthHeight(f, 24, 54, pitch) == 16);
    assert(voxel::frontDepthHeight(f, 24, 47, pitch) == 0); // behind remains occluded
    assert(voxel::frontDepthHeight(f, 40, 54, pitch) == 0);
    assert(voxel::frontDepthHeight(f, 24, 90, pitch) == 0);

    // Exercise the public game hook, including mode/layer and stale-face
    // guards. Native BG screen blocks confirm this synthetic room normally.
    resetScene(false);
    block(1, 2);
    block(1, 1);
    BuildMap();
    sSceneRoom = CurrentRoomId();
    gMain.task = TASK_GAME;
    gMain.state = GAMETASK_MAIN;
    gMain.substate = GAMEMAIN_UPDATE;
    gIoMem[1] = 1 << 1;
    gIoMem[11] = 16; // screen block 16, away from our character art
    auto* screen = reinterpret_cast<u16*>(gVram + 0x8000);
    std::fill(screen, screen + 1024, 1);
    gPlayerEntity = {};
    gPlayerEntity.base.collisionLayer = 1;
    gPlayerState = {};
    const int32_t oldX = 24 * 65536, oldZ = 52 * 65536;
    int32_t nx = 25 * 65536, nz = 50 * 65536;
    assert(Port_Voxel_AssistPlayerMovement(oldX, oldZ, &nx, &nz) && nz == 51 * 65536);
    assert(nx == 25 * 65536); // lateral native movement is preserved
    voxelEnabled = false;
    nz = 50 * 65536;
    assert(!Port_Voxel_AssistPlayerMovement(oldX, oldZ, &nx, &nz) && nz == 50 * 65536);
    voxelEnabled = true;
    gPlayerEntity.base.collisionLayer = 2;
    assert(!Port_Voxel_AssistPlayerMovement(oldX, oldZ, &nx, &nz));
    gPlayerEntity.base.collisionLayer = 1;
    gPlayerState.jump_status = 1;
    assert(!Port_Voxel_AssistPlayerMovement(oldX, oldZ, &nx, &nz));
    gPlayerState.jump_status = 0;
    gMapBottom.collisionData[2 * 64 + 1] = 0;
    assert(!Port_Voxel_AssistPlayerMovement(oldX, oldZ, &nx, &nz));
}

static void aspects() {
    for (float aspect : {1.5f, 16.0f/9, 21.0f/9, 32.0f/9, 3120.0f/1440}) {
        for (auto size : {std::pair{3120, 1440}, std::pair{960, 540}, std::pair{800, 600}}) {
            const auto v = voxel::fitViewport(size.first, size.second, aspect);
            assert(v.w > 0 && v.h > 0);
            assert(v.x >= 0 && v.y >= 0);
            assert(v.x + v.w <= size.first + 0.01f && v.y + v.h <= size.second + 0.01f);
            assert(std::abs(v.w / v.h - aspect) < 0.00001f);
            assert(std::isfinite(Perspective(0.785f, v.w / v.h, 24, 3072).m[0]));
        }
    }
}

int main() {
    outdoorRuns();
    indoorDoorsAndScraps();
    longIndoorSideWall();
    twoRowDoorframes();
    ledgeAndCapacity();
    transitionsAndBindings();
    movementAndOcclusion();
    aspects();
    std::cout << "voxel scene regression tour passed (BuildMap, room transitions, movement, occlusion, aspects)\n";
}
