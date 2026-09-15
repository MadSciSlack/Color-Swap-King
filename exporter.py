from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Set


def parse_layer_range(range_str: str, max_layer: int = 999999) -> Optional[Set[int]]:
    """Parses layer range strings (e.g., '1-50', '5, 10-12', '100-') into a set of layer numbers.
    Returns None if the filter string is empty or invalid (meaning 'all layers').
    """
    if not range_str or not range_str.strip():
        return None

    layers = set()
    parts = range_str.replace(" ", "").split(",")

    for part in parts:
        if not part:
            continue
        if "-" in part:
            sub = part.split("-")
            if len(sub) == 2:
                start_str, end_str = sub[0], sub[1]
                start = int(start_str) if start_str.isdigit() else 1
                end = int(end_str) if end_str.isdigit() else max_layer
                if start <= end:
                    layers.update(range(start, end + 1))
        elif part.isdigit():
            layers.add(int(part))

    return layers if layers else None


def normalize_hex_color(raw_color: Optional[str]) -> str:
    """Normalizes Bambu/3MF hex color strings into standard 6-character hex (#RRGGBB)."""
    if not raw_color:
        return "#808080"
    
    raw = str(raw_color).strip().lstrip("#").upper()
    if len(raw) == 8:
        if raw.endswith("FF"):
            clean_hex = raw[:6]
        elif raw.startswith("FF"):
            clean_hex = raw[2:]
        else:
            r, g, b = raw[0:2], raw[2:4], raw[4:6]
            clean_hex = f"{b}{g}{r}"
    elif len(raw) == 6:
        clean_hex = raw
    else:
        clean_hex = "808080"
        
    return f"#{clean_hex}"


@dataclass
class ChecklistConfig:
    title: str = "Color Swap Execution Checklist"
    font_size: str = "13px"
    columns: int = 2  # Supports 1 to 10 columns
    show_sequence: bool = True
    show_z_height: bool = True
    show_dotted_borders: bool = True
    show_filament_legend: bool = True
    layer_range_str: str = ""  # e.g. "1-50" or "10, 15-30"


class HTMLChecklistExporter:

    def __init__(self, job, events, config: Optional[ChecklistConfig] = None):
        self.job = job
        self.raw_events = events
        self.config = config or ChecklistConfig()

    def _build_legend_html(self) -> str:
        if not self.config.show_filament_legend or not self.job or not self.job.filaments:
            return ""

        items_html = ""
        for fil in self.job.filaments:
            hex_color = normalize_hex_color(fil.color)
            type_str = f" ({fil.filament_type})" if fil.filament_type else ""
            items_html += f"""
            <div class="legend-item">
                <span class="swatch" style="background-color: {hex_color};"></span>
                <span><b>#{fil.number}</b>{type_str}</span>
            </div>
            """

        return f"""
        <div class="legend-box">
            <div class="legend-title">Filament Legend</div>
            <div class="legend-grid">
                {items_html}
            </div>
        </div>
        """

    def generate_html(self) -> str:
        filename = Path(self.job.source_file).name if self.job else "Unknown"
        cols = max(1, min(self.config.columns, 10))

        # Filter events by specified layer range
        max_layer = self.job.total_layers if (self.job and self.job.total_layers) else 999999
        allowed_layers = parse_layer_range(self.config.layer_range_str, max_layer)

        filtered_events = [
            e for e in self.raw_events
            if allowed_layers is None or (e.layer is not None and e.layer in allowed_layers)
        ]

        cards_html = ""
        for e in filtered_events:
            z_info = (
                f'<span class="meta-item"><b>Z:</b> {e.z_height:.2f}mm</span>'
                if self.config.show_z_height and e.z_height is not None
                else ""
            )
            seq_info = (
                f'<span class="seq-badge">#{e.sequence}</span>'
                if self.config.show_sequence
                else ""
            )
            src_str = f"#{e.source}" if e.source is not None else "Start"
            actions = ", ".join(e.interactions)

            cards_html += f"""
            <div class="swap-card">
                <div class="card-left">
                    <input type="checkbox" class="chk">
                    {seq_info}
                    <span class="layer-badge">L{e.layer or '?'}</span>
                </div>
                <div class="card-body">
                    <div class="swap-path">F{src_str} &rarr; #{e.destination} {z_info}</div>
                    <div class="action-text">{actions}</div>
                </div>
            </div>
            """

        grid_css = f"grid-template-columns: repeat({cols}, 1fr);"
        border_css = (
            "border-right: 1px dotted #a0a0a0;"
            if self.config.show_dotted_borders and cols > 1
            else ""
        )

        range_label = (
            f" | <b>Layer Filter:</b> {self.config.layer_range_str.strip()}"
            if self.config.layer_range_str.strip()
            else ""
        )

        legend_html = self._build_legend_html()

        return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>{self.config.title}</title>
    <style>
        * {{ box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif;
            font-size: {self.config.font_size};
            margin: 16px;
            color: #111;
        }}
        .header {{
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            border-bottom: 2px solid #333;
            padding-bottom: 8px;
            margin-bottom: 12px;
            gap: 16px;
        }}
        .header-info {{ flex: 1; }}
        .header h2 {{ margin: 0 0 4px 0; font-size: 1.3em; }}
        .header p {{ margin: 0; color: #555; font-size: 0.9em; }}
        
        /* Filament Legend Styling */
        .legend-box {{
            border: 1px solid #ccc;
            border-radius: 4px;
            padding: 6px 10px;
            background: #fafafa;
            min-width: 180px;
        }}
        .legend-title {{
            font-size: 0.8em;
            font-weight: bold;
            text-transform: uppercase;
            color: #666;
            margin-bottom: 4px;
            border-bottom: 1px solid #e0e0e0;
            padding-bottom: 2px;
        }}
        .legend-grid {{
            display: flex;
            flex-wrap: wrap;
            gap: 6px 12px;
        }}
        .legend-item {{
            display: flex;
            align-items: center;
            gap: 5px;
            font-size: 0.85em;
        }}
        .swatch {{
            display: inline-block;
            width: 12px;
            height: 12px;
            border: 1px solid #333;
            border-radius: 2px;
        }}

        .grid-container {{
            display: grid;
            {grid_css}
            gap: 8px 12px;
        }}
        
        .swap-card {{
            display: flex;
            align-items: center;
            padding: 6px 8px;
            border-bottom: 1px solid #eee;
            {border_css}
            page-break-inside: avoid;
        }}
        
        .card-left {{
            display: flex;
            align-items: center;
            gap: 6px;
            margin-right: 10px;
        }}
        .chk {{ transform: scale(1.2); cursor: pointer; }}
        .seq-badge {{
            font-weight: bold;
            background: #e0e0e0;
            padding: 2px 5px;
            border-radius: 3px;
            font-size: 0.85em;
        }}
        .layer-badge {{
            font-weight: bold;
            color: #333;
            font-size: 0.9em;
        }}
        
        .card-body {{ flex: 1; }}
        .swap-path {{ font-size: 0.85em; color: #444; }}
        .meta-item {{ margin-left: 6px; color: #666; }}
        .action-text {{ font-weight: bold; color: #000; font-size: 0.95em; }}

        @media print {{
            body {{ margin: 0; }}
            .grid-container {{ gap: 4px 8px; }}
            .legend-box {{ background: #fff; }}
        }}
    </style>
</head>
<body>
    <div class="header">
        <div class="header-info">
            <h2>{self.config.title}</h2>
            <p><b>File:</b> {filename} | <b>Total Layers:</b> {self.job.total_layers or '?'} | <b>Exported Swaps:</b> {len(filtered_events)}{range_label}</p>
        </div>
        {legend_html}
    </div>
    <div class="grid-container">
        {cards_html}
    </div>
</body>
</html>
"""