#!/usr/bin/env python3
from pathlib import Path

path = Path("upstream/tmc/port/port_ppu.cpp")
src = path.read_text(encoding="utf-8")

old = """        const PortBgFill bgFill = Port_Config_BgFill();
        if (bgFill == PORT_BG_FILL_SOLID_COLOR) {
            u8 bgR = 0, bgG = 0, bgB = 0;
            Port_Config_BgFillColor(&bgR, &bgG, &bgB);
            SDL_SetRenderDrawColor(sRenderer, bgR, bgG, bgB, 255);
            SDL_RenderFillRect(sRenderer, &stage);
        } else if (bgFill == PORT_BG_FILL_BLURRED_FRAME) {
            /* Stretch the same texture across the whole stage with
             * linear filtering for a soft "ambient mode" halo, then
             * the sharp letterboxed copy paints over the center. */
            Port_PPU_SetTextureScaleModeCached(tex, SDL_SCALEMODE_LINEAR);
            SDL_RenderTexture(sRenderer, tex, nullptr, &stage);
        }
"""

new = """        const PortBgFill bgFill = Port_Config_BgFill();
        if (bgFill == PORT_BG_FILL_SOLID_COLOR) {
            u8 bgR = 0, bgG = 0, bgB = 0;
            Port_Config_BgFillColor(&bgR, &bgG, &bgB);
            SDL_SetRenderDrawColor(sRenderer, bgR, bgG, bgB, 255);
            SDL_RenderFillRect(sRenderer, &stage);
        } else if (bgFill == PORT_BG_FILL_BLURRED_FRAME) {
#ifndef __ANDROID__
            /* Desktop ambient fill: stretch the same texture across the stage,
             * then draw the sharp frame over it. */
            Port_PPU_SetTextureScaleModeCached(tex, SDL_SCALEMODE_LINEAR);
            SDL_RenderTexture(sRenderer, tex, nullptr, &stage);
#else
            /*
             * Android phone port: DO NOT draw a second copy of the game behind
             * the primary frame. On wide phone displays (S24 Ultra especially),
             * the old ambient-fill implementation looked like two/three game
             * screens layered side-by-side because it was literally the same
             * frame stretched behind the aspect-correct frame.
             *
             * The renderer was already cleared to black above, so leaving the
             * stage untouched gives clean pillar/letterboxing while the normal
             * frame below remains the single visible gameplay surface.
             */
#endif
        }
"""

if old not in src:
    raise SystemExit("expected background-fill present block not found")

src = src.replace(old, new, 1)

viewport_old = """    int aspW = FW;
    int aspH = FH;
    const PortAspectMode mode = Port_Config_AspectMode();
    switch (mode) {
        case PORT_ASPECT_WIDESCREEN_16_9:
            aspW = 16;
            aspH = 9;
            break;
        case PORT_ASPECT_ULTRAWIDE_21_9:
            aspW = 21;
            aspH = 9;
            break;
        case PORT_ASPECT_SUPER_ULTRAWIDE_32_9:
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
    }
"""

viewport_new = """    int aspW = FW;
    int aspH = FH;
#if defined(__ANDROID__) && (MODE1_GBA_WIDTH > 240)
    /*
     * A true-wide Android gameplay frame already tracks the physical phone
     * aspect (Port_Widescreen_TargetViewWidth). Do not letterbox that frame
     * again inside a separate 16:9/21:9 presentation stage. This is what made
     * "Widescreen" still show side bars on 19.5:9 phones.
     *
     * Fixed 240px canvases (title, pause, file-select, one-screen rooms) keep
     * the normal aspect-mode path below and are never stretched.
     */
    if (fbW > 240 && Port_Config_WidescreenEnabled()) {
        aspW = outW;
        aspH = outH;
    } else
#endif
    {
        const PortAspectMode mode = Port_Config_AspectMode();
        switch (mode) {
            case PORT_ASPECT_WIDESCREEN_16_9:
                aspW = 16;
                aspH = 9;
                break;
            case PORT_ASPECT_ULTRAWIDE_21_9:
                aspW = 21;
                aspH = 9;
                break;
            case PORT_ASPECT_SUPER_ULTRAWIDE_32_9:
                aspW = 32;
                aspH = 9;
                break;
            case PORT_ASPECT_NATIVE_3_2:
            default:
                aspW = outW;
                aspH = outH;
                break;
        }
    }
"""

if viewport_old not in src:
    raise SystemExit("expected SDL_Renderer aspect-mode block not found")
src = src.replace(viewport_old, viewport_new, 1)

path.write_text(src, encoding="utf-8")

gpu_path = Path("upstream/tmc/port/port_gpu_renderer.cpp")
gpu = gpu_path.read_text(encoding="utf-8")

gpu_old = """    if (Port_Config_BgFill() == PORT_BG_FILL_BLURRED_FRAME && (stageW != frameW || stageH != frameH)) {
        SDL_GPUViewport vp = {};
        vp.x = (float)stageX;
        vp.y = (float)stageY;
        vp.w = (float)stageW;
        vp.h = (float)stageH;
        vp.min_depth = 0.0f;
        vp.max_depth = 1.0f;
        SDL_SetGPUViewport(rp, &vp);
        SDL_BindGPUGraphicsPipeline(rp, sPipelines[PORT_GPU_FILTER_NONE]);

        SDL_GPUTextureSamplerBinding tsb_bg = {};
        tsb_bg.texture = sSourceTexture;
        tsb_bg.sampler = sSamplerLinear; /* Blurred halo always uses linear */
        SDL_BindGPUFragmentSamplers(rp, 0, &tsb_bg, 1);

        SDL_DrawGPUPrimitives(rp, /*num_vertices=*/4, /*num_instances=*/1, 0, 0);
    }
"""

gpu_new = """#ifndef __ANDROID__
    if (Port_Config_BgFill() == PORT_BG_FILL_BLURRED_FRAME && (stageW != frameW || stageH != frameH)) {
        SDL_GPUViewport vp = {};
        vp.x = (float)stageX;
        vp.y = (float)stageY;
        vp.w = (float)stageW;
        vp.h = (float)stageH;
        vp.min_depth = 0.0f;
        vp.max_depth = 1.0f;
        SDL_SetGPUViewport(rp, &vp);
        SDL_BindGPUGraphicsPipeline(rp, sPipelines[PORT_GPU_FILTER_NONE]);

        SDL_GPUTextureSamplerBinding tsb_bg = {};
        tsb_bg.texture = sSourceTexture;
        tsb_bg.sampler = sSamplerLinear; /* Desktop ambient fill only */
        SDL_BindGPUFragmentSamplers(rp, 0, &tsb_bg, 1);

        SDL_DrawGPUPrimitives(rp, /*num_vertices=*/4, /*num_instances=*/1, 0, 0);
    }
#else
    /*
     * Android single-screen policy: the old ambient backdrop drew the same
     * source frame a second time across the full stage. On a 19.5:9 phone
     * this presents as duplicate game screens to the left/right of the real
     * aspect-correct frame. The swapchain was already cleared to black, so
     * skip the backdrop and leave clean bars around the one real frame.
     */
#endif
"""

if gpu_old not in gpu:
    raise SystemExit("expected SDL_GPU blurred-frame backdrop block not found")

gpu = gpu.replace(gpu_old, gpu_new, 1)

gpu_aspect_old = """        int aspW = FW, aspH = FH;
        const PortAspectMode mode = Port_Config_AspectMode();
        switch (mode) {
            case PORT_ASPECT_WIDESCREEN_16_9:
                aspW = 16;
                aspH = 9;
                break;
            case PORT_ASPECT_ULTRAWIDE_21_9:
                aspW = 21;
                aspH = 9;
                break;
            case PORT_ASPECT_SUPER_ULTRAWIDE_32_9:
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
        }
"""

gpu_aspect_new = """        int aspW = FW, aspH = FH;
#if defined(__ANDROID__) && (MODE1_GBA_WIDTH > 240)
        if (fb_w > 240 && Port_Config_WidescreenEnabled()) {
            /* The wide source frame was computed from the phone's live aspect.
             * Present it directly to the whole swapchain instead of nesting it
             * inside a second fixed aspect constraint. */
            aspW = (int)swap_w;
            aspH = (int)swap_h;
        } else
#endif
        {
            const PortAspectMode mode = Port_Config_AspectMode();
            switch (mode) {
                case PORT_ASPECT_WIDESCREEN_16_9:
                    aspW = 16;
                    aspH = 9;
                    break;
                case PORT_ASPECT_ULTRAWIDE_21_9:
                    aspW = 21;
                    aspH = 9;
                    break;
                case PORT_ASPECT_SUPER_ULTRAWIDE_32_9:
                    aspW = 32;
                    aspH = 9;
                    break;
                case PORT_ASPECT_NATIVE_3_2:
                default:
                    aspW = (int)swap_w;
                    aspH = (int)swap_h;
                    break;
            }
        }
"""

if gpu_aspect_old not in gpu:
    raise SystemExit("expected SDL_GPU aspect-mode block not found")
gpu = gpu.replace(gpu_aspect_old, gpu_aspect_new, 1)

gpu_path.write_text(gpu, encoding="utf-8")

print("Applied Android single-screen + full-display true-widescreen presentation fixes")
