import sys

from PySide6.QtGui import QDoubleValidator
from PySide6.QtWidgets import QWidget, QApplication, QGridLayout, QLabel, QLineEdit, QPushButton


class ExportSettings(QWidget):
    def __init__(self):
        super().__init__()

        self.main_layout = QGridLayout()
        self.start_label = QLabel("Start Temperature (K):")
        self.start_edit = QLineEdit()
        self.start_edit.setValidator(QDoubleValidator())
        self.stop_label = QLabel("Stop Temperature (K):")
        self.stop_edit = QLineEdit()
        self.stop_edit.setValidator(QDoubleValidator())
        self.step_label = QLabel("Step (K):")
        self.step_edit = QLineEdit()
        self.step_edit.setValidator(QDoubleValidator())

        self.export_button = QPushButton("Export")
        self.close_button = QPushButton("Close")

        self.main_layout.addWidget(self.start_label, 0, 0)
        self.main_layout.addWidget(self.start_edit, 0, 1)
        self.main_layout.addWidget(self.stop_label, 1, 0)
        self.main_layout.addWidget(self.stop_edit, 1, 1)
        self.main_layout.addWidget(self.step_label, 2, 0)
        self.main_layout.addWidget(self.step_edit, 2, 1)
        self.main_layout.addWidget(self.export_button)
        self.main_layout.addWidget(self.close_button)
        self.setLayout(self.main_layout)

        self.close_button.clicked.connect(self.close)



if __name__ == '__main__':
    app = QApplication(sys.argv)
    widget = ExportSettings()
    widget.show()
    sys.exit(app.exec())
