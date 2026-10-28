# Changelog

## [1.0.1] - 2026-10-28

### Added
- Scale Realization: **Find Optimal Combination** searches every subset of fixed points (weighted and
  non-weighted fits), scores each fit on all valid points and ranks by max |dT|. *Apply Best* /
  *Apply Selected Row* tick the fixed points and the Weighted Fit option and run the fit.
- Data Analysis: Domain **Both** now computes derivative, POI and liquidus for temperature and signal;
  the Results tab has a Temperature / Signal report selector. The K/degC toggle is disabled for signal results.
- `CHANGELOG.md`; `openpyxl` added to the requirements (Excel export).

### Changed
- Data Analysis plots always show temperature in kelvin (data loaded in degC is converted); all plot axes
  carry units in `Name, unit` form.
- Built-in and `Fixed Points/*.json` reference temperatures use the published HTFP point-of-inflection values:
  Fe-C 1426.92 K, Pd-C 1765.05 K, Ru-C 2226.99 K, WC-C 3020.85 K, Pt-C 2011.43 K.
  The stored signals were measured against the previous values and have not been re-measured.

### Fixed
- Uncertainty: fixed-point temperatures are passed in kelvin, so degC input no longer inflates the
  uncertainty for n = 1, 2, 3; the n >= 3 fit keeps the fitted a2/a3 (sigma = 0 with a warning if a3 < 0).
- SSE ring correction (linearised Bourson form) and scan validation (sorted, straddles x = 0).
- Custom-equation validation (`safe_math`).
- Deleting a fixed-point row no longer leaves stale row indices on the remaining rows.
- Temperature-drop correction read a non-existent field (`emiss_signal_input`).
- degC/degF offset 273.14 -> 273.15; plot-settings path typo (`modelsplot_settings.json`).
- Calibration export and sensor-data loading reject empty or invalid input.
- `np.trapezoid` error on numpy 1.x (falls back to `np.trapz`).

## [1.0.0] - 2026-03-26
- Initial release.
