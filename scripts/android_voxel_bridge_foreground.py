#!/usr/bin/env python3
"""Foreground occlusion for actual overhead bridge quads.

The standard sprite pipeline deliberately anchors ALL of a character's
subsprites at its native FEET depth. This makes the player's torso win over
an overhead bridge unless its opacity is drawn after sprites. Move only
bridge-tagged map quads into a last foreground pass, while retaining the
original depth test against the rest of the room. No collision or gameplay
mutation, no additional mesh generation and no change to 2D.
"""
from pathlib import Path
path = Path(__file__).resolve().parents[1] / "upstream/tmc/port/port_voxel.cpp"
s = path.read_text(encoding="utf-8")

def patch(old, new):
    global s
    n=s.count(old)
    if n!=1:
        raise SystemExit(f"bridge foreground expected one match ({n}): {old[:115]!r}")
    s=s.replace(old,new,1)

patch(
    "int sMapVertCount = 0;",
    """int sMapVertCount = 0;
int sBridgeFirstVert = 0; /* map quad split: 3D background vs overhead foreground */
""")
patch(
    """    sMapVertCount = n;
    sBuildShapes = nullptr;""",
    """    /* All overhead BG bridge tiles are tagged 0x40000000 by the verified
     * 3D geometry classifier. Unlike an ordinary wall, a bridge must be
     * composited AFTER world sprites: feet-anchored Link/NPC artwork would
     * otherwise paint over the bridge even when standing underneath it.
     * Move whole quads, preserving UVs, vertex order, palette and depth. */
    std::vector<Vert> bridgeFaces;
    bridgeFaces.reserve(256 * 6);
    int sceneCount = 0;
    for (int vi = 0; vi < n; vi += 6) {
        const bool overhead = sMapVerts[vi].p[0] == 0u &&
                              (sMapVerts[vi].p[3] & 0x40000000u) != 0u;
        if (overhead)
            bridgeFaces.insert(bridgeFaces.end(), &sMapVerts[vi], &sMapVerts[vi + 6]);
        else {
            if (sceneCount != vi)
                std::memmove(&sMapVerts[sceneCount], &sMapVerts[vi], 6 * sizeof(Vert));
            sceneCount += 6;
        }
    }
    sBridgeFirstVert = sceneCount;
    if (!bridgeFaces.empty())
        std::memcpy(&sMapVerts[sceneCount], bridgeFaces.data(),
                    bridgeFaces.size() * sizeof(Vert));
    sMapVertCount = n;
    sBuildShapes = nullptr;""")
patch(
    """        if (sMapVertCount > 0)
            SDL_DrawGPUPrimitives(rp, (Uint32)sMapVertCount, 1, 0, 0);""",
    """        if (sBridgeFirstVert > 0)
            SDL_DrawGPUPrimitives(rp, (Uint32)sBridgeFirstVert, 1, 0, 0);""")
patch(
    """            SDL_BindGPUVertexBuffers(rp, 0, &vb, 1);
        }

        /* HUD pass in a centred GBA-aspect rect. */""",
    """            SDL_BindGPUVertexBuffers(rp, 0, &vb, 1);
        }
        /* True overhead scene geometry occludes Link and other world
         * sprites only where the geometry projects in front of them.
         * Render after the sprite pass (which depth tests but does not
         * write), with the SAME room MVP and normal scene depth compare. */
        if (sMapVertCount > sBridgeFirstVert) {
            SDL_PushGPUVertexUniformData(cmd, 0, mvp.m, sizeof(mvp.m));
            SDL_DrawGPUPrimitives(rp, (Uint32)(sMapVertCount - sBridgeFirstVert),
                                  1, (Uint32)sBridgeFirstVert, 0);
        }

        /* HUD pass in a centred GBA-aspect rect. */""")

path.write_text(s,encoding="utf-8")
print("Bridges now draw AFTER feet-anchored world sprites, with scene depth testing")
