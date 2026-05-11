import json
import sys

import pandas as pd
import numpy as np
from PySide6.QtGui import QDoubleValidator, QPixmap
from PySide6.QtWidgets import QWidget, QTabWidget, QScrollArea, QHBoxLayout, QApplication, QVBoxLayout, QSizePolicy, \
    QSpacerItem, QTableWidget, QTableWidgetItem, QTableWidgetSelectionRange, QMenu, QGridLayout, QLabel, QLineEdit, \
    QPushButton, QSplitter, QFileDialog, QAbstractScrollArea, QAbstractItemView, QHeaderView, QCheckBox
from PySide6.QtCore import Qt, QLocale
from pathlib import Path
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qtagg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure

from plot_canvas import PlotCanvas

from RunUncertainty import RunUncertainty
from UncertaintyWidget import UncertaintyWidget
from uncertainty import UncertaintyComponent



class UncertaintyTabWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__()

        models_dir = Path(__file__).parent.parent / "models"
        with open(models_dir / 'standard_deviation_model.json', 'r') as openfile:
            self.std_model = json.load(openfile)

        with open(models_dir / 'mean_wavelength_model.json', 'r') as openfile:
            self.mean_wl_model = json.load(openfile)

        with open(models_dir / 'in-use_signal_model.json', 'r') as openfile:
            self.in_use_signal_model = json.load(openfile)

        self.main_window = parent
        self.n = 0
        self.mean_wl = None
        self.std = None
        self.in_use = None
        self.run = None
        self.sigma = None

        # ------- Main Layout --------
        self.main_layout = QHBoxLayout(self)

        # ------- Splitter ---------
        self.tab_splitter = QSplitter(self)
        self.tab_splitter.setOrientation(Qt.Orientation.Horizontal)

        # ------- Left Side Container (Fixed Points + Components) -------------
        self.left_container = QWidget()
        self.left_layout = QVBoxLayout(self.left_container)
        self.left_layout.setContentsMargins(0, 0, 0, 0)
        
        # Create vertical splitter for Fixed Points Table and Components
        self.left_splitter = QSplitter(self.left_container)
        self.left_splitter.setOrientation(Qt.Orientation.Vertical)
        
        # ------- Fixed Points Table Section -------------
        self.fixed_points_container = QWidget()
        self.fixed_points_table_layout = QVBoxLayout(self.fixed_points_container)

        #buttons layout
        buttons_layout = QHBoxLayout()
        self.fixed_points_table_layout.addLayout(buttons_layout)

        # Run button
        run_button = QPushButton("Run")
        run_button.setMinimumHeight(35)
        run_button.setStyleSheet("font-size: 12pt; font-weight: bold; padding: 5px;")
        buttons_layout.addWidget(run_button)



        # Table label
        self.fixed_point_table_label = QLabel("Fixed Points:")
        self.fixed_point_table_label.setStyleSheet("font-size: 12pt; font-weight: bold;")
        self.fixed_points_table_layout.addWidget(self.fixed_point_table_label)

        # Tables
        self.fixed_point_table = QTableWidget()
        self.fixed_point_table.setRowCount(0)
        self.fixed_point_table.setColumnCount(4) # Increased to 4
        self.fixed_point_table.setHorizontalHeaderLabels(["Select", "Name", "Temperature", "ITS-90"]) # Added ITS-90
        self.fixed_point_table.horizontalHeader().setStretchLastSection(False)
        self.fixed_point_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.fixed_point_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch) # Stretch Name column
        self.fixed_point_table.setSizeAdjustPolicy(QAbstractScrollArea.SizeAdjustPolicy.AdjustToContents)
        self.fixed_point_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.fixed_point_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.fixed_point_table.setStyleSheet("QTableWidget { font-size: 11pt; } QHeaderView::section { font-size: 11pt; font-weight: bold; }")
        self.fixed_points_table_layout.addWidget(self.fixed_point_table)

        # --------- Uncertainty Components ---------------
        self.uncertainty_components_widget = QWidget()

        self.uncertainty_components_scroll = QScrollArea()
        self.uncertainty_components_scroll.setWidgetResizable(True)
        self.uncertainty_components_scroll.setWidget(self.uncertainty_components_widget)

        self.uncertainty_components_tab = QTabWidget(self)
        self.uncertainty_components_tab.addTab(self.uncertainty_components_scroll, "Components")
        
        # Add both containers to the vertical splitter
        self.left_splitter.addWidget(self.fixed_points_container)
        self.left_splitter.addWidget(self.uncertainty_components_tab)
        self.left_splitter.setStretchFactor(0, 1)  # Fixed points table
        self.left_splitter.setStretchFactor(1, 2)  # Components area gets more space
        self.left_splitter.setSizes([250, 500])  # Initial sizes
        
        # Add the vertical splitter to the left container
        self.left_layout.addWidget(self.left_splitter)

        # --------- Results Tabs (Graph and Table) --------
        self.results_tabs = QTabWidget(self)

        # Graph tab
        self.graph_tab_scroll = QScrollArea()
        self.graph_tab_scroll.setWidgetResizable(True)
        self.results_tabs.addTab(self.graph_tab_scroll, "Graph")

        self.graph_tab = QWidget()
        self.graph_tab_scroll.setWidget(self.graph_tab)

        self.graph_tab_layout = QVBoxLayout()

        # Graph tab - Sakuma-Hattori Coefficients
        self.coefficients_layout = QHBoxLayout()
        self.graph_tab_layout.addLayout(self.coefficients_layout)

        sakuma_hattori_label = QLabel("<html><body><b>Sakuma-Hattori Equation Coefficients:</b></body></html>")
        self.coefficients_layout.addWidget(sakuma_hattori_label)

        a1_label = QLabel("a1:")
        self.coefficients_layout.addWidget(a1_label)

        self.a1_edit = QLineEdit()
        self.a1_edit.setReadOnly(True)
        self.coefficients_layout.addWidget(self.a1_edit)

        a2_label = QLabel("a2:")
        self.coefficients_layout.addWidget(a2_label)

        self.a2_edit = QLineEdit()
        self.a2_edit.setReadOnly(True)
        self.coefficients_layout.addWidget(self.a2_edit)

        a3_label = QLabel("a3:")
        self.coefficients_layout.addWidget(a3_label)

        self.a3_edit = QLineEdit()
        self.a3_edit.setReadOnly(True)
        self.coefficients_layout.addWidget(self.a3_edit)

        # Graph tab - calculations
        self.calculation_layout = QHBoxLayout()
        self.graph_tab_layout.addLayout(self.calculation_layout)
        self.graph_tab.setLayout(self.graph_tab_layout)

        calcul_label = QLabel("Temperature (K):")
        self.calculation_layout.addWidget(calcul_label)

        self.calcul_temp_edit = QLineEdit()
        calcul_temp_validator = QDoubleValidator()
        calcul_temp_validator.setLocale(QLocale(QLocale.English))
        self.calcul_temp_edit.setValidator(calcul_temp_validator)

        self.calculation_layout.addWidget(self.calcul_temp_edit)

        self.calcul_signal_btn = QPushButton("Calculate")
        self.calculation_layout.addWidget(self.calcul_signal_btn)

        calcul_label2 = QLabel("Signal:")
        self.calculation_layout.addWidget(calcul_label2)

        self.calcul_signal_edit = QLineEdit()
        calcul_signal_validator = QDoubleValidator()
        calcul_signal_validator.setLocale(QLocale(QLocale.English))
        self.calcul_signal_edit.setValidator(calcul_signal_validator)
        self.calculation_layout.addWidget(self.calcul_signal_edit)

        self.calcul_button = QPushButton("Calculate")
        self.calculation_layout.addWidget(self.calcul_button)

        spacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self.calculation_layout.addItem(spacer)

        # Graph tab - figures
        figures_tabs = QTabWidget(self)
        self.graph_tab_layout.addWidget(figures_tabs)

        # We will get the theme from main_window if possible, default to Nord Dark
        theme_name = "Nord Dark"
        if parent and hasattr(parent, 'theme_name'):
            theme_name = parent.theme_name

        self.graph_canvas_cal = PlotCanvas("Calibration", parent=self, theme_name=theme_name)
        self.cal_ax = self.graph_canvas_cal.ax
        calib_tab = QWidget()
        calib_tab_layout = QVBoxLayout(calib_tab)
        calib_tab_layout.addWidget(self.graph_canvas_cal)
        figures_tabs.addTab(calib_tab, "Calibration")

        self.graph_canvas_un = PlotCanvas("Uncertainty", parent=self, theme_name=theme_name)
        self.un_ax = self.graph_canvas_un.ax
        un_tab = QWidget()
        unc_tab_layout = QVBoxLayout(un_tab)
        unc_tab_layout.addWidget(self.graph_canvas_un)
        figures_tabs.addTab(un_tab, "Uncertainty")

        self.graph_canvas_err = PlotCanvas("Fit Error", parent=self, theme_name=theme_name)
        self.err_ax = self.graph_canvas_err.ax
        fit_tab = QWidget()
        fit_tab_layout = QVBoxLayout(fit_tab)
        fit_tab_layout.addWidget(self.graph_canvas_err)
        figures_tabs.addTab(fit_tab, "Fit Error")

        # Table Tab
        self.table_tab = QWidget()
        self.results_tabs.addTab(self.table_tab, "Table")

        self.table_tab_layout = QVBoxLayout()
        self.table_tab.setLayout(self.table_tab_layout)
        self.table = QTableWidget()
        self.table_tab_layout.addWidget(self.table)

        # ------------ Tab Splitter ------------
        self.tab_splitter.addWidget(self.left_container)
        self.tab_splitter.addWidget(self.results_tabs)
        
        # Set splitter to be resizable with better initial sizes
        self.tab_splitter.setStretchFactor(0, 1)  # Left side (components) can stretch
        self.tab_splitter.setStretchFactor(1, 2)  # Right side (results) stretches more
        self.tab_splitter.setSizes([500, 800])  # Better initial sizes
        self.tab_splitter.setCollapsible(0, False)  # Don't allow left side to collapse
        self.tab_splitter.setCollapsible(1, False)  # Don't allow right side to collapse
        
        self.main_layout.addWidget(self.tab_splitter)

        # ----------- Fixed Point Tab -----------
        self.fixed_points_layout_m = QVBoxLayout()
        self.fixed_points_layout = QVBoxLayout()
        self.uncertainty_components_widget.setLayout(self.fixed_points_layout_m)
        self.fixed_points_layout_m.addLayout(self.fixed_points_layout)
        self.fixed_points_layout_m.addItem(
            QSpacerItem(0, 0, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding))

        self.model_func_layout = QVBoxLayout()
        self.model_label_text = QLabel("Model Function (Sakuma-Hattori):")
        self.model_func_layout.addWidget(self.model_label_text)
        img_path = str(Path(__file__).parent.parent / "img" / "model_function.png")
        pixmap = QPixmap(img_path)
        pixmap_resized = pixmap.scaled(500, 500, Qt.AspectRatioMode.KeepAspectRatio, Qt.SmoothTransformation)
        self.model_label = QLabel()
        self.model_label.setPixmap(pixmap_resized)
        self.model_func_layout.addWidget(self.model_label)
        self.fixed_points_layout_m.insertLayout(0, self.model_func_layout)

        self.add_std_un_widget()
        self.add_mean_wl_un_widget()
        self.add_in_use_signal_un_widget()

        size_policy = self.uncertainty_components_widget.sizePolicy()
        size_policy.setHorizontalPolicy(QSizePolicy.Expanding)
        size_policy.setVerticalPolicy(QSizePolicy.Expanding)
        self.uncertainty_components_widget.setSizePolicy(size_policy)

        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.custom_context_menu_requested)
        self.calcul_button.clicked.connect(self.calculate_temp_button_action)
        self.calcul_signal_btn.clicked.connect(self.calculate_signal_button_action)
        run_button.clicked.connect(self.run_uncertainty)

    def calculate_signal_button_action(self):
        T = float(self.calcul_temp_edit.text())
        self.calcul_signal_edit.setText(str(self.run.sakuma_hattori_signal(T)))

    def calculate_temp_button_action(self):
        S = float(self.calcul_signal_edit.text())
        self.calcul_temp_edit.setText(str(self.run.inv_sakuma_hattor_signal(S)))

    def run_uncertainty(self, s):

        # Collect fixed points first to determine N
        layout = self.fixed_points_layout
        count = layout.count()
        uncertainty_components = []

        for i in range(count):
            widget = layout.itemAt(i).widget()
            uncertainty_components.append(widget.get_info())
        
        # Check selected count
        selected_count = sum(1 for comp in uncertainty_components if comp.get("IsFixedPoint", False))
        
        # Validate at least one fixed point is selected
        if selected_count == 0:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "No Fixed Points Selected", 
                              "Please select at least one fixed point (check the checkbox) before running uncertainty analysis.")
            return

        # Validate sensor data (Required only if N < 3)
        sensor_data_available = len(self.main_window.sensor_wl) > 0 and len(self.main_window.sensor_res) > 0
        
        if selected_count < 3 and not sensor_data_available:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "No Sensor Data", 
                              f"For {selected_count} fixed point(s) (N < 3), spectral response data is required.\n"
                              "Please load sensor data using 'Load Sensor Data' button.")
            return
        
        # Check if any selected component has IsITS90 set to True
        its90 = False
        for comp in uncertainty_components:
            if comp.get("IsFixedPoint", False) and comp.get("IsITS90", False):
                its90 = True
                break
        
        T_lim = self.main_window.unc_graphs_temp_limits
        
        # Pass sensor data (might be empty if N >= 3, which is handled by RunUncertainty)
        self.run = RunUncertainty(uncertainty_components, self.main_window.sensor_wl, self.main_window.sensor_res)
        (T_cal, cal) = self.run.make_calibration(its90, np.arange(*T_lim))
        (T_un, un) = self.run.calculate_componets_un(np.arange(*T_lim), its90)

        title = self.run.get_title()
        self.plot_un_graph(T_un, un, self.run.get_label(its90), title)
        self.plot_cal_graph(T_cal, cal, title)
        T = UncertaintyComponent.to_SI_Units(None, self.run.T, self.run.T_units)[0]
        self.plot_err_graph(T, np.abs(self.run.inv_sakuma_hattor_signal(self.run.S) - T))
        self.fill_table()

        self.a1_edit.setText(str(self.run.a1))
        self.a2_edit.setText(str(self.run.a2))
        self.a3_edit.setText(str(self.run.a3))


    def export_uncertainty(self, T):
        S = self.run.get_detailed_uns(T)
        vHeader = self.getVerticallHeaderLabels()[2:]
        hHeader = np.array(T).astype(str)
        df = pd.DataFrame(S[0], columns=hHeader, index=vHeader)
        df.insert(0, 'Value', S[1])

        file_dialog = QFileDialog(self)
        file_dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptSave)
        file_path, _ = file_dialog.getSaveFileName(self, filter="*.xlsx", dir="UncertaintyData")

        df.to_excel(file_path)

    def export_calibration(self, T):
        S = self.run.sakuma_hattori_signal(T)
        df = pd.DataFrame(np.transpose(np.array([T,S])), columns=["Temperature, K", "Signal"])

        file_dialog = QFileDialog(self)
        file_dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptSave)
        file_path, _ = file_dialog.getSaveFileName(self, filter="*.xlsx", dir="CalibrationData")

        df.to_excel(file_path, index=False)

    def custom_context_menu_requested(self, pos):
        table = self.sender()
        it = table.itemAt(pos)
        if it is None:
            return
        r = it.row()
        item_range = QTableWidgetSelectionRange(r, 0, r, table.columnCount() - 1)
        table.setRangeSelected(item_range, True)

        menu = QMenu()
        add_row_action = menu.addAction("Add Component")
        export_action = menu.addAction("Export")
        action = menu.exec(table.viewport().mapToGlobal(pos))
        if action == add_row_action:
            self.add_point()
        elif action == export_action:
            self.export_to_excel()

    def export_to_excel(self):
        # Convert the table data to a DataFrame
        table_data = []
        for row in range(self.table.rowCount()):
            row_data = []
            for column in range(self.table.columnCount()):
                item = self.table.item(row, column)
                if item is not None:
                    row_data.append(item.text())
                else:
                    row_data.append("")
            table_data.append(row_data)

        df = pd.DataFrame(table_data, index=self.getVerticallHeaderLabels())

        # Export the DataFrame to Excel
        file_path, _ = QFileDialog.getSaveFileName(self, "Save Excel File", "", "Excel Files (*.xlsx)")
        if file_path:
            df.to_excel(file_path, header=False)

    def getVerticallHeaderLabels(self):
        labels = []
        for column in range(self.table.rowCount()):
            header_item = self.table.verticalHeaderItem(column)
            if header_item is not None:
                labels.append(header_item.text())
            else:
                labels.append("")
        return labels

    def add_point(self):
        self.add = AddPoint()
        self.add.add_button.clicked.connect(self.add_point_clicked)
        self.add.show()

    def add_point_clicked(self):
        res = [[self.add.name_edit.text(), float(self.add.temp_edit.text())]]
        self.set_table_fix_points(res)


    def fill_table(self):
        row_headers = self.run.get_components_names()
        fixed_point_meta_data = self.run.get_fixed_points()
        self.set_table_row_headers(row_headers)
        self.set_table_fix_points(fixed_point_meta_data)

    def set_table_fix_points(self, data):
        for d in data:
            count = self.table.columnCount()
            self.table.setColumnCount(count+1)
            self.table.setItem(0, count, QTableWidgetItem(d[0]+"("+str(d[1])+" K)"))
            self.table.setItem(1, 0, QTableWidgetItem("Values"))
            self.table.setItem(1, count, QTableWidgetItem("Temp.Unc.(K)"))
            uns, uns_val = self.run.get_detailed_uns([d[1]])
            for i, un in enumerate(uns):
                self.table.setItem(i + 2, 0, QTableWidgetItem(uns_val[i]))
                self.table.setItem(i+2, count, QTableWidgetItem("{:.3f}".format(round(un[0], 3))))

    def set_table_row_headers(self, row_headers):
        self.table.setColumnCount(1)
        headers = ["", "Uncertainty Component"]
        for h in row_headers.keys():
            headers.append(h)
            for hh in row_headers[h]:
                headers.append("   "+hh)
        headers.append("Combined Uncertainty")
        self.table.setRowCount(len(headers))
        self.table.setVerticalHeaderLabels(headers)

    def plot_un_graph(self, T, data, labels, title=""):
        self.un_ax.clear()

        for d in data:
            self.un_ax.plot(T, d)
            
        self.graph_canvas_un.title = 'Uncertainty ' + title
        self.un_ax.set_title(self.graph_canvas_un.title, fontsize=12, color=self.graph_canvas_un.text_color, weight='bold')
        self.un_ax.set_xlabel("Temperature, K", color=self.graph_canvas_un.text_color)
        self.un_ax.set_ylabel("Uncertainty, K", color=self.graph_canvas_un.text_color)
        self.un_ax.tick_params(colors=self.graph_canvas_un.text_color)
        self.un_ax.grid(True, alpha=0.3, color=self.graph_canvas_un.grid_color, linestyle='--')
        
        # Legend logic to avoid repeating elements nicely
        legend = self.un_ax.legend(labels)
        if legend:
            for text in legend.get_texts():
                text.set_color(self.graph_canvas_un.text_color)
        
        self.graph_canvas_un.draw()

    def plot_cal_graph(self, T, data, title=""):
        self.cal_ax.clear()

        markers = ["-", "."]
        size = [3, 12]
        
        colors = [self.graph_canvas_cal.accent_color, '#e74c3c'] # Main line color and points color
        for i, (t, d, m, s) in enumerate(zip(T, data, markers, size)):
            color = colors[i % len(colors)]
            self.cal_ax.plot(t, d, m, markersize=s, color=color)
            
        self.graph_canvas_cal.title = 'Calibration ' + title
        self.cal_ax.set_title(self.graph_canvas_cal.title, fontsize=12, color=self.graph_canvas_cal.text_color, weight='bold')
        self.cal_ax.set_ylabel("Signal, a.u", color=self.graph_canvas_cal.text_color)
        self.cal_ax.set_xlabel("Temperature, K", color=self.graph_canvas_cal.text_color)
        self.cal_ax.tick_params(colors=self.graph_canvas_cal.text_color)
        self.cal_ax.grid(True, alpha=0.3, color=self.graph_canvas_cal.grid_color, linestyle='--')
        self.graph_canvas_cal.draw()

    def plot_err_graph(self, T, delT):
        self.err_ax.clear()
        mkr_size = 12
        self.err_ax.plot(T, delT, ".", markersize=mkr_size, color=self.graph_canvas_err.accent_color)
        
        self.graph_canvas_err.title = "Fit Error"
        self.err_ax.set_title(self.graph_canvas_err.title, fontsize=12, color=self.graph_canvas_err.text_color, weight='bold')
        self.err_ax.set_xlabel("Temperature, K", color=self.graph_canvas_err.text_color)
        self.err_ax.set_ylabel(r"Error, $\Delta$K", color=self.graph_canvas_err.text_color)
        self.err_ax.tick_params(colors=self.graph_canvas_err.text_color)
        self.err_ax.grid(True, alpha=0.3, color=self.graph_canvas_err.grid_color, linestyle='--')
        self.graph_canvas_err.draw()

    def add_mean_wl_un_widget(self, insert=-1):
        self.mean_wl = UncertaintyWidget()
        self.mean_wl.setToolTip("The mean wavelength of the relative spectral responsivity")
        self.mean_wl.hide_secounds()
        self.mean_wl.temp_label.setText("<html><body>"
                                        "<span>Mean Wavelength (nm):</span>"
                                        "<span style='font-size: 16px;'> &#955;<sub>0</sub></span>"
                                        "</body></html>")
        self.mean_wl.temp_un_label.setText("Components")
        self.mean_wl.load_fixed_point(self.mean_wl_model)
        self.mean_wl.index = -2
        self.mean_wl.save_button.clicked.connect(self.update_mean_or_std)
        if insert >= 0:
            self.fixed_points_layout.insertWidget(insert, self.mean_wl)
        else:
            self.fixed_points_layout.addWidget(self.mean_wl)

    def add_in_use_signal_un_widget(self, insert=-1):
        self.in_use = UncertaintyWidget()
        self.in_use.setToolTip("Radiation thermometer signal")
        self.in_use.hide_secounds()
        self.in_use.temp_edit.hide()
        self.in_use.temp_combo.hide()
        self.in_use.temp_label.setText("<html><body>"
                                       "<span>In-use Signal:</span>"
                                       "<span style='font-size: 16px;'> S<sub>in</sub></span>"
                                       "</body></html>")
        self.in_use.temp_un_label.setText("Components")
        self.in_use.load_fixed_point(self.in_use_signal_model)
        self.in_use.index = -4
        self.in_use.save_button.clicked.connect(self.update_mean_or_std)
        if insert >= 0:
            self.fixed_points_layout.insertWidget(insert, self.in_use)
        else:
            self.fixed_points_layout.addWidget(self.in_use)

    def update_mean_or_std(self):
        button = self.sender()
        un_widget = button.parentWidget().parentWidget()
        if un_widget.index == -2:
            self.mean_wl_model = un_widget.get_info()
        elif un_widget.index == -3:
            self.std_model = un_widget.get_info()
        elif un_widget.index == -4:
            self.in_use_signal_model = un_widget.get_info()

    def add_std_un_widget(self, insert=-1):
        self.std = UncertaintyWidget()
        self.std.setToolTip("The standard deviation of the relative spectral responsivity")
        self.std.hide_secounds()
        self.std.temp_label.setText("<html><body>"
                                   "<span> Standard Deviation (nm):</span>"
                                   "<span style='font-size: 16px;'> &sigma;</span>"
                                   "</body></html>")
        self.std.temp_un_label.setText("Components")
        self.std.load_fixed_point(self.std_model)
        self.std.index = -3
        self.std.save_button.clicked.connect(self.update_mean_or_std)
        if insert >= 0:
            self.fixed_points_layout.insertWidget(insert, self.std)
        else:
            self.fixed_points_layout.addWidget(self.std)

        if self.sigma is not None:
            self.std.temp_edit.setText("{:.3f}".format(self.sigma))

    def add_fixed_point(self, fixed_point):
        self.fixed_points_layout.addWidget(fixed_point)
        if self.n == 2:
            self.mean_wl.hide()
            self.mean_wl.isWidgetActive = False
        elif self.n == 3:
            self.delete_fixed_point(-3)
            self.std = None

    def delete_fixed_point(self, row_index):
        for index in range(self.fixed_points_layout.count()):
            item = self.fixed_points_layout.itemAt(index)
            wwidget = item.widget()
            if wwidget.index == row_index:
                if self.n == 2:
                    self.add_std_un_widget(0)
                elif self.n == 1:
                    self.mean_wl.show()
                    self.mean_wl.isWidgetActive = True

                self.fixed_points_layout.removeWidget(wwidget)
                wwidget.setParent(None)
                wwidget.deleteLater()
                break

class AddPoint(QWidget):
    def __init__(self):
        super().__init__()

        self.main_layout = QGridLayout()
        self.setLayout(self.main_layout)

        name_label = QLabel("Name")
        self.main_layout.addWidget(name_label, 0, 0)
        self.name_edit = QLineEdit("")
        self.main_layout.addWidget(self.name_edit, 0, 1)
        temp_label = QLabel("Temperature (K)")
        self.main_layout.addWidget(temp_label, 1, 0)
        self.temp_edit = QLineEdit()
        self.temp_edit.setValidator(QDoubleValidator())
        self.main_layout.addWidget(self.temp_edit, 1, 1)

        self.add_button = QPushButton("Add")
        self.close_button = QPushButton("Close")
        self.main_layout.addWidget(self.add_button, 2, 0)
        self.main_layout.addWidget(self.close_button, 2, 1)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    widget = UncertaintyTabWidget()
    widget.show()
    sys.exit(app.exec())
