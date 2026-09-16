from __future__ import annotations

from pathlib import Path
from typing import Optional
import re

# Import data models from bambu_parser to maintain exact API contract compatibility
from bambu_parser import Filament, Transition, ParsedJob, _parse_color


def _parse_filaments_from_gcode(text: str) -> list[Filament]:
    """
    Extract filament metadata embedded in ASCII G-code comments.
    Slicers output these in semicolon header or config blocks (e.g. ; filament_colour = #FF0000;#00FF00).
    """
    filaments: dict[int, Filament] = {}

    colors: list[str] = []
    types: list[str] = []

    # Regex patterns for Orca/Bambu/Prusa exported raw G-code comments
    color_match = re.search(r"^\s*;\s*filament_colour\s*=\s*(.+)$", text, re.I | re.M)
    if color_match:
        colors = [c.strip() for c in color_match.group(1).split(";")]

    type_match = re.search(r"^\s*;\s*filament_type\s*=\s*(.+)$", text, re.I | re.M)
    if type_match:
        types = [t.strip() for t in type_match.group(1).split(";")]

    # Fallback to single/legacy comment declarations if array fields aren't present
    if not colors:
        single_colors = re.findall(r"^\s*;\s*filament_colour_(\d+)\s*=\s*(.+)$", text, re.I | re.M)
        if single_colors:
            colors = [c[1].strip() for c in sorted(single_colors, key=lambda x: int(x[0]))]

    max_filaments = max(len(colors), len(types))

    for idx in range(max_filaments):
        num = idx + 1
        c = colors[idx] if idx < len(colors) else None
        t = types[idx] if idx < len(types) else None

        filaments[num] = Filament(
            number=num,
            color=_parse_color(c),
            filament_type=t if t else None,
            tray_info_idx=None
        )

    return [filaments[n] for n in sorted(filaments)]


def parse_generic_gcode(path: str | Path) -> ParsedJob:
    """Parse flat raw ASCII .gcode output."""
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"File not found: {path}")

    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()

    # Extract Total Layer Count
    total_layers: Optional[int] = None
    layer_count_match = re.search(
        r"^\s*;\s*(?:total layer number|total layers count|layer_count)\s*[:=]\s*(\d+)",
        text,
        re.I | re.M
    )
    if layer_count_match:
        total_layers = int(layer_count_match.group(1))

    # Parse Filaments
    filaments = _parse_filaments_from_gcode(text)

    # State tracking for execution stream
    transitions: list[Transition] = []
    current_layer: Optional[int] = None
    current_z: Optional[float] = None
    current_filament: Optional[int] = None
    pending_toolchange = False
    toolchange_seq = 0
    explicit_origin = "unknown"

    # Line Regex Patterns
    layer_re = re.compile(
        r"^\s*;\s*(?:layer\s+#|LAYER[:\s]+|object\s+ids\s+of\s+layer\s+|AFTER_LAYER_CHANGE\s+)(\d+)",
        re.I,
    )
    z_re = re.compile(
        r"^\s*;\s*(?:Z_HEIGHT|Z):\s*([-+]?\d+(?:\.\d+)?)", re.I
    )
    toolchange_re = re.compile(
        r"^\s*;\s*(?:CP\s+TOOLCHANGE\s+START|TOOLCHANGE|toolchange\s+start)\s*$", re.I
    )
    tool_re = re.compile(r"^\s*T(\d+)\s*$", re.I)

    for lineno, line in enumerate(lines, 1):
        m = layer_re.match(line)
        if m:
            current_layer = int(m.group(1))

        m = z_re.match(line)
        if m:
            current_z = float(m.group(1))

        # Check for toolchange start comments or direct 'T' command execution
        if toolchange_re.match(line):
            pending_toolchange = True
            explicit_origin = "unknown"
            continue

        # Process Tool Change Command (e.g. T0, T1...)
        m = tool_re.match(line)
        if m:
            raw_tool = int(m.group(1))
            destination = raw_tool + 1  # 1-indexed conversion matching bambu_parser logic

            # Create transition if the target filament changes
            if current_filament != destination:
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

    warnings: list[str] = []

    if not filaments:
        warnings.append("No filament definitions were extracted from G-code comments.")
    if any(t.source is None for t in transitions):
        warnings.append(
            "One or more transition sources are unknown; initial filament state was inferred after first explicit swap."
        )

    return ParsedJob(
        format="raw_gcode",
        source_file=str(path),
        total_layers=total_layers,
        filaments=filaments,
        transitions=transitions,
        warnings=warnings,
    )