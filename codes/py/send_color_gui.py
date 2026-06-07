"""
send_color_gui.py
-----------------
Interactive screen region selector with two modes:

  FPGA mode  -- captures region, sends [0xAA][R][G][B][0x55] over UART
  Debug mode -- captures region, runs Q8.8 MLP inference locally, no COM port needed

Controls:
  - Click and drag on the overlay to select a region
  - Region is highlighted with a live color preview
  - Toggle mode, start/stop sending from the GUI

Requires:
    pip install mss pyserial numpy pillow
    (tkinter ships with standard Python on Windows)

Usage:
    python send_color_gui.py
"""

import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time
import sys
import os
import numpy as np

try:
    import mss
except ImportError:
    sys.exit("ERROR: Run: pip install mss")

try:
    from PIL import Image, ImageTk
except ImportError:
    sys.exit("ERROR: Run: pip install pillow")

try:
    import serial
    import serial.tools.list_ports
    SERIAL_AVAILABLE = True
except ImportError:
    SERIAL_AVAILABLE = False

# ── Constants ─────────────────────────────────────────────────────────────────
BAUD_RATE   = 9600
START_BYTE  = 0xAA
END_BYTE    = 0x55
COLOR_NAMES = ["yellow", "orange", "red", "violet", "blue", "green", "white", "black"]

# ── Q8.8 MLP for debug mode ───────────────────────────────────────────────────
class Q88MLP:
    def __init__(self):
        self.loaded = False

    def _load_mem(self, path, shape):
        vals = []
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                v = int(line, 16)
                if v >= 32768:
                    v -= 65536
                vals.append(v / 256.0)
        return np.array(vals, dtype=np.float32).reshape(shape)

    def load(self, folder="."):
        try:
            self.w1 = self._load_mem(os.path.join(folder, "w1.mem"), (16, 3))
            self.b1 = self._load_mem(os.path.join(folder, "b1.mem"), (16,))
            self.w2 = self._load_mem(os.path.join(folder, "w2.mem"), (8, 16))
            self.b2 = self._load_mem(os.path.join(folder, "b2.mem"), (8,))
            self.w3 = self._load_mem(os.path.join(folder, "w3.mem"), (8, 8))
            self.b3 = self._load_mem(os.path.join(folder, "b3.mem"), (8,))
            self.loaded = True
            return True
        except FileNotFoundError:
            return False

    def predict(self, r, g, b):
        if not self.loaded:
            return "no weights", -1
        x  = np.array([r / 255.0, g / 255.0, b / 255.0], dtype=np.float32)
        h1 = np.maximum(0, self.w1 @ x  + self.b1)
        h2 = np.maximum(0, self.w2 @ h1 + self.b2)
        h3 =               self.w3 @ h2 + self.b3
        idx = int(np.argmax(h3))
        return COLOR_NAMES[idx], idx

mlp = Q88MLP()

# ── Capture helper ────────────────────────────────────────────────────────────
def capture_avg_rgb(x, y, w, h):
    w = max(1, w)
    h = max(1, h)
    with mss.mss() as sct:
        mon = {"top": y, "left": x, "width": w, "height": h}
        img = sct.grab(mon)
        arr = np.frombuffer(img.raw, dtype=np.uint8).reshape((h, w, 4))
        return int(arr[:,:,2].mean()), int(arr[:,:,1].mean()), int(arr[:,:,0].mean())

# ── Region selector overlay ───────────────────────────────────────────────────
class RegionSelector:
    def __init__(self, callback):
        self.callback = callback
        self.start_x = self.start_y = 0
        self.rect_id = None

    def select(self):
        self.top = tk.Toplevel()
        self.top.attributes("-fullscreen", True)
        self.top.attributes("-alpha", 0.25)
        self.top.attributes("-topmost", True)
        self.top.configure(bg="black")

        self.canvas = tk.Canvas(self.top, cursor="cross", bg="black",
                                highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        lbl = tk.Label(self.top,
                       text="Click and drag to select capture region  |  ESC to cancel",
                       bg="#111111", fg="white", font=("Consolas", 13))
        lbl.place(relx=0.5, rely=0.02, anchor="n")

        self.canvas.bind("<ButtonPress-1>",  self._on_press)
        self.canvas.bind("<B1-Motion>",       self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)
        self.top.bind("<Escape>", lambda e: self.top.destroy())
        self.top.focus_force()

    def _on_press(self, e):
        self.start_x, self.start_y = e.x, e.y
        if self.rect_id:
            self.canvas.delete(self.rect_id)

    def _on_drag(self, e):
        if self.rect_id:
            self.canvas.delete(self.rect_id)
        self.rect_id = self.canvas.create_rectangle(
            self.start_x, self.start_y, e.x, e.y,
            outline="#00FF88", width=2, fill="#00FF88", stipple="gray25"
        )

    def _on_release(self, e):
        x1 = min(self.start_x, e.x)
        y1 = min(self.start_y, e.y)
        x2 = max(self.start_x, e.x)
        y2 = max(self.start_y, e.y)
        self.top.destroy()
        if x2 - x1 > 4 and y2 - y1 > 4:
            self.callback(x1, y1, x2 - x1, y2 - y1)

# ── Main GUI ──────────────────────────────────────────────────────────────────
class App:
    def __init__(self, root):
        self.root = root
        self.root.title("Color Detection Sender")
        self.root.resizable(False, False)

        self.mode         = tk.StringVar(value="debug")
        self.running      = False
        self.ser          = None
        self.region       = [100, 100, 100, 100]
        self.send_thread  = None
        self.packet_count = 0

        self._build_ui()
        self._refresh_ports()
        mlp.load(".")

        # Lock window size after all widgets are laid out
        self.root.update_idletasks()
        w = self.root.winfo_width()
        h = self.root.winfo_height()
        self.root.minsize(w, h)
        self.root.maxsize(w, h)

    # ── UI ────────────────────────────────────────────────────────────────────
    def _build_ui(self):
        PAD = dict(padx=10, pady=6)

        # Mode
        mode_frame = ttk.LabelFrame(self.root, text="Mode", padding=8)
        mode_frame.grid(row=0, column=0, columnspan=2, sticky="ew", **PAD)
        ttk.Radiobutton(mode_frame, text="Debug (no FPGA, local inference)",
                        variable=self.mode, value="debug",
                        command=self._on_mode_change).pack(anchor="w")
        ttk.Radiobutton(mode_frame, text="FPGA (send via UART)",
                        variable=self.mode, value="fpga",
                        command=self._on_mode_change).pack(anchor="w")

        # UART
        self.uart_frame = ttk.LabelFrame(self.root, text="UART settings", padding=8)
        self.uart_frame.grid(row=1, column=0, columnspan=2, sticky="ew", **PAD)
        ttk.Label(self.uart_frame, text="Port:").grid(row=0, column=0, sticky="w")
        self.port_var = tk.StringVar()
        self.port_cb  = ttk.Combobox(self.uart_frame, textvariable=self.port_var,
                                     width=14, state="readonly")
        self.port_cb.grid(row=0, column=1, sticky="w", padx=(4, 0))
        ttk.Button(self.uart_frame, text="Refresh",
                   command=self._refresh_ports).grid(row=0, column=2, padx=(6, 0))
        ttk.Label(self.uart_frame, text="Baud:").grid(row=1, column=0, sticky="w", pady=(4,0))
        ttk.Label(self.uart_frame, text=str(BAUD_RATE)).grid(
            row=1, column=1, sticky="w", padx=(4, 0), pady=(4, 0))

        # Region
        region_frame = ttk.LabelFrame(self.root, text="Capture region", padding=8)
        region_frame.grid(row=2, column=0, columnspan=2, sticky="ew", **PAD)
        self.region_lbl = ttk.Label(region_frame,
                                    text="x=100  y=100  w=100  h=100",
                                    font=("Consolas", 10), width=32, anchor="w")
        self.region_lbl.grid(row=0, column=0, sticky="w")
        ttk.Button(region_frame, text="Select region",
                   command=self._select_region).grid(row=0, column=1, padx=(10, 0))

        # Interval
        int_frame = ttk.LabelFrame(self.root, text="Interval (seconds)", padding=8)
        int_frame.grid(row=3, column=0, columnspan=2, sticky="ew", **PAD)
        self.interval_var = tk.DoubleVar(value=1.0)
        ttk.Scale(int_frame, from_=0.1, to=5.0, orient="horizontal",
                  variable=self.interval_var, length=200).pack(side="left")
        self.interval_lbl = ttk.Label(int_frame, text="1.0s", width=5, anchor="w")
        self.interval_lbl.pack(side="left", padx=(8, 0))
        self.interval_var.trace_add("write", self._update_interval_lbl)

        # Preview — all labels fixed width to prevent layout reflow
        preview_frame = ttk.LabelFrame(self.root, text="Live preview", padding=8)
        preview_frame.grid(row=4, column=0, columnspan=2, sticky="ew", **PAD)

        self.color_canvas = tk.Canvas(preview_frame, width=60, height=40,
                                      bg="#888888", relief="sunken", bd=1)
        self.color_canvas.grid(row=0, column=0, rowspan=3, padx=(0, 12))

        self.rgb_lbl = ttk.Label(preview_frame,
                                 text="R=---  G=---  B=---",
                                 font=("Consolas", 11),
                                 width=28, anchor="w")
        self.rgb_lbl.grid(row=0, column=1, sticky="w")

        self.pred_lbl = ttk.Label(preview_frame,
                                  text="Prediction: ---     ",
                                  font=("Consolas", 11, "bold"),
                                  width=28, anchor="w")
        self.pred_lbl.grid(row=1, column=1, sticky="w")

        self.packet_lbl = ttk.Label(preview_frame,
                                    text="Packet: ----------",
                                    font=("Consolas", 10),
                                    foreground="gray",
                                    width=36, anchor="w")
        self.packet_lbl.grid(row=2, column=1, sticky="w", pady=(4, 0))

        # Log
        log_frame = ttk.LabelFrame(self.root, text="Log", padding=4)
        log_frame.grid(row=5, column=0, columnspan=2, sticky="ew", **PAD)
        self.log_text = tk.Text(log_frame, height=6, width=54,
                                font=("Consolas", 9), state="disabled",
                                bg="#1a1a1a", fg="#c8c8c8", relief="flat")
        self.log_text.pack(fill="both")

        # Buttons
        btn_frame = ttk.Frame(self.root)
        btn_frame.grid(row=6, column=0, columnspan=2, pady=(4, 10))
        self.start_btn = ttk.Button(btn_frame, text="Start",
                                    command=self._start, width=12)
        self.start_btn.pack(side="left", padx=6)
        self.stop_btn  = ttk.Button(btn_frame, text="Stop",
                                    command=self._stop, width=12, state="disabled")
        self.stop_btn.pack(side="left", padx=6)

        self._on_mode_change()

    # ── Helpers ───────────────────────────────────────────────────────────────
    def _log(self, msg):
        self.log_text.configure(state="normal")
        self.log_text.insert("end", msg + "\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _update_interval_lbl(self, *_):
        self.interval_lbl.config(text=f"{self.interval_var.get():.1f}s")

    def _on_mode_change(self):
        is_fpga = self.mode.get() == "fpga"
        state   = "normal" if is_fpga else "disabled"
        for child in self.uart_frame.winfo_children():
            try:
                child.configure(state=state)
            except tk.TclError:
                pass

    def _refresh_ports(self):
        if not SERIAL_AVAILABLE:
            self.port_cb["values"] = ["pyserial not installed"]
            return
        ports = [p.device for p in serial.tools.list_ports.comports()]
        self.port_cb["values"] = ports if ports else ["No ports found"]
        if ports:
            self.port_var.set(ports[0])

    def _select_region(self):
        self.root.withdraw()
        time.sleep(0.15)
        RegionSelector(self._on_region_selected).select()

    def _on_region_selected(self, x, y, w, h):
        self.region = [x, y, w, h]
        self.region_lbl.config(text=f"x={x}  y={y}  w={w}  h={h}")
        self._log(f"Region set: x={x} y={y} w={w} h={h}")
        self.root.deiconify()

    # ── Start / Stop ──────────────────────────────────────────────────────────
    def _start(self):
        if self.mode.get() == "fpga":
            if not SERIAL_AVAILABLE:
                messagebox.showerror("Error", "pyserial not installed.\npip install pyserial")
                return
            port = self.port_var.get()
            if not port or "No ports" in port or "not installed" in port:
                messagebox.showerror("Error", "Select a valid COM port.")
                return
            try:
                self.ser = serial.Serial(
                    port=port, baudrate=BAUD_RATE,
                    bytesize=serial.EIGHTBITS,
                    parity=serial.PARITY_NONE,
                    stopbits=serial.STOPBITS_ONE,
                    timeout=1.0
                )
                self._log(f"Opened {port} @ {BAUD_RATE} baud")
            except Exception as e:
                messagebox.showerror("Error", f"Cannot open port:\n{e}")
                return
        else:
            if not mlp.loaded:
                self._log("WARNING: .mem files not found — predictions unavailable.")
                self._log("  Run export_weights.py first.")

        self.running      = True
        self.packet_count = 0
        self.start_btn.config(state="disabled")
        self.stop_btn.config(state="normal")
        self._log(f"Started in {self.mode.get().upper()} mode.")
        self.send_thread = threading.Thread(target=self._loop, daemon=True)
        self.send_thread.start()

    def _stop(self):
        self.running = False
        if self.ser and self.ser.is_open:
            self.ser.close()
            self._log("Serial port closed.")
        self.ser = None
        self.start_btn.config(state="normal")
        self.stop_btn.config(state="disabled")
        self._log(f"Stopped. Total packets: {self.packet_count}")

    # ── Capture loop ──────────────────────────────────────────────────────────
    def _loop(self):
        while self.running:
            try:
                x, y, w, h = self.region
                r, g, b    = capture_avg_rgb(x, y, w, h)
                packet     = bytes([START_BYTE, r, g, b, END_BYTE])

                if self.mode.get() == "fpga" and self.ser and self.ser.is_open:
                    self.ser.write(packet)
                    self.ser.flush()

                self.packet_count += 1
                pred_name = mlp.predict(r, g, b)[0] if mlp.loaded else "no weights"
                self.root.after(0, self._update_ui, r, g, b, pred_name, packet)

            except Exception as e:
                self.root.after(0, self._log, f"ERROR: {e}")
                self.running = False
                self.root.after(0, self._stop)
                break

            time.sleep(max(0.05, self.interval_var.get()))

    def _update_ui(self, r, g, b, pred_name, packet):
        self.color_canvas.configure(bg=f"#{r:02X}{g:02X}{b:02X}")
        self.rgb_lbl.config(   text=f"R={r:>3}  G={g:>3}  B={b:>3}")
        self.pred_lbl.config(  text=f"Prediction: {pred_name:<8}")
        self.packet_lbl.config(text=f"Packet: {packet.hex().upper()}")
        if self.packet_count % 5 == 1:
            tag = "[FPGA]" if self.mode.get() == "fpga" else "[DBG] "
            self._log(f"{tag} #{self.packet_count:>4}  "
                      f"R={r:>3} G={g:>3} B={b:>3}  "
                      f"{pred_name:<8}  {packet.hex().upper()}")

# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    root = tk.Tk()
    app  = App(root)
    root.mainloop()