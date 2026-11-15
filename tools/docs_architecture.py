"""Draw the README architecture diagram as two theme-matched SVG files.

Run from the repository root:  python3 tools/docs_architecture.py
Writes docs/images/architecture-light.svg and docs/images/architecture-dark.svg.
"""

from html import escape
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "docs" / "images"
FONT = "-apple-system,BlinkMacSystemFont,'Segoe UI','Noto Sans',Helvetica,Arial,sans-serif"
WIDTH, HEIGHT = 1280, 540

THEMES = {
    "light": dict(box="#ffffff", line="#aac9dc", ink="#15344a", muted="#466376", accent="#e3f0fa",
                  accent_line="#3176ae", arrow="#5d7a8e", group="#8fb0c7", group_fill="#f4f9fd"),
    "dark": dict(box="#172e43", line="#547b98", ink="#f5fbff", muted="#c0d7e7", accent="#1d4363",
                 accent_line="#4fa3e0", arrow="#9fbdd2", group="#4f7594", group_fill="#10283d"),
}

# name: (x, y, width, height, title, subtitle, accent)
BOXES = {
    "browser": (30, 80, 210, 84, "Browser", "on your trusted LAN", False),
    "disks": (30, 400, 210, 84, "Disks and volumes", "SATA, chosen in the wizard", False),
    "setup": (420, 80, 320, 84, "setup", "wizard + MQTT publisher · no disk access", True),
    "snapshot": (470, 248, 220, 68, "RAM-backed snapshot", "targets and readings", False),
    "reader": (420, 400, 320, 84, "reader", "SMART + volume space · no network", True),
    "broker": (890, 80, 170, 84, "MQTT broker", "yours", False),
    "ha": (1100, 80, 160, 84, "Home Assistant", "MQTT Discovery", False),
}


def box(c, x, y, w, h, title, subtitle, accent):
    fill, stroke = (c["accent"], c["accent_line"]) if accent else (c["box"], c["line"])
    weight = 700 if accent else 600
    return (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="12" fill="{fill}" stroke="{stroke}" stroke-width="1.5"/>'
            f'<text x="{x + w / 2}" y="{y + h / 2 - 11}" text-anchor="middle" dominant-baseline="central" '
            f'fill="{c["ink"]}" font-size="18" font-weight="{weight}">{escape(title)}</text>'
            f'<text x="{x + w / 2}" y="{y + h / 2 + 14}" text-anchor="middle" dominant-baseline="central" '
            f'fill="{c["muted"]}" font-size="13.5">{escape(subtitle)}</text>')


def arrow(c, x1, y1, x2, y2, text="", side="above", label_x=None):
    parts = [f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{c["arrow"]}" stroke-width="2" marker-end="url(#head)"/>']
    if text:
        if side == "above":
            tx, ty, anchor = label_x if label_x is not None else (x1 + x2) / 2, y1 - 14, "middle"
        elif side == "left":
            tx, ty, anchor = x1 - 10, (y1 + y2) / 2, "end"
        else:
            tx, ty, anchor = x1 + 10, (y1 + y2) / 2, "start"
        parts.append(f'<text x="{tx}" y="{ty}" text-anchor="{anchor}" dominant-baseline="central" '
                     f'fill="{c["muted"]}" font-size="13.5">{escape(text)}</text>')
    return "".join(parts)


def draw(theme: str) -> str:
    c = THEMES[theme]
    p = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}" '
         f'font-family="{FONT}" role="img" aria-labelledby="title">',
         '<title id="title">The setup container serves the browser wizard and publishes to the MQTT broker; '
         'the reader container reads the selected disks without network; they share a RAM-backed snapshot.</title>',
         f'<defs><marker id="head" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" '
         f'orient="auto-start-reverse"><path d="M0 0 10 5 0 10z" fill="{c["arrow"]}"/></marker></defs>',
         f'<rect x="400" y="26" width="360" height="488" rx="18" fill="{c["group_fill"]}" stroke="{c["group"]}" '
         f'stroke-width="1.5" stroke-dasharray="7 6"/>',
         f'<text x="580" y="52" text-anchor="middle" dominant-baseline="central" fill="{c["muted"]}" '
         f'font-size="13.5" font-weight="600">One UGOS Docker project</text>']
    for spec in BOXES.values():
        p.append(box(c, *spec))
    p += [
        arrow(c, 240, 122, 416, 122, "token, settings", "above", 320),
        arrow(c, 240, 442, 416, 442, "read-only", "above", 320),
        arrow(c, 740, 122, 886, 122, "MQTT, outbound", "above", 825),
        arrow(c, 1060, 122, 1096, 122),
        arrow(c, 540, 164, 540, 244, "targets", "left"),
        arrow(c, 620, 244, 620, 168, "readings", "right"),
        arrow(c, 540, 316, 540, 396, "targets", "left"),
        arrow(c, 620, 400, 620, 320, "readings", "right"),
    ]
    p.append("</svg>")
    return "".join(p)


if __name__ == "__main__":
    for theme in THEMES:
        (OUT / f"architecture-{theme}.svg").write_text(draw(theme) + "\n", encoding="utf-8")
