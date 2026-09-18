"""Data manifest resolution and provenance-aware I/O."""

from data_io.jsonl_io import load_jsonl, save_jsonl, save_semi_structured
from data_io.loaders import load
from data_io.manifest import (
    DataManager,
    DatasetNotFoundError,
    TierUnavailableError,
    UnsetEnvPathError,
    find_manifest_path,
    get_manager,
    looks_like_unset_env_path,
    reload_manager,
    resolve,
    resolve_cli_path,
)
from data_io.parquet_io import load_parquet, save_parquet
from data_io.provenance import ProvenanceRecord

__all__ = [
    "DataManager",
    "DatasetNotFoundError",
    "ProvenanceRecord",
    "TierUnavailableError",
    "UnsetEnvPathError",
    "find_manifest_path",
    "get_manager",
    "load",
    "load_jsonl",
    "load_parquet",
    "looks_like_unset_env_path",
    "reload_manager",
    "resolve",
    "resolve_cli_path",
    "run_check",
    "save_jsonl",
    "save_parquet",
    "save_semi_structured",
]


def run_check(*args, **kwargs):  # noqa: ANN002, ANN003
    from data_io.check import run_check as _run_check

    return _run_check(*args, **kwargs)
