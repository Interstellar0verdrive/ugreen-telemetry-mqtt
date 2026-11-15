// Capture the real setup wizard for the documentation, in light and dark mode.
//
// 1. Start the demo server:  PYTHONPATH=src python3 tools/docs_screenshots/demo_server.py
// 2. Start Chrome headless:   chrome --headless=new --remote-debugging-port=9333 --user-data-dir=<temp dir>
// 3. Run:                     node tools/docs_screenshots/capture.mjs 9333
//
// Writes docs/images/wizard-<screen>-<theme>.webp (desktop screens) and
// docs/images/board-<screen>-<theme>.webp (desktop and phone side by side).
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const OUT = join(HERE, "..", "..", "docs", "images");
const [port = "9333", appUrl = "http://127.0.0.1:8799/"] = process.argv.slice(2);
const token = readFileSync(join(HERE, "demo", "secrets", "admin_token"), "utf8").trim();

const target = await (await fetch(`http://127.0.0.1:${port}/json/new?about:blank`, { method: "PUT" })).json();
const ws = new WebSocket(target.webSocketDebuggerUrl);
await new Promise((ok) => ws.addEventListener("open", ok, { once: true }));
let next = 0;
const pending = new Map();
ws.addEventListener("message", (event) => {
  const msg = JSON.parse(event.data);
  if (msg.id && pending.has(msg.id)) { pending.get(msg.id)(msg); pending.delete(msg.id); }
});
const send = (method, params = {}) => new Promise((ok, fail) => {
  const id = ++next;
  pending.set(id, (msg) => (msg.error ? fail(new Error(`${method}: ${msg.error.message}`)) : ok(msg.result)));
  ws.send(JSON.stringify({ id, method, params }));
});
const sleep = (ms) => new Promise((ok) => setTimeout(ok, ms));
const js = async (expression) =>
  (await send("Runtime.evaluate", { expression, awaitPromise: true, returnByValue: true })).result.value;

const DESKTOP = { width: 1200, height: 900, deviceScaleFactor: 2, mobile: false };
const BOARD_DESKTOP = { ...DESKTOP, width: 960 };
const PHONE = { width: 390, height: 844, deviceScaleFactor: 3, mobile: true };
const SCREENS = [["token", null], ["nas", "nas"], ["storage", "storage"], ["readings", "readings"]];

await send("Page.enable");
await send("Emulation.setLocaleOverride", { locale: "en-US" });
await send("Emulation.setTimezoneOverride", { timezoneId: "Europe/Rome" });

const pageBottom = `(() => { let bottom = 0, footer = false;
  for (const el of document.body.children) {
    if (el.hidden || getComputedStyle(el).display === "none" || el.tagName === "SCRIPT") continue;
    const r = el.getBoundingClientRect(); if (r.height === 0) continue;
    if (r.bottom + scrollY > bottom) { bottom = r.bottom + scrollY; footer = el.id === "footer"; }
  }
  return Math.ceil(bottom + (footer ? 0 : 40)); })()`;

async function open(theme, viewport) {
  await send("Emulation.setDeviceMetricsOverride", viewport);
  await send("Emulation.setEmulatedMedia", { features: [
    { name: "prefers-color-scheme", value: theme }, { name: "prefers-reduced-motion", value: "reduce" }] });
  await js("try { sessionStorage.clear() } catch (e) {}");
  await send("Page.navigate", { url: appUrl });
  await sleep(1200);
}

async function unlock() {
  await js(`(() => { const t = document.getElementById("token"); t.value = ${JSON.stringify(token)};
    t.dispatchEvent(new Event("input", { bubbles: true }));
    document.getElementById("login").requestSubmit(); })()`);
  await sleep(1500);
  if (await js("document.getElementById('workspace').hidden")) throw new Error("The wizard did not unlock");
}

async function desktopShot(format, viewport = DESKTOP) {
  await send("Emulation.setDeviceMetricsOverride", viewport);
  await js("document.activeElement && document.activeElement.blur(), window.scrollTo(0, 0)");
  await sleep(400);
  let height = await js(pageBottom);
  await send("Emulation.setDeviceMetricsOverride", { ...viewport, height: height + 400 });
  await sleep(300);
  height = await js(pageBottom);
  const shot = await send("Page.captureScreenshot", { format, quality: format === "webp" ? 92 : undefined,
    clip: { x: 0, y: 0, width: viewport.width, height, scale: 1 } });
  await send("Emulation.setDeviceMetricsOverride", viewport);
  return shot.data;
}

async function phoneShot(panel) {
  await js(`(() => { document.activeElement && document.activeElement.blur();
    const panel = ${JSON.stringify(panel)} && document.getElementById(${JSON.stringify(panel + "-panel")});
    window.scrollTo(0, panel ? panel.getBoundingClientRect().top + scrollY - 16 : 0); })()`);
  await sleep(500);
  return (await send("Page.captureScreenshot", { format: "png" })).data;
}

function board(theme, desktopPng, phonePng) {
  const dark = theme === "dark";
  const c = dark
    ? { bg: "linear-gradient(135deg,#0c2033,#15334d)", bar: "#1d3349", line: "#2f4c66", addr: "#10253a", text: "#c0d7e7" }
    : { bg: "linear-gradient(135deg,#dceefa,#f4f9fd)", bar: "#eef3f7", line: "#cfdde7", addr: "#ffffff", text: "#466376" };
  return `<!doctype html><meta charset="utf-8"><style>
    html,body{margin:0;background:transparent}
    .board{position:relative;box-sizing:border-box;width:1320px;padding:44px 368px 44px 44px;background:${c.bg}}
    .window{border:1px solid ${c.line};border-radius:14px;overflow:hidden;box-shadow:0 24px 60px rgba(4,24,40,${dark ? ".55" : ".18"})}
    .bar{display:flex;align-items:center;gap:8px;height:40px;padding:0 16px;background:${c.bar};border-bottom:1px solid ${c.line}}
    .dot{width:12px;height:12px;border-radius:50%}
    .addr{display:flex;align-items:center;justify-content:center;flex:1;height:24px;margin:0 72px 0 56px;border-radius:7px;
      background:${c.addr};color:${c.text};font:500 13px/1 -apple-system,"Segoe UI",sans-serif}
    .window img{display:block;width:100%}
    .phone{position:absolute;right:44px;bottom:44px;width:262px;padding:11px;border-radius:46px;background:#0a0e13;
      box-shadow:0 28px 60px rgba(4,24,40,${dark ? ".7" : ".32"}),inset 0 0 0 2px #2a3138}
    .phone img{display:block;width:100%;border-radius:36px}
  </style><div class="board" id="board"><div class="window"><div class="bar">
    <span class="dot" style="background:#ff5f57"></span><span class="dot" style="background:#febc2e"></span>
    <span class="dot" style="background:#28c840"></span><span class="addr">http://NAS-IP:8765</span></div>
    <img src="${desktopPng}" alt=""></div>
    <div class="phone"><img src="${phonePng}" alt=""></div></div>`;
}

const raw = {};
for (const theme of ["light", "dark"]) {
  await open(theme, DESKTOP);
  for (const [name, panel] of SCREENS) {
    if (name === "nas") await unlock();
    if (panel) { await js(`document.getElementById(${JSON.stringify(panel + "-tab")}).click()`); await sleep(700); }
    writeFileSync(join(OUT, `wizard-${name}-${theme}.webp`), Buffer.from(await desktopShot("webp"), "base64"));
    raw[`desktop-${name}-${theme}`] = await desktopShot("png", BOARD_DESKTOP);
  }
  await open(theme, PHONE);
  for (const [name, panel] of SCREENS) {
    if (name === "nas") await unlock();
    raw[`phone-${name}-${theme}`] = await phoneShot(panel);
  }
}

await send("Emulation.clearDeviceMetricsOverride");
await send("Emulation.setDeviceMetricsOverride", { width: 1320, height: 900, deviceScaleFactor: 2, mobile: false });
const work = join(HERE, "demo", "raw");
mkdirSync(work, { recursive: true });
for (const [key, data] of Object.entries(raw)) writeFileSync(join(work, `${key}.png`), Buffer.from(data, "base64"));
for (const theme of ["light", "dark"]) {
  for (const name of ["storage", "readings"]) {
    const page = join(work, `board-${name}-${theme}.html`);
    writeFileSync(page, board(theme, `desktop-${name}-${theme}.png`, `phone-${name}-${theme}.png`));
    await send("Page.navigate", { url: pathToFileURL(page).href });
    await sleep(1200);
    if (!(await js("[...document.images].every((img) => img.complete && img.naturalWidth > 0)")))
      throw new Error(`Board images did not load for ${name}-${theme}`);
    const rect = await js("(() => { const r = document.getElementById('board').getBoundingClientRect(); return [r.width, r.height]; })()");
    await send("Emulation.setDeviceMetricsOverride", { width: 1320, height: Math.ceil(rect[1]), deviceScaleFactor: 2, mobile: false });
    await sleep(300);
    const shot = await send("Page.captureScreenshot", { format: "webp", quality: 90,
      clip: { x: 0, y: 0, width: rect[0], height: Math.ceil(rect[1]), scale: 1 } });
    writeFileSync(join(OUT, `board-${name}-${theme}.webp`), Buffer.from(shot.data, "base64"));
  }
}
ws.close();
console.log("Screenshots written to docs/images");
