#!/usr/bin/env python3
"""Selective backport of 999sian/tmc PR #210 to the Android voxel renderer.

Use the 510 curated per-area tile shapes as read-only *defaults*, merged below
existing voxel_shapes.json overrides. Preserve the user's one-tile wall rule
(there is no 'wall' field in the PR asset) and the 3D-only PR #219 OAM path.

Optionally dither ONLY occluding room geometry around Link/enemies. This is a
fragment-stage uniform so no world geometry, gameplay collision, HUD, OAM or
2D path is mutated. Shader binaries are rebuilt by prepare_android.sh.
"""
import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
port = root / "upstream/tmc/port"


def patch(path, old, new):
    src = path.read_text(encoding="utf-8")
    n = src.count(old)
    if n != 1:
        raise SystemExit(f"PR210 patch expected exactly one anchor in {path.name}, got {n}: {old[:90]!r}")
    path.write_text(src.replace(old, new, 1), encoding="utf-8")


# Embed classifications: Android's runtime CWD does not contain assets/; the
# default table must ship inside libmain.so. Read any local user file *after*
# these defaults, so user's previous shape edits win tile-by-tile.
shapes = json.loads((root / "assets/voxel_shapes_pr210.json").read_text(encoding="utf-8"))
entries = []
for area, data in shapes.items():
    assert set(data) == {"tiles"}, f"Unexpected wall/height setting in area {area}"
    for tile, kind in data["tiles"].items():
        assert kind in ("prop", "block"), (area, tile, kind)
        entries.append((int(area), int(tile), kind))
assert len(entries) == 510 and len(shapes) == 59
items = "\n".join(
    f"        {{{area}, {tile}, PORT_VOXEL_SHAPE_{kind.upper()}}},"
    for area, tile, kind in sorted(entries)
)
voxel = port / "port_voxel.cpp"
patch(voxel,
    'const char* kShapesPath = "voxel_shapes.json";',
    '''const char* kShapesPath = "voxel_shapes.json";

/* tmc PR #210: curated tile-shape overrides. A classification affects only
 * the 3D mesh, never engine collision. Do not infer extra height levels. */
void InstallPr210ShapeDefaults(void) {
    struct Shape { int area, tile, kind; };
    static constexpr Shape kDefaultShapes[] = {
''' + items + '''
    };
    for (const Shape& item : kDefaultShapes)
        sShapes[item.area].tiles[item.tile] = item.kind;
}
''')
patch(voxel,
    '''void LoadShapes(void) {
    sShapesLoaded = true;
    std::ifstream f(kShapesPath);''',
    '''void LoadShapes(void) {
    sShapesLoaded = true;
    sShapes.clear();
    InstallPr210ShapeDefaults();
    std::ifstream f(kShapesPath);''')
patch(voxel,
    '''        sShapes.clear();
    }
}

void SaveShapes(void)''',
    '''        sShapes.clear();
        InstallPr210ShapeDefaults(); /* malformed local edits cannot erase safe defaults */
    }
}

void SaveShapes(void)''')

# Persist wall thinning independently of the 3D toggle; default on, with a
# user switch in the phone menu (do not restore tile-height controls).
cfg = port / "port_runtime_config.cpp"
patch(cfg, "bool sVoxelView = false;",
    "bool sVoxelView = false;\nbool sVoxelWallFade = true; /* PR #210: 3D geometry dither near actors */")
patch(cfg, '    { "voxel_view", &sVoxelView, false },',
    '    { "voxel_view", &sVoxelView, false },\n    { "voxel_wall_fade", &sVoxelWallFade, true },')
patch(cfg,
    '''/* Camera elevation presets, low (dramatic) to near top-down. */''',
    '''extern "C" bool Port_Config_GetVoxelWallFade(void) {
    return sVoxelWallFade;
}
extern "C" void Port_Config_SetVoxelWallFade(bool on) {
    sVoxelWallFade = on;
    sConfigJson["voxel_wall_fade"] = on;
    SaveConfig();
}
/* Camera elevation presets, low (dramatic) to near top-down. */''')
patch(port / "port_runtime_config.h",
    '''void Port_Config_SetVoxelView(bool on);''',
    '''void Port_Config_SetVoxelView(bool on);
bool Port_Config_GetVoxelWallFade(void);
void Port_Config_SetVoxelWallFade(bool on);''')

ui = port / "port_imgui_display_tab.inc"
patch(ui,
    '''        // Geometry height and classification are managed by the 3D view.''',
    '''        /* PR #210: screen-door occlusion for 3D room walls. This does
         * NOT adjust geometry height, entity positions or native collisions. */
        ImGui::TableNextRow();
        ImGui::TableSetColumnIndex(0); ImGui::Text("3D walls out of the way");
        ImGui::TableSetColumnIndex(1);
        {
            bool fade = Port_Config_GetVoxelWallFade();
            if (ImGui::Checkbox("##voxel_wall_fade", &fade))
                Port_Config_SetVoxelWallFade(fade);
        }
        RandoUi_HelpTooltip(
            "Dithers walls/roofs between the camera and Link or enemies in "
            "3D mode. Turn off for fully opaque geometry or better performance.");

        // Geometry height and classification are managed by the 3D view.''')

# Pass world-space vertex positions without disturbing the Android fix for
# entity-feet depth and player visibility.
patch(port / "shaders/voxel.vert",
    '''layout(location = 1) flat out uvec4 vParams;''',
    '''layout(location = 1) flat out uvec4 vParams;
layout(location = 2) out vec3 vWorld;''')
patch(port / "shaders/voxel.vert",
    '''    vParams = aParams;''',
    '''    vParams = aParams;
    vWorld = aPos;''')

frag = port / "shaders/voxel.frag"
patch(frag,
    '''layout(location = 1) flat in uvec4 vParams;''',
    '''layout(location = 1) flat in uvec4 vParams;
layout(location = 2) in vec3 vWorld;

/* std140 fragment uniform, set 3 binding 0; uploaded once per drawTo.
 * actor feet (world XYZ), eye (world XYZ), and a 4x4 Bayer pixel screen door.
 * Never dither sprites, HUD, scenery beyond the actor or the ground below it. */
#define VOXEL_FADE_ACTORS 16
layout(set = 3, binding = 0) uniform FadeBlock {
    vec4 uFadeCamera;       // xyz eye, w: enabled
    vec4 uFadeOptions;      // x: opacity, y: radius, z: feather, w: aim height
    ivec4 uFadeCount;
    vec4 uFadeActors[VOXEL_FADE_ACTORS];
};
''')
patch(frag,
    '''void main() {
    ivec2 p = ivec2(floor(vUv));''',
    '''float roomFadeKeep() {
    if (uFadeCamera.w < 0.5) return 1.0;
    float influence = 0.0;
    for (int i = 0; i < VOXEL_FADE_ACTORS; ++i) {
        if (i >= uFadeCount.x) break;
        vec3 feet = uFadeActors[i].xyz;
        if (vWorld.y <= feet.y + 1.0) continue;
        vec3 line = feet + vec3(0.0, uFadeOptions.w, 0.0) - uFadeCamera.xyz;
        float len2 = dot(line, line);
        if (len2 < 1.0) continue;
        float t = dot(vWorld - uFadeCamera.xyz, line) / len2;
        if (t <= 0.0 || t >= 1.0) continue;
        float distanceFromLine = length(vWorld - (uFadeCamera.xyz + line * t));
        float nearLine = 1.0 - smoothstep(uFadeOptions.y,
                                        uFadeOptions.y + uFadeOptions.z,
                                        distanceFromLine);
        influence = max(influence, nearLine);
    }
    return mix(1.0, uFadeOptions.x, influence);
}

float roomBayer4x4(vec2 pixel) {
    const int order[16] = int[16](0, 8, 2, 10, 12, 4, 14, 6,
                                  3, 11, 1, 9, 15, 7, 13, 5);
    ivec2 p = ivec2(pixel) & 3;
    return (float(order[p.y * 4 + p.x]) + 0.5) / 16.0;
}

void main() {
    ivec2 p = ivec2(floor(vUv));''')
patch(frag,
    '''        if (p.x < 0 || p.y < 0 || p.x >= 1024 || p.y >= 1024)
            discard;''',
    '''        if (p.x < 0 || p.y < 0 || p.x >= 1024 || p.y >= 1024)
            discard;
        float keep = roomFadeKeep();
        if (keep < 1.0 && roomBayer4x4(gl_FragCoord.xy) > keep)
            discard;''')

# Shader uniform declaration must match the CPU block and be bound for BOTH
# main 3D draws and the optional screenshot pass. Camera is the actual
# Android viewport camera, not a fixed GBA 240px screen.
patch(voxel,
    '''constexpr float kFovYDeg = 45.0f;''',
    '''constexpr float kFovYDeg = 45.0f;
/* PR #210: geometry-only dither, one fragment UBO, no new draw calls. */
constexpr int kFadeMaxActors = 16;
struct PortVoxelFade {
    float cam[4];
    float opts[4];
    Sint32 count[4];
    float actors[kFadeMaxActors][4];
};
static_assert(sizeof(PortVoxelFade) == (3 + kFadeMaxActors) * 16);
''')
patch(voxel,
    '''    fs.num_samplers = 5;''',
    '''    fs.num_samplers = 5;
    fs.num_uniform_buffers = 1;''')
patch(voxel,
    '''    sShotRequested = true;
}

PortVoxelTileAhead Port_Voxel_TileAhead(void) {''',
    '''    sShotRequested = true;
}

/* Gather physical actors; cap work at 16 even in busy rooms.
 * The wall fade only affects *rendered* geometry, not their native AI.
 * Link first so the player always gets an unobstructed view. */
static void GatherFadeActors(PortVoxelFade& fade) {
    int n = 0;
    auto add = [&](const Entity& e) {
        if (n >= kFadeMaxActors) return;
        fade.actors[n][0] = (float)(e.x.HALF.HI - gRoomControls.origin_x);
        const float raised = (e.collisionLayer & 0x7f) == 2 ? 16.0f : 0.0f;
        fade.actors[n][1] = raised + std::max(0.0f, -(float)e.z.HALF.HI);
        fade.actors[n][2] = (float)(e.y.HALF.HI - gRoomControls.origin_y);
        fade.actors[n][3] = 0.0f;
        ++n;
    };
    add(gPlayerEntity.base);
    for (int l = 0; l < 9 && n < kFadeMaxActors; ++l) {
        LinkedList* list = &gEntityLists[l];
        for (Entity* e = list->first; e && e != (Entity*)list && n < kFadeMaxActors; e = e->next)
            if (e->kind == ENEMY)
                add(*e);
    }
    fade.count[0] = n;
    fade.count[1] = fade.count[2] = fade.count[3] = 0;
}

PortVoxelTileAhead Port_Voxel_TileAhead(void) {''')
patch(voxel,
    '''        /* Backdrop: BG3 stretched over the whole target at the far plane. */''',
    '''        /* The 3D pass owns wall fade. Push before drawing the first quad
         * and again for each drawTo (screen and screenshot). Set disabled
         * when the user turns the switch off; 2D never executes this path. */
        const float fadeTarget[3] = {
            scrollX + viewW * 0.5f, 0.0f, scrollY + 80.0f
        };
        const float fadeEye[3] = {
            fadeTarget[0], kDistance * std::sin(pitch),
            fadeTarget[2] + kDistance * std::cos(pitch)
        };
        PortVoxelFade fade = {};
        fade.cam[0] = fadeEye[0]; fade.cam[1] = fadeEye[1];
        fade.cam[2] = fadeEye[2];
        fade.cam[3] = Port_Config_GetVoxelWallFade() ? 1.0f : 0.0f;
        fade.opts[0] = 0.20f; /* keep 20 percent of intervening wall pixels */
        fade.opts[1] = 20.0f; /* width around camera-to-actor sight line */
        fade.opts[2] = 14.0f; /* feather */
        fade.opts[3] = 12.0f; /* look towards upper body */
        if (fade.cam[3] > 0.0f)
            GatherFadeActors(fade);
        SDL_PushGPUFragmentUniformData(cmd, 0, &fade, sizeof(fade));

        /* Backdrop: BG3 stretched over the whole target at the far plane. */''')

print(f"Applied selective PR #210: {len(entries)} per-area shape defaults, 3D-only wall dither and an Android toggle")
