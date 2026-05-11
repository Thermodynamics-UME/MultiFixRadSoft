

import json
import logging
import os
from pathlib import Path
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, 
    QGridLayout, QLineEdit, QColorDialog, QMessageBox, QFrame
)
from PySide6.QtGui import QColor
from PySide6.QtCore import Qt

logger = logging.getLogger(__name__)


class ThemeManager:
    """Manage customizable themes"""
    
    THEMES = {
        "Nord Dark": {
            "MAIN_COLOR": "#2E3440",
            "ACCENT_COLOR": "#5E81AC",
            "SECONDARY_COLOR": "#88C0D0",
            "SUCCESS_COLOR": "#A3BE8C",
            "WARNING_COLOR": "#EBCB8B",
            "ERROR_COLOR": "#BF616A",
            "TEXT_PRIMARY": "#ECEFF4",
            "TEXT_SECONDARY": "#D8DEE9",
        },
        "Dracula": {
            "MAIN_COLOR": "#282A36",
            "ACCENT_COLOR": "#6272A4",
            "SECONDARY_COLOR": "#50FA7B",
            "SUCCESS_COLOR": "#50FA7B",
            "WARNING_COLOR": "#FFB86C",
            "ERROR_COLOR": "#FF5555",
            "TEXT_PRIMARY": "#F8F8F2",
            "TEXT_SECONDARY": "#E8E8D3",
        },
        "Monokai": {
            "MAIN_COLOR": "#272822",
            "ACCENT_COLOR": "#66D9EF",
            "SECONDARY_COLOR": "#A1EFE4",
            "SUCCESS_COLOR": "#A6E22E",
            "WARNING_COLOR": "#E6DB74",
            "ERROR_COLOR": "#F92672",
            "TEXT_PRIMARY": "#F8F8F2",
            "TEXT_SECONDARY": "#E6DB74",
        },
        "One Dark": {
            "MAIN_COLOR": "#282C34",
            "ACCENT_COLOR": "#61AFEF",
            "SECONDARY_COLOR": "#56B6C2",
            "SUCCESS_COLOR": "#98C379",
            "WARNING_COLOR": "#E5C07B",
            "ERROR_COLOR": "#E06C75",
            "TEXT_PRIMARY": "#ABB2BF",
            "TEXT_SECONDARY": "#D8DEE9",
        },
        "Light Mode": {
            "MAIN_COLOR": "#FFFFFF",
            "ACCENT_COLOR": "#007BFF",
            "SECONDARY_COLOR": "#0056B3",
            "SUCCESS_COLOR": "#28A745",
            "WARNING_COLOR": "#FFC107",
            "ERROR_COLOR": "#DC3545",
            "TEXT_PRIMARY": "#212529",
            "TEXT_SECONDARY": "#6C757D",
        },
        "Soft Light": {
            "MAIN_COLOR": "#F8F9FA",
            "ACCENT_COLOR": "#4A90E2",
            "SECONDARY_COLOR": "#357ABD",
            "SUCCESS_COLOR": "#5CB85C",
            "WARNING_COLOR": "#F0AD4E",
            "ERROR_COLOR": "#D9534F",
            "TEXT_PRIMARY": "#2C3E50",
            "TEXT_SECONDARY": "#34495E",
        },
        "Mint Light": {
            "MAIN_COLOR": "#F5FFFE",
            "ACCENT_COLOR": "#1ABC9C",
            "SECONDARY_COLOR": "#16A085",
            "SUCCESS_COLOR": "#27AE60",
            "WARNING_COLOR": "#F39C12",
            "ERROR_COLOR": "#E74C3C",
            "TEXT_PRIMARY": "#2C3E50",
            "TEXT_SECONDARY": "#7F8C8D",
        },
    }
    
    CUSTOM_THEMES_FILE = str(Path(__file__).parent.parent / "models" / "custom_themes.json")
    CUSTOM_THEMES = {}

    @staticmethod
    def load_custom_themes():
        """Load custom themes from file"""
        if os.path.exists(ThemeManager.CUSTOM_THEMES_FILE):
            try:
                with open(ThemeManager.CUSTOM_THEMES_FILE, 'r') as f:
                    ThemeManager.CUSTOM_THEMES = json.load(f)
            except Exception as e:
                logger.warning("Error loading custom themes: %s", e)

    @staticmethod
    def save_custom_themes():
        """Save custom themes to file"""
        try:
            with open(ThemeManager.CUSTOM_THEMES_FILE, 'w') as f:
                json.dump(ThemeManager.CUSTOM_THEMES, f, indent=4)
        except Exception as e:
            logger.warning("Error saving custom themes: %s", e)

    @staticmethod
    def get_theme(theme_name="Nord Dark"):
        """Get theme colors"""
        # Load custom themes if not loaded (basic check)
        if not ThemeManager.CUSTOM_THEMES and os.path.exists(ThemeManager.CUSTOM_THEMES_FILE):
             ThemeManager.load_custom_themes()
             
        if theme_name in ThemeManager.CUSTOM_THEMES:
            return ThemeManager.CUSTOM_THEMES[theme_name]
            
        return ThemeManager.THEMES.get(theme_name, ThemeManager.THEMES["Nord Dark"])
    
    @staticmethod
    def get_theme_names():
        """Get available theme names"""
        # Ensure custom themes are loaded
        if not ThemeManager.CUSTOM_THEMES and os.path.exists(ThemeManager.CUSTOM_THEMES_FILE):
             ThemeManager.load_custom_themes()
             
        # Add "Custom" option if not present (placeholder for creating new)
        base_themes = list(ThemeManager.THEMES.keys())
        custom_themes = list(ThemeManager.CUSTOM_THEMES.keys())
        all_themes = base_themes + custom_themes
        if "Custom" not in all_themes:
            all_themes.append("Custom")
        return all_themes


class ModernStylesheet:
    """Modern dark theme with gradient effects"""
    
    def __init__(self, theme_name="Nord Dark"):
        self.theme = ThemeManager.get_theme(theme_name)
        self.MAIN_COLOR = self.theme["MAIN_COLOR"]
        self.ACCENT_COLOR = self.theme["ACCENT_COLOR"]
        self.SECONDARY_COLOR = self.theme["SECONDARY_COLOR"]
        self.SUCCESS_COLOR = self.theme["SUCCESS_COLOR"]
        self.WARNING_COLOR = self.theme["WARNING_COLOR"]
        self.ERROR_COLOR = self.theme["ERROR_COLOR"]
        self.TEXT_PRIMARY = self.theme["TEXT_PRIMARY"]
        self.TEXT_SECONDARY = self.theme["TEXT_SECONDARY"]
    
    @staticmethod
    def get_stylesheet():
        """
        Static method from original code.
        Note: The original code referenced class attributes that were not defined.
        Returning empty string to prevent errors as get_stylesheet_instance is preferred.
        """
        return ""
    
    def get_stylesheet_instance(self):
        """Get stylesheet with instance colors"""
        # Determine if it's a light theme
        is_light = self.MAIN_COLOR in ["#FFFFFF", "#F8F9FA", "#F5FFFE"]
        
        # For dark themes, ensure high contrast with white bold text
        # For light themes, use dark text
        widget_text = "#FFFFFF" if not is_light else self.TEXT_PRIMARY
        button_text = "#FFFFFF" if not is_light else "#212529"
        input_text = "#FFFFFF" if not is_light else "#212529"
        table_text = "#FFFFFF" if not is_light else "#212529"
        tab_text = "#FFFFFF" if not is_light else "#212529"
        tab_unselected_text = "#FFFFFF" if not is_light else "#6C757D"
        font_weight = "bold" if not is_light else "normal"
        
        # Adjust colors for light themes
        input_bg = "#F5F5F5" if is_light else "#3B4252"
        input_border_focus = self.ACCENT_COLOR if is_light else self.SECONDARY_COLOR
        table_bg = "#FFFFFF" if is_light else "#3B4252"
        table_alt_bg = "#F8F8F8" if is_light else "#434C5E"
        table_grid = "#E0E0E0" if is_light else "#4C566A"
        scrollbar_bg = "#E5E5E5" if is_light else "#3B4252"
        
        return f"""
        QMainWindow {{
            background-color: {self.MAIN_COLOR};
            color: {widget_text};
            font-weight: {font_weight};
        }}
        
        QWidget {{
            background-color: {self.MAIN_COLOR};
            color: {widget_text};
            font-weight: {font_weight};
        }}
        
        QPushButton {{
            background-color: {self.ACCENT_COLOR};
            color: {button_text};
            border: none;
            border-radius: 6px;
            padding: 8px 16px;
            font-weight: bold;
            font-size: 16px;
        }}
        
        QPushButton:hover {{
            background-color: {self.SECONDARY_COLOR};
        }}
        
        QPushButton:pressed {{
            background-color: {self.ACCENT_COLOR};
            opacity: 0.8;
        }}
        
        QLineEdit, QTextEdit {{
            background-color: {input_bg};
            color: {input_text};
            border: 2px solid {self.ACCENT_COLOR};
            border-radius: 4px;
            padding: 5px;
            font-size: 10px;
            font-weight: {font_weight};
        }}
        
        QLineEdit:focus, QTextEdit:focus {{
            border: 2px solid {input_border_focus};
        }}
        
        QGroupBox {{
            color: {widget_text};
            border: 2px solid {self.ACCENT_COLOR};
            border-radius: 6px;
            margin-top: 10px;
            padding-top: 10px;
            font-weight: bold;
        }}
        
        QGroupBox::title {{
            subcontrol-origin: margin;
            subcontrol-position: top left;
            padding: 0 3px;
            color: {widget_text};
        }}
        
        QLabel {{
            color: {widget_text};
            font-weight: {font_weight};
        }}
        
        QCheckBox, QRadioButton {{
            color: {widget_text};
            spacing: 5px;
            font-weight: {font_weight};
        }}
        
        QCheckBox::indicator, QRadioButton::indicator {{
            width: 18px;
            height: 18px;
        }}
        
        QCheckBox::indicator:checked {{
            background-color: {self.SUCCESS_COLOR};
        }}
        
        QComboBox {{
            background-color: {input_bg};
            color: {input_text};
            border: 2px solid {self.ACCENT_COLOR};
            border-radius: 4px;
            padding: 5px;
            font-size: 10px;
            font-weight: {font_weight};
        }}
        
        QComboBox::drop-down {{
            border: none;
            background-color: {self.ACCENT_COLOR};
            width: 30px;
        }}
        
        QComboBox QAbstractItemView {{
            background-color: {input_bg};
            color: {input_text};
            selection-background-color: {self.ACCENT_COLOR};
            selection-color: {button_text};
            font-weight: {font_weight};
        }}
        
        QSpinBox, QDoubleSpinBox {{
            background-color: {input_bg};
            color: {input_text};
            border: 2px solid {self.ACCENT_COLOR};
            border-radius: 4px;
            padding: 5px;
            font-weight: {font_weight};
        }}
        
        QTableWidget {{
            background-color: {table_bg};
            alternate-background-color: {table_alt_bg};
            color: {table_text};
            border: 1px solid {self.ACCENT_COLOR};
            gridline-color: {table_grid};
            font-weight: {font_weight};
        }}
        
        QTableWidget::item {{
            padding: 5px;
            border-bottom: 1px solid {table_grid};
            color: {table_text};
        }}
        
        QTableWidget::item:selected {{
            background-color: {self.ACCENT_COLOR};
            color: {button_text};
        }}
        
        QHeaderView::section {{
            background-color: {self.ACCENT_COLOR};
            color: {button_text};
            padding: 5px;
            border: none;
            font-weight: bold;
        }}
        
        QScrollBar:vertical {{
            background-color: {scrollbar_bg};
            width: 12px;
            border: none;
        }}
        
        QScrollBar::handle:vertical {{
            background-color: {self.ACCENT_COLOR};
            border-radius: 6px;
            min-height: 20px;
        }}
        
        QScrollBar::handle:vertical:hover {{
            background-color: {self.SECONDARY_COLOR};
        }}
        
        QTabWidget::pane {{
            border: 1px solid {self.ACCENT_COLOR};
        }}
        
        QTabBar::tab {{
            background-color: {input_bg};
            color: {tab_unselected_text};
            padding: 8px 20px;
            border-bottom: 2px solid {input_bg};
            font-weight: {font_weight};
        }}
        
        QTabBar::tab:selected {{
            background-color: {self.ACCENT_COLOR};
            color: {tab_text};
            border-bottom: 2px solid {self.SECONDARY_COLOR};
            font-weight: bold;
        }}
        
        QProgressBar {{
            border: 2px solid {self.ACCENT_COLOR};
            border-radius: 5px;
            text-align: center;
            height: 20px;
            background-color: {input_bg};
            color: {widget_text};
            font-weight: {font_weight};
        }}
        
        QProgressBar::chunk {{
            background-color: {self.SUCCESS_COLOR};
            border-radius: 3px;
        }}
        """


class ThemeEditorDialog(QDialog):
    """Dialog for editing or creating custom themes"""
    
    def __init__(self, parent=None, base_theme="Nord Dark"):
        super().__init__(parent)
        self.setWindowTitle("Custom Theme Editor")
        self.resize(500, 600)
        
        # Load base colors (handle "Custom" placeholder by defaulting to Nord Dark)
        if base_theme == "Custom":
            base_theme = "Nord Dark"
            
        self.colors = ThemeManager.get_theme(base_theme).copy()
        
        layout = QVBoxLayout(self)
        
        # Theme Name
        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("Theme Name:"))
        self.name_edit = QLineEdit("My Custom Theme")
        name_layout.addWidget(self.name_edit)
        layout.addLayout(name_layout)
        
        # Color editors
        self.color_widgets = {}
        grid = QGridLayout()
        
        # Using a QFrame/ScrollArea if needed, but for 8 colors it fits
        row = 0
        for key, value in self.colors.items():
            lbl = QLabel(key.replace("_", " ").title() + ":")
            
            # Color preview/button
            btn = QPushButton()
            btn.setStyleSheet(f"background-color: {value}; border: 1px solid #555;")
            btn.setFixedSize(60, 30)
            btn.clicked.connect(lambda checked, k=key, b=btn: self.pick_color(k, b))
            
            # Text edit for hex code
            hex_edit = QLineEdit(value)
            hex_edit.textChanged.connect(lambda text, k=key, b=btn: self.update_color_from_hex(k, b, text))
            
            grid.addWidget(lbl, row, 0)
            grid.addWidget(btn, row, 1)
            grid.addWidget(hex_edit, row, 2)
            
            self.color_widgets[key] = (btn, hex_edit)
            row += 1
            
        layout.addLayout(grid)
        
        layout.addStretch()
        
        # Buttons
        btn_layout = QHBoxLayout()
        save_btn = QPushButton("Save Theme")
        save_btn.clicked.connect(self.save_theme)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        
        btn_layout.addWidget(save_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)
        
    def pick_color(self, key, btn):
        current = self.colors.get(key, "#000000")
        color = QColorDialog.getColor(QColor(current), self, f"Select {key}")
        
        if color.isValid():
            hex_color = color.name().upper()
            self.colors[key] = hex_color
            btn.setStyleSheet(f"background-color: {hex_color}; border: 1px solid #555;")
            # Update hex text too
            self.color_widgets[key][1].setText(hex_color)
            
    def update_color_from_hex(self, key, btn, text):
        if len(text) == 7 and text.startswith("#"):
            self.colors[key] = text
            btn.setStyleSheet(f"background-color: {text}; border: 1px solid #555;")
            
    def save_theme(self):
        name = self.name_edit.text().strip()
        if not name or name == "Custom":
            QMessageBox.warning(self, "Invalid Name", "Please enter a valid theme name. 'Custom' is a reserved placeholder.")
            return
            
        # Save to custom themes
        ThemeManager.CUSTOM_THEMES[name] = self.colors
        ThemeManager.save_custom_themes()
        
        self.custom_theme_name = name
        self.accept()
