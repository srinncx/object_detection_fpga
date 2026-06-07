"""
gen_dataset.py
--------------
Generates a programmatic RGB dataset for 8-class color detection.
Colors: yellow, orange, red, violet, blue, green, white, black

Each color is defined by a central RGB value and a jitter range.
Uniform random jitter is applied to simulate real-world variation.

Output: dataset.csv with columns  R, G, B, label, label_name
        - train split : 1000 samples per class (8000 total)
        - test  split :  200 samples per class (1600 total)

Usage:
    python gen_dataset.py
Outputs:
    train.csv
    test.csv
"""

import csv
import random
import os

# ── Reproducibility ──────────────────────────────────────────────────────────
random.seed(42)

# ── Color definitions ─────────────────────────────────────────────────────────
# Each entry: (label_index, label_name, center_R, center_G, center_B, jitter)
# jitter = max ± offset applied independently to each channel (uniform)
COLORS = [
    (0, "yellow",  240, 220,  20,  25),
    (1, "orange",  230, 110,  15,  25),
    (2, "red",     210,  15,  15,  25),
    (3, "violet",  130,  20, 200,  25),
    (4, "blue",     15,  60, 210,  25),
    (5, "green",    20, 180,  30,  25),
    (6, "white",   230, 230, 230,  20),
    (7, "black",    20,  20,  20,  18),
]

TRAIN_SAMPLES = 1000   # per class
TEST_SAMPLES  =  200   # per class

# ── Helper ────────────────────────────────────────────────────────────────────
def clamp(value, lo=0, hi=255):
    return max(lo, min(hi, value))

def generate_samples(color_def, n):
    """Return n (R, G, B, label, label_name) rows for one color."""
    idx, name, cr, cg, cb, jitter = color_def
    samples = []
    for _ in range(n):
        r = clamp(cr + random.randint(-jitter, jitter))
        g = clamp(cg + random.randint(-jitter, jitter))
        b = clamp(cb + random.randint(-jitter, jitter))
        samples.append((r, g, b, idx, name))
    return samples

def write_csv(filepath, rows):
    with open(filepath, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["R", "G", "B", "label", "label_name"])
        writer.writerows(rows)
    print(f"  Wrote {len(rows):>5} rows -> {filepath}")

# ── Build splits ──────────────────────────────────────────────────────────────
def build_dataset():
    train_rows = []
    test_rows  = []

    for color in COLORS:
        train_rows.extend(generate_samples(color, TRAIN_SAMPLES))
        test_rows.extend(generate_samples(color,  TEST_SAMPLES))

    # Shuffle both splits independently
    random.shuffle(train_rows)
    random.shuffle(test_rows)

    return train_rows, test_rows

# ── Main ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("Generating dataset...")
    train_rows, test_rows = build_dataset()

    write_csv("train.csv", train_rows)
    write_csv("test.csv",  test_rows)

    print()
    print(f"Train: {len(train_rows)} samples  ({TRAIN_SAMPLES} per class x {len(COLORS)} classes)")
    print(f"Test : {len(test_rows)} samples  ({TEST_SAMPLES} per class x {len(COLORS)} classes)")
    print()
    print("Color centers used:")
    print(f"  {'Label':<8} {'Name':<8}  R    G    B   Jitter")
    print(f"  {'-'*46}")
    for idx, name, cr, cg, cb, jitter in COLORS:
        print(f"  {idx:<8} {name:<8}  {cr:<4} {cg:<4} {cb:<4} ±{jitter}")
    print()
    print("Done. Files: train.csv, test.csv")