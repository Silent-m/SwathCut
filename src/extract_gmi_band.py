"""
Extract GPM GMI L1B pixels within a lat/lon box and write them to text.

Usage:
    python extract_gmi_band.py FILE.nc [lat_min lat_max [lon_min lon_max]]

Writes one file per swath (S1 = 10-89 GHz, S2 = 166/183 GHz), because the two
swaths have separate geolocation. Longitudes are -180..180; lon_min > lon_max
selects a box crossing the 180 meridian.

Output layout follows the AMSR2 *_low_freq.txt files used with NOESYS:
three header lines (time, orbit, equator crossing), a #lat #lon #ch... line,
then "lat lon Tb..." rows.
"""
import os
import sys

import numpy as np
from netCDF4 import Dataset

GMI_LABELS = {
    9: ["10v", "10h", "18v", "18h", "23v", "36v", "36h", "89v", "89h"],
    4: ["166v", "166h", "183+-3v", "183+-7v"],
}


def find_swaths(grp, path=""):
    """Return (path, group) for every group holding Latitude/Longitude."""
    found = []
    if "Latitude" in grp.variables and "Longitude" in grp.variables:
        found.append((path or "root", grp))
    for name, sub in grp.groups.items():
        found += find_swaths(sub, f"{path}/{name}")
    return found


def as_float(var):
    return np.ma.filled(np.ma.asarray(var[:], dtype=float), np.nan)


def header_info(nc):
    """Parse 'key=value;' records of the GPM global attributes."""
    info = {}
    for att in ("FileHeader", "NavigationRecord"):
        if att in nc.ncattrs():
            for item in nc.getncattr(att).split(";"):
                if "=" in item:
                    k, v = item.strip().split("=", 1)
                    info[k] = v
    return info


def scan_times(g):
    """ISO time string per scan, or None if ScanTime is absent."""
    if "ScanTime" not in g.groups:
        return None
    t = g["ScanTime"]
    parts = [np.ma.filled(t[k][:], -1).astype(int)
             for k in ("Year", "Month", "DayOfMonth", "Hour", "Minute", "Second", "MilliSecond")]
    return [f"{y:04d}-{mo:02d}-{d:02d}T{h:02d}:{mi:02d}:{s:02d}.{ms:03d}Z"
            for y, mo, d, h, mi, s, ms in zip(*parts)]


def lon_mask(lon, lon_min, lon_max):
    if lon_min <= lon_max:
        return (lon >= lon_min) & (lon <= lon_max)
    return (lon >= lon_min) | (lon <= lon_max)  # box across 180


def extract(fname, lat_min=50.0, lat_max=65.0, lon_min=-180.0, lon_max=180.0,
            out_dir=None, swaths=None, log=print):
    """Write one text file per swath; return the list of written paths.

    swaths: iterable of swath names to keep (e.g. {"S1"}); None = all.
    """
    stem = os.path.splitext(os.path.basename(fname))[0]
    out_dir = out_dir or "."
    written = []
    with Dataset(fname) as nc:
        found = find_swaths(nc)
        if not found:
            raise ValueError("No Latitude/Longitude variables found in the file.")
        info = header_info(nc)
        granule = str(int(stem.split("_")[4])) if stem.count("_") >= 4 else "?"

        for gpath, g in found:
            tag = gpath.strip("/").replace("/", "_")
            if swaths is not None and tag not in swaths:
                continue
            lat, lon = as_float(g["Latitude"]), as_float(g["Longitude"])
            mask = (lat >= lat_min) & (lat <= lat_max) & lon_mask(lon, lon_min, lon_max)

            tbname = next((n for n in ("Tb", "Tc") if n in g.variables), None)
            if tbname is None:
                log(f"{tag}: no Tb/Tc variable, skipped")
                continue
            tb = as_float(g[tbname])
            if tb.ndim == 2:
                tb = tb[..., None]
            mask &= np.isfinite(tb).all(axis=-1)
            if not mask.any():
                log(f"{tag}: no pixels in the box, skipped")
                continue
            nch = tb.shape[-1]
            labels = GMI_LABELS.get(nch, [f"ch{i + 1}" for i in range(nch)])

            iscan, _ = np.nonzero(mask)
            times = scan_times(g)
            t0, t1 = (times[iscan.min()], times[iscan.max()]) if times else ("?", "?")
            eq_lon = info.get("LongitudeOnEquator", "nan")
            header = "\n".join([
                f"Begin: {t0} End: {t1}",
                f"Start Orbit: {granule} Stop Orbit: {granule}",
                f"Equatorial Cross. Lon: {float(eq_lon):.2f}  "
                f"Equatorial Cross. time: {info.get('UTCDateTimeOnEquator', '?')}",
                " ".join(["#lat", "#lon"] + ["#" + s for s in labels]),
            ])
            table = np.column_stack([lat[mask], lon[mask], tb[mask]])

            out = os.path.join(out_dir, f"{stem}_{tag}_{lat_min:g}_{lat_max:g}N_"
                                        f"{lon_min:g}_{lon_max:g}E.txt")
            np.savetxt(out, table, fmt="%.2f", header=header, comments="")
            log(f"{tag}: {len(table)} pixels -> {out}")
            written.append(out)
    return written


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    args = sys.argv[1:]
    extract(args[0], *(float(a) for a in args[1:5]))
