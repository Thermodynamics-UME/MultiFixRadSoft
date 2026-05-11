import sys

from PySide6.QtGui import QDoubleValidator
from PySide6.QtWidgets import QWidget, QApplication, QGridLayout, QLabel, QLineEdit, QPushButton, QDialog, \
    QDialogButtonBox


class GraphsOptions(QDialog):
    def __init__(self, T_lim, parent=None):
        super().__init__(parent)

        self.setWindowTitle("Graph Options")
        self.main_layout = QGridLayout()

        self.graph_upper_label = QLabel("Temperature Upper Limit:")
        self.graph_upper_edit = QLineEdit(str(T_lim[1]))
        self.graph_upper_edit.setValidator(QDoubleValidator())

        self.graph_lower_label = QLabel("Temperature Lower Limit:")
        self.graph_lower_edit = QLineEdit(str(T_lim[0]))
        self.graph_lower_edit.setValidator(QDoubleValidator())

        # Butonlar
        QBtn = (QDialogButtonBox.Apply | QDialogButtonBox.Cancel)
        self.buttonBox = QDialogButtonBox(QBtn)
        self.buttonBox.button(QDialogButtonBox.Apply).clicked.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)

        # Layout'a ekleme
        self.main_layout.addWidget(self.graph_upper_label, 0,0)
        self.main_layout.addWidget(self.graph_upper_edit, 0, 1)
        self.main_layout.addWidget(self.graph_lower_label, 1, 0)
        self.main_layout.addWidget(self.graph_lower_edit, 1, 1)
        self.main_layout.addWidget(self.buttonBox, 2, 0, 1, 2)

        self.setLayout(self.main_layout)

    def get_T_lim(self):
        return [float(self.graph_lower_edit.text()), float(self.graph_upper_edit.text())]


if __name__ == '__main__':
    app = QApplication(sys.argv)
    widget = GraphsOptions([1000, 3000])
    widget.show()
    sys.exit(app.exec())
