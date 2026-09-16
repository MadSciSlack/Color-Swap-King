from pathlib import Path
import sys
import traceback

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QIcon, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

import dispatcher
from exporter import ChecklistConfig, HTMLChecklistExporter, normalize_hex_color


class ExportConfigDialog(QDialog):
    """Modal dialog for configuring export settings (columns, layer ranges, legend, toggles)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Export Checklist Options")
        self.resize(360, 290)

        layout = QFormLayout(self)

        self.spin_cols = QSpinBox()
        self.spin_cols.setRange(1, 10)
        self.spin_cols.setValue(2)

        self.txt_layer_range = QLineEdit()
        self.txt_layer_range.setPlaceholderText("e.g. 1-50, 60, 80-100 (Blank = All)")

        self.chk_seq = QCheckBox("Include Sequence Numbers (#)")
        self.chk_seq.setChecked(True)

        self.chk_z = QCheckBox("Include Z-Height Values")
        self.chk_z.setChecked(True)

        self.chk_dotted = QCheckBox("Dotted Grid Lines Between Columns")
        self.chk_dotted.setChecked(True)

        self.chk_legend = QCheckBox("Include Filament Legend in Header")
        self.chk_legend.setChecked(True)

        layout.addRow("Columns per Row (1-10):", self.spin_cols)
        layout.addRow("Layer Range Filter:", self.txt_layer_range)
        layout.addRow(self.chk_seq)
        layout.addRow(self.chk_z)
        layout.addRow(self.chk_dotted)
        layout.addRow(self.chk_legend)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def get_config(self) -> ChecklistConfig:
        return ChecklistConfig(
            columns=self.spin_cols.value(),
            layer_range_str=self.txt_layer_range.text().strip(),
            show_sequence=self.chk_seq.isChecked(),
            show_z_height=self.chk_z.isChecked(),
            show_dotted_borders=self.chk_dotted.isChecked(),
            show_filament_legend=self.chk_legend.isChecked(),
        )


class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Color Swap King — v0.60")
        self.resize(1100, 700)
        
        # Enables drag & drop directly on the QMainWindow
        self.setAcceptDrops(True)

        self.current_job = None
        self.manual_infeed_ids = set()

        self._init_ui()

    def _init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)

        splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(splitter)

        # --- LEFT PANEL: Controls & Options ---
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)

        # File Controls
        file_box = QGroupBox("File Input")
        file_layout = QVBoxLayout(file_box)

        self.btn_open = QPushButton("Open Sliced File")
        self.btn_open.setFixedHeight(36)
        self.btn_open.clicked.connect(self.open_file_dialog)

        self.lbl_file_status = QLabel(
            "Drag & Drop a .gcode or .3mf file here\nor use the button above."
        )
        self.lbl_file_status.setWordWrap(True)

        file_layout.addWidget(self.btn_open)
        file_layout.addWidget(self.lbl_file_status)
        left_layout.addWidget(file_box)

        # Dynamic Manual Infeed Checkboxes
        self.infeed_box = QGroupBox("Manual Infeed Filaments")
        self.infeed_box_layout = QVBoxLayout(self.infeed_box)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)

        self.scroll_content = QWidget()
        self.scroll_layout = QVBoxLayout(self.scroll_content)

        self.lbl_no_filaments = QLabel("Load a file to detect filaments.")
        self.scroll_layout.addWidget(self.lbl_no_filaments)

        self.scroll.setWidget(self.scroll_content)
        self.infeed_box_layout.addWidget(self.scroll)
        left_layout.addWidget(self.infeed_box)

        # Display Options
        opts_box = QGroupBox("Filters & Actions")
        opts_layout = QVBoxLayout(opts_box)

        self.chk_show_all = QCheckBox("Show Automatic Swaps")
        self.chk_show_all.stateChanged.connect(self.refresh_swap_table)
        opts_layout.addWidget(self.chk_show_all)

        self.btn_export = QPushButton("Export Checklist (HTML)")
        self.btn_export.setFixedHeight(32)
        self.btn_export.clicked.connect(self.export_checklist_html)
        opts_layout.addWidget(self.btn_export)

        left_layout.addWidget(opts_box)

        # Job Summary
        metrics_box = QGroupBox("Job Summary")
        metrics_layout = QVBoxLayout(metrics_box)
        self.lbl_metrics_layers = QLabel("Total Layers: -")
        self.lbl_metrics_swaps = QLabel("Total Transitions: -")
        self.lbl_metrics_manual = QLabel("Manual Interventions: -")

        metrics_layout.addWidget(self.lbl_metrics_layers)
        metrics_layout.addWidget(self.lbl_metrics_swaps)
        metrics_layout.addWidget(self.lbl_metrics_manual)
        left_layout.addWidget(metrics_box)

        left_layout.addStretch()
        splitter.addWidget(left_widget)

        # --- RIGHT PANEL: Execution Table ---
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)

        table_label = QLabel("Color Swap Execution Schedule")
        font = QFont()
        font.setBold(True)
        table_label.setFont(font)
        right_layout.addWidget(table_label)

        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(
            ["Seq", "Layer", "Z Height", "From", "To", "Required Action"]
        )
        self.table.horizontalHeader().setSectionResizeMode(
            5, QHeaderView.Stretch
        )

        right_layout.addWidget(self.table)
        splitter.addWidget(right_widget)

        splitter.setSizes([320, 780])

    # --- RESTORED V0.50 DRAG & DROP HANDLERS ---
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        for url in event.mimeData().urls():
            file_path = Path(url.toLocalFile())
            if file_path.suffix.lower() in [".3mf", ".gcode", ".gco", ".g"]:
                self.load_file(file_path)
                break

    def open_file_dialog(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Sliced Print File",
            "",
            "Supported Files (*.gcode *.3mf);;G-Code Files (*.gcode);;3MF Archives (*.3mf);;All Files (*)",
        )
        if file_path:
            self.load_file(Path(file_path))

    def load_file(self, path: Path):
        try:
            self.current_job = dispatcher.parse(path)
            self.lbl_file_status.setText(f"Loaded: {path.name}")
            self.manual_infeed_ids.clear()

            self.populate_filament_checkboxes()
            self.refresh_swap_table()

        except Exception as err:
            self.lbl_file_status.setText(f"Error: {err}")

    def populate_filament_checkboxes(self):
        while self.scroll_layout.count():
            item = self.scroll_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not self.current_job or not self.current_job.filaments:
            lbl = QLabel("No filament metadata detected.")
            self.scroll_layout.addWidget(lbl)
            return

        for fil in self.current_job.filaments:
            label_text = f"Filament #{fil.number}"
            if fil.filament_type:
                label_text += f" ({fil.filament_type})"

            chk = QCheckBox(label_text)
            chk.setProperty("filament_id", fil.number)
            chk.stateChanged.connect(self.on_filament_toggled)

            # Color Swatch Icon using shared hex normalization
            if fil.color:
                hex_color = normalize_hex_color(fil.color)
                pixmap = QPixmap(14, 14)
                pixmap.fill(QColor(hex_color))
                chk.setIcon(QIcon(pixmap))
                chk.setToolTip(f"Color: {hex_color}")

            self.scroll_layout.addWidget(chk)

        self.scroll_layout.addStretch()

    def on_filament_toggled(self, state):
        chk = self.sender()
        fil_id = chk.property("filament_id")

        if state == 2 or state == Qt.Checked:
            self.manual_infeed_ids.add(fil_id)
        else:
            self.manual_infeed_ids.discard(fil_id)

        self.refresh_swap_table()

    def refresh_swap_table(self):
        if not self.current_job:
            self.table.setRowCount(0)
            self.lbl_metrics_layers.setText("Total Layers: -")
            self.lbl_metrics_swaps.setText("Total Transitions: -")
            self.lbl_metrics_manual.setText("Manual Interventions: -")
            return

        show_all = self.chk_show_all.isChecked()
        events = self.current_job.color_swap_list(
            self.manual_infeed_ids, show_all=show_all
        )

        self.lbl_metrics_layers.setText(
            f"Total Layers: {self.current_job.total_layers or 'Unknown'}"
        )
        self.lbl_metrics_swaps.setText(
            f"Total Transitions: {len(self.current_job.transitions)}"
        )
        self.lbl_metrics_manual.setText(
            f"Manual Interventions: {len(events) if not show_all else len([e for e in self.current_job.transitions if any('Manual' in act for act in e.interactions)])}"
        )

        self.table.setRowCount(len(events))
        for row, event in enumerate(events):
            src_str = (
                f"#{event.source}" if event.source is not None else "Start"
            )
            details = ", ".join(event.interactions)
            z_str = (
                f"{event.z_height:.2f} mm"
                if event.z_height is not None
                else "?"
            )

            self.table.setItem(row, 0, QTableWidgetItem(str(event.sequence)))
            self.table.setItem(
                row, 1, QTableWidgetItem(str(event.layer or "?"))
            )
            self.table.setItem(row, 2, QTableWidgetItem(z_str))
            self.table.setItem(row, 3, QTableWidgetItem(src_str))
            self.table.setItem(
                row, 4, QTableWidgetItem(f"#{event.destination}")
            )

            action_item = QTableWidgetItem(details)
            if "Manual" in details:
                action_item.setBackground(QColor("#fff3cd"))
            self.table.setItem(row, 5, action_item)

    def export_checklist_html(self):
        if not self.current_job:
            return

        dlg = ExportConfigDialog(self)
        if dlg.exec() != QDialog.Accepted:
            return

        config = dlg.get_config()

        show_all = self.chk_show_all.isChecked()
        events = self.current_job.color_swap_list(
            self.manual_infeed_ids, show_all=show_all
        )

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export HTML Checklist",
            "color_swap_checklist.html",
            "HTML Files (*.html)",
        )

        if file_path:
            exporter = HTMLChecklistExporter(self.current_job, events, config)
            html_content = exporter.generate_html()
            Path(file_path).write_text(html_content, encoding="utf-8")


if __name__ == "__main__":

    def handle_exception(exc_type, exc_value, exc_traceback):
        print("CRITICAL ERROR ON LAUNCH:")
        traceback.print_exception(exc_type, exc_value, exc_traceback)

    sys.excepthook = handle_exception

    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())