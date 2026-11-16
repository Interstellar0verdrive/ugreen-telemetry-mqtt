from __future__ import annotations

import io
import json
import shutil
import subprocess
import unittest
from pathlib import Path

from ugreen_telemetry import web

SCRIPT = Path(web.__file__).parent / "web_assets" / "update-check.js"
NODE = shutil.which("node")

# Runs chooseUpdate() from the page script in Node, without a DOM.
HARNESS = """
const vm = require('vm');
const fs = require('fs');
const context = {};
vm.createContext(context);
vm.runInContext(fs.readFileSync(process.argv[1], 'utf8') + ';this.chooseUpdate=chooseUpdate;', context);
const cases = JSON.parse(fs.readFileSync(0, 'utf8'));
const results = cases.map(([releases, installed]) => {
  const result = context.chooseUpdate(releases, installed);
  return result && {kind: result.kind, latest: result.latest.version.text, url: result.latest.url};
});
process.stdout.write(JSON.stringify(results));
"""


def release(tag, draft=False):
    return {"tag_name": tag, "draft": draft, "html_url": f"https://example.invalid/{tag}"}


@unittest.skipIf(NODE is None, "Node.js is not installed")
class ChooseUpdateTests(unittest.TestCase):
    def choose(self, *cases):
        result = subprocess.run([NODE, "-e", HARNESS, str(SCRIPT)], input=json.dumps(cases),
                                capture_output=True, text=True, check=True, timeout=30)
        return json.loads(result.stdout)

    def test_beta_install_is_offered_the_next_beta(self):
        releases = [release("v0.3.0b1"), release("v0.3.0b3"), release("v0.3.0b2")]
        available, current = self.choose([releases, "v0.3.0b2"], [releases, "v0.3.0b3"])
        self.assertEqual(available, {"kind": "available", "latest": "0.3.0b3",
                                     "url": "https://example.invalid/v0.3.0b3"})
        self.assertEqual(current["kind"], "current")

    def test_stable_install_ignores_betas(self):
        only_beta_newer, stable_newer = self.choose(
            [[release("v0.4.0b1"), release("v0.3.0")], "v0.3.0"],
            [[release("v0.4.0b1"), release("v0.3.1")], "v0.3.0"])
        self.assertEqual((only_beta_newer["kind"], only_beta_newer["latest"]), ("current", "0.3.0"))
        self.assertEqual((stable_newer["kind"], stable_newer["latest"]), ("available", "0.3.1"))

    def test_python_version_order(self):
        final_after_beta, rc_after_beta, numeric, alpha = self.choose(
            [[release("v0.3.0")], "v0.3.0b2"],
            [[release("v0.3.0rc1"), release("v0.3.0b9")], "v0.3.0b9"],
            [[release("v0.10.0b1"), release("v0.9.0b1")], "v0.9.0b1"],
            [[release("v0.3.0a1")], "v0.3.0b1"])
        self.assertEqual((final_after_beta["kind"], final_after_beta["latest"]), ("available", "0.3.0"))
        self.assertEqual(rc_after_beta["latest"], "0.3.0rc1")
        self.assertEqual(numeric["latest"], "0.10.0b1")
        self.assertEqual((alpha["kind"], alpha["latest"]), ("current", "0.3.0a1"))

    def test_drafts_and_unknown_tags_are_ignored(self):
        result, nothing = self.choose(
            [[release("v9.9.9", draft=True), release("v0.3.0.dev2"), release("latest"), release("v0.3.0b2")], "v0.3.0b1"],
            [[release("v0.3.0.dev2")], "v0.3.0b1"])
        self.assertEqual(result["latest"], "0.3.0b2")
        self.assertIsNone(nothing)

    def test_unreadable_installed_version_still_names_the_latest_release(self):
        development, preview = self.choose([[release("v0.3.0b2")], "vdevelopment"],
                                           [[release("v0.3.0b2")], "Local preview"])
        self.assertEqual((development["kind"], development["latest"]), ("unknown", "0.3.0b2"))
        self.assertEqual(preview["kind"], "unknown")


class SetupPageTests(unittest.TestCase):
    def response(self, path):
        handler = object.__new__(web.Handler)
        handler.path = path
        handler.headers = {}
        handler.wfile = io.BytesIO()
        sent = {}
        handler.send_response = lambda code: sent.setdefault("code", code)
        handler.send_header = lambda name, value: sent.setdefault(name, value)
        handler.end_headers = lambda: None
        handler.do_GET()
        return sent, handler.wfile.getvalue()

    def test_page_may_contact_only_itself_and_the_github_api(self):
        headers, _body = self.response("/")
        policy = dict(part.strip().split(" ", 1) for part in headers["Content-Security-Policy"].split(";"))
        self.assertEqual(policy["connect-src"], "'self' https://api.github.com")
        self.assertEqual(policy["script-src"], "'self'")

    def test_update_script_is_served_and_loaded(self):
        headers, body = self.response("/update-check.js?v=1")
        self.assertEqual(headers["code"], 200)
        self.assertIn(b"'Interstellar0verdrive/ugreen-telemetry-mqtt'", body)
        self.assertIn(b"https://api.github.com/repos/${UPDATE_REPOSITORY}/releases", body)
        _headers, page = self.response("/")
        self.assertIn(b'src="update-check.js', page)
        self.assertIn(b'id="update-check"', page)

    def test_icons_are_small_and_served_with_their_type(self):
        _headers, page = self.response("/")
        for name, kind in (("app-icon-light.webp", "image/webp"), ("app-icon-dark.webp", "image/webp"),
                           ("favicon-light.png", "image/png"), ("favicon-dark.png", "image/png")):
            with self.subTest(name=name):
                headers, body = self.response("/" + name)
                self.assertEqual((headers["code"], headers["Content-Type"]), (200, kind))
                self.assertLess(len(body), 32 * 1024)
                self.assertIn(name.encode(), page)


if __name__ == "__main__":
    unittest.main()
