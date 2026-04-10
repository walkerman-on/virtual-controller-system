import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional


RESULTS_DIR = Path(__file__).resolve().parent / "results"
REPORT_PATH = RESULTS_DIR / "LOAD_TEST_REPORT.md"


def pick_latest(files: List[Path], prefix: str) -> Optional[Path]:
    matched = [p for p in files if p.name.startswith(prefix) and p.suffix == ".json"]
    if not matched:
        return None
    return sorted(matched, key=lambda p: p.stat().st_mtime)[-1]


def load_json(path: Path) -> Dict:
    return json.loads(path.read_text(encoding="utf-8"))


def pass_fail(error_rate: float, p95: float, p99: float, missed_rate: float) -> str:
    if error_rate <= 1.0 and p95 <= 300.0 and p99 <= 700.0 and missed_rate <= 5.0:
        return "PASS"
    if error_rate <= 2.0 and p95 <= 500.0 and p99 <= 1000.0 and missed_rate <= 10.0:
        return "WARNING"
    return "FAIL"


def scenario_conclusion(status: str) -> str:
    if status == "PASS":
        return "Нагрузка в этом сценарии устойчива. Можно использовать как рабочий режим."
    if status == "WARNING":
        return "Система работает на грани. Желательны оптимизации до промышленного использования."
    return "Сценарий показывает перегруз или нестабильность. Нужны доработки конфигурации/архитектуры."


def main() -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    files = list(RESULTS_DIR.glob("*.json"))

    scenarios = {
        "baseline": pick_latest(files, "baseline_"),
        "workload": pick_latest(files, "workload_"),
        "spike": pick_latest(files, "spike_"),
    }

    lines = [
        "# Отчет по экспресс-нагрузочному тесту",
        "",
        f"- Дата формирования: `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`",
        "- Критерии оценки: `error_rate <= 1%`, `p95 <= 300ms`, `p99 <= 700ms`, `missed_deadline <= 5%`",
        "",
        "## Сводная таблица",
        "",
        "| Сценарий | Контроллеры | Цикл, мс | Длительность, с | Error % | Missed deadline % | p95, мс | p99, мс | Max, мс | Статус |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]

    overall = []
    for name in ["baseline", "workload", "spike"]:
        path = scenarios[name]
        if not path:
            lines.append(f"| `{name}` | - | - | - | - | - | - | - | - | `NO DATA` |")
            continue

        data = load_json(path)
        profile = data.get("profile", {})
        summary = data.get("summary", {})
        latency = summary.get("latency_ms", {})

        err = float(summary.get("error_rate_pct", 0.0))
        missed = float(summary.get("missed_deadline_rate_pct", 0.0))
        p95 = float(latency.get("p95", 0.0))
        p99 = float(latency.get("p99", 0.0))
        max_v = float(latency.get("max", 0.0))
        status = pass_fail(err, p95, p99, missed)
        overall.append(status)

        lines.append(
            f"| `{name}` | {int(profile.get('controllers', 0))} | {int(profile.get('cycle_ms', 0))} | "
            f"{int(profile.get('duration_sec', 0))} | {err:.2f} | {missed:.2f} | {p95:.2f} | {p99:.2f} | "
            f"{max_v:.2f} | `{status}` |"
        )

    lines.extend(["", "## Выводы по сценариям", ""])

    for name in ["baseline", "workload", "spike"]:
        path = scenarios[name]
        if not path:
            lines.append(f"- **{name}**: данные отсутствуют, прогоните сценарий.")
            continue
        data = load_json(path)
        summary = data.get("summary", {})
        latency = summary.get("latency_ms", {})
        status = pass_fail(
            float(summary.get("error_rate_pct", 0.0)),
            float(latency.get("p95", 0.0)),
            float(latency.get("p99", 0.0)),
            float(summary.get("missed_deadline_rate_pct", 0.0)),
        )
        lines.append(f"- **{name}**: `{status}` — {scenario_conclusion(status)}")

    final_status = "PASS" if overall and all(s == "PASS" for s in overall) else "WARNING"
    if any(s == "FAIL" for s in overall):
        final_status = "FAIL"

    lines.extend(
        [
            "",
            "## Общий итог",
            "",
            f"- Итоговый статус стенда: `{final_status}`",
            "- Рекомендация: для сравнения с ПЛК используйте в качестве рабочей границы последний сценарий со статусом `PASS`.",
            "",
            "## Файлы исходных данных",
            "",
        ]
    )

    for name in ["baseline", "workload", "spike"]:
        p = scenarios[name]
        if p:
            lines.append(f"- `{name}`: `{p.name}`")

    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"[report] markdown report: {REPORT_PATH}")


if __name__ == "__main__":
    main()
