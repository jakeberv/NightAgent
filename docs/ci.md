# Continuous integration

The `CI` workflow runs when a pull request targets `main`, when new commits land
on `main`, and when manually dispatched. New commits to an open PR rerun the
check; superseded runs are cancelled. The check is named
**Study tests (CPU, Python 3.12)**.

GitHub hosts the job on Ubuntu 24.04 with Python 3.12. It installs the portable
study dependency ranges from `requirements-study.txt`, then PyTorch from its
[official CPU wheel index](https://download.pytorch.org/whl/cpu). The macOS GPU
calibration lock is deliberately separate. Each run uploads its exact installed
dependency versions and JUnit test results for seven days.

The full `tests/` suite runs, including MLP/CNN CPU fits, isolated worker and
artifact roundtrips, GPU queue scheduling with fake workers, and explicit
unavailable-MPS behavior. No neural tests are excluded merely because their file
name contains `gpu`. CPU-only PyTorch is explicitly imported and checked before
testing, so a missing optional runtime cannot silently skip neural coverage.
Fixtures are synthetic; dataset downloads, literature access and model requests
are mocked. No provider credentials, paid calls or real Fashion-MNIST download
are needed. The standalone Claude SDK prototype is not exercised by this study
suite.

Real Apple MPS execution and performance calibration remain local checks. Run
[the Fashion calibration command](fashion-pilot.md) on a supported Mac after
changes to neural training or scheduling. Passing CPU CI establishes neither GPU
compatibility nor model quality on the full dataset.

The workflow uses `pull_request` (the proposed merge result), read-only repository
permissions and pinned action revisions. It does not grant fork PRs secrets or
merge code itself. Branch-protection requirements are a repository setting;
adding the workflow alone does not enforce them. Configure the check above as
required if repository policy should block every merge until it passes.
