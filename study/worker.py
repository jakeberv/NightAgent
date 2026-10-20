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
    adapter = None
    if 'problem' in request:
        from study.problem import ProblemSpec
        from study.tasks import get_adapter
        adapter = get_adapter(ProblemSpec.from_dict(request['problem']))
    from study.resources import worker_threads
    threads = worker_threads(request["config"]["model"], request.get("cores", 1))
    pipeline = (adapter.build_pipeline if adapter else build_pipeline)(request['config'], seed=request['seed'])
    if request["config"]["model"] == "random_forest":
        pipeline.steps[-1][1].set_params(n_jobs=threads["jobs"])
    with np.load(request["train_path"], allow_pickle=False) as train, np.load(request["validation_path"], allow_pickle=False) as validation, threadpool_limits(limits=threads["blas"], user_api="blas"), threadpool_limits(limits=threads["openmp"], user_api="openmp"):
        pipeline.fit(train["X"], train["y"])
        if adapter is None:
            score = float(roc_auc_score(validation['y'], pipeline.predict_proba(validation['X'])[:, 1]))
        else:
            metrics = adapter.metrics(pipeline, validation['X'], validation['y'])
            score = metrics[adapter.problem.objective['metric']]
    artifact = Path(request["artifact_path"])
    metadata = request["metadata"] | {"config": request["config"], "seed": request["seed"], "allocated_cores": request.get("cores", 1)}
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
    result = {'status': 'completed', 'artifact_hash': hashlib.sha256(artifact.read_bytes()).hexdigest()}
    if adapter is None:
        result['validation_auc'] = score
    else:
        result.update(metrics=metrics, score=score)
        if adapter.problem.objective['metric'] == 'roc_auc':
            result['validation_auc'] = score
    return result


def main() -> None:
    try:
        result = execute(json.load(sys.stdin))
    except Exception as exc:
        result = {"status": "failed", "error": f"{type(exc).__name__}: {exc}"[:2000]}
    print(json.dumps(result, allow_nan=False), flush=True)


if __name__ == "__main__":
    main()
