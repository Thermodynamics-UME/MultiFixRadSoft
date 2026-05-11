#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MultiFixRadSoft - Modern Multi-Page GUI for Relative Primary Radiation Thermometry Analysis Toolkit
Created by TUBITAK-UME Thermodynamic Metrology Laboratory
Features: Data Analysis, Scale Realization, Corrections, and Uncertainty Budget
"""

import sys
import json
import logging
from pathlib import Path

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFileDialog, QLineEdit, QCheckBox, QGroupBox, QFormLayout,
    QTableWidget, QTableWidgetItem, QComboBox, QSpinBox, QDoubleSpinBox,
    QMessageBox, QScrollArea, QStackedWidget, QHeaderView, QTabWidget,
    QProgressBar, QDateEdit, QTextEdit, QListWidget, QListWidgetItem,
    QGraphicsOpacityEffect, QMenu, QDialog, QColorDialog, QInputDialog,
    QGridLayout, QSplitter, QMenuBar, QSizePolicy
)
from PySide6.QtCore import Qt, QSize, QDate, QTimer, QPropertyAnimation, QEasingCurve, QPoint
from PySide6.QtGui import QIcon, QFont, QColor, QPalette, QPixmap, QBrush, QAction, QDoubleValidator
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from matplotlib.ticker import FuncFormatter
from matplotlib.widgets import SpanSelector, RectangleSelector

# --- Import uncertainty calculation modules ---
try:
    sys.path.insert(0, str(Path(__file__).parent / "src"))
    from UncertaintyFunctions import _Sin, func_dic
    from uncertainty import UncertaintyComponent, combine_uns, to_SI
    from UncertaintyWidget import UncertaintyWidget
    from UncertaintyTabWidget import UncertaintyTabWidget
    from addFixedPoint import AddFixedPoint
    from GraphsOptions import GraphsOptions
    from ExportSettings import ExportSettings
    from RunUncertainty import RunUncertainty
except ImportError as e:
    logging.warning("Could not import uncertainty modules: %s", e)
    _Sin = None
    func_dic = None
    UncertaintyComponent = None
    combine_uns = None
    to_SI = None
    UncertaintyWidget = None
    UncertaintyTabWidget = None
    AddFixedPoint = None
    GraphsOptions = None
    ExportSettings = None
    RunUncertainty = None

# --- Refactored modules imports ---
from src.theme_manager import ThemeManager, ModernStylesheet
from src.plot_canvas import PlotCanvas, load_plot_settings, save_plot_settings

class HomePage(QWidget):
    """Home page with animated big buttons"""
    
    page_selected_signal = None  # Will be set by parent
    
    def __init__(self, theme_name="Nord Dark", parent=None):
        super().__init__(parent)
        self.theme_name = theme_name
        self.theme = ThemeManager.get_theme(theme_name)
        self.page_selected = False
        self.animations = []
        self.original_geometries = []
        self.main_window = parent  # Store reference to main window
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Title
        title_layout = QVBoxLayout()
        title_layout.setContentsMargins(40, 40, 40, 20)
        title = QLabel("MultiFixRadSoft")
        title.setFont(QFont("Arial", 48, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        subtitle = QLabel("TUBITAK-UME Thermodynamic Metrology Laboratory")
        subtitle.setFont(QFont("Arial", 18))
        subtitle.setAlignment(Qt.AlignCenter)
        title_layout.addWidget(title)
        title_layout.addWidget(subtitle)
        layout.addLayout(title_layout)
        
        # Center buttons
        self.center_layout = QHBoxLayout()
        self.center_layout.setSpacing(20)
        self.center_layout.setContentsMargins(40, 40, 40, 40)
        
        # Create 4 big buttons
        self.buttons = []
        button_data = [
            ("📊", "Data Analysis", 1),
            ("📏", "Scale Realization", 2),
            ("⚙️", "Corrections", 3),
            ("📈", "Uncertainty Budget", 4),
        ]
        
        for icon, text, idx in button_data:
            btn = self.create_big_button(icon, text, idx)
            self.buttons.append((btn, idx))
            self.center_layout.addWidget(btn)
        
        layout.addLayout(self.center_layout, stretch=1)
        
        # Footer
        self.footer = QLabel("Click any button to begin")
        self.footer.setFont(QFont("Arial", 16))
        self.footer.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.footer)
        
        self.setLayout(layout)
    
    def showEvent(self, event):
        """Store button geometries when widget is shown"""
        super().showEvent(event)
        if not self.original_geometries and self.buttons:
            self.original_geometries = [btn.geometry() for btn, _ in self.buttons]
    
    def create_big_button(self, icon, text, page_idx):
        """Create a big animated button"""
        btn = QPushButton()
        btn.setText(f"{icon}\n{text}")
        btn.setMinimumSize(220, 200)
        btn.setFont(QFont("Arial", 24, QFont.Bold))
        btn.setCursor(Qt.PointingHandCursor)
        btn.page_index = page_idx
        btn.clicked.connect(lambda: self.on_button_clicked(page_idx, btn))
        # Override stylesheet font size with inline style
        btn.setStyleSheet(f"font-size: 24px; font-weight: bold;")
        
        return btn
    
    def on_button_clicked(self, page_idx, btn):
        """Handle button click with animation"""
        if not self.page_selected:
            self.page_selected = True
            self.animate_all_buttons(page_idx, btn)
    
    def animate_all_buttons(self, page_idx, clicked_btn):
        """Animate all buttons sliding down off screen, then switch page"""
        # Slide all buttons down off screen
        for i, (button, idx) in enumerate(self.buttons):
            # Slide down animation
            start_pos = button.pos()
            end_pos = QPoint(start_pos.x(), start_pos.y() + 600)  # Slide down 600px
            
            anim = QPropertyAnimation(button, b"pos")
            anim.setDuration(400)
            anim.setEasingCurve(QEasingCurve.InOutQuad)
            anim.setStartValue(start_pos)
            anim.setEndValue(end_pos)
            
            # Connect the clicked button's animation to switch page when finished
            if button == clicked_btn:
                anim.finished.connect(lambda p=page_idx: self.switch_to_page(p))
            
            anim.start()
            self.animations.append(anim)
    
    def switch_to_page(self, page_idx):
        """Switch to the selected page"""
        # Use stored main window reference
        if self.main_window and hasattr(self.main_window, 'stacked'):
            # Show sidebar before switching page
            if hasattr(self.main_window, 'sidebar'):
                self.main_window.sidebar.show()
            
            self.main_window.stacked.setCurrentIndex(page_idx)
            # Update sidebar button highlight
            if hasattr(self.main_window, 'nav_buttons'):
                for btn, idx in self.main_window.nav_buttons:
                    if idx == page_idx:
                        btn.setStyleSheet(f"QPushButton {{ background-color: {self.main_window.stylesheet_manager.SECONDARY_COLOR}; }}")
                    else:
                        btn.setStyleSheet("")
        
        # Reset for next time
        self.page_selected = False
    
    def reset_buttons_to_center(self):
        """Reset buttons sliding up from bottom to original position"""
        # Stop any ongoing animations
        for anim in self.animations:
            if anim.state() == QPropertyAnimation.Running:
                anim.stop()
        self.animations.clear()
        
        # Simply reset the layout - let Qt handle positioning
        # Remove all buttons from layout
        for button, idx in self.buttons:
            self.center_layout.removeWidget(button)
        
        # Re-add all buttons to layout in order
        for button, idx in self.buttons:
            self.center_layout.addWidget(button)
            button.show()
        
        # Update footer
        self.footer.setText("Click any button to begin")
    
    def set_theme(self, theme_name):
        """Update theme"""
        self.theme_name = theme_name
        self.theme = ThemeManager.get_theme(theme_name)


class ModernMainWindow(QMainWindow):
    """Main application window with modern design"""
    
    def __init__(self, theme_name="Nord Dark"):
        super().__init__()
        self.setWindowTitle("MultiFixRadSoft - Created by TUBITAK-UME Thermodynamic Metrology Laboratory")
        self.resize(1400, 850)
        self.setMinimumSize(1000, 600)  # Set reasonable minimum size
        self.theme_name = theme_name
        self.stylesheet_manager = ModernStylesheet(theme_name)
        self.init_ui()
        self.apply_stylesheet()
    
    def init_ui(self):
        # Lazy imports to speed up startup
        from src.pages.data_analysis_page import DataAnalysisPage
        from src.pages.scale_realization_page import ScaleRealizationPage
        from src.pages.corrections_page import CorrectionsPage
        from src.pages.uncertainty_budget_page import UncertaintyBudgetPage
        
        central = QWidget()
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Add menu bar for settings
        menubar = QMenuBar(self)
        settings_menu = menubar.addMenu("Settings")
        save_action = QAction("Save Settings", self)
        export_action = QAction("Export Plot Settings...", self)
        import_action = QAction("Import Plot Settings...", self)
        settings_menu.addAction(save_action)
        settings_menu.addSeparator()
        settings_menu.addAction(export_action)
        settings_menu.addAction(import_action)
        self.setMenuBar(menubar)
        save_action.triggered.connect(self.save_plot_settings_menu)
        export_action.triggered.connect(self.export_plot_settings)
        import_action.triggered.connect(self.import_plot_settings)
        
        # Sidebar with toggle button
        self.sidebar_container = QWidget()
        sidebar_layout = QVBoxLayout(self.sidebar_container)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)
        sidebar_layout.setSpacing(0)
        
        self.sidebar = self.create_sidebar()
        self.sidebar.hide()  # Hide sidebar on startup
        sidebar_layout.addWidget(self.sidebar)
        
        layout.addWidget(self.sidebar_container)
        
        # Main content area with toggle button
        content_container = QWidget()
        content_layout = QVBoxLayout(content_container)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)
        
        # Toggle button for sidebar
        toggle_container = QWidget()
        toggle_container.setMaximumHeight(45)
        toggle_layout = QHBoxLayout(toggle_container)
        toggle_layout.setContentsMargins(5, 5, 5, 5)
        
        self.sidebar_toggle = QPushButton("▶ Menu")
        self.sidebar_toggle.setMinimumWidth(80)
        self.sidebar_toggle.setMinimumHeight(35)
        self.sidebar_toggle.setToolTip("Show Sidebar")
        self.sidebar_toggle.setStyleSheet("""
            QPushButton {
                font-size: 14px;
                font-weight: bold;
                padding: 5px 10px;
            }
        """)
        self.sidebar_toggle.clicked.connect(self.toggle_sidebar)
        toggle_layout.addWidget(self.sidebar_toggle)
        toggle_layout.addStretch()
        
        content_layout.addWidget(toggle_container)
        
        # Main stacked widget
        self.stacked = QStackedWidget()
        self.page_home = HomePage(theme_name=self.theme_name, parent=self)
        self.page_analysis = DataAnalysisPage(theme_name=self.theme_name)
        self.page_scale = ScaleRealizationPage(theme_name=self.theme_name)
        
        # Pass page_scale to corrections page so we can read the fixed points
        self.page_corrections = CorrectionsPage(theme_name=self.theme_name, scale_page=self.page_scale)
        
        # Cross-link: let scale page push Sakuma results to corrections page
        self.page_scale.set_corrections_page(self.page_corrections)
        
        self.page_uncertainty = UncertaintyBudgetPage(theme_name=self.theme_name)
        
        self.stacked.addWidget(self.page_home)          # 0
        self.stacked.addWidget(self.page_analysis)      # 1
        self.stacked.addWidget(self.page_scale)         # 2
        self.stacked.addWidget(self.page_corrections)   # 3
        self.stacked.addWidget(self.page_uncertainty)   # 4
        
        content_layout.addWidget(self.stacked)
        
        layout.addWidget(content_container, stretch=1)
    
    def create_sidebar(self):
        """Create the modern sidebar"""
        sidebar = QWidget()
        sidebar.setMaximumWidth(280)
        sidebar.setMinimumWidth(280)
        layout = QVBoxLayout()
        layout.setContentsMargins(10, 10, 10, 10)
        
        # Logo/Title
        title = QLabel("📊 MultiFixRadSoft")
        title.setFont(QFont("Arial", 14, QFont.Bold))
        layout.addWidget(title)
        
        # Theme selector
        theme_label = QLabel("Theme:")
        theme_label.setFont(QFont("Arial", 9))
        layout.addWidget(theme_label)
        
        self.combo_theme = QComboBox()
        self.combo_theme.addItems(ThemeManager.get_theme_names())
        self.combo_theme.setCurrentText(self.theme_name)
        self.combo_theme.currentTextChanged.connect(self.change_theme)
        layout.addWidget(self.combo_theme)
        
        separator = QLabel("-" * 30)
        layout.addWidget(separator)
        
        # Home button
        btn_home = QPushButton("🏠 Home")
        btn_home.setFixedHeight(50)
        btn_home.setFont(QFont("Arial", 10))
        btn_home.clicked.connect(self.go_home)
        layout.addWidget(btn_home)
        
        # Navigation buttons
        buttons = [
            ("📊 Data Analysis", 1),
            ("📏 Scale Realization", 2),
            ("⚙️ Corrections", 3),
            ("📈 Uncertainty Budget", 4),
        ]
        
        self.nav_buttons = []
        for text, page_idx in buttons:
            btn = QPushButton(text)
            btn.setFixedHeight(50)
            btn.setFont(QFont("Arial", 10))
            btn.clicked.connect(lambda checked, idx=page_idx: self.switch_page(idx))
            self.nav_buttons.append((btn, page_idx))
            layout.addWidget(btn)
        
        layout.addStretch()
        
        # Footer
        footer = QLabel("v1.0 | TUBITAK-UME")
        footer.setFont(QFont("Arial", 8))
        footer.setAlignment(Qt.AlignCenter)
        layout.addWidget(footer)
        
        sidebar.setLayout(layout)
        return sidebar
    
    def toggle_sidebar(self):
        """Toggle sidebar visibility"""
        if self.sidebar.isVisible():
            self.sidebar.hide()
            self.sidebar_toggle.setText("▶ Menu")
            self.sidebar_toggle.setToolTip("Show Sidebar")
        else:
            self.sidebar.show()
            self.sidebar_toggle.setText("◀ Hide")
            self.sidebar_toggle.setToolTip("Hide Sidebar")
    
    def switch_page(self, idx):
        """Switch between pages"""
        self.stacked.setCurrentIndex(idx)
        
        # Show sidebar when switching away from home (idx != 0)
        if idx != 0:
            self.sidebar.show()
            self.sidebar_toggle.setText("◀ Hide")
        
        # Update button highlights (skip home button, only highlight nav buttons)
        for btn, page_idx in self.nav_buttons:
            if page_idx == idx:
                btn.setStyleSheet(f"QPushButton {{ background-color: {self.stylesheet_manager.SECONDARY_COLOR}; }}")
            else:
                btn.setStyleSheet("")
    
    def change_theme(self, theme_name):
        """Change application theme"""
        if theme_name == "Custom":
            # Lazy import
            from src.theme_manager import ThemeEditorDialog, ThemeManager
            dialog = ThemeEditorDialog(self, self.theme_name)
            if dialog.exec():
                # Theme saved
                new_theme_name = dialog.custom_theme_name
                # Reload combo box to include new theme
                self.combo_theme.blockSignals(True)
                self.combo_theme.clear()
                self.combo_theme.addItems(ThemeManager.get_theme_names())
                self.combo_theme.setCurrentText(new_theme_name)
                self.combo_theme.blockSignals(False)
                theme_name = new_theme_name
            else:
                # Revert to previous
                self.combo_theme.blockSignals(True)
                self.combo_theme.setCurrentText(self.theme_name)
                self.combo_theme.blockSignals(False)
                return

        self.theme_name = theme_name
        self.stylesheet_manager = ModernStylesheet(theme_name)
        self.apply_stylesheet()
        
        # Update all pages with new theme
        self.page_home.set_theme(theme_name)
        self.page_analysis.set_theme(theme_name)
        self.page_scale.set_theme(theme_name)
        self.page_corrections.set_theme(theme_name)
        self.page_uncertainty.set_theme(theme_name)
        
        # Update button highlight
        for btn, page_idx in self.nav_buttons:
            if self.stacked.currentIndex() == page_idx:
                btn.setStyleSheet(f"QPushButton {{ background-color: {self.stylesheet_manager.SECONDARY_COLOR}; }}")
            else:
                btn.setStyleSheet("")
    
    def go_home(self):
        """Go back to home page and reset buttons"""
        self.switch_page(0)
        self.sidebar.hide()  # Hide sidebar on home page
        self.page_home.reset_buttons_to_center()
    
    def apply_stylesheet(self):
        """Apply modern stylesheet"""
        self.setStyleSheet(self.stylesheet_manager.get_stylesheet_instance())
    
    def save_plot_settings_menu(self):
        """Save current plot settings to the default plot_settings.json file"""
        # Try to call save_current_plot_settings on all canvases
        saved = False
        for page in [self.page_analysis, self.page_scale, self.page_corrections, self.page_uncertainty]:
            for attr in dir(page):
                obj = getattr(page, attr, None)
                if obj and hasattr(obj, 'save_current_plot_settings'):
                    try:
                        obj.save_current_plot_settings()
                        saved = True
                    except Exception as e:
                        logging.debug("Error saving settings from %s: %s", attr, e)
        if saved:
            QMessageBox.information(self, "Settings Saved", "Plot settings saved to plot_settings.json.")
        else:
            QMessageBox.warning(self, "No Settings", "No plot settings found to save.")
    
    def export_plot_settings(self):
        """Export current plot settings to a user-chosen JSON file"""
        path, _ = QFileDialog.getSaveFileName(self, "Export Plot Settings", "plot_settings.json", "JSON Files (*.json)")
        if not path:
            return
        try:
            settings = load_plot_settings()
            with open(Path(path), "w", encoding="utf-8") as f:
                json.dump(settings, f, indent=2)
            QMessageBox.information(self, "Export Successful", f"Plot settings exported to {path}")
        except Exception as e:
            QMessageBox.warning(self, "Export Failed", str(e))
    
    def import_plot_settings(self):
        """Import plot settings from a user-chosen JSON file and apply globally"""
        path, _ = QFileDialog.getOpenFileName(self, "Import Plot Settings", "", "JSON Files (*.json)")
        if not path:
            return
        try:
            with open(Path(path), "r", encoding="utf-8") as f:
                settings = json.load(f)
            save_plot_settings(settings)
            # Apply to all canvases if possible
            for page in [self.page_analysis, self.page_scale, self.page_corrections, self.page_uncertainty]:
                for attr in dir(page):
                    obj = getattr(page, attr, None)
                    if obj and hasattr(obj, 'apply_plot_settings'):
                        try:
                            obj._plot_settings = settings
                            obj.apply_plot_settings()
                        except Exception as e:
                            logging.debug("Error applying settings to %s: %s", attr, e)
            QMessageBox.information(self, "Import Successful", "Plot settings imported and applied.")
        except Exception as e:
            QMessageBox.warning(self, "Import Failed", str(e))


def main():
    # Configure logging for the entire application
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        datefmt='%H:%M:%S'
    )
    app = QApplication(sys.argv)
    
    # Splash Screen
    from PySide6.QtWidgets import QSplashScreen
    from PySide6.QtGui import QPixmap, QIcon, QImage
    import os
    
    # Set application icon
    icon_path = os.path.join(os.path.dirname(__file__), "img", "ume_1.png")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))
        
    # Path to splash image
    splash_path = os.path.join(os.path.dirname(__file__), "img", "mfx_calc.png")
    splash = None
    if os.path.exists(splash_path):
        splash_pix = QPixmap(splash_path)
        # Scale if too large (optional, but good practice)
        if splash_pix.width() > 800:
            splash_pix = splash_pix.scaledToWidth(800, Qt.SmoothTransformation)
            
        splash = QSplashScreen(splash_pix, Qt.WindowStaysOnTopHint)
        splash.show()
        app.processEvents() # Ensure splash is drawn
    
    # Set global font size (increase from default)
    font = QFont("Arial", 11)  # Increased base font size from 9 to 11
    app.setFont(font)
    
    # You can change the theme here: "Nord Dark", "Dracula", "Monokai", "One Dark", "Light Mode", "Soft Light", "Mint Light"
    window = ModernMainWindow(theme_name="Mint Light")
    
    if splash:
        splash.finish(window)
        
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
