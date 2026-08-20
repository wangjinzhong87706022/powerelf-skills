#!/usr/bin/env python3
"""test_freeze_guard.py — 代码冻结护栏单测（临时 git 仓库 fixture，不碰真实仓库）。

跑法：python3 docs/test_freeze_guard.py   （标准库 only）

覆盖（2026-08-20 护栏升级，docs/eval-mutation-forensics-20260820.md）：
  - 检测：M/D（tracked 改/删）、A（新增 untracked 代码）、A+（评测中 git add）、
    U~/U-（基线 untracked 改/删）、豁免（原样 git add 不报、OK 清单不报）
  - 恢复：内容快照回写往返一致（含基线 untracked）、A 删除、A+ 出索引、
    rm --cached 后内容未漂移不误报
  - 内容快照落盘：manifest.json + tree/untracked 镜像
  - 报告去污染：CODE-MUTATED / DRY-RUN 不进均分与维度统计

fixture 技巧：runner 的护栏函数读模块级 _PROJECT_ROOT，setUp 里整体指向临时仓库，
tearDown 恢复——runner 本体无需参数化。
"""
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("hr", _HERE / "hermes_eval_runner.py")
hr = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(hr)


class FreezeGuardTest(unittest.TestCase):
    def setUp(self):
        self.repo = Path(tempfile.mkdtemp(prefix="freeze-guard-repo-"))
        self.git("init", "-q")
        self.git("config", "user.email", "t@t")
        self.git("config", "user.name", "t")
        # 复刻真实布局：guarded 前缀下的 tracked 文件 + 评测题面
        (self.repo / "powerelf-data-governance").mkdir()
        (self.repo / "_shared/lib").mkdir(parents=True)
        (self.repo / "_shared/scripts").mkdir(parents=True)
        (self.repo / "docs").mkdir()
        (self.repo / "powerelf-data-governance" / "SKILL.md").write_text("skill v1\n")
        (self.repo / "_shared/lib/db.py").write_text("DB=1\n")
        (self.repo / "docs/eval-questions-master.json").write_text("{}\n")
        self.git("add", "-A")
        self.git("commit", "-qm", "init")
        # 先把 runner 指到 fixture 仓库（护栏函数读模块级 _PROJECT_ROOT）
        self._orig_root = hr._PROJECT_ROOT
        hr._PROJECT_ROOT = self.repo
        # 基线 untracked：评测启动前已存在的人工未提交脚本（合法起点）
        (self.repo / "_shared/scripts/human_wip.py").write_text("wip\n")
        # untracked 目录（如 __pycache__）不得让基线崩掉（曾致护栏整体关闭）
        (self.repo / "_shared/hooks/__pycache__").mkdir(parents=True)
        (self.repo / "_shared/hooks/__pycache__/x.pyc").write_text("bin\n")

        self.snap = Path(tempfile.mkdtemp(prefix="freeze-guard-snap-"))
        self.b = hr.snapshot_guarded_state(snapshot_dir=self.snap / "freeze-baseline")
        self.assertIsNotNone(self.b, "基线快照失败（fixture 或护栏实现回归）")
        # untracked 目录（porcelain 折叠为 `_shared/hooks/`）应展开为内部文件，
        # 目录路径本身不得进基线（否则 hash/copy 目录会fatal/IsADirectory）
        self.assertEqual(
            self.b["untracked"],
            ["_shared/hooks/__pycache__/x.pyc", "_shared/scripts/human_wip.py"],
            "untracked 目录条目应展开为内部真实文件")

    def tearDown(self):
        hr._PROJECT_ROOT = self._orig_root
        shutil.rmtree(self.repo, ignore_errors=True)
        shutil.rmtree(self.snap, ignore_errors=True)

    def git(self, *a):
        r = subprocess.run(["git", "-C", str(self.repo), *a],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, f"git {a}: {r.stderr}")
        return r

    # ---------- 检测 ----------

    def test_clean_tree_detects_nothing(self):
        self.assertEqual(hr.detect_code_mutation(self.b), [])

    def test_detect_M_tracked_modified(self):
        (self.repo / "powerelf-data-governance/SKILL.md").write_text("skill MUTATED\n")
        self.assertEqual(hr.detect_code_mutation(self.b), ["M powerelf-data-governance/SKILL.md"])

    def test_detect_D_tracked_deleted(self):
        (self.repo / "_shared/lib/db.py").unlink()
        self.assertIn("D _shared/lib/db.py", hr.detect_code_mutation(self.b))

    def test_detect_A_new_untracked_code(self):
        (self.repo / "_shared/scripts/agent_new.py").write_text("x\n")
        self.assertEqual(hr.detect_code_mutation(self.b), ["A _shared/scripts/agent_new.py"])

    def test_detect_A_new_untracked_report_md_exempt(self):
        # OK 清单：guarded 前缀下 untracked .md、根级 report_*/output/ 都不算代码污染
        (self.repo / "powerelf-data-governance/notes.md").write_text("n\n")
        (self.repo / "report_run1.md").write_text("r\n")
        (self.repo / "output").mkdir()
        (self.repo / "output/result.json").write_text("{}\n")
        self.assertEqual(hr.detect_code_mutation(self.b), [])

    def test_git_add_unchanged_untracked_exempt(self):
        # 盲区④豁免：人工 untracked 文件被原样 git add（内容未变）→ 不报
        self.git("add", "--", "_shared/scripts/human_wip.py")
        self.assertEqual(hr.detect_code_mutation(self.b), [])

    def test_git_add_new_file_is_A_plus(self):
        (self.repo / "_shared/scripts/staged_new.py").write_text("new\n")
        self.git("add", "--", "_shared/scripts/staged_new.py")
        self.assertEqual(hr.detect_code_mutation(self.b), ["A+ _shared/scripts/staged_new.py"])

    def test_git_add_modified_untracked_is_A_plus_and_U_tilde(self):
        self.git("add", "--", "_shared/scripts/human_wip.py")
        (self.repo / "_shared/scripts/human_wip.py").write_text("drifted\n")
        muts = hr.detect_code_mutation(self.b)
        self.assertIn("A+ _shared/scripts/human_wip.py", muts)
        self.assertIn("U~ _shared/scripts/human_wip.py", muts)

    def test_untracked_content_drift(self):
        (self.repo / "_shared/scripts/human_wip.py").write_text("drift\n")
        self.assertEqual(hr.detect_code_mutation(self.b), ["U~ _shared/scripts/human_wip.py"])

    def test_untracked_deleted(self):
        (self.repo / "_shared/scripts/human_wip.py").unlink()
        self.assertEqual(hr.detect_code_mutation(self.b), ["U- _shared/scripts/human_wip.py"])

    def test_rm_cached_unchanged_not_flagged(self):
        # tracked 文件被移出索引但内容未变 → 代码面未漂移，不报（防级联误杀）
        self.git("rm", "--cached", "-q", "--", "_shared/lib/db.py")
        self.assertEqual(hr.detect_code_mutation(self.b), [])

    # ---------- 恢复 ----------

    def test_restore_M_roundtrip(self):
        p = self.repo / "powerelf-data-governance/SKILL.md"
        p.write_text("skill MUTATED\n")
        acts, failed = hr.restore_guarded_state(self.b)
        self.assertEqual(failed, [])
        self.assertEqual(hr.detect_code_mutation(self.b), [])
        self.assertEqual(p.read_text(), "skill v1\n")

    def test_restore_D_roundtrip(self):
        p = self.repo / "_shared/lib/db.py"
        p.unlink()
        acts, failed = hr.restore_guarded_state(self.b)
        self.assertEqual(failed, [])
        self.assertEqual(hr.detect_code_mutation(self.b), [])
        self.assertEqual(p.read_text(), "DB=1\n")

    def test_restore_A_deletes_new_file(self):
        p = self.repo / "_shared/scripts/agent_new.py"
        p.write_text("x\n")
        acts, failed = hr.restore_guarded_state(self.b)
        self.assertEqual(failed, [])
        self.assertFalse(p.exists())
        self.assertEqual(hr.detect_code_mutation(self.b), [])

    def test_restore_A_plus_unstages_and_deletes(self):
        p = self.repo / "_shared/scripts/staged_new.py"
        p.write_text("new\n")
        self.git("add", "--", "_shared/scripts/staged_new.py")
        hr.restore_guarded_state(self.b)
        self.assertFalse(p.exists())
        self.assertEqual(self.git("ls-files", "--", "_shared/scripts/staged_new.py").stdout.strip(), "")
        self.assertEqual(hr.detect_code_mutation(self.b), [])

    def test_restore_git_add_plus_drift_full_roundtrip(self):
        p = self.repo / "_shared/scripts/human_wip.py"
        self.git("add", "--", str(p.relative_to(self.repo)))
        p.write_text("drifted\n")
        acts, failed = hr.restore_guarded_state(self.b)
        self.assertEqual(failed, [])
        self.assertEqual(hr.detect_code_mutation(self.b), [])
        self.assertEqual(p.read_text(), "wip\n")
        self.assertEqual(self.git("ls-files", "--", "_shared/scripts/human_wip.py").stdout.strip(), "",
                         "应已移出索引恢复为 untracked")
        # porcelain 会把全 untracked 目录折叠成 `?? _shared/scripts/`
        self.assertIn("?? _shared/scripts/",
                      self.git("status", "--porcelain").stdout)

    def test_restore_without_snapshot_reports_failure(self):
        p = self.repo / "powerelf-data-governance/SKILL.md"
        p.write_text("MUT\n")
        b2 = dict(self.b)
        b2["snapshot_dir"] = None
        acts, failed = hr.restore_guarded_state(b2)
        self.assertIn("no_snapshot", failed)
        self.assertEqual(p.read_text(), "MUT\n", "无快照时不得乱动工作区")

    # ---------- 内容快照落盘 ----------

    def test_snapshot_manifest_and_mirrors(self):
        man = json.loads((self.snap / "freeze-baseline/manifest.json").read_text())
        self.assertEqual(man["project_root"], str(self.repo))
        self.assertIn("powerelf-data-governance/SKILL.md", man["tracked"])
        self.assertIn("_shared/scripts/human_wip.py", man["untracked"])
        mirror = self.snap / "freeze-baseline/tree/powerelf-data-governance/SKILL.md"
        self.assertEqual(mirror.read_text(), "skill v1\n")
        um = self.snap / "freeze-baseline/untracked/_shared/scripts/human_wip.py"
        self.assertEqual(um.read_text(), "wip\n")

    def test_snapshot_dir_inside_repo_rejected(self):
        # 2026-08-20 事故回归：快照落仓库 output/ 下，SKILL.md 镜像经
        # ~/.hermes/skills/powerelf 软链暴露 → skill 同名冲突 → 全题秒败。
        # 快照目录在仓库内必须直接报错，不得静默落盘。
        with self.assertRaises(ValueError):
            hr.snapshot_guarded_state(snapshot_dir=self.repo / "output" / "freeze-baseline")

    def test_prune_freeze_snapshots(self):
        # 旧快照清理：只保留最近 keep 个 run；无 manifest.json 的目录不得被碰
        root = Path(tempfile.mkdtemp(prefix="freeze-guard-root-"))
        try:
            for i, age in enumerate((100.0, 200.0, 300.0, 400.0)):  # run-0 最老
                d = root / f"run-{i}"
                (d / "tree").mkdir(parents=True)
                (d / "manifest.json").write_text("{}")
                (d / "tree" / "x").write_text("x" * 100)
                os.utime(d, (age, age))
            (root / "not-a-snapshot").mkdir()  # 非快照目录（无 manifest）
            removed, freed = hr.prune_freeze_snapshots(
                root, keep=3, current_dir=root / "run-3")
            self.assertEqual(removed, 1)
            self.assertGreater(freed, 0)
            self.assertFalse((root / "run-0").exists(), "最老的应被删")
            for name in ("run-1", "run-2", "run-3", "not-a-snapshot"):
                self.assertTrue((root / name).exists(), f"{name} 应保留")
            # keep=0 = 不清理
            self.assertEqual(hr.prune_freeze_snapshots(root, keep=0), (0, 0))
        finally:
            shutil.rmtree(root, ignore_errors=True)

    # ---------- 报告去污染 ----------

    def test_report_excludes_mutated_and_dryrun(self):
        dims = {dn: 1.0 for dn in hr.DIMENSION_WEIGHTS}
        zero = {dn: 0.0 for dn in hr.DIMENSION_WEIGHTS}
        rows = [
            {"id": "a", "set": "s1", "score": 1.0, "verdict": "PASS", "dimensions": dims},
            {"id": "b", "set": "s1", "score": 0.0, "verdict": "CODE-MUTATED", "dimensions": zero},
            {"id": "c", "set": "s2", "score": 0.0, "verdict": "DRY-RUN", "dimensions": zero},
        ]
        rep = hr.generate_json_report(rows, {"master_version": "t"}, "run-x", "green", {})
        self.assertEqual(rep["valid_questions"], 1)
        self.assertEqual(rep["excluded_from_score"], 2)
        self.assertEqual(rep["overall_score"], 1.0)
        self.assertEqual(rep["per_set_summary"]["s1"]["valid"], 1)
        self.assertEqual(rep["per_set_summary"]["s1"]["excluded"], 1)
        self.assertEqual(rep["per_dimension_summary"]["D1_functional"]["avg"], 1.0)

    def test_report_all_excluded_scores_zero_not_nan(self):
        zero = {dn: 0.0 for dn in hr.DIMENSION_WEIGHTS}
        rows = [{"id": "b", "set": "s1", "score": 0.0, "verdict": "CODE-MUTATED", "dimensions": zero}]
        rep = hr.generate_json_report(rows, {}, "run-y", "green", {})
        self.assertEqual(rep["overall_score"], 0.0)
        self.assertEqual(rep["valid_questions"], 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
