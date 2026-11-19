# Changelog

## 0.5.1 — 2026-11-19
- Preview: mouse-wheel zoom around the cursor.

## 0.5.0 — 2026-11-19
- Preview lists every channel of the file: AMSR3 L1B 89/165/183 GHz,
  GMI 166/183 GHz; PRC shows both 89 GHz scans.
- AMSR3 L1R: pixels flagged with geometry, Tb, count drop-off or failed
  resampling errors are dropped (as for L1B).
- Clear messages for unsupported or unusual files and for an output folder
  that cannot be created.
- AMSR3 files convert with no GMI swath ticked; Convert is always re-enabled.

## 0.4.0 — 2026-11-09
- AMSR3 L1B: low_freq, 89, 165 and 183 GHz files.
- Resizable window; Clear log button.

## 0.3.1 — 2026-11-08
- GMI orbit number read from the file header, not the file name.
- Infinite values in L2 output written as -999.
- Thread-safe log.

## 0.3.0 — 2026-11-08
- AMSR3 Level-2 swath products (TPW, CLW, PRC, SST, SSW, ASW, …).
- Preview titles and colour-bar units describe the field shown.

## 0.2.0 — 2026-11-08
- AMSR3 L1R in the AMSR2 low_freq layout.
- Lat/lon area remembered between runs.
- Build works with Python 3.14.10 / Tcl-Tk 9.

## 0.1.0 — 2026-11-07
- First release: GPM GMI L1B area extraction, preview map with area
  selection, remembered folders, Help menu, icon.
