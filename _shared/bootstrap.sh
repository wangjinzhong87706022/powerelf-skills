#!/usr/bin/env bash
# hermes-skills 共享引导：统一导出 DB_URL，消除各 skill CLI 连接风格不一致。
#
# 背景：inspection 的 impl 工具用 `--db "$DB_URL"`，但 DB_URL 从未被定义；
# data-governance 用内联 `mysql+pymysql://${POWERELF_DB_USER}:...@${POWERELF_DB_HOST}:3306/...`
# （且写死 3306，忽略 POWERELF_DB_PORT）。本脚本以 _shared/lib/db.py 为单一来源，
# 统一导出 DB_URL，两条风格收敛为一处。
#
# 用法（在执行任意 skill 的 impl 工具前）:
#   source <hermes-skills>/_shared/bootstrap.sh
#   python3 powerelf-data-governance/impl/anomaly_detector.py --db "$DB_URL" ...
#
# 依赖: python3 + pymysql；POWERELF_DB_* 或 SRM_DB_* 环境变量（见 _shared/lib/db.py）。

_HERE="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
export DB_URL="$(python3 -c "import sys; sys.path.insert(0,'$_HERE/lib'); from db import get_sqlalchemy_url; print(get_sqlalchemy_url())" 2>/dev/null)"

if [ -n "$DB_URL" ]; then
  echo "[bootstrap] DB_URL 已设置（来自 _shared/lib/db.py）"
else
  echo "[bootstrap] ⚠️ DB_URL 为空 —— 请先设置 POWERELF_DB_* / SRM_DB_* 环境变量" >&2
fi

# chatbi 只读 URL（7 层护栏层1 DB 兜底，来自 get_readonly_sqlalchemy_url）
export RO_DB_URL="$(python3 -c "import sys; sys.path.insert(0,'$_HERE/lib'); from db import get_readonly_sqlalchemy_url; print(get_readonly_sqlalchemy_url())" 2>/dev/null)"

if [ -n "$RO_DB_URL" ]; then
  echo "[bootstrap] RO_DB_URL 已设置（chatbi 只读，来自 get_readonly_sqlalchemy_url）"
else
  echo "[bootstrap] ⚠️ RO_DB_URL 为空 —— chatbi query_exec 将后备主账号" >&2
fi
