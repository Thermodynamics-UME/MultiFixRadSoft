"""Calibration fitting and uncertainty calculation engine.

Orchestrates Sakuma-Hattori parameter estimation for 1 to N fixed points
and propagates measurement uncertainties through the calibration model.
"""

from __future__ import annotations

import logging
from typing import Any, Callable

import numpy as np
from numpy.typing import NDArray
from uncertainty import UncertaintyComponent
from UncertaintyFunctions import (
    build_wls_propagation_matrices,
    func_dic,
    sakuma_hattori_model_funcs,
)
from scipy import integrate
from scipy.optimize import fsolve, leastsq, curve_fit, least_squares


logger = logging.getLogger(__name__)


def _make_wls_sensitivity_fn(
    idx: int,
    P_y: NDArray,
    P_x: NDArray,
    model_funcs: dict,
    params: NDArray,
    *,
    use_lx: bool,
) -> Callable:
    """Vectorised sensitivity coeff using pre-computed P_y = C·H⁻¹, P_x = B·H⁻¹.

    H, C, B depend only on calibration data and are computed once.  For any
    array of in-use temperatures T the g vector is evaluated in batch:

        G[:,k] = -df_da(T_k) / df_dx(T_k)   shape (N, K)

    and the sensitivity is then a single matrix-vector multiply:

        lambda[idx, :] = P[idx, :] @ G        shape (K,)

    This avoids the Python loop over T that the old per-scalar approach used.

    Args:
        idx:        0-based calibration-point index.
        P_y:        C @ H^{-1}, shape (M, N) — pre-computed.
        P_x:        B @ H^{-1}, shape (M, N) — pre-computed.
        model_funcs: Dict from sakuma_hattori_model_funcs().
        params:     Fitted parameters [A1, A2, A3].
        use_lx:     True → temperature sensitivity (P_x); False → signal (P_y).

    Returns:
        A function f(T, *ignored) -> NDArray of shape (len(T),).
    """
    p_row = (P_x if use_lx else P_y)[idx, :]   # (N,) — captured once at creation

    def coeff(T: NDArray, *_: Any) -> NDArray:
        T_arr = np.asarray(T, dtype=float).ravel()           # (K,)
        # df_da returns (N, K) when passed a 1-D array
        df_da_T = np.asarray(model_funcs['df_da'](T_arr, params), dtype=float)   # (N, K)
        df_dx_T = np.asarray(model_funcs['df_dx'](T_arr, params), dtype=float)   # (K,)
        # g_j(T) = -(∂S/∂a_j) / (∂S/∂T) — inverse-problem gradient, shape (N, K)
        G = -df_da_T / df_dx_T[np.newaxis, :]
        return p_row @ G   # (N,) @ (N, K) = (K,)

    return coeff


class RunUncertainty:
    """Sakuma-Hattori calibration and uncertainty engine.

    Performs multi-fixed-point calibration fitting and computes
    temperature-dependent uncertainty budgets.

    Args:
        raw_data: List of fixed-point dictionaries from the uncertainty budget UI.
        sensor_wl: Sensor spectral wavelengths (nm).
        sensor_res: Sensor spectral response values.
    """

    def __init__(self, raw_data: list[dict[str, Any]], sensor_wl: list[float], sensor_res: list[float]) -> None:
        self.raw_data = raw_data
        self.lamda = 0
        self.lamda_unit = ""
        self.c2 = 0.014388
        self.a1 = 0
        self.a2 = 0
        self.a3 = 0
        self.sigma = 0
        self.sigma_unit = ""
        self.T = []
        self.T_units = []
        self.S = []
        self.S_units = []
        self.n = 0
        self.components = []
        self.fxp_names = []
        self.its90 = False
        self.labels = ["T"]
        self.c1 = 1.191156e-16
        self.sensor_wl = np.array(sensor_wl)*1e-9
        self.sensor_res = np.array(sensor_res)

        self.get_params()

    def get_label(self, its90=False):
        if its90 and self.n == 1:
            labels = self.labels.copy()
            labels.pop(4)
            return labels
        else:
            return self.labels

    def get_title(self):
        res = "/".join(self.fxp_names)
        if self.its90 and self.n == 1:
            res = "ITS90 " + res

        res = "(" + res + ")"
        return res

    def make_calibration(self, its90: bool = False, T_: NDArray = np.arange(1000, 3200)) -> tuple[list[NDArray], list[NDArray]]:
        """Fit Sakuma-Hattori parameters and return calibration curves.

        Args:
            its90: Whether to use ITS-90 scale mode (single fixed point only).
            T_: Temperature range for the output calibration curve.

        Returns:
            Tuple of ([T_range, T_data], [S_fitted, S_data]).
        """
        self.its90 = its90
        self.get_params(True)

        T = UncertaintyComponent.to_SI_Units(None, self.T, self.T_units)[0]
        # Convert datasets to numpy arrays (for safety)
        T_data = np.array(T, dtype=float)
        S_data = np.array(self.S, dtype=float)

        # Cache calibration arrays for WLS uncertainty propagation (n > 3)
        self.T_cal = T_data
        self.S_cal = S_data

        # --- HELPER: Logarithmic Residual Calculator ---
        # This function minimizes the Log(Signal) difference, not the Signal difference.
        # This equalizes the errors at low and high temperatures.
        def log_residuals(params, t_vals, s_vals):
            lam, a1, sig = params
            # Model sinyalini hesapla
            s_model = self.sakuma_hattori_expended(lam, sig, a1, t_vals)

            # Small epsilon to avoid negative or zero log errors
            s_model = np.maximum(s_model, 1e-50)
            s_vals = np.maximum(s_vals, 1e-50)

            return np.log(s_model) - np.log(s_vals)

        # --- HELPER: Initial Parameter Estimation (Wien Approximation) ---
        def estimate_initial_params(temps, signals):
            valid = signals > 0
            if np.sum(valid) < 2: return [1e-6, 1.0, 1e-8]

            x_reg = 1.0 / temps[valid]
            y_reg = np.log(signals[valid])
            slope, intercept = np.polyfit(x_reg, y_reg, 1)

            if abs(slope) < 1e-9: slope = -1
            lam_est = -self.c2 / slope
            a1_est = np.exp(intercept)
            sig_est = abs(lam_est * 0.02)  # Assuming 2% bandwidth

            # Clip to physical boundaries
            lam_est = np.clip(lam_est, 1e-7, 20e-6)

            return [lam_est, a1_est, sig_est]

        # --- N = 1 or N = 2 ---
        if self.n <= 2:
            a1_es = self.S[0] * self.c1 * integrate.simpson(self.sensor_res / self.sensor_wl ** 5, self.sensor_wl) / \
                integrate.simpson(self.sensor_res * self.planck_radiation(self.sensor_wl, T_data[0]),
                                  self.sensor_wl)
        
        if self.n == 1:
            logger.debug("--- N=1: Single Fixed Point ---")
            self.a1 = a1_es
            self.a2 = (1-6*((self.sigma/self.lamda)**2))*self.lamda*1e-9
            self.a3 = self.c2*((self.sigma/self.lamda)**2)/2
            if its90:
                self.a1 = self.S[0] * (np.exp(self.c2/(self.a2*T_data[0]+self.a3))-1)
                logger.debug("ITS-90 mode enabled")
            logger.debug("Fit: Lam=%.2fnm, A1=%.4e, Sig=%.2fnm", self.lamda, self.a1, self.sigma)
            logger.debug("Coeffs: A1=%.4e, A2=%.4e, A3=%.4e", self.a1, self.a2, self.a3)
        elif self.n == 2:
            logger.debug("--- N=2: Two Fixed Points ---")
            r_func = lambda x: [self.S[0] - self.sakuma_hattori_expended(x[0], self.sigma*1e-9, x[1], T_data[0]),
                                self.S[1] - self.sakuma_hattori_expended(x[0], self.sigma*1e-9, x[1], T_data[1])]
            logger.debug("Pre-fit: Lam=%.2fnm, A1=%.4e, Sig=%.2fnm", self.lamda, a1_es, self.sigma)
            (lam, self.a1) = fsolve(r_func, [self.lamda*1e-9, a1_es])
            logger.debug("Fit: Lam=%.2fnm, A1=%.4e", lam*1e9, self.a1)
            self.lamda = lam*1e9
            self.a2 = (1 - 6 * ((self.sigma / self.lamda) ** 2)) * self.lamda * 1e-9
            self.a3 = self.c2 * ((self.sigma / self.lamda) ** 2) / 2
            logger.debug("Coeffs: A1=%.4e, A2=%.4e, A3=%.4e", self.a1, self.a2, self.a3)
        # --- N = 3 (EXACT SOLUTION / LEAST SQUARES) ---
        # --- N >= 3 (Full Fit / Coefficients) ---
        elif self.n >= 3:
            logger.debug("--- N>=3 Full Fit (Coefficients) ---")
            
            # Initial guess strategy:
            # 1. Estimate Lambda, Sigma, A1 using simplified specific method
            # 2. Convert to A1, A2, A3
            # 3. Use these as initial guess for leastsq
            
            # Estimate physical params first
            params_est = estimate_initial_params(T_data, S_data)
            lam_est, a1_est, sig_est = params_est
            
            # Convert to coefficients (initial guess)
            # a1 = c (Amplitude)
            # a2 = a (Slope)
            # a3 = b (Intercept)
            
            c_guess = a1_est
            a_guess = (1 - 6 * ((sig_est / lam_est) ** 2)) * lam_est
            b_guess = self.c2 * ((sig_est / lam_est) ** 2) / 2
            
            # Note: RunUncertainty uses: a1(Amp), a2(Slope), a3(Intercept)
            p0 = [c_guess, a_guess, b_guess]
            
            logger.debug("Pre-fit guesses: A1=%.4e, A2=%.4e, A3=%.4e", c_guess, a_guess, b_guess)
            
            # Residual function for inverse fit: Minimize T_meas - T_calc
            # T = (c2 / log(a1/S + 1) - a3) / a2
            def residual_inverse(params, t_meas, s_meas):
                p_a1, p_a2, p_a3 = params
                
                 # Add validation to prevent log domain errors
                with np.errstate(invalid='ignore', divide='ignore'):
                     ratio = (p_a1 / s_meas) + 1
                     mask = ratio > 0
                     
                     residuals = np.zeros_like(t_meas)
                     
                     # Calculate T from S
                     # T = (c2 / ln(a1/S + 1) - a3) / a2
                     val_log = np.log(ratio[mask])
                     # Avoid division by zero if log is 0 (should correspond to ratio=1 -> S=inf?)
                     
                     t_calc = (self.c2 / val_log - p_a3) / p_a2
                     
                     residuals[mask] = t_meas[mask] - t_calc
                     
                     # Heavy penalty for invalid points
                     residuals[~mask] = 1e10
                     
                return residuals

            try:
                # Use leastsq (Levenberg-Marquardt)
                roots, flag = leastsq(residual_inverse, p0, args=(T_data, S_data), maxfev=10000)
                
                self.a1 = roots[0]
                self.a2 = roots[1]
                self.a3 = roots[2]
                
                # Back-calculate physical parameters for display (approximate)
                # A2 = lambda * (1 - ...)
                # A3 = c2 * ...
                # This inverse mapping is complex, but we can approximate lambda ~ A2
                # Or solve the system:
                # x = (sigma/lambda)^2
                # A3 = c2 * x / 2  => x = 2 * A3 / c2
                # A2 = lambda * (1 - 6x) => lambda = A2 / (1 - 6x)
                
                x_val = 2 * self.a3 / self.c2
                if 1 - 6 * x_val != 0:
                    self.lamda = (self.a2 / (1 - 6 * x_val)) * 1e9 # to nm
                    self.sigma = (self.lamda * 1e-9 * np.sqrt(x_val)) * 1e9 # to nm
                else:
                    self.lamda = 0
                    self.sigma = 0

                logger.debug("Fit Result (Flag %s):", flag)
                logger.debug("A1=%.4e, A2=%.4e, A3=%.4e", self.a1, self.a2, self.a3)
                logger.debug("Physical (Approx): Lam=%.2fnm, Sig=%.2fnm", self.lamda, self.sigma)

            except Exception as e:
                logger.error("N>=3 Fit Error: %s", e)
                # Fallback to initial guess
                self.a1, self.a2, self.a3 = p0

        # Convert the coefficients to Sakuma-Hattori form
        if self.n >= 3:  # Already calculated above for N=1,2
            self.a2 = (1 - 6 * ((self.sigma / self.lamda) ** 2)) * self.lamda * 1e-9
            self.a3 = self.c2 * ((self.sigma / self.lamda) ** 2) / 2

        logger.debug("Final Coeffs -> A1: %.4e, A2: %.4e, A3: %.4e", self.a1, self.a2, self.a3)

        self.get_components()
        return [T_, T], [self.sakuma_hattori_signal(T_), self.S]

    def planck_radiation(self, lam, T):
        return self.c1/(lam**5*(np.exp(self.c2/(lam*T))-1))

    def sakuma_hattori_signal(self, T: NDArray) -> NDArray:
        """Compute signal from temperature using fitted S-H coefficients."""
        return self.a1/(np.exp(self.c2/(self.a2*T + self.a3))-1)

    def sakuma_hattori(self, T, a1, a2, a3):
        return a1/np.exp(self.c2*1e6/(a2*T + a3))

    def inv_sakuma_hattor_signal(self, S: NDArray) -> NDArray:
        """Invert Sakuma-Hattori: compute temperature from signal."""
        S = np.array(S, dtype=float)
        return (self.c2/np.log(self.a1/S+1)-self.a3)/self.a2

    def inv_sakuma_hattori(self, a1, a2, a3, S):
        return (self.c2 / np.log(a1 / S + 1) - a3) / a2

    def sakuma_hattori_expended(self, lam, sig, a1, T):
        return a1/(np.exp(self.c2/(lam*(1-6*(sig/lam)**2)*T+.5*self.c2*(sig/lam)**2))-1)

    def calculate_sensor_params(self, wavelength, spectral_resp):
        lam = integrate.simpson(wavelength * spectral_resp, wavelength) / integrate.simpson(spectral_resp, wavelength)
        sig = (integrate.simpson((wavelength - lam) ** 2 * spectral_resp, wavelength) / integrate.simpson(spectral_resp,
                                                                                                          wavelength)) ** .5
        return lam, sig

    def get_detailed_uns(self, T):
        uns = []
        uns_val = []
        T = np.array(T)
        for comp in self.components:
            uns.append(comp.combined_uncertainties(T))
            uns_val.append("")
            uns.extend(np.abs(comp.components_uncertainties(T)))
            uns_val.extend(comp.get_componets_values_data())
        _, com_un = self.calculate_componets_un(T)
        uns_val.append("")
        uns.append(com_un[0])
        return uns, uns_val

    def get_components_names(self):
        comps_names = {}
        i = 0
        for fx in self.raw_data:
            if fx["IsFixedPoint"]:
                i += 1
                comps_names["T"+str(i)] = fx["Temperature_Un"]["Names"]
                comps_names["S"+str(i)] = fx["Signal_Un"]["Names"]
            else:
                comps_names[fx["Name"]] = fx["Temperature_Un"]["Names"]
        return comps_names

    def get_fixed_points(self):
        fixed_points = []
        for fx in self.raw_data:
            if fx["IsFixedPoint"]:
                fixed_points.append([fx["Name"], fx["Temperature"]])

        return fixed_points

    def get_params(self, update=False):
        self.n = 0
        self.T = []
        self.T_units = []
        self.S = []
        self.S_units = []
        self.labels = ["T"]
        self.fxp_names = []
        for fx in self.raw_data:
            if fx["IsFixedPoint"]:
                self.fxp_names.append(fx["Name"])
                self.T.append(fx["Temperature"])
                self.T_units.append(fx["Unit"])
                self.S.append(fx["Signal"])
                self.S_units.append("")
                self.n += 1
                self.labels.append("T"+str(self.n))
                self.labels.append("S"+str(self.n))
            else:
                if fx["Name"] == "MeanWavelength":
                    self.lamda = fx["Temperature"]
                    self.lamda_unit = fx["Unit"]
                    self.labels.append(r"$\lambda_0$")
                elif fx["Name"] == "Standard Deviation":
                    self.sigma = fx["Temperature"]
                    self.sigma_unit = fx["Unit"]
                    self.labels.append(r"$\sigma$")
                elif fx["Name"] == "In-Use Signal":
                    self.labels.append("$S_{in}$")
                else:
                    raise Exception("Unknown fixed point data")

        if self.n == 2:
            (self.lamda, self.sigma) = self.calculate_sensor_params(self.sensor_wl * 1e9, self.sensor_res)
            if not update:
                del self.raw_data[1]
            del self.labels[2]
        elif self.n >= 3:
            if not update:
                del self.raw_data[0]
            del self.labels[1]
        else:
            (self.lamda, self.sigma) = self.calculate_sensor_params(self.sensor_wl * 1e9, self.sensor_res)

    def get_components(self):
        self.components = []
        if self.n <= 2:
            params = [self.a1, self.c2, self.sigma*1e-9, self.lamda*1e-9, *self.T, *self.S]
            n_key = self.n
        else:
            params = [self.a1, self.c2, self.sigma * 1e-9, self.lamda * 1e-9, self.T, self.S]
            n_key = 3

        # --- WLS propagation machinery for overdetermined case (n > 3) ---
        # For n == 3 the fit is exact so Lagrange coefficients in func_dic[3] remain
        # correct.  For n > 3 the system is overdetermined (least-squares fit), and
        # Lagrange coefficients are invalid; we use the WLS propagation
        # instead, which accounts for the full Hessian of the calibration fit.
        wls_coeffs: dict[int, tuple[Callable, Callable]] = {}
        if self.n > 3:
            if hasattr(self, "T_cal") and hasattr(self, "S_cal"):
                fitted_params = np.array([self.a1, self.a2, self.a3])
                model_funcs = sakuma_hattori_model_funcs(self.c2)
                x_cal = np.asarray(self.T_cal, dtype=float)
                y_cal = np.asarray(self.S_cal, dtype=float)
                # Statistically optimal weights for the calibration fit:
                #
                #   w_i = 1 / [ u_yi^2 + (∂y/∂x|_{x_i} · u_xi)^2 ]
                #
                # where u_xi = combined standard uncertainty of T_i (K)
                #       u_yi = combined standard uncertainty of S_i (signal)
                #       ∂y/∂x = dS/dT at T_i  (projects T uncertainty to signal space)
                #
                # This is the maximum-likelihood weight when both the calibration
                # temperature and the measured signal have uncertainties.
                w = np.empty(self.n, dtype=float)
                fp_counter = 0
                for fx in self.raw_data:
                    if not fx["IsFixedPoint"]:
                        continue
                    T_i   = float(UncertaintyComponent.to_SI_Units(
                                None, [fx["Temperature"]], [fx["Unit"]])[0][0])
                    S_i   = float(fx["Signal"])

                    # --- u_T_i : RSS of temperature uncertainty components (K) ---
                    T_un_vals  = fx["Temperature_Un"]["Values"]
                    T_un_units = fx["Temperature_Un"]["Unit"]
                    T_si_vals, _ = UncertaintyComponent.to_SI_Units(
                        None, T_un_vals, T_un_units)
                    u_T_i = float(np.sqrt(sum(v ** 2 for v in T_si_vals))) if T_si_vals else 0.0

                    # --- u_S_i : RSS of signal uncertainty components (signal units) ---
                    S_un_vals  = fx["Signal_Un"]["Values"]
                    S_un_units = fx["Signal_Un"]["Unit"]
                    u_S_abs = []
                    for v, u in zip(S_un_vals, S_un_units):
                        if u in ("%", "% "):
                            u_S_abs.append(v * S_i / 100.0)
                        else:
                            conv, _ = UncertaintyComponent.to_SI_Units(None, [v], [u])
                            u_S_abs.append(float(conv[0]))
                    u_S_i = float(np.sqrt(sum(v ** 2 for v in u_S_abs))) if u_S_abs else 0.0

                    # --- ∂S/∂T at T_i ---
                    df_dx_i = model_funcs['df_dx'](T_i, fitted_params)

                    # --- eq. (8) ---
                    var_i = u_S_i ** 2 + (df_dx_i * u_T_i) ** 2
                    w[fp_counter] = 1.0 / max(var_i, 1e-300)
                    fp_counter += 1
                # Pre-compute P_y = C·H⁻¹ and P_x = B·H⁻¹ once from the
                # calibration data.  The vectorised coeff functions then use
                # P @ G(T) for the entire temperature array in one multiply.
                H, C, B = build_wls_propagation_matrices(
                    x_cal, y_cal, w, fitted_params, model_funcs
                )
                try:
                    H_inv = np.linalg.solve(H, np.eye(len(fitted_params)))
                except np.linalg.LinAlgError:
                    logger.warning("H singular; using lstsq for WLS inversion.")
                    H_inv, _, _, _ = np.linalg.lstsq(
                        H, np.eye(len(fitted_params)), rcond=None
                    )
                P_y = C @ H_inv   # (M, N)
                P_x = B @ H_inv   # (M, N)
                for fp_idx in range(self.n):
                    wls_coeffs[fp_idx] = (
                        _make_wls_sensitivity_fn(
                            fp_idx, P_y, P_x, model_funcs, fitted_params, use_lx=True
                        ),
                        _make_wls_sensitivity_fn(
                            fp_idx, P_y, P_x, model_funcs, fitted_params, use_lx=False
                        ),
                    )
                logger.debug(
                    "WLS sensitivity coefficients prepared for %d fixed points.", self.n
                )
            else:
                logger.warning(
                    "n=%d > 3 but calibration arrays not cached; "
                    "falling back to n=3 Lagrange coefficients.",
                    self.n,
                )

        i = 0
        for fx in self.raw_data:
            if not fx["IsFixedPoint"]:
                # Non-fixed-point components (MeanWavelength, StdDev, In-Use Signal):
                # the in-use signal sensitivity formula is identical across all n.
                un_comp = UncertaintyComponent(
                    fx["Temperature"], fx["Unit"], func_dic[n_key][fx["Name"]],
                    fx["Temperature_Un"], [*params, 0]
                )
                if fx["Name"] == "In-Use Signal":
                    un_comp.is_in_use_signal = True
                self.components.append(un_comp)
            else:
                i += 1
                if self.n < 3:
                    # n=1,2: individual Lagrange coefficients keyed by suffix
                    suffix = str(i)
                    T_coeff: Callable = func_dic[n_key]["T" + suffix]
                    S_coeff: Callable = func_dic[n_key]["S" + suffix]
                elif self.n == 3:
                    # n=3: exact fit — generic Lagrange coefficients
                    T_coeff = func_dic[3]["T"]
                    S_coeff = func_dic[3]["S"]
                else:
                    # n>3: overdetermined — use WLS coefficients
                    fp_idx = i - 1
                    if fp_idx in wls_coeffs:
                        T_coeff, S_coeff = wls_coeffs[fp_idx]
                    else:
                        # fallback if WLS setup failed
                        T_coeff = func_dic[3]["T"]
                        S_coeff = func_dic[3]["S"]

                un_comp = UncertaintyComponent(
                    fx["Temperature"], fx["Unit"], T_coeff,
                    fx["Temperature_Un"], [*params, i]
                )
                self.components.append(un_comp)
                un_comp = UncertaintyComponent(
                    fx["Signal"], "", S_coeff,
                    fx["Signal_Un"], [*params, i]
                )
                self.components.append(un_comp)

    def calculate_componets_un(self, T: NDArray = np.arange(1000, 3200), its90: bool = False) -> tuple[NDArray, list[NDArray]]:
        """Calculate combined and individual component uncertainties.

        Returns:
            Tuple of (T, [combined_uncertainty, *individual_uncertainties]).
        """
        uns = []
        components = self.components.copy()
        if its90 and self.n == 1:
            components.pop(3)
        for comp in components:
            un = comp.combined_uncertainties(T)
            uns.append(un)
        uns = np.array(uns)
        return T, [np.sqrt(np.sum(uns**2, axis=0)), *uns]


"""
    def make_calibration(self,its90=False, T_=np.arange(1000, 3200)):
        self.its90 = its90
        self.get_params(True)
        T = UncertaintyComponent.to_SI_Units(None, self.T, self.T_units)[0]

        if self.n <= 2:
            a1_es = self.S[0] * self.c1 * integrate.simpson(self.sensor_res / self.sensor_wl ** 5, self.sensor_wl) / \
                integrate.simpson(self.sensor_res * self.planck_radiation(self.sensor_wl, T[0]),
                                  self.sensor_wl)

        if self.n == 1:
            print("----------------------------------")
            self.a1 = a1_es
            self.a2 = (1-6*((self.sigma/self.lamda)**2))*self.lamda*1e-9
            self.a3 = self.c2*((self.sigma/self.lamda)**2)/2
            if its90:
                self.a1 = self.S[0] * (np.exp(self.c2/(self.a2*T[0]+self.a3))-1)
                print(its90)
            print("fit:", self.lamda*1e-9, a1_es, self.sigma*1e-9)
            print("Coeff", self.a1, self.a2, self.a3)
        elif self.n == 2:
            print("----------------------------------")
            r_func = lambda x: [self.S[0] - self.sakuma_hattori_expended(x[0], self.sigma*1e-9, x[1], T[0]),
                                self.S[1] - self.sakuma_hattori_expended(x[0], self.sigma*1e-9, x[1], T[1])]
            print("pre_fit", self.lamda*1e-9, a1_es, self.sigma*1e-9)
            (lam, self.a1) = fsolve(r_func, [self.lamda*1e-9, a1_es])
            print("fit:", lam, self.a1)
            self.lamda = lam*1e9
            self.a2 = (1 - 6 * ((self.sigma / self.lamda) ** 2)) * self.lamda * 1e-9
            self.a3 = self.c2 * ((self.sigma / self.lamda) ** 2) / 2
            print("Coeff", self.a1, self.a2, self.a3)
        elif self.n == 3:
            print("----------------------------------")
            r_func = lambda x: [self.S[0] - self.sakuma_hattori_expended(x[0], x[2], x[1], T[0]),
                               self.S[1] - self.sakuma_hattori_expended(x[0], x[2], x[1], T[1]),
                               self.S[2] - self.sakuma_hattori_expended(x[0], x[2], x[1], T[2])]
            #print("pre_fit", self.lamda * 1e-9, a1_es, self.sigma*1e-9)
            bounds = [(0, 1), (0, 1), (self.sigma *.5, self.sigma*1.5)]
            #(lam, self.a1, sig) = fsolve(r_func, [self.lamda*1e-9, a1_es, self.sigma*1e-9])
            (lam, self.a1, sig) = fsolve(r_func, [1e-7, 1e-3, 1e-9])
            print("fit:", lam, self.a1, sig)
            self.lamda = lam * 1e9
            self.sigma = sig * 1e9
            self.a2 = (1 - 6 * ((self.sigma / self.lamda) ** 2)) * self.lamda * 1e-9
            self.a3 = self.c2 * ((self.sigma / self.lamda) ** 2) / 2
            print("Coeff", self.a1, self.a2, self.a3)
        elif self.n > 3:
            def lsq_fun3(x, params):
                return ((1 / params[1]) * ((self.c2 / np.log((params[0] / x) + 1)) - params[2]))

            def residual2(coeff, y, x):
                return y - lsq_fun3(x, coeff)

            #a2 = (1 - 6 * ((self.sigma / self.lamda) ** 2)) * self.lamda * 1e-9
            #a3 = self.c2 * ((self.sigma / self.lamda) ** 2) / 2
            #x0 = [a1_es, a2, a3]
            print("Pre_fit:", *x0)
            roots, a = leastsq(residual2, x0 = [0.0001, 0.0001, 0.0001], args=(T, self.S))
            self.a3 = roots[2]
            self.a2 = roots[1]
            self.a1 = roots[0]
            print("Coeff", self.a1, self.a2, self.a3)
            print(a)
            self.lamda = self.a2 / (1 - 12 * self.a3 / self.c2) * 1e9
            self.sigma = self.lamda*np.sqrt(2*self.a1/self.c2)
            print("params:", self.a1, self.lamda, self.sigma)

        self.get_components()

        return [T_, T], [self.sakuma_hattori_signal(T_), self.S]
"""
