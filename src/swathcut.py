"""
SwathCut - cut a lat/lon area out of GPM GMI L1B or GOSAT-GW AMSR3 L1R swath
files (.nc) and save the brightness temperatures as text. Window around extract_gmi_band.extract().

    python swathcut.py

Pick one or more .nc files, type (or drag on the preview map) the lat/lon box,
choose swaths and output folder, press Convert.
"""
import json
import os
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import numpy as np
from netCDF4 import Dataset

from extract_gmi_band import GMI_LABELS, extract, preview_data

APP_NAME = "SwathCut"
__version__ = "0.2.0"
AUTHOR = "Lev Mitnik"

HOW_TO = """1. Press Add... and pick one or more .nc files:
   GPM GMI L1B, or GOSAT-GW AMSR3 L1R (Resampled Tb, *_S1RTBR*).
2. Set the area: type Lat/Lon limits, or press Preview / select area
   and draw (or drag/resize) the box on the map.
   Longitudes are -180..180; Lon min > Lon max crosses the 180 meridian.
3. GMI: tick the swaths S1 (10-89 GHz) and/or S2 (166-183 GHz).
   AMSR3: always one low_freq file (6.9-36.5 GHz, 6.9 GHz footprint),
   in the same layout as AMSR2 *_low_freq.txt.
4. Choose the output folder (default: folder of the first file).
   The area and the folders are remembered for the next start.
5. Press Convert. One .txt file is written per file and swath.

Output: 3 header lines (time, orbit, equator crossing), a
#lat #lon #channel... line, then "lat lon Tb..." rows in K."""

SETTINGS = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")),
                        APP_NAME, "settings.json")


def resource(name):
    """Path of a bundled file: SwathCut/assets/ in the source tree, or inside the .exe."""
    base = getattr(sys, "_MEIPASS", os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
    return os.path.join(base, "assets", name)


def load_settings():
    try:
        with open(SETTINGS, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def save_settings(**changes):
    data = {**load_settings(), **changes}
    try:
        os.makedirs(os.path.dirname(SETTINGS), exist_ok=True)
        with open(SETTINGS, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=1)
    except OSError:
        pass  # remembering folders is a convenience only


ABOUT = f"""{APP_NAME}  version {__version__}

Extracts a latitude/longitude area from GPM GMI Level-1B and
GOSAT-GW AMSR3 Level-1R swath files (.nc) and saves
brightness temperatures as text.

\u00a9 2026 {AUTHOR}. Released under the MIT License.

GMI data: NASA / JAXA Global Precipitation Measurement mission.
AMSR3 data: JAXA GOSAT-GW mission."""


class ConverterApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_NAME)
        self.resizable(False, False)
        try:
            self.iconbitmap(default=resource("swathcut.ico"))  # also used by the preview window
        except tk.TclError:
            pass  # icon missing: keep the default one

        pad = dict(padx=6, pady=4)

        # --- Help (Windows menu bars cannot right-align, so use a menubutton)
        helpbtn = ttk.Menubutton(self, text="Help")
        helpmenu = tk.Menu(helpbtn, tearoff=False)
        helpmenu.add_command(label="How to use",
                             command=lambda: messagebox.showinfo(f"How to use {APP_NAME}", HOW_TO))
        helpmenu.add_separator()
        helpmenu.add_command(label=f"About {APP_NAME}",
                             command=lambda: messagebox.showinfo(f"About {APP_NAME}", ABOUT))
        helpbtn["menu"] = helpmenu
        helpbtn.grid(row=0, column=0, sticky="e", padx=6, pady=(4, 0))

        # --- Files
        ff = ttk.LabelFrame(self, text="Input files (.nc)")
        ff.grid(row=1, column=0, sticky="ew", **pad)
        self.files = tk.Listbox(ff, width=70, height=5, selectmode=tk.EXTENDED)
        self.files.grid(row=0, column=0, rowspan=2, **pad)
        ttk.Button(ff, text="Add...", command=self.add_files).grid(row=0, column=1, sticky="ew", **pad)
        ttk.Button(ff, text="Remove", command=self.remove_files).grid(row=1, column=1, sticky="new", **pad)

        # --- Area
        af = ttk.LabelFrame(self, text="Area (degrees, longitude -180..180)")
        af.grid(row=2, column=0, sticky="ew", **pad)
        self.box = {}
        saved_box = load_settings().get("box", {})
        for col, (key, label, default) in enumerate([
                ("lat_min", "Lat min", "50"), ("lat_max", "Lat max", "65"),
                ("lon_min", "Lon min", "-180"), ("lon_max", "Lon max", "180")]):
            ttk.Label(af, text=label).grid(row=0, column=2 * col, sticky="e", **pad)
            v = saved_box.get(key)
            self.box[key] = tk.StringVar(value=f"{v:g}" if isinstance(v, (int, float)) else default)
            ttk.Entry(af, textvariable=self.box[key], width=8).grid(row=0, column=2 * col + 1, **pad)

        # --- Swaths
        sf = ttk.LabelFrame(self, text="GMI swaths  (AMSR3 L1R: always one low_freq file)")
        sf.grid(row=3, column=0, sticky="ew", **pad)
        self.s1 = tk.BooleanVar(value=True)
        self.s2 = tk.BooleanVar(value=False)
        ttk.Checkbutton(sf, text="S1  (10-89 GHz)", variable=self.s1).grid(row=0, column=0, **pad)
        ttk.Checkbutton(sf, text="S2  (166-183 GHz)", variable=self.s2).grid(row=0, column=1, **pad)

        # --- Output
        of = ttk.LabelFrame(self, text="Output folder")
        of.grid(row=4, column=0, sticky="ew", **pad)
        self.out_dir = tk.StringVar(value=load_settings().get("output_dir", ""))
        ttk.Entry(of, textvariable=self.out_dir, width=62).grid(row=0, column=0, **pad)
        ttk.Button(of, text="Browse...", command=self.pick_out_dir).grid(row=0, column=1, **pad)

        # --- Actions
        bf = ttk.Frame(self)
        bf.grid(row=5, column=0, sticky="ew", **pad)
        ttk.Label(bf, text="Preview channel").pack(side=tk.LEFT)
        self.channel = ttk.Combobox(bf, values=GMI_LABELS[9], width=6, state="readonly")
        self.channel.set("89v")
        self.channel.pack(side=tk.LEFT, padx=6)
        ttk.Button(bf, text="Preview / select area", command=self.preview).pack(side=tk.LEFT, padx=6)
        self.convert_btn = ttk.Button(bf, text="Convert", command=self.convert)
        self.convert_btn.pack(side=tk.RIGHT, padx=6)

        # --- Log
        self.log_box = tk.Text(self, width=85, height=10, state=tk.DISABLED)
        self.log_box.grid(row=6, column=0, **pad)

    # ---------------------------------------------------------------- helpers
    def log(self, msg):
        def put():
            self.log_box.configure(state=tk.NORMAL)
            self.log_box.insert(tk.END, msg + "\n")
            self.log_box.see(tk.END)
            self.log_box.configure(state=tk.DISABLED)
        self.after(0, put)

    def add_files(self):
        names = filedialog.askopenfilenames(title="Select .nc files",
                                            initialdir=load_settings().get("input_dir"),
                                            filetypes=[("netCDF", "*.nc"), ("All files", "*.*")])
        if names:
            save_settings(input_dir=os.path.dirname(names[0]))
        for n in names:
            if n not in self.files.get(0, tk.END):
                self.files.insert(tk.END, n)
        if names and not self.out_dir.get():
            self.out_dir.set(os.path.dirname(names[0]))

    def remove_files(self):
        for i in reversed(self.files.curselection()):
            self.files.delete(i)

    def pick_out_dir(self):
        d = filedialog.askdirectory(title="Output folder", initialdir=self.out_dir.get() or None)
        if d:
            self.out_dir.set(d)

    def read_box(self):
        try:
            b = {k: float(v.get()) for k, v in self.box.items()}
        except ValueError:
            raise ValueError("Lat/lon limits must be numbers.")
        if not (-90 <= b["lat_min"] < b["lat_max"] <= 90):
            raise ValueError("Need -90 <= Lat min < Lat max <= 90.")
        if not all(-180 <= b[k] <= 180 for k in ("lon_min", "lon_max")):
            raise ValueError("Longitudes must be within -180..180.")
        return b

    # ---------------------------------------------------------------- preview
    def preview(self):
        sel = self.files.curselection()
        idx = sel[0] if sel else 0
        if self.files.size() == 0:
            messagebox.showinfo("Preview", "Add a .nc file first.")
            return
        try:
            import matplotlib
            matplotlib.use("TkAgg")
            from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
            from matplotlib.figure import Figure
            from matplotlib.widgets import RectangleSelector
        except ImportError:
            messagebox.showerror("Preview", "Preview needs matplotlib:  pip install matplotlib")
            return

        fname = self.files.get(idx)
        try:
            with Dataset(fname) as nc:
                lat, lon, tb, labels = preview_data(nc)
        except (OSError, KeyError, ValueError) as e:
            messagebox.showerror("Preview", f"{os.path.basename(fname)}:\n{e}")
            return
        self.channel["values"] = labels  # GMI and AMSR3 have different channels
        if self.channel.get() not in labels:
            self.channel.set(labels[-2])  # 89v for GMI, 36-v for AMSR3
        step = 2  # thin out for speed
        lat, lon = lat[::step, ::step], lon[::step, ::step]
        tb = tb[::step, ::step, labels.index(self.channel.get())]
        ok = np.isfinite(lat) & np.isfinite(lon) & np.isfinite(tb)

        win = tk.Toplevel(self)
        win.title(f"{os.path.basename(fname)}  -  {self.channel.get()}")
        fig = Figure(figsize=(9, 5), dpi=100)
        ax = fig.add_subplot()
        sc = ax.scatter(lon[ok], lat[ok], c=tb[ok], s=1, cmap="jet", rasterized=True)
        fig.colorbar(sc, ax=ax, label=f"Tb {self.channel.get()} (K)")
        ax.set_xlim(-180, 180)
        ax.set_ylim(-90, 90)
        ax.set_xlabel("Longitude")
        ax.set_ylabel("Latitude")
        ax.grid(True, lw=0.5, color="k", alpha=0.4)
        ax.set_title("Draw a new area, or drag/resize the box")

        def on_select(_press, _release):
            x0, x1, y0, y1 = selector.extents
            if x1 - x0 < 0.5 or y1 - y0 < 0.5:  # a click, not an area
                return
            x0, x1 = max(x0, -180), min(x1, 180)
            y0, y1 = max(y0, -90), min(y1, 90)
            for key, val in zip(("lon_min", "lon_max", "lat_min", "lat_max"), (x0, x1, y0, y1)):
                self.box[key].set(f"{val:.1f}")

        canvas = FigureCanvasTkAgg(fig, master=win)
        NavigationToolbar2Tk(canvas, win)
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        selector = RectangleSelector(ax, on_select, useblit=True, interactive=True,
                                     drag_from_anywhere=True, button=[1],
                                     props=dict(fill=False, ec="k", lw=1.5))
        try:
            b = self.read_box()
            if b["lon_min"] <= b["lon_max"]:  # boxes across 180 are not drawn
                selector.extents = (b["lon_min"], b["lon_max"], b["lat_min"], b["lat_max"])
        except ValueError:
            pass
        win._selector = selector  # keep a reference, or it stops responding
        canvas.draw()

    # ---------------------------------------------------------------- convert
    def convert(self):
        files = list(self.files.get(0, tk.END))
        if not files:
            messagebox.showinfo("Convert", "Add at least one .nc file.")
            return
        try:
            b = self.read_box()
        except ValueError as e:
            messagebox.showerror("Area", str(e))
            return
        swaths = {s for s, v in (("S1", self.s1), ("S2", self.s2)) if v.get()}
        if not swaths:
            messagebox.showerror("Swaths", "Tick at least one swath.")
            return
        out_dir = self.out_dir.get() or os.path.dirname(files[0])
        os.makedirs(out_dir, exist_ok=True)
        save_settings(output_dir=out_dir, box=b)

        self.convert_btn.state(["disabled"])

        def work():
            n = 0
            for f in files:
                self.log(f"--- {os.path.basename(f)}")
                try:
                    n += len(extract(f, out_dir=out_dir, swaths=swaths, log=self.log, **b))
                except Exception as e:  # report and continue with next file
                    self.log(f"ERROR: {e}")
            self.log(f"Done: {n} file(s) written to {out_dir}")
            self.after(0, lambda: self.convert_btn.state(["!disabled"]))

        threading.Thread(target=work, daemon=True).start()


if __name__ == "__main__":
    ConverterApp().mainloop()
