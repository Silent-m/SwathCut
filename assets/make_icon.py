"""SwathCut icon: a curved satellite swath in Tb colours with a white cut-out box."""
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
import matplotlib
matplotlib.use("Agg")
from matplotlib import colormaps

S = 1024  # supersampled canvas

def render(simple=False):
    yy, xx = np.mgrid[0:S, 0:S].astype(float)
    # swath centreline: a gentle S-curve, like an orbit track on a map
    t = xx / S
    yc = S * (0.52 - 0.20 * np.sin(2 * np.pi * (t - 0.08)))
    slope = S * (-0.20 * 2 * np.pi / S * np.cos(2 * np.pi * (t - 0.08)))
    d = (yy - yc) / np.sqrt(1 + slope ** 2)          # perpendicular distance
    half = S * (0.17 if simple else 0.15)
    band = np.clip((half - np.abs(d)) / 6, 0, 1)      # antialiased edge

    # brightness-temperature-like colouring: varies along and across track
    v = 0.5 + 0.30 * np.sin(2 * np.pi * (t * 1.3 + 0.1)) + 0.10 * (d / half)
    if not simple:
        v += 0.05 * np.sin(xx / 37) * np.cos(yy / 53)
    rgb = colormaps["turbo"](np.clip(v, 0.22, 0.82))[..., :3] ** 0.8  # brighter

    # cut-out box
    bx0, bx1, by0, by1 = 0.36 * S, 0.66 * S, 0.27 * S, 0.67 * S
    inside = (xx >= bx0) & (xx <= bx1) & (yy >= by0) & (yy <= by1)
    dim = np.where(inside, 1.0, 0.78)                 # swath outside the box is dimmed

    bg_top, bg_bot = np.array([0.07, 0.12, 0.24]), np.array([0.02, 0.05, 0.12])
    bg = bg_top + (bg_bot - bg_top) * (yy / S)[..., None]
    img = bg * (1 - band[..., None]) + rgb * dim[..., None] * band[..., None]

    im = Image.fromarray((img * 255).astype(np.uint8)).convert("RGBA")
    if not simple:  # faint lat/lon grid, blended
        grid = Image.new("RGBA", (S, S), (0, 0, 0, 0))
        gd = ImageDraw.Draw(grid)
        for g in (0.25, 0.5, 0.75):
            gd.line([(g * S, 0), (g * S, S)], fill=(255, 255, 255, 40), width=5)
            gd.line([(0, g * S), (S, g * S)], fill=(255, 255, 255, 40), width=5)
        im.alpha_composite(grid)
    dr = ImageDraw.Draw(im)
    lw = int(S * (0.05 if simple else 0.032))
    dr.rectangle([bx0, by0, bx1, by1], outline=(255, 255, 255, 255), width=lw)
    if not simple:  # corner grips of the selection box
        g = int(S * 0.055)
        for cx, cy in ((bx0, by0), (bx1, by0), (bx0, by1), (bx1, by1)):
            dr.rectangle([cx - g / 2, cy - g / 2, cx + g / 2, cy + g / 2], fill=(255, 255, 255, 255))

    # rounded-square mask
    mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, S - 1, S - 1], radius=int(S * 0.2), fill=255)
    im.putalpha(mask)
    return im

big, small = render(False), render(True)
sizes = [256, 128, 64, 48, 32, 24, 16]
frames = [(big if s >= 48 else small).resize((s, s), Image.LANCZOS) for s in sizes]
frames[0].save("swathcut.ico", sizes=[(s, s) for s in sizes], append_images=frames[1:])
big.resize((512, 512), Image.LANCZOS).save("swathcut.png")

# preview sheet: all sizes on light and dark backgrounds
sheet = Image.new("RGBA", (760, 560), (240, 240, 240, 255))
dark = Image.new("RGBA", (760, 280), (32, 32, 32, 255)); sheet.paste(dark, (0, 280))
x = 10
for f in frames:
    s = f.size[0]
    for y0 in (0, 280):
        sheet.alpha_composite(f, (x, y0 + (280 - s) // 2))
    x += s + 14
sheet.save("preview_sizes.png")
