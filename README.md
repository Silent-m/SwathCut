<img src="assets/swathcut.png" width="96" align="right" alt="SwathCut icon">

# SwathCut

Cut a latitude/longitude area out of **GPM GMI Level-1B** swath files (`.nc`)
and save the brightness temperatures as plain text.

## Download

Get `SwathCut.exe` from the [Releases](../../releases) page and run it.
No Python or other installation is needed (Windows 10/11, 64-bit).

## Use

1. **Add...** one or more GMI L1B files (`1B.GPM.GMI…` / `GPMCOR_GMI_…_1BS_…nc`).
2. Set the area: type Lat/Lon limits, or press **Preview / select area** and
   draw, drag or resize the box on the swath map.
   Longitudes are −180…180; *Lon min > Lon max* selects a box across the 180° meridian.
3. Tick the swaths: **S1** (10–89 GHz) and/or **S2** (166–183 GHz).
4. Choose the output folder and press **Convert**.

One text file is written per input file and swath. Granules that do not cross
the area are skipped. Input and output folders are remembered between runs.

## Screenshots

<img src="docs/main_window.png" width="430" alt="SwathCut main window">
<img src="docs/preview.png" width="560" alt="Preview map: GMI 89 GHz swath with the selection box">

## Output format

```
Begin: 2026-03-18T17:15:00.039Z End: 2026-03-18T17:22:33.783Z
Start Orbit: 68387 Stop Orbit: 68387
Equatorial Cross. Lon: 179.82  Equatorial Cross. time: 2026-03-18T17:00:43.793Z
#lat #lon #10v #10h #18v #18h #23v #36v #36h #89v #89h
50.02 -159.22 163.71 90.32 178.79 106.65 189.58 206.47 143.33 237.57 189.63
...
```

Latitude, longitude (degrees) and brightness temperatures (K), one pixel per row;
pixels with missing data are dropped. S2 files have the columns
`#166v #166h #183+-3v #183+-7v`.

## Run from source

Python 3.10 or newer:

```
pip install -r requirements.txt
python src/swathcut.py
```

Command line, without the window:

```
python src/extract_gmi_band.py FILE.nc lat_min lat_max [lon_min lon_max]
```

## Build the .exe

```
pip install -r requirements.txt pyinstaller
build_exe.bat
```

The result is `dist\SwathCut.exe`.

## License

MIT © 2026 Lev Mitnik. GMI data: NASA / JAXA Global Precipitation Measurement mission.
