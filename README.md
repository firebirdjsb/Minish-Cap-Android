# Minish Cap Android

Android-focused single-screen port of Project Picori / The Legend of Zelda: The Minish Cap native port.

## Goal

This repository targets modern Android phones, with the Samsung Galaxy S24 Ultra as the primary reference device:

- native ARM64 Android build
- one gameplay screen filling the phone display
- transparent touch controls over the game
- floating analog stick or GBA-style D-pad
- A / B / R face cluster plus L / Start / Select
- automatic touch-overlay hiding when a physical controller is used
- immersive landscape fullscreen
- display-cutout / rounded-corner safe handling
- SDL3 controller support
- Android-safe save/config storage
- ROM import from user-owned supported Minish Cap ROMs
- no ROM or Nintendo game data distributed in this repository

## Upstream

The game/decomp/native-port code comes from:

- https://github.com/999sian/tmc

It is tracked as the `upstream/tmc` git submodule. Android-specific files live under `overrides/` and are applied by `scripts/prepare_android.sh`, so upstream Project Picori updates can be adopted without maintaining a permanently diverged source copy.

## Legal

Project Picori is GPL-3.0 and is based on the zeldaret Minish Cap decompilation. This repository does not distribute a Minish Cap ROM or Nintendo-owned game assets. A legitimately owned supported ROM is required by the upstream project.

## Status

The ARM64 Android build is now passing in CI. The current test APK is a true single-screen landscape build with overlaid touch controls, immersive fullscreen, native Android ROM selection, and Android save import/export.
