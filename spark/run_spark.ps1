# 在本机跑 Spark 4.3 对照实验（不依赖 Docker）
# 用法：powershell -ExecutionPolicy Bypass -File spark/run_spark.ps1
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$jdk = Join-Path $root "tools\jdk-21.0.2"
$spark = Join-Path $root "tools\spark-4.3.0-bin-hadoop3"
$hadoop = Join-Path $root "tools\hadoop"

if (-not (Test-Path $jdk)) { throw "JDK 21 not found: $jdk" }
if (-not (Test-Path $spark)) { throw "Spark not found: $spark" }

$env:JAVA_HOME = (Resolve-Path $jdk).Path
$env:HADOOP_HOME = (Resolve-Path $hadoop).Path
$env:PATH = "$env:JAVA_HOME\bin;$env:HADOOP_HOME\bin;$env:PATH"
$env:PYSPARK_PYTHON = "D:\Python\python.exe"
$env:PYSPARK_DRIVER_PYTHON = "D:\Python\python.exe"
$env:PYTHONPATH = (Join-Path $root "lib")

& (Join-Path $spark "bin\spark-submit.cmd") `
    --master "local[2]" `
    --driver-memory "2g" `
    --conf "spark.sql.shuffle.partitions=8" `
    --conf "spark.sql.adaptive.enabled=true" `
    (Join-Path $PSScriptRoot "spark_dwd_sample.py")
