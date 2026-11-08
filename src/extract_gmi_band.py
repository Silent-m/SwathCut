"""
Extract GPM GMI L1B or GOSAT-GW AMSR3 L1R pixels within a lat/lon box and write
them to text.

Usage:
    python extract_gmi_band.py FILE.nc [lat_min lat_max [lon_min lon_max]]

Writes one file per swath (S1 = 10-89 GHz, S2 = 166/183 GHz), because the two
swaths have separate geolocation. Longitudes are -180..180; lon_min > lon_max
selects a box crossing the 180 meridian.

Output layout follows the AMSR2 *_low_freq.txt files used with NOESYS:
three header lines (time, orbit, equator crossing), a #lat #lon #ch... line,
then "lat lon Tb..." rows.

AMSR3 L1R gives one file, *_low_freq_*.txt, with the AMSR2 low_freq channels
(6.925, 7.3, 10.65, 18.7, 23.8, 36.42 GHz V/H) all at the 6.9 GHz footprint
(FOV06). The overlap scans shared with the neighbouring granules are dropped.

AMSR3 L2 (TPW, CLW, PRC, SST, SSW, ASW, SIC, HSI, ...) gives one file with a
column per product field (e.g. #SST_6G #SST_10G #SST_Multi). Pixels flagged
NoData get -999 in that column; rows where every field is NoData are dropped.
"""
import os
import sys

import numpy as np
from netCDF4 import Dataset

GMI_LABELS = {
    9: ["10v", "10h", "18v", "18h", "23v", "36v", "36h", "89v", "89h"],
    4: ["166v", "166h", "183+-3v", "183+-7v"],
}

# AMSR3 L1R: (output label, variable name) - same columns as AMSR2 *_low_freq.txt
AMSR3_LOW_FREQ = [(f"{f}-{p.lower()}", f"Tb_FOV06Ch{c}{p}_P89o")
                  for f, c in (("6", "06"), ("7", "07"), ("10", "10"),
                               ("18", "18"), ("23", "23"), ("36", "36"))
                  for p in "VH"]

# AMSR3 L2 quality flags: 0-63 Good, 64-127 LowQuality, 128-254 NoData, 255 fill.
# LowQuality values are kept; set this to 64 to drop them as well.
L2_NODATA_FROM = 128
L2_MISSING = -999.0  # written for NoData fields


def is_amsr3(nc):
    return getattr(nc, "SensorShortName", "") == "AMSR3"


def amsr3_kind(nc):
    """'L1R', 'L2', or an error for AMSR3 files SwathCut cannot read."""
    if AMSR3_LOW_FREQ[0][1] in nc.variables:
        return "L1R"
    if "DataDatasetName" in nc.ncattrs():
        return "L2"
    raise ValueError("AMSR3: only L1R (Resampled Tb, *_S1RTBR*) and Level-2 "
                     "swath files are supported.")


def amsr3_header(nc):
    """The three header lines of the AMSR2 low_freq layout, from AMSR3 attributes."""
    return [
        f"Begin: {nc.time_coverage_start} End: {nc.time_coverage_end}",
        f"Start Orbit: {nc.OrbitNumberStart} Stop Orbit: {nc.OrbitNumberEnd}",
        f"Equatorial Cross. Lon: {float(nc.ObservationEquatorCrossingLongitude):.2f}  "
        f"Equatorial Cross. time: {nc.ObservationEquatorCrossingDateTime}",
    ]


def amsr3_l2(nc):
    """[(lat, lon, values[scan, pixel, n], labels), ...] per footprint (P89o, or P89A/P89B).

    Labels come from DataCode (e.g. SST_6G); NoData pixels are NaN.
    """
    names = [n for n in nc.DataDatasetName.split(";") if n.strip()]
    codes = [c for c in getattr(nc, "DataCode", "").split(";") if c.strip()]
    if len(codes) != len(names):
        codes = names
    groups = {}
    for name, code in zip(names, codes):
        footprint = name.strip().split("_", 1)[1]  # Data1_P89o -> P89o
        values = as_float(nc[name.strip()])
        if name.strip() + "_Quality" in nc.variables:
            q = np.ma.filled(nc[name.strip() + "_Quality"][:], 255)
            values[q >= L2_NODATA_FROM] = np.nan
        groups.setdefault(footprint, []).append((code.strip(), values))
    return [(as_float(nc["Latitude_" + fp]), as_float(nc["Longitude_" + fp]),
             np.stack([v for _, v in items], axis=-1), [c for c, _ in items])
            for fp, items in groups.items()]


def amsr3_low_freq(nc):
    """lat, lon, Tb[scan, pixel, 12] and labels from an AMSR3 L1R file, overlap scans removed."""
    n = int(getattr(nc, "NumberOfScansOverlap", 0))
    keep = slice(n, len(nc.dimensions["time"]) - n)
    lat = as_float(nc["Latitude_P89o"])[keep]
    lon = as_float(nc["Longitude_P89o"])[keep]
    tb = np.stack([as_float(nc[v])[keep] for _, v in AMSR3_LOW_FREQ], axis=-1)
    return lat, lon, tb, [lab for lab, _ in AMSR3_LOW_FREQ]


def preview_data(nc):
    """lat, lon, Tb[..., ch], labels of the first swath (GMI S1 or AMSR3 low_freq)."""
    if is_amsr3(nc):
        return amsr3_low_freq(nc) if amsr3_kind(nc) == "L1R" else amsr3_l2(nc)[0]
    g = nc["S1"]
    return as_float(g["Latitude"]), as_float(g["Longitude"]), as_float(g["Tb"]), GMI_LABELS[9]


GMI_FREQ = {"10": "10.65", "18": "18.7", "23": "23.8", "36": "36.64", "89": "89.0",
            "166": "166.0", "183+-3": "183.31+/-3", "183+-7": "183.31+/-7"}
UNITS = {"degree_Celsius": "\u00b0C", "kg/m^2": "kg/m\u00b2"}


def field_titles(nc, labels):
    """{label: (sensor + description, units)} for the preview title and colour bar."""
    if not is_amsr3(nc):
        return {lab: (f"GMI brightness temperature {GMI_FREQ[lab[:-1]]} GHz {lab[-1].upper()}", "K")
                for lab in labels if lab[:-1] in GMI_FREQ}
    if amsr3_kind(nc) == "L1R":
        names = dict(AMSR3_LOW_FREQ)
        return {lab: ("AMSR3 " + nc[names[lab]].long_name.split(" (")[0], "K") for lab in labels}
    names = [n.strip() for n in nc.DataDatasetName.split(";") if n.strip()]
    codes = [c.strip() for c in getattr(nc, "DataCode", "").split(";") if c.strip()]
    longs = [t.strip() for t in getattr(nc, "DataLongName", "").split(";") if t.strip()]
    if len(codes) != len(names):
        codes = names
    if len(longs) != len(names):
        longs = codes
    out = {}
    for name, code, long in zip(names, codes, longs):
        units = getattr(nc[name], "units", "")
        out.setdefault(code, (f"AMSR3 L2 {long}", UNITS.get(units, units)))
    return out


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
        if is_amsr3(nc):
            return extract_amsr3(nc, stem, lat_min, lat_max, lon_min, lon_max, out_dir, log)
        found = find_swaths(nc)
        if not found:
            raise ValueError("No Latitude/Longitude variables found in the file.")
        info = header_info(nc)
        gnum = info.get("GranuleNumber", "").strip()  # from the file, not the file name
        granule = str(int(gnum)) if gnum.isdigit() else "?"

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


def extract_amsr3(nc, stem, lat_min, lat_max, lon_min, lon_max, out_dir, log):
    """AMSR3 L1R -> one *_low_freq_*.txt file in the AMSR2 low_freq layout."""
    if amsr3_kind(nc) == "L2":
        return extract_amsr3_l2(nc, stem, lat_min, lat_max, lon_min, lon_max, out_dir, log)
    lat, lon, tb, labels = amsr3_low_freq(nc)
    mask = (lat >= lat_min) & (lat <= lat_max) & lon_mask(lon, lon_min, lon_max)
    mask &= np.isfinite(tb).all(axis=-1)
    if not mask.any():
        log("low_freq: no pixels in the box, skipped")
        return []
    header = "\n".join(amsr3_header(nc) + [" ".join(["#lat", "#lon"] + ["#" + s for s in labels])])
    table = np.column_stack([lat[mask], lon[mask], tb[mask]])
    out = os.path.join(out_dir or ".", f"{stem}_low_freq_{lat_min:g}_{lat_max:g}N_"
                                       f"{lon_min:g}_{lon_max:g}E.txt")
    np.savetxt(out, table, fmt="%.2f", header=header, comments="")
    log(f"low_freq: {len(table)} pixels -> {out}")
    return [out]


def extract_amsr3_l2(nc, stem, lat_min, lat_max, lon_min, lon_max, out_dir, log):
    """AMSR3 L2 -> one .txt file: lat, lon and one column per product field.

    Footprints with the same fields (PRC 89A and 89B) go into the same file.
    """
    tables = {}
    for lat, lon, values, labels in amsr3_l2(nc):
        mask = (lat >= lat_min) & (lat <= lat_max) & lon_mask(lon, lon_min, lon_max)
        mask &= np.isfinite(values).any(axis=-1)
        if mask.any():
            rows = np.column_stack([lat[mask], lon[mask], values[mask]])
            tables.setdefault(tuple(labels), []).append(rows)
    if not tables:
        log("L2: no valid pixels in the box, skipped")
        return []
    written = []
    for labels, parts in tables.items():
        table = np.nan_to_num(np.vstack(parts), nan=L2_MISSING,
                              posinf=L2_MISSING, neginf=L2_MISSING)
        name = stem if len(tables) == 1 else f"{stem}_{labels[0]}"
        out = os.path.join(out_dir or ".", f"{name}_{lat_min:g}_{lat_max:g}N_"
                                           f"{lon_min:g}_{lon_max:g}E.txt")
        header = "\n".join(amsr3_header(nc) +
                           [" ".join(["#lat", "#lon"] + ["#" + s for s in labels])])
        np.savetxt(out, table, fmt=["%.2f", "%.2f"] + ["%.3f"] * len(labels),
                   header=header, comments="")
        log(f"{nc.ProductName}: {len(table)} pixels -> {out}")
        written.append(out)
    return written


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    args = sys.argv[1:]
    extract(args[0], *(float(a) for a in args[1:5]))
