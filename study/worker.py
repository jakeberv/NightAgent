"""Trusted trial worker: receives only fixed train/validation paths and a schema.

No role supplied executable expressions, imports, feature names or paths enter
this process. Parent owns invocation, inputs and artifact verification.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile

import joblib
import numpy as np
from sklearn.metrics import roc_auc_score
from threadpoolctl import threadpool_limits

from study.science import build_pipeline


def execute(request: dict) -> dict:
    pipeline = build_pipeline(request["config"], seed=request["seed"])
    with np.load(request["train_path"], allow_pickle=False) as train, np.load(request["validation_path"], allow_pickle=False) as validation, threadpool_limits(limits=1):
        pipeline.fit(train["X"], train["y"])
        score = float(roc_auc_score(validation["y"], pipeline.predict_proba(validation["X"])[:, 1]))
    artifact = Path(request["artifact_path"])
    metadata = request["metadata"] | {"config": request["config"], "seed": request["seed"]}
    with tempfile.NamedTemporaryFile(dir=artifact.parent, suffix=".joblib.tmp", delete=False) as handle:
        temporary = Path(handle.name)
        try:
            joblib.dump({"pipeline": pipeline, "metadata": metadata}, handle)
            handle.flush()
            os.fsync(handle.fileno())
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise
    try:
        os.replace(temporary, artifact)
        descriptor = os.open(artifact.parent, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    finally:
        temporary.unlink(missing_ok=True)
    return {"status": "completed", "validation_auc": score, "artifact_hash": hashlib.sha256(artifact.read_bytes()).hexdigest()}


def main() -> None:
    try:
        result = execute(json.load(sys.stdin))
    except Exception as exc:
        result = {"status": "failed", "error": f"{type(exc).__name__}: {exc}"[:2000]}
    print(json.dumps(result, allow_nan=False), flush=True)


if __name__ == "__main__":
    main()
