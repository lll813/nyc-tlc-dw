"""Airflow DAG：把 run_all.py 的步骤拆成可重试、可回填的任务。

本机不装 Airflow（Windows 安装成本高），此文件用于展示生产调度写法；
在 Linux/Airflow 环境中把 PROJECT 指向项目目录即可。
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.bash import BashOperator

PROJECT = os.environ.get("TLC_PROJECT", "/opt/airflow/nyc_tlc_dw")
PYTHON = os.environ.get("TLC_PYTHON", "python")

default_args = {
    "owner": "data-eng",
    "depends_on_past": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
    "execution_timeout": timedelta(hours=2),
}

with DAG(
    dag_id="nyc_tlc_dw_daily",
    description="NYC TLC 出行数仓：下载 → ODS → DWD → DWS → ADS → 质量 → 看板",
    default_args=default_args,
    start_date=datetime(2026, 1, 1),
    schedule="0 3 * * *",          # 每天 03:00
    catchup=False,
    max_active_runs=1,
    tags=["data-warehouse", "tlc", "duckdb"],
) as dag:
    download = BashOperator(
        task_id="download",
        bash_command=f"cd {PROJECT} && {PYTHON} scripts/00_download.py",
    )
    dim = BashOperator(task_id="dim", bash_command=f"cd {PROJECT} && {PYTHON} scripts/01_build_dim.py")
    ods = BashOperator(task_id="ods", bash_command=f"cd {PROJECT} && {PYTHON} scripts/02_build_ods.py")
    dwd = BashOperator(task_id="dwd", bash_command=f"cd {PROJECT} && {PYTHON} scripts/03_build_dwd.py")
    dws = BashOperator(task_id="dws", bash_command=f"cd {PROJECT} && {PYTHON} scripts/04_build_dws.py")
    ads = BashOperator(task_id="ads", bash_command=f"cd {PROJECT} && {PYTHON} scripts/05_build_ads.py")
    quality = BashOperator(
        task_id="quality_gate",
        bash_command=(
            f"cd {PROJECT} && {PYTHON} scripts/06_quality.py && "
            f"{PYTHON} -c \"import json;r=json.load(open('output/quality_report.json'));"
            f"raise SystemExit(0 if r['overall']!='FAIL' else 1)\""
        ),
        retries=0,
    )
    report = BashOperator(task_id="report", bash_command=f"cd {PROJECT} && {PYTHON} scripts/08_report.py")

    download >> dim >> ods >> dwd >> dws >> ads >> quality >> report
