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
    origin: str = "unknown"  # Parser intentionally does not guess manual/user-added origin.
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

    def color_swap_list(self, manual_infeed: set[int]) -> list[Transition]:
        """Resolve physical user interactions from the user's manual-infeed map."""
        previous: Optional[int] = None
        result = []
        for event in self.transitions:
            # Prefer the transition's immediately preceding destination when available.
            source = event.source if event.source is not None else previous
            interactions = []
            if source is not None and source in manual_infeed:
                interactions.append(f"Manual Unload #{source}")
            if event.destination in manual_infeed:
                interactions.append(f"Manual Load #{event.destination}")
            event.interactions = interactions
            if interactions:
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

    # slice_info.config is the most useful source because it provides 1-based
    # user-facing filament IDs and detailed material information.
    if "Metadata/slice_info.config" in z.namelist():
        root = ET.fromstring(z.read("Metadata/slice_info.config").decode("utf-8", "replace"))
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

    # plate_1.json gives a useful fallback and cross-check.
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
                filaments[number] = Filament(number=number, color=_parse_color(color))
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
    toolchange_start_line: Optional[int] = None
    explicit_origin = "unknown"

    layer_re = re.compile(r"^\s*;\s*layer\s+#\s*(\d+)", re.I)
    z_re = re.compile(r"^\s*;\s*Z_HEIGHT:\s*([-+]?\d+(?:\.\d+)?)", re.I)
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
            toolchange_start_line = lineno
            explicit_origin = "unknown"
            continue

        # Keep the first tool command inside a CP TOOLCHANGE block.
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

        # Ignore non-toolchange T commands for now. They are typically startup,
        # shutdown, or unrelated printer commands rather than color-swap events.

    # If the first print toolchange was encountered without a known source,
    # infer the initial source from the first destination only when possible.
    # For a prototype we leave source unknown rather than inventing it.
    return transitions


def parse_bambu_3mf(path: str | Path) -> ParsedJob:
    path = Path(path)
    if not zipfile.is_zipfile(path):
        raise ValueError("Not a ZIP/3MF container.")

    with zipfile.ZipFile(path) as z:
        names = set(z.namelist())
        required = {"Metadata/plate_1.gcode"}
        if not required.issubset(names):
            raise ValueError("3MF does not contain Metadata/plate_1.gcode; not recognized as Bambu 3MF G-code.")

        gcode = z.read("Metadata/plate_1.gcode").decode("utf-8", "replace")
        total_layers = None
        m = re.search(r"^;\s*total layer number:\s*(\d+)\s*$", gcode, re.I | re.M)
        if m:
            total_layers = int(m.group(1))

        filaments = _parse_filaments(z)
        transitions = _parse_gcode(gcode, total_layers)
        warnings = []
        if not filaments:
            warnings.append("No filament definitions were found in Bambu metadata.")
        if any(t.source is None for t in transitions):
            warnings.append("One or more transition sources are unknown; the prototype does not infer them from startup commands.")

        return ParsedJob(
            format="bambu_3mf_gcode",
            source_file=str(path),
            total_layers=total_layers,
            filaments=filaments,
            transitions=transitions,
            warnings=warnings,
        )


def detect_format(path: str | Path) -> str:
    path = Path(path)
    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as z:
            names = set(z.namelist())
            if "Metadata/plate_1.gcode" in names:
                return "bambu_3mf_gcode"
            return "3mf_unknown"
    return "unknown"


def parse(path: str | Path) -> ParsedJob:
    fmt = detect_format(path)
    if fmt == "bambu_3mf_gcode":
        return parse_bambu_3mf(path)
    raise ValueError(f"Unsupported input format: {fmt}")


def to_dict(job: ParsedJob) -> dict:
    return asdict(job)
