"""确定性的 144 时段合成数据演示，不依赖竞赛附件。"""
from pathlib import Path
import json
import math

from .billing import BillingRates, cash_bill
from .controller import Battery, rollout


def synthetic_day(slots: int = 144) -> dict[str, list[float]]:
    """生成负荷、光伏和分时电价；同一输入始终得到同一结果。"""
    hours = [24 * i / slots for i in range(slots)]
    loads = [
        520 + 90 * math.sin((hour - 7) * math.pi / 12) ** 2
        + 130 * math.exp(-((hour - 19) / 2.2) ** 2)
        for hour in hours
    ]
    pvs = [520 * max(0.0, math.sin((hour - 6) * math.pi / 12)) ** 1.7 for hour in hours]
    prices = [0.42 if hour < 7 else 1.18 if 17 <= hour < 22 else 0.72 for hour in hours]
    return {"hours": hours, "loads": loads, "pvs": pvs, "prices": prices}


def build_plan(data: dict[str, list[float]]) -> tuple[list[float], list[float]]:
    """用低价充电、高价减购的透明规则构造演示计划。"""
    contracts: list[float] = []
    targets: list[float] = []
    for load, pv, price in zip(data["loads"], data["pvs"], data["prices"]):
        net = max(load - pv, 0.0)
        if price <= 0.42:
            contracts.append(net + 150.0)
            targets.append(150.0)
        elif price >= 1.18:
            contracts.append(max(net - 120.0, 0.0))
            targets.append(0.0)
        else:
            contracts.append(net)
            targets.append(0.0)
    return contracts, targets


def run_demo() -> tuple[dict[str, object], dict[str, list[float]]]:
    data = synthetic_day()
    contracts, targets = build_plan(data)
    battery = Battery(1200.0, 10800.0, 5000 / 6, 5000 / 6, 0.9, 0.9)
    dispatch = rollout(6000.0, data["loads"], data["pvs"], contracts, targets, battery)
    emergency = [row["emergency"] for row in dispatch]
    bill = cash_bill(data["prices"], contracts, contracts, emergency, BillingRates())
    baseline_emergency = [max(load - pv - contract, 0.0) for load, pv, contract in zip(
        data["loads"], data["pvs"], contracts
    )]
    baseline_bill = cash_bill(data["prices"], contracts, contracts, baseline_emergency)

    max_residual = max(abs(row["balance_residual"]) for row in dispatch)
    summary: dict[str, object] = {
        "data": "deterministic synthetic 24-hour profile",
        "intervals": len(dispatch),
        "interval_minutes": 10,
        "cash_bill_with_storage": round(bill["total"], 6),
        "cash_bill_without_storage": round(baseline_bill["total"], 6),
        "emergency_energy_with_storage_kwh": round(sum(emergency), 6),
        "emergency_energy_without_storage_kwh": round(sum(baseline_emergency), 6),
        "initial_soc_kwh": 6000.0,
        "final_soc_kwh": round(dispatch[-1]["soc_end"], 6),
        "max_balance_residual_kwh": max_residual,
        "soc_bounds_satisfied": all(1200 - 1e-7 <= row["soc_end"] <= 10800 + 1e-7 for row in dispatch),
        "charge_discharge_mutually_exclusive": all(not (row["charge"] > 1e-7 and row["discharge"] > 1e-7) for row in dispatch),
    }
    plot_data = {
        **data,
        "contracts": contracts,
        "soc": [row["soc_end"] for row in dispatch],
        "emergency": emergency,
    }
    return summary, plot_data


def save_plot(data: dict[str, list[float]], output: Path) -> None:
    """仅用标准库生成轻量 SVG，保证克隆后无需额外依赖即可运行。"""
    width, height = 1000, 560
    left, right = 75, 960
    top1, bottom1 = 70, 285
    top2, bottom2 = 345, 510

    def points(values: list[float], top: float, bottom: float) -> str:
        low, high = min(values), max(values)
        span = high - low or 1.0
        coords = []
        for index, value in enumerate(values):
            x = left + (right - left) * index / (len(values) - 1)
            y = bottom - (bottom - top) * (value - low) / span
            coords.append(f"{x:.1f},{y:.1f}")
        return " ".join(coords)

    grid = []
    labels = []
    for hour in (0, 6, 12, 18, 24):
        x = left + (right - left) * hour / 24
        grid.append(f'<line x1="{x:.1f}" y1="{top1}" x2="{x:.1f}" y2="{bottom2}" class="grid"/>')
        labels.append(f'<text x="{x:.1f}" y="540" text-anchor="middle">{hour}</text>')

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
<style>
text {{ font-family: Arial, sans-serif; fill: #25364a; font-size: 14px; }}
.title {{ font-size: 22px; font-weight: 700; }} .grid {{ stroke: #dfe5ea; stroke-width: 1; }}
.axis {{ stroke: #708090; stroke-width: 1.2; }} .series {{ fill: none; stroke-width: 2.5; }}
</style>
<rect width="100%" height="100%" fill="white"/>
<text x="{width/2}" y="34" text-anchor="middle" class="title">Synthetic microgrid dispatch demo</text>
{''.join(grid)}
<line x1="{left}" y1="{bottom1}" x2="{right}" y2="{bottom1}" class="axis"/>
<line x1="{left}" y1="{bottom2}" x2="{right}" y2="{bottom2}" class="axis"/>
<polyline points="{points(data['loads'], top1, bottom1)}" class="series" stroke="#25364a"/>
<polyline points="{points(data['pvs'], top1, bottom1)}" class="series" stroke="#e0a11b"/>
<polyline points="{points(data['contracts'], top1, bottom1)}" class="series" stroke="#4b8b6f"/>
<polyline points="{points(data['soc'], top2, bottom2)}" class="series" stroke="#6750a4"/>
<text x="82" y="92">Load</text><line x1="122" y1="87" x2="158" y2="87" stroke="#25364a" stroke-width="3"/>
<text x="175" y="92">PV</text><line x1="198" y1="87" x2="234" y2="87" stroke="#e0a11b" stroke-width="3"/>
<text x="250" y="92">Grid contract</text><line x1="340" y1="87" x2="376" y2="87" stroke="#4b8b6f" stroke-width="3"/>
<text x="82" y="368">Battery SOC</text><line x1="170" y1="363" x2="206" y2="363" stroke="#6750a4" stroke-width="3"/>
<text x="26" y="190" transform="rotate(-90 26 190)" text-anchor="middle">Energy / interval (kWh)</text>
<text x="26" y="430" transform="rotate(-90 26 430)" text-anchor="middle">SOC (kWh)</text>
{''.join(labels)}<text x="{width/2}" y="556" text-anchor="middle">Hour</text>
</svg>'''
    output.write_text(svg, encoding="utf-8")


def main(output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    summary, data = run_demo()
    (output_dir / "demo_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    save_plot(data, output_dir / "demo_dispatch.svg")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"Artifacts written to: {output_dir}")\n