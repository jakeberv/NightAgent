# Continuous integration

The `CI` workflow runs for pull requests targeting `main`, pushes to `main` and manual dispatches. Superseded runs are cancelled. Two independent jobs run the full offline suite on Ubuntu 24.04 x86_64 and Python 3.12:

| Check | Dependency policy | Diagnostic artifact |
|---|---|---|
| **Study locked baseline (CPU, Python 3.12)** | Exact runtime and test versions in [`requirements-study-cpu.lock`](../requirements-study-cpu.lock), including `torch==2.14.1+cpu` | `study-locked-results` |
| **Study supported ranges (CPU, Python 3.12)** | Fresh resolution of [`requirements-study.txt`](../requirements-study.txt) and `torch>=2.5,<3` from the official CPU index | `study-ranges-results` |

The locked check tests a reproducible package-version baseline. Its CPU lock pins the entire dependency closure and is passed as both requirements and constraints, alongside the supported base ranges. A conflicting range fails resolution. No later unconstrained install can replace a pin; the job checks every installed version and rejects any newly introduced unpinned runtime dependency before testing. The `+cpu` version selects the Linux CPU wheel from the [official PyTorch CPU index](https://download.pytorch.org/whl/cpu/torch/), avoiding PyPI's Linux CUDA build. Wheels are required, so a missing compatible binary fails explicitly instead of invoking a local source build.

The supported-range check deliberately omits the exact lock. Its separate PyTorch install retains the base range constraints, then `pip check` verifies the combined environment. A failure identifies a dependency-update issue separately from a regression on the pinned baseline. It does not silently regenerate the lock or install updates into the baseline job. This checks a current allowed resolution, not every version combination or the oldest supported versions.

Each job records installation logs, pip's installation report when resolution succeeds, Python/pip versions, exact installed packages, package metadata and `pip check` output, even if installation or tests fail. JUnit results are present when tests start. Separate artifacts are retained for seven days. The workflow explicitly selects GitHub's `bash` shell, whose error/pipe handling propagates failed installs through `tee`.

## Local reproduction and lock updates

On Linux x86_64 with Python 3.12, create a fresh environment and run the baseline install from the repository root:

```bash
python3.12 -m venv .venv-ci
.venv-ci/bin/python -m pip install --only-binary=:all: \
  -r requirements-study.txt -r requirements-study-cpu.lock \
  -c requirements-study-cpu.lock \
  --extra-index-url https://download.pytorch.org/whl/cpu
.venv-ci/bin/python -m pip check
.venv-ci/bin/python -m pytest -q
```

The CPU lock shares base versions with [`requirements-study.lock`](../requirements-study.lock), which was recorded on macOS arm64. Its neural versions are matched to [`requirements-gpu.lock`](../requirements-gpu.lock), with the explicit Linux CPU wheel substituted. The CPU closure was independently resolved for CPython 3.12 / manylinux x86_64 using package metadata; that verifies satisfiability and wheel availability, not execution on Ubuntu. The macOS/MPS lock remains separate. Neither neural lock claims universal platform support, and these files pin versions rather than wheel hashes or the GitHub runner image.

When updating dependencies, review the supported-range artifact, resolve a complete CPU closure for the target platform, update the exact pins deliberately, and run both checks. Keep the base lock in sync when intentionally changing shared versions; recalibrate MPS separately when changing its environment. Local static workflow checks or cross-platform resolution do not substitute for a native Linux install/test run.

## Coverage and platform boundary

Both jobs explicitly import PyTorch and assert CPU-only execution before running all of `tests/`. Coverage includes MLP/CNN CPU fits, isolated worker and artifact roundtrips, GPU queue scheduling with fake workers, and unavailable-MPS behavior. Neural test files are not excluded based on their names. Fixtures are synthetic; dataset downloads, literature access and model requests are mocked. No provider credentials, paid calls or real Fashion-MNIST download are needed. The separate Claude SDK conversational prototype has its own dependencies and is not exercised by this study suite.

Real Apple MPS execution and performance calibration remain local checks. Run [Fashion calibration](fashion-pilot.md) on a supported Mac after changes to neural training or scheduling. Passing CPU CI establishes neither MPS compatibility nor model quality on the full dataset.

The workflow uses `pull_request` (the proposed merge result), read-only repository permissions and pinned action revisions. It does not grant fork PRs secrets or merge code. Branch-protection requirements are a repository setting; configure the desired checks there if repository policy should require them before merge.
