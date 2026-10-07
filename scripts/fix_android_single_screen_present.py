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

path.write_text(src.replace(old, new, 1), encoding="utf-8")
print("Disabled duplicate-frame ambient fill on Android")
