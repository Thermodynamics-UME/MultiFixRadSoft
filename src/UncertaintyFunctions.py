"""Sensitivity coefficient functions for Sakuma-Hattori radiation thermometry.

Provides the signal function (_Sin), Lagrange interpolation helpers (_T, _S),
and a dictionary of sensitivity coefficient lambdas (func_dic) used by the
uncertainty propagation engine.
"""

import logging

import numpy as np
from numpy.typing import NDArray

logger = logging.getLogger(__name__)


def _Sin(T: NDArray, a1: float, c2: float, sig: float, lam: float) -> NDArray:
    """Compute the Sakuma-Hattori signal function.

    Args:
        T: Temperature array (K).
        a1: Amplitude coefficient.
        c2: Second radiation constant (m·K).
        sig: Spectral bandwidth (m).
        lam: Mean wavelength (m).

    Returns:
        Signal values corresponding to the input temperatures.
    """
    r_1 = lam*(1-6*sig**2/lam**2)
    r_2 = T+c2*sig**2/(2*lam**2)

    try:
        res = a1 / (np.exp(c2 / (r_1 * r_2)) - 1)
    except (ZeroDivisionError, FloatingPointError, OverflowError) as e:
        logger.error("_Sin calculation error: r_1=%s, r_2=%s — %s", r_1, r_2, e)
        raise

    return res

def _T(T: NDArray, Ts: list[float], i: int) -> NDArray:
    """Lagrange basis product for temperature interpolation."""
    funcs = []
    Tss = Ts.copy()
    Tn = Tss.pop(i-1)
    for j, Ti in enumerate(Tss):
        funcs.append((T - Ti) / (Tn - Ti))
    funcs = np.array(funcs)

    def product_func(T):
        result = 1
        for func in funcs:
            result *= func(T)
        return result

    return np.prod(funcs, axis=0)


def _S(Ss: list[float], Ts: list[float], i: int):
    """Signal sensitivity coefficient via Lagrange interpolation."""
    return lambda T: _T(T, Ts, i)*Ts[i-1]**2/Ss[i-1]


func_dic = {1: {"MeanWavelength": lambda T, a1, c2, sig, lam, T1, S1, i: (1-T/T1)*T/lam,
                "Standard Deviation": lambda T, a1, c2, sig, lam, T1, S1, i: (1/T1-1/T)*(12-(1/T1+1/T)*c2/lam)*(np.power(T, 2)*sig)/np.power(lam, 2),
                "T1": lambda T, a1, c2, sig, lam, T1, S1, i: (T**2)/(T1**2),
                "S1": lambda T, a1, c2, sig, lam, T1, S1, i: (lam*T**2)/(c2*S1),
                "In-Use Signal": lambda T, a1, c2, sig, lam, T1, S1, i: (lam*T**2)/(c2*_Sin(T, a1, c2, sig, lam))},
            2: {"Standard Deviation": lambda T, a1, c2, sig, lam, T1, T2, S1, S2, i: (T-T1)*(T-T2)*c2*sig/(T1*T2*lam**3),
                "T1": lambda T, a1, c2, sig, lam, T1, T2, S1, S2, i: T*(T-T2)/(T1*(T1-T2)),
                "S1": lambda T, a1, c2, sig, lam, T1, T2, S1, S2, i: ((lam*T*T1)/(c2*S1))*((T-T2)/(T1-T2)),
                "T2": lambda T, a1, c2, sig, lam, T1, T2, S1, S2, i: T*(T-T1)/(T2*(T2-T1)),
                "S2": lambda T, a1, c2, sig, lam, T1, T2, S1, S2, i: ((lam*T*T2)/(c2*S2))*((T-T1)/(T2-T1)),
                "In-Use Signal": lambda T, a1, c2, sig, lam, T1, T2, S1, S2, i: (lam*T**2)/(c2*_Sin(T, a1, c2, sig, lam))},
            3: {"In-Use Signal": lambda T, a1, c2, sig, lam, Ts, Ss, i: (lam*T**2)/(c2*_Sin(T, a1, c2, sig, lam)),
                "T": lambda T, a1, c2, sig, lam, Ts, Ss, i: _T(T, Ts, i),
                "S": lambda T, a1, c2, sig, lam, Ts, Ss, i: _S(Ss, Ts, i)(T)*lam/c2}
            }


def build_wls_propagation_matrices(
    x_cal: NDArray,
    y_cal: NDArray,
    w: NDArray,
    params: NDArray,
    model_funcs: dict,
    include_residuals: bool = False,
) -> tuple[NDArray, NDArray, NDArray]:
    """Build H (N×N), C (M×N) and B (M×N) for weighted least-squares sensitivity propagation.

    These matrices depend only on calibration data and fitted parameters,
    NOT on the in-use temperature T_target.  Pre-computing them once and
    storing P_y = C·H⁻¹, P_x = B·H⁻¹ allows the sensitivity coefficients
    for the entire temperature range to be evaluated with a single matrix
    multiply instead of a Python loop.

    Args:
        x_cal: Calibration temperatures [K], shape (M,).
        y_cal: Calibration signals, shape (M,).
        w: Per-point weights, shape (M,).
        params: Fitted model parameters [A1, A2, A3], shape (N,).
        model_funcs: Dict from sakuma_hattori_model_funcs().
        include_residuals: Add residual correction to H (as derived in literature).

    Returns:
        H (N×N), C (M×N), B (M×N) numpy arrays.
    """
    x_cal  = np.asarray(x_cal,  dtype=float)
    y_cal  = np.asarray(y_cal,  dtype=float)
    w      = np.asarray(w,      dtype=float)
    params = np.asarray(params, dtype=float)
    M = len(x_cal)
    N = len(params)

    # H (N×N) — Gauss-Newton Hessian approximation (eq. B12)
    H = np.zeros((N, N))
    for k in range(M):
        g_k = np.asarray(model_funcs['df_da'](x_cal[k], params), dtype=float)
        H += w[k] * np.outer(g_k, g_k)
        if include_residuals and 'd2f_da2' in model_funcs:
            r_k = y_cal[k] - model_funcs['f'](x_cal[k], params)
            for i in range(N):
                for j in range(N):
                    H[i, j] += w[k] * r_k * model_funcs['d2f_da2'](x_cal[k], params, i, j)

    # C (M×N) — eq. B15
    C = np.zeros((M, N))
    for k in range(M):
        C[k, :] = w[k] * np.asarray(model_funcs['df_da'](x_cal[k], params), dtype=float)

    # B (M×N) — eq. B9
    B = np.zeros((M, N))
    for k in range(M):
        r_k        = y_cal[k] - model_funcs['f'](x_cal[k], params)
        df_dx_k    = model_funcs['df_dx'](x_cal[k], params)
        df_da_k    = np.asarray(model_funcs['df_da'](x_cal[k], params), dtype=float)
        d2f_dxda_k = np.asarray(model_funcs['d2f_dxda'](x_cal[k], params), dtype=float)
        B[k, :] = -w[k] * df_dx_k * df_da_k + w[k] * r_k * d2f_dxda_k

    return H, C, B


def overdetermined_calibration_sensitivity(
    x_cal: NDArray,
    y_cal: NDArray,
    w: NDArray,
    params: NDArray,
    x_target: float,
    model_funcs: dict,
    include_residuals: bool = False,
) -> tuple[NDArray, NDArray]:
    """Sensitivity coefficients for overdetermined non-linear calibration.

    For a model y = f(x; a) fitted by weighted least-squares to M calibration points
    with N parameters, computes the sensitivity coefficients of the predicted inverse
    x_hat (obtained by inverting a measured y at x_target) with respect to each
    calibration output y_i and input x_i.

    Args:
        x_cal: Calibration input values, shape (M,). e.g. fixed-point temperatures [K].
        y_cal: Calibration output values, shape (M,). e.g. measured signals.
        w: Non-negative weights for each calibration point, shape (M,).
        params: Fitted model parameters [a_1, ..., a_N], shape (N,).
        x_target: The input value where the prediction is evaluated (e.g. T_in_use).
        model_funcs: Dict with keys:
            'f'        : callable(x, params) -> float  — model y = f(x; params)
            'df_da'    : callable(x, params) -> NDArray(N,) — grad w.r.t. parameters
            'df_dx'    : callable(x, params) -> float  — derivative w.r.t. input x
            'd2f_dxda' : callable(x, params) -> NDArray(N,) — cross-deriv d²f/dx da_j
            'd2f_da2'  : callable(x, params, i, j) -> float — (optional) 2nd param deriv
        include_residuals: If True, adds the residual correction term to H (eq. B3 in
            residual-based corrections to the Hessian. Requires 'd2f_da2' in model_funcs.

    Returns:
        lambda_y: Sensitivity coefficients for calibration outputs y_i, shape (M,).
                  u(x_hat) contribution: sum_i (lambda_y[i] * u(y_i))^2
        lambda_x: Sensitivity coefficients for calibration inputs x_i, shape (M,).
                  u(x_hat) contribution: sum_i (lambda_x[i] * u(x_i))^2

    References:
        Saunders, P. (2003). Metrologia, 40(2), 93–101. Appendix B.
    """
    x_cal  = np.asarray(x_cal,  dtype=float)
    y_cal  = np.asarray(y_cal,  dtype=float)
    w      = np.asarray(w,      dtype=float)
    params = np.asarray(params, dtype=float)

    # H, C, B depend only on calibration data — delegate to the shared builder.
    H, C, B = build_wls_propagation_matrices(
        x_cal, y_cal, w, params, model_funcs, include_residuals
    )

    # g_j = ∂x̂/∂a_j = −(∂f/∂a_j)|_T / (∂f/∂x)|_T  (gradient vector at x_target)
    df_da_t = np.asarray(model_funcs['df_da'](x_target, params), dtype=float)  # (N,)
    df_dx_t = model_funcs['df_dx'](x_target, params)                            # scalar
    g = -df_da_t / df_dx_t

    try:
        H_inv_g = np.linalg.solve(H, g)
    except np.linalg.LinAlgError:
        H_inv_g, _, _, _ = np.linalg.lstsq(H, g, rcond=None)

    lambda_y = C @ H_inv_g   # (M,)
    lambda_x = B @ H_inv_g   # (M,)
    return lambda_y, lambda_x





def sakuma_hattori_model_funcs(c2: float) -> dict:
    """Return model_funcs dict for the Sakuma-Hattori coefficient form.

    Model:  S(T; A1, A2, A3) = A1 / (exp(c2 / (A2*T + A3)) - 1)
    Parameters: params = [A1, A2, A3]

    Args:
        c2: Second radiation constant [m·K].

    Returns:
        Dict compatible with overdetermined_calibration_sensitivity().
    """
    def _common(T, params):
        A1, A2, A3 = params
        denom = A2 * T + A3
        u = c2 / denom
        eu = np.exp(u)
        S = A1 / (eu - 1.0)
        # phi = A1 * eu / (eu - 1)^2  — appears in most derivatives
        phi = A1 * eu / (eu - 1.0) ** 2
        return S, phi, u, eu, denom

    def f(T, params):
        A1, A2, A3 = params
        return A1 / (np.exp(c2 / (A2 * T + A3)) - 1.0)

    def df_da(T, params):
        S, phi, u, eu, denom = _common(T, params)
        # dS/dA1 = S / A1
        dS_dA1 = S / params[0]
        # dS/dA2 = phi * (c2 * T) / denom^2
        dS_dA2 = phi * c2 * T / denom ** 2
        # dS/dA3 = phi * c2 / denom^2
        dS_dA3 = phi * c2 / denom ** 2
        return np.array([dS_dA1, dS_dA2, dS_dA3])

    def df_dx(T, params):
        S, phi, u, eu, denom = _common(T, params)
        A1, A2, A3 = params
        # dS/dT = phi * c2 * A2 / denom^2
        return phi * c2 * A2 / denom ** 2

    def d2f_dxda(T, params):
        """Cross-derivatives d²S/(dT dA_j) for j = 1, 2, 3."""
        A1, A2, A3 = params
        S, phi, u, eu, denom = _common(T, params)

        # Shared factors
        q = c2 / denom ** 2          # c2 / denom^2
        dphi_dT = phi * (u / denom) * A2 * (eu + 1.0) / (eu - 1.0)

        # d²S / (dT dA1) = (1/A1) * dS/dT
        d2S_dT_dA1 = (1.0 / A1) * phi * c2 * A2 / denom ** 2

        # d²S / (dT dA2):  dS/dA2 = phi * c2 * T / denom^2
        # d/dT [phi * c2 * T / denom^2]
        #   = (dphi/dT) * c2*T/denom^2 + phi * c2/denom^2 + phi*c2*T*(-2*A2/denom^3)
        d2S_dT_dA2 = (
            dphi_dT * c2 * T / denom ** 2
            + phi * c2 / denom ** 2
            - 2.0 * phi * c2 * T * A2 / denom ** 3
        )

        # d²S / (dT dA3): dS/dA3 = phi * c2 / denom^2
        # d/dT [phi * c2 / denom^2]
        #   = (dphi/dT) * c2/denom^2 - 2*phi*c2*A2/denom^3
        d2S_dT_dA3 = (
            dphi_dT * c2 / denom ** 2
            - 2.0 * phi * c2 * A2 / denom ** 3
        )

        return np.array([d2S_dT_dA1, d2S_dT_dA2, d2S_dT_dA3])

    def d2f_da2(T, params, i, j):
        """Second param derivatives d²S/(dA_i dA_j) — used only with include_residuals."""
        A1, A2, A3 = params
        S, phi, u, eu, denom = _common(T, params)
        q = c2 / denom ** 2

        # Derivative of phi w.r.t. A_j
        def dphi_dAj(idx):
            if idx == 0:   # A1
                return eu / (eu - 1.0) ** 2
            elif idx == 1:  # A2
                return -phi * u * T / denom * (eu + 1.0) / (eu - 1.0)
            else:           # A3
                return -phi * u / denom * (eu + 1.0) / (eu - 1.0)

        # dS/dA_i factor (without phi for i=0)
        def factor(idx):
            if idx == 0:
                return q * 0.0  # handled separately below
            elif idx == 1:
                return q * T
            else:
                return q

        if i == 0 and j == 0:   return 0.0
        if i == 0:               return dphi_dAj(0) * factor(j) if j > 0 else 0.0
        if j == 0:               return d2f_da2(T, params, j, i)

        # i,j in {1,2}: d/dA_j [phi * c2 * factor_i] = dphi_dAj * c2 * factor_i + phi * d(factor_i)/dA_j
        f_i = factor(i)
        d_fi_dAj = -2.0 * c2 * (T if i == 1 else 1.0) * (T if j == 1 else 1.0) / denom ** 3
        return dphi_dAj(j) * c2 * f_i + phi * d_fi_dAj

    return {
        'f': f,
        'df_da': df_da,
        'df_dx': df_dx,
        'd2f_dxda': d2f_dxda,
        'd2f_da2': d2f_da2,
    }


if __name__ == "__main__":
    print(func_dic[3]["T"](np.array([1597.39, 1357.802, 2747.84]), 1,1,1,1,[1597.39, 1357.802, 2747.84],[3.0723e-09, 2.6772e-10, 1.00886e-06], 1))
