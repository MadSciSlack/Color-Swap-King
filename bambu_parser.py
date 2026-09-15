from __future__ import annotations

from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional
import json
import re
import zipfile
import xml.etree.ElementTree as ET


@dataclass
class Filament:
    number: int
    color: Optional[str] = None
    filament_type: Optional[str] = None
    tray_info_idx: Optional[str] = None


@dataclass
class Transition:
    sequence: int
    layer: Optional[int]
    z_height: Optional[float]
    source: Optional[int]
    destination: int
    raw_tool: int
    line_number: int
    origin: str = "unknown"
    raw_marker: str = "CP TOOLCHANGE START"
    interactions: list[str] = field(default_factory=list)


@dataclass
class ParsedJob:
    format: str
    source_file: str
    total_layers: Optional[int]
    filaments: list[Filament]
    transitions: list[Transition]
    warnings: list[str] = field(default_factory=list)

    def color_swap_list(
        self, manual_infeed: set[int], show_all: bool = False
    ) -> list[Transition]:
        """Resolve physical user interactions and classify actions as Manual or Automatic."""
        previous: Optional[int] = None
        result = []

        for event in self.transitions:
            source = event.source if event.source is not None else previous

            # Unload action
            if source is not None:
                unload_type = (
                    "Manual" if source in manual_infeed else "Automatic"
                )
                unload_str = f"{unload_type} Unload"
            else:
                unload_str = "Unknown Unload"

            # Load action
            load_type = (
                "Manual" if event.destination in manual_infeed else "Automatic"
            )
            load_str = f"{load_type} Load"

            event.interactions = [unload_str, load_str]

            # Filter logic
            is_manual_event = (
                source in manual_infeed if source is not None else False
            ) or (event.destination in manual_infeed)

            if show_all or is_manual_event:
                result.append(event)

            previous = event.destination

        return result


def _parse_color(s: Optional[str]) -> Optional[str]:
    if not s:
        return None
    return s.upper()


def _read_json(z: zipfile.ZipFile, name: str) -> dict:
    return json.loads(z.read(name).decode("utf-8", "replace"))


def _parse_filaments(z: zipfile.ZipFile) -> list[Filament]:
    filaments: dict[int, Filament] = {}

    if "Metadata/slice_info.config" in z.namelist():
        root = ET.fromstring(
            z.read("Metadata/slice_info.config").decode("utf-8", "replace")
        )
        for node in root.iter("filament"):
            try:
                number = int(node.attrib["id"])
            except (KeyError, ValueError):
                continue
            filaments[number] = Filament(
                number=number,
                color=_parse_color(node.attrib.get("color")),
                filament_type=node.attrib.get("type"),
                tray_info_idx=node.attrib.get("tray_info_idx"),
            )

    if "Metadata/plate_1.json" in z.namelist():
        data = _read_json(z, "Metadata/plate_1.json")
        ids = data.get("filament_ids", [])
        colors = data.get("filament_colors", [])
        for raw_id, color in zip(ids, colors):
            try:
                number = int(raw_id) + 1
            except (TypeError, ValueError):
                continue
            if number not in filaments:
                filaments[number] = Filament(
                    number=number, color=_parse_color(color)
                )
            elif not filaments[number].color:
                filaments[number].color = _parse_color(color)

    return [filaments[n] for n in sorted(filaments)]


def _parse_gcode(text: str, total_layers: Optional[int]) -> list[Transition]:
    lines = text.splitlines()
    transitions: list[Transition] = []
    current_layer: Optional[int] = None
    current_z: Optional[float] = None
    current_filament: Optional[int] = None
    pending_toolchange = False
    toolchange_seq = 0
    explicit_origin = "unknown"

    layer_re = re.compile(
        r"^\s*;\s*(?:layer\s+#|LAYER[:\s]+|object\s+ids\s+of\s+layer\s+)(\d+)",
        re.I,
    )
    z_re = re.compile(
        r"^\s*;\s*(?:Z_HEIGHT|Z):\s*([-+]?\d+(?:\.\d+)?)", re.I
    )
    toolchange_re = re.compile(r"^\s*;\s*CP\s+TOOLCHANGE\s+START\s*$", re.I)
    tool_re = re.compile(r"^\s*T(\d+)\s*$", re.I)

    for lineno, line in enumerate(lines, 1):
        m = layer_re.match(line)
        if m:
            current_layer = int(m.group(1))

        m = z_re.match(line)
        if m:
            current_z = float(m.group(1))

        if toolchange_re.match(line):
            pending_toolchange = True
            explicit_origin = "unknown"
            continue

        if pending_toolchange:
            m = tool_re.match(line)
            if m:
                raw_tool = int(m.group(1))
                destination = raw_tool + 1
                toolchange_seq += 1
                transitions.append(
                    Transition(
                        sequence=toolchange_seq,
                        layer=current_layer,
                        z_height=current_z,
                        source=current_filament,
                        destination=destination,
                        raw_tool=raw_tool,
                        line_number=lineno,
                        origin=explicit_origin,
                    )
                )
                current_filament = destination
                pending_toolchange = False
                continue

    return transitions


def _find_plate_gcode_files(z: zipfile.ZipFile) -> list[str]:
    plate_re = re.compile(r"^metadata/plate_(\d+)\.gcode$", re.I)
    found_plates = []

    for name in z.namelist():
        match = plate_re.match(name)
        if match:
            plate_num = int(match.group(1))
            found_plates.append((plate_num, name))

    found_plates.sort(key=lambda item: item[0])
    return [name for _, name in found_plates]


def detect_format(path: str | Path) -> str:
    path = Path(path)
    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as z:
            if _find_plate_gcode_files(z):
                return "bambu_3mf_gcode"
            return "3mf_unknown"

    if path.suffix.lower() == ".gcode":
        return "raw_gcode"

    return "unknown"


def parse_bambu_3mf(
    path: str | Path, target_plate_path: Optional[str] = None
) -> ParsedJob:
    path = Path(path)
    if not zipfile.is_zipfile(path):
        raise ValueError("Not a ZIP/3MF container.")

    with zipfile.ZipFile(path) as z:
        available_plates = _find_plate_gcode_files(z)

        if not available_plates:
            raise ValueError(
                "3MF archive does not contain any Metadata/plate_X.gcode file; not recognized as Bambu 3MF G-code."
            )

        selected_gcode_file = (
            target_plate_path
            if target_plate_path and target_plate_path in available_plates
            else available_plates[0]
        )

        gcode = z.read(selected_gcode_file).decode("utf-8", "replace")
        total_layers = None
        m = re.search(
            r"^;\s*total layer number:\s*(\d+)\s*$", gcode, re.I | re.M
        )
        if m:
            total_layers = int(m.group(1))

        filaments = _parse_filaments(z)
        transitions = _parse_gcode(gcode, total_layers)
        warnings = []

        if len(available_plates) > 1:
            warnings.append(
                f"Multiple plates found in 3MF container ({len(available_plates)}). Parsed '{selected_gcode_file}'."
            )
        if not filaments:
            warnings.append(
                "No filament definitions were found in Bambu metadata."
            )
        if any(t.source is None for t in transitions):
            warnings.append(
                "One or more transition sources are unknown; the prototype does not infer them from startup commands."
            )

        return ParsedJob(
            format="bambu_3mf_gcode",
            source_file=str(path),
            total_layers=total_layers,
            filaments=filaments,
            transitions=transitions,
            warnings=warnings,
        )


def parse(path: str | Path) -> ParsedJob:
    fmt = detect_format(path)
    if fmt == "bambu_3mf_gcode":
        return parse_bambu_3mf(path)
    elif fmt == "3mf_unknown":
        raise ValueError(
            "Selected 3MF archive does not contain 'Metadata/plate_X.gcode'. Ensure this is a sliced Bambu Studio print file."
        )
    elif fmt == "raw_gcode":
        raise ValueError(
            "Raw G-code parsing is not yet implemented in this prototype."
        )

    raise ValueError(f"Unsupported or unrecognized file format: {fmt}")


def to_dict(job: ParsedJob) -> dict:
    return asdict(job)