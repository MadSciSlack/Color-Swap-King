from __future__ import annotations

from pathlib import Path
import re
import zipfile

from bambu_parser import ParsedJob, parse_bambu_3mf
from generic_gcode_parser import parse_generic_gcode


def _find_plate_gcode_files(z: zipfile.ZipFile) -> list[str]:
    plate_re = re.compile(r"^metadata/plate_(\d+)\.gcode$", re.I)
    return [name for name in z.namelist() if plate_re.match(name)]


def detect_format(path: str | Path) -> str:
    path = Path(path)
    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as z:
            if _find_plate_gcode_files(z):
                return "bambu_3mf_gcode"
            return "3mf_unknown"

    if path.suffix.lower() in (".gcode", ".gco", ".g"):
        return "raw_gcode"

    return "unknown"


def parse(path: str | Path) -> ParsedJob:
    fmt = detect_format(path)

    if fmt == "bambu_3mf_gcode":
        return parse_bambu_3mf(path)
    elif fmt == "raw_gcode":
        return parse_generic_gcode(path)
    elif fmt == "3mf_unknown":
        raise ValueError(
            "Selected 3MF archive does not contain 'Metadata/plate_X.gcode'. Ensure this is a sliced Bambu Studio print file."
        )

    raise ValueError(f"Unsupported or unrecognized file format: {fmt}")