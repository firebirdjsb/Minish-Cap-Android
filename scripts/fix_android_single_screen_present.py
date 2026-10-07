#!/usr/bin/env python3
from pathlib import Path

# Keep the original single-screen safety fix: Android must never render a
# second stretched copy of the full game frame behind the real frame.
ppu_path = Path("upstream/tmc/port/port_ppu.cpp")
src = ppu_path.read_text(encoding="utf-8")

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
            Port_PPU_SetTextureScaleModeCached(tex, SDL_SCALEMODE_LINEAR);
            SDL_RenderTexture(sRenderer, tex, nullptr, &stage);
#else
            /*
             * Never draw the complete game frame a second time as an Android
             * backdrop. That was the source of the duplicated/overlaid screen
             * seen on wide Samsung displays.
             */
#endif
        }
"""

if old not in src:
    raise SystemExit("expected SDL_Renderer ambient-fill block not found")
src = src.replace(old, new, 1)
ppu_path.write_text(src, encoding="utf-8")

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
        tsb_bg.sampler = sSamplerLinear;
        SDL_BindGPUFragmentSamplers(rp, 0, &tsb_bg, 1);
        SDL_DrawGPUPrimitives(rp, 4, 1, 0, 0);
    }
#else
    /* Android: one game image only. No duplicated full-frame backdrop. */
#endif
"""

if gpu_old not in gpu:
    raise SystemExit("expected SDL_GPU ambient-fill block not found")
gpu = gpu.replace(gpu_old, gpu_new, 1)
gpu_path.write_text(gpu, encoding="utf-8")

print("Applied Android one-frame-only presentation safety fix")
