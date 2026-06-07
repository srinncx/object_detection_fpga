"""
export_weights.py
-----------------
Converts trained PyTorch float32 weights -> Q8.8 fixed-point hex .mem files
for use with Verilog $readmemh.

Q8.8 format:
    16-bit signed integer = round(float_value * 256)
    Range: -128.0 to +127.996  (sufficient for normalised RGB inputs)
    Stored as 16-bit two's complement hex, e.g.  0100 = +1.0,  FF00 = -1.0

Output files (one value per line, 4 hex digits):
    w1.mem  -- Layer 1 weights  [16 x 3]  = 48  values
    b1.mem  -- Layer 1 biases   [16]      = 16  values
    w2.mem  -- Layer 2 weights  [8  x 16] = 128 values
    b2.mem  -- Layer 2 biases   [8]       =  8  values
    w3.mem  -- Layer 3 weights  [8  x 8]  = 64  values
    b3.mem  -- Layer 3 biases   [8]       =  8  values

Row-major order: w[i][j] means neuron i, input j.
In Verilog: w1_mem[i*3 + j] gives weight from input j to neuron i.

Usage:
    python export_weights.py
Requires:
    pip install torch numpy
"""

import torch
import torch.nn as nn
import numpy as np
import os

# ── Must match train.py exactly ───────────────────────────────────────────────
class ColorMLP(nn.Module):
    def __init__(self):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(3,  16),
            nn.ReLU(),
            nn.Linear(16,  8),
            nn.ReLU(),
            nn.Linear(8,   8),
        )
    def forward(self, x):
        return self.net(x)

# ── Q8.8 conversion ───────────────────────────────────────────────────────────
Q_SCALE = 256   # 2^8

def to_q88(float_val):
    """Convert a single float to Q8.8 signed 16-bit integer."""
    scaled = int(round(float_val * Q_SCALE))
    # Clip to int16 range
    scaled = max(-32768, min(32767, scaled))
    # Two's complement: negative numbers wrap around 2^16
    if scaled < 0:
        scaled = scaled + 65536
    return scaled

def write_mem(filepath, tensor):
    """Flatten tensor row-major and write one Q8.8 hex value per line."""
    flat = tensor.detach().numpy().flatten()
    with open(filepath, "w") as f:
        for v in flat:
            f.write(f"{to_q88(v):04X}\n")
    print(f"  {filepath:<12}  {len(flat):>4} values  "
          f"(min={flat.min():.4f}, max={flat.max():.4f})")

# ── Verify Q8.8 round-trip accuracy ──────────────────────────────────────────
def verify_inference(model):
    """
    Run a Q8.8 fixed-point forward pass on one sample per color and
    compare argmax against float32 PyTorch result.
    """
    # Extract weights as Q8.8 integers then back to float (simulates FPGA rounding)
    def q88_layer(w, b):
        wq = np.array([[to_q88(v) for v in row] for row in w.tolist()])
        bq = np.array([to_q88(v) for v in b.tolist()])
        # Convert back: divide by Q_SCALE
        wf = (np.where(wq >= 32768, wq - 65536, wq)).astype(np.float32) / Q_SCALE
        bf = (np.where(bq >= 32768, bq - 65536, bq)).astype(np.float32) / Q_SCALE
        return wf, bf

    w1 = model.net[0].weight.data
    b1 = model.net[0].bias.data
    w2 = model.net[2].weight.data
    b2 = model.net[2].bias.data
    w3 = model.net[4].weight.data
    b3 = model.net[4].bias.data

    w1q, b1q = q88_layer(w1, b1)
    w2q, b2q = q88_layer(w2, b2)
    w3q, b3q = q88_layer(w3, b3)

    # Test colors (center RGB values, normalised)
    test_colors = [
        ([240/255, 220/255,  20/255], "yellow"),
        ([230/255, 110/255,  15/255], "orange"),
        ([210/255,  15/255,  15/255], "red"),
        ([130/255,  20/255, 200/255], "violet"),
        ([ 15/255,  60/255, 210/255], "blue"),
        ([ 20/255, 180/255,  30/255], "green"),
        ([230/255, 230/255, 230/255], "white"),
        ([ 20/255,  20/255,  20/255], "black"),
    ]
    names = ["yellow","orange","red","violet","blue","green","white","black"]

    print("\n  Q8.8 round-trip verification:")
    print(f"  {'Color':<8}  {'Float pred':<12}  {'Q8.8 pred':<12}  {'Match'}")
    print(f"  {'-'*46}")
    all_match = True
    for rgb, name in test_colors:
        x = np.array(rgb, dtype=np.float32)

        # Float32 (PyTorch)
        with torch.no_grad():
            logits_f = model(torch.tensor(x).unsqueeze(0))
        pred_f = names[logits_f.argmax().item()]

        # Q8.8 simulation
        h1 = np.maximum(0, w1q @ x  + b1q)
        h2 = np.maximum(0, w2q @ h1 + b2q)
        h3 =              w3q @ h2 + b3q
        pred_q = names[int(np.argmax(h3))]

        match = "OK" if pred_f == pred_q else "MISMATCH"
        if pred_f != pred_q:
            all_match = False
        print(f"  {name:<8}  {pred_f:<12}  {pred_q:<12}  {match}")

    print()
    if all_match:
        print("  All predictions match between float32 and Q8.8.")
    else:
        print("  WARNING: Some mismatches detected — check weight ranges.")

# ── Main ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    if not os.path.exists("color_mlp.pt"):
        raise FileNotFoundError("'color_mlp.pt' not found. Run train.py first.")

    model = ColorMLP()
    model.load_state_dict(torch.load("color_mlp.pt", weights_only=True))
    model.eval()

    print("Exporting weights to Q8.8 fixed-point .mem files...")
    print(f"  Q_SCALE = {Q_SCALE}  (Q8.8: multiply float by 256, round to int16)\n")

    write_mem("w1.mem", model.net[0].weight)
    write_mem("b1.mem", model.net[0].bias)
    write_mem("w2.mem", model.net[2].weight)
    write_mem("b2.mem", model.net[2].bias)
    write_mem("w3.mem", model.net[4].weight)
    write_mem("b3.mem", model.net[4].bias)

    print(f"\n  Total weights exported: "
          f"{16*3 + 16 + 8*16 + 8 + 8*8 + 8} values")

    verify_inference(model)

    print("Done. Files: w1.mem b1.mem w2.mem b2.mem w3.mem b3.mem")
    print()
    print("Verilog usage:")
    print('  $readmemh("w1.mem", w1);  // [0:47]  16-bit signed, row-major')
    print('  $readmemh("b1.mem", b1);  // [0:15]  16-bit signed')
    print('  // Divide MAC result by 256 (arithmetic right shift 8) for Q8.8')