"""最小 Spark 读文件测试：排查 Windows 本地路径 ACL / winutils 问题。"""
import sys
from pyspark.sql import SparkSession

path = sys.argv[1]
spark = SparkSession.builder.master("local[2]").appName("read-test").config("spark.driver.memory", "1g").getOrCreate()
spark.sparkContext.setLogLevel("WARN")
print("reading", path)
df = spark.read.parquet(path)
print("count", df.count())
df.printSchema()
spark.stop()
