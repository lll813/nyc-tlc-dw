"""Step 0: 下载 NYC TLC 黄色出租车月度 Parquet + zone 维表 + 天气。

数据源（官方、免登录）：
- https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page
- CloudFront 直链：https://d37ci6vzurychx.cloudfront.net/trip-data/yellow_tripdata_YYYY-MM.parquet
- Zone 维表：https://d37ci6vzurychx.cloudfront.net/misc/taxi_zone_lookup.csv
- 天气：Open-Meteo Archive API（免费、无需 key）

用法：
    python scripts/00_download.py            # 断点续传，已存在则跳过
    python scripts/00_download.py --force    # 强制重下
"""
from __future__ import annotations

import argparse
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import requests

from config import END_YEAR, MONTHS, RAW, START_YEAR
from scripts.common import fmt_sec

BASE = "https://d37ci6vzurychx.cloudfront.net"
ZONE_URL = f"{BASE}/misc/taxi_zone_lookup.csv"
WEATHER_URL = "https://archive-api.open-meteo.com/v1/archive"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) nyc-tlc-dw/1.0"}


def download(url: str, out: Path, force: bool = False, min_bytes: int = 1_000_000) -> tuple[str, int, float]:
    if out.exists() and out.stat().st_size >= min_bytes and not force:
        return out.name, out.stat().st_size, 0.0
    t0 = time.time()
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(out.suffix + ".part")
    last_err: Exception | None = None
    for attempt in range(3):
        try:
            with requests.get(url, headers=UA, stream=True, timeout=180) as r:
                r.raise_for_status()
                with open(tmp, "wb") as f:
                    for chunk in r.iter_content(4 << 20):
                        f.write(chunk)
            tmp.replace(out)
            return out.name, out.stat().st_size, time.time() - t0
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            if tmp.exists():
                tmp.unlink(missing_ok=True)
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"download failed: {url}: {last_err}")


def download_weather() -> Path:
    out = RAW / "weather_daily.csv"
    if out.exists() and out.stat().st_size > 10_000:
        print(f"[skip ] {out.name}")
        return out
    params = {
        "latitude": 40.7128,
        "longitude": -74.0060,
        "start_date": f"{START_YEAR}-01-01",
        "end_date": f"{END_YEAR}-12-31",
        "daily": "temperature_2m_mean,precipitation_sum,snowfall_sum,wind_speed_10m_max",
        "timezone": "America/New_York",
    }
    r = requests.get(WEATHER_URL, params=params, headers=UA, timeout=60)
    r.raise_for_status()
    daily = r.json()["daily"]
    lines = ["date,temp_mean_c,precip_mm,snow_mm,wind_max_kmh"]
    for i, date in enumerate(daily["time"]):
        vals = [
            daily["temperature_2m_mean"][i],
            daily["precipitation_sum"][i],
            daily["snowfall_sum"][i],
            daily["wind_speed_10m_max"][i],
        ]
        lines.append(",".join("" if v is None else str(v) for v in [date, *vals]))
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"[weather] {out.name} {len(lines)-1} days")
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    RAW.mkdir(parents=True, exist_ok=True)
    tasks = []
    for year, month in MONTHS:
        name = f"yellow_tripdata_{year}-{month:02d}.parquet"
        tasks.append((name, f"{BASE}/trip-data/{name}", 1_000_000))
    tasks.append(("taxi_zone_lookup.csv", ZONE_URL, 1_000))

    t0 = time.time()
    total_bytes = 0
    with ThreadPoolExecutor(max_workers=4) as ex:
        futs = [ex.submit(download, url, RAW / name, args.force, min_bytes) for name, url, min_bytes in tasks]
        for fut in as_completed(futs):
            name, size, sec = fut.result()
            total_bytes += size
            print(f"[ok   ] {name:36s} {size/1024/1024:6.1f} MB {sec:5.1f}s", flush=True)
    download_weather()

    files = sorted(RAW.glob("yellow_tripdata_*.parquet"))
    print(
        f"\n[done] {len(files)} monthly files, "
        f"{sum(f.stat().st_size for f in files)/1024**3:.2f} GB, {fmt_sec(time.time()-t0)}"
    )


if __name__ == "__main__":
    main()
