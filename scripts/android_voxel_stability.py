#!/usr/bin/env python3
from pathlib import Path

voxel = Path("upstream/tmc/port/port_voxel.cpp")
src = voxel.read_text(encoding="utf-8")

# Stable physical separation for layers that intentionally overlap. The old
# 0.25-0.3 px offsets could collapse to the same depth value at oblique camera
# angles and flicker while walking.
anchor = """constexpr float kTopLayerLift = 16.0f; /* lifted overhead art floats one tile up */
"""
replacement = anchor + """constexpr float kSurfaceEpsilon = 1.25f; /* stacked room layers: avoid z-fighting */
constexpr float kDecalEpsilon = 0.85f;  /* shadows/flat decals above floors */
constexpr float kSpriteEpsilon = 1.10f; /* billboard feet above floor depth */
"""
if anchor not in src:
    raise SystemExit("voxel constants anchor not found")
src = src.replace(anchor, replacement, 1)

# Static room geometry uses strict LESS so exactly-coplanar fragments don't
# alternate winners. Sprites retain LEQUAL to preserve the intended GBA OAM
# ordering when sprite parts share a depth.
old_pipe = """    pci.depth_stencil_state.compare_op = SDL_GPU_COMPAREOP_LESS_OR_EQUAL;
    pci.target_info.color_target_descriptions = &ctd;
    pci.target_info.num_color_targets = 1;
    pci.target_info.has_depth_stencil_target = true;
"""
new_pipe = """    pci.depth_stencil_state.compare_op = SDL_GPU_COMPAREOP_LESS;
    pci.target_info.color_target_descriptions = &ctd;
    pci.target_info.num_color_targets = 1;
    pci.target_info.has_depth_stencil_target = true;
"""
if old_pipe not in src:
    raise SystemExit("voxel map depth pipeline anchor not found")
src = src.replace(old_pipe, new_pipe, 1)

old_sprite = """    sPipeline = SDL_CreateGPUGraphicsPipeline(sDev, &pci);
    pci.depth_stencil_state.enable_depth_write = false;
    sSpritePipeline = SDL_CreateGPUGraphicsPipeline(sDev, &pci);
"""
new_sprite = """    sPipeline = SDL_CreateGPUGraphicsPipeline(sDev, &pci);
    pci.depth_stencil_state.enable_depth_write = false;
    pci.depth_stencil_state.compare_op = SDL_GPU_COMPAREOP_LESS_OR_EQUAL;
    sSpritePipeline = SDL_CreateGPUGraphicsPipeline(sDev, &pci);
"""
if old_sprite not in src:
    raise SystemExit("voxel sprite pipeline anchor not found")
src = src.replace(old_sprite, new_sprite, 1)

# Increase all tiny coplanar offsets consistently.
repls = {
    "h + 0.3f, z0, z1, mask": "h + kSurfaceEpsilon, z0, z1, mask",
    "v[2] += 0.3f;": "v[2] += kSurfaceEpsilon;",
    "d + 0.25f, y * 16.0f": "d + kSurfaceEpsilon, y * 16.0f",
    "h + 0.3f, y * 16.0f": "h + kSurfaceEpsilon, y * 16.0f",
    "const float y = elev + 0.25f,": "const float y = elev + kDecalEpsilon,",
    "const float footZ = foot + scrollY, footY = elev + 0.5f;":
        "const float footZ = foot + scrollY, footY = elev + kSpriteEpsilon;",
}
for a, b in repls.items():
    if a not in src:
        raise SystemExit(f"voxel depth-separation pattern not found: {a}")
    src = src.replace(a, b)

# Give interiors a small edge safety skirt too. The original voxel renderer
# used no interior margin, so low/steep camera angles could see past a room's
# last wall tile into the black void. This extends existing edge material only
# in world geometry; it does not duplicate the final screen.
margin_old = """    constexpr int kMargin = 24;
    const int margin = outdoors ? kMargin : 0;
"""
margin_new = """    constexpr int kOutdoorMargin = 24;
    constexpr int kIndoorMargin = 6;
    const int margin = outdoors ? kOutdoorMargin : kIndoorMargin;
"""
if margin_old not in src:
    raise SystemExit("voxel room-edge margin block not found")
src = src.replace(margin_old, margin_new, 1)

# A far plane of 4000 throws away depth precision for rooms capped at 1024 px
# plus the 24-tile exterior margin. 2048 comfortably covers the scene and
# materially improves precision at every supported pitch.
old_persp = """        const Mat4 mvp = Mul(Perspective(kFovYDeg * 3.14159265f / 180.0f, (float)tw / (float)th, 32.0f, 4000.0f),
                             LookAt(eye, target3));
"""
new_persp = """        const Mat4 mvp = Mul(Perspective(kFovYDeg * 3.14159265f / 180.0f, (float)tw / (float)th, 32.0f, 2048.0f),
                             LookAt(eye, target3));
"""
if old_persp not in src:
    raise SystemExit("voxel perspective block not found")
src = src.replace(old_persp, new_persp, 1)

# Log which depth path the phone actually receives, useful for any remaining
# device-specific reports.
depth_anchor = """    sDepthFmt = SDL_GPUTextureSupportsFormat(sDev, SDL_GPU_TEXTUREFORMAT_D32_FLOAT, SDL_GPU_TEXTURETYPE_2D,
                                             SDL_GPU_TEXTUREUSAGE_DEPTH_STENCIL_TARGET)
                    ? SDL_GPU_TEXTUREFORMAT_D32_FLOAT
                    : SDL_GPU_TEXTUREFORMAT_D16_UNORM;
"""
depth_repl = depth_anchor + """    std::fprintf(stderr, "[voxel] depth=%s\\n",
                 sDepthFmt == SDL_GPU_TEXTUREFORMAT_D32_FLOAT ? "D32_FLOAT" : "D16_UNORM");
"""
if depth_anchor not in src:
    raise SystemExit("voxel depth-format selection block not found")
src = src.replace(depth_anchor, depth_repl, 1)

voxel.write_text(src, encoding="utf-8")

# Perspective floor/wall texture stabilization. The 3D shader decodes GBA
# texels manually with texelFetch, so ordinary sampler filtering cannot prevent
# temporal shimmer when an oblique screen pixel covers several source texels.
# Keep exact nearest decoding when magnified, but use a four-point footprint
# average only during minification.
frag = Path("upstream/tmc/port/shaders/voxel.frag")
sh = frag.read_text(encoding="utf-8")

helper_anchor = """uint bgTexel(uint entry, uint charBase, bool bpp8, uint px, uint py) {
    uint tile = entry & 0x3FFu;
    if ((entry & 0x400u) != 0u) px = 7u - px;
    if ((entry & 0x800u) != 0u) py = 7u - py;
    if (bpp8)
        return vram8(charBase + tile * 64u + py * 8u + px);
    uint b = vram8(charBase + tile * 32u + py * 4u + (px >> 1));
    uint ci = (px & 1u) != 0u ? (b >> 4) : (b & 15u);
    return ci == 0u ? 0u : (entry >> 12) * 16u + ci;
}

"""
if helper_anchor not in sh:
    raise SystemExit("voxel shader bgTexel anchor not found")

helper = helper_anchor + r'''vec4 roomSample(vec2 uv) {
    ivec2 p = ivec2(floor(uv));
    if (p.x < 0 || p.y < 0 || p.x >= 1024 || p.y >= 1024)
        return vec4(0.0);

    uint entry = texelFetch(uMaps, ivec2(p.x >> 3, (p.y >> 3) + int(vParams.y)), 0).r;

    uint mslot = (vParams.w >> 8) & 511u;
    if (mslot != 0u) {
        mslot -= 1u;
        ivec2 mp = ivec2(int(mslot % 16u) * 16 + (p.x & 15),
                         int(mslot / 16u) * 16 + (p.y & 15));
        if (texelFetch(uMask, mp, 0).r < 0.5)
            return vec4(0.0);
    }

    uint idx = bgTexel(entry, vParams.z, (vParams.w & 1u) != 0u,
                       uint(p.x) & 7u, uint(p.y) & 7u);
    if (idx == 0u && (vParams.w & 2u) != 0u)
        idx = (vParams.w >> 20) & 255u;
    if (idx == 0u)
        return vec4(0.0);

    return vec4(texelFetch(uPal, ivec2(int(idx), 0), 0).rgb, 1.0);
}

'''
sh = sh.replace(helper_anchor, helper, 1)

old_room = r'''    if (vParams.x == 0u) {
        if (p.x < 0 || p.y < 0 || p.x >= 1024 || p.y >= 1024)
            discard;
        uint entry = texelFetch(uMaps, ivec2(p.x >> 3, (p.y >> 3) + int(vParams.y)), 0).r;
        // w: bit0 8bpp, bit1 fill-transparent, bits 8-16 prop mask slot+1, bits 20-27 fill palette index
        uint mslot = (vParams.w >> 8) & 511u;
        if (mslot != 0u) {
            mslot -= 1u;
            ivec2 mp = ivec2(int(mslot % 16u) * 16 + (p.x & 15), int(mslot / 16u) * 16 + (p.y & 15));
            if (texelFetch(uMask, mp, 0).r < 0.5)
                discard;
        }
        idx = bgTexel(entry, vParams.z, (vParams.w & 1u) != 0u, uint(p.x) & 7u, uint(p.y) & 7u);
        if (idx == 0u && (vParams.w & 2u) != 0u)
            idx = (vParams.w >> 20) & 255u;
    } else if (vParams.x == 1u) {
'''
new_room = r'''    if (vParams.x == 0u) {
        vec2 dx = dFdx(vUv);
        vec2 dy = dFdy(vUv);
        float footprint = max(length(dx), length(dy));

        vec4 c;
        if (footprint <= 1.05) {
            c = roomSample(vUv);
        } else {
            // Four samples over the projected source footprint. This is only
            // active for minified/tilted room surfaces and removes the rapid
            // nearest-neighbour texel switching seen as walking flicker.
            vec4 c0 = roomSample(vUv - dx * 0.25 - dy * 0.25);
            vec4 c1 = roomSample(vUv + dx * 0.25 - dy * 0.25);
            vec4 c2 = roomSample(vUv - dx * 0.25 + dy * 0.25);
            vec4 c3 = roomSample(vUv + dx * 0.25 + dy * 0.25);
            float coverage = c0.a + c1.a + c2.a + c3.a;
            if (coverage <= 0.0)
                discard;
            vec3 rgb = (c0.rgb * c0.a + c1.rgb * c1.a +
                        c2.rgb * c2.a + c3.rgb * c3.a) / coverage;
            c = vec4(rgb, 1.0);
        }
        if (c.a == 0.0)
            discard;
        oColor = vec4(c.rgb, 1.0);
        return;
    } else if (vParams.x == 1u) {
'''
if old_room not in sh:
    raise SystemExit("voxel shader room branch not found")
sh = sh.replace(old_room, new_room, 1)
frag.write_text(sh, encoding="utf-8")

print("Applied voxel depth stability and minification anti-flicker fixes")
