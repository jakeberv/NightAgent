"""MNIST data loading for the NightAgent MNIST project.

Downloads the four official MNIST IDX files (torchvision's S3 mirror of
LeCun's originals), verifies MD5 checksums, parses them with numpy, and
returns the agreed fixed-seed 55k/5k train/validation split plus the
official 10k test set.

Usage:
    from tools.data import load_mnist
    d = load_mnist()            # dict of uint8 images (N,28,28) and int64 labels
    d["x_train"], d["y_train"], d["x_val"], d["y_val"], d["x_test"], d["y_test"]
"""
import gzip
import hashlib
import urllib.request
from pathlib import Path

import numpy as np

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "mnist"
MIRROR = "https://ossci-datasets.s3.amazonaws.com/mnist/"
FILES = {
    "train_images": ("train-images-idx3-ubyte.gz", "f68b3c2dcbeaaa9fbdd348bbdeb94873"),
    "train_labels": ("train-labels-idx1-ubyte.gz", "d53e105ee54ea40749a09fcbcd1e9432"),
    "test_images": ("t10k-images-idx3-ubyte.gz", "9fb629c4189551a2d022fa330f9573f3"),
    "test_labels": ("t10k-labels-idx1-ubyte.gz", "ec29112dd5afa0611ce80d1b7f02629c"),
}
SPLIT_SEED = 0  # fixed project-wide; do not change (agreed M00)
N_VAL = 5000


def _md5(path):
    return hashlib.md5(path.read_bytes()).hexdigest()


def download(data_dir=DATA_DIR):
    """Download any missing MNIST files into `data_dir` and verify checksums."""
    data_dir.mkdir(parents=True, exist_ok=True)
    for name, md5 in FILES.values():
        path = data_dir / name
        if not path.exists():
            urllib.request.urlretrieve(MIRROR + name, path)
        if _md5(path) != md5:
            raise RuntimeError(f"Checksum mismatch for {path}")


def _read_idx(path):
    """Parse a gzipped IDX file into a numpy array."""
    with gzip.open(path, "rb") as f:
        raw = f.read()
    ndim = raw[3]
    shape = tuple(int.from_bytes(raw[4 + 4 * i: 8 + 4 * i], "big") for i in range(ndim))
    return np.frombuffer(raw, dtype=np.uint8, offset=4 + 4 * ndim).reshape(shape)


def load_mnist(data_dir=DATA_DIR, n_val=N_VAL, split_seed=SPLIT_SEED):
    """Return the 55k/5k/10k train/val/test split as uint8 images and int64 labels.

    The validation set is a random (seeded) subset of the official 60k training
    set; the official 10k test set is returned unchanged.
    """
    download(data_dir)
    x = _read_idx(data_dir / FILES["train_images"][0])
    y = _read_idx(data_dir / FILES["train_labels"][0]).astype(np.int64)
    x_test = _read_idx(data_dir / FILES["test_images"][0])
    y_test = _read_idx(data_dir / FILES["test_labels"][0]).astype(np.int64)
    perm = np.random.default_rng(split_seed).permutation(len(x))
    val_idx, train_idx = perm[:n_val], perm[n_val:]
    return {
        "x_train": x[train_idx], "y_train": y[train_idx],
        "x_val": x[val_idx], "y_val": y[val_idx],
        "x_test": x_test, "y_test": y_test,
        "train_idx": train_idx, "val_idx": val_idx,
    }
