# Android build notes

## Current target

Primary device: Samsung Galaxy S24 Ultra.

The build is intentionally phone-first:

- arm64-v8a
- landscape
- one SDL gameplay surface
- touch controls drawn over the gameplay surface
- immersive fullscreen
- display-cutout support
- physical controllers remain supported through SDL3

## Prepare source

```bash
git clone --recurse-submodules https://github.com/firebirdjsb/Minish-Cap-Android.git
cd Minish-Cap-Android
git checkout android-s24-single-screen
./scripts/prepare_android.sh
```

The preparation script resets the pinned Project Picori submodule and overlays the phone-specific files from `overrides/`. This avoids fragile patch hunks while the upstream commit is pinned.

## ROM/assets

This repository does not contain a Minish Cap ROM. The upstream port validates a user-owned supported ROM. Do not commit ROMs, extracted Nintendo assets, save files, signing keys, or generated APK signing material.

## Build direction

The upstream native build already contains Android-specific xmake logic and an Android Gradle package. The Android deliverable will be restricted to `arm64-v8a` for the phone build rather than carrying emulator/x86 Android ABIs.

The next integration stages are:

1. verify the upstream native Android target against the pinned commit
2. enforce arm64-v8a packaging
3. validate the existing SDL Android document picker for ROM import
4. add user-facing save import/export (runtime saves already live in Android app storage)
5. tune the touch layout for the S24 Ultra landscape safe area
6. validate audio, suspend/resume and controller hot-plug
7. produce a signed test APK through GitHub Actions


## Android runtime storage

Project Picori already contains Android-specific runtime handling. On Android it changes the working directory to the app-specific external files directory when writable, with a private app-storage fallback. That means `config.json`, `tmc.sav`, extracted assets, quicksaves and bug reports do not attempt to write beside the APK.

The existing pre-launch ROM picker uses SDL3's Android Storage Access Framework support, accepts a user-selected `.gba` file through a `content://` URI, validates it by hash, and copies a valid ROM into the app data directory as `baserom.gba`. The APK therefore does **not** need storage-wide permissions and never bundles the ROM.
