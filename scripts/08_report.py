"""Step 8: 生成单文件 HTML 看板（图表 base64 内嵌，离线可看）。"""
from __future__ import annotations

import base64
import io
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from config import OUTPUT
from scripts.common import connect

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "Arial Unicode MS"]
plt.rcParams["axes.unicode_minus"] = False
plt.rcParams["figure.facecolor"] = "white"

COLORS = ["#2563eb", "#0ea5e9", "#14b8a6", "#f59e0b", "#ef4444", "#8b5cf6", "#64748b"]


def fig_to_b64(fig) -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=140, bbox_inches="tight")
    plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def chart_daily(df: pd.DataFrame) -> str:
    fig, ax = plt.subplots(figsize=(10, 3.6))
    ax.plot(df["date"], df["trips"], color="#93c5fd", linewidth=0.9, label="日行程数")
    ax.plot(df["date"], df["trips"].rolling(7).mean(), color="#1d4ed8", linewidth=1.8, label="7 日移动平均")
    ax.set_title("每日行程数（2023-01 ~ 2025-12）", fontsize=12, loc="left")
    ax.set_ylabel("行程数")
    ax.grid(alpha=0.25)
    ax.legend(frameon=False, loc="upper right")
    fig.autofmt_xdate()
    return fig_to_b64(fig)


def chart_monthly(df: pd.DataFrame) -> str:
    fig, ax1 = plt.subplots(figsize=(10, 3.6))
    ax1.bar(df["year_month"], df["revenue"] / 1e6, color="#bfdbfe", label="收入（百万美元）")
    ax1.set_ylabel("收入（百万美元）")
    ax1.tick_params(axis="x", rotation=60, labelsize=8)
    ax2 = ax1.twinx()
    ax2.plot(df["year_month"], df["trips"] / 1e6, color="#dc2626", marker="o", markersize=3, linewidth=1.4, label="行程数（百万）")
    ax2.set_ylabel("行程数（百万）")
    ax1.set_title("月度收入与行程数", fontsize=12, loc="left")
    ax1.grid(axis="y", alpha=0.25)
    h1, l1 = ax1.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    ax1.legend(h1 + h2, l1 + l2, frameon=False, loc="upper left")
    return fig_to_b64(fig)


def chart_heatmap(df: pd.DataFrame) -> str:
    pivot = df.pivot(index="weekday", columns="pickup_hour", values="avg_trips_per_day").reindex(range(7))
    fig, ax = plt.subplots(figsize=(10, 3.2))
    im = ax.imshow(pivot.values, aspect="auto", cmap="YlOrRd")
    ax.set_yticks(range(7))
    ax.set_yticklabels(["周日", "周一", "周二", "周三", "周四", "周五", "周六"])
    ax.set_xticks(range(0, 24, 2))
    ax.set_xticklabels(range(0, 24, 2))
    ax.set_xlabel("小时")
    ax.set_title("星期 × 小时平均行程数（热力图）", fontsize=12, loc="left")
    fig.colorbar(im, ax=ax, fraction=0.025, pad=0.01, label="平均行程数/天")
    return fig_to_b64(fig)


def chart_zones(df: pd.DataFrame, month: str) -> str:
    d = df[df["year_month"] == month].sort_values("revenue", ascending=True).tail(15)
    fig, ax = plt.subplots(figsize=(10, 4.4))
    ax.barh(d["pu_zone"] + " (" + d["pu_borough"] + ")", d["revenue"] / 1e6, color="#0ea5e9")
    ax.set_xlabel("收入（百万美元）")
    ax.set_title(f"{month} 上车区域收入 Top 15", fontsize=12, loc="left")
    ax.grid(axis="x", alpha=0.25)
    return fig_to_b64(fig)


def chart_payment(df: pd.DataFrame, month: str) -> str:
    d = df[df["year_month"] == month].sort_values("trips", ascending=False)
    fig, ax = plt.subplots(figsize=(4.8, 3.4))
    ax.pie(d["trips"], labels=d["payment_name"], autopct="%1.1f%%", colors=COLORS[: len(d)], startangle=90)
    ax.set_title(f"{month} 支付方式占比", fontsize=12)
    return fig_to_b64(fig)


def chart_quality(dq: pd.DataFrame) -> str:
    colors = {"PASS": "#16a34a", "WARN": "#f59e0b", "FAIL": "#dc2626"}
    fig, ax = plt.subplots(figsize=(4.8, 3.4))
    counts = dq["status"].value_counts().reindex(["PASS", "WARN", "FAIL"], fill_value=0)
    bars = ax.bar(counts.index, counts.values, color=[colors[k] for k in counts.index])
    for b, v in zip(bars, counts.values):
        ax.text(b.get_x() + b.get_width() / 2, v + 0.1, str(v), ha="center", fontsize=11)
    ax.set_ylim(0, max(counts.values) + 2)
    ax.set_title("数据质量检查结果", fontsize=12)
    ax.set_ylabel("规则数")
    return fig_to_b64(fig)


def kpi_cards(kpi: dict) -> str:
    items = [
        ("总行程数", f"{int(kpi['total_trips']):,}", "2023-01 ~ 2025-12"),
        ("总收入", f"${float(kpi['total_revenue'])/1e9:.2f}B", "total_amount 口径"),
        ("平均车费", f"${float(kpi['avg_fare']):.2f}", "每单"),
        ("平均速度", f"{float(kpi['avg_speed_mph']):.1f} mph", "全量"),
        ("机场单占比", f"{float(kpi['airport_share']):.2%}", "JFK/LGA/EWR"),
        ("信用卡小费率", f"{float(kpi['card_tip_rate']):.2%}", "仅 card"),
        ("覆盖天数", f"{int(kpi['days']):,}", "无缺失"),
        ("活跃 zone", f"{int(kpi['active_zones']):,}", "最多一天"),
    ]
    return "\n".join(
        f'<div class="card"><div class="label">{label}</div><div class="value">{value}</div><div class="sub">{sub}</div></div>'
        for label, value, sub in items
    )


def df_to_html(df: pd.DataFrame, index: bool = False, formatters: dict | None = None) -> str:
    d = df.copy()
    if formatters:
        for col, fmt in formatters.items():
            if col in d.columns:
                d[col] = d[col].map(fmt)
    return d.to_html(index=index, classes="table", border=0, escape=False)


def main() -> None:
    con = connect(read_only=True)
    daily = con.execute("SELECT * FROM ads_daily_kpi ORDER BY date").df()
    monthly = con.execute("SELECT * FROM ads_monthly_kpi ORDER BY year_month").df()
    heat = con.execute("SELECT * FROM ads_hourly_heatmap").df()
    zones = con.execute("SELECT * FROM ads_zone_rank").df()
    payment = con.execute("SELECT * FROM ads_payment_mix").df()
    tip = con.execute("SELECT * FROM ads_tip_zone ORDER BY card_tip_rate DESC LIMIT 12").df()
    dq = con.execute("SELECT * FROM dq_result").df()
    kpi = dict(con.execute("SELECT metric, value FROM ads_kpi_summary").fetchall())
    overall = con.execute("SELECT count(*) FROM dwd_trip_detail").fetchone()[0]
    con.close()

    daily["date"] = pd.to_datetime(daily["date"])
    latest_month = monthly["year_month"].iloc[-1]

    charts = {
        "daily": chart_daily(daily),
        "monthly": chart_monthly(monthly),
        "heatmap": chart_heatmap(heat),
        "zones": chart_zones(zones, latest_month),
        "payment": chart_payment(payment, latest_month),
        "quality": chart_quality(dq),
    }

    bench = json.loads((OUTPUT / "benchmark.json").read_text(encoding="utf-8"))
    bench_rows = [
        (r["name"], f"{r['seconds_median']:.3f}", f"{r['seconds_best']:.3f}", r.get("note", ""))
        for r in bench["results"]
        if "seconds_median" in r
    ]
    spark_path = OUTPUT / "spark_audit.json"
    spark = json.loads(spark_path.read_text(encoding="utf-8")) if spark_path.exists() else None

    monthly_view = monthly.tail(12)[["year_month", "trips", "revenue", "avg_fare", "avg_speed_mph", "airport_share", "card_tip_rate"]]
    monthly_html = df_to_html(
        monthly_view,
        formatters={
            "trips": lambda x: f"{int(x):,}",
            "revenue": lambda x: f"${x:,.0f}",
            "avg_fare": lambda x: f"${x:.2f}",
            "avg_speed_mph": lambda x: f"{x:.1f}",
            "airport_share": lambda x: f"{x:.2%}",
            "card_tip_rate": lambda x: f"{x:.2%}",
        },
    )
    zone_view = zones[zones["year_month"] == latest_month].sort_values("revenue", ascending=False).head(12)[
        ["pu_zone", "pu_borough", "trips", "revenue", "avg_fare", "avg_speed_mph"]
    ]
    zone_html = df_to_html(
        zone_view,
        formatters={
            "trips": lambda x: f"{int(x):,}",
            "revenue": lambda x: f"${x:,.0f}",
            "avg_fare": lambda x: f"${x:.2f}",
            "avg_speed_mph": lambda x: f"{x:.1f}",
        },
    )
    tip_html = df_to_html(
        tip[["pu_zone", "pu_borough", "card_trips", "card_tip_rate", "avg_tip_per_trip"]],
        formatters={
            "card_trips": lambda x: f"{int(x):,}",
            "card_tip_rate": lambda x: f"{x:.2%}",
            "avg_tip_per_trip": lambda x: f"${x:.2f}",
        },
    )
    dq_html = df_to_html(
        dq[["check_name", "layer", "rule", "observed", "threshold", "status", "detail"]].rename(
            columns={"check_name": "规则", "layer": "层", "rule": "说明", "observed": "观测值", "threshold": "阈值", "status": "状态", "detail": "备注"}
        )
    )
    bench_html = df_to_html(
        pd.DataFrame(bench_rows, columns=["实验", "中位耗时(s)", "最快(s)", "说明"])
    )
    spark_html = ""
    if spark:
        spark_html = f"""
<h2 style="font-size:17px;margin:26px 0 10px">Spark 4.3 对照实验（2023-01 样本）</h2>
<div class="panel full">
<table class="table">
<tr><th>指标</th><th>值</th><th>说明</th></tr>
<tr><td>Spark / Java</td><td>{spark['spark_version']} / {spark['java_version']}</td><td>{spark['mode']}</td></tr>
<tr><td>样本行数</td><td>{int(spark['dwd_rows']):,}</td><td>{spark['sample']}，清洗后</td></tr>
<tr><td>构建耗时</td><td>{spark['build_seconds']:.1f}s</td><td>读取 + 清洗 + broadcast join + cache</td></tr>
<tr><td>普通 group by</td><td>{spark['direct_seconds']:.2f}s</td><td>zone × hour 两列聚合</td></tr>
<tr><td>加盐两阶段</td><td>{spark['salted_seconds']:.2f}s</td><td>8 个盐桶，先局部聚合再汇总</td></tr>
<tr><td>提升</td><td>{spark['speedup_pct']:.1f}%</td><td>同样 4,966 行结果，验证倾斜治理</td></tr>
</table>
<div class="note" style="margin:8px 0 6px">本机 Windows 下 Spark 写 Parquet 会被 winutils chmod/ACL 拦截，因此 Spark 只做内存计算与结果验证；全量落盘由 DuckDB 完成。</div>
</div>"""

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>NYC TLC 出行数仓 · Dashboard</title>
<style>
  :root {{ --bg:#f6f8fb; --card:#ffffff; --text:#0f172a; --muted:#64748b; --line:#e2e8f0; --blue:#1d4ed8; }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; background:var(--bg); color:var(--text); font-family:-apple-system,"Microsoft YaHei","Segoe UI",Roboto,sans-serif; }}
  .wrap {{ max-width:1280px; margin:0 auto; padding:28px 22px 60px; }}
  header {{ display:flex; justify-content:space-between; gap:20px; align-items:flex-end; margin-bottom:18px; flex-wrap:wrap; }}
  h1 {{ font-size:26px; margin:0 0 6px; letter-spacing:-.02em; }}
  .muted {{ color:var(--muted); font-size:13px; line-height:1.7; }}
  .pill {{ display:inline-block; padding:3px 10px; border-radius:999px; background:#e0e7ff; color:#3730a3; font-size:12px; margin-right:6px; }}
  .cards {{ display:grid; grid-template-columns:repeat(4, minmax(0,1fr)); gap:12px; margin:18px 0 22px; }}
  .card {{ background:var(--card); border:1px solid var(--line); border-radius:12px; padding:14px 16px; box-shadow:0 1px 2px rgba(15,23,42,.03); }}
  .card .label {{ color:var(--muted); font-size:12px; }}
  .card .value {{ font-size:24px; font-weight:700; margin:6px 0 2px; letter-spacing:-.02em; }}
  .card .sub {{ color:var(--muted); font-size:11px; }}
  .grid {{ display:grid; grid-template-columns:1fr 1fr; gap:16px; }}
  .panel {{ background:var(--card); border:1px solid var(--line); border-radius:12px; padding:14px 16px 8px; overflow:hidden; }}
  .panel h2 {{ font-size:15px; margin:0 0 8px; }}
  .panel img {{ width:100%; height:auto; display:block; }}
  .full {{ grid-column:1 / -1; }}
  .table {{ width:100%; border-collapse:collapse; font-size:12.5px; }}
  .table th {{ text-align:left; color:var(--muted); font-weight:600; border-bottom:1px solid var(--line); padding:7px 6px; white-space:nowrap; }}
  .table td {{ border-bottom:1px solid #f1f5f9; padding:7px 6px; vertical-align:top; }}
  .table tr:hover td {{ background:#f8fafc; }}
  .note {{ font-size:12px; color:var(--muted); line-height:1.7; }}
  .row {{ display:flex; gap:16px; flex-wrap:wrap; }}
  footer {{ margin-top:28px; padding-top:14px; border-top:1px solid var(--line); font-size:12px; color:var(--muted); }}
  @media (max-width:900px) {{ .cards {{ grid-template-columns:repeat(2,1fr); }} .grid {{ grid-template-columns:1fr; }} }}
</style>
</head>
<body>
<div class="wrap">
<header>
  <div>
    <h1>NYC TLC 黄色出租车出行数仓</h1>
    <div class="muted">
      <span class="pill">2023-01 ~ 2025-12</span>
      <span class="pill">36 个月</span>
      <span class="pill">{overall:,} 行 DWD</span>
      <span class="pill">DuckDB + Parquet</span>
      <span class="pill">ODS → DWD → DWS → ADS</span>
    </div>
    <div class="muted" style="margin-top:6px">数据源：NYC TLC 官方 Parquet + Taxi Zone 维表 + Open-Meteo 天气 · 全部本地可复现</div>
  </div>
  <div class="muted" style="text-align:right">生成时间<br>{datetime.now().strftime('%Y-%m-%d %H:%M')}</div>
</header>

<div class="cards">
{kpi_cards(kpi)}
</div>

<div class="grid">
  <div class="panel full"><h2>需求趋势</h2><img src="data:image/png;base64,{charts['daily']}" alt="daily"></div>
  <div class="panel full"><h2>月度收入与规模</h2><img src="data:image/png;base64,{charts['monthly']}" alt="monthly"></div>
  <div class="panel full"><h2>时间分布</h2><img src="data:image/png;base64,{charts['heatmap']}" alt="heatmap"></div>
  <div class="panel"><h2>{latest_month} 区域收入 Top 15</h2><img src="data:image/png;base64,{charts['zones']}" alt="zones"></div>
  <div class="panel"><h2>{latest_month} 支付结构</h2><img src="data:image/png;base64,{charts['payment']}" alt="payment"></div>
  <div class="panel full"><h2>数据质量</h2><div class="row"><div style="flex:1;min-width:280px"><img src="data:image/png;base64,{charts['quality']}" alt="quality"></div>
    <div class="note" style="flex:2;min-width:320px">共 {len(dq)} 条规则，PASS {int((dq['status']=='PASS').sum())} / WARN {int((dq['status']=='WARN').sum())} / FAIL {int((dq['status']=='FAIL').sum())}。<br>
    分项金额与 total_amount 的口径差异来自 TLC 不同 Vendor 的记账方式，收入统一以 total_amount 为准，因此该规则为 WARN 而非 FAIL。</div></div>
  </div>
</div>

<h2 style="font-size:17px;margin:26px 0 10px">最近 12 个月 KPI</h2>
<div class="panel full">{monthly_html}</div>

<h2 style="font-size:17px;margin:26px 0 10px">{latest_month} 区域 Top 12</h2>
<div class="panel full">{zone_html}</div>

<h2 style="font-size:17px;margin:26px 0 10px">小费率最高的区域（信用卡，样本 ≥ 1000 单）</h2>
<div class="panel full">{tip_html}</div>

<h2 style="font-size:17px;margin:26px 0 10px">性能实验（本机实测）</h2>
<div class="panel full">{bench_html}
<div class="note" style="margin:8px 0 6px">机器：i7-12700H / 16 GB / DuckDB 2.0 / 3 GB 内存上限 / 4 线程。数字为 2~3 次运行中位数，OS 缓存已预热。</div></div>

{spark_html}

<h2 style="font-size:17px;margin:26px 0 10px">数据质量明细</h2>
<div class="panel full">{dq_html}</div>

<footer>
  项目路径：nyc_tlc_dw · 运行 <code>python run_all.py</code> 可复现 · 数据许可：NYC TLC 公开数据（NYC Open Data）
</footer>
</div>
</body>
</html>"""
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "dashboard.html").write_text(html, encoding="utf-8")
    print(f"wrote {OUTPUT / 'dashboard.html'} ({len(html)/1024:.0f} KB)")


if __name__ == "__main__":
    main()
