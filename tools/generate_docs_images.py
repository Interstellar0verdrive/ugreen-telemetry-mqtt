"""Generate privacy-safe README and guide figures from fictional sample data.

Run with the bundled Pillow-capable Python or any Python with Pillow installed.
No NAS credentials, live data, or screenshots are used.
"""

from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter, ImageFont


OUT = Path(__file__).resolve().parents[1] / "docs" / "images"
OUT.mkdir(parents=True, exist_ok=True)
AVENIR = Path("/System/Library/Fonts/Avenir Next.ttc")
DEJAVU = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
DEJAVU_BOLD = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")
S = 2

C = {
    "page": "#f6f8fa",
    "surface": "#ffffff",
    "ink": "#293c49",
    "muted": "#627886",
    "line": "#d3dfe6",
    "brand": "#3176ae",
    "brand_deep": "#286ba5",
    "brand_soft": "#edf5fb",
    "success": "#368263",
    "success_soft": "#e6f3eb",
    "navy": "#122a42",
    "cyan": "#54d6ed",
    "green": "#5fe1ae",
}


class Canvas:
    def __init__(self, width, height, bg="page"):
        self.w, self.h = width, height
        self.im = Image.new("RGB", (width * S, height * S), C.get(bg, bg))
        self.d = ImageDraw.Draw(self.im)

    def font(self, size, weight="regular"):
        if AVENIR.exists():
            index = {"bold": 0, "demi": 2, "medium": 5, "regular": 7}[weight]
            return ImageFont.truetype(str(AVENIR), round(size * S), index=index)
        fallback = DEJAVU_BOLD if weight in {"bold", "demi"} else DEJAVU
        if fallback.exists():
            return ImageFont.truetype(str(fallback), round(size * S))
        return ImageFont.load_default(size=round(size * S))

    def rect(self, xy, fill, radius=0, outline=None, width=1):
        box = tuple(round(v * S) for v in xy)
        self.d.rounded_rectangle(
            box,
            radius=round(radius * S),
            fill=C.get(fill, fill),
            outline=C.get(outline, outline) if outline else None,
            width=round(width * S),
        )

    def circle(self, x, y, r, fill, outline=None, width=1):
        self.d.ellipse(
            ((x-r)*S, (y-r)*S, (x+r)*S, (y+r)*S),
            fill=C.get(fill, fill),
            outline=C.get(outline, outline) if outline else None,
            width=round(width*S),
        )

    def line(self, points, fill, width=2, joint="curve"):
        self.d.line([(round(x*S), round(y*S)) for x, y in points], fill=C.get(fill, fill), width=round(width*S), joint=joint)

    def text(self, x, y, value, size=18, color="ink", weight="regular", anchor="lt"):
        self.d.text((round(x*S), round(y*S)), value, font=self.font(size, weight), fill=C.get(color, color), anchor=anchor)

    def centered(self, x, y, value, size=18, color="ink", weight="regular"):
        self.text(x, y, value, size, color, weight, anchor="mt")

    def shadow(self, xy, radius=18, blur=20, alpha=28):
        layer = Image.new("RGBA", self.im.size, (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        d.rounded_rectangle(tuple(round(v*S) for v in xy), radius=radius*S, fill=(20, 42, 62, alpha))
        layer = layer.filter(ImageFilter.GaussianBlur(blur*S))
        self.im = Image.alpha_composite(self.im.convert("RGBA"), layer).convert("RGB")
        self.d = ImageDraw.Draw(self.im)

    def save(self, name):
        self.im.save(OUT / name, optimize=True)


def arrow(c, x1, y, x2, color="brand", width=3):
    c.line([(x1, y), (x2, y)], color, width)
    c.line([(x2-11, y-8), (x2, y), (x2-11, y+8)], color, width)


def pill(c, x, y, w, label, bg="success_soft", fg="success"):
    c.rect((x, y, x+w, y+30), bg, 15)
    c.centered(x+w/2, y+5, label, 14, fg, "demi")


def check(c, x, y, active=True):
    c.rect((x, y, x+22, y+22), "brand" if active else "surface", 5, None if active else "line", 1.5)
    if active:
        c.line([(x+5, y+11), (x+10, y+16), (x+18, y+6)], "surface", 2.6)


def hero():
    c = Canvas(1440, 360, "navy")
    # Restrained glow and signal lines, distinct from a cloud-service symbol.
    for r, color in [(260, "#173d62"), (205, "#1c4a70"), (145, "#205778")]:
        c.circle(1190, 195, r, color)
    for y in (65, 104, 264, 301):
        c.line([(755, y), (930, y), (970, y-15), (1100, y-15)], "#2a5b7a", 2)
    c.text(82, 67, "NAS readings", 24, "#b7d9ec", "demi")
    c.text(82, 113, "Connected through MQTT.", 46, "surface", "bold")
    c.text(82, 177, "A quiet bridge from local storage to the tools you choose.", 21, "#c6d9e6")
    c.rect((82, 255, 403, 304), "#234f71", 14, "#4d7590")
    c.centered(242, 266, "UGREEN Telemetry MQTT", 19, "surface", "demi")
    c.line([(680, 198), (760, 198), (788, 198), (815, 160), (848, 244), (882, 179), (920, 198), (1042, 198)], "cyan", 9)
    c.line([(920, 198), (1064, 198), (1094, 171), (1188, 171)], "green", 4)
    for x, y, r, color in [(680,198,8,"cyan"),(1042,198,8,"cyan"),(1188,171,14,"green")]:
        c.circle(x,y,r,color)
    c.save("hero-flow.png")


def architecture():
    c = Canvas(1440, 600)
    c.text(60, 38, "How the browser pilot is separated", 30, "ink", "bold")
    c.text(60, 88, "One UGOS Docker project · two services using the same image", 19, "muted")
    c.shadow((50,145,972,508),16,16,19)
    c.rect((50,145,972,508),"surface",16,"line")
    c.text(76,164,"UGOS Docker project",20,"brand_deep","demi")
    c.rect((78,218,424,410),"brand_soft",16,"#b8d2e4")
    c.text(106,244,"Reader",25,"ink","bold")
    c.text(106,286,"SMART + selected volumes",18,"ink")
    c.text(106,321,"No network access",17,"muted")
    pill(c,106,360,182,"Disk access only","#dcecf6","brand_deep")
    c.rect((592,218,944,410),"brand_soft",16,"#b8d2e4")
    c.text(620,244,"Setup + publisher",25,"ink","bold")
    c.text(620,286,"Web wizard + MQTT",18,"ink")
    c.text(620,321,"No direct disk access",17,"muted")
    pill(c,620,360,220,"Network + MQTT login","#dcecf6","brand_deep")
    arrow(c,438,314,578,"brand")
    c.centered(508,259,"RAM snapshot",15,"muted","demi")
    c.rect((78,438,944,486),"#f5f8fa",12,"line")
    c.centered(510,449,"Persistent settings and password stay in named NAS volumes",17,"muted","medium")
    arrow(c,970,315,1047,"brand")
    c.rect((1062,240,1386,389),"#e6f3eb",16,"#b7d9c7")
    c.text(1090,265,"MQTT broker",24,"ink","bold")
    c.text(1090,308,"Home Assistant or any",18,"ink")
    c.text(1090,339,"other MQTT consumer",18,"ink")
    c.text(60,538,"Illustrative architecture · the host-installer path has a different layout",16,"muted")
    c.save("architecture.png")


def shell(title, subtitle, active, height=670):
    c=Canvas(1200,height)
    c.rect((42,32,1158,height-31),"surface",18,"line")
    c.rect((62,52,1138,109),"#f9fbfc",12)
    c.text(84,65,"UGREEN Telemetry",25,"brand_deep","bold")
    pill(c,964,64,150,"Illustrative preview","#e6f3eb","success")
    c.rect((73,125,1127,183),"#f5f8fa",12,"line")
    tabs=["NAS and MQTT","Disks and volumes","Readings to publish"]
    for i,label in enumerate(tabs):
        x=82+i*347
        if i==active: c.rect((x,134,x+338,174),"brand",9)
        c.centered(x+169,144,label,17,"surface" if i==active else "muted","demi")
    c.text(84,212,title,28,"ink","bold")
    c.text(84,254,subtitle,17,"muted")
    return c


def field(c,x,y,w,label,value,masked=False,dim=False):
    c.text(x,y,label,16,"ink","demi")
    c.rect((x,y+30,x+w,y+80),"#f9fbfc" if dim else "surface",9,"line")
    c.text(x+14,y+43,"••••••••••••" if masked else value,17,"muted" if dim else "ink")
    if masked:
        c.circle(x+w-27,y+55,10,"surface","muted",2)
        c.line([(x+w-39,y+68),(x+w-15,y+42)],"muted",2)


def screen_token():
    c=Canvas(1120,560)
    c.rect((54,45,1066,515),"surface",18,"line")
    c.text(94,78,"UGREEN Telemetry",32,"ink","bold")
    c.text(94,128,"Enter the setup token",23,"brand_deep","demi")
    c.text(94,176,"Find the Setup token line in the setup container log.",17,"muted")
    c.text(94,205,"Copy only the 43-character code after the colon, without spaces.",17,"muted")
    field(c,94,260,932,"Setup token","",True)
    c.text(94,385,"The code stays on this NAS and is not sent to MQTT.",16,"muted")
    c.rect((822,417,1026,475),"brand",10)
    c.centered(924,431,"Continue",19,"surface","demi")
    c.text(94,481,"Illustrative screen · no real token shown",15,"muted")
    c.save("wizard-token.png")


def screen_nas():
    c=shell("NAS and MQTT","Identify the NAS and connect it to your existing MQTT broker.",0,740)
    field(c,84,305,496,"NAS display name","UGREEN NAS")
    field(c,620,305,496,"Stable NAS ID","myugreennas")
    field(c,84,414,496,"MQTT broker IP or host","mqtt.example.local")
    field(c,620,414,496,"MQTT port","1883")
    field(c,84,523,496,"Dedicated MQTT username","telemetry_user")
    field(c,620,523,496,"MQTT password  ·  stored on NAS","",True)
    c.text(84,659,"Illustrative screen with fictional values · no credentials shown",15,"muted")
    c.save("wizard-nas-mqtt.png")


def disk_card(c,x,y,name,detail):
    c.rect((x,y,x+496,y+75),"brand_soft",10,"#b8d2e4")
    check(c,x+19,y+26)
    c.text(x+57,y+13,name,19,"ink","demi")
    c.text(x+57,y+42,detail,15,"muted")


def screen_disks():
    c=shell("Disks and volumes","Choose only the storage you want to monitor. No serial numbers are displayed.",1,780)
    c.text(84,307,"Detected SATA disks",20,"ink","demi")
    pill(c,978,304,138,"4 selected")
    for i,(name,detail) in enumerate([
        ("HDD sda","/dev/sda · SATA hard drive"),("HDD sdb","/dev/sdb · SATA hard drive"),
        ("HDD sdc","/dev/sdc · SATA hard drive"),("HDD sdd","/dev/sdd · SATA hard drive")]):
        disk_card(c,84+(i%2)*536,348+(i//2)*88,name,detail)
    c.text(84,550,"Mounted data volumes",20,"ink","demi")
    c.rect((84,591,1116,663),"brand_soft",10,"#b8d2e4")
    check(c,104,615)
    c.text(143,601,"Volume data",19,"ink","demi")
    c.text(143,630,"/volume1",15,"muted")
    c.text(84,706,"Compare Linux disk names with UGOS Storage before saving.",16,"muted")
    c.save("wizard-disks-volumes.png")


def reading_card(c,x,y,label,detail,minutes,enabled=True):
    c.rect((x,y,x+496,y+73),"brand_soft" if enabled else "surface",9,"#b8d2e4" if enabled else "line")
    check(c,x+17,y+25,enabled)
    c.text(x+53,y+12,label,17,"ink" if enabled else "muted","demi")
    c.text(x+53,y+40,detail,14,"muted")
    c.rect((x+405,y+18,x+456,y+55),"surface",7,"line")
    c.centered(x+430,y+25,str(minutes),16,"ink" if enabled else "muted","demi")
    c.text(x+461,y+27,"min",14,"muted")


def screen_readings():
    c=shell("Readings to publish","Choose each reading and its update interval.",2,800)
    rows=[
        ("CPU usage","Current processor load",1,True),
        ("Memory usage","Current RAM usage",1,True),
        ("CPU temperature","Processor temperature",15,True),
        ("HDD temperatures","Selected SATA hard drives",15,True),
        ("Volume space","Used and available space",15,True),
        ("Uptime","Time since NAS start",15,True),
        ("SSD/NVMe temperatures","When exposed by the NAS",15,True),
        ("HDD SMART diagnostics","Optional health counters",15,False),
    ]
    for i,(label,detail,minutes,enabled) in enumerate(rows):
        reading_card(c,84+(i%2)*536,311+(i//2)*85,label,detail,minutes,enabled)
    c.text(84,721,"A sleeping HDD is skipped until a fresh reading is available.",16,"muted")
    c.save("wizard-readings.png")


def installer_map():
    c=Canvas(1200,440)
    c.text(56,38,"Match the installer's candidates to UGOS Storage",29,"ink","bold")
    c.text(56,83,"Example paths only: confirm the device type on your own NAS.",18,"muted")
    c.rect((58,145,532,373),"surface",15,"line")
    c.text(84,169,"UGOS Storage",23,"brand_deep","demi")
    c.text(84,225,"SATA hard drive",19,"ink")
    c.text(84,285,"USB disk",19,"ink")
    c.text(84,345,"Data volume",19,"ink")
    for y in (236,296,356): arrow(c,548,y,644,"brand")
    c.rect((660,145,1142,373),"surface",15,"line")
    c.text(686,169,"Installer candidate",23,"brand_deep","demi")
    c.text(686,225,"/dev/sda  ·  select after checking",19,"ink")
    c.text(686,285,"/dev/sdc  ·  leave unselected",19,"muted")
    c.text(686,345,"/volume1  ·  select if intended",19,"ink")
    c.save("installer-selection.png")


def upgrade_flow():
    c=Canvas(1200,440)
    c.text(54,38,"Private image upgrade and rollback test",29,"ink","bold")
    c.text(54,83,"Observed on the DXP4800 Pro pilot · not yet a public update flow",18,"muted")
    tags=[("GHCR dev1",58),("GHCR dev2",354),("GHCR dev1",650),("Local image",946)]
    for label,x in tags:
        c.rect((x,155,x+194,235),"brand_soft",12,"#b8d2e4")
        c.centered(x+97,181,label,20,"brand_deep","demi")
    for x in (268,564,860): arrow(c,x,195,x+68,"brand")
    c.rect((58,292,1140,373),"#e6f3eb",14,"#b7d9c7")
    c.centered(600,308,"Persistent configuration volumes + stable NAS ID",21,"success","demi")
    c.centered(600,341,"Retained across every image switch in this test",16,"muted")
    c.save("upgrade-flow.png")


def migration_flow():
    c=Canvas(1200,420)
    c.text(54,37,"Cut over one publisher at a time",29,"ink","bold")
    c.text(54,83,"Draft procedure · verify the same MQTT device before removing the old installation",18,"muted")
    steps=[("1  Stop old publisher",58),("2  Start pilot",452),("3  Verify identity",846)]
    for label,x in steps:
        c.rect((x,159,x+288,249),"surface",13,"line")
        c.centered(x+144,188,label,19,"ink","demi")
    arrow(c,362,205,433)
    arrow(c,756,205,827)
    c.rect((58,291,1134,365),"brand_soft",12,"#b8d2e4")
    c.centered(596,307,"If verification fails: stop the pilot, then restore the old publisher and timer",18,"brand_deep","demi")
    c.save("migration-cutover.png")


if __name__ == "__main__":
    for fn in (hero, architecture, screen_token, screen_nas, screen_disks, screen_readings, installer_map, upgrade_flow, migration_flow):
        fn()
    print(f"Generated 9 figures in {OUT}")
