#!/usr/bin/env python3
"""Compile a ROM-free tour of the actual prepared renderer at both widths."""
import argparse
import os
from pathlib import Path
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--include-dir", action="append", default=[])
parser.add_argument("--package-root", action="append", default=[])
parser.add_argument("--sanitize", action="store_true")
args = parser.parse_args()
includes = list(args.include_dir)
package_roots = [*args.package_root, os.environ.get("XMAKE_GLOBALDIR", ""),
                 str(Path.home() / ".xmake"), str(root / ".xmake-cache")]
for package_root in dict.fromkeys(package_roots):
    if not package_root or not Path(package_root).is_dir():
        continue
    files = subprocess.run(["rg", "--files", "--hidden", package_root,
                            "-g", "SDL.h", "-g", "json.hpp", "-g", "png.h", "-g", "zlib.h"],
                           text=True, capture_output=True, check=False).stdout.splitlines()
    for name in files:
        path = Path(name)
        includes.append(str(path.parent.parent if path.parent.name in ("SDL3", "nlohmann") else path.parent))

with tempfile.TemporaryDirectory(prefix="voxel-scene-") as directory:
    temporary = Path(directory)
    for name in ("voxel.vert", "voxel.frag"):
        data = (root / "upstream/tmc/port/shaders/build" / (name + ".spv")).read_bytes()
        (temporary / (name + ".spv.h")).write_text(",".join(str(b) for b in data), encoding="utf-8")
    dirs = [temporary, root / "upstream/tmc", root / "upstream/tmc/include",
            root / "upstream/tmc/port", root / "upstream/tmc/port/ppu/include", *includes]
    for width in (240, 576):
        output = temporary / f"tour-{width}"
        command = [os.environ.get("CXX", "g++"), "-std=c++20", "-O1", "-g",
                   "-ffunction-sections", "-fdata-sections", "-Wl,--gc-sections",
                   "-DPC_PORT", "-DTMC_GPU_RENDERER", "-DUSA", "-DENGLISH",
                   f"-DMODE1_GBA_WIDTH={width}"]
        if args.sanitize:
            command += ["-fsanitize=address,undefined", "-fno-omit-frame-pointer"]
        command += [f"-I{path}" for path in dict.fromkeys(map(str, dirs))]
        command += [str(root / "tests/voxel_scene_test.cpp"), "-o", str(output)]
        subprocess.run(command, check=True, cwd=root)
        subprocess.run([str(output)], check=True, cwd=temporary)
        print(f"Native scene tour passed: MODE1_GBA_WIDTH={width}", flush=True)
