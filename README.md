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

It is tracked as the `upstream/tmc` git submodule. Android-specific changes live in this repository as patches and wrapper tooling so upstream Project Picori updates can be merged without maintaining a permanently diverged copy.

## Legal

Project Picori is GPL-3.0 and is based on the zeldaret Minish Cap decompilation. This repository does not distribute a Minish Cap ROM or Nintendo-owned game assets. A legitimately owned supported ROM is required by the upstream project.

## Status

Initial Android/S24 Ultra integration branch is being established. The first target is a sideloadable `arm64-v8a` APK with a true single-screen landscape presentation and overlaid controls.
