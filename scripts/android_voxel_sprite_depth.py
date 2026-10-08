#!/usr/bin/env python3
from pathlib import Path

vox = Path("upstream/tmc/port/port_voxel.cpp")
src = vox.read_text(encoding="utf-8")

old_call = """        QuadUv(sVerts, kMaxVerts, n, c, o.uv, 1, o.tile, o.pal, o.rowParam);
    }
    const int worldVerts = n;
"""
new_call = """        /*
         * Every OAM piece emitted for one entity must share ONE depth anchor:
         * the entity's native ground/feet row. Using each piece's own bottom
         * makes Link's hat/body/subsprites cross a wall at different moments
         * as animation frames change, producing slicing/clipping.
         */
        Uint32 tileParam = o.tile;
        Uint32 rowParam = o.rowParam;
        if (tag.kind == PORT_VOXEL_OAM_ENTITY) {
            /* Anchor depth to the exact physical feet position used for the
             * card above. In raised/tilted areas, using layer 0 here while the
             * card itself is at groundHeight makes Link slice through walls. */
            const int packedY = std::clamp((int)std::lround(elev + 0.5f), -128, 127) + 128;
            const int packedZ = std::clamp((int)std::lround(entityFootZ), -2048, 2047) + 2048;
            tileParam |= (Uint32)(packedY & 0xFF) << 16;
            rowParam |= 0x80000000u | ((Uint32)(packedZ & 0xFFF) << 16);
        }
        QuadUv(sVerts, kMaxVerts, n, c, o.uv, 1, tileParam, o.pal, rowParam);
    }
    const int worldVerts = n;
"""
if old_call not in src:
    raise SystemExit("world sprite QuadUv call not found")
src = src.replace(old_call, new_call, 1)
vox.write_text(src, encoding="utf-8")

vert = Path("upstream/tmc/port/shaders/voxel.vert")
sh = vert.read_text(encoding="utf-8")
old_main = """void main() {
    vUv = aUv;
    vParams = aParams;
    gl_Position = uMvp * vec4(aPos, 1.0);
}
"""
new_main = """void main() {
    vUv = aUv;
    vParams = aParams;

    vec4 clip = uMvp * vec4(aPos, 1.0);

    /*
     * Entity sprite marker/anchor packed by port_voxel.cpp:
     *   aParams.w bit31      = native-feet depth anchor
     *   aParams.w bits16-27 = one shared entity foot Z + 2048
     *   aParams.y bits16-23 = rendered feet height + 128
     *
     * Keep clip X/Y from the camera-facing tilted card, but use one depth for
     * the entire sprite based on its feet. This reproduces the GBA's foot-row
     * occlusion ordering in the 3D view and prevents upper-body wall clipping.
     */
    if (aParams.x == 1u && (aParams.w & 0x80000000u) != 0u) {
        int footZPacked = int((aParams.w >> 16) & 0xFFFu);
        int footYPacked = int((aParams.y >> 16) & 0xFFu);
        float footZ = float(footZPacked - 2048);
        float footY = float(footYPacked - 128) + 0.5;
        vec4 anchor = uMvp * vec4(aPos.x, footY, footZ, 1.0);
        float anchorNdcDepth = anchor.z / anchor.w;
        clip.z = anchorNdcDepth * clip.w;
    }

    gl_Position = clip;
}
"""
if old_main not in sh:
    raise SystemExit("voxel vertex shader main not found")
sh = sh.replace(old_main, new_main, 1)
vert.write_text(sh, encoding="utf-8")

print("Applied stable native-feet depth for all 3D entity sprite pieces")
