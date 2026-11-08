"""Copy the Tcl and Tk script libraries to a normal folder for PyInstaller.

Tcl/Tk 9 (Python 3.14.10+ on Windows) keeps them inside the DLL ("zipfs"), which
PyInstaller does not collect, so the .exe would stop with
"Tcl data directory ... _tcl_data not found".

    python tools/extract_tcltk.py build/tcltk   ->  build/tcltk/tcl, build/tcltk/tk
"""
import os
import shutil
import sys
import tkinter

dest = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else os.path.join("build", "tcltk"))
root = tkinter.Tk()
root.withdraw()
libs = {"tcl": root.tk.eval("info library"), "tk": root.tk.globalgetvar("tk_library")}

shutil.rmtree(dest, ignore_errors=True)
os.makedirs(dest)
for name, src in libs.items():
    out = os.path.join(dest, name)
    if os.path.isdir(src):  # library on disk (older Python): plain copy
        shutil.copytree(src, out)
    else:                   # library inside the DLL: let Tcl copy it out
        root.tk.call("file", "copy", src, out.replace("\\", "/"))
    if not os.path.isfile(os.path.join(out, "init.tcl" if name == "tcl" else "tk.tcl")):
        sys.exit(f"extract_tcltk: {name} library not copied from {src}")
    print(f"{name}: {src} -> {out}")
root.destroy()
