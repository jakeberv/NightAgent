"""Generic PyTorch train/evaluate loop for MNIST classifiers.

Every run logs validation and test accuracy, wall-clock time and parameter
count (agreed M00). Inputs are scaled to [0, 1] then standardised with the
*training-set* mean/std only.

Usage:
    from tools.data import load_mnist
    from tools.train import train_and_evaluate
    res = train_and_evaluate(lambda: torch.nn.Sequential(torch.nn.Flatten(), torch.nn.Linear(784, 10)),
                             load_mnist(), seed=0, epochs=10)
    res["val_acc"], res["test_acc"], res["train_time_s"], res["n_params"]
    res["val_pred"], res["test_pred"]   # numpy arrays for confusion matrices
    res["model"]                        # trained model (on CPU)
"""
import random
import time

import numpy as np
import torch
import torch.nn.functional as F


def set_seed(seed):
    """Seed python, numpy and torch RNGs."""
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)


def to_tensors(data, device):
    """Convert the load_mnist dict to standardised float tensors of shape (N,1,28,28)."""
    x_train = data["x_train"].astype(np.float32) / 255.0
    mean, std = float(x_train.mean()), float(x_train.std())
    out = {"norm_mean": mean, "norm_std": std}
    for split in ("train", "val", "test"):
        x = (data[f"x_{split}"].astype(np.float32) / 255.0 - mean) / std
        out[f"x_{split}"] = torch.from_numpy(x).unsqueeze(1).to(device)
        out[f"y_{split}"] = torch.from_numpy(data[f"y_{split}"]).to(device)
    return out


@torch.no_grad()
def predict(model, x, batch_size=2048):
    """Return argmax class predictions for tensor x as a numpy array."""
    model.eval()
    preds = [model(x[i:i + batch_size]).argmax(1) for i in range(0, len(x), batch_size)]
    return torch.cat(preds).cpu().numpy()


def train_and_evaluate(model_fn, data, seed=0, epochs=10, batch_size=128, lr=1e-3,
                       weight_decay=0.0, device="cpu", verbose=True):
    """Train model_fn() with Adam + cross-entropy; return metrics and predictions.

    Model selection is NOT done here; the final-epoch model is evaluated on both
    val and test. Per-epoch val accuracy is recorded in `history`.
    """
    set_seed(seed)
    t = to_tensors(data, device)
    model = model_fn().to(device)
    n_params = sum(p.numel() for p in model.parameters())
    opt = torch.optim.Adam(model.parameters(), lr=lr, weight_decay=weight_decay)
    g = torch.Generator(device="cpu").manual_seed(seed)
    n = len(t["x_train"])
    history = []
    start = time.perf_counter()
    for epoch in range(epochs):
        model.train()
        perm = torch.randperm(n, generator=g).to(device)
        total_loss = 0.0
        for i in range(0, n, batch_size):
            idx = perm[i:i + batch_size]
            loss = F.cross_entropy(model(t["x_train"][idx]), t["y_train"][idx])
            opt.zero_grad()
            loss.backward()
            opt.step()
            total_loss += loss.item() * len(idx)
        val_acc = float((predict(model, t["x_val"]) == data["y_val"]).mean())
        history.append({"epoch": epoch + 1, "train_loss": total_loss / n, "val_acc": val_acc})
        if verbose:
            print(f"seed {seed} epoch {epoch + 1}: loss {total_loss / n:.4f} val {val_acc:.4f}")
    train_time = time.perf_counter() - start
    val_pred, test_pred = predict(model, t["x_val"]), predict(model, t["x_test"])
    return {
        "seed": seed, "epochs": epochs, "batch_size": batch_size, "lr": lr,
        "weight_decay": weight_decay, "device": device, "n_params": n_params,
        "train_time_s": train_time,
        "train_acc": float((predict(model, t["x_train"]) == data["y_train"]).mean()),
        "val_acc": float((val_pred == data["y_val"]).mean()),
        "test_acc": float((test_pred == data["y_test"]).mean()),
        "history": history, "val_pred": val_pred, "test_pred": test_pred,
        "model": model.cpu(),
    }
