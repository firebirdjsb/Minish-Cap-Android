#!/usr/bin/env python3
from pathlib import Path

# Android aspect handling:
# - Native 3:2, 16:9, 21:9 and 32:9 are real render targets.
# - Device / Full Screen renders to the phone's live aspect.
# - Wide gameplay is rendered at the chosen aspect before presentation,
#   instead of rendering for the phone then letterboxing it a second time.

hdr = Path("upstream/tmc/port/port_runtime_config.h")
h = hdr.read_text(encoding="utf-8")

old_enum = """typedef enum {
    PORT_ASPECT_NATIVE_3_2 = 0,
    PORT_ASPECT_WIDESCREEN_16_9 = 1,
    PORT_ASPECT_ULTRAWIDE_21_9 = 2,
    PORT_ASPECT_SUPER_ULTRAWIDE_32_9 = 3,
    PORT_ASPECT_COUNT,
} PortAspectMode;
"""
new_enum = """typedef enum {
    PORT_ASPECT_NATIVE_3_2 = 0,
    PORT_ASPECT_WIDESCREEN_16_9 = 1,
    PORT_ASPECT_ULTRAWIDE_21_9 = 2,
    PORT_ASPECT_SUPER_ULTRAWIDE_32_9 = 3,
    PORT_ASPECT_DEVICE = 4,
    PORT_ASPECT_COUNT,
} PortAspectMode;
"""
if old_enum not in h:
    raise SystemExit("aspect enum anchor not found")
h = h.replace(old_enum, new_enum, 1)
hdr.write_text(h, encoding="utf-8")

cfg = Path("upstream/tmc/port/port_runtime_config.cpp")
src = cfg.read_text(encoding="utf-8")

src = src.replace(
"""PortAspectMode sAspectMode = PORT_ASPECT_NATIVE_3_2;
""",
"""#ifdef __ANDROID__
PortAspectMode sAspectMode = PORT_ASPECT_DEVICE;
#else
PortAspectMode sAspectMode = PORT_ASPECT_NATIVE_3_2;
#endif
""", 1)

src = src.replace(
"""    j["aspect_mode"] = "native";
""",
"""#ifdef __ANDROID__
    j["aspect_mode"] = "device";
#else
    j["aspect_mode"] = "native";
#endif
""", 1)

parse_old = """            if (am == "16:9" || am == "widescreen")
                sAspectMode = PORT_ASPECT_WIDESCREEN_16_9;
            else if (am == "21:9" || am == "ultrawide")
                sAspectMode = PORT_ASPECT_ULTRAWIDE_21_9;
            else if (am == "32:9" || am == "super_ultrawide")
                sAspectMode = PORT_ASPECT_SUPER_ULTRAWIDE_32_9;
            else
                sAspectMode = PORT_ASPECT_NATIVE_3_2;
"""
parse_new = """            if (am == "16:9" || am == "widescreen")
                sAspectMode = PORT_ASPECT_WIDESCREEN_16_9;
            else if (am == "21:9" || am == "ultrawide")
                sAspectMode = PORT_ASPECT_ULTRAWIDE_21_9;
            else if (am == "32:9" || am == "super_ultrawide")
                sAspectMode = PORT_ASPECT_SUPER_ULTRAWIDE_32_9;
            else if (am == "device" || am == "fullscreen" || am == "full_screen")
                sAspectMode = PORT_ASPECT_DEVICE;
            else
                sAspectMode = PORT_ASPECT_NATIVE_3_2;
"""
if parse_old not in src:
    raise SystemExit("aspect parse block not found")
src = src.replace(parse_old, parse_new, 1)

name_old = """        case PORT_ASPECT_SUPER_ULTRAWIDE_32_9:
            return "Super Ultrawide 32:9";
        case PORT_ASPECT_NATIVE_3_2:
        default:
            return "Native 3:2 (GBA)";
"""
name_new = """        case PORT_ASPECT_SUPER_ULTRAWIDE_32_9:
            return "Super Ultrawide 32:9";
        case PORT_ASPECT_DEVICE:
            return "Device / Full Screen";
        case PORT_ASPECT_NATIVE_3_2:
        default:
            return "Native 3:2 (GBA)";
"""
if name_old not in src:
    raise SystemExit("aspect name block not found")
src = src.replace(name_old, name_new, 1)

set_old = """        case PORT_ASPECT_SUPER_ULTRAWIDE_32_9:
            name = "32:9";
            break;
        case PORT_ASPECT_NATIVE_3_2:
        default:
            name = "native";
            break;
"""
set_new = """        case PORT_ASPECT_SUPER_ULTRAWIDE_32_9:
            name = "32:9";
            break;
        case PORT_ASPECT_DEVICE:
            name = "device";
            break;
        case PORT_ASPECT_NATIVE_3_2:
        default:
            name = "native";
            break;
"""
if set_old not in src:
    raise SystemExit("aspect save block not found")
src = src.replace(set_old, set_new, 1)

# One-time migration: old Android builds defaulted to 16:9/native presentation.
# Move existing installs to exact device fill once, then preserve user choice.
migration_old = """    if (!sConfigJson.contains("android_color_correction_default_version")) {
        sColorCorrect = true;
        sConfigJson["color_correction"] = true;
        sConfigJson["android_color_correction_default_version"] = 1;
        SaveConfig();
    }
#endif
"""
migration_new = """    if (!sConfigJson.contains("android_color_correction_default_version")) {
        sColorCorrect = true;
        sConfigJson["color_correction"] = true;
        sConfigJson["android_color_correction_default_version"] = 1;
        SaveConfig();
    }

    if (!sConfigJson.contains("android_aspect_default_version")) {
        sAspectMode = PORT_ASPECT_DEVICE;
        sConfigJson["aspect_mode"] = "device";
        sConfigJson["android_aspect_default_version"] = 1;
        SaveConfig();
    }
#endif
"""
if migration_old not in src:
    raise SystemExit("Android config migration anchor not found")
src = src.replace(migration_old, migration_new, 1)
cfg.write_text(src, encoding="utf-8")

# Make the internal true-widescreen width follow the selected aspect.
ws = Path("upstream/tmc/port/port_linked_stubs.c")
w = ws.read_text(encoding="utf-8")

target_old = """    if (sWsWindowW <= 0 || sWsWindowH <= 0) {
        return 240;
    }
    /* Exact aspect fit: the width that makes the 160-line frame fill the
     * window (no rounding — every consumer is pixel-based, and exact fit
     * beats up-to-7px side bars). */
    w = (int)(((long long)sWsWindowW * 160) / sWsWindowH);
    if (w < 240)
        w = 240;
    if (w > MODE1_GBA_WIDTH)
        w = MODE1_GBA_WIDTH;
    return w;
"""
target_new = """    {
        const PortAspectMode mode = Port_Config_AspectMode();
        switch (mode) {
            case PORT_ASPECT_NATIVE_3_2:
                return 240;
            case PORT_ASPECT_WIDESCREEN_16_9:
                w = (160 * 16 + 4) / 9;
                break;
            case PORT_ASPECT_ULTRAWIDE_21_9:
                w = (160 * 21 + 4) / 9;
                break;
            case PORT_ASPECT_SUPER_ULTRAWIDE_32_9:
                w = (160 * 32 + 4) / 9;
                break;
            case PORT_ASPECT_DEVICE:
            default:
                if (sWsWindowW <= 0 || sWsWindowH <= 0)
                    return 240;
                w = (int)(((long long)sWsWindowW * 160 + sWsWindowH / 2) / sWsWindowH);
                break;
        }
    }
    if (w < 240)
        w = 240;
    if (w > MODE1_GBA_WIDTH)
        w = MODE1_GBA_WIDTH;
    return w;
"""
if target_old not in w:
    raise SystemExit("widescreen target-width block not found")
w = w.replace(target_old, target_new, 1)
ws.write_text(w, encoding="utf-8")

# SDL_Renderer presentation: each aspect gets a real stage. Wide gameplay is
# presented directly into that exact stage, avoiding a second nested fit.
ppu = Path("upstream/tmc/port/port_ppu.cpp")
p = ppu.read_text(encoding="utf-8")

switch_old = """        case PORT_ASPECT_SUPER_ULTRAWIDE_32_9:
            aspW = 32;
            aspH = 9;
            break;
        case PORT_ASPECT_NATIVE_3_2:
        default:
            /* "No constraint": the stage spans the whole window. With the
             * historical black fill this is pixel-identical to the old
             * stage==frame behavior; with solid/blurred fills it lets the
             * ambient backdrop cover the entire monitor, so fixed-canvas
             * scenes (title, one-screen rooms) have no dead black bars. */
            aspW = outW;
            aspH = outH;
            break;
"""
switch_new = """        case PORT_ASPECT_SUPER_ULTRAWIDE_32_9:
            aspW = 32;
            aspH = 9;
            break;
        case PORT_ASPECT_DEVICE:
            aspW = outW;
            aspH = outH;
            break;
        case PORT_ASPECT_NATIVE_3_2:
        default:
            aspW = 3;
            aspH = 2;
            break;
"""
if switch_old not in p:
    raise SystemExit("SDL aspect switch block not found")
p = p.replace(switch_old, switch_new, 1)

fit_old = """    Port_PPU_FitAspectRect(outW, outH, aspW, aspH, stageX, stageY, stageW, stageH);
    // Inside the stage, fit the GBA frame at its native 3:2.
    int fx, fy, fw, fh;
    Port_PPU_FitAspectRect(*stageW, *stageH, FW, FH, &fx, &fy, &fw, &fh);
    *frameX = *stageX + fx;
    *frameY = *stageY + fy;
    *frameW = fw;
    *frameH = fh;
"""
fit_new = """    Port_PPU_FitAspectRect(outW, outH, aspW, aspH, stageX, stageY, stageW, stageH);

#if defined(__ANDROID__) && (MODE1_GBA_WIDTH > 240)
    if (Port_Config_WidescreenEnabled() && fbW > 240) {
        /* The source width was generated for this same selected aspect.
         * Present it directly into the stage so 16:9/21:9/32:9/device are
         * exact rather than being fitted a second time. */
        *frameX = *stageX;
        *frameY = *stageY;
        *frameW = *stageW;
        *frameH = *stageH;
        return;
    }
#endif

    int fx, fy, fw, fh;
    Port_PPU_FitAspectRect(*stageW, *stageH, FW, FH, &fx, &fy, &fw, &fh);
    *frameX = *stageX + fx;
    *frameY = *stageY + fy;
    *frameW = fw;
    *frameH = fh;
"""
if fit_old not in p:
    raise SystemExit("SDL frame-fit block not found")
p = p.replace(fit_old, fit_new, 1)
ppu.write_text(p, encoding="utf-8")

# SDL_GPU/Vulkan equivalent.
gpu = Path("upstream/tmc/port/port_gpu_renderer.cpp")
g = gpu.read_text(encoding="utf-8")

gpu_switch_old = """            case PORT_ASPECT_SUPER_ULTRAWIDE_32_9:
                aspW = 32;
                aspH = 9;
                break;
            case PORT_ASPECT_NATIVE_3_2:
            default:
                /* "No constraint": stage spans the whole swapchain (see
                 * Port_PPU_ComputeViewportRects — identical for black fill,
                 * lets solid/blurred fills cover the entire monitor). */
                aspW = (int)swap_w;
                aspH = (int)swap_h;
                break;
"""
gpu_switch_new = """            case PORT_ASPECT_SUPER_ULTRAWIDE_32_9:
                aspW = 32;
                aspH = 9;
                break;
            case PORT_ASPECT_DEVICE:
                aspW = (int)swap_w;
                aspH = (int)swap_h;
                break;
            case PORT_ASPECT_NATIVE_3_2:
            default:
                aspW = 3;
                aspH = 2;
                break;
"""
if gpu_switch_old not in g:
    raise SystemExit("GPU aspect switch block not found")
g = g.replace(gpu_switch_old, gpu_switch_new, 1)

gpu_fit_old = """        if (stageW * FH >= stageH * FW) {
            frameH = stageH;
            frameW = (stageH * FW) / FH;
        } else {
            frameW = stageW;
            frameH = (stageW * FH) / FW;
        }
        frameX = stageX + (stageW - frameW) / 2;
        frameY = stageY + (stageH - frameH) / 2;
"""
gpu_fit_new = """#if defined(__ANDROID__) && (MODE1_GBA_WIDTH > 240)
        if (Port_Config_WidescreenEnabled() && fb_w > 240) {
            frameX = stageX;
            frameY = stageY;
            frameW = stageW;
            frameH = stageH;
        } else
#endif
        {
            if (stageW * FH >= stageH * FW) {
                frameH = stageH;
                frameW = (stageH * FW) / FH;
            } else {
                frameW = stageW;
                frameH = (stageW * FH) / FW;
            }
            frameX = stageX + (stageW - frameW) / 2;
            frameY = stageY + (stageH - frameH) / 2;
        }
"""
if gpu_fit_old not in g:
    raise SystemExit("GPU frame-fit block not found")
g = g.replace(gpu_fit_old, gpu_fit_new, 1)
gpu.write_text(g, encoding="utf-8")

print("Applied native Android aspect targets: 3:2, 16:9, 21:9, 32:9, Device")
