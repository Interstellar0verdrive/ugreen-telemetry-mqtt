"""Build the theme-matched README preview from the wizard's actual labels.

This is a UI mockup, not a screenshot or a claim about a particular NAS's data.
The selected/off states and intervals mirror the tested DXP4800 Pro pilot.
"""

from html import escape
from pathlib import Path


OUT = Path(__file__).resolve().parents[1] / "docs" / "images"

THEMES = {
    "light": dict(page="#f6f8fa", surface="#ffffff", ink="#293c49", muted="#627886",
                  line="#d3dfe6", brand="#3176ae", soft="#edf5fb", input="#ffffff",
                  off="#ffffff", on_brand="#ffffff", shadow="#233c4b"),
    "dark": dict(page="#151f29", surface="#1e2d39", ink="#e8f0f4", muted="#b5c7d0",
                 line="#597381", brand="#2e75aa", soft="#203d52", input="#192631",
                 off="#1e2d39", on_brand="#ffffff", shadow="#07111b"),
}

ROWS = [
    (("CPU usage", "Current processor load", "1", True),
     ("Memory usage", "Current RAM usage", "1", True)),
    (("CPU temperature", "Processor temperature, when exposed", "15", True),
     ("HDD temperatures", "Selected SATA hard drives", "15", True)),
    (("SSD and NVMe temperatures", "Detected solid-state storage", "15", False),
     ("Uptime", "Time since the NAS started", "15", True)),
    (("Volume space", "Used and available space on selected volumes", "15", True),
     ("HDD SMART diagnostics", "Optional health counters", "15", False)),
]


def rect(x, y, w, h, r, fill, stroke="none", extra=""):
    return (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" '
            f'fill="{fill}" stroke="{stroke}" {extra}/>')


def label(x, y, value, size, fill, weight=400, extra=""):
    return (f'<text x="{x}" y="{y}" fill="{fill}" font-size="{size}" '
            f'font-weight="{weight}" {extra}>{escape(value)}</text>')


def reading(x, y, title, sub, minutes, enabled, c):
    out = []
    fill = c["soft"] if enabled else c["off"]
    out.append(rect(x, y, 474, 76, 10, fill, c["line"]))
    out.append(rect(x + 16, y + 28, 20, 20, 4,
                    c["brand"] if enabled else c["off"],
                    c["brand"] if enabled else c["line"]))
    if enabled:
        out.append(f'<path d="M{x+21} {y+37} l5 5 9 -10" fill="none" '
                   f'stroke="{c["on_brand"]}" stroke-width="2.5" '
                   'stroke-linecap="round" stroke-linejoin="round"/>')
    fg = c["ink"] if enabled else c["muted"]
    out.append(label(x + 49, y + 32, title, 16, fg, 600))
    out.append(label(x + 49, y + 54, sub, 12.5, c["muted"]))
    out.append(rect(x + 388, y + 20, 51, 36, 7, c["input"], c["line"]))
    out.append(label(x + 413.5, y + 44, minutes, 15, fg, 700, 'text-anchor="middle"'))
    out.append(label(x + 445, y + 44, "min", 12, c["muted"]))
    return "\n".join(out)


def build(theme, c):
    p = []
    p.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="730" '
             f'viewBox="0 0 1200 730" role="img" font-family="Arial, Helvetica, sans-serif" '
             f'aria-label="UGREEN Telemetry, Readings to publish UI preview, {theme} theme">')
    p.append('<defs><filter id="shadow" x="-20%" y="-20%" width="140%" height="150%">'
             '<feGaussianBlur stdDeviation="17"/></filter></defs>')
    p.append(rect(0, 0, 1200, 730, 0, c["page"]))
    p.append(rect(82, 71, 1036, 610, 23, c["shadow"], extra='opacity=".15" filter="url(#shadow)"'))
    p.append(rect(70, 54, 1060, 640, 22, c["surface"], c["line"]))
    p.append(label(100, 99, "UGREEN Telemetry", 29, c["ink"], 700))
    p.append(label(100, 124, "Configure which NAS readings to publish to your MQTT broker.", 15, c["muted"]))
    p.append(rect(100, 146, 1000, 54, 12, c["surface"], c["line"]))
    p.append(rect(766, 152, 326, 42, 9, c["brand"]))
    for x, t, active in [(267, "NAS and MQTT", False),
                         (600, "Disks and volumes", False),
                         (933, "Readings to publish", True)]:
        p.append(label(x, 179, t, 15, c["on_brand"] if active else c["muted"],
                       700, 'text-anchor="middle"'))
    p.append(label(100, 246, "Readings to publish", 24, c["ink"], 700))
    p.append(label(100, 272, "Choose what to publish. For each reading, enter the number of minutes between updates.", 14, c["muted"]))
    p.append(label(100, 292, "Disk readings have a minimum interval to avoid frequent checks.", 14, c["muted"]))
    for row, pair in enumerate(ROWS):
        for col, item in enumerate(pair):
            p.append(reading(100 + 507 * col, 321 + 83 * row, *item, c))
    p.append('</svg>')
    (OUT / f"readme-preview-{theme}.svg").write_text("\n".join(p) + "\n", encoding="utf-8")


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    for theme, palette in THEMES.items():
        build(theme, palette)
