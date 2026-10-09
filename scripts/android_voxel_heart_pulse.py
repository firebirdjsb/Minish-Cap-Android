#!/usr/bin/env python3
"""Restore subtle slow pulse of the current life-heart in tilted 3D HUD.

The GBA heart bar is BG0 tile art, and its current-heart overlay is an OAM
sprite. The voxel GPU's independent HUD path composites BOTH; it must pulse
both instead of leaving the HUD flat. Restrict the effect to current heart's
8x8 icon and red pixels, sampled from the genuine BG0/OBJ palette (do not
change VRAM, native health counters, or the standard 2D renderer).

Uses the 60-Hz native room frame counter, rather than display FPS, for a
90-tick slow breathe. Leaves world geometry, 3D sprite depth, PR210 dither,
PR219 OAM visibility, menus, and all other HUD elements unchanged.
"""
from pathlib import Path
root=Path(__file__).resolve().parents[1]
vox=root/"upstream/tmc/port/port_voxel.cpp"
frag=root/"upstream/tmc/port/shaders/voxel.frag"

# Explicit header import: gHUD and HUD_HIDE_HEARTS live in include/ui.h.
def include_ui():
    src = vox.read_text(encoding="utf-8")
    old = '#include "room.h"'
    if src.count(old) != 1:
        raise SystemExit("Heart pulse expected one room.h include")
    vox.write_text(src.replace(old, old + '\n#include "ui.h"', 1), encoding="utf-8")

include_ui()

def patch(path, old, new):
    src=path.read_text(encoding="utf-8")
    n=src.count(old)
    if n!=1:
        raise SystemExit(f"Heart pulse: expected 1 anchor, saw {n}, in {path.name}: {old[:110]!r}")
    path.write_text(src.replace(old,new,1),encoding="utf-8")

# Mark genuine HUD OAM cards explicitly. World entities at room z=0 must
# not be mistaken for the heart overlay in the upper-left viewport.
patch(vox,
    '''        const float c[4][3] = { { x0, y0, 0 }, { x1, y0, 0 }, { x0, y1, 0 }, { x1, y1, 0 } };
        QuadUv(sVerts, kMaxVerts, n, c, o.uv, 1, o.tile, o.pal, o.rowParam);''',
    '''        const float c[4][3] = { { x0, y0, 0 }, { x1, y0, 0 }, { x0, y1, 0 }, { x1, y1, 0 } };
        QuadUv(sVerts, kMaxVerts, n, c, o.uv, 1, o.tile, o.pal,
               o.rowParam | 0x20000000u); /* screen-space HUD OAM */''')

patch(vox,
    '''    float actors[kFadeMaxActors][4];
};
static_assert(sizeof(PortVoxelFade) == (3 + kFadeMaxActors) * 16);''',
    '''    float actors[kFadeMaxActors][4];
    float heart[4]; /* screen X,Y, 60Hz slow pulse luminance, 1=HUD visible */
};
static_assert(sizeof(PortVoxelFade) == (4 + kFadeMaxActors) * 16);''')
patch(vox,
    '''        if (fade.cam[3] > 0.0f)
            GatherFadeActors(fade);
        SDL_PushGPUFragmentUniformData(cmd, 0, &fade, sizeof(fade));''',
    '''        if (fade.cam[3] > 0.0f)
            GatherFadeActors(fade);

        // The real last filled heart is an OBJ over BG0, so apply the same
        // subtle slow pulse to both. Its location follows HeartUIElement()
        // in src/ui.c; a second row begins after ten hearts.
        const int filledHearts = ((int)gHUD.health + 3) >> 2;
        if (filledHearts > 0 && !(gHUD.hideFlags & HUD_HIDE_HEARTS)) {
            fade.heart[0] = (float)(filledHearts * 8 + 3);
            fade.heart[1] = 12.0f;
            if (gHUD.health > 40) {
                fade.heart[0] -= 77.0f;
                fade.heart[1] = 20.0f;
            }
            // GBA game ticks (60Hz), not the screen swap interval: stable
            // heartbeat across native/widescreen 60/90/120Hz output.
            const float phase = (float)(gRoomTransition.frameCount % 90) *
                                (6.28318530718f / 90.0f);
            fade.heart[2] = 0.94f + 0.16f * (0.5f - 0.5f * std::cos(phase));
            fade.heart[3] = 1.0f;
        }
        SDL_PushGPUFragmentUniformData(cmd, 0, &fade, sizeof(fade));''')

patch(frag,
    '''    vec4 uFadeActors[VOXEL_FADE_ACTORS];
};''',
    '''    vec4 uFadeActors[VOXEL_FADE_ACTORS];
    vec4 uHudHeart; // X,Y, slow-pulse brightness, enabled
};''')
patch(frag,
    '''float roomFadeKeep() {''',
    '''/* Only the current heart's native red pixels, whether BG0 or HUD OBJ.
 * All outlines, unfilled hearts, text, world sprites and 2D remain untouched.
 * For HUD quads, vWorld.xy are SCREEN pixels; world quads have world Z.
 * To avoid accidental world sprite tinting, only apply to HUD geometry
 * in the final ortho pass (marked by uHudHeart.w and screen Y region). */
vec3 pulseCurrentHeart(vec3 c) {
    if (uHudHeart.w < 0.5) return c;
    if (vWorld.x < uHudHeart.x - 9.0 ||
        vWorld.x > uHudHeart.x + 9.0 ||
        vWorld.y < uHudHeart.y - 9.0 ||
        vWorld.y > uHudHeart.y + 9.0) return c;
    if (c.r < c.g * 1.35 || c.r < c.b * 1.25) return c;
    return clamp(c * uHudHeart.z, vec3(0.0), vec3(1.0));
}

float roomFadeKeep() {''')
patch(frag,
    '''        oColor = vec4(c.rgb, 1.0);
        return;''',
    '''        // BG0 source hearts use their authentic colours and only a tiny
        // brightness pulse on the last/current heart.
        oColor = vec4(vParams.y == 0u ? pulseCurrentHeart(c.rgb) : c.rgb, 1.0);
        return;''')
patch(frag,
    '''    oColor = vec4(texelFetch(uPal, ivec2(int(idx), 0), 0).rgb, 1.0);''',
    '''    vec3 rgb = texelFetch(uPal, ivec2(int(idx), 0), 0).rgb;
    // Heart UI OBJ cards are flat screen quads at z=0; other sprites stand
    // in 3D world space and must NEVER receive HUD pulse modulation.
    if (vParams.x == 1u && (vParams.w & 0x20000000u) != 0u)
        rgb = pulseCurrentHeart(rgb);
    oColor = vec4(rgb, 1.0);''')
print("Restored slow current-heart HUD pulse, game-tick paced; preserves 2D and other 3D effects")
