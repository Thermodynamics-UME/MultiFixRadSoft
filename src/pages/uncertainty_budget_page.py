import sys
import logging
import json
from pathlib import Path
import numpy as np
import pandas as pd
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                               QPushButton, QFileDialog, QMessageBox, QCheckBox, 
                               QTableWidgetItem, QMenu)
from PySide6.QtCore import Qt

from theme_manager import ThemeManager

logger = logging.getLogger(__name__)

# Try to import uncertainty modules
# These are expected to be in the src folder (or added to path by main script)
try:
    from UncertaintyTabWidget import UncertaintyTabWidget
    from UncertaintyWidget import UncertaintyWidget
    from addFixedPoint import AddFixedPoint
    from GraphsOptions import GraphsOptions
    from ExportSettings import ExportSettings
    # RunUncertainty, UncertaintyFunctions, uncertainty imported by the widgets above
except ImportError:
    UncertaintyTabWidget = None
    UncertaintyWidget = None
    AddFixedPoint = None
    GraphsOptions = None
    ExportSettings = None

class UncertaintyBudgetPage(QWidget):
    """Uncertainty Budget page using UncertaintyTabWidget from main.py architecture"""
    
    def __init__(self, theme_name="Nord Dark"):
        super().__init__()
        self.theme_name = theme_name
        
        # Data storage (matching main.py)
        self.fixed_points = {}  # Dictionary, not list
        self.uncertainty_components = []
        self.sensor_wl = np.array([])  # Initialize as numpy array
        self.sensor_res = np.array([])  # Initialize as numpy array
        self.unc_graphs_temp_limits = [1000, 3200]
        
        self.init_ui()
    
    def init_ui(self):
        """Initialize the UI"""
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Check if UncertaintyTabWidget is available
        if UncertaintyTabWidget is None:
            error_label = QLabel(
                "⚠️ UncertaintyTabWidget not available.\n\n"
                "Please ensure the uncertainty modules are in the src folder:\n"
                "- UncertaintyTabWidget.py\n"
                "- UncertaintyWidget.py\n"
                "- addFixedPoint.py\n"
                "- GraphsOptions.py\n"
                "- ExportSettings.py"
            )
            error_label.setStyleSheet("color: #ff6b6b; padding: 20px; font-size: 12pt;")
            error_label.setAlignment(Qt.AlignCenter)
            main_layout.addWidget(error_label)
        else:
            # Compact toolbar at the top
            toolbar = QWidget()
            toolbar.setMaximumHeight(40)
            toolbar_layout = QHBoxLayout(toolbar)
            toolbar_layout.setContentsMargins(10, 5, 10, 5)
            
            # Menu button
            menu_btn = QPushButton("☰ Menu")
            menu_btn.setMaximumWidth(100)
            menu_btn.setMaximumHeight(28)
            menu_btn.setToolTip("File, Export, and Settings")
            menu_btn.clicked.connect(self.show_menu)
            
            # Apply theme to menu button
            theme = ThemeManager.get_theme(self.theme_name)
            menu_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {theme['ACCENT_COLOR']};
                    color: {theme['TEXT_PRIMARY']};
                    border: none;
                    border-radius: 4px;
                }}
                QPushButton:hover {{
                    background-color: {theme['SECONDARY_COLOR']};
                }}
            """)
            
            toolbar_layout.addWidget(menu_btn)
            toolbar_layout.addStretch()
            
            main_layout.addWidget(toolbar)
            
            # Create uncertainty tab widget
            self.uncertainty_tab = UncertaintyTabWidget(self)
            main_layout.addWidget(self.uncertainty_tab)
            
            # Connect context menu for fixed points table
            # Check if table exists (it should)
            if hasattr(self.uncertainty_tab, 'fixed_point_table'):
                self.uncertainty_tab.fixed_point_table.customContextMenuRequested.connect(
                    self.fixed_points_custom_context_menu_requested
                )
            
            # Try to auto-load default sensor data
            self.auto_load_sensor_data()
        
        self.setLayout(main_layout)
    
    def show_menu(self):
        """Show dropdown menu with all options"""
        menu = QMenu(self)
        
        # Fixed Points section
        menu.addSection("Fixed Points")
        new_fp_action = menu.addAction("New Fixed Point")
        new_fp_action.triggered.connect(self.add_new_fixed_point_window)
        
        load_fp_action = menu.addAction("Load Fixed Point(s)")
        load_fp_action.triggered.connect(self.load_fixed_points)
        
        menu.addSeparator()
        
        # Sensor Data section
        menu.addSection("Sensor Data")
        load_sensor_action = menu.addAction("Load Sensor Data")
        load_sensor_action.triggered.connect(self.load_sensor_data)
        
        menu.addSeparator()
        
        # Export section
        menu.addSection("Export")
        export_cal_action = menu.addAction("Export Calibration")
        export_cal_action.triggered.connect(self.export_calibration)
        
        export_unc_action = menu.addAction("Export Uncertainty")
        export_unc_action.triggered.connect(self.export_uncertainty)
        
        menu.addSeparator()
        
        # Settings section
        menu.addSection("Settings")
        graph_opt_action = menu.addAction("Graph Options")
        graph_opt_action.triggered.connect(self.show_uncertainty_graph_options)
        
        # Show menu at button position
        menu_btn = self.sender()
        menu.exec(menu_btn.mapToGlobal(menu_btn.rect().bottomLeft()))
    
    def auto_load_sensor_data(self):
        """Automatically load default sensor data and fixed points if available"""
        # Note: logic adapted slightly for path differences
        # Assuming folder "MultiFIX Calculator v0.9.1" is in the same dir as the main script
        # But we are in src/pages/ now.
        # Main script is at root.
        # Original code: Path(__file__).parent / "MultiFIX Calculator v0.9.1" / "SensorData.csv"
        # Where __file__ was MultiFixCalculator.py
        
        # We need to find the root directory.
        # If we assume src/pages is 2 levels deep from root
        root_dir = Path(__file__).parent.parent.parent
        
        # Load sensor data
        try:
            sensor_data_path = root_dir / "SensorData.csv"
            if sensor_data_path.exists():
                df = pd.read_csv(sensor_data_path)
                self.sensor_wl = np.array(df.values[:, 0], dtype=float)
                self.sensor_res = np.array(df.values[:, 1], dtype=float)
                
                # Calculate mean wavelength and standard deviation
                from scipy import integrate
                lam = integrate.simpson(self.sensor_wl * self.sensor_res, self.sensor_wl) / \
                      integrate.simpson(self.sensor_res, self.sensor_wl)
                sig = (integrate.simpson((self.sensor_wl - lam) ** 2 * self.sensor_res, self.sensor_wl) / \
                       integrate.simpson(self.sensor_res, self.sensor_wl)) ** 0.5
                
                # Update uncertainty tab
                if hasattr(self, 'uncertainty_tab'):
                    self.uncertainty_tab.mean_wl.temp_edit.setText("{:.3f}".format(lam))
                    self.uncertainty_tab.std.temp_edit.setText("{:.3f}".format(sig))
                    self.uncertainty_tab.sigma = sig
                
                logger.info("Auto-loaded sensor data: λ=%.3f nm, σ=%.3f nm", lam, sig)
        except Exception as e:
            pass # Silent fail for auto-load
        
        # Auto-load fixed points from Fixed Points folder
        try:
            fixed_points_folder = root_dir / "Fixed Points"
            if fixed_points_folder.exists():
                json_files = list(fixed_points_folder.glob("*.json"))
                for json_file in json_files:
                    try:
                        with open(json_file, "r") as openfile:
                            fix_point = json.load(openfile)
                            # Add to dictionary first to get the correct index
                            fp_index = len(self.fixed_points.keys())
                            self.fixed_points[fp_index] = fix_point
                            # Then add to table with the correct index
                            self.add_row_fixed_points_table(fix_point, fp_index)
                    except Exception as e:
                        logger.debug("Could not load %s: %s", json_file.name, e)
                
                if json_files:
                    logger.info("Auto-loaded %d fixed points", len(json_files))
        except Exception as e:
            pass
    
    def show_uncertainty_graph_options(self):
        """Show dialog to set temperature limits for uncertainty graphs"""
        if GraphsOptions is None:
            QMessageBox.warning(self, "Warning", "GraphsOptions module not available")
            return
        
        dialog = GraphsOptions(self.unc_graphs_temp_limits)
        if dialog.exec():
            self.unc_graphs_temp_limits = dialog.get_T_lim()
            QMessageBox.information(self, "Success", 
                f"Temperature limits updated: {self.unc_graphs_temp_limits[0]} K - {self.unc_graphs_temp_limits[1]} K")
    
    def export_uncertainty(self):
        """Export uncertainty budget"""
        if ExportSettings is None:
            QMessageBox.warning(self, "Warning", "ExportSettings module not available")
            return
        
        self.export_dialog = ExportSettings()
        self.export_dialog.export_button.clicked.connect(self.export_uncertainty_action)
        self.export_dialog.show()
    
    def export_uncertainty_action(self):
        """Execute uncertainty export"""
        start = float(self.export_dialog.start_edit.text())
        stop = float(self.export_dialog.stop_edit.text())
        step = float(self.export_dialog.step_edit.text())
        self.export_dialog.close()
        
        if hasattr(self, 'uncertainty_tab'):
            self.uncertainty_tab.export_uncertainty(np.arange(start, stop, step))
        else:
            QMessageBox.warning(self, "Warning", "Uncertainty tab not available")
    
    def export_calibration(self):
        """Export calibration data"""
        if ExportSettings is None:
            QMessageBox.warning(self, "Warning", "ExportSettings module not available")
            return
        
        self.export_dialog = ExportSettings()
        self.export_dialog.export_button.clicked.connect(self.export_calibration_action)
        self.export_dialog.show()
    
    def export_calibration_action(self):
        """Execute calibration export"""
        start = float(self.export_dialog.start_edit.text())
        stop = float(self.export_dialog.stop_edit.text())
        step = float(self.export_dialog.step_edit.text())
        self.export_dialog.close()
        
        if hasattr(self, 'uncertainty_tab'):
            self.uncertainty_tab.export_calibration(np.arange(start, stop, step))
        else:
            QMessageBox.warning(self, "Warning", "Uncertainty tab not available")
    
    def load_sensor_data(self):
        """Load sensor spectral response data from CSV"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, 
            "Load Sensor Data", 
            "",
            "CSV Files (*.csv);;All Files (*)"
        )
        
        if not file_path:
            return
        
        try:
            df = pd.read_csv(file_path)
            
            # Assume first column is wavelength, second is response
            # Convert to numpy arrays explicitly
            self.sensor_wl = np.array(df.values[:, 0], dtype=float)
            self.sensor_res = np.array(df.values[:, 1], dtype=float)
            
            # Calculate mean wavelength and standard deviation
            from scipy import integrate
            lam = integrate.simpson(self.sensor_wl * self.sensor_res, self.sensor_wl) / \
                  integrate.simpson(self.sensor_res, self.sensor_wl)
            sig = (integrate.simpson((self.sensor_wl - lam) ** 2 * self.sensor_res, self.sensor_wl) / \
                   integrate.simpson(self.sensor_res, self.sensor_wl)) ** 0.5
            
            # Update uncertainty tab if available
            # Update uncertainty tab if available
            if hasattr(self, 'uncertainty_tab'):
                # Update Mean Wavelength if widget exists
                if self.uncertainty_tab.mean_wl:
                    try:
                        self.uncertainty_tab.mean_wl.temp_edit.setText("{:.3f}".format(lam))
                    except RuntimeError:
                        # Widget might be deleted but reference exists
                        pass
                
                # Update Standard Deviation if widget exists
                if self.uncertainty_tab.std:
                    try:
                        self.uncertainty_tab.std.temp_edit.setText("{:.3f}".format(sig))
                    except RuntimeError:
                        pass
                
                self.uncertainty_tab.sigma = sig
            
            QMessageBox.information(self, "Success", 
                f"Loaded sensor data\n"
                f"Mean Wavelength: {lam:.3f} nm\n"
                f"Standard Deviation: {sig:.3f} nm")
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load sensor data:\n{str(e)}")

    def its90_fixed_point_func(self, state):
        """Handle ITS-90 checkbox state changes"""
        checkbox = self.sender()
        if isinstance(checkbox, QCheckBox):
            row_index = checkbox.property("row_index")
            if row_index is not None and row_index in self.fixed_points:
                # Update Dictionary
                self.fixed_points[row_index]["IsITS90"] = (state == 2)
                
                # Check if this row is currently selected (active widget exists)
                # We need to find the active widget in the layout corresponding to this index
                if hasattr(self.uncertainty_tab, 'fixed_points_layout'):
                    layout = self.uncertainty_tab.fixed_points_layout
                    for i in range(layout.count()):
                        item = layout.itemAt(i)
                        if item:
                            w = item.widget()
                            if hasattr(w, 'index') and w.index == row_index:
                                w.isITS90 = (state == 2)
                                break
    
    def select_fixed_point_func(self, state):
        """Handle fixed point checkbox state changes"""
        checkbox = self.sender()
        if isinstance(checkbox, QCheckBox):
            row_index = checkbox.property("row_index")
            
            if row_index is None:
                logger.error("Could not find row index for checkbox")
                return
            
            if state == 2:  # Checked (Qt.CheckState.Checked)
                if UncertaintyWidget is None:
                    QMessageBox.warning(self, "Warning", "UncertaintyWidget not available")
                    checkbox.setChecked(False)
                    return
                
                if row_index not in self.fixed_points:
                    QMessageBox.warning(self, "Warning", f"Fixed point at row {row_index} not found")
                    checkbox.setChecked(False)
                    return
                
                # Update Dictionary State
                self.fixed_points[row_index]["IsFixedPoint"] = True

                fixed_point = UncertaintyWidget()
                fixed_point.isFixedPoint = True
                fixed_point.index = row_index
                
                # Load ITS-90 state
                is_its90 = self.fixed_points[row_index].get("IsITS90", False)
                fixed_point.isITS90 = is_its90
                
                fixed_point.load_fixed_point(self.fixed_points[row_index])
                fixed_point.save_button.show()
                fixed_point.save_button.clicked.connect(self.update_fixed_point)
                
                # Check if uncertainty_tab has 'n' attribute and access safely
                if hasattr(self.uncertainty_tab, 'n'):
                    self.uncertainty_tab.n += 1
                    self.uncertainty_tab.add_fixed_point(fixed_point)
                else:
                    logger.warning("uncertainty_tab does not have 'n' attribute")
            else:  # Unchecked (Qt.CheckState.Unchecked)
                # Update Dictionary State
                if row_index in self.fixed_points:
                    self.fixed_points[row_index]["IsFixedPoint"] = False
                    
                if hasattr(self.uncertainty_tab, 'n'):
                    self.uncertainty_tab.n -= 1
                    self.uncertainty_tab.delete_fixed_point(row_index)
        else:
            logger.error("Invalid sender object")
    
    def update_fixed_point_table(self):
        """Update the fixed points table"""
        if hasattr(self, 'uncertainty_tab'):
            self.uncertainty_tab.fixed_point_table.setRowCount(0)
            for fp_index, fix in self.fixed_points.items():
                self.add_row_fixed_points_table(fix, fp_index)
    
    def update_fixed_point(self):
        """Update fixed point data from widget"""
        button = self.sender()
        un_widget = button.parentWidget().parentWidget()
        fixed_point = un_widget.get_info()
        index = un_widget.index
        self.fixed_points[index] = fixed_point
        
        if hasattr(self, 'uncertainty_tab'):
            self.uncertainty_tab.fixed_point_table.item(index, 1).setText(fixed_point["Name"])
            self.uncertainty_tab.fixed_point_table.item(index, 2).setText(
                str(fixed_point["Temperature"]) + " " + fixed_point["Unit"])
            
            # Update ITS-90 Checkbox State based on new Name
            name_lower = str(fixed_point["Name"]).lower()
            is_its90_point = any(x in name_lower for x in ['ag', 'au', 'cu', 'silver', 'gold', 'copper'])
            
            # Find the widget in the table
            widget = self.uncertainty_tab.fixed_point_table.cellWidget(index, 3)
            if widget:
                # Find checkbox in layout
                checkbox = widget.findChild(QCheckBox)  # Assuming only one checkbox
                if checkbox:
                    checkbox.setVisible(is_its90_point)
                    if not is_its90_point:
                        checkbox.setChecked(False)
                        # checkbox.setToolTip("ITS-90 Reference Function only available for Ag, Au, Cu")
                        # Also update the data model to reflect unchecked
                        if index in self.fixed_points:
                            self.fixed_points[index]["IsITS90"] = False
                            # Update widget state too
                            un_widget.isITS90 = False
                    else:
                        checkbox.setToolTip("Use ITS-90 Reference Function")
            
            # Re-sort if temperature changed
            self.sort_and_refresh_ui()
    
    def load_fixed_points(self):
        """Load fixed points from JSON files"""
        file_paths, _ = QFileDialog.getOpenFileNames(
            self, 
            "Load Fixed Points", 
            "",
            "JSON Files (*.json);;All Files (*)"
        )
        
        for path in file_paths:
            if path:
                try:
                    with open(path, "r") as openfile:
                        fix_point = json.load(openfile)
                        fp_index = len(self.fixed_points.keys())
                        self.fixed_points[fp_index] = fix_point
                        # self.add_row_fixed_points_table(fix_point, fp_index)
                except Exception as e:
                    QMessageBox.critical(self, "Error", f"Failed to load {path}:\n{str(e)}")
                    
        # Sort and refresh once after loading all
        self.sort_and_refresh_ui()
    
    def fixed_points_custom_context_menu_requested(self, pos):
        """Show context menu for fixed points table"""
        if not hasattr(self, 'uncertainty_tab'):
            return
        
        it = self.uncertainty_tab.fixed_point_table.itemAt(pos)
        if it is None:
            return
        
        r = it.row()
        from PySide6.QtWidgets import QTableWidgetSelectionRange
        item_range = QTableWidgetSelectionRange(
            r, 0, r, self.uncertainty_tab.fixed_point_table.columnCount() - 1
        )
        self.uncertainty_tab.fixed_point_table.setRangeSelected(item_range, True)
        
        menu = QMenu()
        delete_row_action = menu.addAction("Delete Fixed Point")
        add_row_action = menu.addAction("Add Fixed Point")
        save_as_action = menu.addAction("Save As")
        action = menu.exec(self.uncertainty_tab.fixed_point_table.viewport().mapToGlobal(pos))
        
        if action == delete_row_action:
            checkbox = self.uncertainty_tab.fixed_point_table.cellWidget(r, 0).findChildren(QCheckBox)
            if checkbox and checkbox[0].isChecked():
                msg = QMessageBox()
                msg.setIcon(QMessageBox.Warning)
                msg.setWindowTitle("Warning")
                msg.setText("Selected fixed points cannot be deleted.\nPlease clear your selection first.")
                msg.setStandardButtons(QMessageBox.Ok)
                msg.exec()
            else:
                self.uncertainty_tab.fixed_point_table.removeRow(r)
                self.del_fixed_point_from_dic(r)
        elif action == add_row_action:
            self.add_new_fixed_point_window()
        elif action == save_as_action:
            self.save_as_file_dialog(self.fixed_points[r])
    
    def del_fixed_point_from_dic(self, r):
        """Delete fixed point from dictionary"""
        new_fixed_point = {}
        # Re-index dictionary to match table rows
        # NOTE: This might be risky if keys are expected to be persistent unique IDs.
        # But based on the original code, it seems to re-key them to 0, 1, 2...
        ind = 0
        for key in self.fixed_points.keys():
            if key != r:
                new_fixed_point[ind] = self.fixed_points[key]
                ind += 1
        self.fixed_points = new_fixed_point
    
    def save_as_file_dialog(self, dic):
        """Save fixed point to JSON file"""
        file_path, _ = QFileDialog.getSaveFileName(
            self, 
            "Save Fixed Point", 
            dic.get("Name", "fixed_point"),
            "JSON Files (*.json);;All Files (*)"
        )
        
        if file_path:
            try:
                json_object = json.dumps(dic, indent=4)
                with open(file_path, "w") as outfile:
                    outfile.write(json_object)
                QMessageBox.information(self, "Success", f"Fixed point saved to {file_path}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to save file:\n{str(e)}")
    
    def add_new_fixed_point_window(self):
        """Open window to add new fixed point"""
        if AddFixedPoint is None:
            QMessageBox.warning(self, "Warning", "AddFixedPoint module not available")
            return
        
        self.add_window = AddFixedPoint()
        self.add_window.add_button.clicked.connect(self.add_new_fixed_point)
        self.add_window.show()
    
    def add_new_fixed_point(self):
        """Add new fixed point from window"""
        try:
            fixed_point = self.add_window.un_widget.get_info()
            fp_index = len(self.fixed_points.keys())
            fixed_point = self.add_window.un_widget.get_info()
            fp_index = len(self.fixed_points.keys())
            self.fixed_points[fp_index] = fixed_point
            
            # Use sort and refresh logic instead of just appending
            self.sort_and_refresh_ui()
            
            self.add_window.close()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to add fixed point:\n{str(e)}")
    
    def add_row_fixed_points_table(self, fixed_point, fp_index=None):
        """Add a row to the fixed points table"""
        if not hasattr(self, 'uncertainty_tab'):
            return
        
        row_count = self.uncertainty_tab.fixed_point_table.rowCount()
        self.uncertainty_tab.fixed_point_table.setRowCount(row_count + 1)
        
        # Use provided index or current row count
        if fp_index is None:
            fp_index = row_count
        
        # Checkbox
        check_box = QCheckBox()
        check_box.setProperty("row_index", fp_index)  # Store dictionary index, not row number
        
        check_box.stateChanged.connect(self.select_fixed_point_func)
        
        # Restore selection state (will trigger signal now)
        if fixed_point.get("IsFixedPoint", False):
            check_box.setChecked(True)
            
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.addWidget(check_box)
        layout.setAlignment(check_box, Qt.AlignmentFlag.AlignCenter)
        layout.setContentsMargins(0, 0, 0, 0)
        self.uncertainty_tab.fixed_point_table.setCellWidget(row_count, 0, widget)
        
        # Name
        self.uncertainty_tab.fixed_point_table.setItem(
            row_count, 1, QTableWidgetItem(fixed_point["Name"])
        )
        
        # Temperature
        self.uncertainty_tab.fixed_point_table.setItem(
            row_count, 2, 
            QTableWidgetItem(str(fixed_point["Temperature"]) + " " + fixed_point["Unit"])
        )
        
        # ITS-90 Checkbox
        its90_check = QCheckBox()
        its90_check.setProperty("row_index", fp_index)
        # Enable only if name is appropriate (Ag, Au, Cu)
        name_lower = str(fixed_point["Name"]).lower()
        is_its90_point = any(x in name_lower for x in ['ag', 'au', 'cu', 'silver', 'gold', 'copper'])
        
        its90_check.setVisible(is_its90_point)
        if not is_its90_point:
             its90_check.setChecked(False)
             # its90_check.setToolTip("ITS-90 Reference Function only available for Ag, Au, Cu") 
        else:
             its90_check.setToolTip("Use ITS-90 Reference Function")
        
        # If it was previously saved as ITS90, check it (only if valid)
        if fixed_point.get("IsITS90", False) and is_its90_point:
            its90_check.setChecked(True)
            
        its90_check.stateChanged.connect(self.its90_fixed_point_func)
        
        its90_widget = QWidget()
        its90_layout = QHBoxLayout(its90_widget)
        its90_layout.addWidget(its90_check)
        its90_layout.setAlignment(its90_check, Qt.AlignmentFlag.AlignCenter)
        its90_layout.setContentsMargins(0, 0, 0, 0)
        self.uncertainty_tab.fixed_point_table.setCellWidget(row_count, 3, its90_widget)
    
    
    def sort_and_refresh_ui(self):
        """Sort fixed points by temperature, re-index, and refresh UI"""
        # 1. Capture current state is done via dictionary IsFixedPoint updates
        
        # 2. Sort items
        items = list(self.fixed_points.values())
        items.sort(key=lambda x: x.get("Temperature", 0.0))
        
        # 3. Rebuild dictionary with new indices
        self.fixed_points = {}
        for i, item in enumerate(items):
            self.fixed_points[i] = item
            
        # 4. Clear existing widgets in the layout (because their indices are now wrong)
        # We need to remove them from layout and close them to avoid duplicates/confusion
        if hasattr(self.uncertainty_tab, 'fixed_points_layout'):
            layout = self.uncertainty_tab.fixed_points_layout
            while layout.count():
                item = layout.takeAt(0)
                widget = item.widget()
                if widget:
                    widget.deleteLater()
        
        # 5. Restore Standard Widgets (Mean WL, Std Dev, In-Use Signal)
        # Clearing the layout deleted them, so we must recreate them.
        if hasattr(self.uncertainty_tab, 'add_std_un_widget'):
            self.uncertainty_tab.add_std_un_widget()
        if hasattr(self.uncertainty_tab, 'add_mean_wl_un_widget'):
            self.uncertainty_tab.add_mean_wl_un_widget()
        if hasattr(self.uncertainty_tab, 'add_in_use_signal_un_widget'):
            self.uncertainty_tab.add_in_use_signal_un_widget()
            
        # 6. Reset n counter
        if hasattr(self.uncertainty_tab, 'n'):
            self.uncertainty_tab.n = 0
            
        # 7. Rebuild Table
        self.update_fixed_point_table()
        
        # 7. Restore active widgets from the sorted dictionary
        # Since we moved the signal connection to before setChecked in add_row_fixed_points_table,
        # calling update_fixed_point_table() will automatically trigger select_fixed_point_func
        # for each checked item, thus rebuilding the widgets.
        pass
        
    def set_theme(self, theme_name):
        """Update theme"""
        self.theme_name = theme_name
        # Theme updates for matplotlib are handled by main window triggers or canvas redrawing
