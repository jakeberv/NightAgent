"""Experiment 002: softmax regression baseline, 3 seeds."""
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import matplotlib.pyplot as plt
import numpy as np
import torch

from tools.data import load_mnist
from tools.plotting import confusion_matrix, plot_confusion, plot_image_grid
from tools.train import to_tensors, train_and_evaluate

OUT = Path(__file__).resolve().parent / "results"
OUT.mkdir(exist_ok=True)
SEEDS = (0, 1, 2)
CFG = dict(epochs=20, batch_size=128, lr=1e-3, weight_decay=0.0, device="cpu")

t0 = time.perf_counter()
d = load_mnist()
runs = [train_and_evaluate(lambda: torch.nn.Sequential(torch.nn.Flatten(), torch.nn.Linear(784, 10)), d, seed=s, verbose=False, **CFG)
        for s in SEEDS]

summary = {"config": CFG, "seeds": list(SEEDS), "n_params": runs[0]["n_params"], "per_seed": []}
for r in runs:
    summary["per_seed"].append({k: r[k] for k in ("seed", "train_acc", "val_acc", "test_acc", "train_time_s")})
for k in ("train_acc", "val_acc", "test_acc", "train_time_s"):
    v = np.array([r[k] for r in runs])
    summary[k] = {"mean": float(v.mean()), "std": float(v.std(ddof=1))}
summary["test_minus_val_pp"] = 100 * (summary["test_acc"]["mean"] - summary["val_acc"]["mean"])

# Confusion matrices pooled over seeds; top error pairs
cm_val = sum(confusion_matrix(d["y_val"], r["val_pred"]) for r in runs)
cm_test = sum(confusion_matrix(d["y_test"], r["test_pred"]) for r in runs)
plot_confusion(cm_test, OUT / "confusion_test.png", f"Logistic regression, test, pooled over {len(SEEDS)} seeds")
plot_confusion(cm_val, OUT / "confusion_val.png", f"Logistic regression, val, pooled over {len(SEEDS)} seeds")
summary["confusion_test_pooled"] = cm_test.tolist()
off = cm_test.copy(); np.fill_diagonal(off, 0)
order = np.dstack(np.unravel_index(np.argsort(-off, None), off.shape))[0][:10]
summary["top_test_errors_pooled"] = [[int(i), int(j), int(off[i, j])] for i, j in order]
summary["per_class_test_acc"] = (np.diag(cm_test) / cm_test.sum(1)).round(4).tolist()

# Per-class test accuracy vs nearest-class-mean from 001 (recomputed here, cheap)
x_tr = d["x_train"].reshape(len(d["x_train"]), -1).astype(np.float32) / 255
means = np.stack([x_tr[d["y_train"] == c].mean(0) for c in range(10)])
x_te = d["x_test"].reshape(len(d["x_test"]), -1).astype(np.float32) / 255
ncm_pred = np.argmin(((x_te[:, None] - means[None]) ** 2).sum(2), 1)
cm_ncm = confusion_matrix(d["y_test"], ncm_pred)
summary["per_class_test_acc_ncm"] = (np.diag(cm_ncm) / cm_ncm.sum(1)).round(4).tolist()
summary["ncm_test_acc"] = float((ncm_pred == d["y_test"]).mean())
# Errors into class 1 (the "thin digit" failure in 001)
summary["errors_into_1_test"] = {"ncm": int(cm_ncm[:, 1].sum() - cm_ncm[1, 1]), "logreg_per_seed_mean": float((cm_test[:, 1].sum() - cm_test[1, 1]) / len(SEEDS))}

fig, ax = plt.subplots(figsize=(7, 3.5))
w = 0.38
ax.bar(np.arange(10) - w / 2, 100 * np.array(summary["per_class_test_acc_ncm"]), w, label="nearest class mean (001)")
ax.bar(np.arange(10) + w / 2, 100 * np.array(summary["per_class_test_acc"]), w, label="logistic regression")
ax.set_xticks(range(10)); ax.set_xlabel("class"); ax.set_ylabel("test accuracy %"); ax.set_ylim(50, 100); ax.legend(fontsize=8)
ax.set_title("Per-class test accuracy"); fig.tight_layout(); fig.savefig(OUT / "per_class_vs_ncm.png", dpi=130); plt.close(fig)

# Learning curves
fig, ax = plt.subplots(figsize=(6, 3.5))
for r in runs:
    ax.plot([h["epoch"] for h in r["history"]], [100 * h["val_acc"] for h in r["history"]], label=f"seed {r['seed']}")
ax.set_xlabel("epoch"); ax.set_ylabel("val accuracy %"); ax.legend(); ax.set_title("Validation accuracy per epoch")
fig.tight_layout(); fig.savefig(OUT / "learning_curves.png", dpi=130); plt.close(fig)
summary["history"] = {r["seed"]: r["history"] for r in runs}

# Weight templates (seed 0) vs class means: what has the linear model learned?
W = runs[0]["model"][1].weight.detach().numpy().reshape(10, 28, 28)
mean_centered = means - means.mean(0)
summary["corr_weight_vs_centered_class_mean"] = [float(np.corrcoef(W[c].ravel(), mean_centered[c])[0, 1]) for c in range(10)]
plot_image_grid(list(W) + list(mean_centered.reshape(10, 28, 28)), OUT / "weights_vs_means.png",
                titles=[f"W {c}" for c in range(10)] + [f"mean−avg {c}" for c in range(10)], cmap="RdBu_r", symmetric=True,
                suptitle="Top: learned weights (seed 0, red=evidence for class). Bottom: class mean minus overall mean")

# Most confident test errors (seed 0)
r0 = runs[0]
with torch.no_grad():
    probs = torch.softmax(r0["model"](to_tensors(d, "cpu")["x_test"]), 1).numpy()
wrong = np.where(r0["test_pred"] != d["y_test"])[0]
conf = probs[wrong, r0["test_pred"][wrong]]
top = wrong[np.argsort(-conf)][:20]
plot_image_grid(list(d["x_test"][top]), OUT / "confident_errors.png",
                titles=[f"true {d['y_test'][i]} pred {r0['test_pred'][i]}\np={probs[i, r0['test_pred'][i]]:.2f}" for i in top],
                cmap="gray_r", suptitle="20 most confident test errors (seed 0)")

summary["runtime_s"] = time.perf_counter() - t0
(OUT / "metrics.json").write_text(json.dumps(summary, indent=1))
print(json.dumps({k: v for k, v in summary.items() if k not in ("history", "confusion_test_pooled")}, indent=1))
