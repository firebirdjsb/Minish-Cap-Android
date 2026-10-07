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

The preparation script resets the pinned Project Picori submodule and applies the patches in `patches/`.

## ROM/assets

This repository does not contain a Minish Cap ROM. The upstream port validates a user-owned supported ROM. Do not commit ROMs, extracted Nintendo assets, save files, signing keys, or generated APK signing material.

## Build direction

The upstream native build already contains Android-specific xmake logic and an Android Gradle package. The Android deliverable will be restricted to `arm64-v8a` for the phone build rather than carrying emulator/x86 Android ABIs.

The next integration stages are:

1. verify the upstream native Android target against the pinned commit
2. enforce arm64-v8a packaging
3. add an Android document picker for ROM import
4. move saves/config to app-safe storage with import/export
5. tune the touch layout for the S24 Ultra landscape safe area
6. validate audio, suspend/resume and controller hot-plug
7. produce a signed test APK through GitHub Actions
