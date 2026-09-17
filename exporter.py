from dataclasses import dataclass
from pathlib import Path
import math
from typing import List, Optional, Set

from PySide6.QtCore import QMarginsF, QRectF
from PySide6.QtGui import QFont, QPageLayout, QPageSize, QPainter, QPdfWriter, QTextDocument


def parse_layer_range(range_str: str, max_layer: int = 999999) -> Optional[Set[int]]:
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
            return f"#{b}{g}{r}"
    elif len(raw) == 6:
        clean_hex = raw
    else:
        clean_hex = "808080"
        
    return f"#{clean_hex}"


@dataclass
class ChecklistConfig:
    title: str = "Color Swap Checklist"
    font_size: str = "10pt"
    columns: int = 4
    rows_per_page: int = 19
    show_sequence: bool = True
    show_z_height: bool = False
    show_dotted_borders: bool = True
    show_filament_legend: bool = True
    layer_range_str: str = ""


class HTMLChecklistExporter:

    def __init__(
        self,
        job,
        events,
        config: Optional[ChecklistConfig] = None,
        hide_header_file_info: bool = False,
        hide_legend: bool = False,
    ):
        self.job = job
        self.raw_events = events
        self.config = config or ChecklistConfig()
        self.hide_header_file_info = hide_header_file_info
        self.hide_legend = hide_legend

    def _build_legend_html(self) -> str:
        if (
            self.hide_legend
            or not self.config.show_filament_legend
            or not self.job
            or not self.job.filaments
        ):
            return ""

        items_html = ""
        for fil in self.job.filaments:
            hex_color = normalize_hex_color(fil.color)
            type_str = f" ({fil.filament_type})" if fil.filament_type else ""
            items_html += f"""
            <td style="padding: 1pt 4pt 1pt 0pt; white-space: nowrap;">
                <span style="font-size: 9.5pt; color: {hex_color};">&#9632;</span>
                <span style="font-size: 8pt;"><b>#{fil.number}</b>{type_str}</span>
            </td>
            """

        return f"""
        <table border="0" cellspacing="0" cellpadding="0" style="border: 0.75pt solid #ccc; background-color: #fafafa; padding: 3pt;">
            <tr>
                <td colspan="100" style="font-size: 7pt; font-weight: bold; color: #666; border-bottom: 0.75pt solid #e0e0e0; padding-bottom: 1pt;">
                    FILAMENT LEGEND
                </td>
            </tr>
            <tr>
                {items_html}
            </tr>
        </table>
        """

    def generate_html(self, events_override: Optional[List] = None) -> str:
        filename = Path(self.job.source_file).name if self.job else "Unknown"
        cols = max(1, min(self.config.columns, 10))

        if events_override is not None:
            filtered_events = events_override
        else:
            max_layer = self.job.total_layers if (self.job and self.job.total_layers) else 999999
            allowed_layers = parse_layer_range(self.config.layer_range_str, max_layer)
            filtered_events = [
                e for e in self.raw_events
                if allowed_layers is None or (e.layer is not None and e.layer in allowed_layers)
            ]

        col_width_pct = int(100 / cols)
        rows_html = ""

        for i in range(0, len(filtered_events), cols):
            chunk = filtered_events[i : i + cols]
            row_cells = ""

            for col_idx, e in enumerate(chunk):
                z_info = (
                    f' | <b>Z:</b> {e.z_height:.2f}mm'
                    if self.config.show_z_height and e.z_height is not None
                    else ""
                )
                seq_info = (
                    f'<span style="background-color: #e0e0e0; padding: 1pt 2.5pt; font-weight: bold; font-size: 7.5pt;">#{e.sequence}</span> '
                    if self.config.show_sequence
                    else ""
                )
                src_str = f"#{e.source}" if e.source is not None else "Start"
                actions = ", ".join(e.interactions)

                border_right = (
                    "border-right: 1px dotted #a0a0a0;"
                    if (self.config.show_dotted_borders and col_idx < len(chunk) - 1)
                    else ""
                )

                row_cells += f"""
                <td width="{col_width_pct}%" valign="top" style="padding: 5pt 4pt; border-bottom: 1px solid #c0c0c0; {border_right}">
                    <table width="100%" border="0" cellspacing="0" cellpadding="0">
                        <tr>
                            <td width="18" valign="top" style="font-size: 13pt; line-height: 10pt; padding-top: 0pt;">
                                &#9633;
                            </td>
                            <td valign="top">
                                <div style="font-size: 8.5pt;">{seq_info}<b>L{e.layer or '?'}</b></div>
                                <div style="font-size: 7.5pt; color: #444; margin-top: 1pt;">F{src_str} &rarr; #{e.destination}{z_info}</div>
                                <div style="font-size: 8.5pt; font-weight: bold; color: #000; margin-top: 1pt;">{actions}</div>
                            </td>
                        </tr>
                    </table>
                </td>
                """

            while len(chunk) < cols:
                border_right = (
                    "border-right: 1px dotted #a0a0a0;"
                    if (self.config.show_dotted_borders and len(chunk) - 1 < cols - 1)
                    else ""
                )
                row_cells += f'<td width="{col_width_pct}%" style="border-bottom: 1px solid #c0c0c0; {border_right}"></td>'
                chunk.append(None)

            rows_html += f"<tr>{row_cells}</tr>"

        range_label = (
            f" | <b>Layer Filter:</b> {self.config.layer_range_str.strip()}"
            if self.config.layer_range_str.strip()
            else ""
        )

        legend_html = self._build_legend_html()

        file_meta_html = ""
        if not self.hide_header_file_info:
            file_meta_html = f"""
            <div style="color: #444; font-size: 8pt; white-space: nowrap; margin-top: 2pt;">
                <b>File:</b> {filename} &nbsp;|&nbsp; <b>Total Layers:</b> {self.job.total_layers or '?'} &nbsp;|&nbsp; <b>Exported Swaps:</b> {len(filtered_events)}{range_label}
            </div>
            """

        return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>{self.config.title}</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            font-size: {self.config.font_size};
            margin: 0;
            color: #111;
        }}
    </style>
</head>
<body>
    <table width="100%" border="0" cellspacing="0" cellpadding="0" style="border-bottom: 2px solid #333; padding-bottom: 4pt; margin-bottom: 6pt;">
        <tr>
            <td valign="top" style="padding-top: 0pt;">
                <h1 style="margin: 0; font-size: 14pt; white-space: nowrap;">{self.config.title}</h1>
                {file_meta_html}
            </td>
            <td align="right" valign="top" style="padding-top: 0pt;">
                {legend_html}
            </td>
        </tr>
    </table>

    <table width="100%" border="0" cellspacing="0" cellpadding="0">
        {rows_html}
    </table>
</body>
</html>
"""


class PDFChecklistExporter:

    def __init__(self, job, events, config: Optional[ChecklistConfig] = None):
        self.job = job
        self.events = events
        self.config = config or ChecklistConfig()

    def export_pdf(self, output_path: str | Path) -> bool:
        max_layer = self.job.total_layers if (self.job and self.job.total_layers) else 999999
        allowed_layers = parse_layer_range(self.config.layer_range_str, max_layer)
        filtered_events = [
            e for e in self.events
            if allowed_layers is None or (e.layer is not None and e.layer in allowed_layers)
        ]

        cols = max(1, min(self.config.columns, 10))
        items_per_page = cols * self.config.rows_per_page
        total_pages = math.ceil(len(filtered_events) / items_per_page) or 1

        writer = QPdfWriter(str(output_path))
        writer.setPageSize(QPageSize(QPageSize.Letter))
        writer.setPageOrientation(QPageLayout.Portrait)
        writer.setResolution(96)

        layout = writer.pageLayout()
        layout.setMargins(QMarginsF(0, 0, 0, 0))
        writer.setPageLayout(layout)

        painter = QPainter(writer)
        filename = Path(self.job.source_file).name if self.job else "Unknown"

        margin_x = 35
        margin_top = 45
        margin_bottom = 45
        
        page_width = writer.width()
        page_height = writer.height()
        printable_width = page_width - (margin_x * 2)

        for page_idx in range(total_pages):
            if page_idx > 0:
                writer.newPage()

            chunk_start = page_idx * items_per_page
            page_events = filtered_events[chunk_start : chunk_start + items_per_page]

            pdf_config = ChecklistConfig(
                title=self.config.title,
                font_size="8.5pt",
                columns=self.config.columns,
                rows_per_page=self.config.rows_per_page,
                show_sequence=self.config.show_sequence,
                show_z_height=self.config.show_z_height,
                show_dotted_borders=self.config.show_dotted_borders,
                show_filament_legend=self.config.show_filament_legend,
                layer_range_str=self.config.layer_range_str,
            )

            html_exporter = HTMLChecklistExporter(
                self.job,
                self.events,
                pdf_config,
                hide_header_file_info=True,
                hide_legend=False,  # Keep legend visible on all pages
            )
            html_content = html_exporter.generate_html(events_override=page_events)

            doc = QTextDocument()
            doc.setDocumentMargin(0)
            doc.setTextWidth(printable_width)
            doc.setHtml(html_content)

            painter.save()
            painter.translate(margin_x, margin_top)
            doc.drawContents(painter)
            painter.restore()

            # Footer Rendering
            footer_text = (
                f"File: {filename}  |  "
                f"Total Layers: {self.job.total_layers or '?'}  |  "
                f"Exported Swaps: {len(filtered_events)}"
            )
            if self.config.layer_range_str.strip():
                footer_text += f"  |  Layer Filter: {self.config.layer_range_str.strip()}"
            
            page_indicator = f"Page {page_idx + 1} of {total_pages}"

            painter.setFont(QFont("Arial", 8))
            painter.setPen(0x555555)

            footer_y = page_height - margin_bottom + 10

            # Left Footer
            painter.drawText(
                QRectF(margin_x, footer_y, printable_width - 80, 15),
                int(0x0001),  # AlignLeft
                footer_text,
            )
            # Right Footer
            painter.drawText(
                QRectF(margin_x + printable_width - 100, footer_y, 100, 15),
                int(0x0002),  # AlignRight
                page_indicator,
            )

        painter.end()
        return True