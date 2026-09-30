"""现金结算函数；与调度器分离，便于独立复算。"""
from dataclasses import dataclass
import math


@dataclass(frozen=True)
class BillingRates:
    """合同调整与紧急购电相对正常电价的倍数。"""

    cancellation: float = 0.5
    increase: float = 1.5
    emergency: float = 5.0

    def __post_init__(self) -> None:
        for name in self.__dataclass_fields__:
            value = float(getattr(self, name))
            if not math.isfinite(value) or value < 0:
                raise ValueError(f"{name} must be finite and non-negative")


def cash_bill(
    prices: list[float],
    midnight_plan: list[float],
    final_contract: list[float],
    emergency: list[float],
    rates: BillingRates = BillingRates(),
) -> dict[str, float]:
    """按照最终合同相对零点计划的差额和紧急购电量结算。"""
    vectors = [list(v) for v in (prices, midnight_plan, final_contract, emergency)]
    if len({len(v) for v in vectors}) != 1:
        raise ValueError("billing vectors must have equal length")
    normal = increase = cancellation = emergency_cost = 0.0
    for price, plan, contract, urgent in zip(*vectors):
        if any((not math.isfinite(float(x)) or float(x) < 0) for x in (price, plan, contract, urgent)):
            raise ValueError("billing inputs must be finite and non-negative")
        base = min(plan, contract)
        added = max(contract - plan, 0.0)
        cancelled = max(plan - contract, 0.0)
        normal += price * base
        increase += rates.increase * price * added
        cancellation += rates.cancellation * price * cancelled
        emergency_cost += rates.emergency * price * urgent
    return {
        "normal_contract": normal,
        "contract_increase": increase,
        "cancellation_penalty": cancellation,
        "emergency_purchase": emergency_cost,
        "total": normal + increase + cancellation + emergency_cost,
    }
