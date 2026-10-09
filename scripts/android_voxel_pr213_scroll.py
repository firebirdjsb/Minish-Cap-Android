#!/usr/bin/env python3
"""Selective Android backport of 999sian/tmc PR #213.

The game's scroll registers and the GPU background scroll can differ by one
8px tile during movement. Searching the 3x3 camera-offset neighbourhood
recognizes the correct live room map, avoiding false 2D fallback and room-BG
ownership errors. This is checked BEFORE Android's room latch (rather than
replacing safety checks with a blind multi-frame drawing grace period).
Preserves all native 2D, ROM, collision and gameplay behaviour.
"""
from pathlib import Path

file=Path(__file__).resolve().parents[1]/"upstream/tmc/port/port_voxel.cpp"
src=file.read_text(encoding="utf-8")
begin=src.index("    const int rx0 = gRoomControls.scroll_x - gRoomControls.origin_x;",src.index("int MapShownPct("))
end_marker="    return total ? match * 100 / total : 0;"
end=src.index(end_marker,begin)+len(end_marker)
region=src[begin:end]
assert region.count("for (int sy = 4; sy < 160; sy += 8)") == 1
assert region.count("for (int sx = 4; sx < 240; sx += 8)") == 1
new = """    /* PR #213: 3x3 camera-neighbourhood comparison compensates for one
     * GBA tile of BG latch delay. Do not draw in a genuinely different
     * room: a wrong map still fails the 50% ownership threshold. */
    int bestMatch = 0;
    for (int dy = -8; dy <= 8; dy += 8)
        for (int dx = -8; dx <= 8; dx += 8) {
            const int rx0 = gRoomControls.scroll_x - gRoomControls.origin_x + dx;
            const int ry0 = gRoomControls.scroll_y - gRoomControls.origin_y + dy;
            int match = 0, total = 0;
            for (int sy = 4; sy < 160; sy += 8)
                for (int sx = 4; sx < 240; sx += 8) {
                    const int rx = rx0 + sx, ry = ry0 + sy;
                    if (rx < 0 || ry < 0 || rx >= 1024 || ry >= 1024)
                        continue;
                    const int tx = ((sx + hofs) >> 3) & (size & 1 ? 63 : 31);
                    const int ty = ((sy + vofs) >> 3) & (size & 2 ? 63 : 31);
                    const int block = (tx >> 5) + (ty >> 5) * (size & 1 ? 2 : 1);
                    const u16 e = sb[(block * 1024 + (ty & 31) * 32 +
                                      (tx & 31)) & 0x3fff];
                    match += e == map[(ry >> 3) * 128 + (rx >> 3)];
                    ++total;
                }
            if (total)
                bestMatch = std::max(bestMatch, match * 100 / total);
        }
    return bestMatch;"""
src=src[:begin]+new+src[end:]
file.write_text(src,encoding="utf-8")
print("PR #213: nine-position native BG ownership prevents 3D/2D flicker while scrolling")
