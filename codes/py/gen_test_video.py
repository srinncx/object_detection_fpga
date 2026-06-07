"""
gen_test_video.py
-----------------
Generates a looping test video cycling through all 8 detection colors
with smooth fades between them.

Colors  : yellow, orange, red, violet, blue, green, white, black
Hold    : 2 seconds per color (solid)
Fade    : 0.5 seconds transition between colors
FPS     : 30
Res     : 640 x 480
Output  : test_colors.mp4  (loops cleanly -- last color fades back to first)

Also generates:
    test_colors_labeled.mp4  -- same video with color name overlay

Usage:
    python gen_test_video.py

Requires:
    pip install opencv-python numpy
"""

import cv2
import numpy as np
import sys

try:
    import cv2
except ImportError:
    sys.exit("ERROR: Run: pip install opencv-python")

# ── Config ────────────────────────────────────────────────────────────────────
WIDTH       = 640
HEIGHT      = 480
FPS         = 30
HOLD_SEC    = 2.0      # seconds of solid color per class
FADE_SEC    = 0.5      # seconds of fade between colors
LOOPS       = 3        # how many full cycles in the video
OUT_PLAIN   = "test_colors.mp4"
OUT_LABELED = "test_colors_labeled.mp4"

HOLD_FRAMES = int(HOLD_SEC * FPS)
FADE_FRAMES = int(FADE_SEC * FPS)

# ── Color definitions (R, G, B) ───────────────────────────────────────────────
COLORS = [
    ("yellow",  (240, 220,  20)),
    ("orange",  (230, 110,  15)),
    ("red",     (210,  15,  15)),
    ("violet",  (130,  20, 200)),
    ("blue",    ( 15,  60, 210)),
    ("green",   ( 20, 180,  30)),
    ("white",   (230, 230, 230)),
    ("black",   ( 20,  20,  20)),
]

# ── Helpers ───────────────────────────────────────────────────────────────────
def make_frame(r, g, b, label=None):
    """
    Create a solid color frame (BGR for OpenCV).
    Optional label drawn at center.
    """
    frame = np.full((HEIGHT, WIDTH, 3), (b, g, r), dtype=np.uint8)

    if label:
        # Choose text color for contrast
        brightness = 0.299 * r + 0.587 * g + 0.114 * b
        text_color = (0, 0, 0) if brightness > 128 else (255, 255, 255)

        font       = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 2.2
        thickness  = 4

        # Center the text
        (tw, th), baseline = cv2.getTextSize(label, font, font_scale, thickness)
        tx = (WIDTH  - tw) // 2
        ty = (HEIGHT + th) // 2

        # Subtle outline for readability on mid-tones
        outline_color = (255, 255, 255) if brightness <= 128 else (0, 0, 0)
        cv2.putText(frame, label, (tx, ty), font, font_scale,
                    outline_color, thickness + 3, cv2.LINE_AA)
        cv2.putText(frame, label, (tx, ty), font, font_scale,
                    text_color, thickness, cv2.LINE_AA)

        # Small class index badge top-left
        idx = [c[0] for c in COLORS].index(label)
        badge = f"class {idx}"
        cv2.putText(frame, badge, (16, 36), cv2.FONT_HERSHEY_SIMPLEX,
                    0.7, outline_color, 3, cv2.LINE_AA)
        cv2.putText(frame, badge, (16, 36), cv2.FONT_HERSHEY_SIMPLEX,
                    0.7, text_color, 1, cv2.LINE_AA)

    return frame

def lerp_color(c1, c2, t):
    """Linearly interpolate between two (R,G,B) colors, t in [0,1]."""
    r = int(c1[0] + (c2[0] - c1[0]) * t)
    g = int(c1[1] + (c2[1] - c1[1]) * t)
    b = int(c1[2] + (c2[2] - c1[2]) * t)
    return r, g, b

def write_video(path, labeled):
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(path, fourcc, FPS, (WIDTH, HEIGHT))

    n = len(COLORS)
    total_frames = LOOPS * n * (HOLD_FRAMES + FADE_FRAMES)
    written = 0

    for loop in range(LOOPS):
        for i in range(n):
            name_cur, rgb_cur = COLORS[i]
            name_nxt, rgb_nxt = COLORS[(i + 1) % n]

            label_cur = name_cur if labeled else None
            label_nxt = name_nxt if labeled else None

            # ── Hold frames ──
            for _ in range(HOLD_FRAMES):
                writer.write(make_frame(*rgb_cur, label=label_cur))
                written += 1

            # ── Fade frames ──
            for f in range(FADE_FRAMES):
                t   = (f + 1) / (FADE_FRAMES + 1)
                rgb = lerp_color(rgb_cur, rgb_nxt, t)
                # Blend label opacity: fade out cur, fade in nxt
                frame = make_frame(*rgb, label=None)
                if labeled:
                    # Overlay both labels with complementary alpha
                    alpha_out = 1.0 - t
                    alpha_in  = t
                    for (lbl, alpha) in [(label_cur, alpha_out), (label_nxt, alpha_in)]:
                        if alpha > 0.05:
                            overlay = make_frame(*rgb, label=lbl)
                            frame   = cv2.addWeighted(frame, 1.0,
                                                      overlay, alpha * 0.6, 0)
                writer.write(frame)
                written += 1

        pct = written / total_frames * 100
        print(f"  Loop {loop+1}/{LOOPS} done  ({pct:.0f}%)")

    writer.release()

# ── Progress bar ──────────────────────────────────────────────────────────────
def progress_bar(current, total, width=40):
    filled = int(width * current / total)
    bar    = "#" * filled + "-" * (width - filled)
    pct    = current / total * 100
    print(f"\r  [{bar}] {pct:5.1f}%", end="", flush=True)

# ── Main ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    hold_f = HOLD_FRAMES
    fade_f = FADE_FRAMES
    n      = len(COLORS)
    total  = LOOPS * n * (hold_f + fade_f)
    dur    = total / FPS

    print("Generating test video...")
    print(f"  Resolution : {WIDTH}x{HEIGHT}  @  {FPS} fps")
    print(f"  Hold       : {HOLD_SEC}s per color  ({hold_f} frames)")
    print(f"  Fade       : {FADE_SEC}s transition  ({fade_f} frames)")
    print(f"  Loops      : {LOOPS}x  ({n} colors per loop)")
    print(f"  Total      : {total} frames  ({dur:.1f}s)")
    print()

    print(f"  Writing {OUT_PLAIN} ...")
    write_video(OUT_PLAIN, labeled=False)
    print(f"  Saved -> {OUT_PLAIN}")

    print(f"  Writing {OUT_LABELED} ...")
    write_video(OUT_LABELED, labeled=True)
    print(f"  Saved -> {OUT_LABELED}")

    print()
    print("Color sequence (per loop):")
    for i, (name, (r, g, b)) in enumerate(COLORS):
        bar = f"\x1b[48;2;{r};{g};{b}m    \x1b[0m"
        print(f"  {i}  {bar}  {name:<8}  RGB=({r:>3},{g:>3},{b:>3})")

    print()
    print("Done.")
    print()
    print("How to use with send_color_gui.py:")
    print("  1. Open test_colors_labeled.mp4 in a media player (fullscreen or windowed)")
    print("  2. Launch send_color_gui.py")
    print("  3. Click 'Select region' and drag over the video window")
    print("  4. Set mode to Debug to verify predictions locally first")
    print("  5. Switch to FPGA mode once debug predictions are correct")