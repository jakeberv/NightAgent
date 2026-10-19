# Tools

Reusable code written by the student. One line per tool: name, what it does, how to call it.

- `tools/data.py` — download + checksum MNIST, fixed-seed 55k/5k/10k split. `load_mnist()` → dict of `x_/y_{train,val,test}`.
- `tools/train.py` — generic Adam/cross-entropy loop logging train/val/test acc, wall-clock, #params, per-epoch val. `train_and_evaluate(model_fn, data, seed=…, epochs=…, device="cpu")`.
- `tools/plotting.py` — `confusion_matrix`, `plot_confusion` (errors-only heatmap), `plot_image_grid`.
