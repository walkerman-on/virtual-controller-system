import json
import math
import os
import random
import statistics
import threading
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List

from opcua import Client


@dataclass
class WorkerStats:
    cycles: int = 0
    errors: int = 0
    missed_deadlines: int = 0
    latencies_ms: List[float] = None

    def __post_init__(self):
        if self.latencies_ms is None:
            self.latencies_ms = []


def percentile(sorted_values: List[float], q: float) -> float:
    if not sorted_values:
        return 0.0
    if len(sorted_values) == 1:
        return sorted_values[0]
    idx = (len(sorted_values) - 1) * q
    lo = math.floor(idx)
    hi = math.ceil(idx)
    if lo == hi:
        return sorted_values[int(idx)]
    return sorted_values[lo] + (sorted_values[hi] - sorted_values[lo]) * (idx - lo)


def load_node_ids(config_path: str) -> Dict[str, str]:
    cfg = json.loads(Path(config_path).read_text(encoding="utf-8"))
    pv = cfg["opcua_variables"]["process_variables"]
    return {
        "PV_level": pv["PV_level"]["node_id"],
        "SP_level": pv["SP_level"]["node_id"],
        "OP_valve": pv["OP_valve"]["node_id"],
    }


def run_worker(
    worker_id: int,
    server_url: str,
    duration_sec: int,
    cycle_ms: int,
    write_enabled: bool,
    node_ids: Dict[str, str],
    out_stats: Dict[int, WorkerStats],
) -> None:
    stats = WorkerStats()
    deadline_s = cycle_ms / 1000.0
    stop_at = time.monotonic() + duration_sec
    jitter = random.Random(worker_id)
    client = Client(server_url)

    try:
        client.connect()
        pv_node = client.get_node(node_ids["PV_level"])
        sp_node = client.get_node(node_ids["SP_level"])
        op_node = client.get_node(node_ids["OP_valve"])

        while time.monotonic() < stop_at:
            t0 = time.perf_counter()
            try:
                pv = float(pv_node.get_value())
                sp = float(sp_node.get_value())
                if write_enabled:
                    target = max(0.0, min(100.0, 50.0 + (sp - pv) * 10.0 + jitter.uniform(-1.0, 1.0)))
                    op_node.set_value(target)
            except Exception:
                stats.errors += 1

            elapsed = time.perf_counter() - t0
            elapsed_ms = elapsed * 1000.0
            stats.cycles += 1
            stats.latencies_ms.append(elapsed_ms)
            if elapsed > deadline_s:
                stats.missed_deadlines += 1
                continue
            time.sleep(deadline_s - elapsed)
    except Exception:
        stats.errors += 1
    finally:
        try:
            client.disconnect()
        except Exception:
            pass
        out_stats[worker_id] = stats


def aggregate(stats_by_worker: Dict[int, WorkerStats], profile: Dict[str, object]) -> Dict[str, object]:
    total_cycles = sum(s.cycles for s in stats_by_worker.values())
    total_errors = sum(s.errors for s in stats_by_worker.values())
    total_missed = sum(s.missed_deadlines for s in stats_by_worker.values())
    all_latencies = [v for s in stats_by_worker.values() for v in s.latencies_ms]
    all_latencies.sort()

    result = {
        "profile": profile,
        "summary": {
            "workers": len(stats_by_worker),
            "total_cycles": total_cycles,
            "total_errors": total_errors,
            "error_rate_pct": (total_errors / total_cycles * 100.0) if total_cycles else 0.0,
            "missed_deadlines": total_missed,
            "missed_deadline_rate_pct": (total_missed / total_cycles * 100.0) if total_cycles else 0.0,
            "latency_ms": {
                "avg": statistics.fmean(all_latencies) if all_latencies else 0.0,
                "p50": percentile(all_latencies, 0.50),
                "p95": percentile(all_latencies, 0.95),
                "p99": percentile(all_latencies, 0.99),
                "max": all_latencies[-1] if all_latencies else 0.0,
            },
        },
    }
    return result


def main() -> None:
    server_url = os.getenv("OPCUA_SERVER_URL", "opc.tcp://opcua-server:4840/freeopcua/server/")
    config_path = os.getenv("CONFIG_PATH", "/app/config.json")
    workers = int(os.getenv("CONTROLLERS", "10"))
    cycle_ms = int(os.getenv("CYCLE_MS", "1000"))
    duration_sec = int(os.getenv("DURATION_SEC", "180"))
    write_enabled = os.getenv("WRITE_ENABLED", "false").lower() in {"1", "true", "yes"}
    result_file = os.getenv("RESULT_FILE", "/app/results/latest.json")

    node_ids = load_node_ids(config_path)
    stats_by_worker: Dict[int, WorkerStats] = {}
    threads = []

    print(
        f"[load-test] start workers={workers} cycle_ms={cycle_ms} duration_sec={duration_sec} "
        f"write_enabled={write_enabled} server_url={server_url}"
    )

    for i in range(workers):
        t = threading.Thread(
            target=run_worker,
            args=(i, server_url, duration_sec, cycle_ms, write_enabled, node_ids, stats_by_worker),
            daemon=True,
        )
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    profile = {
        "controllers": workers,
        "cycle_ms": cycle_ms,
        "duration_sec": duration_sec,
        "write_enabled": write_enabled,
        "server_url": server_url,
    }
    report = aggregate(stats_by_worker, profile)
    Path(result_file).parent.mkdir(parents=True, exist_ok=True)
    Path(result_file).write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    print(f"[load-test] report saved: {result_file}")


if __name__ == "__main__":
    main()
