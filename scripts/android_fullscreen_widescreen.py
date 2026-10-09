#!/usr/bin/env python3
from pathlib import Path

ppu = Path("upstream/tmc/port/port_ppu.cpp")
src = ppu.read_text(encoding="utf-8")

src = src.replace(
"""    if (fbW > 240 && Port_Config_WidescreenEnabled()) {
        aspW = outW;
        aspH = outH;
    } else
""",
"""    if (Port_Config_WidescreenEnabled()) {
        /* Android widescreen owns the whole physical display. Wide gameplay
         * frames reveal real world content; fixed 240px GBA canvases remain
         * aspect-correct in the centre and the presenter extends only their
         * edge background into the remaining phone area below. */
        aspW = outW;
        aspH = outH;
    } else
""", 1)

edge_anchor = """        Port_PPU_SetTextureScaleModeCached(tex, scale);
        SDL_RenderTexture(sRenderer, tex, nullptr, &dst);
"""
edge_block = r'''#ifdef __ANDROID__
        /*
         * Phone widescreen fill for fixed GBA canvases.
         *
         * A file-select/name-entry/title screen genuinely contains only a
         * 240x160 canvas, so there is no honest extra world geometry to reveal.
         * Do NOT stretch that UI and do NOT draw a second copy behind it.
         * Instead, extend a thin strip from the left/right scene edges into the
         * unused phone area. The sharp original frame remains untouched in the
         * centre while the display has no black side boxes.
         */
        if (Port_Config_WidescreenEnabled() && (dst.x > stage.x || dst.x + dst.w < stage.x + stage.w)) {
            float tw = 0.0f, th = 0.0f;
            if (SDL_GetTextureSize(tex, &tw, &th) && tw > 1.0f && th > 1.0f) {
                const float edgePx = (tw * 0.045f > 1.0f) ? (tw * 0.045f) : 1.0f;
                Port_PPU_SetTextureScaleModeCached(tex, SDL_SCALEMODE_LINEAR);

                if (dst.x > stage.x) {
                    SDL_FRect srcEdge{ 0.0f, 0.0f, edgePx, th };
                    SDL_FRect dstEdge{ stage.x, dst.y, dst.x - stage.x, dst.h };
                    SDL_RenderTexture(sRenderer, tex, &srcEdge, &dstEdge);
                }
                const float frameRight = dst.x + dst.w;
                const float stageRight = stage.x + stage.w;
                if (frameRight < stageRight) {
                    SDL_FRect srcEdge{ tw - edgePx, 0.0f, edgePx, th };
                    SDL_FRect dstEdge{ frameRight, dst.y, stageRight - frameRight, dst.h };
                    SDL_RenderTexture(sRenderer, tex, &srcEdge, &dstEdge);
                }
            }
        }
#endif

        Port_PPU_SetTextureScaleModeCached(tex, scale);
        SDL_RenderTexture(sRenderer, tex, nullptr, &dst);
'''
if edge_anchor not in src:
    raise SystemExit("SDL sharp-frame anchor not found")
src = src.replace(edge_anchor, edge_block, 1)
ppu.write_text(src, encoding="utf-8")

gpu_path = Path("upstream/tmc/port/port_gpu_renderer.cpp")
gpu = gpu_path.read_text(encoding="utf-8")

gpu = gpu.replace(
"""        if (fb_w > 240 && Port_Config_WidescreenEnabled()) {
            /* The wide source frame was computed from the phone's live aspect.
             * Present it directly to the whole swapchain instead of nesting it
             * inside a second fixed aspect constraint. */
            aspW = (int)swap_w;
            aspH = (int)swap_h;
        } else
""",
"""        if (Port_Config_WidescreenEnabled()) {
            /* Android widescreen always owns the whole swapchain. Fixed
             * 240px scenes stay aspect-correct and get edge-only background
             * extension; true-wide gameplay uses the real wide framebuffer. */
            aspW = (int)swap_w;
            aspH = (int)swap_h;
        } else
""", 1)

gpu_anchor = """    /* Sharp game frame in the inner viewport. */
"""
gpu_edge = r'''#ifdef __ANDROID__
    /*
     * SDL_GPU equivalent of the fixed-canvas edge extension above. The
     * passthrough shader always samples UV 0..1 from the viewport, so an
     * oversized viewport + scissor lets each side bar sample only a narrow
     * source-edge strip without requiring a special shader or duplicating the
     * full game image.
     */
    if (Port_Config_WidescreenEnabled() && frameH > 0 &&
        (frameX > stageX || frameX + frameW < stageX + stageW)) {
        constexpr float edgeFrac = 0.045f;
        SDL_BindGPUGraphicsPipeline(rp, sPipelines[PORT_GPU_FILTER_NONE]);

        SDL_GPUTextureSamplerBinding edgeBinding = {};
        edgeBinding.texture = sSourceTexture;
        edgeBinding.sampler = sSamplerLinear;
        SDL_BindGPUFragmentSamplers(rp, 0, &edgeBinding, 1);

        if (frameX > stageX) {
            const int barW = frameX - stageX;
            SDL_GPUViewport vp = {};
            vp.x = (float)stageX;
            vp.y = (float)frameY;
            vp.w = (float)barW / edgeFrac;
            vp.h = (float)frameH;
            vp.min_depth = 0.0f;
            vp.max_depth = 1.0f;
            SDL_Rect sc{ stageX, frameY, barW, frameH };
            SDL_SetGPUViewport(rp, &vp);
            SDL_SetGPUScissor(rp, &sc);
            SDL_DrawGPUPrimitives(rp, 4, 1, 0, 0);
        }

        const int frameRight = frameX + frameW;
        const int stageRight = stageX + stageW;
        if (frameRight < stageRight) {
            const int barW = stageRight - frameRight;
            const float vpW = (float)barW / edgeFrac;
            SDL_GPUViewport vp = {};
            vp.x = (float)frameRight - (1.0f - edgeFrac) * vpW;
            vp.y = (float)frameY;
            vp.w = vpW;
            vp.h = (float)frameH;
            vp.min_depth = 0.0f;
            vp.max_depth = 1.0f;
            SDL_Rect sc{ frameRight, frameY, barW, frameH };
            SDL_SetGPUViewport(rp, &vp);
            SDL_SetGPUScissor(rp, &sc);
            SDL_DrawGPUPrimitives(rp, 4, 1, 0, 0);
        }

        SDL_Rect fullScissor{ 0, 0, (int)swap_w, (int)swap_h };
        SDL_SetGPUScissor(rp, &fullScissor);
    }
#endif

    /* Sharp game frame in the inner viewport. */
'''
if gpu_anchor not in gpu:
    raise SystemExit("GPU sharp-frame anchor not found")
gpu = gpu.replace(gpu_anchor, gpu_edge, 1)
gpu_path.write_text(gpu, encoding="utf-8")

print("Added full-display Android widescreen with fixed-scene edge extension")
