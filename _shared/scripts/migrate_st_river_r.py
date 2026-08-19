#!/usr/bin/env python3
"""
st_river_r 迁移脚本
  源: SL323 (192.168.100.103) st_stbprp_b + st_river_r
  目标: 本地 powerelf_srm_yml  eq_equip_base + st_river_r

流程:
  1. 从 SL323 拉活跃河道站列表 (st_stbprp_b)
  2. 在本地 eq_equip_base 插入河道水位设备 (type_flag=7, 水位计)
  3. 建立 stcd → eq_id 映射
  4. 从 SL323 拉 st_river_r 数据 (2026-02-18 起), 逐站 INSERT 到本地

用法:
  python3 migrate_st_river_r.py [--start YYYY-MM-DD] [--end YYYY-MM-DD]
  默认: start=2026-02-18  end=2026-08-18
"""

import argparse
import importlib.util
import os
import sys
import time
from datetime import datetime

# ── 本地库 ──────────────────────────────────────────────────────────────────
LOCAL_ROOT = "/home/scada/powerelf-skills"
sys.path.insert(0, os.path.join(LOCAL_ROOT, "_shared", "lib"))
from db import query as local_query, get_connection as local_get_connection

# ── SL323（独立加载，避免与本地 db 模块缓存冲突）─────────────────────────────
for line in open("/opt/git/water-resources-skills/.env"):
    line = line.strip()
    if line and not line.startswith("#") and "=" in line:
        k, _, v = line.partition("=")
        v = v.split("#", 1)[0].strip().strip('"').strip("'")
        os.environ.setdefault(k.strip(), v)

_SL323_DB_PATH = "/root/.hermes/skills/water-resources/lib/db.py"
_spec = importlib.util.spec_from_file_location("wr_db", _SL323_DB_PATH)
_wr_db = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_wr_db)
sl323_query = _wr_db.query

OUTFILE = "/home/scada/powerelf-skills/output/st_river_r_migration.log"
os.makedirs(os.path.dirname(OUTFILE), exist_ok=True)

def log(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    with open(OUTFILE, "a") as f:
        f.write(line + "\n")

def insert_equip(eq_id, name, code, stcd, conn):
    """在本地 eq_equip_base 插入一条河道水位设备"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    # creator/updater 是 bigint, 用 1; tenant_id=1
    sql = """
        INSERT INTO eq_equip_base
          (id, name, code, type_flag, category, status_flag,
           deleted, tenant_id, creator, create_time, updater, update_time)
        VALUES
          (%s, %s, %s, 7, '0', 1, b'0', 1, 1, %s, 1, %s)
    """
    try:
        cur = conn.cursor()
        cur.execute(sql, (eq_id, name, code, now, now))
        conn.commit()
        return True
    except Exception as e:
        log(f"  INSERT 设备失败 eq_id={eq_id} code={code}: {e}")
        return False

def insert_river_row(conn, row):
    """将一行 SL323 st_river_r 转为本地格式并插入"""
    eq_id   = row["eq_id"]
    tm      = row["tm"]
    z       = row.get("z")
    q       = row.get("q")
    xsa     = row.get("xsa")
    xsavv   = row.get("xsavv")
    xsmxv   = row.get("xsmxv")
    flwchrcd= row.get("flwchrcd")
    stcd    = row["stcd"]
    now     = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    sql = """
        INSERT INTO st_river_r
          (eq_id, tm, z, q, xsa, xsavv, xsmxv, flwchrcd,
           stcd, eq_code, deleted, tenant_id, creator, create_time, updater, update_time)
        VALUES
          (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, b'0', 1,
           1, %s, 1, %s)
    """
    try:
        cur = conn.cursor()
        cur.execute(sql, (eq_id, tm, z, q, xsa, xsavv, xsmxv, flwchrcd,
                          stcd, stcd, now, now))
        return True
    except Exception:
        return False

def get_local_max_eq_id():
    r = local_query("SELECT MAX(id) mx FROM eq_equip_base", timeout=10)
    return (r[0]["mx"] or 400) if r else 400

def get_pymysql_conn_local():
    import pymysql
    from db import get_connection
    conn = get_connection()
    return conn

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", default="2026-02-18")
    parser.add_argument("--end",   default="2026-08-18")
    args = parser.parse_args()
    start_dt = args.start
    end_dt   = args.end

    log("=" * 60)
    log(f"st_river_r 迁移开始  窗口: {start_dt} ~ {end_dt}")
    log("=" * 60)

    # ── Step 1: 拉 SL323 活跃河道站 ────────────────────────────────────────
    log("[1/5] 从 SL323 拉活跃河道站 (st_stbprp_b) ...")
    stcd_map = {}  # stcd → stnm
    try:
        rows = sl323_query(
            f"SELECT a.stcd, a.stnm FROM st_stbprp_b a "
            f"JOIN st_river_r r ON a.stcd = r.stcd "
            f"WHERE a.stnm IS NOT NULL AND r.tm >= '{start_dt}' AND r.tm < '{end_dt}'",
            db="sl323", timeout=60
        )
        for r in rows:
            stcd_map[r["stcd"]] = r["stnm"]
        log(f"      找到 {len(stcd_map)} 个活跃河道站")
        for sc, nm in list(stcd_map.items())[:5]:
            log(f"        {sc}  {nm}")
        if len(stcd_map) > 5:
            log(f"        ... 共 {len(stcd_map)} 站")
    except Exception as e:
        log(f"[ERROR] 拉站列表失败: {e}")
        sys.exit(1)

    if not stcd_map:
        log("[ERROR] 无活跃站点，退出")
        sys.exit(1)

    # ── Step 2: 获取本地当前最大 eq_id，分配新 id ──────────────────────────
    log("[2/5] 分配 eq_id ...")
    base_id = get_local_max_eq_id()
    log(f"      当前最大 eq_id = {base_id}, 新 id 从 {base_id+1} 起")
    stcd_eqid = {}  # stcd → eq_id
    for i, stcd in enumerate(sorted(stcd_map.keys())):
        stcd_eqid[stcd] = base_id + 1 + i
    log(f"      分配了 {len(stcd_eqid)} 个 eq_id")

    # ── Step 3: 插入河道设备到 eq_equip_base ───────────────────────────────
    log("[3/5] 插入河道设备到 eq_equip_base ...")
    conn = get_pymysql_conn_local()
    ok_count = 0
    for stcd, eq_id in stcd_eqid.items():
        name = stcd_map[stcd]
        if insert_equip(eq_id, name, stcd, stcd, conn):
            ok_count += 1
    log(f"      成功插入 {ok_count}/{len(stcd_eqid)} 条设备")
    log(f"      设备 id 范围: {min(stcd_eqid.values())} ~ {max(stcd_eqid.values())}")

    # ── Step 4: 迁移 st_river_r 数据 ──────────────────────────────────────
    # 注意: SL323 的 query() 不支持参数化 (cur.execute(sql) 无 args),
    # 故 stcd 直接内插；stcd 来自 SL323 st_stbprp_b，可信。
    log("[4/5] 迁移 st_river_r 数据 ...")
    total_rows = 0
    total_ok   = 0
    total_err  = 0
    t0 = time.time()

    for stcd, eq_id in stcd_eqid.items():
        try:
            rows = sl323_query(
                f"SELECT stcd, tm, z, q, xsa, xsavv, xsmxv, flwchrcd "
                f"FROM st_river_r "
                f"WHERE stcd = '{stcd}' AND tm >= '{start_dt}' AND tm < '{end_dt}'",
                db="sl323", timeout=120
            )
        except Exception as e:
            log(f"  站 {stcd}: 拉数据失败 {e}")
            continue

        ok = 0
        err = 0
        for row in rows:
            row["eq_id"] = eq_id
            if insert_river_row(conn, row):
                ok += 1
            else:
                err += 1
        total_rows += len(rows)
        total_ok   += ok
        total_err  += err
        elapsed = time.time() - t0
        rate = total_ok / elapsed if elapsed > 0 else 0
        log(f"  站 {stcd} ({stcd_map[stcd]}): {ok} 条成功 {err} 条失败  "
            f"(累计 {total_ok}/{total_rows}  {rate:.0f} 行/秒)")

    conn.commit()
    conn.close()

    elapsed = time.time() - t0
    log("")
    log("[5/5] 迁移完成")
    log(f"      总耗时: {elapsed:.1f}s")
    log(f"      总行数: {total_rows}")
    log(f"      成功插入: {total_ok}")
    log(f"      失败: {total_err}")
    log(f"      平均速度: {total_ok/elapsed:.0f} 行/秒")

    # ── Step 5: 验证本地数据 ──────────────────────────────────────────────
    log("")
    log("[验证] 本地 st_river_r 最新状态 ...")
    r = local_query("SELECT COUNT(*) c, MAX(tm) mx FROM st_river_r WHERE deleted=0", timeout=10)
    log(f"      行数: {r[0]['c']}  最新时间: {r[0]['mx']}")

    log("=" * 60)
    log("迁移完成")
    log("=" * 60)

if __name__ == "__main__":
    main()
