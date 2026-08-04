#!/usr/bin/env python3
"""Governed state machine for the lottery scheme generation system.

This tool does not invent scheme logic. It creates and validates the evidence
envelope that AI directors and build tools must follow.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PIPELINE_PATH = ROOT / "controller" / "pipeline.json"
EXTENSIONS_PATH = ROOT / "controller" / "extensions.json"
DEFAULT_RUN_ROOT = ROOT / ".runtime" / "lottery-controller"


class ControllerError(RuntimeError):
    pass


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ControllerError(f"缺少文件: {path.relative_to(ROOT)}") from exc
    except json.JSONDecodeError as exc:
        raise ControllerError(f"JSON错误: {path.relative_to(ROOT)}:{exc.lineno}:{exc.colno}") from exc


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_value(*args: str) -> str | None:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return None
    value = result.stdout.strip()
    return value or None


def validate_configs() -> list[str]:
    errors: list[str] = []
    pipeline = load_json(PIPELINE_PATH)
    extensions = load_json(EXTENSIONS_PATH)

    phases = pipeline.get("phases", [])
    ids = [item.get("id") for item in phases]
    if not ids or len(ids) != len(set(ids)):
        errors.append("pipeline.phases为空或存在重复id")
    for required in ("INTAKE", "PREFLIGHT", "DIRECTOR", "CONTRACT_FROZEN",
                     "EXECUTION", "VALIDATION", "AUDIT", "REWORK",
                     "DELIVERY", "LEARNING", "COMPLETED"):
        if required not in ids:
            errors.append(f"pipeline缺少阶段: {required}")
    transitions = pipeline.get("transitions", {})
    known = set(ids) | {"BLOCKED"}
    for source, targets in transitions.items():
        if source not in known:
            errors.append(f"未知转移源: {source}")
        for target in targets:
            if target not in known:
                errors.append(f"未知转移目标: {source}->{target}")
    if pipeline.get("direct_main_write_forbidden") is not True:
        errors.append("未禁止直接写main")
    max_rework = pipeline.get("max_rework_rounds")
    if not isinstance(max_rework, int) or not 1 <= max_rework <= 3:
        errors.append("max_rework_rounds必须为1至3")
    rollback = pipeline.get("rollback", {})
    for key in ("base_commit_required_before_write",
                "changed_files_hash_required",
                "failed_version_evidence_must_remain",
                "force_push_forbidden"):
        if rollback.get(key) is not True:
            errors.append(f"rollback.{key}未启用")
    cleanup = pipeline.get("cleanup", {})
    if cleanup.get("direct_delete_forbidden") is not True:
        errors.append("清理策略未禁止直接删除")
    if cleanup.get("quarantine_first") is not True:
        errors.append("清理策略未启用先隔离")

    domains = extensions.get("domains", [])
    domain_ids = {item.get("id") for item in domains}
    required_domains = {"PPT", "SCHEME", "PROGRAM", "SYSTEM", "CLEANUP"}
    if domain_ids != required_domains:
        errors.append(f"扩展域错误: {sorted(x for x in domain_ids if x)}")
    for item in domains:
        domain_id = item.get("id", "<unknown>")
        if not item.get("owned_paths"):
            errors.append(f"{domain_id}缺少owned_paths")
        if not item.get("required_validators"):
            errors.append(f"{domain_id}缺少required_validators")
        if not item.get("compatibility_contract"):
            errors.append(f"{domain_id}缺少compatibility_contract")
        if not item.get("rollback_unit"):
            errors.append(f"{domain_id}缺少rollback_unit")
    return errors


def require_valid_configs() -> tuple[dict[str, Any], dict[str, Any]]:
    errors = validate_configs()
    if errors:
        raise ControllerError("配置校验失败:\n- " + "\n- ".join(errors))
    return load_json(PIPELINE_PATH), load_json(EXTENSIONS_PATH)


def make_run_id() -> str:
    return datetime.now().strftime("RUN-%Y%m%d-%H%M%S")


def resolve_run_dir(run_root: Path, run_id: str) -> Path:
    return run_root / run_id


def load_state(run_dir: Path) -> dict[str, Any]:
    return load_json(run_dir / "state.json")


def save_state(run_dir: Path, state: dict[str, Any]) -> None:
    state["updated_at"] = now_iso()
    write_json(run_dir / "state.json", state)


def evidence_index(paths: list[Path]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for path in paths:
        resolved = path if path.is_absolute() else (ROOT / path)
        if not resolved.exists() or not resolved.is_file():
            raise ControllerError(f"证据文件不存在: {path}")
        try:
            display = str(resolved.relative_to(ROOT))
        except ValueError:
            display = str(resolved)
        records.append({
            "path": display.replace("\\", "/"),
            "sha256": sha256_file(resolved),
            "size": resolved.stat().st_size,
        })
    return records


def cmd_validate(_: argparse.Namespace) -> int:
    errors = validate_configs()
    if errors:
        print("CONTROLLER_CONFIG_INVALID")
        for item in errors:
            print(f"- {item}")
        return 1
    print("CONTROLLER_CONFIG_VALID")
    return 0


def cmd_start(args: argparse.Namespace) -> int:
    pipeline, extensions = require_valid_configs()
    run_root = Path(args.run_root).resolve()
    run_id = args.run_id or make_run_id()
    run_dir = resolve_run_dir(run_root, run_id)
    if run_dir.exists():
        raise ControllerError(f"运行ID已存在: {run_id}")
    run_dir.mkdir(parents=True)

    base_branch = git_value("branch", "--show-current") or "main"
    base_commit = git_value("rev-parse", "HEAD") or "UNRESOLVED_BY_LOCAL_GIT"
    task = {
        "run_id": run_id,
        "created_at": now_iso(),
        "request": args.request,
        "mode": args.mode,
        "source_repository": "fdsasaaa/guaji5",
        "stable_source": pipeline["stable_source"],
        "requested_domains": args.domain,
        "delivery": pipeline["default_delivery"],
    }
    rollback = {
        "run_id": run_id,
        "created_at": now_iso(),
        "base_branch": base_branch,
        "base_commit": base_commit,
        "write_started": False,
        "planned_files": [],
        "before_hashes": [],
        "after_hashes": [],
        "validation_evidence": [],
        "rollback_target": pipeline["rollback"]["rollback_target"],
        "failed_evidence_must_remain": True,
        "force_push_forbidden": True,
    }
    state = {
        "run_id": run_id,
        "phase": "INTAKE",
        "status": "ACTIVE",
        "rework_round": 0,
        "max_rework_rounds": pipeline["max_rework_rounds"],
        "history": [{
            "from": None,
            "to": "INTAKE",
            "at": now_iso(),
            "note": "任务已建立",
            "evidence": [],
        }],
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }
    contract = {
        "run_id": run_id,
        "status": "DRAFT",
        "contract_version": 1,
        "research_question": "",
        "data_and_samples": {},
        "candidate_profiles": [],
        "selected_profile": {},
        "scheme_logic": {},
        "monitoring_and_switching": {},
        "execution_structure": {},
        "funding_paths_review": {},
        "risk_and_stops": {},
        "txt_contract": {},
        "ppt_contract": {},
        "acceptance_gates": [],
        "frozen_at": None,
    }
    audit = {
        "run_id": run_id,
        "status": "PENDING",
        "machine_checks": [],
        "semantic_checks": [],
        "delivery_checks": [],
        "decision": None,
    }

    write_json(run_dir / "task.json", task)
    write_json(run_dir / "state.json", state)
    write_json(run_dir / "rollback_manifest.json", rollback)
    write_json(run_dir / "design_contract.json", contract)
    write_json(run_dir / "audit_report.json", audit)
    write_json(run_dir / "extension_snapshot.json", extensions)

    print(json.dumps({
        "run_id": run_id,
        "run_dir": str(run_dir),
        "phase": "INTAKE",
        "next": "PREFLIGHT",
    }, ensure_ascii=False))
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    run_dir = resolve_run_dir(Path(args.run_root).resolve(), args.run_id)
    state = load_state(run_dir)
    print(json.dumps(state, ensure_ascii=False, indent=2))
    return 0


def cmd_advance(args: argparse.Namespace) -> int:
    pipeline, _ = require_valid_configs()
    run_dir = resolve_run_dir(Path(args.run_root).resolve(), args.run_id)
    state = load_state(run_dir)
    current = state["phase"]
    target = args.to
    allowed = pipeline["transitions"].get(current, [])
    if target not in allowed:
        raise ControllerError(f"非法状态转移: {current}->{target}; 允许={allowed}")

    if current == "REWORK" and target != "BLOCKED":
        state["rework_round"] += 1
        if state["rework_round"] > state["max_rework_rounds"]:
            raise ControllerError("返工次数已超过上限，必须转BLOCKED")

    required_outputs = {
        item["id"]: item.get("required_outputs", [])
        for item in pipeline["phases"]
    }.get(current, [])
    missing = [name for name in required_outputs if not (run_dir / name).exists()]
    if missing:
        raise ControllerError(f"当前阶段缺少输出，不能推进: {missing}")

    evidence = evidence_index([Path(item) for item in args.evidence])
    state["phase"] = target
    if target == "BLOCKED":
        state["status"] = "BLOCKED"
    elif target == "COMPLETED":
        state["status"] = "COMPLETED"
    state["history"].append({
        "from": current,
        "to": target,
        "at": now_iso(),
        "note": args.note,
        "evidence": evidence,
    })
    save_state(run_dir, state)
    print(f"ADVANCED {current}->{target}")
    return 0


def cmd_fail(args: argparse.Namespace) -> int:
    pipeline, _ = require_valid_configs()
    run_dir = resolve_run_dir(Path(args.run_root).resolve(), args.run_id)
    state = load_state(run_dir)
    route = pipeline["failure_routes"].get(args.category)
    if route is None:
        raise ControllerError(f"未知失败类别: {args.category}")
    failure = {
        "at": now_iso(),
        "phase": state["phase"],
        "category": args.category,
        "code": args.code,
        "message": args.message,
        "recommended_return": route,
    }
    failure_path = run_dir / "failures.jsonl"
    with failure_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(failure, ensure_ascii=False) + "\n")
    print(json.dumps(failure, ensure_ascii=False))
    return 0


def cmd_rollback_plan(args: argparse.Namespace) -> int:
    pipeline, _ = require_valid_configs()
    run_dir = resolve_run_dir(Path(args.run_root).resolve(), args.run_id)
    manifest = load_json(run_dir / "rollback_manifest.json")
    plan = {
        "run_id": args.run_id,
        "created_at": now_iso(),
        "target": manifest.get("base_commit") or pipeline["rollback"]["rollback_target"],
        "method": "new_revert_or_restore_commit",
        "force_push": False,
        "preserve_failed_branch": True,
        "steps": [
            "冻结当前失败分支并保存校验日志",
            "核对修改文件及修改前后哈希",
            "从最近已验证main提交恢复受影响文件或创建revert提交",
            "运行仓库总校验和受影响域专项校验",
            "通过独立PR恢复main",
        ],
    }
    write_json(run_dir / "rollback_plan.json", plan)
    print(json.dumps(plan, ensure_ascii=False, indent=2))
    return 0


def cmd_cleanup_plan(args: argparse.Namespace) -> int:
    _, extensions = require_valid_configs()
    run_dir = resolve_run_dir(Path(args.run_root).resolve(), args.run_id)
    candidates = [Path(item) for item in args.path]
    records = []
    for candidate in candidates:
        resolved = candidate if candidate.is_absolute() else ROOT / candidate
        record = {
            "path": str(candidate).replace("\\", "/"),
            "exists": resolved.exists(),
            "is_file": resolved.is_file(),
            "sha256": sha256_file(resolved) if resolved.is_file() else None,
            "decision": "REVIEW_REQUIRED",
            "direct_delete_allowed": False,
            "quarantine_first": True,
        }
        records.append(record)
    cleanup_domain = next(
        item for item in extensions["domains"] if item["id"] == "CLEANUP"
    )
    plan = {
        "run_id": args.run_id,
        "created_at": now_iso(),
        "status": "PLAN_ONLY",
        "policy": cleanup_domain["compatibility_contract"],
        "candidates": records,
        "required_next_steps": [
            "扫描清单、协议、工作流、代码和索引引用",
            "分类正式源、构建产物、历史证据、重复文件和未知文件",
            "先隔离并生成恢复清单",
            "运行清理前后全量校验",
            "删除动作使用独立PR",
        ],
    }
    write_json(run_dir / "cleanup_plan.json", plan)
    print(json.dumps(plan, ensure_ascii=False, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="彩票挂机系统治理总控")
    sub = parser.add_subparsers(dest="command", required=True)

    validate = sub.add_parser("validate", help="校验总控配置")
    validate.set_defaults(func=cmd_validate)

    start = sub.add_parser("start", help="建立一次受控任务")
    start.add_argument("--request", required=True)
    start.add_argument("--mode", default="STANDARD_SCHEME_TASK")
    start.add_argument("--domain", action="append", choices=["PPT", "SCHEME", "PROGRAM", "SYSTEM", "CLEANUP"], default=[])
    start.add_argument("--run-id")
    start.add_argument("--run-root", default=str(DEFAULT_RUN_ROOT))
    start.set_defaults(func=cmd_start)

    status = sub.add_parser("status", help="查看运行状态")
    status.add_argument("--run-id", required=True)
    status.add_argument("--run-root", default=str(DEFAULT_RUN_ROOT))
    status.set_defaults(func=cmd_status)

    advance = sub.add_parser("advance", help="推进到合法下一阶段")
    advance.add_argument("--run-id", required=True)
    advance.add_argument("--to", required=True)
    advance.add_argument("--evidence", action="append", default=[])
    advance.add_argument("--note", default="")
    advance.add_argument("--run-root", default=str(DEFAULT_RUN_ROOT))
    advance.set_defaults(func=cmd_advance)

    fail = sub.add_parser("fail", help="登记失败和返工路由")
    fail.add_argument("--run-id", required=True)
    fail.add_argument("--category", required=True, choices=[
        "INPUT_OR_VERSION", "LOGIC_OR_OVERFIT", "CONTRACT_DRIFT",
        "TXT_OR_BUILD", "DATA_OR_BACKTEST", "PPT_OR_SEMANTIC",
        "DELIVERY_INTEGRITY",
    ])
    fail.add_argument("--code", required=True)
    fail.add_argument("--message", required=True)
    fail.add_argument("--run-root", default=str(DEFAULT_RUN_ROOT))
    fail.set_defaults(func=cmd_fail)

    rollback = sub.add_parser("rollback-plan", help="生成非破坏性回滚计划")
    rollback.add_argument("--run-id", required=True)
    rollback.add_argument("--run-root", default=str(DEFAULT_RUN_ROOT))
    rollback.set_defaults(func=cmd_rollback_plan)

    cleanup = sub.add_parser("cleanup-plan", help="生成只读清理计划")
    cleanup.add_argument("--run-id", required=True)
    cleanup.add_argument("--path", action="append", required=True)
    cleanup.add_argument("--run-root", default=str(DEFAULT_RUN_ROOT))
    cleanup.set_defaults(func=cmd_cleanup_plan)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        return args.func(args)
    except ControllerError as exc:
        print(f"CONTROLLER_ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
