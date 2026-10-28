"""Regression tests for the code-review fixes. All inputs come from Example_data/ and Fixed Points/."""
import copy
import itertools
import json
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from scipy import integrate

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from RunUncertainty import RunUncertainty  # noqa: E402
from safe_math import safe_make_function  # noqa: E402
from pages.corrections_page import prepare_scan  # noqa: E402
from pages.scale_realization_page import load_fixed_point_library  # noqa: E402

warnings.filterwarnings("ignore")

_sensor = pd.read_csv(ROOT / "Example_data" / "SensorData.csv")
WL = _sensor.iloc[:, 0].to_numpy(float)
RES = _sensor.iloc[:, 1].to_numpy(float)


def _model(name):
    return json.loads((ROOT / "models" / f"{name}.json").read_text(encoding="utf-8"))


def _fixed_point(name, unit):
    data = json.loads((ROOT / "Fixed Points" / f"{name}.json").read_text(encoding="utf-8"))
    if unit == "C":
        data["Temperature"] -= 273.15
        data["Unit"] = "C"
    return data


def _raw_data(names, unit="K "):
    """Widget list as the Uncertainty Budget page sends it (std widget is removed from n >= 3)."""
    std, mean, in_use = (_model(m) for m in ("standard_deviation_model", "mean_wavelength_model", "in-use_signal_model"))
    lam = integrate.simpson(WL * RES, x=WL) / integrate.simpson(RES, x=WL)
    sig = (integrate.simpson((WL - lam) ** 2 * RES, x=WL) / integrate.simpson(RES, x=WL)) ** 0.5
    mean["Temperature"], std["Temperature"] = lam, sig
    fixed = sorted((_fixed_point(n, unit) for n in names),
                   key=lambda d: d["Temperature"] + (273.15 if d["Unit"] == "C" else 0.0))
    return ([std] if len(fixed) < 3 else []) + [mean, in_use, *fixed]


def _run(names, unit="K "):
    run = RunUncertainty(copy.deepcopy(_raw_data(names, unit)), WL, RES)
    run.make_calibration(False, np.arange(1000, 3200))
    return run


T_PROBE = np.array([1400.0, 2000.0, 3000.0])


# --- #1: fixed points entered in Celsius must give the same budget as Kelvin ----------------
@pytest.mark.parametrize("names", [["Cu"], ["Cu", "Pd-C"], ["Cu", "Pd-C", "Ru-C"]])
def test_celsius_input_matches_kelvin(names):
    u_k = _run(names, "K ").calculate_componets_un(T_PROBE)[1][0]
    u_c = _run(names, "C").calculate_componets_un(T_PROBE)[1][0]
    np.testing.assert_allclose(u_c, u_k, rtol=1e-9)


# --- #2: three or more fixed points must never produce a NaN calibration --------------------
@pytest.mark.parametrize("names", [["Cu", "Fe-C", "CoC"], ["Cu", "Fe-C", "Pd-C"]])
def test_three_point_fit_is_finite(names):
    # these two subsets of the example fixed points used to return NaN coefficients
    run = _run(names)
    assert np.all(np.isfinite([run.a1, run.a2, run.a3]))
    assert np.all(np.isfinite(run.calculate_componets_un(T_PROBE)[1][0]))


@pytest.mark.parametrize("names", list(itertools.combinations(["Cu", "Fe-C", "CoC", "Pd-C", "Ru-C", "ReC", "WC-C"], 7)))
def test_all_example_fixed_points_fit_data(names):
    run = _run(list(names))
    temps = np.array([json.loads((ROOT / "Fixed Points" / f"{n}.json").read_text(encoding="utf-8"))["Temperature"] for n in names])
    sigs = np.array([json.loads((ROOT / "Fixed Points" / f"{n}.json").read_text(encoding="utf-8"))["Signal"] for n in names])
    assert np.max(np.abs(run.inv_sakuma_hattor_signal(sigs) - temps)) < 0.15  # K; signals were measured against pre-POI temperatures (0.11 K worst residual)


# --- #4: fixed-point library must use the repo's Fixed Points folder ------------------------
def test_library_uses_repo_fixed_points():
    lib = load_fixed_point_library()
    assert lib["Fe-C"]["Temperature"] == pytest.approx(1426.92)
    assert lib["Pd-C"]["Temperature"] == pytest.approx(1765.05)
    assert lib["Cu"]["Signal"] == pytest.approx(2.6772e-10)
    assert lib["Pt-C"]["Temperature"] == pytest.approx(2011.43)   # published HTFP value (POI)
    assert {"Ag", "Au"} <= set(lib)                 # built-ins without a JSON file stay selectable
    assert "CoC" not in lib and "Co-C" in lib       # CoC.json replaces the Co-C entry, no duplicate


# --- #9: valid custom equations with a pole at the validator's dummy point --------------------
def test_custom_equation_with_pole_at_dummy_point():
    fit = pd.read_csv(ROOT / "Example_data" / "SSE" / "sse_lp5.txt", sep="\t", header=None)
    x, y = fit[0].to_numpy(float), fit[1].to_numpy(float)
    from scipy.optimize import curve_fit
    func = safe_make_function("a*x/(x-b)", ["a", "b"])   # x = b = 1 in the validator -> 1/0
    params, _ = curve_fit(func, x, y, p0=[1e-3, -5.0], maxfev=20000)
    assert np.max(np.abs(func(x, *params) - y)) < 1e-4


def test_unsafe_equation_still_rejected():
    with pytest.raises(ValueError):
        safe_make_function("__import__('os').system('echo hi')", [])


# --- SSE scan checks -------------------------------------------------------------------------
@pytest.fixture(scope="module")
def scan():
    data = pd.read_csv(ROOT / "Example_data" / "SSE" / "Scan_WCC.txt", sep="\t", header=None)
    return data[0].to_numpy(float), data[1].to_numpy(float)


def test_scan_example_is_accepted(scan):
    x, y, dropped = prepare_scan(*scan)
    assert dropped == 0 and x[0] == -15 and x[-1] == 15


def test_scan_one_sided_is_rejected(scan):
    x, y = scan
    with pytest.raises(ValueError, match="both sides"):
        prepare_scan(x[x >= 0], y[x >= 0])


def test_scan_in_stage_coordinates_is_rejected(scan):
    x, y = scan
    with pytest.raises(ValueError, match="both sides"):
        prepare_scan(x + 25.0, y)


def test_scan_nan_rows_are_dropped(scan):
    x, y = scan
    y = y.copy()
    y[10] = np.nan
    x2, y2, dropped = prepare_scan(x, y)
    assert dropped == 1 and np.all(np.isfinite(y2)) and len(x2) == len(x) - 1


def test_scan_nonpositive_centre_is_rejected(scan):
    x, y = scan
    y = y.copy()
    y[x == 0] = -1e-6
    with pytest.raises(ValueError, match="centre"):
        prepare_scan(x, y)


# ---- Optimal combination search (Scale Realization) -------------------------

@pytest.fixture(scope="module")
def scale_page():
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    from pages.scale_realization_page import ScaleRealizationPage
    app = QApplication.instance() or QApplication([])
    page = ScaleRealizationPage()
    rows = pd.read_csv(ROOT / "Example_data" / "Scale Realization" / "T-S.txt", skipinitialspace=True)
    for _, r in rows.iterrows():
        page.add_fixed_point_row(r["Name"], str(r["Temp"]), str(r["Signal"]))
    yield page, len(rows)
    page.deleteLater()


def test_sakuma_fit_silent_recovers_fixed_points(scale_page):
    page, n = scale_page
    res = page._sakuma_fit_silent(list(range(n)), eval_row_indices=list(range(n)))
    assert res is not None and res["n"] == n
    assert res["max_mK"] < 150  # same data as test_all_example_fixed_points_fit_data


def test_find_optimal_combination_ranks_by_max_error(scale_page, monkeypatch):
    page, n = scale_page
    from pages import scale_realization_page as srp
    captured = {}

    class FakeDialog:
        def __init__(self, results, parent=None, apply_callback=None):
            captured["results"] = results

        def exec(self):
            return 0

    monkeypatch.setattr(srp, "OptimalCombinationResultDialog", FakeDialog)
    page.find_optimal_combination()
    results = captured["results"]
    assert len(results) == sum(1 for k in range(3, n + 1) for _ in itertools.combinations(range(n), k))
    errs = [r["max_mK"] for r in results]
    assert errs == sorted(errs)
    assert all(r["n"] >= 3 for r in results)  # no spectral data loaded -> n starts at 3


# ---- Data analysis: "Both" domain reports temperature and signal --------------

def test_data_analysis_both_domains_reported():
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication, QFileDialog
    from pages.data_analysis_page import DataAnalysisPage
    app = QApplication.instance() or QApplication([])
    page = DataAnalysisPage()
    path = str(ROOT / "Example_data" / "Signal-Temperature" / "LP5_Fe-C.txt")
    QFileDialog.getOpenFileName = staticmethod(lambda *a, **k: (path, ""))
    page.load_data()
    page.cb_domain.setCurrentText("Both")
    page.on_derivative()
    page.cb_poi_method.setCurrentText("3rd Degree Polynomial")
    page.compute_poi()

    poi_t = page.results_by_domain["Temperature"]["3rd Degree Polynomial"]["POI"]
    poi_s = page.results_by_domain["Signal"]["3rd Degree Polynomial"]["POI"]
    assert poi_t is not None and poi_s is not None
    assert poi_t > 100 and poi_s < 1e-3  # temperature in K, signal in A

    page.cb_results_view.setCurrentText("Signal")
    assert not page.btn_temp_unit.isEnabled()
    page.cb_results_view.setCurrentText("Temperature")
    assert page.btn_temp_unit.isEnabled()
    page.deleteLater()


def test_data_analysis_plots_kelvin_with_units():
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication, QFileDialog
    from pages.data_analysis_page import DataAnalysisPage
    app = QApplication.instance() or QApplication([])
    page = DataAnalysisPage()
    path = str(ROOT / "Example_data" / "Signal-Temperature" / "LP5_Fe-C.txt")
    QFileDialog.getOpenFileName = staticmethod(lambda *a, **k: (path, ""))
    page.load_data()
    t_loaded = page.temperature.copy()
    page.cb_domain.setCurrentText("Temperature")
    page.cb_data_unit.setCurrentText("°C")  # file values are interpreted as degrees Celsius
    page.update_main_plot()
    line = page.canvas_main.ax.get_lines()[0]
    assert np.allclose(line.get_ydata(), t_loaded + 273.15)
    assert page.canvas_main.ax.get_ylabel() == "Temperature (K)"
    page.on_derivative()
    assert np.allclose(page.deriv_y, t_loaded + 273.15)
    assert "(K/s)" in page.canvas_poi.figure.axes[1].get_ylabel()
    assert page.canvas_poi.figure.axes[0].get_ylabel() == "Temperature (K)"
    page.deleteLater()
