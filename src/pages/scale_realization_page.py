
import numpy as np
import pandas as pd
from datetime import datetime
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox, 
    QGroupBox, QFormLayout, QSpinBox, QDoubleSpinBox, QCheckBox, 
    QSplitter, QTabWidget, QTextEdit, QLineEdit, QFileDialog, QMessageBox,
    QSizePolicy, QScrollArea, QGridLayout, QFrame, QDialog, QTableWidget, 
    QTableWidgetItem, QHeaderView, QApplication, QMenu, QStackedWidget,
    QRadioButton, QButtonGroup
)
from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtGui import QFont, QColor, QKeyEvent, QKeySequence, QAction

from plot_canvas import PlotCanvas
from theme_manager import ThemeManager

class FixedPointPopup(QDialog):
    """Popup dialog for fixed point table"""
    def __init__(self, table_widget, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        layout = QVBoxLayout()
        layout.addWidget(table_widget)
        
        # Add Close button
        btn_close = QPushButton("Close")
        btn_close.clicked.connect(self.accept)
        btn_close.setStyleSheet("background-color: #d32f2f; color: white; font-weight: bold; padding: 5px;")
        layout.addWidget(btn_close)
        
        self.setLayout(layout)
        self.resize(700, 450)
        
        # Optional: Add border
        self.setStyleSheet("QDialog { border: 2px solid #555; }")

class PasteableTableWidget(QTableWidget):
    """QTableWidget that supports pasting data from Excel/Clipboard"""
    
    rows_pasted = Signal()
    row_add_requested = Signal()
    row_remove_requested = Signal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)
        
    def show_context_menu(self, pos):
        menu = QMenu(self)
        
        add_action = QAction("Add Fixed Point Row", self)
        add_action.triggered.connect(self.row_add_requested.emit)
        menu.addAction(add_action)
        
        remove_action = QAction("Delete Selected Row(s)", self)
        remove_action.triggered.connect(self.row_remove_requested.emit)
        if not self.selectedRanges():
            remove_action.setEnabled(False)
        menu.addAction(remove_action)
        
        menu.exec(self.mapToGlobal(pos))
    
    def keyPressEvent(self, event: QKeyEvent):
        if event.matches(QKeySequence.Paste):
            self.paste_from_clipboard()
        else:
            super().keyPressEvent(event)
            
    def paste_from_clipboard(self):
        clipboard = QApplication.clipboard()
        text = clipboard.text()
        
        if not text:
            return
            
        # Get start row/col
        selected_ranges = self.selectedRanges()
        if not selected_ranges:
            # Fallback to current item logic if no range selection
            current_row = self.currentRow()
            current_col = self.currentColumn()
            if current_row < 0: current_row = 0
            if current_col < 0: current_col = 0
        else:
            current_row = selected_ranges[0].topRow()
            current_col = selected_ranges[0].leftColumn()
            
        rows = text.strip('\n').split('\n')
        
        # Determine if we need to add more rows
        needed_rows = current_row + len(rows)
        if needed_rows > self.rowCount():
             self.setRowCount(needed_rows)
        
        # Iterate over clipboard rows
        for i, row_text in enumerate(rows):
            columns = row_text.split('\t')
            for j, col_text in enumerate(columns):
                r = current_row + i
                c = current_col + j
                
                if c < self.columnCount():
                    item = self.item(r, c)
                    if not item:
                         self.setItem(r, c, QTableWidgetItem(col_text.strip()))
                    else:
                         item.setText(col_text.strip())
                         
        # Emit signal to let parent know to fix missing widgets
        self.rows_pasted.emit()

class SakumaResultDialog(QDialog):
    """Popup dialog for Sakuma-Hattori fit results"""
    def __init__(self, title, params_dict, parent=None, on_push_callback=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setWindowFlags(Qt.Dialog | Qt.WindowCloseButtonHint)
        self.resize(400, 300)
        self.params_dict = params_dict
        self.on_push_callback = on_push_callback
        
        layout = QVBoxLayout()
        
        # Title
        title_lbl = QLabel(title)
        title_lbl.setStyleSheet("font-weight: bold; color: #4caf50; font-size: 12pt; margin-bottom: 10px;")
        title_lbl.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_lbl)
        
        # Grid for results
        grid = QGridLayout()
        row = 0
        col = 0
        
        for key, value in params_dict.items():
            lbl = QLabel(f"{key}:")
            lbl.setStyleSheet("font-weight: bold; font-size: 10pt;")
            val_lbl = QLabel(f"{value}")
            val_lbl.setStyleSheet("font-size: 10pt;")
            val_lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
            grid.addWidget(lbl, row, col * 2)
            grid.addWidget(val_lbl, row, col * 2 + 1)
            col += 1
            if col > 1:
                col = 0
                row += 1
        
        layout.addLayout(grid)
        layout.addStretch()
        
        # Button row
        btn_row = QHBoxLayout()
        
        if on_push_callback is not None:
            btn_push = QPushButton("Send to SSE Correction Page")
            btn_push.setStyleSheet("background-color: #1565c0; color: white; font-weight: bold; padding: 5px;")
            btn_push.clicked.connect(self._do_push)
            btn_row.addWidget(btn_push)
        
        btn_close = QPushButton("Close")
        btn_close.clicked.connect(self.accept)
        btn_row.addWidget(btn_close)
        
        layout.addLayout(btn_row)
        self.setLayout(layout)
    
    def _do_push(self):
        """Extract a, b, c, c2 from params and call the callback"""
        try:
            vals = {}
            for key, val_str in self.params_dict.items():
                k = key.strip().lower().rstrip(" (fixed)(fitted)")
                try:
                    vals[k] = float(val_str.split()[0])
                except (ValueError, IndexError):
                    pass
            if self.on_push_callback:
                self.on_push_callback(vals)
                self.accept()
        except Exception as e:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Error", f"Could not push values: {e}")


class ScaleRealizationPage(QWidget):
    """Scale Realization page with ITS-90 and Sakuma-Hattori fitting"""
    
    def __init__(self, theme_name="Nord Dark", corrections_page=None):
        super().__init__()
        self.theme_name = theme_name
        self.theme = ThemeManager.get_theme(theme_name)
        self.corrections_page = corrections_page
        
        # Data storage
        self.wavelength = None
        self.spectral_resp = None
        self.temperatures = None
        self.signals = None
        self.c2 = 14388  # Default c2 value
        self.last_sakuma_results = None # Store last fit results
        
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout()
        
        # Header
        header = QLabel("📏 Scale Realization - ITS-90 & Sakuma-Hattori")
        header.setFont(QFont("Arial", 16, QFont.Bold))
        layout.addWidget(header)
        
        # Create vertical splitter for tabs and logger
        splitter = QSplitter(Qt.Vertical)
        
        # Tabs
        tabs = QTabWidget()
        
        # Tab 1: Data Input
        input_tab = self.create_input_tab()
        tabs.addTab(input_tab, "📊 Data Input")
        
        # Tab 2: Sakuma-Hattori (swapped position with ITS-90)
        sakuma_tab = self.create_sakuma_tab()
        tabs.addTab(sakuma_tab, "🔬 Sakuma-Hattori")
        
        # Tab 3: ITS-90 Fit
        its90_tab = self.create_its90_tab()
        tabs.addTab(its90_tab, "🌡️ ITS-90 Fit")

        # Tab 4: Converter
        converter_tab = self.create_converter_tab()
        tabs.addTab(converter_tab, "🔄 Converter")

        splitter.addWidget(tabs)
        
        # Add logger at the bottom
        logger_box = QGroupBox("Console / Log")
        logger_layout = QVBoxLayout()
        self.scale_log_console = QTextEdit()
        self.scale_log_console.setReadOnly(True)
        self.scale_log_console.setMinimumHeight(60)  # Minimum instead of maximum
        self.scale_log_console.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #d4d4d4;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 10pt;
                border: 1px solid #5c6bc0;
            }
        """)
        logger_layout.addWidget(self.scale_log_console)
        
        # Clear button for log
        btn_clear_log = QPushButton("🗑️ Clear Log")
        btn_clear_log.clicked.connect(lambda: self.scale_log_console.clear())
        logger_layout.addWidget(btn_clear_log)
        
        logger_box.setLayout(logger_layout)
        splitter.addWidget(logger_box)
        
        # Set initial sizes (tabs get more space than logger)
        splitter.setSizes([600, 100])
        
        layout.addWidget(splitter, stretch=1)
        
        self.setLayout(layout)
    
    def _log(self, message, level="INFO"):
        """Log message to console"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        color_map = {"INFO": "white", "SUCCESS": "green", "ERROR": "red", "WARNING": "orange"}
        color = color_map.get(level, "white")
        self.scale_log_console.append(f'<span style="color: {color};">[{timestamp}] {level}: {message}</span>')
    
    def _format_temp(self, temp_value):
        """Format temperature value without trailing zeros"""
        # Format with high precision, then strip trailing zeros
        temp_str = f"{float(temp_value):.10f}"
        temp_str = temp_str.rstrip('0').rstrip('.')
        return temp_str
    
    def create_input_tab(self):
        widget = QWidget()
        main_layout = QHBoxLayout()
        
        # Left side - Controls
        left_layout = QVBoxLayout()
        
        # Spectral Response Section
        spec_box = QGroupBox("Spectral Responsivity Curve")
        spec_layout = QVBoxLayout()
        
        btn_layout = QHBoxLayout()
        self.btn_load_spec = QPushButton("📁 Load Wavelength & Spectral Response")
        self.btn_load_spec.clicked.connect(self.load_spectral_data)
        self.btn_use_default_spec = QPushButton("⚙️ Use Default (High Temp)")
        self.btn_use_default_spec.clicked.connect(self.use_default_spectral)
        btn_layout.addWidget(self.btn_load_spec)
        # btn_layout.addWidget(self.btn_use_default_spec) - button removed
        spec_layout.addLayout(btn_layout)
        
        self.spec_info_label = QLabel("No spectral data loaded")
        spec_layout.addWidget(self.spec_info_label)
        
        spec_box.setLayout(spec_layout)
        left_layout.addWidget(spec_box)
        
        # Calibration Data Section
        cal_box = QGroupBox("Temperature-Signal Calibration Data")
        cal_layout = QVBoxLayout()
        
        cal_btn_layout = QHBoxLayout()
        self.btn_load_cal = QPushButton("📁 Load Temperature & Signal Data")
        self.btn_load_cal.clicked.connect(self.load_calibration_data)
        # self.btn_use_default_cal button removed - no default data
        self.btn_manual_input = QPushButton("✏️ Manual Input")
        self.btn_manual_input.clicked.connect(self.manual_input_data)
        cal_btn_layout.addWidget(self.btn_load_cal)
        # self.btn_use_default_cal button removed - no default data
        cal_btn_layout.addWidget(self.btn_manual_input)
        cal_layout.addLayout(cal_btn_layout)
        
        self.cal_info_label = QLabel("No calibration data loaded")
        cal_layout.addWidget(self.cal_info_label)
        
        cal_box.setLayout(cal_layout)
        left_layout.addWidget(cal_box)
        
        # Parameters
        param_box = QGroupBox("Parameters")
        param_layout = QFormLayout()
        
        self.sakuma_c2_edit = QLineEdit("14388")
        param_layout.addRow("c₂ (μm·K):", self.sakuma_c2_edit)
        
        param_box.setLayout(param_layout)
        left_layout.addWidget(param_box)
        
        # Sigma calculation from spectral data
        sigma_calc_box = QGroupBox("σ Calculation from Spectral Data")
        sigma_calc_layout = QFormLayout()
        
        self.sigma_dist_combo = QComboBox()
        self.sigma_dist_combo.addItems(["Rect", "Tri", "Gauss", "STri", "2Delta"])
        self.sigma_dist_combo.setCurrentText("Rect")
        self.sigma_dist_combo.currentIndexChanged.connect(self.calculate_sigma_from_spectral)
        sigma_calc_layout.addRow("Distribution Type:", self.sigma_dist_combo)
        
        btn_calc_sigma = QPushButton("Calculate σ from Spectral Data")
        btn_calc_sigma.clicked.connect(self.calculate_sigma_from_spectral)
        sigma_calc_layout.addRow(btn_calc_sigma)
        
        self.sigma_calc_label = QLabel("σ will be calculated from FWHM")
        self.sigma_calc_label.setWordWrap(True)
        self.sigma_calc_label.setStyleSheet("color: gray; font-size: 9pt;")
        sigma_calc_layout.addRow(self.sigma_calc_label)
        
        # Add sigma input field
        self.sakuma_sigma_edit = QLineEdit("0.0085")
        sigma_calc_layout.addRow("σ (μm):", self.sakuma_sigma_edit)
        
        sigma_info = QLabel("Used for Sakuma-Hattori fitting (n=1,2)")
        sigma_info.setStyleSheet("color: gray; font-size: 9pt;")
        sigma_calc_layout.addRow(sigma_info)
        
        sigma_calc_box.setLayout(sigma_calc_layout)
        left_layout.addWidget(sigma_calc_box)
        
        # Plot buttons
        btn_layout = QHBoxLayout()
        btn_preview = QPushButton("📈 Update Preview")
        btn_preview.clicked.connect(self.update_input_preview)
        btn_layout.addWidget(btn_preview)
        
        btn_plot_spectral = QPushButton("📊 Plot Spectral Responsivity")
        btn_plot_spectral.clicked.connect(self.plot_spectral_responsivity)
        btn_layout.addWidget(btn_plot_spectral)
        
        left_layout.addLayout(btn_layout)
        
        left_layout.addStretch()
        
        # Right side - Plot
        right_layout = QVBoxLayout()
        self.input_canvas = PlotCanvas("Data Preview", theme_name=self.theme_name)
        right_layout.addWidget(self.input_canvas)
        
        # Add to main layout
        main_layout.addLayout(left_layout, stretch=1)
        main_layout.addLayout(right_layout, stretch=2)
        
        widget.setLayout(main_layout)
        return widget
    
    def create_its90_tab(self):
        widget = QWidget()
        main_layout = QHBoxLayout()
        
        # Left side - Parameters
        left_layout = QVBoxLayout()
        
        # Parameters
        param_box = QGroupBox("ITS-90 Fitting Parameters")
        param_layout = QFormLayout()
        
        self.c2_edit = QLineEdit("14388")
        param_layout.addRow("c₂ (μm·K):", self.c2_edit)
        
        self.its90_ref_temp_edit = QLineEdit("1357.802")
        param_layout.addRow("Reference Temp (K):", self.its90_ref_temp_edit)
        
        self.its90_ref_signal_edit = QLineEdit("2.6772e-10")
        param_layout.addRow("Reference Signal:", self.its90_ref_signal_edit)
        
        self.its90_gain_edit = QLineEdit("1.0")
        param_layout.addRow("Gain:", self.its90_gain_edit)
        
        self.its90_tstart_edit = QLineEdit("1000")
        param_layout.addRow("T Start (K):", self.its90_tstart_edit)
        
        self.its90_tstop_edit = QLineEdit("3500")
        param_layout.addRow("T Stop (K):", self.its90_tstop_edit)
        
        self.its90_tstep_edit = QLineEdit("10")
        param_layout.addRow("T Step (K):", self.its90_tstep_edit)
        
        param_box.setLayout(param_layout)
        left_layout.addWidget(param_box)
        
        # Fit button
        btn_fit = QPushButton("🔍 Perform ITS-90 Fit")
        btn_fit.clicked.connect(self.perform_its90_fit)
        left_layout.addWidget(btn_fit)
        
        # Results
        result_box = QGroupBox("Fit Results")
        result_layout = QVBoxLayout()
        self.its90_result_label = QLabel("Coefficients: -")
        self.its90_result_label.setWordWrap(True)
        result_layout.addWidget(self.its90_result_label)
        result_box.setLayout(result_layout)
        left_layout.addWidget(result_box)
        
        left_layout.addStretch()
        
        # Right side - Plot
        right_layout = QVBoxLayout()
        self.its90_canvas = PlotCanvas("ITS-90 Error Plot", theme_name=self.theme_name)
        right_layout.addWidget(self.its90_canvas)
        
        # Add to main layout
        main_layout.addLayout(left_layout, stretch=1)
        main_layout.addLayout(right_layout, stretch=2)
        
        widget.setLayout(main_layout)
        return widget
    
    def create_sakuma_tab(self):
        widget = QWidget()
        widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        main_layout = QHBoxLayout()
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(5, 5, 5, 5)
        
        # Left side - Parameters
        left_layout = QVBoxLayout()
        left_layout.setSpacing(8)
        
        # Info
        info_label = QLabel("Sakuma-Hattori Fitting - Select Fixed Points")
        info_label.setFont(QFont("Arial", 11, QFont.Bold))
        left_layout.addWidget(info_label)
        
        # Fixed Points Selection
        fp_box = QGroupBox("Fixed Points Selection")
        fp_main_layout = QVBoxLayout()
        
        # Add/Remove buttons FIRST (at top)
        btn_layout = QHBoxLayout()
        btn_add_fp = QPushButton("➕ Add Fixed Point")
        btn_add_fp.clicked.connect(self.add_new_fixed_point)
        btn_layout.addWidget(btn_add_fp)
        
        btn_remove_fp = QPushButton("➖ Remove Selected")
        btn_remove_fp.clicked.connect(self.remove_selected_fixed_points)
        btn_layout.addWidget(btn_remove_fp)
        
        fp_main_layout.addLayout(btn_layout)
        
        # Table for fixed points
        # Table for fixed points (create but don't add to layout yet)
        self.fp_table = PasteableTableWidget()
        self.fp_table.rows_pasted.connect(self.initialize_new_rows)
        self.fp_table.setColumnCount(5)
        self.fp_table.setHorizontalHeaderLabels(["Sel", "Name", "Temperature (K)", "Signal", "ITS-90"])
        self.fp_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.fp_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.fp_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        
        # Improve readability
        self.fp_table.verticalHeader().setDefaultSectionSize(35) # Taller rows
        self.fp_table.setAlternatingRowColors(True)
        self.fp_table.setColumnWidth(2, 140) # Temperature
        self.fp_table.setColumnWidth(3, 120) # Signal

        # Load fixed point library
        self.load_fixed_point_library()
        
        # Create Popup Container
        self.fp_popup = FixedPointPopup(self.fp_table, self)
        
        # UI Elements for Main Page
        
        # Summary Label
        self.fp_cnt_label = QLabel("0 fixed points selected")
        self.fp_cnt_label.setStyleSheet("font-weight: bold; color: #555;")
        fp_main_layout.addWidget(self.fp_cnt_label)
        
        # Open Editor Button
        self.btn_open_fp = QPushButton("Select / Edit Fixed Points")
        self.btn_open_fp.setMinimumHeight(40)
        self.btn_open_fp.setStyleSheet("font-size: 11pt; font-weight: bold;")
        self.btn_open_fp.clicked.connect(self.show_fp_popup)
        fp_main_layout.addWidget(self.btn_open_fp)
        
        # Connect table changes to summary update
        self.fp_table.rows_pasted.connect(self.update_sakuma_mode)
        self.fp_table.itemChanged.connect(lambda: self.update_sakuma_mode()) # Update if user types
        
        # Connect Context Menu Signals
        self.fp_table.row_add_requested.connect(self.add_new_fixed_point)
        self.fp_table.row_remove_requested.connect(self.remove_selected_fixed_points)
        
        # Also need detailed signals for widgets inside cells?
        # Ideally update_sakuma_mode is called when anything impactful changes.
        # Checkboxes inside cells already connect to update_sakuma_mode.
        
        # Start with no fixed points - user will add them or load from calibration data
        

        
        fp_box.setLayout(fp_main_layout)
        fp_box.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        left_layout.addWidget(fp_box, stretch=0)
        
        # Mode indicator
        self.sakuma_mode_label = QLabel("Mode: Select 1-3 or >3 fixed points")
        self.sakuma_mode_label.setStyleSheet("color: blue; font-weight: bold;")
        left_layout.addWidget(self.sakuma_mode_label)
        
        # ITS-90 checkbox (for Ag, Au, Cu fixed points)
        self.its90_checkbox_box = QGroupBox("ITS-90 Option")
        its90_layout = QVBoxLayout()
        self.its90_checkbox = QCheckBox("Use ITS-90")
        self.its90_checkbox.setChecked(False)
        self.its90_checkbox.stateChanged.connect(self.on_its90_checkbox_changed)
        its90_layout.addWidget(self.its90_checkbox)
        self.its90_checkbox_box.setLayout(its90_layout)
        self.its90_checkbox_box.setVisible(False)  # Hidden by default
        left_layout.addWidget(self.its90_checkbox_box)
        
        # Initial guess box with dynamic fields (2-column layout)
        self.guess_box = QGroupBox("Initial Guess")
        guess_main_layout = QVBoxLayout()
        
        # Mode Selector (Radio Buttons "Switch")
        mode_layout = QHBoxLayout()
        mode_layout.addWidget(QLabel("Mode:"))
        
        self.mode_phys_radio = QRadioButton("Physical Parameters")
        self.mode_coeff_radio = QRadioButton("Coefficients")
        self.mode_phys_radio.setChecked(True) # Default
        
        self.mode_group = QButtonGroup()
        self.mode_group.addButton(self.mode_phys_radio, 0)
        self.mode_group.addButton(self.mode_coeff_radio, 1)
        # Connect group signal
        self.mode_group.idToggled.connect(self.update_guess_fields_visibility)
        
        mode_layout.addWidget(self.mode_phys_radio)
        mode_layout.addWidget(self.mode_coeff_radio)
        mode_layout.addStretch()
        guess_main_layout.addLayout(mode_layout)
        
        self.guess_stack = QStackedWidget()
        
        # Page 1: Physical Parameters (Vertical Layout to avoid squishing)
        page_phys = QWidget()
        phys_layout = QFormLayout() # Use FormLayout for Label-Field pairs in 1 column
        
        self.sakuma_phys_a0 = QLineEdit("0.00316573")
        phys_layout.addRow("a₀ (C):", self.sakuma_phys_a0)
        
        self.sakuma_phys_sigma = QLineEdit("0.0085")
        phys_layout.addRow("σ₀ (μm):", self.sakuma_phys_sigma)
        
        self.sakuma_phys_lambda = QLineEdit("0.65")
        phys_layout.addRow("λ₀ (μm):", self.sakuma_phys_lambda)
        
        self.sakuma_phys_b0 = QLineEdit("0.937109")
        phys_layout.addRow("b₀ (K):", self.sakuma_phys_b0)
        
        page_phys.setLayout(phys_layout)
        self.guess_stack.addWidget(page_phys)
        
        # Page 2: Coefficients (Vertical Layout)
        page_coeff = QWidget()
        coeff_layout = QFormLayout()
        
        self.sakuma_coeff_a = QLineEdit("1.0e-6")
        coeff_layout.addRow("a:", self.sakuma_coeff_a)
        
        self.sakuma_coeff_b = QLineEdit("0.0")
        coeff_layout.addRow("b:", self.sakuma_coeff_b)
        
        self.sakuma_coeff_c = QLineEdit("1.0")
        coeff_layout.addRow("c:", self.sakuma_coeff_c)
        
        page_coeff.setLayout(coeff_layout)
        self.guess_stack.addWidget(page_coeff)
        
        guess_main_layout.addWidget(self.guess_stack)
        self.guess_box.setLayout(guess_main_layout)
        
        self.guess_box.setVisible(False)  # Hidden by default
        left_layout.addWidget(self.guess_box)
        
        # Temperature Range for Fit Plot
        range_box = QGroupBox("Scale Realization Range")
        range_layout = QVBoxLayout()
        
        range_info = QLabel("Specify the temperature range for the fit plot:")
        range_info.setWordWrap(True)
        range_info.setStyleSheet("font-size: 9pt; color: gray;")
        range_layout.addWidget(range_info)
        
        # Grid for Tmin and Tmax
        range_grid = QGridLayout()
        
        self.sakuma_tmin_edit = QLineEdit("1000")
        self.sakuma_tmin_edit.setPlaceholderText("Min T (K)")
        range_grid.addWidget(QLabel("T_min (K):"), 0, 0)
        range_grid.addWidget(self.sakuma_tmin_edit, 0, 1)
        
        self.sakuma_tmax_edit = QLineEdit("3500")
        self.sakuma_tmax_edit.setPlaceholderText("Max T (K)")
        range_grid.addWidget(QLabel("T_max (K):"), 0, 2)
        range_grid.addWidget(self.sakuma_tmax_edit, 0, 3)
        
        range_layout.addLayout(range_grid)
        range_box.setLayout(range_layout)
        left_layout.addWidget(range_box)
        
        # Fit Button & WeightedFit Checkbox
        fit_box = QGroupBox("Fitting")
        fit_layout = QHBoxLayout() # Horizontal layout
        
        # Fit button
        btn_fit = QPushButton("🔍 Perform Sakuma-Hattori Fit")
        btn_fit.clicked.connect(self.perform_unified_sakuma_fit)
        fit_layout.addWidget(btn_fit, stretch=2)
        
        # Show Results Button (Popup)
        self.btn_show_results = QPushButton("📄 Show Results")
        self.btn_show_results.setToolTip("Show results from the last fit")
        self.btn_show_results.clicked.connect(self.show_sakuma_results_popup)
        self.btn_show_results.setEnabled(False) # Disabled until fit is performed
        fit_layout.addWidget(self.btn_show_results, stretch=1)
        
        # Weighted Fit Option
        self.weighted_fit_sched = QCheckBox("Weighted Fit (Relative Error)")
        self.weighted_fit_sched.setToolTip("Minimizes percentage error instead of absolute error.\nUseful when low-temperature signals are very small.")
        fit_layout.addWidget(self.weighted_fit_sched, stretch=1)
        
        fit_box.setLayout(fit_layout)
        left_layout.addWidget(fit_box)
        
        
        left_layout.addStretch(1)  # Add stretch with factor 1 to allow compression
        
        # Right side - Plots with splitter for resizable plots
        plot_splitter = QSplitter(Qt.Vertical)
        self.sakuma_canvas = PlotCanvas("Sakuma-Hattori Fit", theme_name=self.theme_name)
        plot_splitter.addWidget(self.sakuma_canvas)
        
        self.sakuma_error_canvas = PlotCanvas("Error Plot", theme_name=self.theme_name)
        plot_splitter.addWidget(self.sakuma_error_canvas)
        
        # Set initial sizes (equal split)
        plot_splitter.setSizes([400, 400])
        
        # Add to main layout
        main_layout.addLayout(left_layout, stretch=1)
        main_layout.addWidget(plot_splitter, stretch=2)
        
        widget.setLayout(main_layout)
        return widget

    def create_converter_tab(self):
        """Create converter tab with both ITS-90 and Sakuma-Hattori calculators"""
        widget = QWidget()
        main_layout = QVBoxLayout()
        
        # Header
        header = QLabel("Temperature ⇄ Signal Converters")
        header.setFont(QFont("Arial", 14, QFont.Bold))
        header.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(header)
        
        # Two-column layout for the calculators
        calc_layout = QHBoxLayout()
        
        # === ITS-90 Calculator ===
        its90_calc_box = QGroupBox("📊 ITS-90 Calculator")
        its90_calc_layout = QVBoxLayout()
        
        # Input section
        its90_input_layout = QFormLayout()
        
        self.conv_its90_temp_edit = QLineEdit()
        self.conv_its90_temp_edit.setPlaceholderText("Enter temperature (K)")
        its90_input_layout.addRow("Temperature (K):", self.conv_its90_temp_edit)
        
        self.conv_its90_signal_edit = QLineEdit()
        self.conv_its90_signal_edit.setPlaceholderText("Enter signal")
        its90_input_layout.addRow("Signal:", self.conv_its90_signal_edit)
        
        its90_calc_layout.addLayout(its90_input_layout)
        
        # Calculate buttons
        its90_btn_layout = QHBoxLayout()
        
        btn_its90_temp_to_signal = QPushButton("T → S")
        btn_its90_temp_to_signal.setToolTip("Calculate Signal from Temperature (ITS-90)")
        btn_its90_temp_to_signal.clicked.connect(lambda: self.converter_its90_calculate("T_to_S"))
        its90_btn_layout.addWidget(btn_its90_temp_to_signal)
        
        btn_its90_signal_to_temp = QPushButton("S → T")
        btn_its90_signal_to_temp.setToolTip("Calculate Temperature from Signal (ITS-90)")
        btn_its90_signal_to_temp.clicked.connect(lambda: self.converter_its90_calculate("S_to_T"))
        its90_btn_layout.addWidget(btn_its90_signal_to_temp)
        
        its90_calc_layout.addLayout(its90_btn_layout)
        
        # Result
        self.conv_its90_result_label = QLabel("Enter values and click calculate")
        self.conv_its90_result_label.setWordWrap(True)
        self.conv_its90_result_label.setStyleSheet("background-color: #f0f0f0; padding: 10px; border-radius: 3px;")
        its90_calc_layout.addWidget(self.conv_its90_result_label)
        
        its90_calc_layout.addStretch()
        its90_calc_box.setLayout(its90_calc_layout)
        calc_layout.addWidget(its90_calc_box)
        
        # === Sakuma-Hattori Calculator ===
        sakuma_calc_box = QGroupBox("📊 Sakuma-Hattori Calculator")
        sakuma_calc_layout = QVBoxLayout()
        
        # Input section
        sakuma_input_layout = QFormLayout()
        
        self.conv_sakuma_temp_edit = QLineEdit()
        self.conv_sakuma_temp_edit.setPlaceholderText("Enter temperature (K)")
        sakuma_input_layout.addRow("Temperature (K):", self.conv_sakuma_temp_edit)
        
        self.conv_sakuma_signal_edit = QLineEdit()
        self.conv_sakuma_signal_edit.setPlaceholderText("Enter signal")
        sakuma_input_layout.addRow("Signal:", self.conv_sakuma_signal_edit)
        
        sakuma_calc_layout.addLayout(sakuma_input_layout)
        
        # Calculate buttons
        sakuma_btn_layout = QHBoxLayout()
        
        btn_sakuma_temp_to_signal = QPushButton("T → S")
        btn_sakuma_temp_to_signal.setToolTip("Calculate Signal from Temperature (Sakuma-Hattori)")
        btn_sakuma_temp_to_signal.clicked.connect(lambda: self.converter_sakuma_calculate("T_to_S"))
        sakuma_btn_layout.addWidget(btn_sakuma_temp_to_signal)
        
        btn_sakuma_signal_to_temp = QPushButton("S → T")
        btn_sakuma_signal_to_temp.setToolTip("Calculate Temperature from Signal (Sakuma-Hattori)")
        btn_sakuma_signal_to_temp.clicked.connect(lambda: self.converter_sakuma_calculate("S_to_T"))
        sakuma_btn_layout.addWidget(btn_sakuma_signal_to_temp)
        
        sakuma_calc_layout.addLayout(sakuma_btn_layout)
        
        # Result
        self.conv_sakuma_result_label = QLabel("Enter values and click calculate")
        self.conv_sakuma_result_label.setWordWrap(True)
        self.conv_sakuma_result_label.setStyleSheet("background-color: #f0f0f0; padding: 10px; border-radius: 3px;")
        sakuma_calc_layout.addWidget(self.conv_sakuma_result_label)
        
        sakuma_calc_layout.addStretch()
        sakuma_calc_box.setLayout(sakuma_calc_layout)
        calc_layout.addWidget(sakuma_calc_box)
        
        main_layout.addLayout(calc_layout, stretch=1)
        
        # Info label
        info_label = QLabel("Note: Perform fitting in respective tabs before using converters")
        info_label.setStyleSheet("color: gray; font-style: italic;")
        info_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(info_label)
        
        main_layout.addStretch()
        
        widget.setLayout(main_layout)
        return widget

    def add_fixed_point_row(self, name="Custom", temp="", signal=""):
        """Add a fixed point row to the table"""
        row = self.fp_table.rowCount()
        self.fp_table.insertRow(row)
        
        # 1. Checkbox (Centered)
        chk_widget = QWidget()
        chk_layout = QHBoxLayout(chk_widget)
        chk_layout.setContentsMargins(0,0,0,0)
        chk_layout.setAlignment(Qt.AlignCenter)
        chk = QCheckBox()
        chk.stateChanged.connect(self.update_sakuma_mode)
        chk_layout.addWidget(chk)
        self.fp_table.setCellWidget(row, 0, chk_widget)
        
        # 2. Name ComboBox
        name_cb = QComboBox()
        name_cb.setEditable(True)
        names_list = ["Custom"]
        try:
            lib_names = sorted(list(self.fp_library.keys()))
            names_list += lib_names
        except Exception:
            pass
        
        if name and name != "Custom" and name not in names_list:
            names_list.append(name)
            
        name_cb.addItems(names_list)
        name_cb.setCurrentText(name)
        self.fp_table.setCellWidget(row, 1, name_cb)
        
        # 3. Temperature Item (Standard Table Cell)
        temp_item = QTableWidgetItem()
        if temp: temp_item.setText(str(temp))
        self.fp_table.setItem(row, 2, temp_item)
        
        # 4. Signal Item (Standard Table Cell)
        signal_item = QTableWidgetItem()
        if signal: signal_item.setText(str(signal))
        self.fp_table.setItem(row, 3, signal_item)
        
        # 5. ITS-90 Checkbox
        its90_widget = QWidget()
        its90_layout = QHBoxLayout(its90_widget)
        its90_layout.setContentsMargins(0,0,0,0)
        its90_layout.setAlignment(Qt.AlignCenter)
        its90_chk = QCheckBox()
        its90_chk.setToolTip("Use ITS-90 c₂=14388")
        its90_chk.setVisible(False) # Hidden by default
        its90_chk.stateChanged.connect(self.on_fp_its90_changed)
        its90_layout.addWidget(its90_chk)
        self.fp_table.setCellWidget(row, 4, its90_widget)
        
        # Connect signals
        name_cb.currentIndexChanged.connect(lambda: self.on_fp_name_changed(name_cb, temp_item, signal_item))
        name_cb.currentIndexChanged.connect(self.update_sakuma_mode)
        
    def initialize_new_rows(self):
        """Called after a paste operation to ensure all rows have required widgets"""
        for row in range(self.fp_table.rowCount()):
            # Check if row needs initialization (e.g. missing checkbox in col 0)
            if not self.fp_table.cellWidget(row, 0):
                # Using existing add_fixed_point_row logic partially is hard because it assumes appending
                # We need to inject widgets into this specific row
                
                # 1. Checkbox
                chk_widget = QWidget()
                chk_layout = QHBoxLayout(chk_widget)
                chk_layout.setContentsMargins(0,0,0,0)
                chk_layout.setAlignment(Qt.AlignCenter)
                chk = QCheckBox()
                chk.stateChanged.connect(self.update_sakuma_mode)
                chk_layout.addWidget(chk)
                self.fp_table.setCellWidget(row, 0, chk_widget)
                
                # 2. Name Combo
                name_cb = QComboBox()
                name_cb.setEditable(True)
                names_list = ["Custom"]
                try:
                    lib_names = sorted(list(self.fp_library.keys()))
                    names_list += lib_names
                except Exception:
                    pass
                name_cb.addItems(names_list)
                name_cb.setCurrentText("Custom")
                self.fp_table.setCellWidget(row, 1, name_cb)
                
                # 3. Temp Item (Already likely set by paste, but ensure)
                if not self.fp_table.item(row, 2):
                    self.fp_table.setItem(row, 2, QTableWidgetItem(""))
                temp_item = self.fp_table.item(row, 2)
                    
                # 4. Signal Item
                if not self.fp_table.item(row, 3):
                    self.fp_table.setItem(row, 3, QTableWidgetItem(""))
                signal_item = self.fp_table.item(row, 3)
                
                # 5. ITS-90 Checkbox
                its90_widget = QWidget()
                its90_layout = QHBoxLayout(its90_widget)
                its90_layout.setContentsMargins(0,0,0,0)
                its90_layout.setAlignment(Qt.AlignCenter)
                its90_chk = QCheckBox()
                its90_chk.setToolTip("Use ITS-90 c₂=14388")
                its90_chk.setVisible(False)
                its90_chk.stateChanged.connect(self.on_fp_its90_changed)
                its90_layout.addWidget(its90_chk)
                self.fp_table.setCellWidget(row, 4, its90_widget)
                
                # Connect signals
                name_cb.currentIndexChanged.connect(lambda _, cb=name_cb, ti=temp_item, si=signal_item: self.on_fp_name_changed(cb, ti, si))
                name_cb.currentIndexChanged.connect(self.update_sakuma_mode)
    
    def add_new_fixed_point(self):
        """Add a new empty fixed point row"""
        self.add_fixed_point_row("Custom", "", "")
        self._log("New fixed point row added", "INFO")
    
    def remove_selected_fixed_points(self):
        """Remove checked fixed point rows"""
        rows_to_remove = []
        for i in range(self.fp_table.rowCount()):
            chk_widget = self.fp_table.cellWidget(i, 0)
            if chk_widget:
                chk = chk_widget.layout().itemAt(0).widget()
                if chk.isChecked():
                    rows_to_remove.append(i)
        
        if not rows_to_remove:
            QMessageBox.warning(self, "Warning", "No fixed points selected for removal")
            return
            
        for i in reversed(sorted(rows_to_remove)):
            self.fp_table.removeRow(i)
            
        self._log(f"Removed {len(rows_to_remove)} fixed point(s)", "SUCCESS")
        self.update_sakuma_mode()
    
    def remove_last_fixed_point(self):
        """Remove the last fixed point row"""
        row_count = self.fp_table.rowCount()
        if row_count > 0:
            self.fp_table.removeRow(row_count - 1)
    
    def update_sakuma_mode(self):
        """Update mode label and show/hide parameter boxes based on selected fixed points"""
    
    def show_fp_popup(self):
        """Show the fixed point table popup centered on the button"""
        # Calculate position
        pos = self.btn_open_fp.mapToGlobal(self.btn_open_fp.rect().center())
        # Adjust so popup center is at button center
        x = pos.x() - self.fp_popup.width() // 2
        y = pos.y() - self.fp_popup.height() // 2
        
        # ensure on screen
        screen = QApplication.primaryScreen().geometry()
        x = max(0, min(x, screen.width() - self.fp_popup.width()))
        y = max(0, min(y, screen.height() - self.fp_popup.height()))
        
        self.fp_popup.move(x, y)
        self.fp_popup.exec() # Modal execution prevents interaction with main window but allows context menus
    
    def update_sakuma_mode(self):
        """Update mode label and show/hide parameter boxes based on selected fixed points"""
        n_selected = 0
        
        # Count selected and update ITS-90 checkboxes
        its90_metals = ['Ag', 'Au', 'Cu']
        
        # First pass: count selected
        for i in range(self.fp_table.rowCount()):
            chk_widget = self.fp_table.cellWidget(i, 0)
            if chk_widget and chk_widget.layout().itemAt(0).widget().isChecked():
                n_selected += 1

        # Update summary label
        if hasattr(self, 'fp_cnt_label'):
             self.fp_cnt_label.setText(f"{n_selected} fixed point(s) selected")

        # Second pass: update ITS-90 visibility
        for i in range(self.fp_table.rowCount()):
            name_cb = self.fp_table.cellWidget(i, 1)
            its90_widget = self.fp_table.cellWidget(i, 4)
            
            if name_cb and its90_widget:
                name = name_cb.currentText()
                its90_chk = its90_widget.layout().itemAt(0).widget()
                
                should_show = (name in its90_metals) and (n_selected <= 1)
                its90_chk.setVisible(should_show)
        
        # Hide the old group ITS-90 checkbox (we now have individual checkboxes)
        self.its90_checkbox_box.setVisible(False)
        
        if n_selected == 0:
            self.sakuma_mode_label.setText("Mode: Select 1-3 or >3 fixed points")
            self.sakuma_mode_label.setStyleSheet("color: blue; font-weight: bold;")
            # Hide all guess fields based on stack visibility? 
            # Actually let's hide the whole box if 0 selected, just to be clean.
            self.guess_box.setVisible(False)
        else:
            if n_selected == 1:
                self.sakuma_mode_label.setText("Mode: n=1 (λ calculated, σ from Data Input)")
                self.sakuma_mode_label.setStyleSheet("color: green; font-weight: bold;")
            elif n_selected == 2:
                self.sakuma_mode_label.setText("Mode: n=2 (λ fitted, σ fixed)")
                self.sakuma_mode_label.setStyleSheet("color: green; font-weight: bold;")
            else:
                self.sakuma_mode_label.setText(f"Mode: n={n_selected} (Full Fit)")
                self.sakuma_mode_label.setStyleSheet("color: purple; font-weight: bold;")
            
            # Show guess box for all active modes
            self.guess_box.setVisible(True)
            self.update_guess_fields_visibility()

    def update_guess_fields_visibility(self):
        """Update visibility of guess fields based on selected mode"""
        # 0 = Physical, 1 = Coeffs
        # If radio button checked
        idx = 1 if self.mode_coeff_radio.isChecked() else 0
        self.guess_stack.setCurrentIndex(idx)

    # Data loading methods
    def load_spectral_data(self):
        """Load wavelength and spectral responsivity from CSV/TXT"""
        path, _ = QFileDialog.getOpenFileName(
            self, 'Open Spectral Data', '', 'Data files (*.txt *.csv);;All files (*)'
        )
        if not path:
            return
        try:
            data = pd.read_csv(path)
            if len(data.columns) >= 2:
                self.wavelength = data.iloc[:, 0].to_numpy(float)
                self.spectral_resp = data.iloc[:, 1].to_numpy(float)
                self.spec_info_label.setText(
                    f"Loaded: {len(self.wavelength)} points, λ range: {self.wavelength.min():.2f}-{self.wavelength.max():.2f} nm"
                )
                QMessageBox.information(self, "Success", f"Loaded {len(self.wavelength)} spectral points")
                self.update_initial_guesses_from_spectral()
            else:
                QMessageBox.warning(self, "Error", "File must have at least 2 columns (wavelength, spectral_resp)")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load file:\n{str(e)}")
    
    def use_default_spectral(self):
        """Use default high temperature spectral response - DEPRECATED"""
        pass
    
    def update_initial_guesses_from_spectral(self):
        """Update initial guess values based on loaded spectral data"""
        try:
            if self.wavelength is not None and self.spectral_resp is not None:
                # Calculate λ from spectral data
                dot = np.sum(self.wavelength * self.spectral_resp)
                sp_su = np.sum(self.spectral_resp)
                lamda = 0.001 * dot / sp_su  # Convert from nm to μm
                
                # Update λ₀ initial guess
                # The widget is named sakuma_phys_lambda, not sakuma_lambda_guess
                if hasattr(self, 'sakuma_phys_lambda'):
                    self.sakuma_phys_lambda.setText(f"{lamda:.6f}")
                
                self._log(f"Updated initial guess: λ₀={lamda:.6f} μm from spectral data", "INFO")
        except Exception as e:
            self._log(f"Failed to update initial guesses: {str(e)}", "WARNING")
    
    def load_calibration_data(self):
        """Load temperature and signal calibration data"""
        path, _ = QFileDialog.getOpenFileName(
            self, 'Open Calibration Data', '', 'Data files (*.txt *.csv);;All files (*)'
        )
        if not path:
            return
        try:
            data = pd.read_csv(path)
            
            # Try to determine format by checking if first column is numeric
            if len(data.columns) >= 3:
                # Check if first column contains strings (names) or numbers (old format)
                try:
                    # Try to convert first column to float
                    _ = data.iloc[:, 0].astype(float)
                    # If successful, it's old format: Temp, Signal, (extra column)
                    is_new_format = False
                except (ValueError, TypeError):
                    # If conversion fails, first column has names
                    is_new_format = True
                
                if is_new_format:
                    # Format: Name, Temperature, Signal
                    self.fp_names_from_data = data.iloc[:, 0].tolist()
                    self.temperatures = data.iloc[:, 1].to_numpy(float)
                    self.signals = data.iloc[:, 2].to_numpy(float)
                    
                    self._log(f"Found fixed point names in calibration data (column 1): {self.fp_names_from_data}", "INFO")
                    
                    # Auto-populate fixed point rows from calibration data
                    # Clear existing fixed points first
                    self.fp_table.setRowCount(0)
                    
                    self._log(f"Cleared existing fixed points, now adding {len(self.fp_names_from_data)} new rows", "INFO")
                    
                    # Add a row for each fixed point in the data
                    for i, fp_name in enumerate(self.fp_names_from_data):
                        # Clean up the name (remove whitespace)
                        fp_name_clean = str(fp_name).strip() if pd.notna(fp_name) else "Custom"
                        temp_str = self._format_temp(self.temperatures[i])
                        signal_str = f"{self.signals[i]:.6e}"
                        
                        self._log(f"Adding row {i+1}: name='{fp_name_clean}', T={temp_str}, S={signal_str}", "INFO")
                        
                        name_to_use = fp_name_clean if fp_name_clean and fp_name_clean != "Custom" else "Custom"
                        self.add_fixed_point_row(name_to_use, temp_str, signal_str)
                        
                        # Check the checkbox for this fixed point (enable it for fitting)
                        # The row was just added at the end (index match i)
                        # We need to access the widget we just added
                        # Since add_fixed_point_row appends, the index matches i (0-based)
                        if i < self.fp_table.rowCount():
                             chk_widget = self.fp_table.cellWidget(i, 0)
                             if chk_widget:
                                 chk = chk_widget.layout().itemAt(0).widget()
                                 chk.setChecked(True)
                             
                    # Update the mode display after auto-populating
                    self.update_sakuma_mode()
                    
                    self._log(f"Auto-populated {len(self.fp_names_from_data)} fixed point rows", "SUCCESS")
                else:
                    # Old format: Temperature, Signal, ...
                    self.temperatures = data.iloc[:, 0].to_numpy(float)
                    self.signals = data.iloc[:, 1].to_numpy(float)
                    self.fp_names_from_data = None
                    
                self.cal_info_label.setText(
                    f"Loaded: {len(self.temperatures)} points, T range: {self.temperatures.min():.2f}-{self.temperatures.max():.2f} K"
                )
                QMessageBox.information(self, "Success", f"Loaded {len(self.temperatures)} calibration points")
                self._log(f"Loaded {len(self.temperatures)} calibration points from file", "SUCCESS")
                
            elif len(data.columns) >= 2:
                # Old format: Temperature, Signal (no names)
                self.temperatures = data.iloc[:, 0].to_numpy(float)
                self.signals = data.iloc[:, 1].to_numpy(float)
                self.fp_names_from_data = None
                
                self.cal_info_label.setText(
                    f"Loaded: {len(self.temperatures)} points, T range: {self.temperatures.min():.2f}-{self.temperatures.max():.2f} K"
                )
                QMessageBox.information(self, "Success", f"Loaded {len(self.temperatures)} calibration points")
                self._log(f"Loaded {len(self.temperatures)} calibration points from file", "SUCCESS")
                
            else:
                QMessageBox.warning(self, "Error", "File must have at least 2 columns")
                self._log("File format error: need at least 2 columns", "ERROR")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load file:\n{str(e)}")
            self._log(f"Failed to load calibration data: {str(e)}", "ERROR")
    
    def use_default_calibration(self):
        """Use default LP5 calibration data - DEPRECATED"""
        pass
    
    def manual_input_data(self):
        """Manual input dialog for temperature and signal data"""
        dialog = QDialog(self)
        dialog.setWindowTitle("Manual Input - Temperature & Signal Data")
        dialog.resize(500, 400)
        
        layout = QVBoxLayout()
        
        info = QLabel("Enter data one per line.\nFormat: Name,Temperature,Signal (e.g. Cu,1357.8,2.5e-10)\nOR: Temperature,Signal (e.g. 1357.8,2.5e-10)")
        layout.addWidget(info)
        
        text_edit = QTextEdit()
        text_edit.setPlaceholderText("Ag,1234.93,1.2e-10\nAu,1337.33,2.5e-10\n1500.0,5.0e-9")
        layout.addWidget(text_edit)
        
        btn_box = QHBoxLayout()
        btn_ok = QPushButton("OK")
        btn_cancel = QPushButton("Cancel")
        btn_box.addWidget(btn_ok)
        btn_box.addWidget(btn_cancel)
        layout.addLayout(btn_box)
        
        dialog.setLayout(layout)
        
        def accept_data():
            try:
                lines = text_edit.toPlainText().strip().split('\n')
                temps = []
                sigs = []
                names = []
                has_names = False
                
                for line in lines:
                    if line.strip():
                        parts = line.strip().split(',')
                        if len(parts) == 3:
                            n, t, s = parts
                            names.append(n.strip())
                            temps.append(float(t))
                            sigs.append(float(s))
                            has_names = True
                        elif len(parts) == 2:
                            t, s = parts
                            names.append("Custom")
                            temps.append(float(t))
                            sigs.append(float(s))
                        else:
                            raise ValueError(f"Invalid format in line: {line}")
                
                self.temperatures = np.array(temps)
                self.signals = np.array(sigs)
                if has_names:
                    self.fp_names_from_data = names
                    
                    # Auto-populate table if names are present
                    self.fp_table.setRowCount(0)
                    for i, name in enumerate(names):
                         if name and name != "Custom":
                             self.add_fixed_point_row(name, self._format_temp(temps[i]), f"{sigs[i]:.6e}")
                             # Check the box
                             if i < self.fp_table.rowCount():
                                 widget = self.fp_table.cellWidget(i, 0)
                                 if widget:
                                     widget.layout().itemAt(0).widget().setChecked(True)
                else:
                    self.fp_names_from_data = None
                
                self.cal_info_label.setText(
                    f"Loaded: {len(self.temperatures)} points, T range: {self.temperatures.min():.2f}-{self.temperatures.max():.2f} K"
                )
                dialog.accept()
            except Exception as e:
                QMessageBox.critical(dialog, "Error", f"Invalid input format:\n{str(e)}")
        
        btn_ok.clicked.connect(accept_data)
        btn_cancel.clicked.connect(dialog.reject)
        
        dialog.exec()
    
    def update_input_preview(self):
        """Update preview plot of loaded data"""
        try:
            self.input_canvas.ax.clear()
            self.input_canvas.ax.plot(self.temperatures, self.signals, 'o', label='Signal vs Temperature')
            self.input_canvas.ax.set_xlabel('Temperature (K)')
            self.input_canvas.ax.set_ylabel('Signal (a.u.)')
            self.input_canvas.ax.set_title('Calibration Data Preview')
            self.input_canvas.ax.legend()
            self.input_canvas.ax.grid(True, alpha=0.3)
            self.input_canvas.draw()
            self._log("Preview plot updated", "SUCCESS")
        except Exception as e:
            QMessageBox.warning(self, "Plot Error", str(e))
            self._log(f"Plot error: {str(e)}", "ERROR")
    
    def plot_spectral_responsivity(self):
        """Plot spectral responsivity curve with FWHM markers"""
        try:
            if self.wavelength is None or self.spectral_resp is None:
                QMessageBox.warning(self, "No Data", "Please load spectral responsivity data first")
                return
            
            self.input_canvas.ax.clear()
            self.input_canvas.ax.plot(self.wavelength, self.spectral_resp, 'b-', linewidth=2, label='Spectral Responsivity')
            
            # Calculate and plot FWHM markers
            try:
                # Find the two points closest to 0.5 (FWHM points)
                sorted_indices = np.argsort(np.abs(np.array(self.spectral_resp) - 0.5))
                idx1, idx2 = sorted_indices[0], sorted_indices[1]
                
                # Ensure idx1 < idx2
                if idx1 > idx2:
                    idx1, idx2 = idx2, idx1
                
                wl1 = self.wavelength[idx1]
                wl2 = self.wavelength[idx2]
                fwhm = abs(wl2 - wl1)
                
                # Plot FWHM markers
                self.input_canvas.ax.plot([wl1, wl2], [0.5, 0.5], 'r-', linewidth=2, label=f'FWHM = {fwhm:.2f} nm')
                self.input_canvas.ax.plot([wl1, wl1], [0, 0.5], 'r--', linewidth=1, alpha=0.7)
                self.input_canvas.ax.plot([wl2, wl2], [0, 0.5], 'r--', linewidth=1, alpha=0.7)
                self.input_canvas.ax.scatter([wl1, wl2], [0.5, 0.5], color='red', s=50, zorder=5)
                
                # Calculate Effective Wavelength (Centroid)
                lambda_eff = np.sum(self.wavelength * self.spectral_resp) / np.sum(self.spectral_resp)
                
                # Plot Lambda Eff line
                self.input_canvas.ax.axvline(x=lambda_eff, color='green', linestyle='--', linewidth=2, label=f'$\lambda_c$ = {lambda_eff:.2f} nm')
                
                # Add text annotation for FWHM
                mid_wl = (wl1 + wl2) / 2
                self.input_canvas.ax.text(mid_wl, 0.52, f'FWHM\n{fwhm:.2f} nm', 
                                         ha='center', va='bottom', fontsize=10, 
                                         bbox=dict(boxstyle='round,pad=0.5', facecolor='yellow', alpha=0.7))
                
                # Add text annotation for Lambda Eff
                # Position it slightly above the FWHM or at the top
                self.input_canvas.ax.text(lambda_eff, 0.90, f'$\lambda_c$ = {lambda_eff:.2f} nm', 
                                         ha='left', va='top', fontsize=10, transform=self.input_canvas.ax.get_xaxis_transform(),
                                         bbox=dict(boxstyle='round,pad=0.5', facecolor='lightgreen', alpha=0.7))

            except Exception as e:
                self._log(f"Could not calculate FWHM/Lambda markers: {str(e)}", "WARNING")
            
            self.input_canvas.ax.set_xlabel('Wavelength (nm)')
            self.input_canvas.ax.set_ylabel('Spectral Responsivity (a.u.)')
            self.input_canvas.ax.set_title('Spectral Responsivity Curve')
            self.input_canvas.ax.legend()
            self.input_canvas.ax.grid(True, alpha=0.3)
            self.input_canvas.draw()
            self._log(f"Spectral responsivity plot displayed. FWHM={fwhm:.2f}nm, Lambda_eff={lambda_eff:.2f}nm", "SUCCESS")
        except Exception as e:
            QMessageBox.warning(self, "Plot Error", str(e))
            self._log(f"Plot error: {str(e)}", "ERROR")

    def load_fixed_point_library(self):
        """Load standard fixed point definitions from repository JSON files into self.fp_library
        The library maps name -> dict with keys 'Temperature' and 'Signal' (if available).
        """
        self.fp_library = {}
        try:
            import glob, json, os
            base = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        except Exception:
            base = None

        # search common folders in workspace for Fixed Points
        candidates = []
        work_dirs = [
            os.path.join(os.path.dirname(__file__), "MultiFIX Calculator v0.9.1", "Fixed Points"),
            os.path.join(os.path.dirname(__file__), "MultiFIX Calculator v0.9", "Fixed Points"),
            os.path.join(os.path.dirname(__file__), "MultiFIX Calculator", "Fixed Points")
        ]
        for d in work_dirs:
            try:
                if os.path.isdir(d):
                    candidates.append(d)
            except Exception:
                continue

        # also check workspace root
        try:
            import glob
            root = os.path.dirname(__file__)
            g = glob.glob(os.path.join(root, "**", "Fixed Points", "*.json"), recursive=True)
            for p in g:
                candidates.append(os.path.dirname(p))
        except Exception:
            pass

        seen = set()
        for d in candidates:
            try:
                files = glob.glob(os.path.join(d, "*.json"))
                for f in files:
                    name = os.path.splitext(os.path.basename(f))[0]
                    if name in seen:
                        continue
                    with open(f, 'r', encoding='utf-8') as fh:
                        try:
                            jd = json.load(fh)
                            t = jd.get('Temperature')
                            s = jd.get('Signal')
                            if t is not None:
                                self.fp_library[name] = {'Temperature': float(t), 'Signal': float(s) if s is not None else None}
                                seen.add(name)
                        except Exception:
                            continue
            except Exception:
                continue

        # fallback built-ins if library empty
        if not self.fp_library:
            builtins = {
                'Ag': 1234.93,
                'Au': 1337.33,
                'Cu': 1357.802,
                'Fe-C': 1495.0,
                'Co-C': 1597.39,
                'Pd-C': 1828.05,
                'Pt-C': 2041.4,
                'Ru-C': 2227.1,
                'ReC': 2747.84,
                'WC-C': 3020.75
            }
            for k, v in builtins.items():
                self.fp_library[k] = {'Temperature': float(v), 'Signal': None}

    def on_fp_name_changed(self, combobox, temp_edit, signal_edit):
        """When a fixed-point name is chosen, auto-fill temperature and signal (if available).
        First check calibration data, then fall back to library values.
        """
        try:
            name = combobox.currentText()
            if name == 'Custom':
                return
            
            # First priority: Check if this name exists in loaded calibration data
            if hasattr(self, 'fp_names_from_data') and self.fp_names_from_data is not None:
                try:
                    # Find index where name matches
                    for i, cal_name in enumerate(self.fp_names_from_data):
                        if str(cal_name).strip() == name:
                            temp_edit.setText(self._format_temp(self.temperatures[i]))
                            signal_edit.setText(f"{self.signals[i]:.6e}")
                            return
                except Exception:
                    pass
            
            # Second priority: Use fixed point library
            lib = getattr(self, 'fp_library', {})
            if name in lib:
                fixed_temp = lib[name].get('Temperature')
                fixed_sig = lib[name].get('Signal')
                if fixed_temp is not None:
                    # if calibration data loaded (without names), use nearest calibration signal
                    if getattr(self, 'temperatures', None) is not None and getattr(self, 'signals', None) is not None:
                        try:
                            idx = (np.abs(self.temperatures - float(fixed_temp))).argmin()
                            temp_edit.setText(self._format_temp(self.temperatures[idx]))
                            signal_edit.setText(f"{self.signals[idx]:.6e}")
                            return
                        except Exception:
                            pass
                    # else use library values
                    temp_edit.setText(self._format_temp(fixed_temp))
                if fixed_sig is not None and (not temp_edit.text()):
                    signal_edit.setText(f"{fixed_sig:.6e}")
        except Exception:
            pass
    
    def calculate_sigma_from_spectral(self):
        """Calculate sigma from spectral data FWHM using selected distribution type"""
        try:
            if self.wavelength is None or self.spectral_resp is None:
                QMessageBox.warning(self, "Warning", "Please load spectral data first (Data Input tab)")
                return
            
            dist_type = self.sigma_dist_combo.currentText()
            
            # Find the two points closest to 0.5 (FWHM points)
            sorted_indices = np.argsort(np.abs(np.array(self.spectral_resp) - 0.5))
            diff = np.abs(np.array(self.wavelength)[sorted_indices[0]] - np.array(self.wavelength)[sorted_indices[1]])
            
            # Calculate sigma based on distribution type
            if dist_type == "Rect":
                sigma = np.sqrt(np.square(diff) / 12)
            elif dist_type == "2Delta":
                sigma = np.sqrt(np.square(diff) / 4)
            elif dist_type == "Gauss":
                sigma = np.sqrt(np.square(diff) / (8 * np.log(2)))
            elif dist_type == "Tri":
                sigma = np.sqrt(np.square(diff) / 6)
            elif dist_type == "STri":
                sigma = np.sqrt((2 * np.square(diff)) / 9)
            else:
                QMessageBox.warning(self, "Error", "Unknown distribution type")
                return
            
            # Convert from nm to μm
            sigma_um = sigma / 1000.0
            
            # Update the sigma field
            self.sakuma_sigma_edit.setText(f"{sigma_um:.6f}")
            
            # Update label
            self.sigma_calc_label.setText(f"FWHM = {diff:.4f} nm\nσ = {sigma_um:.6f} μm ({dist_type})")
            
            self._log(f"Calculated σ = {sigma_um:.6f} μm using {dist_type} distribution (FWHM = {diff:.4f} nm)", "SUCCESS")
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to calculate sigma:\n{str(e)}")
            self._log(f"Sigma calculation failed: {str(e)}", "ERROR")
    
    def on_its90_checkbox_changed(self):
        """Update c2 value when ITS-90 checkbox is toggled (old group checkbox - deprecated)"""
        if self.its90_checkbox.isChecked():
            self.sakuma_c2_edit.setText("14388")
            self._log("Using ITS-90 c₂ value: 14388 μm·K", "INFO")
        else:
            self.sakuma_c2_edit.setText("14387.752")
            self._log("Using hc/kB c₂ value: 14387.752 μm·K", "INFO")
    
    def on_fp_its90_changed(self):
        """Update c2 value when any fixed point ITS-90 checkbox is toggled"""
        # Check if ANY ITS-90 checkbox is checked
        any_its90_checked = False
        for i in range(self.fp_table.rowCount()):
             widget = self.fp_table.cellWidget(i, 4)
             if widget:
                 chk = widget.layout().itemAt(0).widget()
                 if chk.isVisible() and chk.isChecked():
                     any_its90_checked = True
                     break
        
        if any_its90_checked:
            self.sakuma_c2_edit.setText("14388")
            self._log("Using ITS-90 c₂ value: 14388 μm·K", "INFO")
        else:
            self.sakuma_c2_edit.setText("14387.752")
            self._log("Using hc/kB c₂ value: 14387.752 μm·K", "INFO")

    # Fitting methods
    def perform_its90_fit(self):
        """Perform ITS-90 fit"""
        try:
            if self.wavelength is None or self.spectral_resp is None:
                QMessageBox.warning(self, "No Data", "Please load spectral responsivity data first")
                return
            
            # Constants
            c2_val = 0.014388  # m·K
            
            # Get parameters
            try:
                ref_temp = float(self.its90_ref_temp_edit.text())
                ref_signal = float(self.its90_ref_signal_edit.text())
                gain = float(self.its90_gain_edit.text())
                t_start = float(self.its90_tstart_edit.text())
                t_stop = float(self.its90_tstop_edit.text())
                t_step = float(self.its90_tstep_edit.text())
            except ValueError:
                QMessageBox.warning(self, "Invalid Input", "Please enter valid numerical values")
                return
            
            # Check inputs
            if t_start >= t_stop or t_step <= 0:
                QMessageBox.warning(self, "Invalid Range", "Check start, stop, and step values")
                return
            
            # Prepare calculation
            Sref = ref_signal / gain
            temps_fit = np.arange(t_start, t_stop + t_step, t_step)
            signals_calc = []
            
            # Calculate integrals
            # ref integral
            integrand_ref = self.spectral_resp / ((self.wavelength * 1e-9)**5 * (np.exp(c2_val / (self.wavelength * 1e-9 * ref_temp)) - 1))
            integral_ref = np.trapz(integrand_ref, x=self.wavelength * 1e-9)
            
            self._log(f"Starting ITS-90 fit calculation for {len(temps_fit)} points...", "INFO")
            
            # Calculate signals for range
            for T in temps_fit:
                integrand = self.spectral_resp / ((self.wavelength * 1e-9)**5 * (np.exp(c2_val / (self.wavelength * 1e-9 * T)) - 1))
                integral = np.trapz(integrand, x=self.wavelength * 1e-9)
                S = Sref * integral / integral_ref
                signals_calc.append(S)
            
            signals_calc = np.array(signals_calc)
            
            # Fit polynomial to ln(Signal) vs 1/T
            # ln(S) = sum(a_i * (1/T)^i) -> NO, usually standard is standard polynomial in ln(S) or similar
            # Standard Sakuma-Hattori is simpler, but ITS-90 approximations often use:
            # ln(S) vs 1/T is roughly linear.
            # Here we fit T_inverse = P(ln(S))
            
            y_data = 1.0 / temps_fit
            x_data = np.log(signals_calc)
            
            # Fit 4th order polynomial (usually sufficient)
            coeffs = np.polyfit(x_data, y_data, 5)
            self.its90_coeffs = coeffs
            
            # Calculate errors
            y_fit = np.polyval(coeffs, x_data)
            t_fit = 1.0 / y_fit
            errors = t_fit - temps_fit
            
            # Plot error
            self.its90_canvas.ax.clear()
            self.its90_canvas.ax.plot(temps_fit, errors, 'r-')
            self.its90_canvas.ax.set_xlabel('Temperature (K)')
            self.its90_canvas.ax.set_ylabel('Error (K)')
            self.its90_canvas.ax.set_title('ITS-90 Fit Error')
            self.its90_canvas.ax.grid(True, alpha=0.3)
            self.its90_canvas.draw()
            
            # Display results

            coeffs_str = "\n".join([f"a{i}: {c:.6e}" for i, c in enumerate(coeffs)])
            self.its90_result_label.setText(f"Fit converged.\nMax Error: {np.max(np.abs(errors)):.6f} K\n\nCoefficients:\n{coeffs_str}")
            
            QMessageBox.information(self, "Success", "ITS-90 fit completed successfully")
            self._log(f"ITS-90 fit completed. Max error: {np.max(np.abs(errors)):.6e} K", "SUCCESS")
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"ITS-90 fitting failed:\n{str(e)}")
            self._log(f"ITS-90 fitting failed: {str(e)}", "ERROR")

    def perform_unified_sakuma_fit(self):
        """Unified Sakuma-Hattori fit method that handles n=1, 2, 3, and >3 cases"""
        try:
            from scipy.optimize import least_squares, leastsq
            
            # 1. Identify selected fixed points
            # 1. Extract Data (Temps, Signals)
            temps = []
            signals = []
            names = []
            
            for i in range(self.fp_table.rowCount()):
                chk_widget = self.fp_table.cellWidget(i, 0)
                if chk_widget and chk_widget.layout().itemAt(0).widget().isChecked():
                     # Get data
                     name = self.fp_table.cellWidget(i, 1).currentText()
                     
                     t_item = self.fp_table.item(i, 2)
                     t_text = t_item.text().strip() if t_item else ""
                     
                     s_item = self.fp_table.item(i, 3)
                     s_text = s_item.text().strip() if s_item else ""
                     
                     try:
                         t = float(t_text)
                         s = float(s_text)
                         temps.append(t)
                         signals.append(s)
                         names.append(name)
                     except ValueError:
                         pass
            
            n_selected = len(temps)
            
            if n_selected == 0:
                QMessageBox.warning(self, "Warning", "Please select at least one fixed point")
                return
            
            # Sort by temperature
            sorted_pairs = sorted(zip(temps, signals, names))
            temps = [p[0] for p in sorted_pairs]
            signals = [p[1] for p in sorted_pairs]
            names = [p[2] for p in sorted_pairs]
            
            T1, S1 = temps[0], signals[0]
            
            # Get c2 value (check if any ITS-90 checkbox checked)
            # This is already handled by the line edit which updates when checkboxes change
            # This is already handled by the line edit which updates when checkboxes change
            c2 = float(self.sakuma_c2_edit.text())
            
            # Weighted Fit Flag
            use_weighted = self.weighted_fit_sched.isChecked()
            if use_weighted:
                self._log("Using Weighted Least Squares (Relative Error)", "INFO")

            result_str = ""
            roots = []
            
            # 3. Perform Fit based on n
            
            if n_selected == 1:
                # n=1: Calculate A, use Lambda and Sigma from inputs
                if self.wavelength is None:
                    # Try to use guess values if spectral data not loaded
                    try:
                        lamda = float(self.sakuma_phys_lambda.text())
                        self._log("Using manual λ₀ guess (no spectral data)", "INFO")
                    except ValueError:
                        QMessageBox.warning(self, "Error", "For n=1, please load spectral data or enter λ₀")
                        return
                    
                    try:
                        sigma = float(self.sakuma_sigma_edit.text())
                    except ValueError:
                        sigma = 0.0 # Default to narrow band
                else:
                    # Calculate lambda from spectral data
                    dot = np.sum(self.wavelength * self.spectral_resp)
                    sp_su = np.sum(self.spectral_resp)
                    lamda = 0.001 * dot / sp_su # to um
                    sigma = float(self.sakuma_sigma_edit.text()) # from input field (which is calc'd from spectral)
                
                # Setup equation: S1 = c / (exp(c2/(A*T+B)) - 1)
                # Where A = lambda*(1-6*(sigma/lambda)^2)
                #       B = c2*sigma^2/(2*lambda^2)
                #       c = unknown parameter (often called A' or C)
                # Here we solve for 'c' (amplitude factor)
                
                a_term = lamda * (1 - 6 * (sigma**2) / (lamda**2))
                b_term = c2 * (sigma**2) / (2 * (lamda**2))
                
                # c = S1 * (exp(c2 / (a_term*T1 + b_term)) - 1)
                c_val = S1 * (np.exp(c2 / (a_term * T1 + b_term)) - 1)
                
                self._log(f"n=1 fit completed: λ={lamda:.6f} μm, c={c_val:.6e}", "SUCCESS")
                roots = [a_term, b_term, c_val]
                
                # Display Results
                results = {
                    "λ (fixed)": f"{lamda:.6f} μm",
                    "σ (fixed)": f"{sigma:.6f} μm",
                    "a": f"{a_term:.6e}",
                    "b": f"{b_term:.6e}",
                    "c": f"{c_val:.6e}"
                }
                self.display_sakuma_results("Sakuma-Hattori (n=1)", results)
                
            elif n_selected == 2:
                # n=2: Fit Lambda and C, use Sigma from input
                sigma = float(self.sakuma_sigma_edit.text())
                T2, S2 = temps[1], signals[1]
                
                # Get initial guess for lambda
                try:
                    lamda_guess = float(self.sakuma_phys_lambda.text())
                except ValueError:
                    lamda_guess = 0.65
                
                # Define minimization function for Lambda
                # We need to find Lambda such that the calculated C is consistent for both points
                # OR solve 2 eq system
                
                def residuals_n2(x):
                    # x[0] = lambda
                    # x[1] = c
                    lam = x[0]
                    cc = x[1]
                    
                    if lam <= 0: return [1e9, 1e9]
                    
                    a_t = lam * (1 - 6 * (sigma**2) / (lam**2))
                    b_t = c2 * (sigma**2) / (2 * (lam**2))
                    
                    # Error = S_meas - S_calc
                    s1_calc = cc / (np.exp(c2 / (a_t * T1 + b_t)) - 1)
                    s2_calc = cc / (np.exp(c2 / (a_t * T2 + b_t)) - 1)
                    
                    res1 = S1 - s1_calc
                    res2 = S2 - s2_calc
                    
                    if use_weighted:
                        # Minimize relative error: (Obs - Calc) / Obs
                        # Avoid div by zero
                        if S1 != 0: res1 /= S1
                        if S2 != 0: res2 /= S2
                        
                    return [res1, res2]
                
                # Estimate c from first point
                a_init = lamda_guess * (1 - 6 * (sigma**2) / (lamda_guess**2))
                b_init = c2 * (sigma**2) / (2 * (lamda_guess**2))
                c_guess = S1 * (np.exp(c2 / (a_init * T1 + b_init)) - 1)
                
                result = least_squares(residuals_n2, [lamda_guess, c_guess], bounds=([0.1, 0], [10, np.inf]))
                
                lamda = result.x[0]
                c_val = result.x[1]
                a_term = lamda * (1 - 6 * (sigma**2) / (lamda**2))
                b_term = c2 * (sigma**2) / (2 * (lamda**2))
                
                self._log(f"n=2 fit completed: λ={lamda:.6f} μm, c={c_val:.6e}", "SUCCESS")
                roots = [a_term, b_term, c_val]
                
                # Display Results
                results = {
                    "λ (fitted)": f"{lamda:.6f} μm",
                    "σ (fixed)": f"{sigma:.6f} μm",
                    "a": f"{a_term:.6e}",
                    "b": f"{b_term:.6e}",
                    "c": f"{c_val:.6e}"
                }
                self.display_sakuma_results("Sakuma-Hattori (n=2)", results)
                
            else:
                # n>=3 mode - fit using inverse function (temperature from signal)
                # Matches user request: "n=3 should be fit like n>3 a.k.k full fit not lambda and sigma"
                is_coeff_mode = self.mode_coeff_radio.isChecked()
                
                if is_coeff_mode:
                    # Use coefficients directly
                    try:
                        a_temp = float(self.sakuma_coeff_a.text())
                        b_temp = float(self.sakuma_coeff_b.text())
                        c_temp = float(self.sakuma_coeff_c.text())
                        x0 = [a_temp, b_temp, c_temp]
                        self._log(f"Using coefficients guess: a={a_temp}, b={b_temp}, c={c_temp}", "INFO")
                    except ValueError:
                         self._log("Invalid coefficient input, using default", "WARNING")
                         x0 = [1.0e-6, 0.0, 1.0]

                else:
                    # Use Physical parameters to calculate a, b, c
                    try:
                        a0 = float(self.sakuma_phys_a0.text())
                        lamda0 = float(self.sakuma_phys_lambda.text())
                        sigma0 = float(self.sakuma_phys_sigma.text())
                        b0 = float(self.sakuma_phys_b0.text()) # Usually 0 or small
                        
                        # Calculate b0 and c0 from lambda and sigma
                        # Note: 'a_temp' here corresponds to 'A' in the simplified eqn S = C / (exp(c2/(AT+B)) - 1)
                        # Sakuma-Hattori: A ~= lambda * (1 - ...), B ~= ...
                        
                        a_temp = lamda0 * (1 - (6 * sigma0**2) / (lamda0**2))
                        b_temp = c2 * (sigma0**2) / (2 * lamda0**2) + b0
                        
                        # Calculate c_temp (C)
                        try:
                            exp_arg = c2 / (a_temp * temps[0] + b_temp)
                            if exp_arg > 700:
                                c_temp = signals[0] * 1e10
                            else:
                                c_temp = signals[0] * (np.exp(exp_arg) - 1)
                        except (OverflowError, RuntimeWarning):
                            c_temp = signals[0] * 1e10
                            
                        x0 = [a_temp, b_temp, c_temp]
                        self._log(f"Calculated guesses from physical: a={a_temp:.6e}, b={b_temp:.6e}, c={c_temp:.6e}", "INFO")
                    except ValueError:
                        self._log("Invalid physical input, using defaults", "WARNING")
                        x0 = [1.0e-6, 0.0, 1.0]
                
                xData = np.array(temps)
                yData = np.array(signals)
                
                # Fit using inverse function: T = (1/a) * ((c2/log((c/S)+1)) - b)
                def residual2(coeff, y, x):
                    """Residual for inverse Sakuma-Hattori: minimize T_measured - T_calculated"""
                    # Add validation to prevent log domain errors
                    with np.errstate(invalid='ignore', divide='ignore'):
                        ratio = (coeff[2] / x) + 1
                        # Only calculate where ratio > 0
                        mask = ratio > 0
                        residuals = np.zeros_like(y)
                        residuals[mask] = y[mask] - ((1 / coeff[0]) * ((c2 / np.log(ratio[mask])) - coeff[1]))
                        
                        if use_weighted:
                            # Relative error in T: (T_meas - T_calc) / T_meas
                            # y is T_meas
                            residuals[mask] /= y[mask]
                            
                        # For invalid points, use large residual to discourage them
                        residuals[~mask] = 1e10
                    return residuals
                
                # Use maxfev to allow more iterations
                roots, flag = leastsq(residual2, x0, args=(xData, yData), maxfev=2000)
                
                result_str = f"Sakuma-Hattori Parameters (n={n_selected}):\n"
                result_str += f"a = {roots[0]:.6e}\n"
                result_str += f"b = {roots[1]:.6e}\n"
                result_str += f"c = {roots[2]:.6e}\n"
                result_str += f"Flag: {flag}\n"
                
                if flag not in [1, 2, 3, 4]:
                    self._log(f"Warning: Fit may not have converged (flag={flag})", "WARNING")
                
                self._log(f"n={n_selected} fit completed", "SUCCESS")
                
                 # Display Results
                results = {
                    "a": f"{roots[0]:.6e}",
                    "b": f"{roots[1]:.6e}",
                    "c": f"{roots[2]:.6e}",
                    "Flag": f"{flag}"
                }
                self.display_sakuma_results(f"Sakuma-Hattori (n={n_selected})", results)
            
            # Store results
            self.sakuma_coeffs = roots
            
            # Plot fit (use all loaded calibration data if available, otherwise use selected points)
            if self.temperatures is not None and len(self.temperatures) > n_selected:
                xData_plot = self.temperatures
                yData_plot = self.signals
            else:
                xData_plot = np.array(temps)
                yData_plot = np.array(signals)
            
            # Get user-specified temperature range for fit plot
            try:
                t_min = float(self.sakuma_tmin_edit.text())
                t_max = float(self.sakuma_tmax_edit.text())
                if t_min >= t_max:
                    self._log("Warning: T_min must be less than T_max, using default range", "WARNING")
                    t_min, t_max = 1000, 3500
                elif t_min < 0 or t_max > 10000:
                    self._log("Warning: Temperature range out of reasonable bounds, using default", "WARNING")
                    t_min, t_max = 1000, 3500
            except ValueError:
                self._log("Warning: Invalid temperature range, using default 1000-3500 K", "WARNING")
                t_min, t_max = 1000, 3500
            
            # Interpolate over user-specified range
            xlin = np.linspace(t_min, t_max, 500)
            
            # Calculate fit with overflow protection
            with np.errstate(over='ignore', invalid='ignore'):
                exp_arg = c2 / (roots[0] * xlin + roots[1])
                # Clip extreme values to prevent overflow
                exp_arg = np.clip(exp_arg, -700, 700)
                exp_val = np.exp(exp_arg)
                y_fit = roots[2] / (exp_val - 1)
                # Replace any inf or nan with interpolated values
                valid_mask = np.isfinite(y_fit)
                if not np.all(valid_mask):
                    self._log("Warning: Some fit values are invalid, interpolating", "WARNING")
            
            self.sakuma_canvas.ax.clear()
            self.sakuma_canvas.ax.plot(xData_plot, yData_plot, 'o', label='Data', markersize=8)
            
            # Plot selected fixed points with labels
            for i, (t, s, name) in enumerate(zip(temps, signals, names)):
                if i == 0:
                    self.sakuma_canvas.ax.plot(t, s, 's', markersize=10, markerfacecolor='red', label='Selected FPs')
                else:
                    self.sakuma_canvas.ax.plot(t, s, 's', markersize=10, markerfacecolor='red')
                # Add text label for each fixed point
                self.sakuma_canvas.ax.annotate(name, (t, s), 
                                              textcoords="offset points", 
                                              xytext=(0, 10), 
                                              ha='center',
                                              fontsize=8,
                                              bbox=dict(boxstyle='round,pad=0.3', facecolor='yellow', alpha=0.7))
            
            self.sakuma_canvas.ax.plot(xlin, y_fit, '-', label='Fit', linewidth=2)
            self.sakuma_canvas.ax.set_xlabel('T (K)')
            self.sakuma_canvas.ax.set_ylabel('S (a.u.)')
            self.sakuma_canvas.ax.legend()
            self.sakuma_canvas.ax.grid(True, alpha=0.3)
            # Use subplots_adjust instead of tight_layout for more control over bottom margin (labels)
            self.sakuma_canvas.figure.subplots_adjust(bottom=0.15, top=0.90, left=0.12, right=0.95)
            self.sakuma_canvas.draw()
            
            # Plot error - calculate with validation to avoid log domain errors
            diff_list = []
            valid_indices = []
            for i in range(len(yData_plot)):
                if roots[0] != 0 and yData_plot[i] > 0:
                    ratio = (roots[2] / yData_plot[i]) + 1
                    if ratio > 0:
                        T_calc = (1 / roots[0]) * ((c2 / np.log(ratio)) - roots[1])
                        diff_list.append(T_calc)
                        valid_indices.append(i)
            
            if len(diff_list) > 0:
                diff_arr = np.array(diff_list)
                xData_plot_filtered = xData_plot[valid_indices]
                
                self.sakuma_error_canvas.ax.clear()
                self.sakuma_error_canvas.ax.plot(xData_plot_filtered, np.abs(xData_plot_filtered - diff_arr), 'o')
                self.sakuma_error_canvas.ax.set_xlabel('T (K)')
                self.sakuma_error_canvas.ax.set_ylabel('ΔT (K)')

                self.sakuma_error_canvas.ax.set_title('Fitting Error')
                self.sakuma_error_canvas.ax.grid(True, alpha=0.3)
                self.sakuma_error_canvas.draw()
            else:
                self._log("Warning: No valid data points for error plot", "WARNING")
            
            QMessageBox.information(self, "Success", f"Sakuma-Hattori fit completed (n={n_selected})")
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Sakuma-Hattori fit failed:\n{str(e)}")
            self._log(f"Sakuma-Hattori fit failed: {str(e)}", "ERROR")
    
    def display_sakuma_results(self, title, params_dict):
        """Display fit results in popup dialog"""
        # Store for re-opening
        self.last_sakuma_results = (title, params_dict)
        self.btn_show_results.setEnabled(True)
        
        # Show popup
        self.show_sakuma_results_popup()
        
    def _build_push_callback(self):
        """Return a callback to push Sakuma a,b,c,c2 to the corrections page, or None if not linked."""
        cp = getattr(self, 'corrections_page', None)
        if cp is None:
            return None
        c2_val = float(self.sakuma_c2_edit.text())
        def push(vals):
            try:
                if 'a' in vals and hasattr(cp, 'sse_a_edit'):
                    cp.sse_a_edit.setText(f"{vals['a']:.6e}")
                if 'b' in vals and hasattr(cp, 'sse_b_edit'):
                    cp.sse_b_edit.setText(f"{vals['b']:.6e}")
                if 'c' in vals and hasattr(cp, 'sse_c_edit'):
                    cp.sse_c_edit.setText(f"{vals['c']:.6e}")
                if hasattr(cp, 'sse_c2_edit'):
                    cp.sse_c2_edit.setText(f"{c2_val}")
                if hasattr(cp, '_log'):
                    cp._log(f"Sakuma-Hattori a/b/c/c2 pushed from Scale Realization", "SUCCESS")
            except Exception as e:
                from PySide6.QtWidgets import QMessageBox
                QMessageBox.warning(None, "Error", f"Push failed: {e}")
        return push
        
    def show_sakuma_results_popup(self):
        """Open the results popup"""
        if self.last_sakuma_results:
            title, params = self.last_sakuma_results
            dlg = SakumaResultDialog(title, params, self, on_push_callback=self._build_push_callback())
            dlg.exec_()
        else:
            QMessageBox.information(self, "Info", "No fit results available yet.")
    
    def set_corrections_page(self, cp):
        """Attach a CorrectionsPage reference so results can be pushed to it"""
        self.corrections_page = cp
                
    def sakuma_calculate(self, mode):
        """Calculate temperature from signal or signal from temperature using Sakuma-Hattori fit"""
        try:
            if not hasattr(self, 'sakuma_coeffs'):
                QMessageBox.warning(self, "Warning", "Please perform Sakuma-Hattori fit first")
                return
            
            # Get c2 value
            c2 = float(self.sakuma_c2_edit.text())  # in μm·K
            
            # Get coefficients [a, b, c]
            a, b, c = self.sakuma_coeffs[0], self.sakuma_coeffs[1], self.sakuma_coeffs[2]
            
            if mode == "T_to_S":
                # Calculate Signal from Temperature using Sakuma-Hattori equation
                # S = c / [exp(c2/(a*T + b)) - 1]
                temp = float(self.sakuma_calc_temp_edit.text())
                signal = c / (np.exp(c2 / (a * temp + b)) - 1)
                
                self.sakuma_calc_signal_edit.setText(f"{signal:.6e}")
                self.sakuma_calc_result_label.setText(f"✓ Calculated Signal: {signal:.6e}")
                self._log(f"Sakuma-Hattori Calculator: T={temp} K → S={signal:.6e}", "INFO")
                
            elif mode == "S_to_T":
                # Calculate Temperature from Signal
                # Rearrange: T = (c2 / ln((c/S) + 1) - b) / a
                signal = float(self.sakuma_calc_signal_edit.text())
                
                # Validate signal is positive and within reasonable range
                if signal <= 0:
                    raise ValueError("Signal must be positive")
                
                # Check if (c/S) + 1 is valid for logarithm
                ratio = (c / signal) + 1
                if ratio <= 0:
                    raise ValueError("Invalid signal value for this fit (c/S + 1 must be > 0)")
                
                temp = (c2 / np.log(ratio) - b) / a
                
                # Validate temperature is reasonable
                if temp < 0 or temp > 10000:
                    raise ValueError(f"Calculated temperature ({temp:.2f} K) is outside reasonable range")
                
                self.sakuma_calc_temp_edit.setText(f"{temp:.4f}")
                self.sakuma_calc_result_label.setText(f"✓ Calculated Temperature: {temp:.4f} K")
                self._log(f"Sakuma-Hattori Calculator: S={signal:.6e} → T={temp:.4f} K", "INFO")
                
        except ValueError as ve:
            QMessageBox.warning(self, "Invalid Input", "Please enter valid numerical values")
            self.sakuma_calc_result_label.setText("❌ Invalid input values")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Calculation failed:\n{str(e)}")
            self.sakuma_calc_result_label.setText(f"❌ Error: {str(e)}")
            self._log(f"Sakuma-Hattori calculation failed: {str(e)}", "ERROR")
    
    # Converter tab calculation methods
    def converter_its90_calculate(self, mode):
        """Calculate for converter tab using ITS-90 fit"""
        try:
            if not hasattr(self, 'its90_coeffs'):
                QMessageBox.warning(self, "Warning", "Please perform ITS-90 fit first in the ITS-90 Fit tab")
                self.conv_its90_result_label.setText("❌ Please perform ITS-90 fit first")
                return
            
            c2_fit = 0.014388 # Standard cm.K approx or use input if fitting used it?
            c2_microns = 14388.0
            
            # Using fitted coefficients for S->T
            if mode == "S_to_T":
                # Calculate Temperature from Signal using polynomial
                signal = float(self.conv_its90_signal_edit.text())
                
                if signal <= 0:
                    raise ValueError("Signal must be positive")
                
                ln_signal = np.log(signal)
                # T_inv = P(ln(S))
                T_inv = np.polyval(self.its90_coeffs, ln_signal)
                
                if T_inv <= 0:
                    raise ValueError("Invalid calculation result")
                
                temp = 1 / T_inv
                
                if temp < 0 or temp > 10000:
                    raise ValueError("Temperature out of reasonable range")
                
                self.conv_its90_temp_edit.setText(f"{temp:.4f}")
                self.conv_its90_result_label.setText(f"✓ ITS-90: S={signal:.6e} → T={temp:.4f} K")
                self._log(f"ITS-90 Converter: S={signal:.6e} → T={temp:.4f} K", "INFO")
                
            elif mode == "T_to_S":
                # For T->S, we must use the integral method if we have spectral data,
                # Or inverse the polynomial?
                # The original code for T->S in converter used INTEGRAL method
                
                if self.wavelength is None or self.spectral_resp is None:
                    # Fallback to inverting polynomial if possible, or error
                    QMessageBox.warning(self, "No Data", "Spectral data required for T->S calculation")
                    return
                
                # Recalculate integral ratio
                ref_temp = float(self.its90_ref_temp_edit.text())
                ref_signal = float(self.its90_ref_signal_edit.text())
                gain = float(self.its90_gain_edit.text())
                Sref = ref_signal / gain
                
                temp = float(self.conv_its90_temp_edit.text())
                c2 = float(self.c2_edit.text()) / 1e6 # um to m
                
                # integrals
                integrand_ref = self.spectral_resp / ((self.wavelength * 1e-9)**5 * (np.exp(c2 / (self.wavelength * 1e-9 * ref_temp)) - 1))
                integral_ref = np.trapz(integrand_ref, x=self.wavelength * 1e-9)
                
                integrand = self.spectral_resp / ((self.wavelength * 1e-9)**5 * (np.exp(c2 / (self.wavelength * 1e-9 * temp)) - 1))
                integral = np.trapz(integrand, x=self.wavelength * 1e-9)
                
                signal = Sref * integral / integral_ref
                
                self.conv_its90_signal_edit.setText(f"{signal:.6e}")
                self.conv_its90_result_label.setText(f"✓ ITS-90: T={temp} K → S={signal:.6e}")
                self._log(f"ITS-90 Converter: T={temp} K → S={signal:.6e}", "INFO")
                
        except ValueError as ve:
            QMessageBox.warning(self, "Invalid Input", "Please enter valid numerical values")
            self.conv_its90_result_label.setText("❌ Invalid input values")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Calculation failed:\n{str(e)}")
            self.conv_its90_result_label.setText(f"❌ Error: {str(e)}")
            self._log(f"ITS-90 converter calculation failed: {str(e)}", "ERROR")
    
    def converter_sakuma_calculate(self, mode):
        """Calculate for converter tab using Sakuma-Hattori fit"""
        try:
            if not hasattr(self, 'sakuma_coeffs'):
                QMessageBox.warning(self, "Warning", "Please perform Sakuma-Hattori fit first in the Sakuma-Hattori tab")
                self.conv_sakuma_result_label.setText("❌ Please perform Sakuma-Hattori fit first")
                return
            
            a, b, c = self.sakuma_coeffs
            c2 = float(self.sakuma_c2_edit.text())
            
            if mode == "T_to_S":
                # Calculate Signal from Temperature
                temp = float(self.conv_sakuma_temp_edit.text())
                
                # Sakuma-Hattori equation: S = c / [exp(c2/(a*T+b)) - 1]
                exponent = c2 / (a * temp + b)
                if exponent > 100:  # Prevent overflow
                    signal = 0
                else:
                    signal = c / (np.exp(exponent) - 1)
                
                self.conv_sakuma_signal_edit.setText(f"{signal:.6e}")
                self.conv_sakuma_result_label.setText(f"✓ Sakuma-Hattori: T={temp} K → S={signal:.6e}")
                self._log(f"Sakuma-Hattori Converter: T={temp} K → S={signal:.6e}", "INFO")
                
            elif mode == "S_to_T":
                # Calculate Temperature from Signal
                signal = float(self.conv_sakuma_signal_edit.text())
                
                if signal <= 0:
                    raise ValueError("Signal must be positive")
                
                # Inverse: T = (c2 / ln(c/S + 1) - b) / a
                ratio = c / signal
                if ratio <= 1:
                    raise ValueError("Signal too large for valid calculation")
                
                temp = (c2 / np.log(ratio + 1) - b) / a
                
                if temp < 0 or temp > 10000:
                    raise ValueError("Temperature out of reasonable range")
                
                self.conv_sakuma_temp_edit.setText(f"{temp:.4f}")
                self.conv_sakuma_result_label.setText(f"✓ Sakuma-Hattori: S={signal:.6e} → T={temp:.4f} K")
                self._log(f"Sakuma-Hattori Converter: S={signal:.6e} → T={temp:.4f} K", "INFO")
                
        except ValueError as ve:
            QMessageBox.warning(self, "Invalid Input", "Please enter valid numerical values")
            self.conv_sakuma_result_label.setText("❌ Invalid input values")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Calculation failed:\n{str(e)}")
            self.conv_sakuma_result_label.setText(f"❌ Error: {str(e)}")
            self._log(f"Sakuma-Hattori converter calculation failed: {str(e)}", "ERROR")
    
    def set_theme(self, theme_name):
        """Update theme"""
        self.theme_name = theme_name
        self.theme = ThemeManager.get_theme(theme_name)
        # Update all canvases
        if hasattr(self, 'input_canvas'):
            self.input_canvas.set_theme(theme_name)
        if hasattr(self, 'its90_canvas'):
            self.its90_canvas.set_theme(theme_name)
        if hasattr(self, 'sakuma_canvas'):
            self.sakuma_canvas.set_theme(theme_name)
        if hasattr(self, 'sakuma_error_canvas'):
            self.sakuma_error_canvas.set_theme(theme_name)

            self.its90_canvas.set_theme(theme_name)
        if hasattr(self, 'sakuma_canvas'):
            self.sakuma_canvas.set_theme(theme_name)
        if hasattr(self, 'sakuma_error_canvas'):
            self.sakuma_error_canvas.set_theme(theme_name)

