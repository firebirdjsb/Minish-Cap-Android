#!/usr/bin/env python3
from pathlib import Path

vox = Path("upstream/tmc/port/port_voxel.cpp")
src = vox.read_text(encoding="utf-8")

# Track top-layer occupancy so tiny overlay scraps aren't lifted into the 3D air.
old_cover_decl = """    static Uint8 cover[64 * 64]; /* overhead layer: 0 none, 1 partial, 2 opaque */
    static Uint8 solid[64 * 64], geom[64 * 64];
"""
new_cover_decl = """    static Uint8 cover[64 * 64]; /* overhead layer: 0 none, 1 partial, 2 opaque */
    static Uint16 coverPixels[64 * 64];
    static Uint8 solid[64 * 64], geom[64 * 64];
"""
if old_cover_decl not in src:
    raise SystemExit("cover declaration not found")
src = src.replace(old_cover_decl, new_cover_decl, 1)

old_cover_assign = """            cover[t] = op >= 70 ? 2 : op > 0 ? 1 : 0;
            solid[t] = SolidTile(x, y);
"""
new_cover_assign = """            coverPixels[t] = (Uint16)op;
            cover[t] = op >= 70 ? 2 : op > 0 ? 1 : 0;
            solid[t] = SolidTile(x, y);
"""
if old_cover_assign not in src:
    raise SystemExit("cover assignment not found")
src = src.replace(old_cover_assign, new_cover_assign, 1)

# A mask that follows actual visible pixels. Unlike BuildMask(), dark outline
# pixels remain present, so tree/log/cliff edges don't become see-through.
sil_anchor = """    auto silhouette = [&](int x, int y) -> Uint32 {
"""
sil_end_marker = """    /* The room's commonest walkable ground tile: underlay where no walkable
"""
idx = src.find(sil_anchor)
end = src.find(sil_end_marker, idx)
if idx < 0 or end < 0:
    raise SystemExit("silhouette lambda region not found")
visible_code = r'''    std::map<Uint64, Uint32> visibleMaskCache;
    auto visibleMask = [&](int x, int y) -> Uint32 {
        const u16* ts = &gMapDataTopSpecial[y * 2 * 128 + x * 2];
        const Uint64 key = ((Uint64)gMapBottom.mapData[y * 64 + x] << 48) | ((Uint64)ts[0] << 32) |
                           ((Uint64)ts[1] << 16) | ts[128] ^ ((Uint64)ts[129] << 8);
        const auto it = visibleMaskCache.find(key);
        if (it != visibleMaskCache.end())
            return it->second;
        if (sPropCount >= kMaxProps)
            return 0;

        const int slot = sPropCount;
        const int ox = (slot % 16) * 16, oy = (slot / 16) * 16;
        int visible = 0;
        for (int py = 0; py < 16; ++py)
            for (int px = 0; px < 16; ++px) {
                const bool on = VisPixel(x, y, px, py) >= 0;
                sMaskPixels[(oy + py) * 256 + ox + px] = on ? 255 : 0;
                visible += on;
            }
        if (visible == 0 || visible >= 252) {
            visibleMaskCache[key] = 0;
            return 0;
        }
        ++sPropCount;
        const Uint32 m = (Uint32)sPropCount; /* shader mask slots are 1-based */
        visibleMaskCache[key] = m;
        return m;
    };

'''
src = src[:end] + visible_code + src[end:]

# Re-enable foliage cutouts using the true-alpha mask added above.
old_masks = """        Uint32 rowMask[64] = {};
        bool anyMask = false;
        /* Keep multi-tile scenery closed. Per-pixel cutout masks are reserved
         * for isolated props; on tree/log/cliff runs they create missing tops
         * and thin transparent strips at perspective angles. */
"""
new_masks = """        Uint32 rowMask[64] = {};
        bool anyMask = false;
        if (outdoors && !rn.ledge)
            for (int r = yt; r <= yb; ++r)
                if (Foliage(x, r))
                    anyMask |= (rowMask[r] = visibleMask(x, r)) != 0;
"""
if old_masks not in src:
    raise SystemExit("post-clean foliage mask block not found")
src = src.replace(old_masks, new_masks, 1)

# Tiny top-layer fragments are common decorative/shadow scraps. Raising them
# one tile turns them into floating black glyphs in perspective. Keep them
# composited just above their native floor instead.
old_cover_draw = """                if (Cover(x, y)) {
                    int clear = 0;
                    for (int i = 0; i < 256; i += 3)
                        clear += BottomPixel(x, y, i & 15, i >> 4, bChar, b8 != 0) < 0;
                    if (clear >= 4)
                        flatL(true, x, x, y, d + 0.25f, y * 16.0f, y * 16.0f + 16, 0);
                    else
                        flatL(true, x, x, y, kTopLayerLift, y * 16.0f + kTopLayerLift,
                              y * 16.0f + 16 + kTopLayerLift, 0);
                }
"""
new_cover_draw = """                if (Cover(x, y)) {
                    if (coverPixels[t] < 24) {
                        flatL(true, x, x, y, d + 0.25f, y * 16.0f, y * 16.0f + 16, 0);
                    } else {
                        int clear = 0;
                        for (int i = 0; i < 256; i += 3)
                            clear += BottomPixel(x, y, i & 15, i >> 4, bChar, b8 != 0) < 0;
                        if (clear >= 4)
                            flatL(true, x, x, y, d + 0.25f, y * 16.0f, y * 16.0f + 16, 0);
                        else
                            flatL(true, x, x, y, kTopLayerLift, y * 16.0f + kTopLayerLift,
                                  y * 16.0f + 16 + kTopLayerLift, 0);
                    }
                }
"""
if old_cover_draw not in src:
    raise SystemExit("floor top-layer draw block not found")
src = src.replace(old_cover_draw, new_cover_draw, 1)

# Side faces are geometry the original 2D art never supplies. Reusing a whole
# doorway/tree/wall tile sideways creates duplicated symbols and giant door
# panels. Use the run's derived dominant material as a clean side surface.
old_side_quad = """        Quad(sMapVerts, kMaxMapVerts, n, c, east ? u0 : u0 + 16, v0, east ? u0 + 16 : u0, v0 + 16, 0,
             top ? 128u : 0u, top ? tChar : bChar, (top ? t8 : b8) | 2u | (fill << 20) | (mask << 8));
"""
new_side_quad = """        (void)u0;
        (void)v0;
        (void)top;
        (void)mask;
        Quad(sMapVerts, kMaxMapVerts, n, c, 0, 0, 1, 1, 3, fill, 0, 0);
"""
if old_side_quad not in src:
    raise SystemExit("side face quad not found")
src = src.replace(old_side_quad, new_side_quad, 1)

vox.write_text(src, encoding="utf-8")

frag = Path("upstream/tmc/port/shaders/voxel.frag")
sh = frag.read_text(encoding="utf-8")
old_else = """    } else {
        vec4 c = texelFetch(uBg0, ivec2(p.x, p.y + int(vParams.y)), 0);
        if (c.a == 0.0)
            discard;
        oColor = vec4(c.rgb, 1.0);
        return;
    }
"""
new_else = """    } else if (vParams.x == 3u) {
        idx = vParams.y & 255u;
    } else {
        vec4 c = texelFetch(uBg0, ivec2(p.x, p.y + int(vParams.y)), 0);
        if (c.a == 0.0)
            discard;
        oColor = vec4(c.rgb, 1.0);
        return;
    }
"""
if old_else not in sh:
    raise SystemExit("voxel fragment kind tail not found")
sh = sh.replace(old_else, new_else, 1)
frag.write_text(sh, encoding="utf-8")

print("Applied clean 3D side materials, true foliage alpha and floor-bound tiny overlays")
