import sys

from PySide6.QtGui import QDoubleValidator
from PySide6.QtWidgets import QApplication, QWidget, QLabel, QVBoxLayout, QLineEdit, QComboBox, QHBoxLayout, \
    QSpacerItem, QSizePolicy, QGridLayout, QTableWidget, QTableWidgetSelectionRange, QMenu, QTableWidgetItem, \
    QAbstractScrollArea, QPushButton, QMessageBox, QGroupBox
from PySide6.QtCore import Qt


class UncertaintyWidget(QWidget):
    def __init__(self):
        super().__init__()

        self.index = None
        self.isFixedPoint = False
        self.isITS90 = False # Flag for ITS-90 usage
        self.isWidgetActive = True

        self.group_box = QGroupBox()
        self.group_box_layout = QVBoxLayout()
        self.group_box.setLayout(self.group_box_layout)

        self.main_layout = QVBoxLayout()
        self.main_layout.addWidget(self.group_box)
        self.setLayout(self.main_layout)

        self.save_button = QPushButton("Apply")
        self.save_button.hide()
        
        # Set larger font for better readability
        font_style = """
            QLabel { font-size: 14pt; font-weight: bold; }
            QLineEdit { font-size: 13pt; padding: 7px; }
            QComboBox { font-size: 13pt; padding: 7px; }
            QPushButton { font-size: 13pt; padding: 7px; }
            QTableWidget { font-size: 12pt; }
            QTableWidget::item { padding: 9px; }
            QHeaderView::section { font-size: 13pt; font-weight: bold; padding: 9px; }
            QGroupBox { font-size: 13pt; font-weight: bold; }
        """
        self.setStyleSheet(font_style)

        # Name and Temperature inputs
        self.name_label = QLabel("Name:")
        self.name_edit = QLineEdit()
        self.name_edit.setMinimumWidth(250)

        self.temp_label = QLabel("Temperature:")
        self.temp_edit = QLineEdit()
        self.temp_edit.setValidator(QDoubleValidator())
        self.temp_edit.setMinimumWidth(120)

        self.signal_label = QLabel("Signal:")
        self.signal_edit = QLineEdit()
        self.signal_edit.setValidator(QDoubleValidator())
        self.signal_edit.setMinimumWidth(120)

        # Unit combo box for temperature input
        self.temp_combo = self.UnitComboBox(" K")

        # Horizontal layout for temperature input and unit
        self.temp_widget = QWidget()
        self.temp_layout = QHBoxLayout()
        self.temp_layout.addWidget(self.temp_label)
        self.temp_layout.addWidget(self.temp_edit)
        self.temp_layout.addWidget(self.temp_combo)
        self.temp_layout.addWidget(self.signal_label)
        self.temp_layout.addWidget(self.signal_edit)
        self.temp_layout.addItem(QSpacerItem(0, 0, QSizePolicy.Policy.Expanding))
        self.temp_widget.setLayout(self.temp_layout)

        # Layout for Name and Temperature inputs and adding widgets
        self.name_layout = QHBoxLayout()
        self.name_layout.addWidget(self.name_label)
        self.name_layout.addWidget(self.name_edit)
        self.name_layout.addWidget(self.save_button)
        self.name_layout.addItem(QSpacerItem(0, 0, QSizePolicy.Policy.Expanding))

        self.group_box_layout.addLayout(self.name_layout)
        self.group_box_layout.addWidget(self.temp_widget)

        # Table for temperature uncertainty components input
        self.temp_un_label = QLabel("Temperature Uncertainties:")
        self.temp_un_table = QTableWidget()
        self.temp_un_table.setContextMenuPolicy(Qt.CustomContextMenu)

        # Table for signal uncertainty components input
        self.signal_un_label = QLabel("Signal Uncertainties:")
        self.signal_un_table = QTableWidget()
        self.signal_un_table.setContextMenuPolicy(Qt.CustomContextMenu)

        # Layout to hold temperature and signal uncertainty components
        self.un_layout = QGridLayout()
        self.un_layout.addWidget(self.temp_un_label, 0, 0)
        self.un_layout.addWidget(self.temp_un_table, 1, 0)
        self.un_layout.addWidget(self.signal_un_label, 0, 1)
        self.un_layout.addWidget(self.signal_un_table, 1, 1)
        self.un_layout.addItem(QSpacerItem(0, 0, QSizePolicy.Policy.Expanding), 1, 2)
        self.group_box_layout.addLayout(self.un_layout)

        self.temp_un_table.customContextMenuRequested.connect(self.custom_context_menu_requested)
        self.signal_un_table.customContextMenuRequested.connect(self.custom_context_menu_requested)

        size_policy = self.sizePolicy()
        size_policy.setHorizontalPolicy(QSizePolicy.Fixed)
        size_policy.setVerticalPolicy(QSizePolicy.Fixed)
        self.setSizePolicy(size_policy)

    def get_info(self):
        if self.name_edit.text() == "":
            title = "Warning"
            message = "Fill Name!!!"
            QMessageBox.warning(self, title, message, QMessageBox.StandardButton.Ok)
            return

        if self.temp_edit.text() == "":
            title = "Warning"
            message = "Fill Temperature!!!"
            QMessageBox.warning(self, title, message, QMessageBox.StandardButton.Ok)
            return

        fixed_point = {"Name": self.name_edit.text(), "Temperature": float(self.temp_edit.text()),
                       "Unit": self.temp_combo.currentText(), "Signal": float(self.signal_edit.text()),
                       "IsFixedPoint": self.isFixedPoint, "IsITS90": self.isITS90,
                       "Temperature_Un": {"Names": [], "Values": [], "Unit": []},
                       "Signal_Un": {"Names": [], "Values": [], "Unit": []}}
        add_row_count = self.temp_un_table.rowCount()
        for r in range(add_row_count):
            fixed_point["Temperature_Un"]["Names"].append(self.temp_un_table.item(r, 0).text())
            fixed_point["Temperature_Un"]["Values"].append(float(self.temp_un_table.cellWidget(r, 1).text()))
            fixed_point["Temperature_Un"]["Unit"].append(self.temp_un_table.cellWidget(r, 2).currentText())

        add_row_count = self.signal_un_table.rowCount()
        for r in range(add_row_count):
            fixed_point["Signal_Un"]["Names"].append(self.signal_un_table.item(r, 0).text())
            fixed_point["Signal_Un"]["Values"].append(float(self.signal_un_table.cellWidget(r, 1).text()))
            fixed_point["Signal_Un"]["Unit"].append(self.signal_un_table.cellWidget(r, 2).currentText())

        return fixed_point

    def add_row(self, data, table, insert=-1):
        if insert == -1:
            row_count = table.rowCount()
            table.setRowCount(row_count + 1)
        else:
            row_count = insert
            table.insertRow(insert)
        table.setItem(row_count, 0, QTableWidgetItem(data[0]))
        line_edit = QLineEdit()
        line_edit.setText(str(data[1]))
        line_edit.setValidator(QDoubleValidator())
        line_edit.setMinimumWidth(110)  # Increased by 10%
        line_edit.setMaximumWidth(165)  # Increased by 10%
        line_edit.setStyleSheet("font-size: 13pt; padding: 7px;")  # Explicit styling
        table.setCellWidget(row_count, 1, line_edit)
        table.setCellWidget(row_count, 2, self.UnitComboBox(data[2]))
        table.setRowHeight(row_count, 50)  # Increased to 50px
        self.resize_tables()

    def resize_tables(self):
        row1 = self.signal_un_table.rowCount()
        row2 = self.temp_un_table.rowCount()
        h = 50  # Increased by 10% from 45 to 50 for better readability
        if row2 > row1:
            height = h * row2 + 39  # Increased header space
        else:
            height = h * row1 + 39  # Increased header space

        self.signal_un_table.setMinimumHeight(height)
        self.signal_un_table.setMaximumHeight(height)
        self.temp_un_table.setMaximumHeight(height)
        
        # Set row heights explicitly
        for i in range(row1):
            self.signal_un_table.setRowHeight(i, h)
        for i in range(row2):
            self.temp_un_table.setRowHeight(i, h)

    def setup_table(self, model, table):
        table.setColumnCount(3)
        table.setHorizontalHeaderLabels(["Component", "    Value    ", "Unit"])
        for i, data in enumerate(zip(model["Names"], model["Values"], model["Unit"])):
            self.add_row(data, table)

        table.resizeColumnsToContents()
        table.setSizeAdjustPolicy(QAbstractScrollArea.SizeAdjustPolicy.AdjustToContents)
        
        # Set minimum column widths for better readability
        table.setColumnWidth(2, 100)  # Make unit column wider

    def custom_context_menu_requested(self, pos):
        table = self.sender()
        it = table.itemAt(pos)
        if it is None:
            return
        r = it.row()
        item_range = QTableWidgetSelectionRange(r, 0, r, table.columnCount() - 1)
        table.setRangeSelected(item_range, True)

        menu = QMenu()
        delete_row_action = menu.addAction("Delete Component")
        add_row_action = menu.addAction("Add Component")
        action = menu.exec(table.viewport().mapToGlobal(pos))
        if action == delete_row_action:
            table.removeRow(r)
            self.resize_tables()
        if action == add_row_action:
            self.add_row(["", 0.0, table.cellWidget(r, 2).currentText()], table, r)

    class UnitComboBox(QComboBox):
        def __init__(self, unit, parent=None):
            super().__init__(parent)
            self.big_temp_units = ["K ", "C"]
            self.temp_units = ["mK", "K", "% "]
            self.signal_units = ["%"]
            self.wl_units = ["um", "nm"]

            self.set_items(unit)

        def set_items(self, unit):
            self.clear()
            if unit in self.temp_units:
                self.addItems(self.temp_units)
            elif unit in self.signal_units:
                self.addItems(self.signal_units)
            elif unit in self.wl_units:
                self.addItems(self.wl_units)
            elif unit in self.big_temp_units:
                self.addItems(self.big_temp_units)

            self.setCurrentText(unit)


    def load_fixed_point(self, fixed_point):
        self.name_edit.setText(fixed_point["Name"])
        self.temp_edit.setText(str(fixed_point["Temperature"]))
        self.temp_combo.set_items(fixed_point["Unit"])
        self.signal_edit.setText(str(fixed_point["Signal"]))
        self.setup_table(fixed_point["Signal_Un"], self.signal_un_table)
        self.setup_table(fixed_point["Temperature_Un"], self.temp_un_table)

    def hide_secounds(self):
        self.name_label.hide()
        self.name_edit.hide()
        self.signal_un_label.hide()
        self.signal_un_table.hide()
        self.signal_edit.hide()
        self.signal_label.hide()
        self.save_button.show()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    widget = UncertaintyWidget()
    widget.show()
    sys.exit(app.exec())
