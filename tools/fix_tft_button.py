"""Repair a packaging omission in TFT_eSPI 2.5.43 before PlatformIO builds it."""

import os
import json
from pathlib import Path

Import("env")

# PlatformIO may be directed to an isolated libdeps cache by the build
# environment.  Include the active environment name in both cases.
libdeps_dir = os.environ.get("PLATFORMIO_LIBDEPS_DIR") or env.subst("$PROJECT_LIBDEPS_DIR")
extensions_dir = Path(libdeps_dir) / env["PIOENV"] / "TFT_eSPI" / "Extensions"
include_line = '#include "../TFT_eSPI.h"\n'

for source_file in extensions_dir.glob("*.cpp"):
    contents = source_file.read_text(encoding="utf-8")
    if include_line not in contents:
        source_file.write_text(include_line + contents, encoding="utf-8")

# The extension files are textually included by TFT_eSPI.cpp.  PlatformIO's
# default recursive source discovery also compiles them as standalone units,
# which is invalid and later causes duplicate symbols.  Exclude that folder.
manifest_path = extensions_dir.parent / "library.json"
if manifest_path.exists():
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    build = manifest.setdefault("build", {})
    source_filter = ["-<*>", "+<TFT_eSPI.cpp>"]
    if build.get("srcFilter") != source_filter:
        build["srcFilter"] = source_filter
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
