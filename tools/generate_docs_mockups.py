"""Build theme-matched UI mockups from the wizard's actual labels.

This is a UI mockup, not a screenshot or a claim about a particular NAS's data.
The selected/off states and intervals mirror the tested DXP4800 Pro.
"""

from html import escape
from pathlib import Path


OUT = Path(__file__).resolve().parents[1] / "docs" / "images"

THEMES = {
    "light": dict(page="#dceefa", surface="#ffffff", ink="#15344a", muted="#466376",
                  line="#aac9dc", brand="#1678c6", soft="#deeffb", input="#ffffff",
                  off="#f7fbff", on_brand="#ffffff", shadow="#124a70", panel="#f7fbff"),
    "dark": dict(page="#0c2033", surface="#172e43", ink="#f5fbff", muted="#c0d7e7",
                 line="#547b98", brand="#258dcf", soft="#224b69", input="#10253a",
                 off="#1a3248", on_brand="#ffffff", shadow="#020a12", panel="#10283d"),
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
    out.append(rect(x + 378, y + 20, 51, 36, 7, c["input"], c["line"]))
    out.append(label(x + 403.5, y + 44, minutes, 15, fg, 700, 'text-anchor="middle"'))
    out.append(label(x + 435, y + 44, "min", 12, c["muted"]))
    return "\n".join(out)


def start(theme, c, height, window_height):
    p = []
    p.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="{height}" '
             f'viewBox="0 0 1200 {height}" role="img" font-family="Arial, Helvetica, sans-serif" '
             f'aria-label="UGREEN Telemetry UI mockup, {theme} theme">')
    p.append('<defs><filter id="shadow" x="-20%" y="-20%" width="140%" height="150%">'
             '<feGaussianBlur stdDeviation="17"/></filter>'
             f'<linearGradient id="back" x2="1" y2="1"><stop stop-color="{c["page"]}"/>'
             f'<stop offset="1" stop-color="{c["panel"]}"/></linearGradient></defs>')
    p.append(rect(0, 0, 1200, height, 0, 'url(#back)'))
    p.append(rect(82, 71, 1036, window_height - 30, 23, c["shadow"], extra='opacity=".25" filter="url(#shadow)"'))
    p.append(rect(70, 54, 1060, window_height, 22, c["surface"], c["line"]))
    # Keep the accent fully inside the rounded frame, clear of its curved corners.
    p.append(rect(100, 65, 1000, 5, 2.5, c["brand"]))
    p.append(label(100, 99, "UGREEN Telemetry", 29, c["ink"], 700))
    p.append(label(100, 124, "Configure which NAS readings to publish to your MQTT broker.", 15, c["muted"]))
    return p


def tabs(p, c, active):
    p.append(rect(100, 146, 1000, 54, 12, c["surface"], c["line"]))
    p.append(rect(108 + 330 * active, 152, 324, 42, 9, c["brand"]))
    for i, (x, t) in enumerate([(267, "NAS and MQTT"),
                                 (600, "Disks and volumes"),
                                 (933, "Readings to publish")]):
        p.append(label(x, 179, t, 15, c["on_brand"] if i == active else c["muted"],
                       700, 'text-anchor="middle"'))


def build_readings(theme, c):
    p = start(theme, c, 730, 640)
    tabs(p, c, 2)
    p.append(label(100, 246, "Readings to publish", 24, c["ink"], 700))
    p.append(label(100, 272, "Choose what to publish. For each reading, enter the number of minutes between updates.", 14, c["muted"]))
    p.append(label(100, 292, "Disk readings have a minimum interval to avoid frequent checks.", 14, c["muted"]))
    for row, pair in enumerate(ROWS):
        for col, item in enumerate(pair):
            p.append(reading(100 + 507 * col, 321 + 83 * row, *item, c))
    p.append('</svg>')
    (OUT / f"readme-preview-{theme}.svg").write_text("\n".join(p) + "\n", encoding="utf-8")


def choice(x, y, width, title, sub, c):
    p = [rect(x, y, width, 70, 10, c["soft"], c["line"]),
         rect(x + 16, y + 25, 20, 20, 4, c["brand"], c["brand"]),
         f'<path d="M{x+21} {y+34} l5 5 9 -10" fill="none" stroke="{c["on_brand"]}" '
         'stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>',
         label(x + 49, y + 31, title, 17, c["ink"], 700),
         label(x + 49, y + 53, sub, 13, c["muted"])]
    return "\n".join(p)


def build_storage(theme, c):
    p = start(theme, c, 800, 700)
    tabs(p, c, 1)
    p.append(label(100, 246, "Disks and volumes", 24, c["ink"], 700))
    p.append(label(100, 273, "Choose only the storage you want to monitor. No serial numbers are displayed.", 15, c["muted"]))
    p.append(label(100, 319, "Detected SATA disks", 18, c["ink"], 700))
    p.append(label(1098, 319, "4 selected", 14, c["brand"], 700, 'text-anchor="end"'))
    for i, name in enumerate(("sda", "sdb", "sdc", "sdd")):
        p.append(choice(100 + 507 * (i % 2), 339 + 82 * (i // 2), 474,
                        f"HDD {name}", f"/dev/{name} · SATA hard drive", c))
    p.append(label(100, 543, "Mounted data volumes", 18, c["ink"], 700))
    p.append(choice(100, 561, 981, "Volume data", "/volume1", c))
    p.append(f'<line x1="100" y1="657" x2="1081" y2="657" stroke="{c["line"]}"/>')
    p.append(label(100, 686, "Compare these disks with UGOS Storage before saving.", 14, c["ink"], 700))
    p.append(label(100, 709, "A sleeping HDD is skipped; its previous temperature is not presented as a fresh reading.", 13.5, c["muted"]))
    p.append('</svg>')
    (OUT / f"storage-preview-{theme}.svg").write_text("\n".join(p) + "\n", encoding="utf-8")


def build_token(theme, c):
    p = start(theme, c, 600, 500)
    p.append(label(100, 205, "Unlock setup", 24, c["ink"], 700))
    p.append(label(100, 233, "Enter the setup token to access this NAS's telemetry settings.", 15, c["muted"]))
    p.append(rect(100, 267, 481, 188, 10, c["soft"], c["line"]))
    instructions = (("1.", "Open UGOS Docker and select the telemetry project."),
                    ("2.", "Open the setup container, then its Logs tab."),
                    ("3.", "On the Setup token line, copy only the"))
    for i, (num, item) in enumerate(instructions):
        y = 305 + i * 48
        p.append(label(121, y, num, 15, c["brand"], 700))
        p.append(label(148, y, item, 15, c["ink"], 500))
    p.append(label(148, 423, "43-character code after the colon, without spaces.", 15, c["ink"], 500))
    p.append(label(620, 291, "Setup token", 15, c["ink"], 700))
    p.append(rect(620, 306, 469, 52, 9, c["input"], c["line"]))
    p.append(label(637, 339, "Enter setup token", 16, c["muted"]))
    p.append(f'<path d="M1057 333 q13 -15 26 0 q-13 15 -26 0 M1061 321 l23 24" '
             f'fill="none" stroke="{c["muted"]}" stroke-width="2" stroke-linecap="round"/>')
    p.append(label(620, 382, "The token is shown only in the setup container's log. Keep it private.", 13, c["muted"]))
    p.append(rect(955, 406, 134, 46, 9, c["brand"]))
    p.append(label(1022, 435, "Continue", 15, c["on_brand"], 700, 'text-anchor="middle"'))
    p.append(f'<line x1="100" y1="480" x2="1090" y2="480" stroke="{c["line"]}"/>')
    p.append(label(100, 507, "This setup page uses local HTTP. Enter a token or broker password only on a trusted local network.", 13, c["muted"]))
    p.append('</svg>')
    (OUT / f"token-preview-{theme}.svg").write_text("\n".join(p) + "\n", encoding="utf-8")


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    for theme, palette in THEMES.items():
        build_readings(theme, palette)
        build_storage(theme, palette)
        build_token(theme, palette)
