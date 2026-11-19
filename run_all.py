"""一键编排：下载 → 维度 → ODS → DWD → DWS → ADS → 质量 → 性能 → 看板。

用法：
    python run_all.py                 # 全量（已下载则跳过下载）
    python run_all.py --skip-bench    # 跳过 CSV/性能实验（省 2~3 分钟）
    python run_all.py --only 03,04    # 只跑指定步骤
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PY = sys.executable
STEPS = [
    ("00", "下载数据", "scripts/00_download.py"),
    ("01", "维度层", "scripts/01_build_dim.py"),
    ("02", "ODS", "scripts/02_build_ods.py"),
    ("03", "DWD", "scripts/03_build_dwd.py"),
    ("04", "DWS", "scripts/04_build_dws.py"),
    ("05", "ADS", "scripts/05_build_ads.py"),
    ("06", "数据质量", "scripts/06_quality.py"),
    ("07", "性能实验", "scripts/07_benchmark.py"),
    ("08", "看板", "scripts/08_report.py"),
]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-download", action="store_true")
    parser.add_argument("--skip-bench", action="store_true")
    parser.add_argument("--only", default="", help="逗号分隔步骤号，如 03,04,05")
    args = parser.parse_args()

    only = {s.strip() for s in args.only.split(",") if s.strip()}
    manifest = {"started_at": datetime.now().isoformat(timespec="seconds"), "steps": []}
    t_all = time.perf_counter()

    for code, name, script in STEPS:
        if only and code not in only:
            continue
        if args.skip_download and code == "00":
            continue
        if args.skip_bench and code == "07":
            continue
        t0 = time.perf_counter()
        print(f"\n{'='*72}\n[{code}] {name}\n{'='*72}", flush=True)
        proc = subprocess.run([PY, str(ROOT / script)], cwd=ROOT)
        elapsed = time.perf_counter() - t0
        manifest["steps"].append({"code": code, "name": name, "seconds": round(elapsed, 2), "returncode": proc.returncode})
        if proc.returncode != 0:
            manifest["status"] = "FAILED"
            manifest["failed_step"] = code
            break
    else:
        manifest["status"] = "OK"

    manifest["elapsed_seconds"] = round(time.perf_counter() - t_all, 2)
    manifest["finished_at"] = datetime.now().isoformat(timespec="seconds")
    (ROOT / "output").mkdir(exist_ok=True)
    (ROOT / "output" / "run_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n{'='*72}")
    print(f"status={manifest['status']}  elapsed={manifest['elapsed_seconds']/60:.1f} min")
    for s in manifest["steps"]:
        print(f"  {s['code']} {s['name']:8s} {s['seconds']:8.1f}s  rc={s['returncode']}")
    if manifest["status"] != "OK":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
