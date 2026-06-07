"""
train.py
--------
Trains a 3-layer MLP on the RGB color dataset produced by gen_dataset.py.

Architecture : 3 -> 16 -> 8 -> 8  (ReLU hidden, CrossEntropy output)
Precision    : float32 during training (exported to Q8.8 by export_weights.py)
Epochs       : 100
Optimizer    : Adam, lr=0.001
Loss         : CrossEntropyLoss

Outputs:
    color_mlp.pt          -- saved PyTorch model (state_dict)
    loss_curve.png        -- training + validation loss plot
    confusion_matrix.png  -- test-set confusion matrix

Usage:
    python train.py
Requires:
    pip install torch numpy pandas matplotlib scikit-learn
"""

import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from sklearn.metrics import confusion_matrix, ConfusionMatrixDisplay
import os

# ── Config ────────────────────────────────────────────────────────────────────
TRAIN_CSV   = "train.csv"
TEST_CSV    = "test.csv"
MODEL_OUT   = "color_mlp.pt"
EPOCHS      = 100
BATCH_SIZE  = 64
LR          = 0.001
SEED        = 42

LABEL_NAMES = ["yellow", "orange", "red", "violet", "blue", "green", "white", "black"]

torch.manual_seed(SEED)
np.random.seed(SEED)

# ── Dataset ───────────────────────────────────────────────────────────────────
class ColorDataset(Dataset):
    def __init__(self, csv_path):
        df = pd.read_csv(csv_path)
        # Normalise RGB to [0, 1]
        self.X = torch.tensor(df[["R", "G", "B"]].values / 255.0, dtype=torch.float32)
        self.y = torch.tensor(df["label"].values, dtype=torch.long)

    def __len__(self):
        return len(self.y)

    def __getitem__(self, idx):
        return self.X[idx], self.y[idx]

# ── Model ─────────────────────────────────────────────────────────────────────
class ColorMLP(nn.Module):
    def __init__(self):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(3, 16),
            nn.ReLU(),
            nn.Linear(16, 8),
            nn.ReLU(),
            nn.Linear(8, 8),   # 8 output classes
        )

    def forward(self, x):
        return self.net(x)

# ── Training loop ─────────────────────────────────────────────────────────────
def train():
    # Data
    train_ds = ColorDataset(TRAIN_CSV)
    test_ds  = ColorDataset(TEST_CSV)
    train_dl = DataLoader(train_ds, batch_size=BATCH_SIZE, shuffle=True)
    test_dl  = DataLoader(test_ds,  batch_size=256)

    model     = ColorMLP()
    criterion = nn.CrossEntropyLoss()
    optimizer = torch.optim.Adam(model.parameters(), lr=LR)

    train_losses = []
    test_losses  = []

    print(f"Training MLP: 3 -> 16 -> 8 -> 8  |  {EPOCHS} epochs  |  lr={LR}")
    print(f"Train samples: {len(train_ds)}   Test samples: {len(test_ds)}")
    print("-" * 52)

    for epoch in range(1, EPOCHS + 1):
        # ── Train ──
        model.train()
        running_loss = 0.0
        for xb, yb in train_dl:
            optimizer.zero_grad()
            loss = criterion(model(xb), yb)
            loss.backward()
            optimizer.step()
            running_loss += loss.item() * len(xb)
        train_loss = running_loss / len(train_ds)

        # ── Validate ──
        model.eval()
        with torch.no_grad():
            val_loss = sum(
                criterion(model(xb), yb).item() * len(xb)
                for xb, yb in test_dl
            ) / len(test_ds)

        train_losses.append(train_loss)
        test_losses.append(val_loss)

        if epoch % 10 == 0 or epoch == 1:
            print(f"  Epoch {epoch:>3}/{EPOCHS}  "
                  f"train_loss={train_loss:.4f}  "
                  f"val_loss={val_loss:.4f}")

    # ── Final accuracy ──
    model.eval()
    all_preds, all_labels = [], []
    with torch.no_grad():
        for xb, yb in test_dl:
            preds = model(xb).argmax(dim=1)
            all_preds.extend(preds.numpy())
            all_labels.extend(yb.numpy())

    all_preds  = np.array(all_preds)
    all_labels = np.array(all_labels)
    accuracy   = (all_preds == all_labels).mean() * 100.0

    print("-" * 52)
    print(f"Test accuracy: {accuracy:.2f}%")

    # ── Save model ──
    torch.save(model.state_dict(), MODEL_OUT)
    print(f"Model saved -> {MODEL_OUT}")

    # ── Loss curve ──
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.plot(range(1, EPOCHS + 1), train_losses, label="Train loss", linewidth=1.5)
    ax.plot(range(1, EPOCHS + 1), test_losses,  label="Val loss",   linewidth=1.5, linestyle="--")
    ax.set_xlabel("Epoch")
    ax.set_ylabel("Cross-entropy loss")
    ax.set_title("Training and validation loss")
    ax.legend()
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig("loss_curve.png", dpi=120)
    plt.close(fig)
    print("Loss curve  -> loss_curve.png")

    # ── Confusion matrix ──
    cm  = confusion_matrix(all_labels, all_preds)
    fig, ax = plt.subplots(figsize=(7, 6))
    disp = ConfusionMatrixDisplay(confusion_matrix=cm, display_labels=LABEL_NAMES)
    disp.plot(ax=ax, colorbar=False, cmap="Blues")
    ax.set_title(f"Confusion matrix  (test accuracy {accuracy:.1f}%)")
    fig.tight_layout()
    fig.savefig("confusion_matrix.png", dpi=120)
    plt.close(fig)
    print("Confusion   -> confusion_matrix.png")
    print()
    print("Done.")

# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    for f in [TRAIN_CSV, TEST_CSV]:
        if not os.path.exists(f):
            raise FileNotFoundError(
                f"'{f}' not found. Run gen_dataset.py first."
            )
    train()