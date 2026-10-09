"""Keep two-column indoor side-wall art on its owning wall and doorway."""

from pathlib import Path

path = Path(__file__).resolve().parents[1] / "upstream" / "tmc" / "port" / "port_voxel.cpp"
source = path.read_text(encoding="utf-8")


def replace(old: str, new: str) -> None:
    global source
    count = source.count(old)
    if count != 1:
        raise SystemExit(f"room-edge anchor count {count}: {old[:80]!r}")
    source = source.replace(old, new)


replace(
    "    auto sideFrameArt = [&](int x, int y) {",
    """    /* A passable opening in a two-column indoor side wall uses the same
     * vertical art orientation as its neighbouring solid jambs. Collision
     * remains owned by the native room; only the picture moves off the floor. */
    auto sideOpening = [&](int x, int y) {
        if (outdoors || y < 2 || y >= H - 2 || (x >= 2 && x < W - 2) ||
            gMapBottom.collisionData[y * 64 + x] != 0x23 || solid[y * 64 + x])
            return false;
        return solid[(y - 1) * 64 + x] && solid[(y + 1) * 64 + x];
    };
    auto sideFrameArt = [&](int x, int y) {""",
)
replace(
    "if (!Geom(x, y) && Cover(x, y) < 2 && SinkDepth(x, y) == 0.0f)",
    "if (!Geom(x, y) && !sideOpening(x, y) && Cover(x, y) < 2 && SinkDepth(x, y) == 0.0f)",
)
replace(
    "if (inRoom(nx, ny) && !Geom(nx, ny) && Cover(nx, ny) < 2 && SinkDepth(nx, ny) == 0.0f)",
    "if (inRoom(nx, ny) && !Geom(nx, ny) && !sideOpening(nx, ny) &&\n"
    "                Cover(nx, ny) < 2 && SinkDepth(nx, ny) == 0.0f)",
)
replace(
    "    auto sideDoor = [&](int x, int y, bool east) {",
    "    auto sideDoor = [&](int x, int y, bool east, bool top) {",
)
replace(
    "        QuadUv(sMapVerts, kMaxMapVerts, n, c, uv, 0, 128, tChar, t8);",
    "        QuadUv(sMapVerts, kMaxMapVerts, n, c, uv, 0, top ? 128u : 0u,\n"
    "               top ? tChar : bChar, top ? t8 : b8);",
)
replace(
    "            if (kind[t] == 1) {",
    """            if (sideOpening(x, y)) {
                underlay(x, y);
                sideDoor(x, y, x >= W - 2, false);
                if (Cover(x, y))
                    sideDoor(x, y, x >= W - 2, true);
                continue;
            }
            if (kind[t] == 1) {""",
)
replace(
    "sideDoor(x, y, eastDoor);",
    "sideDoor(x, y, eastDoor, true);",
)
replace(
    "                        sideV(x, yb - i, e != 0, z0, z1, h0, h1,",
    """                        /* A long indoor perimeter wall encodes its length in
                         * successive map rows. Reusing the run's last row
                         * prints the same window or jamb all along that side. */
                        sideV(x, !outdoors && b >= 2 && b < H - 2 &&
                                      ((x == 1 && e == 1) || (x == W - 2 && e == 0))
                                  ? b : yb - i,
                              e != 0, z0, z1, h0, h1,""",
)
replace(
    "sideDoor(x, y, x >= W - 2);",
    "sideDoor(x, y, x >= W - 2, true);",
)
replace(
    "    /* Visible art pixel (RGB555, -1 transparent). */",
    """    // Native two-row doorway art belongs on one vertical wall plane. The
    // north arch has a distinct centre tile type in both rows; the south
    // entrance has native 0x27 walk-through collision between solid jambs.
    // Classify by map topology so other rooms using these layouts follow suit.
    bool northDoorColumns[64] = {}, southDoorColumns[64] = {};
    bool southDoorCenters[64] = {};
    if (!outdoors && H >= 4) {
        for (int x = 3; x < W - 3; ++x) {
            bool arch = true;
            for (int y = 0; y < 2; ++y) {
                const int t = y * 64 + x;
                arch &= solid[t - 1] && solid[t] && solid[t + 1] &&
                        gMapBottom.mapData[t] != gMapBottom.mapData[t - 1] &&
                        gMapBottom.mapData[t] != gMapBottom.mapData[t + 1];
            }
            if (arch)
                northDoorColumns[x - 1] = northDoorColumns[x] = northDoorColumns[x + 1] = true;
        }
        for (int x = 2; x < W - 2; ++x) {
            bool entrance = true;
            for (int y = H - 2; y < H; ++y) {
                const int t = y * 64 + x;
                entrance &= gMapBottom.collisionData[t] == 0x27 &&
                            solid[t - 1] && solid[t + 1];
            }
            if (entrance) {
                southDoorColumns[x - 1] = southDoorColumns[x + 1] = true;
                southDoorCenters[x] = true;
            }
        }
    }

    /* Visible art pixel (RGB555, -1 transparent). */""",
)
replace(
    "        Uint32 rowMask[64] = {};",
    """        // The ordinary run would put one row on the facade and repeat the
        // other as a horizontal cap. Stand both doorway rows on the facade.
        const bool northFrame = northDoorColumns[x] && yt == 0 && yb == 1;
        const bool southFrame = southDoorColumns[x] && yt == H - 2 && yb == H - 1;
        if (northFrame || southFrame) {
            for (int y = yt; y <= yb; ++y)
                wallV(x, y, zFace, (yb - y) * 16.0f, 16.0f, 0);
            const int tile = yb * 64 + x;
            if (solid[tile] && gMapBottom.collisionData[tile] == 0x0f &&
                sFrontCount < 64 * 64)
                sFrontFaces[sFrontCount++] = {x * 16.0f, (x + 1) * 16.0f,
                                             zFace, 32.0f, tile,
                                             gMapBottom.mapData[tile]};
            continue;
        }

        Uint32 rowMask[64] = {};""",
)
replace(
    "    for (int y = 2; y < H - 2; ++y)\n        for (int x = 0; x < W; ++x)",
    """    // Keep the passage itself open: only its upper arch row faces outward.
    for (int x = 0; x < W; ++x)
        if (southDoorCenters[x])
            wallV(x, H - 2, H * 16.0f, 16.0f, 16.0f, 0);
    for (int y = 2; y < H - 2; ++y)
        for (int x = 0; x < W; ++x)""",
)

path.write_text(source, encoding="utf-8")
print("Applied shared indoor wall-row ownership and doorway planes")
