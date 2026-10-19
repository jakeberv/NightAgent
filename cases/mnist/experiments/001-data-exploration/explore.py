"""Experiment 001: MNIST data exploration. Writes figures + metrics.json to results/."""
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import matplotlib.pyplot as plt
import numpy as np

from tools.data import load_mnist
from tools.plotting import confusion_matrix, plot_confusion, plot_image_grid

OUT = Path(__file__).resolve().parent / "results"
OUT.mkdir(exist_ok=True)
t0 = time.perf_counter()
d = load_mnist()
splits = ("train", "val", "test")
X = {s: d[f"x_{s}"].astype(np.float32) / 255.0 for s in splits}
Y = {s: d[f"y_{s}"] for s in splits}
m = {}

# 1. Sample grid: 10 random examples per class from train
rng = np.random.default_rng(0)
imgs, titles = [], []
for c in range(10):
    idx = rng.choice(np.where(Y["train"] == c)[0], 10, replace=False)
    imgs += list(X["train"][idx]); titles += [str(c)] * 10
plot_image_grid(imgs, OUT / "samples.png", ncols=10, cmap="gray_r", suptitle="10 random training examples per class")

# 2. Class balance per split
counts = {s: np.bincount(Y[s], minlength=10).tolist() for s in splits}
m["class_counts"] = counts
m["class_frac"] = {s: (np.array(c) / sum(c)).round(4).tolist() for s, c in counts.items()}
fig, ax = plt.subplots(figsize=(7, 3.5))
for k, s in enumerate(splits):
    ax.bar(np.arange(10) + (k - 1) * 0.27, 100 * np.array(m["class_frac"][s]), 0.27, label=s)
ax.set_xticks(range(10)); ax.set_xlabel("class"); ax.set_ylabel("% of split"); ax.set_ylim(8, 12)
ax.legend(); ax.set_title("Class balance per split"); fig.tight_layout(); fig.savefig(OUT / "class_balance.png", dpi=130); plt.close(fig)

# 3. Per-class mean / std images, ink, within-class spread (train)
means = np.stack([X["train"][Y["train"] == c].mean(0) for c in range(10)])
stds = np.stack([X["train"][Y["train"] == c].std(0) for c in range(10)])
plot_image_grid(list(means) + list(stds), OUT / "class_mean_std.png", titles=[f"mean {c}" for c in range(10)] + [f"std {c}" for c in range(10)],
                ncols=10, cmap="magma", suptitle="Per-class mean (top) and pixel std (bottom), train")
ink = {s: X[s].reshape(len(X[s]), -1).sum(1) for s in splits}
m["ink_per_class_train"] = [float(ink["train"][Y["train"] == c].mean()) for c in range(10)]
spread = []
for c in range(10):
    xc = X["train"][Y["train"] == c].reshape(-1, 784)
    spread.append(float(np.linalg.norm(xc - means[c].ravel(), axis=1).mean()))
m["within_class_spread_train"] = spread

# 4. Class similarity: distances between class means; nearest-class-mean classifier on val
flat_means = means.reshape(10, -1)
D = np.linalg.norm(flat_means[:, None] - flat_means[None], axis=2)
m["class_mean_distance"] = D.round(3).tolist()
pairs = sorted(((D[i, j], i, j) for i in range(10) for j in range(i + 1, 10)))
m["closest_mean_pairs"] = [[int(i), int(j), round(float(v), 3)] for v, i, j in pairs[:6]]
fig, ax = plt.subplots(figsize=(5.5, 4.5))
im = ax.imshow(D, cmap="viridis_r"); fig.colorbar(im, ax=ax, label="L2 distance between class means")
for i in range(10):
    for j in range(10):
        ax.text(j, i, f"{D[i, j]:.1f}", ha="center", va="center", fontsize=6, color="w")
ax.set_xticks(range(10)); ax.set_yticks(range(10)); ax.set_title("Distance between class-mean images")
fig.tight_layout(); fig.savefig(OUT / "class_mean_distance.png", dpi=130); plt.close(fig)

def ncm_predict(x):
    xf = x.reshape(len(x), -1)
    return np.argmin(((xf[:, None] - flat_means[None]) ** 2).sum(2), 1)

for s in ("val", "test"):
    p = ncm_predict(X[s])
    m[f"nearest_class_mean_{s}_acc"] = float((p == Y[s]).mean())
    if s == "val":
        cm = confusion_matrix(Y[s], p)
        m["nearest_class_mean_val_confusion"] = cm.tolist()
        plot_confusion(cm, OUT / "ncm_confusion_val.png", f"Nearest class mean, val acc {m['nearest_class_mean_val_acc']:.3f}")

# 5. PCA (train)
xf = X["train"].reshape(len(X["train"]), -1)
mu = xf.mean(0)
_, S, Vt = np.linalg.svd(xf - mu, full_matrices=False)
ev = S ** 2 / (S ** 2).sum()
cum = np.cumsum(ev)
m["pca_components_for"] = {f"{q}": int(np.searchsorted(cum, q) + 1) for q in (0.5, 0.8, 0.9, 0.95, 0.99)}
Z = (X["val"].reshape(len(X["val"]), -1) - mu) @ Vt[:2].T
fig, axes = plt.subplots(1, 2, figsize=(11, 4.5))
axes[0].plot(np.arange(1, 785), cum); axes[0].set_xscale("log"); axes[0].axhline(0.9, ls="--", c="gray")
axes[0].set_xlabel("# principal components"); axes[0].set_ylabel("cumulative explained variance"); axes[0].set_title("PCA spectrum (train)")
for c in range(10):
    zc = Z[Y["val"] == c]
    axes[1].scatter(zc[:, 0], zc[:, 1], s=3, alpha=0.5, label=str(c), color=plt.cm.tab10(c))
axes[1].legend(markerscale=4, fontsize=7, ncol=2); axes[1].set_title("Val set projected on PC1–PC2")
fig.tight_layout(); fig.savefig(OUT / "pca.png", dpi=130); plt.close(fig)
plot_image_grid(list(Vt[:10].reshape(10, 28, 28)), OUT / "pca_components.png", titles=[f"PC{k + 1}" for k in range(10)],
                cmap="RdBu_r", symmetric=True, suptitle="Top-10 principal components")

# 6. Split shift: pixel histogram, ink distributions, KS statistics, mean-image differences
def ks(a, b):
    grid = np.sort(np.concatenate([a, b]))
    return float(np.abs(np.searchsorted(np.sort(a), grid, "right") / len(a) - np.searchsorted(np.sort(b), grid, "right") / len(b)).max())

m["ink_mean"] = {s: float(ink[s].mean()) for s in splits}
m["ink_std"] = {s: float(ink[s].std()) for s in splits}
m["ks_ink"] = {"train_vs_val": ks(ink["train"], ink["val"]), "train_vs_test": ks(ink["train"], ink["test"])}
# Rough two-sample KS critical value at alpha=0.05: 1.36*sqrt((n+m)/(n*m))
crit = lambda n1, n2: 1.36 * np.sqrt((n1 + n2) / (n1 * n2))
m["ks_crit_0.05"] = {"train_vs_val": float(crit(55000, 5000)), "train_vs_test": float(crit(55000, 10000))}
m["ks_ink_per_class_train_vs_test"] = [ks(ink["train"][Y["train"] == c], ink["test"][Y["test"] == c]) for c in range(10)]
m["nonzero_pixel_frac"] = {s: float((X[s] > 0).mean()) for s in splits}
mean_img = {s: X[s].mean(0) for s in splits}
fig, axes = plt.subplots(1, 4, figsize=(14, 3.5))
for ax, s in zip(axes[:2], ("train", "test")):
    ax.imshow(mean_img[s], cmap="magma"); ax.set_title(f"mean image: {s}"); ax.axis("off")
for ax, s in zip(axes[2:3], ("test",)):
    diff = mean_img[s] - mean_img["train"]; v = np.abs(diff).max()
    im = ax.imshow(diff, cmap="RdBu_r", vmin=-v, vmax=v); ax.set_title("test − train mean"); ax.axis("off"); fig.colorbar(im, ax=ax)
bins = np.linspace(0, 300, 61)
for s in splits:
    axes[3].hist(ink[s], bins=bins, density=True, histtype="step", label=f"{s} (μ={ink[s].mean():.1f})")
axes[3].set_xlabel("total ink (sum of pixel intensities)"); axes[3].legend(fontsize=7); axes[3].set_title("Ink per image")
fig.tight_layout(); fig.savefig(OUT / "split_shift.png", dpi=130); plt.close(fig)

m["runtime_s"] = time.perf_counter() - t0
(OUT / "metrics.json").write_text(json.dumps(m, indent=1))
print(json.dumps({k: v for k, v in m.items() if k not in ("class_mean_distance", "nearest_class_mean_val_confusion")}, indent=1))
