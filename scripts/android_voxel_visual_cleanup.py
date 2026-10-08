#!/usr/bin/env python3
from pathlib import Path

vox = Path("upstream/tmc/port/port_voxel.cpp")
src = vox.read_text(encoding="utf-8")

top_fn = """bool TopMapShown(void) {
    return gMapTop.bgSettings != nullptr && MapShownPct(gMapTop, gMapDataTopSpecial) >= 50;
}
"""
top_helper = top_fn + """
bool StableTopMapShown(void) {
    static bool latched = false;
    static int lastArea = -1, lastRoom = -1;

    const bool roomChanged =
        lastArea != gRoomControls.area || lastRoom != gRoomControls.room;
    if (roomChanged) {
        latched = false;
        lastArea = gRoomControls.area;
        lastRoom = gRoomControls.room;
    }

    if (TopMapShown())
        latched = true;

    /* The top room map is static room geometry. Once observed for this room,
     * keep it in the 3D mesh until the room identity changes; temporary BG
     * repurposing must not make walls/trim disappear for a frame. */
    return latched;
}
"""
if top_fn not in src:
    raise SystemExit("TopMapShown function not found")
src = src.replace(top_fn, top_helper, 1)

# BuildMap and foreground compositing must use the same stable top-layer state.
src = src.replace(
"""    const bool topBelow = TopMapShown() && (ct & 3) > (cb & 3);
    const bool hasTop = TopMapShown() && !topBelow;
""",
"""    const bool topShownStable = StableTopMapShown();
    const bool topBelow = topShownStable && (ct & 3) > (cb & 3);
    const bool hasTop = topShownStable && !topBelow;
""", 1)

src = src.replace(
"""            const bool bound = gMapBottom.bgSettings == bgs[i] || (gMapTop.bgSettings == bgs[i] && TopMapShown());
""",
"""            const bool bound = gMapBottom.bgSettings == bgs[i] ||
                               (gMapTop.bgSettings == bgs[i] && StableTopMapShown());
""", 1)

# Re-introduce ONLY the stable top-state bit into the geometry key. This causes
# one rebuild when the real top map arrives, but no rebuild on one-frame misses.
map_key_anchor = """    mix(&cb, sizeof(cb));
    mix(&ct, sizeof(ct));
"""
map_key_repl = """    const bool topStable = StableTopMapShown();
    mix(&cb, sizeof(cb));
    mix(&ct, sizeof(ct));
    mix(&topStable, sizeof(topStable));
"""
if map_key_anchor not in src:
    raise SystemExit("stable MapKey insertion point not found")
src = src.replace(map_key_anchor, map_key_repl, 1)

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

# Indoor doorway trim often appears as absorbed top-layer overhang on a
# walkable tile between solid wall tiles. Keep that art visual instead of
# classifying the opening itself as a solid 3D wall run.
geom_old = """    auto Geom = [&](int x, int y) { return inRoom(x, y) && geom[y * 64 + x] != 0; };
"""
geom_new = """    auto Geom = [&](int x, int y) {
        if (!inRoom(x, y))
            return false;
        const int t = y * 64 + x;
        if (!geom[t])
            return false;
        if (!outdoors && geom[t] == 2 && !solid[t]) {
            const bool lr = inRoom(x - 1, y) && inRoom(x + 1, y) &&
                            solid[y * 64 + (x - 1)] && solid[y * 64 + (x + 1)];
            const bool ud = inRoom(x, y - 1) && inRoom(x, y + 1) &&
                            solid[(y - 1) * 64 + x] && solid[(y + 1) * 64 + x];
            if (lr || ud)
                return false;
        }
        return true;
    };
"""
if geom_old not in src:
    raise SystemExit("Geom lambda not found for doorway cleanup")
src = src.replace(geom_old, geom_new, 1)

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
                    if (outdoors && coverPixels[t] < 24) {
                        /* Outdoor tiny top-map scraps become floating black
                         * glyphs in perspective. Indoors, small overlays are
                         * often legitimate doorway/workshop/wall details. */
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
new_side_quad = """        /*
         * Native-looking side extrusion:
         * sample only the outermost texel column of the real room tile and
         * stretch that edge through the generated depth. This preserves the
         * wall/door/cliff/tree palette and trim without rotating an entire
         * doorway/tree tile onto the side or replacing it with a flat colour.
         */
        const float edgeU = east ? (u0 + 15.25f) : (u0 + 0.75f);
        const Uint32 sideParams =
            (top ? t8 : b8) | 2u | ((Uint32)fill << 20);
        Quad(sMapVerts, kMaxMapVerts, n, c,
             edgeU, v0, edgeU, v0 + 16.0f, 0,
             top ? 128u : 0u, top ? tChar : bChar, sideParams);
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
        uint material = vParams.y & 255u;
        oColor = vec4(texelFetch(uPal, ivec2(int(material), 0), 0).rgb, 1.0);
        return;
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

print("Applied stable room top textures, native edge-extruded sides and floor-bound overlays")
