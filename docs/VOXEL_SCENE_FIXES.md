# Android 3D scene fixes

The final `android_voxel_scene_fix.py` preparation stage runs after the existing
voxel transforms against pinned Project Picori commit `bd06a6391`. It checks every
source anchor, so an upstream change fails preparation instead of silently
dropping a fix. The disabled full smoke-test transform stays disabled.

## Rendering and room state

- Connected wall, cliff, tree and log runs have no foliage cutout masks. Their
  exposed sides sample the complete facade tile belonging to each height band,
  compose top art over bottom art, and fill transparent base texels. Neighbour
  height limits side generation; north-facing return surfaces close the boxes.
- Every map quad carries its owning tile. Shader UV clamping prevents a reversed
  side or tile endpoint from reading adjacent map art.
- Initial meshes and subsequent changes require three consecutive matching,
  verified map frames. Area, room, origin or dimension changes immediately
  invalidate mesh, layer bindings, height and contact faces, even when rendering
  falls back to 2D during a transition.
- Bottom and top BG ownership and material controls are confirmed together.
  Screen-block changes during scrolling do not change the material identity.
  Accepted map snapshots remain paired with the mesh until the next rebuild;
  palette effects and VRAM tile animations remain live.
- Small unsupported overlay fragments are suppressed. Interior floor details
  stay at floor height. Top-layer side-door opening and jamb art is rendered on
  the left/right boundary plane instead of floating horizontal cards. The two
  edge art columns occupy separate height bands so their textures do not overlap.

## Player interaction

Entity OAM pieces share their physical room position and feet, independently of
animation offsets and camera smoothing. Link's depth gets a local contact
adjustment when his feet are in front of a real wall; his rendered height does
not change. Geometry behind which he stands can still occlude him.

Native movement runs first. A remaining small northward crossing of a rendered,
fully native-blocked front face can be shortened to three pixels in front of
that face. This applies only to ordinary grounded, bottom-layer player walking.
It excludes noclip, jumping, Minish form, other collision types, scrolling,
teleports, overlap recovery, decorative overhangs, openings and low ledges.
Changed native tiles immediately stop enforcing cached faces. It never changes
collision layers, player height, or other entities' movement.

## View and aspect

Camera distance increases from 250 to 290 pixels, and the ground-only outdoor
skirt from 18 to 40 tiles. Raised scenery is never cloned into the skirt. Buffer
capacity covers the larger skirt and closed faces. Projection uses the selected
native, 16:9, 21:9, 32:9 or device viewport; backdrop and screen-space HUD use the
same stage. The far plane is 3072 with a 24-pixel near plane.

## Validation

Run `bash scripts/prepare_android.sh`, then `python3 scripts/check_voxel_scene.py`.
The latter finds installed xmake dependency headers; local builds can pass
`--include-dir` for SDL3, nlohmann/json and PNG headers. `--sanitize` enables
address and undefined-behaviour sanitizers.

The ROM-free regression tour invokes the actual prepared `BuildMap` using
synthetic native maps. It checks connected runs, side ownership, closed ends,
ground-only skirts, doorway planes, orphan suppression, room invalidation,
binding debounce, movement/contact rules and viewport calculations. It compiles
at both 240 and 576 pixel framebuffer widths and runs in Android CI before APK
packaging.

These checks do not replace playing the supplied screenshot locations on a
phone. The renderer still infers heights and doorway ownership from native 2D
maps; area-specific art may require further refinement. A user-owned ROM and
matching saves are required for exact house/blacksmith/outdoor visual QA.
