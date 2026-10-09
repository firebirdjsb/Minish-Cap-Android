# Upstream PR and fork compatibility audit — October 9, 2026

Target: \`firebirdjsb/Minish-Cap-Android\`, branch \`android-s24-single-screen\`.
Pinned source: \`999sian/tmc\` at \`bd06a63919951ed75fca3e8cbb6c6cb728823321\`.
Scope: one-phone-screen Android, 3D voxel geometry, native 2D fidelity, widescreen,
rendering stability. Do **not** pull unrelated PC launchers, Vulkan-only assumptions,
multiplayer, save changes, or Linux/Vita framebuffer code into the app.

## Direct upstream PR review

| PR | Finding | Android decision |
| --- | --- | --- |
| [#219](https://github.com/999sian/tmc/pull/219) | OAM 256px offscreen sprite margin, true-position tags | **Already integrated and confirmed by phone test**; Android 576px x wrapping patched separately |
| [#213](https://github.com/999sian/tmc/pull/213) | One-tile camera/BG scroll latch lag flashes 2D, matches actual observed flicker | **Ported** nine-neighbour best-score matching into \`scripts/android_voxel_pr213_scroll.py\`; keep 3D scene safety and Android room latch |
| [#210](https://github.com/999sian/tmc/pull/210) | 510 default shape classifications / wall dithering | **Integrated previously**; filtered with native collision/one-tile height rules; bridge decks excluded from dither |
| [#218](https://github.com/999sian/tmc/pull/218) | Windows/Linux asset build-cache acceleration | Not runtime 3D; Android custom pipeline already handles assets |
| [#217](https://github.com/999sian/tmc/pull/217), [#216](https://github.com/999sian/tmc/pull/216), [#215](https://github.com/999sian/tmc/pull/215) | Windows first-launch asset extraction speed/race fixes | Consider separately for import performance; do not risk renderer regression |
| [#214](https://github.com/999sian/tmc/pull/214), [#212](https://github.com/999sian/tmc/pull/212) | Windows file binary mode and build.py utility path | Windows-only, not Android single-screen |
| [#207](https://github.com/999sian/tmc/pull/207) | Unit-test symbol stubs | Build-specific; current Android synthetic test harness stubs its symbols already |
| [#206](https://github.com/999sian/tmc/pull/206) | Skip desktop launcher | Separate prelaunch/UI consideration, not 3D voxel |
| [#168](https://github.com/999sian/tmc/pull/168), [#167](https://github.com/999sian/tmc/pull/167), [#188](https://github.com/999sian/tmc/pull/188), [#187](https://github.com/999sian/tmc/pull/187) | Widescreen pacing, map bounds, gameplay and 3DS-audit fixes | Merged *before* pinned master; do not duplicate blindly |
| [#158](https://github.com/999sian/tmc/pull/158) | 2D accuracy / feedback response | Merged before pin; regression-test downstream overrides instead of replaying patch |
| Other merged upstream PRs | Achievements, editor, debug, controller or localization features | Not direct fixes to phone 3D geometry |

Upstream issues also flag touch controls (#202), 3D menu discoverability (#204),
32:9 field-of-view (#174), and cave/waterfall entrances (#195). They are useful
future regression locations, but do not prove an applicable unmerged fix.

## Downstream fork survey

Searched the available public Minish Cap port repositories and inspected the
latest changes in the 22 major forks/derivatives found. Repositories that did
not diverge from the pinned baseline, or did only unrelated changes, are
documented rather than wholesale-merged.

| Repository | Distinctive changes / relevance | Action |
| --- | --- | --- |
| [Strikeborn/tmc](https://github.com/Strikeborn/tmc) | PRs #212–219, esp. #213 scroll flicker and #219 off-screen OAM | **#219 retained; #213 selectively ported** |
| [HelaFaye/tmc](https://github.com/HelaFaye/tmc) | PR #210, roomcap/curated shapes; randomizer work | **PR #210 already adapted for Android** |
| [cualquiercosa327/tmc-Pc](https://github.com/cualquiercosa327/tmc-Pc) | Widescreen overlays, top-edge shake, cave transitions, save protection | Older fixes are also available in upstream history; avoid duplicate renderer replacements |
| [alfonsoalvarohervas-sudo/tmc](https://github.com/alfonsoalvarohervas-sudo/tmc) | Same regional/widescreen changes, game/editor work | No independent 3D/Android fix to port |
| [pacoa-kdbg/tmc](https://github.com/pacoa-kdbg/tmc) | Port edge-case fixes, pointer/demo/alias guards | Older than pinned source; compare only if problem reproduced |
| [luis128-cpu/tmc](https://github.com/luis128-cpu/tmc) | Similar port guards | No novel 3D rendering fix |
| [cgreg21/tmc](https://github.com/cgreg21/tmc) | Merged upstream audited bugfixes | Already part of pinned source |
| [feiyunwill/tmc](https://github.com/feiyunwill/tmc) | Entity-pool and 64-bit boss fixes | Already integrated before pinned baseline |
| [0xcaolan/tmc](https://github.com/0xcaolan/tmc) | Same entity stability lineage | No new voxel changes |
| [NoseDevilEugen/tmc](https://github.com/NoseDevilEugen/tmc) | Pause-menu softslot equipment | Gameplay/UI feature, not 3D |
| [inu667/tmc](https://github.com/inu667/tmc) | Early GPU/PPU experimental compositor, macros | Do not replace modern GPU pipeline with June prototype |
| [ShroomKing/tmc](https://github.com/ShroomKing/tmc) | Audio mixer, reverb and stereo controls | Not relevant to 3D |
| [DrDecki/tmc-vita](https://github.com/DrDecki/tmc-vita) | Vita ARM, framebuffer and offline build | Handheld ideas, but Vita-specific GPU/runtime; no portable 3D bridge fix |
| [leonelavelarv-debug/tmc](https://github.com/leonelavelarv-debug/tmc) | RG35XX framebuffers, evdev and ARM controls | Platform-specific, not Android SDL GPU |
| [crashware/tmc_port](https://github.com/crashware/tmc_port) | Earlier macOS/build and cutscene options | Already superseded upstream |
| [snnh/tmc_cn](https://github.com/snnh/tmc_cn), [Darth-Koopa/tmc_cn](https://github.com/Darth-Koopa/tmc_cn) | Chinese ROM/UI localization | No current 3D rendering fix |
| [AndrewSheff/minishcap-coop](https://github.com/AndrewSheff/minishcap-coop) | Local co-op additions | Not compatible with native gameplay/state guarantees without a separate feature branch |
| [jacobjordan94/tmc](https://github.com/jacobjordan94/tmc) | #206 launcher option, #207 testing stubs on side branches | Leave prelaunch intact for now |
| [Azyzraissi/tmc](https://github.com/Azyzraissi/tmc) | Upstream pinned source at fork HEAD | No independent patches |
| [lorencouse/tmc](https://github.com/lorencouse/tmc) | Suspend/resume on quit; ROM memory optimizations | Possible *future* mobile lifecycle improvement, but changes save semantics; defer |
| [alfredoxee4/tmc](https://github.com/alfredoxee4/tmc) | Inaccessible recent commit listing | Not verified; no claims of fixes |
| [leonelavelarv-debug/tmc](https://github.com/leonelavelarv-debug/tmc) | Dedicated single-screen device renderer | Platform-specific, not ready for SDL Android |

## Integration policy

1. Keep the user's confirmed-working PR #219 visibility behaviour.
2. Use native 2D sprite placement, BG priority and collision as authoritative,
   especially under bridges and at jump-off edges.
3. Keep the one-tile default; forbid globally promoting wide connected cliffs.
4. Do not draw fake top-map roofs over plaza paths; do not dither bridge decks.
5. New PR ports must pass both native 240px and widescreen 576px ROM-free
   voxel scene tests plus the signed ARM64 build, then receive phone validation.
6. Pending synthetic-regression failures must be repaired before offering an APK.

This is a compatibility survey, *not* a claim that all fork gameplay code has
been dynamically exercised. Only ported work that passes Android CI should be
described as built and tested.


## October 9 on-device regression findings

Fresh S24 Ultra screenshots confirmed the PR #210 and early bridge/room passes
did **not** completely fix Hyrule Town artwork or indoor wall reconstruction.
`scripts/android_voxel_scene_fidelity_v2.py` is a follow-up, not a final
visual-fidelity guarantee. Its safeguards:

- Recognize native overhead bridge decks without globally lifting plaza art.
- Keep single-screen Link behind an actually elevated deck via GPU depth.
- Draw only native doorway openings as side-door panels, not their solid
  neighbouring jambs again.
- Treat truly two-row indoor facade artwork as a wall only where both
  native upper-map rows exist; otherwise preserve the one-tile default.
- Render explicitly curated top-map props through a per-pixel silhouette when
  their art is masked instead of extruding a rectangular block.
- Native 2D tiles, movement, jump ledges and PR #219 OAM are untouched.

New on-device checks required: flags, balloons, flower stands, house side doors,
blacksmith's back wall/forge, and Link under Hyrule Town's bridge.
