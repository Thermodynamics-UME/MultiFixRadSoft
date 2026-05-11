"""Uncertainty propagation for radiation thermometry.

Provides unit conversion utilities and the UncertaintyComponent class for
computing sensitivity-weighted measurement uncertainty.
"""

from __future__ import annotations

from typing import Any, Callable

import numpy as np
from numpy.typing import NDArray

from UncertaintyFunctions import _Sin

to_SI = {"C": [lambda x: x+273.15, "K"],  # °
         "F": [lambda x: (x-32)/1.8 + 273.14, "K"],
         "K": [lambda x: x, "K"],
         "K ": [lambda x: x, "K"],
         "mK": [lambda x: 1e-3*x, "K"],
         "uK": [lambda x: 1e-6*x, "K"],
         "m":  [lambda x: x, "m"],
         "mm": [lambda x: 1e-3*x, "m"],
         "um": [lambda x: 1e-6*x, "m"],
         "nm": [lambda x: 1e-9*x, "m"]}


def combine_uns(uns: NDArray) -> NDArray:
    """Root-sum-square combination of uncertainty arrays."""
    return np.sqrt(np.sum(uns**2, axis=0))


class UncertaintyComponent:
    """Single uncertainty component with sensitivity coefficient propagation.

    Each instance represents one source of uncertainty (e.g., a fixed-point
    temperature, signal measurement, or instrument parameter) and computes
    its contribution to the total uncertainty budget.

    Args:
        measurand: The measured value.
        measurand_unit: Unit string for the measurand.
        un_coeff: Sensitivity coefficient function f(T, *params) -> coefficient.
        info: Dict with 'Values', 'Unit', and 'Names' keys.
        params: Parameters passed to the sensitivity coefficient function.
    """

    def __init__(
        self,
        measurand: float | None = None,
        measurand_unit: str | None = None,
        un_coeff: Callable | None = None,
        info: dict[str, Any] | None = None,
        params: list[float] | None = None,
    ) -> None:
        self.measurand = measurand
        self.measurand_unit = measurand_unit
        self.un_coeff = un_coeff
        self.raw_components = info["Values"]
        self.raw_comp_units = info["Unit"]
        self.components = info["Values"]
        self.comp_units = info["Unit"]
        self.params = params
        self.is_in_use_signal = False

        self.update_components()

    def get_componets_values_data(self) -> list[str]:
        """Return raw component values with units as formatted strings."""
        res = []
        for v, u in zip(self.raw_components, self.raw_comp_units):
            res.append(str(v)+" "+u)
        return res

    def update_measurand(self, T: NDArray) -> None:
        """Recompute measurand from the Sakuma-Hattori signal at temperature T."""
        self.measurand = _Sin(T, *self.params[:4])

    def components_uncertainties(self, T: NDArray) -> NDArray:
        """Compute individual uncertainty contributions at temperatures T."""
        self.update_components()
        if self.is_in_use_signal:
            res = []
            for i, t in enumerate(T):
                self.update_measurand(t)
                (un_componets, unit) = self.ratio_to_val()
                res.append(self.un_coeff(np.array([t]), *self.params)*un_componets)
            res = np.array(res)
        else:
            (un_componets, unit) = self.ratio_to_val()
            a1 = np.transpose(np.array([self.un_coeff(T, *self.params)]))
            a2 = np.array([un_componets])
            res = np.matmul(a1, a2)
        return np.transpose(res)

    def combined_uncertainties(self, T: NDArray) -> NDArray:
        """Root-sum-square of all component uncertainties at temperatures T."""
        self.update_components()
        return combine_uns(self.components_uncertainties(T))

    def to_SI_Units(self, values: list, units: list[str]) -> tuple[list, list[str]]:
        """Convert values to SI units using the to_SI lookup table."""
        new_val = []
        new_units = []
        for u, v in zip(units, values):
            try:
                new_val.append(to_SI[u][0](v))
                new_units.append(to_SI[u][1])
            except (KeyError, TypeError):
                new_val.append(v)
                new_units.append(u)
        return new_val, new_units

    def ratio_to_val(self) -> tuple[list, list[str]]:
        """Convert percentage-based components to absolute values."""
        new_val = []
        new_units = []
        for u, v in zip(self.comp_units, self.components):
            if u in ["%", "% "]:
                new_val.append(v * self.measurand / 100)
                new_units.append(self.measurand_unit)
            else:
                new_val.append(v)
                new_units.append(u)

        return new_val, new_units

    def update_components(self) -> None:
        """Re-convert all components and measurand to SI units."""
        (self.components, self.comp_units) = self.to_SI_Units(self.components, self.comp_units)
        (measurand, measurand_unit) = self.to_SI_Units([self.measurand], [self.measurand_unit])
        self.measurand = measurand[0]
        self.measurand_unit = measurand_unit[0]

if __name__ == '__main__':
    measurend = 0.00000000026772
    measurend_unit = ""
    un_coeff = lambda T, l, c2, Sref: l * T ** 2 / (c2 * Sref)
    info = {
        "Values": [0.01, 0.002, 0.003],
        "Unit": ["%", "%", "%"],
        "Names": ["comp1", "comp2", "comp3"],
    }
    params = [650*1e-9, 0.014388, 0.00000000026772]
    test = UncertaintyComponent(measurend, measurend_unit, un_coeff, info, params)
    temps = np.array([1000, 1500])
    print(test.combined_uncertainties(temps))  # noqa: T201 — test code
