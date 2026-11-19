"""公共工具：连接 DuckDB、跑 SQL 文件、计时、落 JSON。"""
from __future__ import annotations

import json
import sys
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
LIB = ROOT / "lib"
if str(LIB) not in sys.path:
    sys.path.insert(0, str(LIB))

import duckdb

from config import DB_PATH, DUCKDB_MEMORY_LIMIT, DUCKDB_THREADS, TEMP_DIR


def connect(read_only: bool = False) -> duckdb.DuckDBPyConnection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(DB_PATH), read_only=read_only)
    con.execute(f"SET memory_limit='{DUCKDB_MEMORY_LIMIT}'")
    con.execute(f"SET threads={DUCKDB_THREADS}")
    con.execute(f"SET temp_directory='{TEMP_DIR.as_posix()}'")
    con.execute("SET preserve_insertion_order=false")
    return con


def run_sql_file(con: duckdb.DuckDBPyConnection, path: Path, **params: Any) -> None:
    """跑 .sql 文件，支持 {{name}} 占位符（路径/常量）。"""
    sql = path.read_text(encoding="utf-8")
    for key, value in params.items():
        sql = sql.replace("{{" + key + "}}", str(value))
    # 允许一个文件里有多条语句
    for stmt in split_statements(sql):
        con.execute(stmt)


def split_statements(sql: str) -> Iterable[str]:
    """按分号切 SQL，忽略注释和字符串里的分号。"""
    buf: list[str] = []
    in_single = False
    in_line_comment = False
    in_block_comment = False
    i = 0
    while i < len(sql):
        ch = sql[i]
        nxt = sql[i + 1] if i + 1 < len(sql) else ""
        if in_line_comment:
            buf.append(ch)
            if ch == "\n":
                in_line_comment = False
        elif in_block_comment:
            buf.append(ch)
            if ch == "*" and nxt == "/":
                buf.append(nxt)
                i += 1
                in_block_comment = False
        elif in_single:
            buf.append(ch)
            if ch == "'":
                if nxt == "'":
                    buf.append(nxt)
                    i += 1
                else:
                    in_single = False
        else:
            if ch == "-" and nxt == "-":
                buf.append(ch)
                buf.append(nxt)
                i += 1
                in_line_comment = True
            elif ch == "/" and nxt == "*":
                buf.append(ch)
                buf.append(nxt)
                i += 1
                in_block_comment = True
            elif ch == "'":
                buf.append(ch)
                in_single = True
            elif ch == ";":
                stmt = "".join(buf).strip()
                if stmt:
                    yield stmt
                buf = []
            else:
                buf.append(ch)
        i += 1
    stmt = "".join(buf).strip()
    if stmt:
        yield stmt


def scalar(con: duckdb.DuckDBPyConnection, sql: str) -> Any:
    row = con.execute(sql).fetchone()
    return None if row is None else row[0]


def one_row(con: duckdb.DuckDBPyConnection, sql: str) -> dict[str, Any]:
    cur = con.execute(sql)
    cols = [d[0] for d in cur.description]
    row = cur.fetchone()
    return dict(zip(cols, row)) if row else {}


def rows(con: duckdb.DuckDBPyConnection, sql: str) -> list[dict[str, Any]]:
    cur = con.execute(sql)
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def table(con: duckdb.DuckDBPyConnection, sql: str) -> list[list[Any]]:
    cur = con.execute(sql)
    return [list(r) for r in cur.fetchall()]


def json_dump(obj: Any, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def fmt_sec(seconds: float) -> str:
    return f"{seconds:.2f}s" if seconds < 60 else f"{seconds/60:.2f}min"


@contextmanager
def timer(label: str):
    t0 = time.perf_counter()
    print(f"[start] {label}", flush=True)
    try:
        yield
    finally:
        dt = time.perf_counter() - t0
        print(f"[done ] {label} {fmt_sec(dt)}", flush=True)


def ensure_dirs(*paths: Path) -> None:
    for p in paths:
        p.mkdir(parents=True, exist_ok=True)


def md_table(headers: list[str], data: list[list[Any]]) -> str:
    out = ["| " + " | ".join(headers) + " |", "|" + "|".join(["---"] * len(headers)) + "|"]
    for row in data:
        out.append("| " + " | ".join("" if v is None else str(v) for v in row) + " |")
    return "\n".join(out)
