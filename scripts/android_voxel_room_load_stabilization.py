#!/usr/bin/env python3
"""Never show the first 3D mesh while native room graphics are loading.

A new room can have a valid bottom BG and map identity before its top BG,
character/tile VRAM, and palette have finished streaming. During that gap
BuildMap can convert uninitialized/native-placeholder art into massive exposed
wooden roof beams or black wall slabs. Render the native transitional frame
until the room's complete BG material is stable; then commit ONE 3D mesh.
Later tile changes and movement retain the original three-frame MeshGate.
No 2D rendering, collision, game logic or user level controls are modified.
"""
from pathlib import Path
path=Path(__file__).resolve().parents[1]/"upstream/tmc/port/port_voxel.cpp"
s=path.read_text(encoding="utf-8")
def patch(a,b):
    global s
    n=s.count(a)
    if n!=1:
        raise SystemExit(f"initial-room stabilization expected one anchor ({n}): {a[:110]!r}")
    s=s.replace(a,b,1)

patch("""voxel::MeshGate sMeshGate;
u16 sBottomMapSnapshot""",
"""voxel::MeshGate sMeshGate;
voxel::RoomBootstrap sRoomBootstrap;
u16 sBottomMapSnapshot""")
patch("""        sMeshGate = {};
        sMapVertCount = 0;""",
"""        sMeshGate = {};
        sRoomBootstrap = {};
        sMapVertCount = 0;""")

patch("""    const bool mapDirty = sMeshGate.observe(mapKey, roomMapStable);""",
"""    /*
     * Room-loading races: bottom/collision may already match the live BG
     * while top art and its VRAM tiles still belong to the previous room.
     * Previously the first three-frame mesh commit exposed wrong beams and
     * roofs before a second BuildMap corrected it moments later.
     *
     * Observe a graphics fingerprint only during initial room bootstrap.
     * Never add palette/animated VRAM to the normal MapKey: those are
     * deliberately live, cheap shader inputs and must not rebuild every tick.
     */
    const int liveTopBg = LayerBg(gMapTop.bgSettings);
    const bool topExpected = liveTopBg >= 0 && gMapTop.bgSettings != nullptr;
    const bool topBound = sTopBinding.bg >= 0 &&
        sTopBinding.agrees(liveTopBg, LayerCnt(gMapTop.bgSettings)) &&
        TopMapShown();
    Uint64 roomGraphics = mapKey;
    if (!sRoomBootstrap.ready && roomMapStable) {
        // All 64 KiB of native BG character/screen data, not just a handful
        // of sample bytes. Includes streaming tile art used by BuildMask.
        for (int i = 0; i < 0x10000; ++i)
            roomGraphics = (roomGraphics ^ gVram[i]) * 1099511628211ull;
        // BuildMask/Foliage/DarkTile classify using live RGB555 colours.
        // Do not capture a mesh midway through a fade to full palette.
        for (int i = 0; i < 256; ++i) {
            const u16 c = gBgPltt[i];
            roomGraphics = (roomGraphics ^ (c & 255u)) * 1099511628211ull;
            roomGraphics = (roomGraphics ^ (c >> 8)) * 1099511628211ull;
        }
    }
    const bool initialRoomReady = sRoomBootstrap.observe(
        roomMapStable, topExpected, topBound, roomGraphics);
    if (initialRoomReady && !sMeshGate.ready && sMeshGate.frames == 0)
        std::fprintf(stderr,
                     "[voxel] room graphics stable area=%d room=%d frames=%d top=%d/%d\\n",
                     gRoomControls.area, gRoomControls.room, sRoomBootstrap.frames,
                     topBound ? 1 : 0, topExpected ? 1 : 0);
    const bool mapDirty = sMeshGate.observe(mapKey, roomMapStable && initialRoomReady);""")
path.write_text(s,encoding="utf-8")
print("Initial 3D room commit now waits for stable BG bindings, VRAM and palette")
