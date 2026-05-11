
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
from PySide6.QtCore import Qt, QPoint, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QFont
from src.theme_manager import ThemeManager

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
        title.setFont(QFont("Arial", 48, QFont.Bold))  # Increased from 36
        title.setAlignment(Qt.AlignCenter)
        subtitle = QLabel("TUBITAK-UME Thermodynamic Metrology")
        subtitle.setFont(QFont("Arial", 18))  # Increased from 14
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
        self.footer.setFont(QFont("Arial", 16))  # Increased from 12
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
        btn.setMinimumSize(220, 200)  # Increased from 200x180
        btn.setFont(QFont("Arial", 24, QFont.Bold))  # Increased to 24pt for visibility
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
