
import logging
import json
from pathlib import Path
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFileDialog, QLineEdit, QCheckBox, QGroupBox, QFormLayout,
    QTableWidget, QTableWidgetItem, QComboBox, QSpinBox, QDoubleSpinBox,
    QMessageBox, QScrollArea, QStackedWidget, QHeaderView, QTabWidget,
    QProgressBar, QDateEdit, QTextEdit, QListWidget, QListWidgetItem,
    QGraphicsOpacityEffect, QMenu, QDialog, QColorDialog, QInputDialog,
    QGridLayout, QSplitter
)
from PySide6.QtCore import Qt, QSize, QDate, QTimer, QPropertyAnimation, QEasingCurve, QPoint
from PySide6.QtGui import QIcon, QFont, QColor, QPalette, QPixmap, QBrush, QAction
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from matplotlib.widgets import SpanSelector, RectangleSelector

from theme_manager import ThemeManager

logger = logging.getLogger(__name__)

# --- Global plot settings logic ---
PLOT_SETTINGS_PATH = Path(__file__).parent.parent / "models/modelsplot_settings.json"

def load_plot_settings(file_path=None):
    """Load plot settings from JSON file"""
    try:
        path = file_path if file_path else PLOT_SETTINGS_PATH
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def save_plot_settings(settings, file_path=None):
    """Save plot settings to JSON file"""
    try:
        path = file_path if file_path else PLOT_SETTINGS_PATH
        with open(path, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2)
    except Exception as e:
        logger.warning("Failed to save plot settings: %s", e)


class PlotCanvas(FigureCanvas):
    """Canvas for matplotlib plots with modern styling and context menu"""
    
    def __init__(self, title="Plot", parent=None, theme_name="Nord Dark"):
        self.theme_name = theme_name
        self.theme = ThemeManager.get_theme(theme_name)
        self.is_light = self.theme["MAIN_COLOR"] in ["#FFFFFF", "#F8F9FA", "#F5FFFE"]
        
        # Set figure colors based on theme
        if self.is_light:
            fig_color = "#FFFFFF"
            axes_color = "#FFFFFF"
            text_color = "#212529"
            grid_color = "#D0D0D0"
        else:
            fig_color = self.theme["MAIN_COLOR"]
            axes_color = self.theme["MAIN_COLOR"]
            text_color = "#FFFFFF"  # White text for dark themes
            grid_color = self.theme["ACCENT_COLOR"]
        
        fig = Figure(figsize=(7, 4), dpi=100, facecolor=fig_color)
        super().__init__(fig)
        self.setParent(parent)
        self.ax = fig.add_subplot(111)
        self.ax.set_facecolor(axes_color)
        self.title = title
        self.fig = fig
        self.text_color = text_color
        self.grid_color = grid_color
        self.accent_color = self.theme["SECONDARY_COLOR"]
        
        # Rectangle selector for zoom
        self.rect_selector = None
        self.zoom_active = False
        self.initial_xlim = None
        self.initial_ylim = None
        self.initial_y2lim = None
        self.initial_y3lim = None
        
        # Enable right-click context menu
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)
        
        # Connect double-click event for editing text
        self.mpl_connect('button_press_event', self._on_click)
        
    def _on_click(self, event):
        """Handle mouse click events for editing text on double-click"""
        if event.dblclick:
            # Check if clicked on title
            for ax in self.fig.axes:
                title = ax.title
                if title.contains(event)[0]:
                    self._edit_text_interactive(ax, 'title')
                    return
                
                # Check if clicked on x-label
                xlabel = ax.xaxis.label
                if xlabel.contains(event)[0]:
                    self._edit_text_interactive(ax, 'xlabel')
                    return
                
                # Check if clicked on y-label
                ylabel = ax.yaxis.label
                if ylabel.contains(event)[0]:
                    self._edit_text_interactive(ax, 'ylabel')
                    return
                
                # Check if clicked on legend
                legend = ax.get_legend()
                if legend and legend.contains(event)[0]:
                    self._edit_legend_text(ax)
                    return
        
    def _show_context_menu(self, position):
        """Show context menu on right-click"""
        menu = QMenu()
        
        # Zoom options
        zoom_menu = menu.addMenu("🔍 Zoom")
        zoom_in = zoom_menu.addAction("Zoom In (Select Area)")
        zoom_out = zoom_menu.addAction("Zoom Out")
        zoom_reset = zoom_menu.addAction("Reset Zoom")
        
        # Check if there are multiple y-axes for additional zoom options
        if len(self.fig.axes) > 1:
            zoom_menu.addSeparator()
            zoom_y2 = zoom_menu.addAction("Zoom Y2-Axis (Select Area)")
        if len(self.fig.axes) > 2:
            zoom_y3 = zoom_menu.addAction("Zoom Y3-Axis (Select Area)")
        
        menu.addSeparator()
        
        # Export options
        export_menu = menu.addMenu("💾 Export")
        export_png = export_menu.addAction("Export as PNG (300 DPI)...")
        export_png_hd = export_menu.addAction("Export as PNG (600 DPI)...")
        export_svg = export_menu.addAction("Export as SVG...")
        export_pdf = export_menu.addAction("Export as PDF...")
        export_csv = export_menu.addAction("Export Data as CSV...")
        
        menu.addSeparator()
        
        # Axis limits
        axis_menu = menu.addMenu("📏 Axis Limits")
        set_xlim = axis_menu.addAction("Set X-Axis Limits...")
        set_ylim = axis_menu.addAction("Set Y-Axis Limits...")
        
        # Check if there are additional axes
        if len(self.fig.axes) > 1:
            set_y2lim = axis_menu.addAction("Set Y2-Axis Limits...")
        if len(self.fig.axes) > 2:
            set_y3lim = axis_menu.addAction("Set Y3-Axis Limits...")
        
        menu.addSeparator()
        
        # Styling options
        style_menu = menu.addMenu("🎨 Plot Styling")
        set_linewidth = style_menu.addAction("Set Line Thickness...")
        set_linestyle = style_menu.addAction("Set Line Type...")
        set_marker = style_menu.addAction("Set Marker Type...")
        set_marker_color = style_menu.addAction("Set Marker Color...")
        
        menu.addSeparator()
        
        # Font options
        font_menu = menu.addMenu("🔤 Font Settings")
        set_title_font = font_menu.addAction("Set Title Font Size...")
        set_label_font = font_menu.addAction("Set Axis Label Font Size...")
        set_tick_font = font_menu.addAction("Set Tick Label Font Size...")
        set_legend_font = font_menu.addAction("Set Legend Font Size...")
        font_menu.addSeparator()
        set_font_type = font_menu.addAction("Set Font Type...")
        set_title_style = font_menu.addAction("Set Title Style (Bold/Italic/Normal)...")
        set_label_style = font_menu.addAction("Set Label Style (Bold/Italic/Normal)...")
        set_tick_style = font_menu.addAction("Set Tick Style (Bold/Italic/Normal)...")
        font_menu.addSeparator()
        set_xlabel = font_menu.addAction("Set X-Label Text...")
        set_ylabel = font_menu.addAction("Set Y-Label Text...")
        
        menu.addSeparator()
        
        # Legend options
        legend_menu = menu.addMenu("📋 Legend")
        set_legend_position = legend_menu.addAction("Set Legend Position...")
        toggle_legend = legend_menu.addAction("Toggle Legend Visibility")
        toggle_legend_draggable = legend_menu.addAction("Toggle Legend Draggable")
        
        menu.addSeparator()
        
        # Grid options
        grid_menu = menu.addMenu("📐 Grid")
        toggle_grid = grid_menu.addAction("Toggle Grid")
        set_grid_style = grid_menu.addAction("Set Grid Style...")
        set_grid_color = grid_menu.addAction("Set Grid Color...")
        set_grid_alpha = grid_menu.addAction("Set Grid Transparency...")
        
        menu.addSeparator()
        
        # Color options
        color_menu = menu.addMenu("🎨 Colors")
        set_bg_color = color_menu.addAction("Set Background Color...")
        set_line_color = color_menu.addAction("Set Line Color...")
        set_label_color = color_menu.addAction("Set Axis Label Color...")
        set_tick_color = color_menu.addAction("Set Tick Label Color...")
        set_title_color = color_menu.addAction("Set Title Color...")
        
        menu.addSeparator()
        
        # Plot Settings options
        settings_menu = menu.addMenu("💾 Plot Settings")
        save_settings = settings_menu.addAction("Save Current Settings")
        export_settings = settings_menu.addAction("Export Settings...")
        import_settings = settings_menu.addAction("Import Settings...")
        
        # Execute menu
        action = menu.exec(self.mapToGlobal(position))
        
        # Handle actions
        if action == zoom_in:
            self._activate_rect_zoom()
        elif action == zoom_out:
            self._zoom_out_step()
        elif action == zoom_reset:
            self._reset_zoom()
        elif len(self.fig.axes) > 1 and action == zoom_y2:
            self._activate_rect_zoom(axis_index=1)
        elif len(self.fig.axes) > 2 and action == zoom_y3:
            self._activate_rect_zoom(axis_index=2)
        elif action == export_png:
            self._export_plot("png", dpi=300)
        elif action == export_png_hd:
            self._export_plot("png", dpi=600)
        elif action == export_svg:
            self._export_plot("svg")
        elif action == export_pdf:
            self._export_plot("pdf")
        elif action == export_csv:
            self._export_csv()
        elif action == set_xlim:
            self._set_axis_limits('x', 0)
        elif action == set_ylim:
            self._set_axis_limits('y', 0)
        elif len(self.fig.axes) > 1 and action == set_y2lim:
            self._set_axis_limits('y', 1)
        elif len(self.fig.axes) > 2 and action == set_y3lim:
            self._set_axis_limits('y', 2)
        elif action == set_linewidth:
            self._set_line_property('linewidth')
        elif action == set_linestyle:
            self._set_line_property('linestyle')
        elif action == set_marker:
            self._set_line_property('marker')
        elif action == set_marker_color:
            self._set_line_property('color')
        elif action == set_title_font:
            self._set_font_size('title')
        elif action == set_label_font:
            self._set_font_size('label')
        elif action == set_tick_font:
            self._set_font_size('tick')
        elif action == set_legend_font:
            self._set_font_size('legend')
        elif action == set_font_type:
            self._set_font_type()
        elif action == set_title_style:
            self._set_text_style('title')
        elif action == set_label_style:
            self._set_text_style('label')
        elif action == set_tick_style:
            self._set_text_style('tick')
        elif action == set_xlabel:
            self._set_label_text('x')
        elif action == set_ylabel:
            self._set_label_text('y')
        elif action == set_legend_position:
            self._set_legend_position()
        elif action == toggle_legend:
            self._toggle_legend()
        elif action == toggle_legend_draggable:
            self._toggle_legend_draggable()
        elif action == toggle_grid:
            self._toggle_grid()
        elif action == set_grid_style:
            self._set_grid_style()
        elif action == set_grid_color:
            self._set_grid_color()
        elif action == set_grid_alpha:
            self._set_grid_alpha()
        elif action == set_bg_color:
            self._set_background_color()
        elif action == set_line_color:
            self._set_element_color('line')
        elif action == set_label_color:
            self._set_element_color('label')
        elif action == set_tick_color:
            self._set_element_color('tick')
        elif action == set_title_color:
            self._set_element_color('title')
        elif action == save_settings:
            self.save_current_plot_settings()
        elif action == export_settings:
            self._export_plot_settings()
        elif action == import_settings:
            self._import_plot_settings()
    
    def _export_plot_settings(self):
        """Export current plot settings to a file"""
        from PySide6.QtWidgets import QFileDialog
        file_path, _ = QFileDialog.getSaveFileName(
            self, 
            "Export Plot Settings", 
            "", 
            "JSON Files (*.json)"
        )
        if file_path:
            self.save_current_plot_settings(file_path=file_path, include_series_style=False, include_grid=False, include_colors=False)
            
    def _import_plot_settings(self):
        """Import plot settings from a file"""
        from PySide6.QtWidgets import QFileDialog, QMessageBox
        file_path, _ = QFileDialog.getOpenFileName(
            self, 
            "Import Plot Settings", 
            "", 
            "JSON Files (*.json)"
        )
        if file_path:
            settings = load_plot_settings(file_path)
            if settings:
                self.apply_plot_settings(settings)
                QMessageBox.information(self, "Import Successful", "Settings imported and applied successfully")
    
    def save_current_plot_settings(self, file_path=None, include_series_style=True, include_grid=True, include_colors=True):
        """
        Extract current plot settings and save them.
        :param file_path: Path to save JSON. If None, saves to default.
        :param include_series_style: If True, saves line colors, markers, widths.
        :param include_grid: If True, saves grid settings.
        :param include_colors: If True, saves background and text colors.
        """
        from PySide6.QtWidgets import QMessageBox
        try:
            settings = {}
            
            if self.fig.axes:
                ax = self.fig.axes[0]
                
                # Legend settings
                legend = ax.get_legend()
                if legend:
                    settings['legend_position'] = legend._loc
                    legend_texts = legend.get_texts()
                    if legend_texts:
                        settings['legend_fontsize'] = legend_texts[0].get_fontsize()
                    settings['legend_draggable'] = legend._draggable is not None
                    settings['legend_frameon'] = legend.get_frame_on()
                    settings['legend_shadow'] = legend.shadow
                    settings['legend_fancybox'] = legend.get_frame().get_boxstyle().__class__.__name__ == 'Round'
                else:
                    settings['legend_position'] = 'best'
                    settings['legend_fontsize'] = 10
                    settings['legend_draggable'] = False
                    settings['legend_frameon'] = True
                    settings['legend_shadow'] = False
                    settings['legend_fancybox'] = True
                
                # Font settings
                settings['title_fontsize'] = ax.title.get_fontsize()
                settings['title_fontweight'] = ax.title.get_fontweight()
                settings['xlabel_fontsize'] = ax.xaxis.label.get_fontsize()
                settings['xlabel_fontweight'] = ax.xaxis.label.get_fontweight()
                settings['ylabel_fontsize'] = ax.yaxis.label.get_fontsize()
                settings['ylabel_fontweight'] = ax.yaxis.label.get_fontweight()
                
                tick_labels = ax.xaxis.get_ticklabels()
                if tick_labels:
                    settings['tick_labelsize'] = tick_labels[0].get_fontsize()
                else:
                    settings['tick_labelsize'] = 9
                
                # Grid settings
                if include_grid:
                    try:
                        grid_visible = False
                        if hasattr(ax, 'xaxis') and hasattr(ax.xaxis, 'get_gridlines'):
                            gridlines = ax.xaxis.get_gridlines()
                            if gridlines:
                                grid_visible = gridlines[0].get_visible()
                                if grid_visible and gridlines:
                                    settings['grid_alpha'] = gridlines[0].get_alpha() or 0.3
                                    settings['grid_linestyle'] = gridlines[0].get_linestyle() or '--'
                                    settings['grid_linewidth'] = gridlines[0].get_linewidth() or 0.8
                                    settings['grid_color'] = gridlines[0].get_color() or '#888888'
                    except Exception:
                        grid_visible = False
                    
                    settings['grid_visible'] = grid_visible
                    if 'grid_alpha' not in settings:
                        settings['grid_alpha'] = 0.3
                    if 'grid_linestyle' not in settings:
                        settings['grid_linestyle'] = '--'
                    if 'grid_linewidth' not in settings:
                        settings['grid_linewidth'] = 0.8
                    if 'grid_color' not in settings:
                        settings['grid_color'] = '#888888'
                
                # Color settings
                if include_colors:
                    settings['background_color'] = ax.get_facecolor()
                    settings['figure_facecolor'] = self.fig.get_facecolor()
                    
                    # Title and label colors
                    settings['title_color'] = ax.title.get_color()
                    settings['xlabel_color'] = ax.xaxis.label.get_color()
                    settings['ylabel_color'] = ax.yaxis.label.get_color()
                    
                    # Tick colors
                    if tick_labels:
                        settings['tick_color'] = tick_labels[0].get_color()
                    else:
                        settings['tick_color'] = '#000000'

                    # Spine color
                    settings['spine_color'] = ax.spines['bottom'].get_edgecolor()
                
                # Spine settings (Structure)
                settings['spines_visible'] = {
                    'top': ax.spines['top'].get_visible(),
                    'right': ax.spines['right'].get_visible(),
                    'bottom': ax.spines['bottom'].get_visible(),
                    'left': ax.spines['left'].get_visible()
                }
                
                settings['spine_linewidth'] = ax.spines['bottom'].get_linewidth()
                
                # Get colors from current elements (Only if requested)
                if include_series_style:
                    lines = ax.get_lines()
                    if lines:
                        settings['line_color'] = lines[0].get_color()
                        settings['linewidth'] = lines[0].get_linewidth()
                        settings['linestyle'] = lines[0].get_linestyle()
                        marker = lines[0].get_marker()
                        settings['marker'] = marker if marker != 'None' else 'o'
                        settings['markersize'] = lines[0].get_markersize()
                    else:
                        settings['line_color'] = '#1f77b4'
                        settings['linewidth'] = 1.5
                        settings['linestyle'] = '-'
                        settings['marker'] = 'o'
                        settings['markersize'] = 6
                
                # Theme name
                settings['theme_name'] = self.theme_name
            
            # Save settings
            save_plot_settings(settings, file_path)
            
            if file_path:
                QMessageBox.information(self, "Export Successful", f"Settings exported to {file_path}")
            else:
                QMessageBox.information(self, "Settings Saved", "Plot settings saved successfully!")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to save settings: {str(e)}")
    
    def apply_plot_settings(self, settings):
        """Apply loaded settings to the current plot"""
        if not settings or not self.fig.axes:
            return
        
        # Apply figure-level settings
        if 'figure_facecolor' in settings:
            self.fig.set_facecolor(settings['figure_facecolor'])
        
        for ax in self.fig.axes:
            # Apply background color
            if 'background_color' in settings:
                ax.set_facecolor(settings['background_color'])
            
            # Apply font settings
            if 'title_fontsize' in settings:
                ax.title.set_fontsize(settings['title_fontsize'])
            if 'title_fontweight' in settings:
                ax.title.set_fontweight(settings['title_fontweight'])
            if 'title_color' in settings:
                ax.title.set_color(settings['title_color'])
                
            if 'xlabel_fontsize' in settings:
                ax.xaxis.label.set_fontsize(settings['xlabel_fontsize'])
            if 'xlabel_fontweight' in settings:
                ax.xaxis.label.set_fontweight(settings['xlabel_fontweight'])
            if 'xlabel_color' in settings:
                ax.xaxis.label.set_color(settings['xlabel_color'])
                
            if 'ylabel_fontsize' in settings:
                ax.yaxis.label.set_fontsize(settings['ylabel_fontsize'])
            if 'ylabel_fontweight' in settings:
                ax.yaxis.label.set_fontweight(settings['ylabel_fontweight'])
            if 'ylabel_color' in settings:
                ax.yaxis.label.set_color(settings['ylabel_color'])
                
            if 'tick_labelsize' in settings:
                ax.tick_params(labelsize=settings['tick_labelsize'])
            if 'tick_color' in settings:
                ax.tick_params(colors=settings['tick_color'])
            
            # Apply legend settings
            legend = ax.get_legend()
            if legend:
                if 'legend_fontsize' in settings:
                    for text in legend.get_texts():
                        text.set_fontsize(settings['legend_fontsize'])
                if 'legend_position' in settings:
                    legend.set_loc(settings['legend_position'])
                if 'legend_draggable' in settings:
                    legend.set_draggable(settings['legend_draggable'])
                if 'legend_frameon' in settings:
                    legend.set_frame_on(settings['legend_frameon'])
                if 'legend_shadow' in settings:
                    legend.shadow = settings['legend_shadow']
                if 'legend_fancybox' in settings:
                    legend.get_frame().set_boxstyle('round' if settings['legend_fancybox'] else 'square')
            
            # Apply grid settings
            if 'grid_visible' in settings:
                if settings['grid_visible']:
                    ax.grid(True, 
                           alpha=settings.get('grid_alpha', 0.3),
                           linestyle=settings.get('grid_linestyle', '--'),
                           linewidth=settings.get('grid_linewidth', 0.8),
                           color=settings.get('grid_color', '#888888'))
                else:
                    ax.grid(False)
            
            # Apply spine settings
            if 'spines_visible' in settings:
                for spine_name, visible in settings['spines_visible'].items():
                    if spine_name in ax.spines:
                        ax.spines[spine_name].set_visible(visible)
            
            if 'spine_linewidth' in settings:
                for spine in ax.spines.values():
                    spine.set_linewidth(settings['spine_linewidth'])
            
            if 'spine_color' in settings:
                for spine in ax.spines.values():
                    spine.set_edgecolor(settings['spine_color'])
            
            # Apply line settings to existing lines
            if 'line_color' in settings or 'linewidth' in settings or 'linestyle' in settings:
                lines = ax.get_lines()
                for line in lines:
                    if 'line_color' in settings:
                        line.set_color(settings['line_color'])
                    if 'linewidth' in settings:
                        line.set_linewidth(settings['linewidth'])
                    if 'linestyle' in settings:
                        line.set_linestyle(settings['linestyle'])
                    if 'marker' in settings:
                        line.set_marker(settings['marker'])
                    if 'markersize' in settings:
                        line.set_markersize(settings['markersize'])
        
        self.draw()
    
    def _zoom(self, factor):
        """Zoom in/out on all axes"""
        for ax in self.fig.axes:
            xlim = ax.get_xlim()
            ylim = ax.get_ylim()
            xrange = (xlim[1] - xlim[0]) * factor
            yrange = (ylim[1] - ylim[0]) * factor
            xcenter = (xlim[0] + xlim[1]) / 2
            ycenter = (ylim[0] + ylim[1]) / 2
            ax.set_xlim([xcenter - xrange/2, xcenter + xrange/2])
            ax.set_ylim([ycenter - yrange/2, ycenter + yrange/2])
        self.draw()
    
    def _activate_rect_zoom(self, axis_index=0):
        """Activate rectangular zoom selector"""
        if self.rect_selector is not None:
            self.rect_selector.set_active(False)
        
        # Store the axis index for the zoom operation
        self.zoom_axis_index = axis_index
        
        # Get the target axis
        if axis_index >= len(self.fig.axes):
            return
        
        target_ax = self.fig.axes[axis_index]
        
        # Save initial limits if not already saved
        if self.initial_xlim is None:
            self.initial_xlim = self.ax.get_xlim()
        if self.initial_ylim is None:
            self.initial_ylim = self.ax.get_ylim()
        if len(self.fig.axes) > 1 and self.initial_y2lim is None:
            self.initial_y2lim = self.fig.axes[1].get_ylim()
        if len(self.fig.axes) > 2 and self.initial_y3lim is None:
            self.initial_y3lim = self.fig.axes[2].get_ylim()
        
        # Create rectangle selector on the target axis
        self.rect_selector = RectangleSelector(
            target_ax,
            self._on_rect_select,
            useblit=True,
            button=[1],  # Left mouse button
            minspanx=5,
            minspany=5,
            spancoords='pixels',
            interactive=False,
            props=dict(facecolor='red', edgecolor='red', alpha=0.2, fill=True)
        )
        self.zoom_active = True
        
        # Show message
        axis_name = "Main" if axis_index == 0 else f"Y{axis_index+1}"
        self.ax.set_title(f"{self.title}\n(Click and drag to select {axis_name} zoom area, right-click to cancel)", 
                         fontsize=10, color=self.text_color)
        self.draw()
    
    def _on_rect_select(self, eclick, erelease):
        """Handle rectangle selection for zoom"""
        if not self.zoom_active:
            return
        
        # Get the selected rectangle coordinates
        x1, y1 = eclick.xdata, eclick.ydata
        x2, y2 = erelease.xdata, erelease.ydata
        
        if x1 is None or x2 is None or y1 is None or y2 is None:
            return
        
        # Ensure x1 < x2 and y1 < y2
        xmin, xmax = min(x1, x2), max(x1, x2)
        ymin, ymax = min(y1, y2), max(y1, y2)
        
        # Apply zoom based on which axis was selected
        if hasattr(self, 'zoom_axis_index'):
            axis_index = self.zoom_axis_index
        else:
            axis_index = 0
        
        if axis_index == 0:
            # Main axis - apply to all axes for x, but only main for y
            for ax in self.fig.axes:
                ax.set_xlim(xmin, xmax)
            self.ax.set_ylim(ymin, ymax)
        else:
            # Secondary axis - apply x to all, y only to selected axis
            if axis_index < len(self.fig.axes):
                for ax in self.fig.axes:
                    ax.set_xlim(xmin, xmax)
                self.fig.axes[axis_index].set_ylim(ymin, ymax)
        
        # Deactivate selector
        if self.rect_selector is not None:
            self.rect_selector.set_active(False)
        self.zoom_active = False
        
        # Reset title
        self.ax.set_title(self.title, fontsize=12, color=self.text_color, weight='bold')
        self.draw()
    
    def _zoom_out_step(self):
        """Zoom out by a fixed factor"""
        self._zoom(1.25)
    
    def _reset_zoom(self):
        """Reset zoom to initial scale"""
        # Restore initial limits if they were saved
        if self.initial_xlim is not None:
            self.ax.set_xlim(self.initial_xlim)
        if self.initial_ylim is not None:
            self.ax.set_ylim(self.initial_ylim)
        
        # Restore secondary axes if they exist
        if len(self.fig.axes) > 1 and self.initial_y2lim is not None:
            self.fig.axes[1].set_ylim(self.initial_y2lim)
        if len(self.fig.axes) > 2 and self.initial_y3lim is not None:
            self.fig.axes[2].set_ylim(self.initial_y3lim)
        
        # If no initial limits were saved, autoscale
        if self.initial_xlim is None or self.initial_ylim is None:
            for ax in self.fig.axes:
                ax.autoscale()
        
        # Deactivate selector if active
        if self.rect_selector is not None:
            self.rect_selector.set_active(False)
        self.zoom_active = False
        
        # Reset title
        self.ax.set_title(self.title, fontsize=12, color=self.text_color, weight='bold')
        self.draw()
    
    def _export_plot(self, format_type, dpi=300):
        """Export plot to file"""
        from PySide6.QtWidgets import QFileDialog
        file_filter = f"{format_type.upper()} Files (*.{format_type})"
        filename, _ = QFileDialog.getSaveFileName(
            self, f"Export Plot as {format_type.upper()}", 
            f"plot.{format_type}", file_filter
        )
        if filename:
            self.fig.savefig(filename, dpi=dpi, bbox_inches='tight')
    
    def _export_csv(self):
        """Export plot data to CSV"""
        from PySide6.QtWidgets import QFileDialog
        import csv
        
        filename, _ = QFileDialog.getSaveFileName(
            self, "Export Data as CSV", "plot_data.csv", "CSV Files (*.csv)"
        )
        if filename:
            with open(filename, 'w', newline='') as csvfile:
                writer = csv.writer(csvfile)
                # Write header
                headers = ['X']
                for i, ax in enumerate(self.fig.axes):
                    for j, line in enumerate(ax.get_lines()):
                        headers.append(f'Y_axis{i}_line{j}')
                writer.writerow(headers)
                
                # Write data
                ax = self.fig.axes[0]
                if ax.get_lines():
                    line = ax.get_lines()[0]
                    xdata = line.get_xdata()
                    for i, x in enumerate(xdata):
                        row = [x]
                        for ax in self.fig.axes:
                            for line in ax.get_lines():
                                ydata = line.get_ydata()
                                if i < len(ydata):
                                    row.append(ydata[i])
                        writer.writerow(row)
    
    def _set_axis_limits(self, axis_type, ax_index):
        """Set axis limits via dialog"""
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton
        
        if ax_index >= len(self.fig.axes):
            return
        
        ax = self.fig.axes[ax_index]
        
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Set {axis_type.upper()}-Axis Limits")
        layout = QVBoxLayout()
        
        # Get current limits
        if axis_type == 'x':
            current_lim = ax.get_xlim()
        else:
            current_lim = ax.get_ylim()
        
        # Min value
        min_layout = QHBoxLayout()
        min_layout.addWidget(QLabel("Min:"))
        min_input = QLineEdit(str(current_lim[0]))
        min_layout.addWidget(min_input)
        layout.addLayout(min_layout)
        
        # Max value
        max_layout = QHBoxLayout()
        max_layout.addWidget(QLabel("Max:"))
        max_input = QLineEdit(str(current_lim[1]))
        max_layout.addWidget(max_input)
        layout.addLayout(max_layout)
        
        # Buttons
        btn_layout = QHBoxLayout()
        btn_ok = QPushButton("OK")
        btn_cancel = QPushButton("Cancel")
        btn_layout.addWidget(btn_ok)
        btn_layout.addWidget(btn_cancel)
        layout.addLayout(btn_layout)
        
        dialog.setLayout(layout)
        
        def apply_limits():
            try:
                min_val = float(min_input.text())
                max_val = float(max_input.text())
                if axis_type == 'x':
                    ax.set_xlim([min_val, max_val])
                else:
                    ax.set_ylim([min_val, max_val])
                self.draw()
                dialog.accept()
            except ValueError:
                pass
        
        btn_ok.clicked.connect(apply_limits)
        btn_cancel.clicked.connect(dialog.reject)
        
        dialog.exec()
    
    def _set_line_property(self, property_name):
        """Set line properties via dialog"""
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QComboBox
        
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Set {property_name.title()}")
        layout = QVBoxLayout()
        
        if property_name == 'linewidth':
            label = QLabel("Line Width:")
            input_widget = QLineEdit("2.0")
            layout.addWidget(label)
            layout.addWidget(input_widget)
        elif property_name == 'linestyle':
            label = QLabel("Line Style:")
            input_widget = QComboBox()
            input_widget.addItems(['-', '--', '-.', ':', 'None'])
            layout.addWidget(label)
            layout.addWidget(input_widget)
        elif property_name == 'marker':
            label = QLabel("Marker Type:")
            input_widget = QComboBox()
            input_widget.addItems(['o', 's', '^', 'v', 'D', '*', '+', 'x', 'None'])
            layout.addWidget(label)
            layout.addWidget(input_widget)
        elif property_name == 'color':
            label = QLabel("Click OK to choose color")
            layout.addWidget(label)
            input_widget = None
        
        # Buttons
        btn_layout = QHBoxLayout()
        btn_ok = QPushButton("OK")
        btn_cancel = QPushButton("Cancel")
        btn_layout.addWidget(btn_ok)
        btn_layout.addWidget(btn_cancel)
        layout.addLayout(btn_layout)
        
        dialog.setLayout(layout)
        
        def apply_property():
            for ax in self.fig.axes:
                for line in ax.get_lines():
                    if property_name == 'linewidth':
                        try:
                            line.set_linewidth(float(input_widget.text()))
                        except ValueError:
                            pass
                    elif property_name == 'linestyle':
                        style = input_widget.currentText()
                        if style == 'None':
                            style = ''
                        line.set_linestyle(style)
                    elif property_name == 'marker':
                        marker = input_widget.currentText()
                        if marker == 'None':
                            marker = ''
                        line.set_marker(marker)
                    elif property_name == 'color':
                        color = QColorDialog.getColor()
                        if color.isValid():
                            line.set_color(color.name())
            self.draw()
            dialog.accept()
        
        btn_ok.clicked.connect(apply_property)
        btn_cancel.clicked.connect(dialog.reject)
        
        dialog.exec()
    
    def _set_font_size(self, element_type):
        """Set font size for various elements"""
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton
        
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Set {element_type.title()} Font Size")
        layout = QVBoxLayout()
        
        label = QLabel("Font Size:")
        input_widget = QLineEdit("12")
        layout.addWidget(label)
        layout.addWidget(input_widget)
        
        # Buttons
        btn_layout = QHBoxLayout()
        btn_ok = QPushButton("OK")
        btn_cancel = QPushButton("Cancel")
        btn_layout.addWidget(btn_ok)
        btn_layout.addWidget(btn_cancel)
        layout.addLayout(btn_layout)
        
        dialog.setLayout(layout)
        
        def apply_font():
            try:
                size = int(input_widget.text())
                for ax in self.fig.axes:
                    if element_type == 'title':
                        ax.title.set_fontsize(size)
                    elif element_type == 'label':
                        ax.xaxis.label.set_fontsize(size)
                        ax.yaxis.label.set_fontsize(size)
                    elif element_type == 'tick':
                        ax.tick_params(axis='both', labelsize=size)
                    elif element_type == 'legend':
                        legend = ax.get_legend()
                        if legend:
                            for text in legend.get_texts():
                                text.set_fontsize(size)
                self.draw()
                dialog.accept()
            except ValueError:
                pass
        
        btn_ok.clicked.connect(apply_font)
        btn_cancel.clicked.connect(dialog.reject)
        
        dialog.exec()
    
    def _set_label_text(self, axis_type):
        """Set axis label text"""
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton
        
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Set {axis_type.upper()}-Label Text")
        layout = QVBoxLayout()
        
        label = QLabel(f"{axis_type.upper()}-Label:")
        input_widget = QLineEdit()
        if axis_type == 'x' and self.fig.axes:
            input_widget.setText(self.fig.axes[0].get_xlabel())
        elif axis_type == 'y' and self.fig.axes:
            input_widget.setText(self.fig.axes[0].get_ylabel())
        
        layout.addWidget(label)
        layout.addWidget(input_widget)
        
        # Buttons
        btn_layout = QHBoxLayout()
        btn_ok = QPushButton("OK")
        btn_cancel = QPushButton("Cancel")
        btn_layout.addWidget(btn_ok)
        btn_layout.addWidget(btn_cancel)
        layout.addLayout(btn_layout)
        
        dialog.setLayout(layout)
        
        def apply_label():
            text = input_widget.text()
            if axis_type == 'x':
                self.fig.axes[0].set_xlabel(text)
            else:
                self.fig.axes[0].set_ylabel(text)
            self.draw()
            dialog.accept()
        
        btn_ok.clicked.connect(apply_label)
        btn_cancel.clicked.connect(dialog.reject)
        
        dialog.exec()
    
    def _edit_text_interactive(self, ax, text_type):
        """Edit text interactively after double-click"""
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton
        
        dialog = QDialog(self)
        if text_type == 'title':
            dialog.setWindowTitle("Edit Title")
            current_text = ax.get_title()
            label_text = "Title:"
        elif text_type == 'xlabel':
            dialog.setWindowTitle("Edit X-Label")
            current_text = ax.get_xlabel()
            label_text = "X-Label:"
        elif text_type == 'ylabel':
            dialog.setWindowTitle("Edit Y-Label")
            current_text = ax.get_ylabel()
            label_text = "Y-Label:"
        
        layout = QVBoxLayout()
        
        label = QLabel(label_text)
        input_widget = QLineEdit(current_text)
        layout.addWidget(label)
        layout.addWidget(input_widget)
        
        # Buttons
        btn_layout = QHBoxLayout()
        btn_ok = QPushButton("OK")
        btn_cancel = QPushButton("Cancel")
        btn_layout.addWidget(btn_ok)
        btn_layout.addWidget(btn_cancel)
        layout.addLayout(btn_layout)
        
        dialog.setLayout(layout)
        
        def apply_text():
            text = input_widget.text()
            if text_type == 'title':
                ax.set_title(text)
            elif text_type == 'xlabel':
                ax.set_xlabel(text)
            elif text_type == 'ylabel':
                ax.set_ylabel(text)
            self.draw()
            dialog.accept()
        
        btn_ok.clicked.connect(apply_text)
        btn_cancel.clicked.connect(dialog.reject)
        
        dialog.exec()
    
    def _edit_legend_text(self, ax):
        """Edit legend labels interactively after double-click"""
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QFormLayout
        
        legend = ax.get_legend()
        if not legend:
            return
        
        dialog = QDialog(self)
        dialog.setWindowTitle("Edit Legend Labels")
        layout = QVBoxLayout()
        
        # Get current legend labels
        labels = [text.get_text() for text in legend.get_texts()]
        
        # Create input fields for each label
        form_layout = QFormLayout()
        input_widgets = []
        for i, label_text in enumerate(labels):
            label = QLabel(f"Label {i+1}:")
            input_widget = QLineEdit(label_text)
            input_widgets.append(input_widget)
            form_layout.addRow(label, input_widget)
        
        layout.addLayout(form_layout)
        
        # Buttons
        btn_layout = QHBoxLayout()
        btn_ok = QPushButton("OK")
        btn_cancel = QPushButton("Cancel")
        btn_layout.addWidget(btn_ok)
        btn_layout.addWidget(btn_cancel)
        layout.addLayout(btn_layout)
        
        dialog.setLayout(layout)
        
        def apply_labels():
            # Get the lines from the axis
            lines = ax.get_lines()
            new_labels = [widget.text() for widget in input_widgets]
            
            # Update legend with new labels
            if len(new_labels) == len(lines):
                ax.legend(lines, new_labels, loc=legend._loc if hasattr(legend, '_loc') else 'best')
            self.draw()
            dialog.accept()
        
        btn_ok.clicked.connect(apply_labels)
        btn_cancel.clicked.connect(dialog.reject)
        
        dialog.exec()
    
    def _set_element_color(self, element_type):
        """Set color for labels, ticks, title, or lines"""
        color = QColorDialog.getColor()
        if color.isValid():
            color_hex = color.name()
            for ax in self.fig.axes:
                if element_type == 'label':
                    ax.xaxis.label.set_color(color_hex)
                    ax.yaxis.label.set_color(color_hex)
                elif element_type == 'tick':
                    ax.tick_params(axis='both', colors=color_hex)
                elif element_type == 'title':
                    ax.title.set_color(color_hex)
                elif element_type == 'line':
                    # Change color of all lines in the axis
                    for line in ax.get_lines():
                        line.set_color(color_hex)
            self.draw()
    
    def _set_background_color(self):
        """Set background color for plot canvas and axes"""
        color = QColorDialog.getColor()
        if color.isValid():
            color_hex = color.name()
            # Set figure background
            self.fig.set_facecolor(color_hex)
            # Set all axes backgrounds
            for ax in self.fig.axes:
                ax.set_facecolor(color_hex)
            self.draw()
    
    def _set_font_type(self):
        """Set font type for all text elements"""
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QPushButton
        
        dialog = QDialog(self)
        dialog.setWindowTitle("Set Font Type")
        layout = QVBoxLayout()
        
        label = QLabel("Font Family:")
        font_combo = QComboBox()
        fonts = ['Arial', 'Times New Roman', 'Courier New', 'Helvetica', 'Verdana', 
                 'Georgia', 'Comic Sans MS', 'Trebuchet MS', 'Calibri', 'DejaVu Sans']
        font_combo.addItems(fonts)
        layout.addWidget(label)
        layout.addWidget(font_combo)
        
        # Buttons
        btn_layout = QHBoxLayout()
        btn_ok = QPushButton("OK")
        btn_cancel = QPushButton("Cancel")
        btn_layout.addWidget(btn_ok)
        btn_layout.addWidget(btn_cancel)
        layout.addLayout(btn_layout)
        
        dialog.setLayout(layout)
        
        def apply_font():
            font_name = font_combo.currentText()
            for ax in self.fig.axes:
                ax.title.set_fontfamily(font_name)
                ax.xaxis.label.set_fontfamily(font_name)
                ax.yaxis.label.set_fontfamily(font_name)
                for tick in ax.get_xticklabels() + ax.get_yticklabels():
                    tick.set_fontfamily(font_name)
                legend = ax.get_legend()
                if legend:
                    for text in legend.get_texts():
                        text.set_fontfamily(font_name)
            self.draw()
            dialog.accept()
        
        btn_ok.clicked.connect(apply_font)
        btn_cancel.clicked.connect(dialog.reject)
        
        dialog.exec()
    
    def _set_text_style(self, element_type):
        """Set text style (bold, italic, normal) for title, labels, or ticks"""
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QPushButton
        
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Set {element_type.title()} Style")
        layout = QVBoxLayout()
        
        label = QLabel("Style:")
        style_combo = QComboBox()
        style_combo.addItems(['Normal', 'Bold', 'Italic', 'Bold Italic'])
        layout.addWidget(label)
        layout.addWidget(style_combo)
        
        # Buttons
        btn_layout = QHBoxLayout()
        btn_ok = QPushButton("OK")
        btn_cancel = QPushButton("Cancel")
        btn_layout.addWidget(btn_ok)
        btn_layout.addWidget(btn_cancel)
        layout.addLayout(btn_layout)
        
        dialog.setLayout(layout)
        
        def apply_style():
            style_text = style_combo.currentText()
            weight = 'bold' if 'Bold' in style_text else 'normal'
            style = 'italic' if 'Italic' in style_text else 'normal'
            
            for ax in self.fig.axes:
                if element_type == 'title':
                    ax.title.set_weight(weight)
                    ax.title.set_style(style)
                elif element_type == 'label':
                    ax.xaxis.label.set_weight(weight)
                    ax.xaxis.label.set_style(style)
                    ax.yaxis.label.set_weight(weight)
                    ax.yaxis.label.set_style(style)
                elif element_type == 'tick':
                    for tick in ax.get_xticklabels() + ax.get_yticklabels():
                        tick.set_weight(weight)
                        tick.set_style(style)
            self.draw()
            dialog.accept()
        
        btn_ok.clicked.connect(apply_style)
        btn_cancel.clicked.connect(dialog.reject)
        
        dialog.exec()
    
    def _set_legend_position(self):
        """Set legend position"""
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QPushButton
        
        dialog = QDialog(self)
        dialog.setWindowTitle("Set Legend Position")
        layout = QVBoxLayout()
        
        label = QLabel("Position:")
        pos_combo = QComboBox()
        positions = ['best', 'upper right', 'upper left', 'lower left', 'lower right',
                    'right', 'center left', 'center right', 'lower center', 'upper center', 'center']
        pos_combo.addItems(positions)
        layout.addWidget(label)
        layout.addWidget(pos_combo)
        
        # Buttons
        btn_layout = QHBoxLayout()
        btn_ok = QPushButton("OK")
        btn_cancel = QPushButton("Cancel")
        btn_layout.addWidget(btn_ok)
        btn_layout.addWidget(btn_cancel)
        layout.addLayout(btn_layout)
        
        dialog.setLayout(layout)
        
        def apply_position():
            position = pos_combo.currentText()
            for ax in self.fig.axes:
                legend = ax.get_legend()
                if legend:
                    # Move the existing legend to the new position without recreating it
                    legend.set_bbox_to_anchor(None)  # Reset any custom anchor
                    legend.set_loc(position)
                    legend.set_draggable(True)
            self.draw()
            dialog.accept()
        
        btn_ok.clicked.connect(apply_position)
        btn_cancel.clicked.connect(dialog.reject)
        
        dialog.exec()
    
    def _toggle_legend(self):
        """Toggle legend visibility"""
        for ax in self.fig.axes:
            legend = ax.get_legend()
            if legend:
                legend.set_visible(not legend.get_visible())
        self.draw()
    
    def _toggle_legend_draggable(self):
        """Toggle legend draggable state"""
        for ax in self.fig.axes:
            legend = ax.get_legend()
            if legend:
                # Toggle draggable state
                current_state = legend.get_draggable()
                if current_state:
                    legend.set_draggable(False)
                else:
                    legend.set_draggable(True)
        self.draw()
    
    def _toggle_grid(self):
        """Toggle grid visibility"""
        for ax in self.fig.axes:
            # Check current grid state by checking if gridlines exist
            current_state = ax.xaxis._major_tick_kw.get('gridOn', False)
            ax.grid(not current_state)
        self.draw()
    
    def _set_grid_style(self):
        """Set grid line style"""
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QPushButton
        
        dialog = QDialog(self)
        dialog.setWindowTitle("Set Grid Style")
        layout = QVBoxLayout()
        
        label = QLabel("Line Style:")
        style_combo = QComboBox()
        style_combo.addItems(['solid', 'dashed', 'dotted', 'dashdot'])
        layout.addWidget(label)
        layout.addWidget(style_combo)
        
        # Buttons
        btn_layout = QHBoxLayout()
        btn_ok = QPushButton("OK")
        btn_cancel = QPushButton("Cancel")
        btn_layout.addWidget(btn_ok)
        btn_layout.addWidget(btn_cancel)
        layout.addLayout(btn_layout)
        
        dialog.setLayout(layout)
        
        def apply_style():
            style = style_combo.currentText()
            for ax in self.fig.axes:
                ax.grid(True, linestyle=style)
            self.draw()
            dialog.accept()
        
        btn_ok.clicked.connect(apply_style)
        btn_cancel.clicked.connect(dialog.reject)
        
        dialog.exec()
    
    def _set_grid_color(self):
        """Set grid color"""
        color = QColorDialog.getColor()
        if color.isValid():
            color_hex = color.name()
            for ax in self.fig.axes:
                ax.grid(True, color=color_hex)
            self.draw()
    
    def _set_grid_alpha(self):
        """Set grid transparency"""
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QDoubleSpinBox, QPushButton
        
        dialog = QDialog(self)
        dialog.setWindowTitle("Set Grid Transparency")
        layout = QVBoxLayout()
        
        label = QLabel("Alpha (0.0 = transparent, 1.0 = opaque):")
        alpha_spin = QDoubleSpinBox()
        alpha_spin.setRange(0.0, 1.0)
        alpha_spin.setSingleStep(0.1)
        alpha_spin.setValue(0.3)
        layout.addWidget(label)
        layout.addWidget(alpha_spin)
        
        # Buttons
        btn_layout = QHBoxLayout()
        btn_ok = QPushButton("OK")
        btn_cancel = QPushButton("Cancel")
        btn_layout.addWidget(btn_ok)
        btn_layout.addWidget(btn_cancel)
        layout.addLayout(btn_layout)
        
        dialog.setLayout(layout)
        
        def apply_alpha():
            alpha = alpha_spin.value()
            for ax in self.fig.axes:
                ax.grid(True, alpha=alpha)
            self.draw()
            dialog.accept()
        
        btn_ok.clicked.connect(apply_alpha)
        btn_cancel.clicked.connect(dialog.reject)
        
        dialog.exec()
        
    def set_theme(self, theme_name):
        """Update theme dynamically"""
        self.theme_name = theme_name
        self.theme = ThemeManager.get_theme(theme_name)
        self.is_light = self.theme["MAIN_COLOR"] in ["#FFFFFF", "#F8F9FA", "#F5FFFE"]
        
        if self.is_light:
            fig_color = "#FFFFFF"
            axes_color = "#FFFFFF"
            self.text_color = "#212529"
            self.grid_color = "#D0D0D0"
        else:
            fig_color = self.theme["MAIN_COLOR"]
            axes_color = self.theme["MAIN_COLOR"]
            self.text_color = "#FFFFFF"  # White text for dark themes
            self.grid_color = self.theme["ACCENT_COLOR"]
        
        self.fig.set_facecolor(fig_color)
        self.ax.set_facecolor(axes_color)
        self.accent_color = self.theme["SECONDARY_COLOR"]
        
        # Redraw canvas
        self.fig.canvas.draw_idle()
        
    def draw_plot(self, x, y, title=None, xlabel="X", ylabel="Y", style="line"):
        """Draw a plot with modern styling"""
        self.ax.clear()
        self.ax.set_facecolor("#FFFFFF" if self.is_light else self.theme["MAIN_COLOR"])
        
        if style == "line":
            self.ax.plot(x, y, marker="o", color=self.accent_color, linewidth=2, markersize=6)
        elif style == "scatter":
            self.ax.scatter(x, y, color=self.accent_color, s=50, alpha=0.6)
        elif style == "bar":
            self.ax.bar(x, y, color=self.theme["ACCENT_COLOR"], alpha=0.7)
        
        if title:
            self.ax.set_title(title, fontsize=12, color=self.text_color, fontweight='bold')
        self.ax.set_xlabel(xlabel, fontsize=10, color=self.text_color)
        self.ax.set_ylabel(ylabel, fontsize=10, color=self.text_color)
        
        self.ax.tick_params(colors=self.text_color, labelsize=9)
        self.ax.grid(True, alpha=0.2, color=self.grid_color)
        self.ax.spines['bottom'].set_color(self.text_color)
        self.ax.spines['left'].set_color(self.text_color)
        self.ax.spines['top'].set_visible(False)
        self.ax.spines['right'].set_visible(False)
        self.fig.tight_layout()
        self.draw()
        
        # Save initial limits after drawing
        self._save_initial_limits()
    
    def _save_initial_limits(self):
        """Save the initial axis limits for reset zoom"""
        if self.initial_xlim is None:
            self.initial_xlim = self.ax.get_xlim()
        if self.initial_ylim is None:
            self.initial_ylim = self.ax.get_ylim()
        if len(self.fig.axes) > 1 and self.initial_y2lim is None:
            self.initial_y2lim = self.fig.axes[1].get_ylim()
        if len(self.fig.axes) > 2 and self.initial_y3lim is None:
            self.initial_y3lim = self.fig.axes[2].get_ylim()
