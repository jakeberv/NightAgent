"""Shared plotting / metric helpers.

    confusion_matrix(y_true, y_pred, n_classes=10) -> (C, C) int array, rows = true class
    plot_confusion(cm, path, title)                 -> saves a row-normalised heatmap PNG
    plot_image_grid(images, path, titles=None, ncols=10, cmap="gray", symmetric=False)
"""
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


def confusion_matrix(y_true, y_pred, n_classes=10):
    cm = np.zeros((n_classes, n_classes), dtype=int)
    np.add.at(cm, (y_true, y_pred), 1)
    return cm


def plot_confusion(cm, path, title=""):
    """Heatmap of errors only (diagonal masked) as % of each true class, with counts."""
    off = cm.astype(float).copy()
    np.fill_diagonal(off, np.nan)
    pct = 100 * off / cm.sum(1, keepdims=True)
    fig, ax = plt.subplots(figsize=(6, 5))
    im = ax.imshow(pct, cmap="Reds")
    for i in range(cm.shape[0]):
        for j in range(cm.shape[1]):
            if i != j and cm[i, j] > 0:
                ax.text(j, i, cm[i, j], ha="center", va="center", fontsize=7)
    ax.set_xlabel("predicted"); ax.set_ylabel("true")
    ax.set_xticks(range(cm.shape[1])); ax.set_yticks(range(cm.shape[0]))
    ax.set_title(title)
    fig.colorbar(im, ax=ax, label="% of true class (errors only)")
    fig.tight_layout(); fig.savefig(path, dpi=130); plt.close(fig)


def plot_image_grid(images, path, titles=None, ncols=10, cmap="gray", symmetric=False, suptitle=""):
    n = len(images)
    nrows = int(np.ceil(n / ncols))
    fig, axes = plt.subplots(nrows, ncols, figsize=(ncols * 1.1, nrows * 1.2), squeeze=False)
    for k, ax in enumerate(axes.flat):
        ax.axis("off")
        if k < n:
            img = images[k]
            if symmetric:
                v = np.abs(img).max()
                ax.imshow(img, cmap=cmap, vmin=-v, vmax=v)
            else:
                ax.imshow(img, cmap=cmap)
            if titles is not None:
                ax.set_title(titles[k], fontsize=7)
    if suptitle:
        fig.suptitle(suptitle)
    fig.tight_layout(); fig.savefig(path, dpi=130); plt.close(fig)
