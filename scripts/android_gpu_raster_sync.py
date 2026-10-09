#!/usr/bin/env python3
from pathlib import Path

ppu = Path("upstream/tmc/port/port_ppu.cpp")
src = ppu.read_text(encoding="utf-8")

old = """        } else {
            /* Deferred: false only during warm-up (no prior frame ready yet) —
             * then let the CPU render this one frame. */
            if (!Port_GpuRaster_RenderReadbackDeferred(sGpuRaster, &f, virtuappu_frame_buffer, pitch)) {
                return false;
            }
        }
"""

new = """        } else {
#ifdef __ANDROID__
            /*
             * Android correctness path:
             *
             * The deferred raster path can miss its previous-frame fence and
             * return false. The caller then CPU-renders the CURRENT frame, but
             * the delayed GPU frame stays queued and may be copied out on the
             * next tick. That violates presentation order:
             *
             *   current CPU frame -> older GPU frame -> current frame
             *
             * On a moving camera this is visible as a one-refresh world jump /
             * flicker. Never mix those two timelines on Android. Read back the
             * current GPU frame synchronously so every presented framebuffer
             * belongs to the current emulation tick.
             */
            if (!Port_GpuRaster_RenderReadback(sGpuRaster, &f, virtuappu_frame_buffer, pitch)) {
                return false;
            }
#else
            /* Desktop keeps the latency-optimized deferred path. */
            if (!Port_GpuRaster_RenderReadbackDeferred(sGpuRaster, &f, virtuappu_frame_buffer, pitch)) {
                return false;
            }
#endif
        }
"""
if old not in src:
    raise SystemExit("deferred GPU raster block not found")
src = src.replace(old, new, 1)
ppu.write_text(src, encoding="utf-8")
print("Android GPU raster now presents current-frame readback only")
