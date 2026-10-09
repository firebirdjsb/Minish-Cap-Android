#pragma once

/* Pure scene rules shared by the renderer and the synthetic regression tour.
 * No SDL or game globals: these rules must also work before the GPU is ready. */
#include <algorithm>
#include <cmath>
#include <cstdint>

namespace voxel {
struct RoomId {
    int area = -1, room = -1, x = 0, z = 0, width = 0, height = 0;
    bool operator==(const RoomId& b) const {
        return area == b.area && room == b.room && x == b.x && z == b.z &&
               width == b.width && height == b.height;
    }
    bool operator!=(const RoomId& b) const { return !(*this == b); }
};

struct LayerBinding {
    int bg = -1, candidateBg = -1, frames = 0;
    std::uint16_t control = 0, candidateControl = 0;
    void observe(int liveBg, std::uint16_t liveControl, bool shown) {
        // Screen-block/size bits change during scrolling; only art format and
        // priority belong to the room material binding.
        liveControl &= 0x008f;
        if (!shown || liveBg < 0) {
            frames = 0;
            candidateBg = -1;
            return;
        }
        if (bg == liveBg && control == liveControl) {
            frames = 0;
            candidateBg = -1;
            return;
        }
        if (candidateBg != liveBg || candidateControl != liveControl) {
            candidateBg = liveBg;
            candidateControl = liveControl;
            frames = 1;
        } else {
            ++frames;
        }
        if (frames >= (bg < 0 ? 3 : 5)) {
            bg = liveBg;
            control = liveControl;
            frames = 0;
        }
    }
    bool agrees(int liveBg, std::uint16_t liveControl) const {
        return bg >= 0 && bg == liveBg && control == (liveControl & 0x008f);
    }
};

/* Room loading is not atomic: native collision, BG1/BG2 ownership,
 * characters and palette may arrive across several game frames. The mesh
 * classifier reads ALL of these, so rendering after the bottom map alone
 * briefly exposes bare roof beams and scrambled sides. Only the FIRST mesh
 * of a room needs a longer handoff; ordinary animated room updates retain
 * MeshGate's shorter three-frame stabilization.
 *
 * The top layer may legitimately be unused in a room. Wait for a confirmed
 * top binding when one is configured, with a bounded fallback so bottom-only
 * rooms are never locked out of 3D.
 */
struct RoomBootstrap {
    std::uint64_t previous = 0;
    int frames = 0;
    int unchanged = 0;
    bool ready = false;

    bool observe(bool bottomReady, bool expectsTop, bool topReady,
                 std::uint64_t graphicsSignature) {
        if (ready)
            return true;
        if (!bottomReady) {
            // A transition frame is not a meaningful sample. A later room
            // update must establish a fresh run of stable graphics.
            unchanged = 0;
            return false;
        }
        ++frames;
        if (unchanged && previous == graphicsSignature)
            ++unchanged;
        else {
            previous = graphicsSignature;
            unchanged = 1;
        }

        // Even when bottom arrives first, allow time for the top map and
        // animated tile graphics to be uploaded by the native loader.
        const int minimum = expectsTop && !topReady ? 48 : 14;
        if (frames < minimum)
            return false;
        if (expectsTop && !topReady && frames < 48)
            return false;
        if (unchanged >= 8 || frames >= 96)
            ready = true; // bounded if native BG animation changes every tick
        return ready;
    }
};

struct MeshGate {
    std::uint64_t pending = 0, accepted = 0;
    int frames = 0;
    bool ready = false;
    bool observe(std::uint64_t key, bool stable) {
        if (!stable) {
            frames = 0;
            return false;
        }
        if (ready && key == accepted) {
            frames = 0;
            return false;
        }
        if (!frames || key != pending) {
            pending = key;
            frames = 1;
        } else {
            ++frames;
        }
        if (frames < 3)
            return false;
        accepted = key;
        ready = true;
        frames = 0;
        return true;
    }
};

struct FrontFace {
    float x0, x1, z, height;
    int tile;
    std::uint16_t mapTile;
};

inline bool crossFront(const FrontFace& f, float oldX, float oldZ,
                       float newX, float newZ, float& contactZ) {
    // A small approach from the south to a real front face. No teleport,
    // overlap recovery, side-face collision, or height/layer replacement.
    const float dz = newZ - oldZ;
    const float plane = f.z + 3.0f;
    if (dz >= 0.0f || dz < -8.0f || std::abs(newX - oldX) > 8.0f ||
        oldZ < plane || newZ >= plane)
        return false;
    const float x = oldX + (newX - oldX) * (plane - oldZ) / dz;
    if (x < f.x0 + 1.0f || x > f.x1 - 1.0f)
        return false;
    contactZ = plane;
    return true;
}

inline float frontDepthHeight(const FrontFace& f, float x, float z, float pitch) {
    // A sprite whose physical feet are south of a wall must win over that
    // wall's raised top. Bias DEPTH only, within its projected contact band.
    const float band = std::min(32.0f, f.height * std::cos(pitch) /
                                          std::max(0.1f, std::sin(pitch)) + 3.0f);
    return x >= f.x0 && x <= f.x1 && z >= f.z && z <= f.z + band ? f.height : 0.0f;
}

struct Viewport { float x, y, w, h; };
inline Viewport fitViewport(int w, int h, float aspect) {
    Viewport v{0, 0, static_cast<float>(w), static_cast<float>(h)};
    if (v.w / v.h > aspect)
        v.w = v.h * aspect;
    else
        v.h = v.w / aspect;
    v.x = (w - v.w) * 0.5f;
    v.y = (h - v.h) * 0.5f;
    return v;
}
} // namespace voxel
