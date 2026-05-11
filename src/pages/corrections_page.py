import numpy as np
import pandas as pd
from datetime import datetime
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                               QSplitter, QTabWidget, QGroupBox, QTextEdit, 
                               QPushButton, QFileDialog, QMessageBox, QComboBox, 
                               QLineEdit, QFormLayout, QGridLayout, QScrollArea, 
                               QCheckBox, QDoubleSpinBox, QInputDialog)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from matplotlib.ticker import FuncFormatter

from theme_manager import ThemeManager
from plot_canvas import PlotCanvas


def _r2_score(y_true, y_pred):
    """Compute R^2 score without external dependencies."""
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)

    if y_true.shape != y_pred.shape:
        raise ValueError("y_true and y_pred must have the same shape")
    if y_true.size == 0:
        raise ValueError("y_true and y_pred must not be empty")

    ss_res = np.sum((y_true - y_pred) ** 2)
    ss_tot = np.sum((y_true - np.mean(y_true)) ** 2)

    # Keep behavior stable when variance is zero.
    if ss_tot == 0:
        return 1.0 if ss_res == 0 else 0.0

    return 1.0 - (ss_res / ss_tot)

class CorrectionsPage(QWidget):
    """Corrections page for linearity and other corrections"""
    
    def __init__(self, theme_name="Nord Dark", scale_page=None):
        super().__init__()
        self.theme_name = theme_name
        self.theme = ThemeManager.get_theme(theme_name)
        self.scale_page = scale_page
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout()
        
        # Header
        header = QLabel("⚙️ Corrections")
        header.setFont(QFont("Arial", 16, QFont.Bold))
        layout.addWidget(header)
        
        # Create vertical splitter for tabs and logger
        splitter = QSplitter(Qt.Vertical)
        
        # Tabs for different corrections
        tabs = QTabWidget()
        
        # 1. Size-of-Source Correction
        sse_widget = self.create_sse_tab()
        tabs.addTab(sse_widget, "Size-of-Source Correction")
        
        # 2. Linearity Correction
        linearity_widget = self.create_linearity_tab()
        tabs.addTab(linearity_widget, "Linearity Correction")
        
        # 3. Emissivity & Temperature Drop Correction (Combined)
        emissivity_widget = self.create_emissivity_tab()
        tabs.addTab(emissivity_widget, "Emissivity and Temperature Drop Corrections")
        
        splitter.addWidget(tabs)
        
        # Add logger/console widget at the bottom
        logger_group = QGroupBox("Console / Error Log")
        logger_layout = QVBoxLayout()
        self.log_console = QTextEdit()
        self.log_console.setReadOnly(True)
        self.log_console.setMinimumHeight(60)  # Minimum instead of maximum
        self.log_console.setStyleSheet(f"""
            QTextEdit {{
                background-color: #1e1e1e;
                color: #d4d4d4;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 10pt;
                border: 1px solid {self.theme["ACCENT_COLOR"]};
            }}
        """)
        logger_layout.addWidget(self.log_console)
        
        # Clear button for log
        btn_clear_log = QPushButton("🗑️ Clear Log")
        btn_clear_log.clicked.connect(lambda: self.log_console.clear())
        logger_layout.addWidget(btn_clear_log)
        
        logger_group.setLayout(logger_layout)
        splitter.addWidget(logger_group)
        
        # Set initial sizes (tabs get more space than logger)
        splitter.setSizes([600, 100])
        
        layout.addWidget(splitter, stretch=1)
        
        self.setLayout(layout)
        self._log("CorrectionsPage initialized successfully")
    
    def _log(self, message, level="INFO"):
        """Log message to console widget"""
        import datetime
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        
        # Color coding based on level
        if level == "ERROR":
            color = "#E06C75"
        elif level == "WARNING":
            color = "#E5C07B"
        elif level == "SUCCESS":
            color = "#98C379"
        else:  # INFO
            color = "#61AFEF"
        
        formatted_msg = f'<span style="color: #888;">[{timestamp}]</span> <span style="color: {color}; font-weight: bold;">[{level}]</span> <span style="color: {color};">{message}</span>'
        self.log_console.append(formatted_msg)
        
        # Auto-scroll to bottom
        scrollbar = self.log_console.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
    
    # SSE Methods
    def sse_upload_fit_data(self):
        """Upload SSE fit data"""
        try:
            file_path, _ = QFileDialog.getOpenFileName(self, "Select Fit Data File", "", "Text Files (*.txt);;CSV Files (*.csv)")
            if not file_path:
                return
            
            if file_path.endswith('.csv'):
                data = pd.read_csv(file_path, header=None)
            else:
                data = pd.read_csv(file_path, sep='\t', header=None)
            
            self.sse_x_data = data.iloc[:, 0].values
            self.sse_y_data = data.iloc[:, 1].values
            
            # Plot data
            self.sse_canvas_fit.ax.clear()
            self.sse_canvas_fit.ax.plot(self.sse_x_data, self.sse_y_data, 'o')
            self.sse_canvas_fit.ax.set_xlabel('Aperture Diameter (mm)')
            self.sse_canvas_fit.ax.set_ylabel('SSE (a.u.)')
            self.sse_canvas_fit.ax.set_title('SSE Fit Data')
            self.sse_canvas_fit.draw()
            
            self.btn_sse_fit.setEnabled(True)
            self.sse_fit_result_label.setText("Fit Result: Data loaded, ready to fit")
            self._log("SSE fit data loaded successfully", "SUCCESS")
            
        except Exception as e:
            self._log(f"Error loading SSE fit data: {str(e)}", "ERROR")
            QMessageBox.warning(self, "Load Error", f"Failed to load data: {str(e)}")
    
    def sse_upload_scan_data(self):
        """Upload scan result data"""
        try:
            file_path, _ = QFileDialog.getOpenFileName(self, "Select Scan Result File", "", "Text Files (*.txt);;CSV Files (*.csv)")
            if not file_path:
                return
            
            if file_path.endswith('.csv'):
                data = pd.read_csv(file_path, header=None)
            else:
                data = pd.read_csv(file_path, sep='\t', header=None)
            
            self.sse_scan_x = data.iloc[:, 0].values
            self.sse_scan_y = data.iloc[:, 1].values
            
            # Set furnace size to the range of x-axis
            furnace_size = max(self.sse_scan_x) - min(self.sse_scan_x)
            self.sse_furnace_edit.setText(f"{furnace_size:.2f}")
            
            # Plot scan data
            self.sse_canvas_scan.ax.clear()
            self.sse_canvas_scan.ax.plot(self.sse_scan_x, self.sse_scan_y, 'o-')
            self.sse_canvas_scan.ax.set_xlabel('Distance from Center (mm)')
            self.sse_canvas_scan.ax.set_ylabel('Normalized Signal')
            self.sse_canvas_scan.ax.set_title('Scan Result')
            self.sse_canvas_scan.draw()
            
            self._log("Scan result data loaded successfully", "SUCCESS")
            
        except Exception as e:
            self._log(f"Error loading scan data: {str(e)}", "ERROR")
            QMessageBox.warning(self, "Load Error", f"Failed to load scan data: {str(e)}")
    
    def sse_fit_data(self):
        """Fit SSE data with selected function"""
        if self.sse_x_data is None or self.sse_y_data is None:
            QMessageBox.warning(self, "No Data", "Please upload fit data first")
            return
        
        fit_type = self.sse_fit_type_combo.currentText()
        
        try:
            if fit_type == "Polynomial":
                degree, ok = QInputDialog.getInt(self, "Polynomial Degree", "Enter degree (1-10):", 2, 1, 10)
                if not ok:
                    return
                coeffs = np.polyfit(self.sse_x_data, self.sse_y_data, degree)
                y_pred = np.polyval(coeffs, self.sse_x_data)
                self.sse_fit_func = lambda x: np.polyval(coeffs, x)
                self.sse_fit_params = coeffs
                fit_label = f'Polynomial (deg {degree})'
                
            elif fit_type == "Exponential":
                from scipy.optimize import curve_fit
                a_guess, ok1 = QInputDialog.getDouble(self, "Initial Guess", "Enter a (amplitude):", 2e-4, -1e10, 1e10, 10)
                if not ok1:
                    return
                b_guess, ok2 = QInputDialog.getDouble(self, "Initial Guess", "Enter b (rate):", 5e-2, -1e10, 1e10, 10)
                if not ok2:
                    return
                
                exp_func = lambda x, a, b: a * (1 - np.exp(-(b * x)))
                params, _ = curve_fit(exp_func, self.sse_x_data, self.sse_y_data, p0=[a_guess, b_guess])
                y_pred = exp_func(self.sse_x_data, *params)
                self.sse_fit_func = lambda x: exp_func(x, *params)
                self.sse_fit_params = params
                fit_label = 'Exponential'
                
            elif fit_type == "Logarithmic":
                from scipy.optimize import curve_fit
                if np.any(self.sse_x_data <= 0):
                    raise ValueError("Logarithmic fit requires positive x values")
                
                log_func = lambda x, a, b: a + b * np.log(x)
                params, _ = curve_fit(log_func, self.sse_x_data, self.sse_y_data, p0=[1, 1])
                y_pred = log_func(self.sse_x_data, *params)
                self.sse_fit_func = lambda x: log_func(x, *params)
                self.sse_fit_params = params
                fit_label = 'Logarithmic'
                
            elif fit_type == "Power":
                from scipy.optimize import curve_fit
                if np.any(self.sse_x_data <= 0):
                    raise ValueError("Power fit requires positive x values")
                
                a_guess, ok1 = QInputDialog.getDouble(self, "Initial Guess", "Enter a (coefficient):", 1.0, -1e10, 1e10, 10)
                if not ok1:
                    return
                b_guess, ok2 = QInputDialog.getDouble(self, "Initial Guess", "Enter b (exponent):", 1.0, -1e10, 1e10, 10)
                if not ok2:
                    return
                
                power_func = lambda x, a, b: a * x**b
                params, _ = curve_fit(power_func, self.sse_x_data, self.sse_y_data, p0=[a_guess, b_guess])
                y_pred = power_func(self.sse_x_data, *params)
                self.sse_fit_func = lambda x: power_func(x, *params)
                self.sse_fit_params = params
                fit_label = 'Power'
                
            elif fit_type == "Two-term Exponential":
                from scipy.optimize import curve_fit
                
                A1, ok1 = QInputDialog.getDouble(self, "Initial Guess", "Enter A1:", 2e-4, -1e10, 1e10, 10)
                if not ok1:
                    return
                b1, ok2 = QInputDialog.getDouble(self, "Initial Guess", "Enter b1:", 0.05, -1e10, 1e10, 10)
                if not ok2:
                    return
                A2, ok3 = QInputDialog.getDouble(self, "Initial Guess", "Enter A2:", 2e-4, -1e10, 1e10, 10)
                if not ok3:
                    return
                b2, ok4 = QInputDialog.getDouble(self, "Initial Guess", "Enter b2:", 0.005, -1e10, 1e10, 10)
                if not ok4:
                    return
                c, ok5 = QInputDialog.getDouble(self, "Initial Guess", "Enter c:", 1e-5, -1e10, 1e10, 10)
                if not ok5:
                    return
                
                two_exp_func = lambda x, A1, b1, A2, b2, c: c + A1*(1 - np.exp(-b1*x)) + A2*(1 - np.exp(-b2*x))
                p0 = [A1, b1, A2, b2, c]
                lb = [0, 1e-6, 0, 1e-6, -np.inf]
                ub = [1e-2, 1.0, 5e-1, 1.0, np.inf]
                params, _ = curve_fit(two_exp_func, self.sse_x_data, self.sse_y_data, p0=p0, bounds=(lb, ub), maxfev=200000)
                y_pred = two_exp_func(self.sse_x_data, *params)
                self.sse_fit_func = lambda x: two_exp_func(x, *params)
                self.sse_fit_params = params
                fit_label = 'Two-term Exponential'
            
            elif fit_type == "Custom Equation":
                from scipy.optimize import curve_fit
                
                # Get custom equation and parameters
                equation_str = self.sse_custom_eq_edit.text().strip()
                params_str = self.sse_custom_params_edit.text().strip()
                guess_str = self.sse_custom_guess_edit.text().strip()
                
                if not equation_str or not params_str or not guess_str:
                    raise ValueError("Please enter equation, parameters, and initial guesses")
                
                # Parse parameter names
                param_names = [p.strip() for p in params_str.split(',')]
                
                # Parse initial guesses
                try:
                    p0 = [float(g.strip()) for g in guess_str.split(',')]
                except ValueError:
                    raise ValueError("Initial guesses must be numbers separated by commas")
                
                if len(param_names) != len(p0):
                    raise ValueError(f"Number of parameters ({len(param_names)}) must match number of guesses ({len(p0)})")
                
                # Create function from equation string
                # Build parameter string for lambda
                param_str_lambda = ', '.join(param_names)
                
                # Create the fit function using safe AST-based parser (no eval)
                from safe_math import safe_make_function
                try:
                    custom_func = safe_make_function(equation_str, param_names)
                except Exception as e:
                    raise ValueError(f"Invalid equation: {str(e)}")
                
                # Test the function
                try:
                    test_result = custom_func(self.sse_x_data[0], *p0)
                except Exception as e:
                    raise ValueError(f"Equation evaluation failed: {str(e)}")
                
                # Fit the data
                try:
                    params, _ = curve_fit(custom_func, self.sse_x_data, self.sse_y_data, p0=p0, maxfev=200000)
                except Exception as e:
                    raise ValueError(f"Curve fitting failed: {str(e)}")
                
                y_pred = custom_func(self.sse_x_data, *params)
                self.sse_fit_func = lambda x: custom_func(x, *params)
                self.sse_fit_params = params
                self.sse_custom_param_names = param_names
                fit_label = 'Custom Equation'
            
            # Calculate R²
            r2 = _r2_score(self.sse_y_data, y_pred)
            
            # Plot fit
            self.sse_canvas_fit.ax.clear()
            self.sse_canvas_fit.ax.plot(self.sse_x_data, self.sse_y_data, 'o', label='Data')
            x_fit = np.linspace(min(self.sse_x_data), max(self.sse_x_data), 100)
            y_fit = self.sse_fit_func(x_fit)
            self.sse_canvas_fit.ax.plot(x_fit, y_fit, 'r-', label=f'{fit_label} fit')
            self.sse_canvas_fit.ax.set_xlabel('Aperture Diameter (mm)')
            self.sse_canvas_fit.ax.set_ylabel('SSE (a.u.)')
            self.sse_canvas_fit.ax.set_title(f'{fit_label} Fit: R² = {r2:.4f}')
            self.sse_canvas_fit.ax.legend()
            self.sse_canvas_fit.draw()
            
            # Generate readable equation and parameters
            if fit_type == "Polynomial":
                degree = len(self.sse_fit_params)
                coeffs = self.sse_fit_params
                if degree == 1:
                    model_str = "y = a"
                    params_str = f"a = {coeffs[0]:.4e}"
                elif degree == 2:
                    model_str = "y = a·x + b"
                    params_str = f"a = {coeffs[0]:.4e}\nb = {coeffs[1]:.4e}"
                elif degree == 3:
                    model_str = "y = a·x² + b·x + c"
                    params_str = f"a = {coeffs[0]:.4e}\nb = {coeffs[1]:.4e}\nc = {coeffs[2]:.4e}"
                elif degree == 4:
                    model_str = "y = a·x³ + b·x² + c·x + d"
                    params_str = f"a = {coeffs[0]:.4e}\nb = {coeffs[1]:.4e}\nc = {coeffs[2]:.4e}\nd = {coeffs[3]:.4e}"
                elif degree == 5:
                    model_str = "y = a·x⁴ + b·x³ + c·x² + d·x + e"
                    params_str = f"a = {coeffs[0]:.4e}\nb = {coeffs[1]:.4e}\nc = {coeffs[2]:.4e}\nd = {coeffs[3]:.4e}\ne = {coeffs[4]:.4e}"
                elif degree == 6:
                    model_str = "y = a·x⁵ + b·x⁴ + c·x³ + d·x² + e·x + f"
                    params_str = f"a = {coeffs[0]:.4e}\nb = {coeffs[1]:.4e}\nc = {coeffs[2]:.4e}\nd = {coeffs[3]:.4e}\ne = {coeffs[4]:.4e}\nf = {coeffs[5]:.4e}"
                else:
                    model_str = f"y = Polynomial (degree {degree-1})"
                    params_str = "\n".join([f"a{i} = {c:.4e}" for i, c in enumerate(coeffs)])
            elif fit_type == "Exponential":
                model_str = "y = a · (1 - exp(-b·x))"
                a, b = self.sse_fit_params
                params_str = f"a = {a:.4e}\nb = {b:.4e}"
            elif fit_type == "Logarithmic":
                model_str = "y = a + b · ln(x)"
                a, b = self.sse_fit_params
                params_str = f"a = {a:.4e}\nb = {b:.4e}"
            elif fit_type == "Power":
                model_str = "y = a · x^b"
                a, b = self.sse_fit_params
                params_str = f"a = {a:.4e}\nb = {b:.4e}"
            elif fit_type == "Two-term Exponential":
                model_str = "y = c + A₁·(1 - exp(-b₁·x)) + A₂·(1 - exp(-b₂·x))"
                A1, b1, A2, b2, c = self.sse_fit_params
                params_str = f"c = {c:.4e}\nA₁ = {A1:.4e}\nb₁ = {b1:.4e}\nA₂ = {A2:.4e}\nb₂ = {b2:.4e}"
            elif fit_type == "Custom Equation":
                equation_str = self.sse_custom_eq_edit.text().strip()
                model_str = f"y = {equation_str}"
                # Use custom parameter names if available
                if hasattr(self, 'sse_custom_param_names'):
                    params_str = "\n".join([f"{name} = {val:.4e}" for name, val in zip(self.sse_custom_param_names, self.sse_fit_params)])
                else:
                    params_str = "\n".join([f"p{i} = {val:.4e}" for i, val in enumerate(self.sse_fit_params)])
            else:
                model_str = "y = Unknown model"
                params_str = ""
            
            # Update labels
            self.sse_equation_label.setText(model_str)
            self.sse_params_label.setText(params_str)
            self.sse_fit_result_label.setText(f"R² = {r2:.4f}")
            
            self._log(f"SSE fit completed: {fit_label}, R² = {r2:.4f}", "SUCCESS")
            
        except Exception as e:
            self._log(f"Fit error: {str(e)}", "ERROR")
            QMessageBox.warning(self, "Fit Error", f"Fit failed: {str(e)}")
            
    
    def sse_calculate_temperature(self):
        """Calculate temperature from signal using Sakuma-Hattori equation"""
        try:
            signal = float(self.sse_signal_edit.text())
            a = float(self.sse_a_edit.text())
            b = float(self.sse_b_edit.text())
            c = float(self.sse_c_edit.text())
            c2 = float(self.sse_c2_edit.text())
            
            if signal <= 0 or a == 0:
                raise ValueError("Signal must be positive and a cannot be zero")
            
            # Sakuma-Hattori equation: T = (1/a) * ((c2 / ln(c / signal + 1)) - b)
            argument = c / signal + 1
            if argument <= 0:
                raise ValueError("Invalid signal value")
            
            T = (1 / a) * ((c2 / np.log(argument)) - b)
            
            self.sse_calculated_temp = T
            self.sse_temp_result_label.setText(f"Calculated Temperature: {T:.4f} K")
            self._log(f"Temperature calculated: {T:.4f} K", "SUCCESS")
            
        except ValueError as e:
            self._log(f"Temperature calculation error: {str(e)}", "ERROR")
            QMessageBox.warning(self, "Calculation Error", str(e))
    
    def sse_calculate_signal(self):
        """Calculate signal from temperature using inverse Sakuma-Hattori equation"""
        try:
            temp = float(self.sse_temp_edit.text())
            a = float(self.sse_a_edit.text())
            b = float(self.sse_b_edit.text())
            c = float(self.sse_c_edit.text())
            c2 = float(self.sse_c2_edit.text())
            
            if temp <= 0 or a == 0 or c == 0:
                raise ValueError("Temperature, a, and c must be positive")
            
            # Inverse Sakuma-Hattori: signal = c / (exp(c2 / (temp * a + b)) - 1)
            exponent = c2 / (temp * a + b)
            signal = c / (np.exp(exponent) - 1)
            
            self.sse_calculated_signal = signal
            self.sse_signal_result_label.setText(f"Calculated Signal: {signal:.6e}")
            self._log(f"Signal calculated: {signal:.6e}", "SUCCESS")
            
        except ValueError as e:
            self._log(f"Signal calculation error: {str(e)}", "ERROR")
            QMessageBox.warning(self, "Calculation Error", str(e))
    
    def sse_calculate_sse_correction(self):
        """Calculate SSE correction (ΔT and corrected signal)"""
        try:
            if self.sse_fit_func is None:
                raise ValueError("Please fit data first")
            
            # Get parameters
            temp = float(self.sse_temp_edit.text())
            signal = float(self.sse_signal_edit.text())
            cavity_size = float(self.sse_cavity_edit.text())
            target_size = float(self.sse_target_edit.text())
            furnace_size = float(self.sse_furnace_edit.text())
            wavelength = float(self.sse_wavelength_edit.text())
            a = float(self.sse_a_edit.text())
            b = float(self.sse_b_edit.text())
            c = float(self.sse_c_edit.text())
            c2 = float(self.sse_c2_edit.text())
            
            # Get SSE values from fit
            sse_cavity = self.sse_fit_func(cavity_size)
            sse_target = self.sse_fit_func(target_size)
            sse_furnace = self.sse_fit_func(furnace_size)
            
            # ---------------------------------------------------------
            # Ring-by-Ring Numerical Integration
            # ---------------------------------------------------------
            scan_x = getattr(self, 'sse_scan_x', None)
            scan_y = getattr(self, 'sse_scan_y', None)
            has_scan_data = scan_x is not None and scan_y is not None
            
            c_sse_pos = 0.0
            c_sse_neg = 0.0
            
            # 2.0 mm diameter step (1.0 mm radius step)
            step_d = 2.0
            current_d = cavity_size
            
            while current_d < furnace_size:
                d_in = current_d
                d_out = min(current_d + step_d, furnace_size)
                
                if d_in >= d_out:
                    break
                    
                # Calculate delta SSE for this ring
                sse_in = self.sse_fit_func(d_in)
                sse_out = self.sse_fit_func(d_out)
                delta_sse = sse_out - sse_in
                
                # Get L_norm at the midpoint radius of this ring
                d_mid = (d_in + d_out) / 2.0
                r_mid = d_mid / 2.0
                
                l_norm = 1.0
                if has_scan_data:
                    l_norm = np.interp(r_mid, scan_x, scan_y)
                
                # Assign to positive or negative contribution
                if d_mid <= target_size:
                    c_sse_pos += delta_sse / l_norm
                else:
                    c_sse_neg += delta_sse * l_norm
                    
                current_d = d_out
                
            c_sse = c_sse_pos - c_sse_neg
            
            # Calculate ΔT
            # ΔT = (λ * T^2 / c2) * C_SSE
            delta_t = (wavelength * temp**2 / c2) * c_sse
            
            # Calculate corrected signal
            sc = signal * (1 + c_sse)
            
            # Display results
            self.sse_delta_t_label.setText(f"ΔT: {delta_t:.4f} K")
            self.sse_sc_label.setText(f"Corrected Signal (S_c): {sc:.6e}")
            
            self._log(f"SSE correction calculated: ΔT = {delta_t:.4f} K, S_c = {sc:.6e}", "SUCCESS")
            
        except ValueError as e:
            self._log(f"SSE correction error: {str(e)}", "ERROR")
            QMessageBox.warning(self, "Calculation Error", str(e))
        except Exception as e:
            self._log(f"SSE correction error: {str(e)}", "ERROR")
            QMessageBox.warning(self, "Calculation Error", f"Failed: {str(e)}")
    
    def sse_reset_cache(self):
        """Reset cached SSE calculations when parameters change"""
        pass
    
    def sse_refresh_presets(self):
        """Refresh preset fixed points from Scale Realization page"""
        if not hasattr(self, 'scale_page') or self.scale_page is None:
            self._log("Scale Realization page not linked", "WARNING")
            return
            
        current_text = self.sse_preset_combo.currentText()
        self.sse_preset_combo.blockSignals(True)
        self.sse_preset_combo.clear()
        self.sse_preset_combo.addItem("Custom Input", userData={"temp": None, "signal": None})
        
        # Pull fixed points from ScaleRealizationPage's fp_table
        table = getattr(self.scale_page, 'fp_table', None)
        if table:
            added = 0
            for row in range(table.rowCount()):
                try:
                    # Column 1 is a QComboBox widget, not a table item
                    name_widget = table.cellWidget(row, 1)
                    name = name_widget.currentText().strip() if name_widget else ""
                    
                    # Columns 2 and 3 are plain QTableWidgetItem
                    temp_item = table.item(row, 2)
                    sig_item = table.item(row, 3)
                    
                    if name and temp_item and sig_item:
                        temp_text = temp_item.text().strip()
                        sig_text = sig_item.text().strip()
                        if temp_text and sig_text:
                            temp = float(temp_text)
                            sig = float(sig_text)
                            self.sse_preset_combo.addItem(f"{name} ({temp:.4f} K)", userData={"temp": temp, "signal": sig})
                            added += 1
                except (ValueError, AttributeError, TypeError):
                    continue
            if added == 0:
                self._log("No fixed points with temperature and signal found in Scale Realization", "WARNING")
        
        # Try to restore previous selection
        idx = self.sse_preset_combo.findText(current_text)
        if idx >= 0:
            self.sse_preset_combo.setCurrentIndex(idx)
        else:
            self.sse_preset_combo.setCurrentIndex(0)
            
        self.sse_preset_combo.blockSignals(False)
        
        # Always re-populate fields after refresh so updated signal values are loaded
        final_idx = self.sse_preset_combo.currentIndex()
        if final_idx > 0:
            self.sse_on_preset_changed(final_idx)
        
        self.sse_preset_combo.blockSignals(False)
        self._log("Presets refreshed from Scale Realization", "INFO")
        
    def sse_on_preset_changed(self, index):
        """Handle preset selection to auto-populate fields"""
        if index <= 0:
            return  # Custom input
            
        data = self.sse_preset_combo.itemData(index)
        if data:
            self.sse_temp_edit.setText(f"{data['temp']}")
            self.sse_signal_edit.setText(f"{data['signal']:.6e}")
            
    def sse_on_manual_edit(self):
        """Switch to 'Custom Input' if the user manually types over a preset"""
        if self.sse_preset_combo.currentIndex() != 0:
            self.sse_preset_combo.blockSignals(True)
            self.sse_preset_combo.setCurrentIndex(0)
            self.sse_preset_combo.blockSignals(False)

    def sse_toggle_custom_equation(self, fit_type):
        """Show/hide custom equation widget based on fit type"""
        if hasattr(self, 'sse_custom_eq_widget'):
            self.sse_custom_eq_widget.setVisible(fit_type == "Custom Equation")
    
    def sse_update_mode(self):
        """Auto-update calculation mode based on target vs cavity size"""
        try:
            target_size = float(self.sse_target_edit.text())
            cavity_size = float(self.sse_cavity_edit.text())
            
            self.sse_mode_combo.blockSignals(True)
            if target_size > cavity_size:
                self.sse_mode_combo.setCurrentIndex(0)
            else:
                self.sse_mode_combo.setCurrentIndex(1)
            self.sse_mode_combo.blockSignals(False)
            
        except ValueError:
            pass
    
    def apply_emissivity_correction(self):
        """Apply emissivity correction using Planck's law"""
        try:
            # Get the emissivity value
            emissivity = float(self.emiss_emissivity_edit.text())
            
            # Get ambient temperature
            T_amb = float(self.emiss_ambient_temp_edit.text())
            
            # Check if we have SSE corrected signal and auto-populate if available
            use_sse_signal = False
            if hasattr(self, 'sse_sc_label') and 'S_c:' in self.sse_sc_label.text():
                sc_text = self.sse_sc_label.text().split(': ')[1] if ': ' in self.sse_sc_label.text() else None
                if sc_text and sc_text != '-':
                    # SSE correction is available, use it and update the input field
                    sc = float(sc_text)
                    self.emiss_signal_edit.setText(f"{sc:.6e}")
                    use_sse_signal = True
                    self._log("Using SSE corrected signal for emissivity correction", "INFO")
            
            # Get the signal to use (either from SSE or manual input)
            sc = float(self.emiss_signal_edit.text())
            
            # Get wavelength and c2 from SSE page
            wavelength = float(self.sse_wavelength_edit.text())  # μm
            c2 = float(self.sse_c2_edit.text())  # μm·K
            
            # Get temperature from SSE page
            T_ind = float(self.sse_temp_edit.text())  # Indicated temperature
            
            # Planck's law constants
            C1 = 3.7418e-16  # W·m²
            C2 = c2 / 1e6  # Convert from μm·K to m·K (c2 is in μm·K, need m·K)
            
            # Convert wavelength to meters
            lambda_m = wavelength * 1e-6  # μm to m
            
            # Planck's law function
            def planck_radiance(T, wavelength_m):
                """Calculate spectral radiance using Planck's law
                L_λ,bb(T) = C1 / (λ^5 * (exp(C2/(λ*T)) - 1))
                """
                return C1 / (wavelength_m**5 * (np.exp(C2 / (wavelength_m * T)) - 1))
            
            # Calculate radiances
            L_ind = planck_radiance(T_ind, lambda_m)
            L_amb = planck_radiance(T_amb, lambda_m)
            
            # The corrected signal corresponds to the indicated temperature with emissivity effect
            # We need to find T_obj such that:
            # L_bb(T_ind) = ε * L_bb(T_obj) + (1-ε) * L_bb(T_amb)
            # Solving for L_bb(T_obj):
            # L_bb(T_obj) = [L_bb(T_ind) - (1-ε) * L_bb(T_amb)] / ε
            
            L_obj_radiance = (L_ind - (1 - emissivity) * L_amb) / emissivity
            
            # Now we need to invert Planck's law to get T_obj from L_obj_radiance
            # L = C1 / (λ^5 * (exp(C2/(λ*T)) - 1))
            # Rearranging: exp(C2/(λ*T)) = 1 + C1/(λ^5 * L)
            # C2/(λ*T) = ln(1 + C1/(λ^5 * L))
            # T = C2 / (λ * ln(1 + C1/(λ^5 * L)))
            
            exp_term = 1 + C1 / (lambda_m**5 * L_obj_radiance)
            T_obj = C2 / (lambda_m * np.log(exp_term))
            
            # Calculate the corrected signal based on T_obj
            # Signal ratio follows Planck's law ratio
            signal_correction_factor = L_obj_radiance / L_ind
            emissivity_corrected_signal = sc * signal_correction_factor
            
            # Calculate ΔT
            delta_T_emissivity = T_obj - T_ind
            
            # Display result
            self.emissivity_corrected_label.setText(
                f"T_obj (Corrected): {T_obj:.2f} K\n"
                f"ΔT (emissivity): {delta_T_emissivity:.4f} K\n"
                f"Corrected Signal: {emissivity_corrected_signal:.6e}"
            )
            
            # Store for potential further use
            self.emissivity_corrected_temp = T_obj
            self.delta_t_emissivity = delta_T_emissivity
            self.emissivity_corrected_signal = emissivity_corrected_signal
            self.T_ind = T_ind
            
            self._log(f"Emissivity correction applied: ΔT = {delta_T_emissivity:.4f} K", "SUCCESS")
            
        except ValueError as e:
            self._log(f"Emissivity correction error: {str(e)}", "ERROR")
            QMessageBox.warning(self, "Input Error", f"Please enter valid numeric values! {str(e)}")
        except Exception as e:
            self._log(f"Emissivity correction error: {str(e)}", "ERROR")
            QMessageBox.warning(self, "Calculation Error", f"Failed to apply emissivity correction: {str(e)}")
    
    def apply_temp_drop_correction(self):
        """Apply temperature drop correction using the cavity geometry formula"""
        try:
            # Get all parameters
            theta_deg = float(self.theta_edit.text())  # degrees
            emissivity_td = float(self.emis_td_edit.text())  # dimensionless
            sigma = float(self.sigma_edit.text())  # W m⁻² K⁻⁴
            d = float(self.d_edit.text())  # mm (backwall thickness)
            k = float(self.k_edit.text())  # W/(mK) (thermal conductivity)
            r = float(self.r_edit.text())  # mm (aperture radius)
            L = float(self.L_edit.text())  # mm (cavity length)
            
            # Convert theta to radians
            theta_rad = np.deg2rad(theta_deg)
            
            # Convert mm to m for calculation
            d_m = d / 1000.0
            r_m = r / 1000.0
            L_m = L / 1000.0
            
            # Check if we have emissivity corrected temperature
            if hasattr(self, 'emissivity_corrected_temp'):
                base_temp = self.emissivity_corrected_temp
                temp_source = "Emissivity Corrected Temperature"
            else:
                # Use measured temperature from SSE page
                base_temp = float(self.sse_temp_edit.text())
                temp_source = "Measured Temperature"
            
            # Calculate temperature drop using the formula:
            # ΔT = (cos(θ) * emissivity * σ * d / k) * (r / L)² * T⁴
            delta_t = (np.cos(theta_rad) * emissivity_td * sigma * d_m / k) * (r_m / L_m)**2 * base_temp**4
            
            # Corrected temperature accounting for the drop
            corrected_temp = base_temp - delta_t  # Subtract because it's a temperature drop
            
            # Get wavelength and c2 for signal recalculation
            wavelength = float(self.sse_wavelength_edit.text())
            c2 = float(self.sse_c2_edit.text())
            
            # Get base signal - prioritize emissivity correction input field
            if hasattr(self, 'emissivity_corrected_signal'):
                base_signal = self.emissivity_corrected_signal
                signal_source = "Emissivity Corrected Signal"
            else:
                # Try to get from emissivity signal input field
                try:
                    base_signal = float(self.emiss_signal_input.text())
                    signal_source = "Emissivity Input Signal"
                except (ValueError, AttributeError):
                    # Fallback: Extract sc from SSE label
                    sc_text = self.sse_sc_label.text().split(': ')[1] if ': ' in self.sse_sc_label.text() else None
                    if not sc_text or sc_text == '-':
                        QMessageBox.warning(self, "Warning", "Please enter a signal value or calculate SSE correction first!")
                        return
                    base_signal = float(sc_text)
                    signal_source = "SSE Corrected Signal"
            
            # Recalculate signal at corrected temperature using Wien's approximation
            temp_drop_corrected_signal = base_signal * np.exp(
                (c2 / wavelength) * (1 / base_temp - 1 / corrected_temp)
            )
            
            # Display results
            self.temp_drop_corrected_label.setText(
                f"Calculated ΔT (drop): {delta_t:.4f} K\n"
                f"Corrected Temperature: {corrected_temp:.2f} K\n"
                f"Temperature Drop Corrected Signal: {temp_drop_corrected_signal:.6e}"
            )
            
            # Store for potential further use
            self.temp_drop_corrected_signal = temp_drop_corrected_signal
            self.corrected_temperature = corrected_temp
            self.calculated_delta_t = delta_t
            
            self._log(f"Temperature drop correction applied: ΔT = {delta_t:.4f} K", "SUCCESS")
            
        except ValueError:
            self._log("Temperature drop correction error: Invalid input", "ERROR")
            QMessageBox.warning(self, "Input Error", "Please enter valid numeric values!")
        except Exception as e:
            self._log(f"Temperature drop correction error: {str(e)}", "ERROR")
            QMessageBox.warning(self, "Calculation Error", f"Failed to apply temperature drop correction: {str(e)}")
    
    def set_theme(self, theme_name):
        """Update theme for all plot canvases"""
        self.theme_name = theme_name
        if hasattr(self, 'canvas_linearity'):
            self.canvas_linearity.set_theme(theme_name)
        if hasattr(self, 'sse_canvas_fit'):
            self.sse_canvas_fit.set_theme(theme_name)
        if hasattr(self, 'sse_canvas_scan'):
            self.sse_canvas_scan.set_theme(theme_name)

    def detect_and_extract_columns(self, df: pd.DataFrame, use_dark: bool):
        """Detect and extract S1, S2, S12 columns from DataFrame"""
        cols = {c.lower(): c for c in df.columns}
        dark = df[cols["dark"]].to_numpy(float) if use_dark and "dark" in cols else None

        if {"s1","s2","s12"}.issubset(cols):
            S1, S2, S12 = df[cols["s1"]], df[cols["s2"]], df[cols["s12"]]
            schema = "NPL S1/S2/S12"
        elif {"i1","i2"}.issubset(cols) and ("i1+i2_meas".lower() in cols or "imeas" in cols):
            S1, S2 = df[cols["i1"]], df[cols["i2"]]
            key = "i1+i2_meas".lower() if "i1+i2_meas".lower() in cols else "imeas"
            S12 = df[cols[key]]
            schema = "Two-lamp (I1/I2/Imeas→S1/S2/S12)"
        else:
            raise ValueError("CSV must include either (S1,S2,S12) or (I1,I2,Imeas).")

        S1, S2, S12 = map(lambda x: x.to_numpy(float), (S1, S2, S12))
        if dark is not None:
            S1, S2, S12 = S1-dark, S2-dark, S12-dark
        return S1, S2, S12, schema

    def compute_nl(self, S1, S2, S12):
        """Compute non-linearity factor NL = (S1+S2)/S12"""
        eps = np.finfo(float).tiny
        S12 = np.where(np.abs(S12) < eps, eps, S12)
        return (S1+S2)/S12

    def cumulative_preceding(self, NL):
        """Compute cumulative correction factor from NL array"""
        C = np.ones_like(NL)
        for k in range(1, len(NL)):
            C[k] = C[k-1] * NL[k-1]
        return C

    def interp_linear(self, x, xp, fp):
        """Linear interpolation helper"""
        if x <= xp[0]: return fp[0]
        if x >= xp[-1]: return fp[-1]
        i = np.searchsorted(xp, x) - 1
        t = (x - xp[i])/(xp[i+1]-xp[i])
        return fp[i] + t*(fp[i+1]-fp[i])

    def create_linearity_tab(self):
        """NPL Radiance-Doubling (Preceding-Product Correction) Tab"""
        widget = QWidget()
        root = QVBoxLayout()
        
        # Initialize linearity data storage
        self.linearity_df = None
        self.S12_sorted = None
        self.Ccum_sorted = None
        
        # Controls
        top = QHBoxLayout()
        self.btn_lin_load = QPushButton("📁 Load txt/csv")
        self.btn_lin_load.clicked.connect(self.load_linearity_csv)
        self.chk_lin_dark = QCheckBox("Apply 'dark' column")
        self.chk_lin_dark.setChecked(True)
        self.btn_lin_compute = QPushButton("🔍 Compute")
        self.btn_lin_compute.clicked.connect(self.compute_linearity_all)
        top.addWidget(self.btn_lin_load)
        top.addWidget(self.chk_lin_dark)
        top.addWidget(self.btn_lin_compute)
        top.addStretch(1)
        root.addLayout(top)
        
        # Tabs for NL and Cumulative Correction plots
        self.linearity_tabs = QTabWidget()
        
        # Non-linearity plot tab
        w1 = QWidget()
        l1 = QVBoxLayout(w1)
        self.canvas_NL = PlotCanvas("Non-linearity NL", theme_name=self.theme_name)
        l1.addWidget(self.canvas_NL)
        
        # Cumulative correction plot tab
        w2 = QWidget()
        l2 = QVBoxLayout(w2)
        self.canvas_C = PlotCanvas("Cumulative Correction", theme_name=self.theme_name)
        l2.addWidget(self.canvas_C)
        
        self.linearity_tabs.addTab(w1, "Non-linearity")
        self.linearity_tabs.addTab(w2, "Cumulative Correction")
        root.addWidget(self.linearity_tabs, stretch=1)
        
        # Bottom section
        bottom = QHBoxLayout()
        root.addLayout(bottom)
        
        # Summary box
        box_sum = QGroupBox("Summary")
        fsum = QFormLayout(box_sum)
        self.lbl_lin_schema = QLabel("-")
        self.lbl_lin_points = QLabel("-")
        self.lbl_lin_minmaxS = QLabel("-")
        self.lbl_lin_minmaxNL = QLabel("-")
        self.lbl_lin_minmaxC = QLabel("-")
        fsum.addRow("Schema:", self.lbl_lin_schema)
        fsum.addRow("Points:", self.lbl_lin_points)
        fsum.addRow("S min/max:", self.lbl_lin_minmaxS)
        fsum.addRow("NL min/max:", self.lbl_lin_minmaxNL)
        fsum.addRow("C min/max:", self.lbl_lin_minmaxC)
        
        # Calculator box
        box_calc = QGroupBox("Calculator")
        fcal = QFormLayout(box_calc)
        self.le_lin_S = QLineEdit()
        self.le_lin_S.setPlaceholderText("Enter S")
        self.le_lin_S.textChanged.connect(self.update_linearity_calc)
        self.le_lin_C = QLineEdit()
        self.le_lin_Scorr = QLineEdit()
        for le in (self.le_lin_C, self.le_lin_Scorr):
            le.setReadOnly(True)
        fcal.addRow("Raw S:", self.le_lin_S)
        fcal.addRow("Ccum(S):", self.le_lin_C)
        fcal.addRow("S_corr:", self.le_lin_Scorr)
        
        bottom.addWidget(box_sum)
        bottom.addWidget(box_calc)
        
        widget.setLayout(root)
        return widget
    
    def load_linearity_csv(self):
        """Load linearity data from CSV file"""
        path, _ = QFileDialog.getOpenFileName(
            self, 'Open file', '', 'Data files (*.txt *.csv);;All files (*)'
        )
        if not path:
            return
        try:
            self.linearity_df = pd.read_csv(path)
            QMessageBox.information(self, "Loaded", f"Loaded {len(self.linearity_df)} rows.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load file:\n{str(e)}")
    
    def compute_linearity_all(self):
        """Compute linearity correction from loaded data"""
        if self.linearity_df is None:
            QMessageBox.warning(self, "Warning", "Please load data first.")
            return
        
        try:
            S1, S2, S12, schema = self.detect_and_extract_columns(
                self.linearity_df, self.chk_lin_dark.isChecked()
            )
            NL = self.compute_nl(S1, S2, S12)
            
            # Sort by S12
            idx = np.argsort(S12)
            S12, NL = S12[idx], NL[idx]
            C = self.cumulative_preceding(NL)
            
            # Update summary labels
            self.lbl_lin_schema.setText(schema)
            self.lbl_lin_points.setText(str(len(S12)))
            self.lbl_lin_minmaxS.setText(f"{S12.min():.4g} / {S12.max():.4g}")
            self.lbl_lin_minmaxNL.setText(f"{NL.min():.4g} / {NL.max():.4g}")
            self.lbl_lin_minmaxC.setText(f"{C.min():.4g} / {C.max():.4g}")
            
            # Store sorted data for calculator
            self.S12_sorted, self.Ccum_sorted = S12, C
            
            # Plot NL
            self.canvas_NL.ax.clear()
            self.canvas_NL.ax.plot(S12, NL, marker="o")
            self.canvas_NL.ax.set_xscale("log")
            self.canvas_NL.ax.set_title("Non-linearity NL")
            self.canvas_NL.ax.set_xlabel("S(1+2) (A)")
            self.canvas_NL.ax.set_ylabel("Non-linearity")
            self.canvas_NL.ax.grid(True, alpha=0.3)
            self.canvas_NL.ax.yaxis.set_major_formatter(FuncFormatter(lambda x, pos: f'{x:.4f}'))
            self.canvas_NL.draw()
            
            # Plot C
            self.canvas_C.ax.clear()
            self.canvas_C.ax.plot(S12, C, marker="o")
            self.canvas_C.ax.set_xscale("log")
            self.canvas_C.ax.set_title("Cumulative Correction")
            self.canvas_C.ax.set_xlabel("S(1+2) (A)")
            self.canvas_C.ax.set_ylabel("Non-linearity Correction Factor")
            self.canvas_C.ax.grid(True, alpha=0.3)
            self.canvas_C.ax.yaxis.set_major_formatter(FuncFormatter(lambda x, pos: f'{x:.4f}'))
            self.canvas_C.draw()
            
            self.update_linearity_calc()
            
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))
    
    def update_linearity_calc(self):
        """Update linearity calculator with interpolated correction"""
        if self.linearity_df is None or not hasattr(self, 'S12_sorted'):
            return
        try:
            S = float(self.le_lin_S.text())
        except ValueError:
            return
        
        C = self.interp_linear(S, self.S12_sorted, self.Ccum_sorted)
        self.le_lin_C.setText(f"{C:.6f}")
        self.le_lin_Scorr.setText(f"{S*C:.6g}")

    def create_wavelength_tab(self):
        widget = QWidget()
        layout = QVBoxLayout()
        
        # Parameters
        params_box = QGroupBox("Wavelength Correction Parameters")
        params_layout = QFormLayout()
        
        sb_center = QDoubleSpinBox()
        sb_center.setRange(200, 2500)
        sb_center.setValue(650)
        sb_center.setSuffix(" nm")
        params_layout.addRow("Center Wavelength:", sb_center)
        
        sb_width = QDoubleSpinBox()
        sb_width.setRange(1, 500)
        sb_width.setValue(50)
        sb_width.setSuffix(" nm")
        params_layout.addRow("Bandwidth:", sb_width)
        
        sb_correction = QDoubleSpinBox()
        sb_correction.setRange(-10, 10)
        sb_correction.setValue(0)
        sb_correction.setSuffix(" %")
        params_layout.addRow("Correction Factor:", sb_correction)
        
        params_box.setLayout(params_layout)
        layout.addWidget(params_box)
        
        # Apply button
        btn_apply = QPushButton("✓ Apply Correction")
        layout.addWidget(btn_apply)
        
        layout.addStretch()
        
        widget.setLayout(layout)
        return widget
    
    def create_sse_tab(self):
        """Size-of-Source Effect Correction tab with sub-tabs"""
        widget = QWidget()
        main_layout = QVBoxLayout()
        
        # Initialize SSE data storage
        self.sse_x_data = None
        self.sse_y_data = None
        self.sse_scan_x = None
        self.sse_scan_y = None
        self.sse_fit_func = None
        self.sse_fit_params = None
        
        # Create sub-tabs
        sse_tabs = QTabWidget()
        
        # Fitting tab
        fitting_tab = self.create_sse_fitting_tab()
        sse_tabs.addTab(fitting_tab, "📊 Fitting")
        
        # Analysis tab
        analysis_tab = self.create_sse_analysis_tab()
        sse_tabs.addTab(analysis_tab, "🔬 Analysis")
        
        main_layout.addWidget(sse_tabs)
        widget.setLayout(main_layout)
        
        return widget
    
    def create_sse_fitting_tab(self):
        """SSE Fitting sub-tab"""
        widget = QWidget()
        layout = QHBoxLayout()
        
        # Left panel - Controls
        left_panel = QVBoxLayout()
        
        # Upload data
        upload_box = QGroupBox("📁 Data Management")
        upload_layout = QVBoxLayout()
        
        btn_upload_fit_data = QPushButton("Upload Fit Data (TXT/CSV)")
        btn_upload_fit_data.clicked.connect(self.sse_upload_fit_data)
        upload_layout.addWidget(btn_upload_fit_data)
        
        upload_box.setLayout(upload_layout)
        left_panel.addWidget(upload_box)
        
        # Fit type section
        fit_box = QGroupBox("📊 Fitting Options")
        fit_layout = QVBoxLayout()
        
        fit_type_layout = QHBoxLayout()
        fit_type_layout.addWidget(QLabel("Fit Type:"))
        self.sse_fit_type_combo = QComboBox()
        self.sse_fit_type_combo.addItems(["Polynomial", "Exponential", "Logarithmic", "Power", "Two-term Exponential", "Custom Equation"])
        self.sse_fit_type_combo.currentTextChanged.connect(self.sse_toggle_custom_equation)
        fit_type_layout.addWidget(self.sse_fit_type_combo)
        fit_layout.addLayout(fit_type_layout)
        
        # Custom equation input (initially hidden)
        self.sse_custom_eq_widget = QWidget()
        custom_eq_layout = QVBoxLayout()
        custom_eq_layout.setContentsMargins(0, 0, 0, 0)
        
        eq_label = QLabel("Equation (use 'x' as variable):")
        custom_eq_layout.addWidget(eq_label)
        
        self.sse_custom_eq_edit = QLineEdit()
        self.sse_custom_eq_edit.setPlaceholderText("e.g., a*x**2 + b*x + c or a*np.exp(-b*x) + c")
        custom_eq_layout.addWidget(self.sse_custom_eq_edit)
        
        param_label = QLabel("Parameters (comma-separated):")
        custom_eq_layout.addWidget(param_label)
        
        self.sse_custom_params_edit = QLineEdit()
        self.sse_custom_params_edit.setPlaceholderText("e.g., a, b, c")
        custom_eq_layout.addWidget(self.sse_custom_params_edit)
        
        guess_label = QLabel("Initial Guesses (comma-separated):")
        custom_eq_layout.addWidget(guess_label)
        
        self.sse_custom_guess_edit = QLineEdit()
        self.sse_custom_guess_edit.setPlaceholderText("e.g., 1.0, 1.0, 0.0")
        custom_eq_layout.addWidget(self.sse_custom_guess_edit)
        
        self.sse_custom_eq_widget.setLayout(custom_eq_layout)
        self.sse_custom_eq_widget.setVisible(False)
        fit_layout.addWidget(self.sse_custom_eq_widget)
        
        self.btn_sse_fit = QPushButton("🔬 Fit Data")
        self.btn_sse_fit.clicked.connect(self.sse_fit_data)
        self.btn_sse_fit.setEnabled(False)
        fit_layout.addWidget(self.btn_sse_fit)
        
        fit_box.setLayout(fit_layout)
        left_panel.addWidget(fit_box)
        
        # Fit equation display
        equation_box = QGroupBox("📐 Fitted Equation")
        equation_layout = QVBoxLayout()
        
        self.sse_equation_label = QLabel("y = ?")
        self.sse_equation_label.setWordWrap(True)
        self.sse_equation_label.setStyleSheet("font-size: 12pt; font-weight: bold;")
        equation_layout.addWidget(self.sse_equation_label)
        
        equation_box.setLayout(equation_layout)
        left_panel.addWidget(equation_box)
        
        # Fit parameters display
        params_box = QGroupBox("📊 Parameters")
        params_layout = QVBoxLayout()
        
        self.sse_params_label = QLabel("-")
        self.sse_params_label.setWordWrap(True)
        self.sse_params_label.setStyleSheet("font-family: 'Courier New', monospace;")
        params_layout.addWidget(self.sse_params_label)
        
        params_box.setLayout(params_layout)
        left_panel.addWidget(params_box)
        
        # Fit quality display
        quality_box = QGroupBox("📈 Fit Quality")
        quality_layout = QVBoxLayout()
        
        self.sse_fit_result_label = QLabel("R² = -")
        self.sse_fit_result_label.setWordWrap(True)
        quality_layout.addWidget(self.sse_fit_result_label)
        
        quality_box.setLayout(quality_layout)
        left_panel.addWidget(quality_box)
        
        left_panel.addStretch()
        
        # Right panel - Fit plot
        right_panel = QVBoxLayout()
        self.sse_canvas_fit = PlotCanvas("SSE Fit Data", theme_name=self.theme_name)
        right_panel.addWidget(self.sse_canvas_fit)
        
        # Add panels to layout
        layout.addLayout(left_panel, 1)
        layout.addLayout(right_panel, 2)
        
        widget.setLayout(layout)
        return widget
    
    def create_sse_analysis_tab(self):
        """SSE Analysis sub-tab - Compact layout"""
        widget = QWidget()
        layout = QHBoxLayout()
        
        # Left panel - Parameters and Controls
        left_panel = QVBoxLayout()
        
        # Upload and measurement in one box
        data_box = QGroupBox("📁 Data & Measurement")
        data_layout = QVBoxLayout()
        
        btn_upload_scan_data = QPushButton("Upload Scan Data")
        btn_upload_scan_data.clicked.connect(self.sse_upload_scan_data)
        data_layout.addWidget(btn_upload_scan_data)
        
        # Measurement parameters - 2x2 grid so all fields share equal width
        LABEL_STYLE = "font-size: 9pt;"
        meas_grid = QGridLayout()
        meas_grid.setVerticalSpacing(5)
        meas_grid.setHorizontalSpacing(8)
        meas_grid.setColumnStretch(0, 1)
        meas_grid.setColumnStretch(1, 1)

        # Row 0: Signal (left) | Temp (right)
        col0 = QVBoxLayout()
        col0.setSpacing(2)
        lbl_sig = QLabel("Signal:")
        lbl_sig.setStyleSheet(LABEL_STYLE)
        col0.addWidget(lbl_sig)
        self.sse_signal_edit = QLineEdit("2.0866e-6")
        self.sse_signal_edit.textEdited.connect(self.sse_on_manual_edit)
        col0.addWidget(self.sse_signal_edit)
        meas_grid.addLayout(col0, 0, 0)

        col1 = QVBoxLayout()
        col1.setSpacing(2)
        lbl_temp = QLabel("Temp (K):")
        lbl_temp.setStyleSheet(LABEL_STYLE)
        col1.addWidget(lbl_temp)
        self.sse_temp_edit = QLineEdit("3020.46")
        self.sse_temp_edit.textEdited.connect(self.sse_on_manual_edit)
        col1.addWidget(self.sse_temp_edit)
        meas_grid.addLayout(col1, 0, 1)

        # Row 1: λ (left) | Preset+🔄 (right)
        col2 = QVBoxLayout()
        col2.setSpacing(2)
        lbl_wl = QLabel("λ (μm):")
        lbl_wl.setStyleSheet(LABEL_STYLE)
        col2.addWidget(lbl_wl)
        self.sse_wavelength_edit = QLineEdit("0.65")
        col2.addWidget(self.sse_wavelength_edit)
        meas_grid.addLayout(col2, 1, 0)

        col3 = QVBoxLayout()
        col3.setSpacing(2)
        lbl_preset = QLabel("Preset:")
        lbl_preset.setStyleSheet(LABEL_STYLE)
        col3.addWidget(lbl_preset)
        preset_row = QHBoxLayout()
        preset_row.setSpacing(4)
        self.sse_preset_combo = QComboBox()
        self.sse_preset_combo.addItem("Custom Input")
        self.sse_preset_combo.currentIndexChanged.connect(self.sse_on_preset_changed)
        preset_row.addWidget(self.sse_preset_combo)
        self.btn_refresh_presets = QPushButton("↻")
        self.btn_refresh_presets.setToolTip("Refresh presets from Scale Realization fixed points")
        self.btn_refresh_presets.setFixedSize(30, 30)
        self.btn_refresh_presets.setStyleSheet("font-size: 12px; padding: 0px;")
        self.btn_refresh_presets.clicked.connect(self.sse_refresh_presets)
        preset_row.addWidget(self.btn_refresh_presets)
        col3.addLayout(preset_row)
        meas_grid.addLayout(col3, 1, 1)

        data_layout.addLayout(meas_grid)
        data_box.setLayout(data_layout)
        left_panel.addWidget(data_box)
        
        # Geometry and mode in one compact box
        geom_box = QGroupBox("📏 Geometry")
        geom_layout = QFormLayout()
        geom_layout.setVerticalSpacing(5)
        
        self.sse_mode_combo = QComboBox()
        self.sse_mode_combo.addItems(["Target > BB", "Target ≤ BB"])
        self.sse_mode_combo.currentIndexChanged.connect(self.sse_reset_cache)
        geom_layout.addRow("Mode:", self.sse_mode_combo)
        
        self.sse_cavity_edit = QLineEdit("3")
        self.sse_cavity_edit.textChanged.connect(self.sse_reset_cache)
        self.sse_cavity_edit.textChanged.connect(self.sse_update_mode)
        geom_layout.addRow("BB (mm):", self.sse_cavity_edit)
        
        self.sse_target_edit = QLineEdit("3")
        self.sse_target_edit.textChanged.connect(self.sse_reset_cache)
        self.sse_target_edit.textChanged.connect(self.sse_update_mode)
        geom_layout.addRow("Target (mm):", self.sse_target_edit)
        
        self.sse_furnace_edit = QLineEdit("100")
        self.sse_furnace_edit.textChanged.connect(self.sse_reset_cache)
        geom_layout.addRow("Furnace (mm):", self.sse_furnace_edit)
        
        geom_box.setLayout(geom_layout)
        left_panel.addWidget(geom_box)
        
        # Sakuma-Hattori in 2x2 grid for compactness
        sh_box = QGroupBox("🧮 Sakuma-Hattori")
        sh_layout = QGridLayout()
        sh_layout.setVerticalSpacing(5)
        sh_layout.setHorizontalSpacing(5)
        
        sh_layout.addWidget(QLabel("a:"), 0, 0)
        self.sse_a_edit = QLineEdit("0.649976")
        sh_layout.addWidget(self.sse_a_edit, 0, 1)
        
        sh_layout.addWidget(QLabel("b:"), 0, 2)
        self.sse_b_edit = QLineEdit("0.937109")
        sh_layout.addWidget(self.sse_b_edit, 0, 3)
        
        sh_layout.addWidget(QLabel("c:"), 1, 0)
        self.sse_c_edit = QLineEdit("0.00316573")
        sh_layout.addWidget(self.sse_c_edit, 1, 1)
        
        sh_layout.addWidget(QLabel("c2:"), 1, 2)
        self.sse_c2_edit = QLineEdit("14387.7687")
        sh_layout.addWidget(self.sse_c2_edit, 1, 3)
        
        sh_box.setLayout(sh_layout)
        left_panel.addWidget(sh_box)
        
        # Calculation buttons (horizontal layout)
        btn_layout = QHBoxLayout()
        
        btn_calc_temp = QPushButton("Calc T")
        btn_calc_temp.clicked.connect(self.sse_calculate_temperature)
        btn_calc_temp.setToolTip("Calculate Temperature from Signal")
        btn_layout.addWidget(btn_calc_temp)
        
        btn_calc_signal = QPushButton("Calc S")
        btn_calc_signal.clicked.connect(self.sse_calculate_signal)
        btn_calc_signal.setToolTip("Calculate Signal from Temperature")
        btn_layout.addWidget(btn_calc_signal)
        
        btn_calc_sse = QPushButton("SSE Corr")
        btn_calc_sse.clicked.connect(self.sse_calculate_sse_correction)
        btn_calc_sse.setToolTip("Calculate SSE Correction (ΔT and S_c)")
        btn_layout.addWidget(btn_calc_sse)
        
        left_panel.addLayout(btn_layout)
        
        # Results - compact format
        results_box = QGroupBox("📊 Results")
        results_layout = QFormLayout()
        results_layout.setVerticalSpacing(3)
        
        self.sse_temp_result_label = QLabel("-")
        results_layout.addRow("T calc:", self.sse_temp_result_label)
        
        self.sse_signal_result_label = QLabel("-")
        results_layout.addRow("S calc:", self.sse_signal_result_label)
        
        self.sse_delta_t_label = QLabel("-")
        results_layout.addRow("ΔT:", self.sse_delta_t_label)
        
        self.sse_sc_label = QLabel("-")
        results_layout.addRow("S_c:", self.sse_sc_label)
        
        results_box.setLayout(results_layout)
        left_panel.addWidget(results_box)
        
        left_panel.addStretch()
        
        # Right panel - Scan plot
        right_panel = QVBoxLayout()
        self.sse_canvas_scan = PlotCanvas("Scan Result", theme_name=self.theme_name)
        right_panel.addWidget(self.sse_canvas_scan)
        
        # Add panels to layout
        layout.addLayout(left_panel, 1)
        layout.addLayout(right_panel, 2)
        
        widget.setLayout(layout)
        return widget
    
    def create_emissivity_tab(self):
        """Combined Emissivity & Temperature Drop Correction tab"""
        widget = QWidget()
        layout = QHBoxLayout()
        
        # Left panel - Parameters
        left_panel = QVBoxLayout()
        
        # Emissivity Correction Parameters
        emiss_box = QGroupBox("📐 Emissivity Correction")
        emiss_layout = QFormLayout()
        
        self.emiss_signal_edit = QLineEdit("2.0866e-6")
        emiss_layout.addRow("Input Signal:", self.emiss_signal_edit)
        
        self.emiss_emissivity_edit = QLineEdit("0.95")
        emiss_layout.addRow("Emissivity (ελ):", self.emiss_emissivity_edit)
        
        self.emiss_ambient_temp_edit = QLineEdit("300")
        emiss_layout.addRow("Ambient Temp (K):", self.emiss_ambient_temp_edit)
        
        emiss_box.setLayout(emiss_layout)
        left_panel.addWidget(emiss_box)
        
        # Apply emissivity button
        btn_apply_emiss = QPushButton("Apply Emissivity Correction")
        btn_apply_emiss.clicked.connect(self.apply_emissivity_correction)
        left_panel.addWidget(btn_apply_emiss)
        
        # Emissivity results
        emiss_result_box = QGroupBox("Emissivity Results")
        emiss_result_layout = QVBoxLayout()
        
        self.emissivity_corrected_label = QLabel("T_obj: -\nΔT: -\nCorrected Signal: -")
        self.emissivity_corrected_label.setWordWrap(True)
        emiss_result_layout.addWidget(self.emissivity_corrected_label)
        
        emiss_result_box.setLayout(emiss_result_layout)
        left_panel.addWidget(emiss_result_box)
        
        # Temperature Drop Correction Parameters
        temp_drop_box = QGroupBox("🌡️ Temperature Drop Correction")
        temp_drop_layout = QFormLayout()
        
        self.theta_edit = QLineEdit("0")
        temp_drop_layout.addRow("θ (Tilt Angle, deg):", self.theta_edit)
        
        self.emis_td_edit = QLineEdit("0.95")
        temp_drop_layout.addRow("Emissivity:", self.emis_td_edit)
        
        self.sigma_edit = QLineEdit("5.6704e-8")
        temp_drop_layout.addRow("σ (W m⁻² K⁻⁴):", self.sigma_edit)
        
        self.d_edit = QLineEdit("5")
        temp_drop_layout.addRow("d (Backwall, mm):", self.d_edit)
        
        self.k_edit = QLineEdit("4300")
        temp_drop_layout.addRow("k (W/(m·K)):", self.k_edit)
        
        self.r_edit = QLineEdit("3")
        temp_drop_layout.addRow("r (Aperture, mm):", self.r_edit)
        
        self.L_edit = QLineEdit("40")
        temp_drop_layout.addRow("L (Cavity, mm):", self.L_edit)
        
        temp_drop_box.setLayout(temp_drop_layout)
        left_panel.addWidget(temp_drop_box)
        
        # Apply temperature drop button
        btn_apply_temp_drop = QPushButton("Apply Temperature Drop Correction")
        btn_apply_temp_drop.clicked.connect(self.apply_temp_drop_correction)
        left_panel.addWidget(btn_apply_temp_drop)
        
        # Temperature drop results
        temp_drop_result_box = QGroupBox("Temperature Drop Results")
        temp_drop_result_layout = QVBoxLayout()
        
        self.temp_drop_corrected_label = QLabel("ΔT (drop): -\nCorrected Temp: -\nCorrected Signal: -")
        self.temp_drop_corrected_label.setWordWrap(True)
        temp_drop_result_layout.addWidget(self.temp_drop_corrected_label)
        
        temp_drop_result_box.setLayout(temp_drop_result_layout)
        left_panel.addWidget(temp_drop_result_box)
        
        left_panel.addStretch()
        
        # Right panel - Info/Help
        right_panel = QVBoxLayout()
        
        info_box = QGroupBox("ℹ️ Information")
        info_layout = QVBoxLayout()
        
        info_text = QLabel(
            "<b>Emissivity Correction:</b><br>"
            "Corrects for non-unity emissivity using Planck's law.<br>"
            "Requires SSE corrected signal from Size-of-Source page.<br><br>"
            "<b>Temperature Drop Correction:</b><br>"
            "Corrects for temperature gradient in blackbody cavity.<br>"
            "Uses cavity geometry and thermal properties.<br><br>"
            "<b>Workflow:</b><br>"
            "1. Complete SSE correction first<br>"
            "2. Apply emissivity correction<br>"
            "3. Apply temperature drop correction"
        )
        info_text.setWordWrap(True)
        info_layout.addWidget(info_text)
        
        info_box.setLayout(info_layout)
        right_panel.addWidget(info_box)
        
        right_panel.addStretch()
        
        # Add panels to layout
        layout.addLayout(left_panel, 2)
        layout.addLayout(right_panel, 1)
        
        widget.setLayout(layout)
        return widget
    
    def create_temperature_drop_tab(self):
        """Temperature Drop Correction tab - now combined with emissivity"""
        # This method is kept for compatibility but returns the combined tab
        return self.create_emissivity_tab()

