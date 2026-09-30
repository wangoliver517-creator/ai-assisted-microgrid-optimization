"""只使用当前信息的固定储能执行规则；所有电量单位均为 kWh。"""
from dataclasses import dataclass
import math


def _finite_nonnegative(value: float, name: str) -> float:
    if isinstance(value, (bool, str, bytes)):
        raise ValueError(f"{name} must be a finite non-negative number")
    number = float(value)
    if not math.isfinite(number) or number < 0:
        raise ValueError(f"{name} must be a finite non-negative number")
    return number


@dataclass(frozen=True)
class Battery:
    """储能物理参数；充放电量均在交流侧计量。"""

    soc_min: float
    soc_max: float
    max_charge_kwh: float
    max_discharge_kwh: float
    eta_charge: float
    eta_discharge: float

    def __post_init__(self) -> None:
        for field in self.__dataclass_fields__:
            object.__setattr__(self, field, _finite_nonnegative(getattr(self, field), field))
        if self.soc_min > self.soc_max:
            raise ValueError("soc_min cannot exceed soc_max")
        if not 0 < self.eta_charge <= 1 or not 0 < self.eta_discharge <= 1:
            raise ValueError("efficiencies must be in (0, 1]")


def step(
    soc: float,
    load: float,
    pv: float,
    contract: float,
    charge_target: float,
    battery: Battery,
    tolerance: float = 1e-7,
) -> dict[str, float]:
    """执行一个时段，并立即核验能量平衡、SOC 和互斥约束。"""
    values = ((soc, "soc"), (load, "load"), (pv, "pv"),
              (contract, "contract"), (charge_target, "charge_target"))
    soc, load, pv, contract, charge_target = [
        _finite_nonnegative(value, name) for value, name in values
    ]
    if not battery.soc_min <= soc <= battery.soc_max:
        raise ValueError("initial SOC is outside battery bounds")
    if charge_target > battery.max_charge_kwh:
        raise ValueError("charge target exceeds the interval power limit")

    charge_cap = min(
        battery.max_charge_kwh,
        (battery.soc_max - soc) / battery.eta_charge,
    )
    discharge_cap = min(
        battery.max_discharge_kwh,
        battery.eta_discharge * (soc - battery.soc_min),
    )
    residual_supply = contract + pv - load

    if residual_supply < 0:
        charge = 0.0
        discharge = min(discharge_cap, -residual_supply)
        emergency = max(0.0, -residual_supply - discharge)
        unused_contract = 0.0
        curtailed_pv = 0.0
    else:
        charge = min(charge_target, charge_cap, residual_supply)
        discharge = 0.0
        emergency = 0.0
        remaining = residual_supply - charge
        curtailed_pv = min(pv, remaining)
        unused_contract = remaining - curtailed_pv

    soc_end = soc + battery.eta_charge * charge - discharge / battery.eta_discharge
    balance = (
        contract - unused_contract + pv - curtailed_pv
        + discharge + emergency - load - charge
    )
    if (
        abs(balance) > tolerance
        or not battery.soc_min - tolerance <= soc_end <= battery.soc_max + tolerance
        or (charge > tolerance and discharge > tolerance)
    ):
        raise ArithmeticError("physical constraint validation failed")

    return {
        "soc_start": soc,
        "soc_end": soc_end,
        "charge": charge,
        "discharge": discharge,
        "emergency": emergency,
        "unused_contract": unused_contract,
        "curtailed_pv": curtailed_pv,
        "balance_residual": balance,
    }


def rollout(
    initial_soc: float,
    loads: list[float],
    pvs: list[float],
    contracts: list[float],
    targets: list[float],
    battery: Battery,
) -> list[dict[str, float]]:
    """按时间顺序推进状态；序列长度不同会直接报错。"""
    sequences = [list(x) for x in (loads, pvs, contracts, targets)]
    if len({len(x) for x in sequences}) != 1:
        raise ValueError("all input sequences must have equal length")
    state = _finite_nonnegative(initial_soc, "initial_soc")
    results: list[dict[str, float]] = []
    for load, pv, contract, target in zip(*sequences):
        result = step(state, load, pv, contract, target, battery)
        results.append(result)
        state = result["soc_end"]
    return results
