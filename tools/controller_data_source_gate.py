from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / "controller" / "data_sources.json"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class DataSourceGateError(RuntimeError):
    pass


def load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise DataSourceGateError(f"缺少数据源证据: {path}") from exc
    except json.JSONDecodeError as exc:
        raise DataSourceGateError(
            f"数据源JSON错误: {path}:{exc.lineno}:{exc.colno}"
        ) from exc


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def registry() -> dict[str, Any]:
    return load_json(REGISTRY_PATH)


def available_source_ids() -> tuple[str, ...]:
    return tuple(sorted(registry().get("sources", {})))


def required_for_task(task: dict[str, Any]) -> bool:
    source_id = task.get("data_source")
    if not source_id:
        return False
    source = registry().get("sources", {}).get(source_id)
    return bool(source and source.get("formal_gate_required"))


def sync_task_source(
    *,
    run_dir: Path,
    task: dict[str, Any],
    cache_root: Path | None = None,
    allow_same_latest: bool = False,
) -> dict[str, Any]:
    source_id = task.get("data_source")
    if not source_id:
        result = {
            "status": "NOT_APPLICABLE",
            "formal_generation_allowed": True,
            "data_source": None,
            "reason": "本任务未声明外部数据源",
        }
        write_json(run_dir / "preflight.json", result)
        return result
    if source_id != "hxffc":
        raise DataSourceGateError(f"未实现的数据源适配器: {source_id}")

    from data_sources import HashFFCSource, SourceError

    source_config = registry().get("sources", {}).get(source_id, {})
    source = HashFFCSource(
        cache_root=cache_root or (ROOT / "data_sources" / "hxffc"),
        min_records=int(source_config.get("minimum_records", 100)),
        max_age_minutes=int(source_config.get("max_age_minutes", 360)),
        retention_count=int(source_config.get("snapshot_retention", 5)),
    )
    try:
        draws, metadata, paths = source.sync(
            task_id=str(task.get("run_id") or task.get("task_id") or "UNRESOLVED"),
            task_run_dir=run_dir,
            require_newer=not allow_same_latest,
        )
    except SourceError as exc:
        blocked = {
            "schema_version": 1,
            "status": "BLOCKED",
            "failure_state": source_config.get(
                "failure_state", "EXTERNAL_DATA_SOURCE_FAILED"
            ),
            "data_source": source_id,
            "source_url": source_config.get("fixed_url"),
            "formal_generation_allowed": False,
            "reason": str(exc),
        }
        write_json(run_dir / "data_source_snapshot.json", blocked)
        write_json(run_dir / "preflight.json", blocked)
        raise DataSourceGateError(str(exc)) from exc

    result = {
        "schema_version": 1,
        "status": "PASS",
        "data_source": source_id,
        "formal_generation_allowed": True,
        "metadata": metadata,
        "paths": paths,
        "draw_count": len(draws),
    }
    write_json(run_dir / "preflight.json", result)
    return result


def validate_task_snapshot(
    *,
    run_dir: Path,
    task: dict[str, Any],
) -> list[str]:
    errors: list[str] = []
    source_id = task.get("data_source")
    if not source_id:
        return errors

    source_config = registry().get("sources", {}).get(source_id)
    if not source_config:
        return [f"任务声明了未登记数据源: {source_id}"]
    if not source_config.get("formal_gate_required"):
        return errors

    snapshot_path = run_dir / "data_source_snapshot.json"
    metadata_path = run_dir / "inputs" / "hxffc_metadata.json"
    history_path = run_dir / "inputs" / "hxffc_history.txt"
    draws_path = run_dir / "inputs" / "hxffc_draws.json"
    for path in (snapshot_path, metadata_path, history_path, draws_path):
        if not path.is_file():
            errors.append(f"缺少外部数据源任务快照: {path.name}")
    if errors:
        return errors

    try:
        snapshot = load_json(snapshot_path)
        metadata = load_json(metadata_path)
        draws = load_json(draws_path)
    except DataSourceGateError as exc:
        return [str(exc)]

    if snapshot.get("status") != "PASS":
        errors.append("data_source_snapshot.status不是PASS")
    if snapshot.get("formal_generation_allowed") is not True:
        errors.append("外部数据源未允许正式生成")
    snapshot_metadata = snapshot.get("metadata", {})
    if snapshot_metadata != metadata:
        errors.append("快照metadata与任务metadata不一致")
    if metadata.get("source_id") != source_id:
        errors.append("metadata.source_id与任务不一致")
    if metadata.get("source_url") != source_config.get("fixed_url"):
        errors.append("metadata未使用登记的固定下载地址")
    if metadata.get("validation_passed") is not True:
        errors.append("metadata.validation_passed不是true")
    if metadata.get("formal_generation_allowed") is not True:
        errors.append("metadata未允许正式生成")
    digest = str(metadata.get("sha256", ""))
    if not SHA256_RE.fullmatch(digest):
        errors.append("metadata.sha256格式错误")
    elif sha256_file(history_path) != digest:
        errors.append("任务历史快照SHA-256与metadata不一致")
    minimum = int(source_config.get("minimum_records", 1))
    record_count = metadata.get("record_count")
    if not isinstance(record_count, int) or record_count < minimum:
        errors.append(f"任务快照记录数不足: {record_count} < {minimum}")
    latest_issue = str(metadata.get("latest_issue", ""))
    earliest_issue = str(metadata.get("earliest_issue", ""))
    if not latest_issue.isdigit() or not earliest_issue.isdigit():
        errors.append("任务快照期号范围非法")
    if isinstance(draws, dict):
        records = draws.get("records")
        if draws.get("source_id") != source_id:
            errors.append("标准分析输入source_id错误")
        if not isinstance(records, list) or len(records) != record_count:
            errors.append("标准分析输入记录数与metadata不一致")
        elif any("source" in item for item in records if isinstance(item, dict)):
            errors.append("上游source字段泄漏到方案分析输入")
    else:
        errors.append("标准分析输入不是JSON对象")
    return errors
