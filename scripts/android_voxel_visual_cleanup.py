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

# Cache which hardware BG owns the native bottom/top room maps. During camera
# scrolling or HDMA hand-off the MapLayer pointer can briefly point elsewhere
# even though the room did not change. Treating that transient pointer as truth
# makes the real room BG look "unbound", so it gets composited as a giant
# one-frame screen-space tree/wall overlay.
binding_helper = r'''
/* A MapLayer pointer may be reassigned for a transient HDMA/BG frame. Do not
 * reclassify an entire native room BG as an overlay on that one frame. A real
 * BG ownership change must be confirmed by successive matching room frames. */
int StableBottomLayerBg(void) {
    static int area = -1, room = -1, bg = -1;
    static int pending = -1, pendingFrames = 0;
    if (area != gRoomControls.area || room != gRoomControls.room) {
        area = gRoomControls.area;
        room = gRoomControls.room;
        bg = pending = -1;
        pendingFrames = 0;
    }
    const int live = LayerBg(gMapBottom.bgSettings);
    if (live >= 0 && BottomMapShown()) {
        if (bg < 0) {
            bg = live;
        } else if (live != bg) {
            if (pending != live) {
                pending = live;
                pendingFrames = 1;
            } else if (++pendingFrames >= 5) {
                std::fprintf(stderr,
                             "[voxel] bottom room BG ownership %d -> %d area=%d room=%d\n",
                             bg, live, area, room);
                bg = live;
                pending = -1;
                pendingFrames = 0;
            }
        } else {
            pending = -1;
            pendingFrames = 0;
        }
    } else {
        pending = -1;
        pendingFrames = 0;
    }
    return bg;
}

int StableTopLayerBg(void) {
    static int area = -1, room = -1, bg = -1;
    static int pending = -1, pendingFrames = 0;
    if (area != gRoomControls.area || room != gRoomControls.room) {
        area = gRoomControls.area;
        room = gRoomControls.room;
        bg = pending = -1;
        pendingFrames = 0;
    }
    const int live = LayerBg(gMapTop.bgSettings);
    if (live >= 0 && TopMapShown()) {
        if (bg < 0) {
            bg = live;
        } else if (live != bg) {
            if (pending != live) {
                pending = live;
                pendingFrames = 1;
            } else if (++pendingFrames >= 5) {
                std::fprintf(stderr,
                             "[voxel] top room BG ownership %d -> %d area=%d room=%d\n",
                             bg, live, area, room);
                bg = live;
                pending = -1;
                pendingFrames = 0;
            }
        } else {
            pending = -1;
            pendingFrames = 0;
        }
    } else {
        pending = -1;
        pendingFrames = 0;
    }
    return bg;
}
'''
stable_top_marker = "bool StableTopMapShown(void) {"
stable_top_pos = src.find(stable_top_marker)
if stable_top_pos < 0:
    raise SystemExit("StableTopMapShown marker not found")
stable_top_end = src.find("\n}\n", stable_top_pos)
if stable_top_end < 0:
    raise SystemExit("StableTopMapShown end not found")
stable_top_end += 3
src = src[:stable_top_end] + binding_helper + src[stable_top_end:]

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
"""        const int bottomBg = LayerBg(gMapBottom.bgSettings);
        const int kb = bottomBg < 0 ? 0 : key(bottomBg);
""",
"""        const int bottomBg = StableBottomLayerBg();
        const int topBg = StableTopLayerBg();
        const int kb = bottomBg < 0 ? 0 : key(bottomBg);
""", 1)

src = src.replace(
"""            const bool bound = gMapBottom.bgSettings == bgs[i] || (gMapTop.bgSettings == bgs[i] && TopMapShown());
""",
"""            /* Use the latched hardware BG ownership, not a one-frame
             * MapLayer pointer. This prevents native room trees/walls from
             * being drawn again as a full-screen foreground overlay. */
            /* Exclude both the stable owner and a newly verified live owner
             * during a BG transition; neither is a screen-space foreground. */
            const bool bound =
                i == bottomBg || i == topBg ||
                (i == LayerBg(gMapBottom.bgSettings) && BottomMapShown()) ||
                (i == LayerBg(gMapTop.bgSettings) && TopMapShown());
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
        /*
         * Do not punch holes into connected tree, cliff or log extrusions:
         * masks there make the 3D run see-through/lanky and delete treetops
         * at steep camera angles. Only isolated one-tile foliage may have
         * per-pixel cutouts. Native standalone props keep their own masks.
         */
        if (outdoors && !rn.ledge && yt == yb)
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

# Generated side faces need a material even when the tile art is mostly dark.
# Prefer the dominant lit colour, but fall back to the dominant visible colour
# instead of palette entry 0 / black.
fill_old = """        std::map<int, int> counts;
        int fill = 0, fillN = 0;
        for (int r = yt; r <= yb; ++r)
            for (int i = 0; i < 256; i += 4) {
                int ci = Cover(x, r) ? TopIndex(x, r, i & 15, i >> 4, tChar, t8 != 0) : -1;
                if (ci < 0)
                    ci = BottomIndex(x, r, i & 15, i >> 4, bChar, b8 != 0);
                if (ci >= 0 && !Dark555(gBgPltt[ci]) && ++counts[ci] > fillN)
                    fillN = counts[ci], fill = ci;
            }
        const Uint32 fillP = fillN ? (Uint32)fill + 1 : 0;
"""
fill_new = """        std::map<int, int> litCounts, allCounts;
        int fill = 0, fillN = 0, fallbackFill = 0, fallbackN = 0;
        for (int r = yt; r <= yb; ++r)
            for (int i = 0; i < 256; i += 4) {
                int ci = Cover(x, r) ? TopIndex(x, r, i & 15, i >> 4, tChar, t8 != 0) : -1;
                if (ci < 0)
                    ci = BottomIndex(x, r, i & 15, i >> 4, bChar, b8 != 0);
                if (ci < 0)
                    continue;
                if (++allCounts[ci] > fallbackN)
                    fallbackN = allCounts[ci], fallbackFill = ci;
                if (!Dark555(gBgPltt[ci]) && ++litCounts[ci] > fillN)
                    fillN = litCounts[ci], fill = ci;
            }
        if (!fillN && fallbackN)
            fill = fallbackFill, fillN = fallbackN;
        const Uint32 fillP = fillN ? (Uint32)fill + 1 : 0;
"""
if fill_old not in src:
    raise SystemExit("dominant side material block not found")
src = src.replace(fill_old, fill_new, 1)

# Side faces are geometry the original 2D art never supplies. Reusing a whole
# doorway/tree/wall tile sideways creates duplicated symbols and giant door
# panels. Use the run's derived dominant material as a clean side surface.
old_side_quad = """        Quad(sMapVerts, kMaxMapVerts, n, c, east ? u0 : u0 + 16, v0, east ? u0 + 16 : u0, v0 + 16, 0,
             top ? 128u : 0u, top ? tChar : bChar, (top ? t8 : b8) | 2u | (fill << 20) | (mask << 8));
"""
new_side_quad = """        /*
         * Generated side extrusion:
         * use an interior texel column rather than the tile's outer outline.
         * Stretching the outermost column was turning black sprite/tile outlines
         * into the long black slits visible beside trees, cliffs and room walls.
         * 'fill' is palette-index+1 (fillP); transparent samples fall back to
         * the run's dominant real material when one exists.
         */
        const float edgeU = east ? (u0 + 12.5f) : (u0 + 3.5f);
        const Uint32 sideParams =
            (top ? t8 : b8) |
            (fill ? (2u | ((fill - 1u) << 20)) : 0u);
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

print("Applied stable room BG ownership, top textures, native side faces and floor-bound overlays")
