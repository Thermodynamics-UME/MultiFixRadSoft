
import sys
import json
from pathlib import Path
import numpy as np
import pandas as pd
from datetime import datetime
from scipy.signal import find_peaks
from scipy.optimize import curve_fit, least_squares
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox, 
    QGroupBox, QFormLayout, QSpinBox, QDoubleSpinBox, QCheckBox, 
    QSplitter, QTabWidget, QTextEdit, QLineEdit, QFileDialog, QMessageBox,
    QSizePolicy, QScrollArea, QGridLayout, QFrame, QTableWidget, QTableWidgetItem, QHeaderView
)
from PySide6.QtCore import Qt, QSize, QDate, QTimer, QPropertyAnimation, QEasingCurve, QPoint
from PySide6.QtGui import QIcon, QFont, QColor, QPalette, QPixmap, QBrush, QAction
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from matplotlib.ticker import FuncFormatter
from matplotlib.widgets import SpanSelector, RectangleSelector

from theme_manager import ThemeManager
from plot_canvas import PlotCanvas

class DataAnalysisPage(QWidget):
    """Data Analysis page with POI, Liquidus, and advanced analysis capabilities"""
    
    def __init__(self, theme_name="Nord Dark"):
        super().__init__()
        self.theme_name = theme_name
        
        # Data storage
        self.time = None
        self.temperature = None
        self.signal = None
        self.temperature_raw = None
        self.signal_raw = None
        self.filter_applied = None
        
        # Region selection
        self.region_xmin = None
        self.region_xmax = None
        self.last_region_left = None
        self.last_region_right = None
        self.span_selector = None
        
        # Theme
        self.theme = ThemeManager.get_theme(theme_name)
        
        # POI/Derivative
        self.deriv_x = None
        self.deriv_y = None
        self.deriv_dy = None
        self.deriv_yname = "Temperature"
        self.deriv_offset = 0  # Offset from start of full data array
        
        # Results
        self.results_data = {
            'CCT WG5 method': {'POI': None, 'Liquidus Fraction': None, 'Liquidus Intersection': None, 'Melt Range': None},
            '3rd Degree Polynomial': {'POI': None, 'Liquidus Fraction': None, 'Liquidus Intersection': None, 'Melt Range': None},
            'Selective Fit': {'POI': None, 'Liquidus Fraction': None, 'Liquidus Intersection': None, 'Melt Range': None}
        }
        
        # Temperature units
        self.data_unit_kelvin = True  # Unit of loaded data: True = Kelvin, False = Celsius
        self.temp_unit_celsius = False  # Display unit for results: False = Kelvin, True = Celsius
        
        self.init_ui()
    
    def init_ui(self):
        main_layout = QVBoxLayout()
        
        # Header
        header = QLabel("📊 Data Analysis & POI")
        header.setFont(QFont("Arial", 18, QFont.Bold))  # Increased from 16
        main_layout.addWidget(header)
        
        # Create vertical splitter for tabs and logger
        splitter = QSplitter(Qt.Vertical)
        
        # Create tabs for different analyses
        self.tabs = QTabWidget()
        
        # Tab 1: File Loading & Main Plot
        tab_main = self._create_main_tab()
        self.tabs.addTab(tab_main, "Data Loading")
        
        # Tab 2: Derivatives & POI
        tab_poi = self._create_poi_tab()
        self.tabs.addTab(tab_poi, "POI Analysis")
        
        # Tab 3: Liquidus
        tab_liquidus = self._create_liquidus_tab()
        self.tabs.addTab(tab_liquidus, "Liquidus")
        
        # Tab 4: Results
        tab_results = self._create_results_tab()
        self.tabs.addTab(tab_results, "Results")
        
        splitter.addWidget(self.tabs)
        
        # Add logger/console widget at the bottom
        logger_group = QGroupBox("Console / Error Log")
        logger_layout = QVBoxLayout()
        self.log_console = QTextEdit()
        self.log_console.setReadOnly(True)
        self.log_console.setMinimumHeight(60)  # Minimum instead of maximum
        self.log_console.setStyleSheet(f"""
            QTextEdit {{
                background-color: #1e1e1e;
                color: #d4d4d4;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 10pt;
                border: 1px solid {self.theme["ACCENT_COLOR"]};
            }}
        """)
        logger_layout.addWidget(self.log_console)
        
        # Clear button for log
        btn_clear_log = QPushButton("🗑️ Clear Log")
        btn_clear_log.clicked.connect(lambda: self.log_console.clear())
        logger_layout.addWidget(btn_clear_log)
        
        logger_group.setLayout(logger_layout)
        splitter.addWidget(logger_group)
        
        # Set initial sizes (tabs get more space than logger)
        splitter.setSizes([600, 100])
        
        main_layout.addWidget(splitter, stretch=1)
        
        self.setLayout(main_layout)
        self._log("DataAnalysisPage initialized successfully")

    def _create_main_tab(self):
        """Create the main data loading and visualization tab"""
        widget = QWidget()
        layout = QVBoxLayout()
        
        # Controls
        ctrl_layout = QHBoxLayout()
        self.btn_load = QPushButton("📂 Load Data (txt/csv)")
        self.btn_load.clicked.connect(self.load_data)
        self.btn_derivative = QPushButton("📈 Compute Derivative")
        self.btn_derivative.clicked.connect(self.on_derivative)
        
        ctrl_layout.addWidget(self.btn_load)
        ctrl_layout.addWidget(QLabel("Domain:"))
        self.cb_domain = QComboBox()
        self.cb_domain.addItems(["Temperature", "Signal", "Both"])
        self.cb_domain.currentTextChanged.connect(self.on_domain_changed)
        ctrl_layout.addWidget(self.cb_domain)
        self.btn_derivative = QPushButton("📈 Compute Derivative")
        self.btn_derivative.clicked.connect(self.on_derivative)
        ctrl_layout.addWidget(self.btn_derivative)
        ctrl_layout.addStretch()
        layout.addLayout(ctrl_layout)
        
        # Main content
        content = QHBoxLayout()
        
        # Left: Info and controls
        left = QVBoxLayout()
        
        info_box = QGroupBox("File Information")
        info_form = QFormLayout()
        self.lbl_filename = QLabel("None")
        self.lbl_rows = QLabel("0")
        self.lbl_columns = QLabel("3 (Time, Temp, Signal)")
        info_form.addRow("File:", self.lbl_filename)
        info_form.addRow("Data Points:", self.lbl_rows)
        info_form.addRow("Columns:", self.lbl_columns)
        
        # Input data temperature unit selector
        unit_layout = QHBoxLayout()
        unit_layout.addWidget(QLabel("Data Unit:"))
        self.cb_data_unit = QComboBox()
        self.cb_data_unit.addItems(["K", "°C"])
        self.cb_data_unit.setCurrentIndex(0)  # Default to Kelvin
        self.cb_data_unit.currentTextChanged.connect(self.on_data_unit_changed)
        self.cb_data_unit.setMaximumWidth(80)
        unit_layout.addWidget(self.cb_data_unit)
        unit_layout.addStretch()
        unit_widget = QWidget()
        unit_widget.setLayout(unit_layout)
        info_form.addRow("Temperature:", unit_widget)
        
        info_box.setLayout(info_form)
        left.addWidget(info_box)
        
        # Region selection
        region_box = QGroupBox("Region Selection")
        region_form = QFormLayout()
        self.chk_region = QCheckBox("Enable Region Selection")
        self.chk_region.stateChanged.connect(self.on_region_toggled)
        region_form.addRow("Click & Drag:", self.chk_region)
        self.lbl_region = QLabel("None")
        region_form.addRow("Selected:", self.lbl_region)
        region_box.setLayout(region_form)
        left.addWidget(region_box)
        
        # Data Filter controls
        filter_group = QGroupBox('Data Filter')
        filter_layout = QVBoxLayout()
        
        # Filter type selector
        filter_type_layout = QHBoxLayout()
        filter_type_layout.addWidget(QLabel('Filter Type:'))
        self.cb_filter_type = QComboBox()
        self.cb_filter_type.addItems(['Kalman Filter', 'Savitzky-Golay', 'Moving Average'])
        self.cb_filter_type.currentTextChanged.connect(self._on_filter_type_changed)
        filter_type_layout.addWidget(self.cb_filter_type)
        filter_layout.addLayout(filter_type_layout)
        
        # Kalman Filter parameters
        self.kalman_widget = QWidget()
        kalman_form = QFormLayout()
        self.spin_process_var = QDoubleSpinBox()
        self.spin_process_var.setDecimals(8)
        self.spin_process_var.setRange(1e-10, 1.0)
        self.spin_process_var.setValue(1e-5)
        self.spin_process_var.setSingleStep(1e-6)
        self.spin_process_var.setToolTip('Process variance (Q): how much the process changes')
        kalman_form.addRow('Process Var (Q):', self.spin_process_var)
        
        self.spin_measurement_var = QDoubleSpinBox()
        self.spin_measurement_var.setDecimals(8)
        self.spin_measurement_var.setRange(1e-10, 10.0)
        self.spin_measurement_var.setValue(0.1)
        self.spin_measurement_var.setSingleStep(0.01)
        self.spin_measurement_var.setToolTip('Measurement variance (R): noise in measurements')
        kalman_form.addRow('Measurement Var (R):', self.spin_measurement_var)
        self.kalman_widget.setLayout(kalman_form)
        filter_layout.addWidget(self.kalman_widget)
        
        # Savitzky-Golay parameters
        self.savgol_widget = QWidget()
        savgol_form = QFormLayout()
        self.spin_window_length = QSpinBox()
        self.spin_window_length.setRange(5, 501)
        self.spin_window_length.setValue(51)
        self.spin_window_length.setSingleStep(2)
        self.spin_window_length.setToolTip('Window length (must be odd): larger = smoother')
        savgol_form.addRow('Window Length:', self.spin_window_length)
        
        self.spin_polyorder = QSpinBox()
        self.spin_polyorder.setRange(1, 10)
        self.spin_polyorder.setValue(3)
        self.spin_polyorder.setToolTip('Polynomial order: degree of fitting polynomial')
        savgol_form.addRow('Poly Order:', self.spin_polyorder)
        self.savgol_widget.setLayout(savgol_form)
        filter_layout.addWidget(self.savgol_widget)
        self.savgol_widget.hide()  # Initially hidden
        
        # Moving Average parameters
        self.movavg_widget = QWidget()
        movavg_form = QFormLayout()
        self.spin_movavg_window = QSpinBox()
        self.spin_movavg_window.setRange(3, 501)
        self.spin_movavg_window.setValue(10)
        self.spin_movavg_window.setSingleStep(1)
        self.spin_movavg_window.setToolTip('Window size: number of points to average')
        movavg_form.addRow('Window Size:', self.spin_movavg_window)
        self.movavg_widget.setLayout(movavg_form)
        filter_layout.addWidget(self.movavg_widget)
        self.movavg_widget.hide()  # Initially hidden
        
        # Apply and Reset buttons
        self.btn_apply_filter = QPushButton('Apply Filter')
        self.btn_apply_filter.clicked.connect(self._on_apply_filter)
        filter_layout.addWidget(self.btn_apply_filter)
        
        self.btn_reset_filter = QPushButton('Reset to Original')
        self.btn_reset_filter.clicked.connect(self._on_reset_filter)
        filter_layout.addWidget(self.btn_reset_filter)
        
        filter_group.setLayout(filter_layout)
        left.addWidget(filter_group)
        
        left.addStretch()
        
        # Right: Plot canvas
        right = QVBoxLayout()
        plot_box = QGroupBox("Time-Temperature-Signal Plot")
        plot_layout = QVBoxLayout()
        self.canvas_main = PlotCanvas("Temperature and Signal", theme_name=self.theme_name)
        plot_layout.addWidget(self.canvas_main)
        plot_box.setLayout(plot_layout)
        right.addWidget(plot_box)
        
        content.addLayout(left, 25)
        content.addLayout(right, 75)
        layout.addLayout(content, stretch=1)
        
        widget.setLayout(layout)
        return widget
    
    def _create_poi_tab(self):
        """Create the POI analysis tab"""
        widget = QWidget()
        layout = QVBoxLayout()
        
        # POI Method selector
        ctrl_layout = QHBoxLayout()
        ctrl_layout.addWidget(QLabel("POI Method:"))
        self.cb_poi_method = QComboBox()
        self.cb_poi_method.addItems(['CCT WG5', '3rd Degree Polynomial', 'Selective Fit'])
        self.cb_poi_method.currentTextChanged.connect(self._on_poi_method_changed)
        ctrl_layout.addWidget(self.cb_poi_method)
        
        # R² threshold input (only for Selective Fit)
        self.lbl_r2_thresh = QLabel("R² Threshold:")
        self.spin_r2_thresh = QDoubleSpinBox()
        self.spin_r2_thresh.setRange(0.0, 1.0)
        self.spin_r2_thresh.setSingleStep(0.05)
        self.spin_r2_thresh.setValue(0.70)
        self.spin_r2_thresh.setDecimals(2)
        self.spin_r2_thresh.setVisible(False)
        self.lbl_r2_thresh.setVisible(False)
        ctrl_layout.addWidget(self.lbl_r2_thresh)
        ctrl_layout.addWidget(self.spin_r2_thresh)
        
        self.btn_compute_poi = QPushButton("🔍 Compute POI")
        self.btn_compute_poi.clicked.connect(self.compute_poi)
        ctrl_layout.addWidget(self.btn_compute_poi)
        ctrl_layout.addStretch()
        layout.addLayout(ctrl_layout)
        
        # POI Plot
        plot_box = QGroupBox("POI / Derivative Analysis")
        plot_layout = QVBoxLayout()
        self.canvas_poi = PlotCanvas("POI Analysis", theme_name=self.theme_name)
        plot_layout.addWidget(self.canvas_poi)
        plot_box.setLayout(plot_layout)
        layout.addWidget(plot_box, stretch=1)
        
        widget.setLayout(layout)
        return widget
    
    def _create_liquidus_tab(self):
        """Create the liquidus analysis tab"""
        widget = QWidget()
        layout = QVBoxLayout()
        
        # Liquidus controls
        ctrl_layout = QHBoxLayout()
        ctrl_layout.addWidget(QLabel("Method:"))
        self.cb_liq_method = QComboBox()
        self.cb_liq_method.addItems(['Fraction Method', 'Intersection Method'])
        ctrl_layout.addWidget(self.cb_liq_method)
        self.btn_compute_liquidus = QPushButton("🌡️ Compute Liquidus")
        self.btn_compute_liquidus.clicked.connect(self.compute_liquidus)
        ctrl_layout.addWidget(self.btn_compute_liquidus)
        ctrl_layout.addStretch()
        layout.addLayout(ctrl_layout)
        
        # Liquidus plot
        plot_box = QGroupBox("Liquidus Analysis")
        plot_layout = QVBoxLayout()
        self.canvas_liquidus = PlotCanvas("Liquidus", theme_name=self.theme_name)
        plot_layout.addWidget(self.canvas_liquidus)
        plot_box.setLayout(plot_layout)
        layout.addWidget(plot_box, stretch=1)
        
        widget.setLayout(layout)
        return widget
    
    def _create_results_tab(self):
        """Create the results display tab"""
        widget = QWidget()
        layout = QVBoxLayout()
        
        # Temperature unit toggle
        unit_layout = QHBoxLayout()
        unit_label = QLabel("Temperature Unit:")
        unit_label.setStyleSheet("font-weight: bold;")
        unit_layout.addWidget(unit_label)
        
        self.btn_temp_unit = QPushButton("K")
        self.btn_temp_unit.setCheckable(True)
        self.btn_temp_unit.setMaximumWidth(80)
        self.btn_temp_unit.setStyleSheet("""
            QPushButton {
                font-weight: bold;
                padding: 5px;
            }
            QPushButton:checked {
                background-color: #5e81ac;
            }
        """)
        self.btn_temp_unit.clicked.connect(self.toggle_temp_unit)
        unit_layout.addWidget(self.btn_temp_unit)
        
        unit_info = QLabel("(Click to toggle between Kelvin and Celsius)")
        unit_info.setStyleSheet("color: gray; font-size: 9pt;")
        unit_layout.addWidget(unit_info)
        unit_layout.addStretch()
        
        layout.addLayout(unit_layout)
        
        self.results_table = QTableWidget()
        self.results_table.setColumnCount(4)
        self.results_table.setRowCount(3)
        self.results_table.setHorizontalHeaderLabels(['POI', 'Liquidus Fraction', 'Liquidus Intersection', 'Melt Range'])
        self.results_table.setVerticalHeaderLabels(['CCT WG5', '3rd Degree Poly', 'Selective Fit'])
        self.results_table.horizontalHeader().setStretchLastSection(True)
        self.results_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.results_table)
        
        btn_layout = QHBoxLayout()
        clear_btn = QPushButton("🗑️ Clear Results")
        clear_btn.clicked.connect(self.on_clear_results)
        btn_layout.addWidget(clear_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        
        widget.setLayout(layout)
        return widget
    
    def set_theme(self, theme_name):
        """Update theme for all canvases"""
        self.theme_name = theme_name
        if hasattr(self, 'canvas_main'):
            self.canvas_main.set_theme(theme_name)
        if hasattr(self, 'canvas_poi'):
            self.canvas_poi.set_theme(theme_name)
        if hasattr(self, 'canvas_liquidus'):
            self.canvas_liquidus.set_theme(theme_name)
    
    def load_data(self):
        """Load time-temperature-signal data from file"""
        self._log("Opening file dialog...", "INFO")
        path, _ = QFileDialog.getOpenFileName(self, 'Load Data File', '', 'Data files (*.txt *.csv);;All files (*)')
        if not path:
            self._log("File selection cancelled", "WARNING")
            return
        
        self._log(f"Loading file: {path}", "INFO")
        try:
            import csv
            with open(path, 'r', newline='', encoding='utf-8', errors='ignore') as f:
                sniffer = csv.Sniffer()
                sample = f.read(1024)
                f.seek(0)
                try:
                    delimiter = sniffer.sniff(sample).delimiter
                except Exception:
                    delimiter = ',' if ',' in sample else '\t' if '\t' in sample else ' '
                f.seek(0)
                rows = list(csv.reader(f, delimiter=delimiter))
            
            if not rows:
                self._log("No data found in file", "ERROR")
                return
            
            times, temps, sigs = [], [], []
            
            # Try to skip header rows (detect if first row has non-numeric data)
            start_idx = 0
            for i, first_row in enumerate(rows[:3]):
                try:
                    # Try parsing first column as either time format or number
                    first_col = first_row[0].strip() if first_row else ""
                    if self._parse_time(first_col) is not None or self._is_numeric(first_col):
                        start_idx = i
                        break
                except (ValueError, IndexError):
                    start_idx = i + 1
            
            # Parse data rows
            for r in rows[start_idx:]:
                r = [c.strip() for c in r if c.strip()]  # Remove empty strings
                if len(r) < 2:  # Minimum 2 columns needed (time + temp)
                    continue
                try:
                    # Parse time (can be hh:mm:ss or numeric seconds)
                    time_str = r[0]
                    t = self._parse_time(time_str)
                    if t is None:
                        t = float(time_str)
                    
                    temp = float(r[1])
                    sig = float(r[2]) if len(r) > 2 else 0.0  # Signal is optional
                    times.append(t)
                    temps.append(temp)
                    sigs.append(sig)
                except (ValueError, IndexError):
                    continue  # Skip rows with parsing errors
            
            if not times:
                QMessageBox.critical(self, "Error", 
                    "No valid numeric data found in file.\n\n"
                    "Expected format:\n"
                    "• Column 1: Time (hh:mm:ss or seconds)\n"
                    "• Column 2: Temperature\n"
                    "• Column 3: Signal (optional)\n\n"
                    "Delimiter: comma or tab")
                return
            
            t = np.array(times, dtype=float)
            t = t - t[0]  # Normalize to start at 0
            self.time = t
            self.temperature = np.array(temps, dtype=float)
            self.signal = np.array(sigs, dtype=float) if sigs else np.zeros_like(temps)
            self.temperature_raw = self.temperature.copy()
            self.signal_raw = self.signal.copy()
            
            self.lbl_filename.setText(Path(path).name)
            self.lbl_rows.setText(str(len(self.time)))
            
            self.update_main_plot()
            self._log(f"Successfully loaded {len(self.time)} data points from {Path(path).name}", "SUCCESS")
        except Exception as e:
            self._log(f"Error loading file: {str(e)}", "ERROR")
            import traceback
            self._log(traceback.format_exc(), "ERROR")
    
    def _parse_time(self, time_str):
        """Parse time string in format hh:mm:ss or hh:mm:ss.fff"""
        time_str = time_str.strip()
        if not time_str or ':' not in time_str:
            return None
        
        try:
            parts = time_str.split(':')
            if len(parts) == 3:
                hours = int(parts[0])
                minutes = int(parts[1])
                seconds = float(parts[2])
                total_seconds = hours * 3600 + minutes * 60 + seconds
                return total_seconds
        except (ValueError, IndexError):
            pass
        return None
    
    def _is_numeric(self, s):
        """Check if string is numeric"""
        try:
            float(s)
            return True
        except ValueError:
            return False
    
    def update_main_plot(self):
        """Update the main time-temperature-signal plot"""
        if self.time is None:
            return
        
        self.canvas_main.figure.clear()
        ax = self.canvas_main.figure.add_subplot(111)
        self.canvas_main.ax = ax
        
        domain = self.cb_domain.currentText() if hasattr(self, 'cb_domain') else "Both"
        
        # Plot based on domain selection
        if domain in ["Temperature", "Both"]:
            ax.plot(self.time, self.temperature, '-', lw=2, label='Temperature', color='blue')
            ax.set_ylabel('Temperature (°C)', color='blue')
            ax.tick_params(axis='y', labelcolor='blue')
        
        if domain in ["Signal", "Both"] and self.signal is not None:
            if domain == "Signal":
                ax.plot(self.time, self.signal, '-', lw=2, label='Signal', color='orange')
                ax.set_ylabel('Signal', color='orange')
                ax.tick_params(axis='y', labelcolor='orange')
            else:  # Both
                ax2 = ax.twinx()
                ax2.plot(self.time, self.signal, '-', lw=1.5, label='Signal', color='orange')
                ax2.set_ylabel('Signal', color='orange')
                ax2.tick_params(axis='y', labelcolor='orange')
        
        # Format x-axis as hh:mm:ss
        ax.set_xlabel('Time')
        ax.xaxis.set_major_formatter(FuncFormatter(self._seconds_to_hhmmss))
        
        # Add region shading if selected
        if self.region_xmin is not None and self.region_xmax is not None:
            ax.axvspan(self.region_xmin, self.region_xmax, alpha=0.2, color='green', label='Selected Region')
        
        ax.grid(True, alpha=0.25)
        leg = ax.legend(loc='upper left')
        leg.set_draggable(True)
        self.canvas_main.figure.tight_layout()
        self.canvas_main.draw()
        
        # Save initial limits for zoom reset
        self.canvas_main._save_initial_limits()
    
    def _on_filter_type_changed(self, filter_type):
        """Show/hide filter parameter controls based on selected filter type."""
        if filter_type == 'Kalman Filter':
            self.kalman_widget.show()
            self.savgol_widget.hide()
            self.movavg_widget.hide()
        elif filter_type == 'Savitzky-Golay':
            self.kalman_widget.hide()
            self.savgol_widget.show()
            self.movavg_widget.hide()
        elif filter_type == 'Moving Average':
            self.kalman_widget.hide()
            self.savgol_widget.hide()
            self.movavg_widget.show()
    
    def _on_apply_filter(self):
        """Apply selected filter to temperature and signal data."""
        if self.temperature_raw is None:
            self._log("No data loaded to filter", "WARNING")
            return
        
        filter_type = self.cb_filter_type.currentText()
        
        if filter_type == 'Kalman Filter':
            process_var = self.spin_process_var.value()
            measurement_var = self.spin_measurement_var.value()
            
            self.temperature = self._kalman_filter(self.temperature_raw, process_var, measurement_var)
            if self.signal_raw is not None:
                self.signal = self._kalman_filter(self.signal_raw, process_var, measurement_var)
            
            self.filter_applied = 'Kalman'
            self._log(f"Applied Kalman Filter (Q={process_var:.2e}, R={measurement_var:.2e})", "SUCCESS")
            
        elif filter_type == 'Savitzky-Golay':
            from scipy.signal import savgol_filter
            window_length = self.spin_window_length.value()
            polyorder = self.spin_polyorder.value()
            
            # Ensure window is odd
            if window_length % 2 == 0:
                window_length += 1
                self.spin_window_length.setValue(window_length)
            
            # Ensure polyorder < window_length
            if polyorder >= window_length:
                polyorder = window_length - 1
                self.spin_polyorder.setValue(polyorder)
            
            self.temperature = savgol_filter(self.temperature_raw, window_length, polyorder)
            if self.signal_raw is not None:
                self.signal = savgol_filter(self.signal_raw, window_length, polyorder)
            
            self.filter_applied = 'Savitzky-Golay'
            self._log(f"Applied Savitzky-Golay Filter (window={window_length}, order={polyorder})", "SUCCESS")
        
        elif filter_type == 'Moving Average':
            window_size = self.spin_movavg_window.value()
            
            self.temperature = self._moving_average(self.temperature_raw, window_size)
            if self.signal_raw is not None:
                self.signal = self._moving_average(self.signal_raw, window_size)
            
            self.filter_applied = 'Moving Average'
            self._log(f"Applied Moving Average Filter (window={window_size})", "SUCCESS")
        
        self.update_main_plot()
    
    def _on_reset_filter(self):
        """Reset data to original (unfiltered) values."""
        if self.temperature_raw is None:
            self._log("No data to reset", "WARNING")
            return
        
        self.temperature = self.temperature_raw.copy()
        if self.signal_raw is not None:
            self.signal = self.signal_raw.copy()
        
        self.filter_applied = None
        self.update_main_plot()
        self._log("Data reset to original (filter removed)", "SUCCESS")
    
    def _kalman_filter(self, data, process_variance=1e-5, measurement_variance=0.1):
        """Apply 1D Kalman filter to smooth noisy data."""
        if data is None or len(data) == 0:
            return data
        
        n = len(data)
        filtered = np.zeros(n)
        
        # Initial estimates
        x_est = data[0]  # Initial state estimate
        p_est = 1.0      # Initial estimation error covariance
        
        for i in range(n):
            # Prediction
            x_pred = x_est
            p_pred = p_est + process_variance
            
            # Update
            K = p_pred / (p_pred + measurement_variance)  # Kalman gain
            x_est = x_pred + K * (data[i] - x_pred)
            p_est = (1 - K) * p_pred
            
            filtered[i] = x_est
        
        return filtered
    
    def _moving_average(self, data, window_size=10):
        """Apply moving average filter to smooth noisy data."""
        if data is None or len(data) == 0:
            return data
        
        # Ensure window_size is valid
        window_size = max(1, min(window_size, len(data)))
        
        # Apply moving average using convolution
        window = np.ones(window_size) / window_size
        filtered = np.convolve(data, window, mode='same')
        
        # Handle edges by using original values
        edge = window_size // 2
        if edge > 0:
            filtered[:edge] = data[:edge]
            filtered[-edge:] = data[-edge:]
        
        return filtered
    
    def _seconds_to_hhmmss(self, seconds, pos=None):
        """Convert seconds to hh:mm:ss format for matplotlib"""
        if seconds < 0:
            return "00:00:00"
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    
    def _log(self, message, level="INFO"):
        """Log message to console widget"""
        import datetime
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        
        # Color coding based on level
        if level == "ERROR":
            color = "#ff6b6b"
        elif level == "WARNING":
            color = "#ffd93d"
        elif level == "SUCCESS":
            color = "#6bcf7f"
        else:  # INFO
            color = "#d4d4d4"
        
        formatted_msg = f'<span style="color: #888;">[{timestamp}]</span> <span style="color: {color}; font-weight: bold;">[{level}]</span> <span style="color: {color};">{message}</span>'
        self.log_console.append(formatted_msg)
        
        # Auto-scroll to bottom
        scrollbar = self.log_console.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
    
    def on_domain_changed(self, domain):
        """Handle domain selection change"""
        if self.time is not None:
            self.update_main_plot()
    
    def on_region_toggled(self, state):
        """Handle region selection toggle with SpanSelector"""
        if state:
            if hasattr(self, 'canvas_main') and hasattr(self.canvas_main, 'ax'):
                def on_select(xmin, xmax):
                    """Callback for SpanSelector"""
                    self.region_xmin = xmin
                    self.region_xmax = xmax
                    self.lbl_region.setText(f"{self._seconds_to_hhmmss(xmin)} to {self._seconds_to_hhmmss(xmax)}")
                    self.update_main_plot()
                
                # Create SpanSelector for region selection
                self.span_selector = SpanSelector(
                    self.canvas_main.ax,
                    on_select,
                    useblit=True,
                    props=dict(alpha=0.3, facecolor='cyan'),
                    interactive=True,
                    direction='horizontal'
                )
                QMessageBox.information(self, "Region Selection", "Click and drag on the plot to select a region")
        else:
            if hasattr(self, 'span_selector') and self.span_selector is not None:
                self.span_selector.set_active(False)
                self.span_selector = None
            self.region_xmin = None
            self.region_xmax = None
            self.lbl_region.setText("None")
            self.update_main_plot()
    def on_derivative(self):
        """Compute and display derivative"""
        if self.time is None:
            self._log("Cannot compute derivative: no data loaded", "WARNING")
            return
        
        self.tabs.setCurrentIndex(1)
        
        # Use full range if no region selected
        if self.region_xmin is None or self.region_xmax is None:
            left, right = 0, len(self.time)
        else:
            xmin, xmax = sorted([self.region_xmin, self.region_xmax])
            left = int(np.searchsorted(self.time, xmin, side='left'))
            right = int(np.searchsorted(self.time, xmax, side='right'))
        
        # Get domain selection
        domain = self.cb_domain.currentText()
        
        x = self.time[left:right]
        
        # Check if we have enough data points
        if len(x) < 2:
            self._log("Cannot compute derivative: need at least 2 data points in selected region", "WARNING")
            return
        
        # Select y-axis data based on domain
        if domain == "Signal":
            y = self.signal[left:right]
            y_label = 'Signal'
            dy_label = 'dS/dt'
            self.deriv_yname = "Signal"
        else:  # Temperature or Both (use Temperature for derivative)
            y = self.temperature[left:right]
            y_label = 'Temperature'
            dy_label = 'dT/dt'
            self.deriv_yname = "Temperature"
        
        dy = np.gradient(y, x)
        
        self.deriv_x = x
        self.deriv_y = y
        self.deriv_dy = dy
        self.deriv_offset = left  # Store offset for index mapping
        
        # Plot
        self.canvas_poi.figure.clear()
        ax = self.canvas_poi.figure.add_subplot(111)
        line1 = ax.plot(x, y, 'b-', lw=2, label=y_label)[0]
        ax2 = ax.twinx()
        line2 = ax2.plot(x, dy, 'r-', lw=1.5, label=dy_label)[0]
        ax.set_xlabel('Time')
        ax.set_ylabel(f'{y_label} ({"°C" if domain == "Temperature" else "a.u."})', color='b')
        ax2.set_ylabel(dy_label, color='r')
        ax.xaxis.set_major_formatter(FuncFormatter(self._seconds_to_hhmmss))
        
        # Create legends with proper handles and make them draggable
        leg1 = ax.legend([line1], [y_label], loc='upper left')
        leg2 = ax2.legend([line2], [dy_label], loc='upper right')
        leg1.set_draggable(True)
        leg2.set_draggable(True)
        
        ax.grid(True, alpha=0.25)
        self.canvas_poi.figure.tight_layout()
        self.canvas_poi.draw()
        
        # Save initial limits for zoom reset
        self.canvas_poi._save_initial_limits()
    
    def _on_poi_method_changed(self, method):
        """Show/hide R² threshold input based on selected POI method"""
        is_selective = (method == 'Selective Fit')
        self.lbl_r2_thresh.setVisible(is_selective)
        self.spin_r2_thresh.setVisible(is_selective)
    
    def compute_poi(self):
        """Compute POI based on selected method"""
        if self.deriv_y is None:
            self._log("Cannot compute POI: derivative not computed", "WARNING")
            return
        
        method = self.cb_poi_method.currentText()
        self._log(f"Starting POI computation using method: {method}", "INFO")
        
        try:
            if method == 'CCT WG5':
                self._compute_poi_cct_wg5()
            elif method == '3rd Degree Polynomial':
                self._compute_poi_polynomial()
            elif method == 'Selective Fit':
                self._compute_poi_selective()
        except Exception as e:
            self._log(f"POI computation failed: {str(e)}", "ERROR")
            import traceback
            self._log(traceback.format_exc(), "ERROR")
    
    def _compute_poi_cct_wg5(self):
        """CCT WG5 style: place marker at minimum derivative; mark two peak maxima and quartiles."""
        self._log("Starting CCT WG5 POI computation", "INFO")
        x = self.deriv_x
        y = self.deriv_y
        dy = self.deriv_dy
        
        # Clear canvas properly
        for ax in list(self.canvas_poi.figure.axes):
            self.canvas_poi.figure.delaxes(ax)
        ax = self.canvas_poi.figure.add_subplot(111)
        self.canvas_poi.ax = ax
        
        # Find derivative minimum
        self._log("Finding derivative minimum...", "INFO")
        idx_min = int(np.nanargmin(dy))
        x_min = float(x[idx_min])
        x_near, y_near, _ = self._nearest_on_series(x, y, x_min)
        
        # Find top two peaks of derivative
        self._log("Finding two peaks in derivative data...", "INFO")
        peaks = self._find_two_peaks(x, dy, min_sep=200.0)
        if len(peaks) < 2:
            self._log(f"Only found {len(peaks)} peak(s), need 2", "WARNING")
            return
        
        self._log(f"Found 2 peaks at indices: {peaks[0]}, {peaks[1]}", "INFO")
        i1, i2 = peaks
        if x[i1] > x[i2]:
            i1, i2 = i2, i1
        
        dist = abs(i2 - i1)
        q = max(1, int(round(dist / 4.0)))
        s = i1 + q
        e = i2 - q
        
        if e > s:
            xtann = x[s:e+1]
            ytann = y[s:e+1]
            try:
                p = np.polyfit(xtann, ytann, 1)
                p1 = float(p[0])
                melt_range_cct = p1 * (float(x[i2]) - float(x[i1]))
            except Exception:
                p1, melt_range_cct = np.nan, np.nan
        else:
            p1, melt_range_cct = np.nan, np.nan
        
        # Draw POI plot
        ax.set_title('POI / Derivative (CCT WG5)')
        ax.set_xlabel('Time, hh:mm:ss')
        ax.set_ylabel(self.deriv_yname, color='b')
        ax.plot(x, y, 'b-', lw=2, label=self.deriv_yname)
        ax.tick_params(axis='y', labelcolor='b')
        
        ax2 = ax.twinx()
        deriv_label = 'dS/dt' if self.deriv_yname == 'Signal' else 'dT/dt'
        ax2.set_ylabel(deriv_label, color='r')
        ax2.plot(x, dy, 'r-', lw=1.5, label=deriv_label)
        ax2.tick_params(axis='y', labelcolor='r')
        
        # Mark POI
        ax.scatter([x_near], [y_near], s=100, c='green', marker='o', zorder=5, label='CCT POI')
        
        # Mark peaks
        for p_idx in peaks:
            xp = float(x[p_idx])
            xn_p, yn_p, _ = self._nearest_on_series(x, y, xp)
            ax.scatter([xn_p], [yn_p], s=80, c='cyan', marker='^', zorder=4, label='Melt start/end')
        
        # Mark quartile boundaries
        xs_val, ys_val, _ = self._nearest_on_series(x, y, float(x[s]))
        xe_val, ye_val, _ = self._nearest_on_series(x, y, float(x[e]))
        ax.scatter([xs_val, xe_val], [ys_val, ye_val], s=80, c='orange', marker='D', zorder=4, label='Quartile bounds')
        
        ax.grid(True, alpha=0.25)
        ax.xaxis.set_major_formatter(FuncFormatter(self._seconds_to_hhmmss))
        
        # Combined legend
        from matplotlib.lines import Line2D
        deriv_label = 'dS/dt' if self.deriv_yname == 'Signal' else 'dT/dt'
        legend_elements = [
            Line2D([0], [0], color='b', lw=2, label=self.deriv_yname),
            Line2D([0], [0], color='r', lw=1.5, label=deriv_label),
            Line2D([0], [0], marker='o', color='w', markerfacecolor='g', markersize=8, label='CCT POI'),
            Line2D([0], [0], marker='^', color='w', markerfacecolor='c', markersize=8, label='Melt start/end'),
            Line2D([0], [0], marker='D', color='w', markerfacecolor='orange', markersize=8, label='Quartile bounds')
        ]
        leg = ax.legend(handles=legend_elements, loc='upper left', fontsize=8)
        if leg is not None:
            leg.set_draggable(True)
        
        self.canvas_poi.figure.tight_layout()
        self.canvas_poi.draw()
        
        # Store results
        self.results_data['CCT WG5 method']['POI'] = float(y_near)
        self.results_data['CCT WG5 method']['Melt Range'] = float(melt_range_cct)
        self.results_data['3rd Degree Polynomial']['Melt Range'] = float(melt_range_cct)
        self.results_data['Selective Fit']['Melt Range'] = float(melt_range_cct)
        self._update_results_table()
        
        # Smart formatting for logger
        poi_str = f"{y_near:.5e}" if abs(y_near) < 0.001 and y_near != 0 else f"{y_near:.4f}"
        melt_str = f"{melt_range_cct:.5e}" if abs(melt_range_cct) < 0.001 and melt_range_cct != 0 else f"{melt_range_cct:.4f}"
        self._log(f"CCT WG5 POI computed: {self.deriv_yname}={poi_str}, Melt Range={melt_str}", "SUCCESS")
    
    def _compute_poi_polynomial(self):
        """3rd degree polynomial: fit to central block and use inflection point"""
        x = self.deriv_x
        y = self.deriv_y
        dy = self.deriv_dy
        
        peaks = self._find_two_peaks(x, dy, min_sep=200.0)
        if len(peaks) < 2:
            self._log("Could not find two distinct peaks in derivative data", "WARNING")
            return
        
        i1, i2 = peaks
        if x[i1] > x[i2]:
            i1, i2 = i2, i1
        
        dist = abs(i2 - i1)
        q = max(1, int(round(dist / 4.0)))
        s = i1 + q
        e = i2 - q
        
        if e <= s:
            self._log("Invalid central block for cubic fit", "ERROR")
            return
        
        xtann = x[s:e+1]
        ytann = y[s:e+1]
        
        # Scale signal values to avoid degenerate cubic
        scale_factor = 1.0
        if self.deriv_yname == "Signal":
            # Find magnitude of signal and scale up
            y_magnitude = np.max(np.abs(ytann))
            if y_magnitude > 0:
                # Calculate decimal places needed
                decimal_places = int(np.ceil(-np.log10(y_magnitude)))
                if decimal_places > 0:
                    scale_factor = 10.0 ** decimal_places
                    ytann = ytann * scale_factor
                    self._log(f"Scaling signal by 10^{decimal_places} to avoid degenerate cubic", "INFO")
        
        try:
            p = np.polyfit(xtann, ytann, 3)
        except Exception as ex:
            self._log(f"Cubic fit failed: {ex}", "ERROR")
            return
        
        a3, a2, a1, a0 = [float(_) for _ in p]
        
        if abs(a3) < 1e-16:
            self._log("Degenerate cubic (a3 ~ 0)", "ERROR")
            return
        
        # Inflection point: x = -a2/(3*a3)
        x_poi = -a2 / (3.0 * a3)
        y_poi = a3 * x_poi**3 + a2 * x_poi**2 + a1 * x_poi + a0
        
        # Scale back if we scaled up
        if scale_factor != 1.0:
            y_poi = y_poi / scale_factor
        
        xn, yn, _ = self._nearest_on_series(x, y, x_poi)
        
        # Clear canvas properly
        for ax_old in list(self.canvas_poi.figure.axes):
            self.canvas_poi.figure.delaxes(ax_old)
        ax = self.canvas_poi.figure.add_subplot(111)
        self.canvas_poi.ax = ax
        
        # Plot
        ax.set_title('POI / Derivative (3rd Degree Polynomial)')
        ax.set_xlabel('Time')
        ax.set_ylabel(self.deriv_yname)
        ax.plot(x, y, 'b-', lw=2, label=self.deriv_yname)
        ax2 = ax.twinx()
        deriv_label = 'dS/dt' if self.deriv_yname == 'Signal' else 'dT/dt'
        ax2.set_ylabel(deriv_label)
        ax2.plot(x, dy, 'r-', lw=1.5, label=deriv_label)
        
        # Cubic fit line (scale back if needed)
        x_fit = np.linspace(float(x[i1]), float(x[i2]), 300)
        y_fit = np.polyval(p, x_fit)
        if scale_factor != 1.0:
            y_fit = y_fit / scale_factor
        ax.plot(x_fit, y_fit, '--', lw=2, color='#ff00ff', alpha=0.9, label='Cubic Fit')
        
        # Mark POI
        ax.scatter([xn], [yn], s=120, c='#ff00ff', marker='o', zorder=5, label='POI (3rd Degree)')
        
        ax.grid(True, alpha=0.25)
        ax.xaxis.set_major_formatter(FuncFormatter(self._seconds_to_hhmmss))
        leg = ax.legend(loc='upper left')
        if leg is not None:
            leg.set_draggable(True)
        ax.set_ylabel(self.deriv_yname, color='b')
        ax.tick_params(axis='y', labelcolor='b')
        ax2.set_ylabel(deriv_label, color='r')
        ax2.tick_params(axis='y', labelcolor='r')
        self.canvas_poi.figure.tight_layout()
        self.canvas_poi.draw()
        
        # Store results
        self.results_data['3rd Degree Polynomial']['POI'] = float(yn)
        self._update_results_table()
        
        # Smart formatting for logger
        poi_str = f"{yn:.5e}" if abs(yn) < 0.001 and yn != 0 else f"{yn:.4f}"
        self._log(f"3rd Degree Polynomial POI computed: {self.deriv_yname}={poi_str}", "SUCCESS")
    
    def _compute_poi_selective(self):
        """Selective fitting: multiple cubic fits, average by R²"""
        x = self.deriv_x
        y = self.deriv_y
        dy = self.deriv_dy
        
        peaks = self._find_two_peaks(x, dy, min_sep=200.0)
        if len(peaks) < 2:
            self._log("Could not find two distinct peaks in derivative data", "WARNING")
            return
        
        i1, i2 = peaks
        if x[i1] > x[i2]:
            i1, i2 = i2, i1
        
        q = max(1, int(round(abs(i2 - i1) / 4.0)))
        
        # Try derivative-based limits (ts/te/tms/tme)
        try:
            ts_idx, te_idx, tms_idx, tme_idx = self._detect_ts_te_tms_tme(x, y, float(x[i1]), float(x[i2]))
            ts, te = ts_idx, te_idx
            # Validate that ts and te are reasonable
            if ts >= te or ts < 0 or te >= len(x):
                raise ValueError("Invalid ts/te indices from derivative detection")
        except Exception as e:
            # Fallback to quartile-based method
            ts, te = i1 + q, i2 - q
            tms_idx = max(0, ts - q)
            tme_idx = min(len(x) - 1, te + q)
            self._log(f"Using fallback quartile method (derivative detection failed: {e})", "INFO")
        
        if te <= ts:
            self._log("Invalid range for selective fit", "ERROR")
            return
        
        start_min, start_max = max(0, ts), min(len(x) - 4, tms_idx)
        end_min, end_max = max(4, tme_idx), min(len(x) - 1, te)
        
        if start_max < start_min:
            start_max = start_min + 1
        if end_max < end_min:
            end_max = end_min + 1
        
        starts = list(range(start_min, start_max + 1))
        ends = list(range(end_min, end_max + 1))
        
        if not starts or not ends:
            self._log("No valid candidate ranges for selective fit", "ERROR")
            return
        
        # Scale signal values to avoid degenerate cubic
        scale_factor = 1.0
        y_scaled = y.copy()
        if self.deriv_yname == "Signal":
            # Find magnitude of signal in the fitting region
            y_region = y[start_min:end_max+1]
            y_magnitude = np.max(np.abs(y_region))
            if y_magnitude > 0:
                # Calculate decimal places needed
                decimal_places = int(np.ceil(-np.log10(y_magnitude)))
                if decimal_places > 0:
                    scale_factor = 10.0 ** decimal_places
                    y_scaled = y * scale_factor
                    self._log(f"Scaling signal by 10^{decimal_places} to avoid degenerate cubic", "INFO")
        
        # Get R² threshold from input
        r2_thresh = self.spin_r2_thresh.value()
        aa, bb, cc, dd = [], [], [], []
        attempted, accepted = 0, 0
        
        for s in starts:
            for e in ends:
                if e <= s + 3:
                    continue
                attempted += 1
                xs = x[s:e+1]
                ys = y_scaled[s:e+1]
                try:
                    p = np.polyfit(xs, ys, 3)
                except Exception:
                    continue
                yfit = np.polyval(p, xs)
                r2a = self._adjusted_r2(ys, yfit, 4)
                if r2a >= r2_thresh:
                    aa.append(float(p[0]))
                    bb.append(float(p[1]))
                    cc.append(float(p[2]))
                    dd.append(float(p[3]))
                    accepted += 1
        
        if len(aa) == 0:
            self._log(f"No fits with R²≥{r2_thresh:.2f}. Try other methods.", "ERROR")
            return
        
        a3 = float(np.mean(aa))
        a2 = float(np.mean(bb))
        a1 = float(np.mean(cc))
        a0 = float(np.mean(dd))
        
        if abs(a3) < 1e-16:
            self._log("Degenerate cubic after averaging", "ERROR")
            return
        
        x_poi = -a2 / (3.0 * a3)
        xn, yn, _ = self._nearest_on_series(x, y, x_poi)
        
        # Calculate second derivative for display
        try:
            # Second derivative: d²T/dt² from dT/dt
            ddy = np.gradient(dy, x)
        except Exception as e:
            self._log(f"Could not compute second derivative: {str(e)}", "WARNING")
            ddy = np.zeros_like(dy)
        
        # Clear canvas properly
        for ax_old in list(self.canvas_poi.figure.axes):
            self.canvas_poi.figure.delaxes(ax_old)
        ax = self.canvas_poi.figure.add_subplot(111)
        self.canvas_poi.ax = ax
        
        # Plot
        ax.set_title(f'POI / Derivative (Selective Fit - {accepted} fits)')
        ax.set_xlabel('Time')
        ax.set_ylabel(self.deriv_yname, color='b')
        ax.plot(x, y, 'b-', lw=2, label=self.deriv_yname)
        ax.tick_params(axis='y', labelcolor='b')
        
        # First derivative on first right axis
        ax2 = ax.twinx()
        deriv_label = 'dS/dt' if self.deriv_yname == 'Signal' else 'dT/dt'
        ax2.set_ylabel(deriv_label, color='r')
        ax2.plot(x, dy, 'r-', lw=1.5, label=deriv_label)
        ax2.tick_params(axis='y', labelcolor='r')
        
        # Second derivative on third y-axis (orange with outward positioning)
        ax3 = ax.twinx()
        # Offset the third axis to the right (increased offset for better visibility)
        ax3.spines['right'].set_position(('outward', 70))
        deriv2_label = 'd²S/dt²' if self.deriv_yname == 'Signal' else 'd²T/dt²'
        ax3.set_ylabel(deriv2_label, color='orange', fontsize=9)
        ax3.plot(x, ddy, '-', lw=1.5, color='orange', label=deriv2_label, alpha=0.7)
        ax3.tick_params(axis='y', labelcolor='orange')
        
        # Set custom y-limits for second derivative plot: (min, 5*max)
        d2_min = np.nanmin(ddy)
        d2_max = np.nanmax(ddy)
        if np.isfinite(d2_min) and np.isfinite(d2_max):
            ax3.set_ylim(d2_min, 5 * d2_max)
        
        # Adjust tick formatting for third axis to prevent overlap and improve visibility
        from matplotlib.ticker import MaxNLocator
        ax3.tick_params(axis='y', labelsize=8, pad=1, width=0.5, length=3)
        # Reduce number of ticks significantly and use scientific notation
        ax3.yaxis.set_major_locator(MaxNLocator(nbins=3, prune='both'))
        ax3.ticklabel_format(axis='y', style='sci', scilimits=(-1, 1), useMathText=True)
        # Adjust offset text (scientific notation multiplier) position and size
        ax3.yaxis.get_offset_text().set_fontsize(6)
        
        # Ensure the figure has enough space on the right for the third axis
        self.canvas_poi.figure.subplots_adjust(right=0.85)
        
        # Add markers for ts, te (squares) and tms, tme (triangles) on the blue plot
        # ts, te: squares (T start, T end - maxima of first derivative)
        x_ts, y_ts, _ = self._nearest_on_series(x, y, float(x[ts_idx]))
        x_te, y_te, _ = self._nearest_on_series(x, y, float(x[te_idx]))
        ax.scatter([x_ts], [y_ts], s=100, marker='s', c='orange', edgecolors='black', 
                   zorder=5, label='T start', linewidths=1.5)
        ax.scatter([x_te], [y_te], s=100, marker='s', c='green', edgecolors='black', 
                   zorder=5, label='T end', linewidths=1.5)
        
        # tms, tme: triangles (T melt start, T melt end - extrema of second derivative)
        x_tms, y_tms, _ = self._nearest_on_series(x, y, float(x[tms_idx]))
        x_tme, y_tme, _ = self._nearest_on_series(x, y, float(x[tme_idx]))
        ax.scatter([x_tms], [y_tms], s=100, marker='^', c='magenta', edgecolors='black', 
                   zorder=5, label='T melt start', linewidths=1.5)
        ax.scatter([x_tme], [y_tme], s=100, marker='v', c='magenta', edgecolors='black', 
                   zorder=5, label='T melt end', linewidths=1.5)
        
        # Averaged cubic fit (scale back if needed)
        x_fit = np.linspace(float(x[i1]), float(x[i2]), 300)
        y_fit = a3 * x_fit**3 + a2 * x_fit**2 + a1 * x_fit + a0
        if scale_factor != 1.0:
            y_fit = y_fit / scale_factor
        ax.plot(x_fit, y_fit, '--', lw=2, color='#800080', alpha=0.95, label=f'Avg Cubic ({accepted} fits)')
        
        # Mark POI
        ax.scatter([xn], [yn], s=120, c='#800080', marker='s', zorder=5, label='POI (Selective)')
        
        ax.grid(True, alpha=0.25)
        ax.xaxis.set_major_formatter(FuncFormatter(self._seconds_to_hhmmss))
        leg = ax.legend(loc='upper left', fontsize=8, ncol=2)
        if leg is not None:
            leg.set_draggable(True)
        
        self.canvas_poi.figure.tight_layout()
        self.canvas_poi.draw()
        
        # Store results
        self.results_data['Selective Fit']['POI'] = float(yn)
        self._update_results_table()
        
        # Log detailed results
        self._log(f"--- Selective Fit POI ---", "INFO")
        self._log(f"Accepted fits: {accepted} (attempted={attempted}, R²_thresh={r2_thresh:.3f})", "INFO")
        self._log(f"POI: x={xn:.6g}, {self.deriv_yname}={yn:.7g}", "SUCCESS")
        self._log(f"ts (start): idx={ts_idx}, x={x_ts:.6g}, {self.deriv_yname}={y_ts:.7g}", "INFO")
        self._log(f"te (end): idx={te_idx}, x={x_te:.6g}, {self.deriv_yname}={y_te:.7g}", "INFO")
        self._log(f"tms (melt start): idx={tms_idx}, x={x_tms:.6g}, {self.deriv_yname}={y_tms:.7g}", "INFO")
        self._log(f"tme (melt end): idx={tme_idx}, x={x_tme:.6g}, {self.deriv_yname}={y_tme:.7g}", "INFO")
    
    def compute_liquidus(self):
        """Compute liquidus based on selected method"""
        if self.temperature is None:
            self._log("Cannot compute liquidus: no data loaded", "WARNING")
            return
        
        method = self.cb_liq_method.currentText()
        self._log(f"Starting liquidus computation using method: {method}", "INFO")
        
        try:
            if method == 'Fraction Method':
                self._compute_liquidus_fraction()
            elif method == 'Intersection Method':
                self._compute_liquidus_intersection()
        except Exception as e:
            self._log(f"Liquidus computation failed: {str(e)}", "ERROR")
            import traceback
            self._log(traceback.format_exc(), "ERROR")
    
    def _compute_liquidus_fraction(self):
        """Liquidus by fraction method with power-law fit (CCT WG5 method)"""
        if self.temperature is None or self.time is None:
            self._log("Cannot compute liquidus fraction: no data loaded", "WARNING")
            return
        
        if self.deriv_y is None:
            self._log("Need derivative for fraction method. Compute derivative first.", "WARNING")
            return
        
        # Get POI from the selected method
        poi_method = self.cb_poi_method.currentText()
        if poi_method == 'CCT WG5':
            method_key = 'CCT WG5 method'
        else:
            method_key = poi_method
        
        poi_value = self.results_data[method_key].get('POI', None)
        if poi_value is None:
            self._log(f"POI not computed yet for {poi_method}. Compute POI first.", "WARNING")
            return
        
        # Use the same data type as derivative (Temperature or Signal)
        y_data = self.deriv_y  # This is already set to signal or temperature based on domain
        y_label = self.deriv_yname  # "Temperature" or "Signal"
        n = len(y_data)
        
        # Find peaks to determine melt start/end region (work in derivative space)
        try:
            peaks = self._find_two_peaks(self.deriv_x, self.deriv_dy, min_sep=200.0)
            if len(peaks) >= 2:
                i1, i2 = peaks
                if self.deriv_x[i1] > self.deriv_x[i2]:
                    i1, i2 = i2, i1
                # Use derivative indices directly (they're relative to deriv_y)
                ms_deriv = i1
                me_deriv = i2
            else:
                # Fallback: use middle 50% of derivative data
                ms_deriv = n // 4
                me_deriv = 3 * n // 4
        except Exception:
            ms_deriv = n // 4
            me_deriv = 3 * n // 4
        
        # Find POI index from the selected POI method's result (in derivative space)
        try:
            value_diffs = np.abs(y_data - poi_value)
            cct_ind_deriv = int(np.argmin(value_diffs))  # Index relative to derivative data
            # Make sure POI is within the melt region (in derivative space)
            if cct_ind_deriv < ms_deriv or cct_ind_deriv > me_deriv:
                self._log(f"POI at index {cct_ind_deriv} is outside melt region [{ms_deriv}, {me_deriv}] in derivative space, adjusting...", "WARNING")
                cct_ind_deriv = np.clip(cct_ind_deriv, ms_deriv, me_deriv)
        except Exception:
            cct_ind_deriv = (ms_deriv + me_deriv) // 2
        
        # Compute region-relative coordinates (in derivative space)
        region_size = me_deriv - ms_deriv + 1
        if region_size <= 0:
            self._log("Empty region for fraction method", "ERROR")
            return
        
        x_region = np.arange(0, region_size)
        frac = x_region / float(region_size)
        
        # Find starting point (fraction > 0.30 as per CCT WG5)
        mask = frac > 0.30
        if not np.any(mask):
            self._log("No fraction > 0.30 found in selected region", "WARNING")
            return
        first_idx_region = int(np.nonzero(mask)[0][0])
        
        # Convert POI index to region-relative (in derivative space)
        cct_ind_deriv = max(0, min(cct_ind_deriv, len(y_data) - 1))
        cct_ind_region = cct_ind_deriv - ms_deriv
        cct_ind_region = max(0, min(cct_ind_region, region_size - 1))
        
        # Extract fraction and values for fitting (from ~0.3 to POI) - all in derivative space
        xl = frac[first_idx_region:cct_ind_region+1]
        yl = y_data[ms_deriv + first_idx_region:ms_deriv + cct_ind_region+1]
        
        if len(xl) < 3:
            self._log(f"Not enough points for power-law fit: only {len(xl)} points between fraction 0.3 and POI (indices {ms_deriv + first_idx_region} to {ms_deriv + cct_ind_region} in derivative space)", "ERROR")
            return
        
        # Clear canvas and create subplots
        self.canvas_liquidus.figure.clear()
        ax_top = self.canvas_liquidus.figure.add_subplot(211)
        ax_bottom = self.canvas_liquidus.figure.add_subplot(212)
        self.canvas_liquidus.figure.subplots_adjust(hspace=0.5)
        
        # Top subplot: cropped time-series (in derivative space)
        crop_times = self.deriv_x[ms_deriv:me_deriv+1]
        crop_vals = y_data[ms_deriv:me_deriv+1]
        ax_top.plot(crop_times, crop_vals, color='b', lw=2, label=y_label)
        ax_top.set_ylabel(f"{y_label}, {'°C' if y_label == 'Temperature' else 'a.u.'}")
        ax_top.set_xlabel("Time, hh:mm:ss")
        ax_top.set_title("Liquidus (Fraction Method)")
        ax_top.legend()
        ax_top.grid(True, alpha=0.3)
        ax_top.xaxis.set_major_formatter(FuncFormatter(self._seconds_to_hhmmss))
        
        # Bottom subplot: fraction fit
        ax_bottom.plot(xl, yl, color='#1f77b4', lw=2, label="Fraction data")
        
        try:
            # Fit a*x^b using log-log linear regression
            mask_pos = (xl > 0) & np.isfinite(yl)
            if np.sum(mask_pos) < 3:
                raise ValueError('Not enough positive points for power-law fit')
            
            X = xl[mask_pos]
            Y = yl[mask_pos]
            
            Lx = np.log(X)
            Ly = np.log(Y)
            A = np.vstack([Lx, np.ones_like(Lx)]).T
            sol, _, _, _ = np.linalg.lstsq(A, Ly, rcond=None)
            b_est = float(sol[0])
            a_est = float(np.exp(sol[1]))
            
            # Generate full fraction array for plotting the fit (0.1 to 1.0)
            frac_full = np.linspace(0.1, 1.0, 300)
            funcl = a_est * (frac_full ** b_est)
            
            # Smart formatting for 'a' parameter
            a_str = f"{a_est:.5e}" if abs(a_est) < 0.001 and a_est != 0 else f"{a_est:.3f}"
            
            # Plot fit
            ax_bottom.plot(frac_full, funcl, color='#ff7f0e', lw=2, linestyle='--',
                          label=f"Fit: {y_label[0]} = a·F^b, a={a_str}, b={b_est:.5e}")
            
            # LIQUIDUS: Extrapolate to F = 1.0 (CCT WG5 method)
            liquidus_value = a_est * (1.0 ** b_est)  # equals a_est
            
            # Smart formatting for liquidus value
            liq_str = f"{liquidus_value:.5e}" if abs(liquidus_value) < 0.001 and liquidus_value != 0 else f"{liquidus_value:.3f}"
            
            # Mark liquidus on fraction plot at F=1.0
            ax_bottom.scatter([1.0], [liquidus_value], c='r', s=80, zorder=5, marker='*',
                            label=f"Liquidus (F=1.0): {liq_str}")
            
            # Find corresponding point on time-series (in derivative space)
            value_region = y_data[ms_deriv:me_deriv+1]
            time_region = self.deriv_x[ms_deriv:me_deriv+1]
            diffs = np.abs(value_region - liquidus_value)
            liq_idx_region = int(np.argmin(diffs))
            
            # Mark liquidus on top time-series plot
            ax_top.scatter([time_region[liq_idx_region]], [value_region[liq_idx_region]],
                          c='r', s=60, zorder=5, label=f"Liquidus: {liq_str}")
            
            # Formatting bottom plot
            ax_bottom.set_xlabel("Fraction")
            ax_bottom.set_ylabel(f"{y_label}, {'°C' if y_label == 'Temperature' else 'a.u.'}")
            ax_bottom.set_title("Power-Law Fit (CCT WG5)")
            ax_bottom.grid(True, alpha=0.3)
            ax_bottom.legend()
            
            # Update top plot legend
            ax_top.legend()
            
            self.canvas_liquidus.draw()
            
            # Log results
            poi_frac = cct_ind_region / float(region_size)
            poi_val_str = f"{poi_value:.5e}" if abs(poi_value) < 0.001 and poi_value != 0 else f"{poi_value:.4f}"
            self._log(f"Fraction Method (using {poi_method} POI): ms_deriv={ms_deriv}, me_deriv={me_deriv}, region_size={region_size}", "INFO")
            self._log(f"POI: deriv_idx={cct_ind_deriv}, region_idx={cct_ind_region}, fraction={poi_frac:.3f}, value={poi_val_str}", "INFO")
            self._log(f"Fit: a={a_est:.6g}, b={b_est:.6g}", "INFO")
            self._log(f"Liquidus (F=1.0): {liquidus_value:.6g}", "SUCCESS")
            
            # Store results - only for the selected POI method
            self.results_data[method_key]['Liquidus Fraction'] = float(liquidus_value)
            self._update_results_table()
            
        except Exception as e:
            self._log(f"Liquidus fit error: {str(e)}", "ERROR")
            import traceback
            self._log(traceback.format_exc(), "ERROR")
    
    def _compute_liquidus_intersection(self):
        """Liquidus by intersection method: fit midrange and end lines, find intersection"""
        if self.temperature is None or self.deriv_y is None:
            self._log("Cannot compute liquidus intersection: need data and derivative", "WARNING")
            return
        
        x = self.deriv_x if self.deriv_x is not None else self.time
        y = self.deriv_y if self.deriv_y is not None else self.temperature
        y_label = self.deriv_yname if hasattr(self, 'deriv_yname') else "Temperature"
        n = len(y)
        
        # Find peaks to determine melt start/end (if available)
        try:
            peaks = self._find_two_peaks(x, self.deriv_dy, min_sep=200.0)
            if len(peaks) >= 2:
                i1, i2 = peaks
                if x[i1] > x[i2]:
                    i1, i2 = i2, i1
                ms, me = i1, i2
            else:
                # Fallback: use middle portions
                ms = n // 4
                me = 3 * n // 4
        except Exception:
            ms = n // 4
            me = 3 * n // 4
        
        # Quartile offset for midrange
        dist = abs(me - ms)
        qu = max(1, int(round(dist / 4.0)))
        s = max(ms + qu, 0)
        e = min(me - qu, n - 1)
        
        if e <= s:
            self._log("Invalid midrange after quartile offset", "ERROR")
            return
        
        # Fit midrange line
        x1 = x[s:e+1]
        y1 = y[s:e+1]
        try:
            p1 = np.polyfit(x1, y1, 1)
        except Exception as ex:
            self._log(f"Midrange linear fit failed: {ex}", "ERROR")
            return
        
        # Fit end segment near ME
        i2s = me
        i2e = min(me + 3, n - 1)
        if i2e <= i2s:
            i2s = max(me - 1, 0)
            i2e = me
        x2 = x[i2s:i2e+1]
        y2 = y[i2s:i2e+1]
        
        if len(x2) < 2:
            self._log("Not enough points for end segment", "ERROR")
            return
        
        try:
            p2 = np.polyfit(x2, y2, 1)
        except Exception as ex:
            self._log(f"End segment linear fit failed: {ex}", "ERROR")
            return
        
        # Find line intersection
        P1 = (x1[0], np.polyval(p1, x1[0]))
        P2 = (x1[-1], np.polyval(p1, x1[-1]))
        P3 = (x2[0], np.polyval(p2, x2[0]))
        P4 = (x2[-1], np.polyval(p2, x2[-1]))
        xi, yi = self._line_intersection(P1, P2, P3, P4)
        
        if not (np.isfinite(xi) and np.isfinite(yi)):
            self._log("Lines are parallel or intersection failed", "ERROR")
            return
        
        # Get the selected POI method to get POI value
        poi_method = self.cb_poi_method.currentText()
        if poi_method == 'CCT WG5':
            method_key = 'CCT WG5 method'
        else:
            method_key = poi_method
        
        poi_value = self.results_data[method_key].get('POI', None)
        if poi_value is None:
            self._log(f"POI not computed yet for {poi_method}. Compute POI first.", "WARNING")
            return
        
        # Calculate midpoint between intersection and POI
        liq_intersection = float((yi + poi_value) / 2.0)
        
        # Clear canvas properly
        for ax_old in list(self.canvas_liquidus.figure.axes):
            self.canvas_liquidus.figure.delaxes(ax_old)
        ax = self.canvas_liquidus.figure.add_subplot(111)
        
        # Plot
        ax.set_title('Liquidus (Intersection Method)')
        ax.set_xlabel('Time, hh:mm:ss')
        ax.set_ylabel(f'{y_label} ({"°C" if y_label == "Temperature" else "a.u."})')
        ax.plot(x, y, 'b-', lw=2, label=y_label)
        
        # Plot fitted lines
        xs1 = np.linspace(min(x.min(), xi - 50), max(x1.max(), xi + 50), 200)
        ax.plot(xs1, np.polyval(p1, xs1), 'g-', lw=2, label='Midrange line', alpha=0.7)
        
        xs2 = np.linspace(min(x2.min(), xi - 50), max(x.max(), xi + 50), 200)
        ax.plot(xs2, np.polyval(p2, xs2), 'c-', lw=2, label='End line', alpha=0.7)
        
        # Smart formatting for plot labels
        yi_str = f"{yi:.5e}" if abs(yi) < 0.001 and yi != 0 else f"{yi:.3f}"
        poi_str = f"{poi_value:.5e}" if abs(poi_value) < 0.001 and poi_value != 0 else f"{poi_value:.3f}"
        liq_str = f"{liq_intersection:.5e}" if abs(liq_intersection) < 0.001 and liq_intersection != 0 else f"{liq_intersection:.3f}"
        
        # Mark intersection point
        ax.scatter([xi], [yi], s=120, c='magenta', marker='o', zorder=5, label=f'Intersection: {yi_str}')
        
        # Mark POI value on the plot (find closest point)
        poi_diffs = np.abs(y - poi_value)
        poi_idx = int(np.argmin(poi_diffs))
        ax.scatter([x[poi_idx]], [y[poi_idx]], s=120, c='green', marker='s', zorder=5, label=f'POI: {poi_str}')
        
        # Mark liquidus (midpoint)
        liq_diffs = np.abs(y - liq_intersection)
        liq_idx = int(np.argmin(liq_diffs))
        ax.scatter([x[liq_idx]], [y[liq_idx]], s=140, c='red', marker='*', zorder=6, label=f'Liquidus: {liq_str}')
        
        ax.grid(True, alpha=0.25)
        ax.xaxis.set_major_formatter(FuncFormatter(self._seconds_to_hhmmss))
        leg = ax.legend(loc='best')
        leg.set_draggable(True)
        self.canvas_liquidus.figure.tight_layout()
        self.canvas_liquidus.draw()
        
        # Save initial limits for zoom reset
        self.canvas_liquidus._save_initial_limits()
        
        # Store results - only for the selected POI method
        self.results_data[method_key]['Liquidus Intersection'] = float(liq_intersection)
        self._update_results_table()
        
        # Smart formatting for logger
        self._log(f"Liquidus (Intersection): Intersection={yi_str}, POI={poi_str}, Midpoint={liq_str}", "SUCCESS")
    
    def _update_results_table(self):
        """Update the results table with current data"""
        for row, method in enumerate(['CCT WG5', '3rd Degree Polynomial', 'Selective Fit']):
            for col, key in enumerate(['POI', 'Liquidus Fraction', 'Liquidus Intersection', 'Melt Range']):
                # Map display name to data key
                if method == 'CCT WG5':
                    method_key = 'CCT WG5 method'
                else:
                    method_key = method
                value = self.results_data[method_key][key]
                
                # Convert temperature for display if needed (for POI, Liquidus columns)
                if value is not None and key in ['POI', 'Liquidus Fraction', 'Liquidus Intersection']:
                    # Values are stored in the same unit as loaded data
                    # Convert to display unit if different
                    if self.data_unit_kelvin and self.temp_unit_celsius:
                        # Data is in K, display in °C
                        value = value - 273.15
                    elif not self.data_unit_kelvin and not self.temp_unit_celsius:
                        # Data is in °C, display in K
                        value = value + 273.15
                    # If both are same unit, no conversion needed
                
                # Smart formatting: use scientific notation for very small values
                if value is not None:
                    if abs(value) < 0.001 and value != 0:
                        # Use scientific notation for very small values
                        text = f"{value:.5e}"
                    else:
                        # Use fixed-point notation for normal values
                        text = f"{value:.3f}"
                else:
                    text = "-"
                
                item = QTableWidgetItem(text)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.results_table.setItem(row, col, item)
    
    def toggle_temp_unit(self):
        """Toggle between Kelvin and Celsius for temperature display"""
        self.temp_unit_celsius = not self.temp_unit_celsius
        
        # Update button text
        if self.temp_unit_celsius:
            self.btn_temp_unit.setText("°C")
            self._log("Display unit changed to Celsius", "INFO")
        else:
            self.btn_temp_unit.setText("K")
            self._log("Display unit changed to Kelvin", "INFO")
        
        # Update the results table with new unit
        self._update_results_table()
    
    def on_data_unit_changed(self, unit_text):
        """Handle change in input data temperature unit"""
        old_unit_kelvin = self.data_unit_kelvin
        self.data_unit_kelvin = (unit_text == "K")
        
        if self.temperature is not None and old_unit_kelvin != self.data_unit_kelvin:
            # Only update the unit flag, do not convert the actual data values
            self._log(f"Data unit indicator changed to {unit_text} (data values unchanged)", "INFO")
            
            # Update plots with new unit label
            self.update_main_plot()
            if self.deriv_y is not None:
                self._log("Data unit label changed - derivative still valid", "INFO")
    
    def _find_two_peaks(self, x, dy, min_sep=200.0):
        """Find indices of two highest peaks in derivative, separated by min_sep"""
        vals = np.nan_to_num(dy, nan=-np.inf)
        order = np.argsort(vals)[::-1]
        peaks = []
        for idx in order:
            if not np.isfinite(vals[idx]):
                continue
            cand_x = float(x[idx])
            ok = True
            for p_idx in peaks:
                if abs(cand_x - float(x[p_idx])) < min_sep:
                    ok = False
                    break
            if ok:
                peaks.append(int(idx))
            if len(peaks) >= 2:
                break
        return peaks
    
    def _nearest_on_series(self, xs, ys, x0):
        """Find nearest y value at given x on series"""
        idx = int(np.abs(xs - x0).argmin())
        return float(xs[idx]), float(ys[idx]), idx
    
    def _adjusted_r2(self, y_true, y_fit, p):
        """Calculate adjusted R² for model with p parameters"""
        y = np.asarray(y_true)
        f = np.asarray(y_fit)
        n = len(y)
        if n <= p + 1:
            return -np.inf
        ss_res = float(np.sum((f - y) ** 2))
        ss_tot = float(np.sum((y - np.mean(y)) ** 2))
        if ss_tot == 0:
            return -np.inf
        r2 = 1.0 - ss_res / ss_tot
        return 1.0 - (1.0 - r2) * (n - 1) / (n - p - 1)
    
    def _line_intersection(self, p1, p2, p3, p4):
        """Find intersection of two lines defined by points p1-p2 and p3-p4"""
        x1, y1 = p1
        x2, y2 = p2
        x3, y3 = p3
        x4, y4 = p4
        den = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
        if abs(den) < 1e-15:
            return np.nan, np.nan
        xi = ((x1 * y2 - y1 * x2) * (x3 - x4) - (x1 - x2) * (x3 * y4 - y3 * x4)) / den
        yi = ((x1 * y2 - y1 * x2) * (y3 - y4) - (y1 - y2) * (x3 * y4 - y3 * x4)) / den
        return float(xi), float(yi)
    
    def _detect_ts_te_tms_tme(self, xdata, ydata, x_peak1, x_peak2):
        """
        Detect ts, te, tms, tme indices based on derivative extrema.
        ts, te: indices of first derivative maxima (melt start/end)
        tms, tme: indices of second derivative extrema (inflection points)
        
        Returns: (ts_idx, te_idx, tms_idx, tme_idx)
        """
        # Calculate first derivative
        d1 = np.gradient(ydata, xdata)
        
        # Calculate second derivative
        d2 = np.gradient(d1, xdata)
        
        # Find ts and te: maxima of first derivative near the peaks
        # Search in a window around each peak
        search_window = int(len(xdata) * 0.1)  # 10% of data length
        
        # ts: maximum of first derivative near peak1
        peak1_idx = int(np.abs(xdata - x_peak1).argmin())
        ts_start = max(0, peak1_idx - search_window)
        ts_end = min(len(xdata), peak1_idx + search_window)
        ts_region = d1[ts_start:ts_end]
        ts_idx = ts_start + int(np.argmax(ts_region))
        
        # te: maximum of first derivative near peak2
        peak2_idx = int(np.abs(xdata - x_peak2).argmin())
        te_start = max(0, peak2_idx - search_window)
        te_end = min(len(xdata), peak2_idx + search_window)
        te_region = d1[te_start:te_end]
        te_idx = te_start + int(np.argmax(te_region))
        
        # tms: minimum of second derivative (left inflection)
        # Search between ts and midpoint
        mid_idx = (ts_idx + te_idx) // 2
        tms_region = d2[ts_idx:mid_idx]
        if len(tms_region) > 0:
            tms_idx = ts_idx + int(np.argmin(tms_region))
        else:
            tms_idx = ts_idx
        
        # tme: maximum of second derivative (right inflection)
        # Search between midpoint and te
        tme_region = d2[mid_idx:te_idx]
        if len(tme_region) > 0:
            tme_idx = mid_idx + int(np.argmax(tme_region))
        else:
            tme_idx = te_idx
        
        return ts_idx, te_idx, tms_idx, tme_idx
    
    def on_clear_results(self):
        """Clear all results"""
        self.results_table.clearContents()
        for method in self.results_data:
            for key in self.results_data[method]:
                self.results_data[method][key] = None

