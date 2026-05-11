import json
from PySide6.QtWidgets import (QApplication, QMainWindow, QHBoxLayout, QWidget, QVBoxLayout, QPushButton, QSizePolicy,
                               QSpacerItem)
from UncertaintyWidget import UncertaintyWidget


from pathlib import Path

class AddFixedPoint(QMainWindow):
    def __init__(self):
        super().__init__()

        # Load model for uncertainty components
        model_path = Path(__file__).parent.parent / "models" / "uncertainty_model.json"
        with open(model_path, 'r') as openfile:
            self.un_model = json.load(openfile)

        # Main widget and layout
        self.main_widget = QWidget()
        self.setCentralWidget(self.main_widget)
        self.main_layout = QVBoxLayout()
        self.main_widget.setLayout(self.main_layout)

        self.un_widget = UncertaintyWidget()
        self.un_widget.isFixedPoint = True
        self.un_widget.load_fixed_point(self.un_model)
        self.main_layout.addWidget(self.un_widget)

        # Add and close buttons and their layout
        self.add_button = QPushButton("Add")
        self.close_button = QPushButton("Close")
        self.button_layout = QHBoxLayout()
        self.button_layout.addItem(QSpacerItem(0, 0, QSizePolicy.Policy.Expanding))
        self.button_layout.addWidget(self.add_button)
        self.button_layout.addWidget(self.close_button)
        self.main_layout.addLayout(self.button_layout)

        # Signal-Slot
        self.close_button.clicked.connect(self.close)

if __name__ == '__main__':
    app = QApplication([])
    window = AddFixedPoint()
    window.show()
    app.exec()
