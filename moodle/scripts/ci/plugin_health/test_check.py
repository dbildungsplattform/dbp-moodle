"""Unit tests for check.py. Run: python -m unittest discover -s moodle/scripts/ci/plugin_health"""
import io
import json
import os
import shutil
import sys
import types
import unittest
import zipfile
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import check  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "../../../.."))
INSTALL = os.path.join(REPO, "moodle/scripts/install")


def make_checker(config=None, **argv):
    import tempfile
    args = types.SimpleNamespace(repo_root=REPO, work_dir=tempfile.mkdtemp(prefix="ph-work-"), offline=False,
                                 cve_dir=None, live_pluglist=False, no_bash_crosscheck=True, download_delay=0,
                                 moodle_version=None)
    for k, v in argv.items():
        setattr(args, k, v)
    return check.Checker(args, config or {"thresholds": {}})


def zip_bytes(files):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, content in files.items():
            zf.writestr(name, content)
    return buf.getvalue()


GPL_HEADER = """<?php
// This file is part of Moodle - https://moodle.org/
//
// Moodle is free software: you can redistribute it and/or modify
// it under the terms of the GNU General Public License as published by
// the Free Software Foundation, either version 3 of the License, or
// (at your option) any later version.
"""


class ParseBashArrays(unittest.TestCase):
    def test_multiline_comments_and_refs(self):
        text = """
deps=(
    local_a # dependency of x
    tool_b
)
main=(
    # mod_custom   custom download logic
    mod_c
    mod_d   # trailing comment
)
all=("${deps[@]}" "${main[@]}")
"""
        arrays, commented = check.parse_bash_arrays(text)
        self.assertEqual(arrays["deps"], ["local_a", "tool_b"])
        self.assertEqual(arrays["main"], ["mod_c", "mod_d"])
        self.assertEqual(arrays["all"], ["local_a", "tool_b", "mod_c", "mod_d"])
        self.assertEqual(commented["main"][0][0], "mod_custom")

    def test_append_form(self):
        arrays, _ = check.parse_bash_arrays("a=(x)\na+=(y z)\n")
        self.assertEqual(arrays["a"], ["x", "y", "z"])

    def test_circular_reference_is_an_error(self):
        with self.assertRaises(ValueError):
            check.parse_bash_arrays('a=("${b[@]}")\nb=("${a[@]}")\n')

    def test_real_file_matches_bash(self):
        path = os.path.join(INSTALL, "pluginList.sh")
        if not os.path.exists(path) or not shutil.which("bash"):
            self.skipTest("pluginList.sh oder bash fehlt")
        arrays, _ = check.parse_bash_arrays(check.read_text(path))
        seen = check.bash_crosscheck(path, list(arrays))
        self.assertIsNotNone(seen)
        for name, items in arrays.items():
            self.assertEqual(seen[name], items, name)


class ParseDownloadScript(unittest.TestCase):
    SAMPLE = """
download_x() {
    target_tag="v1.2.3"
    git clone https://github.com/o/moodle-mod_x.git x
}
download_y() {
    target_branch="main" # comment
    git clone https://github.com/o/y.git
}
unused() {
    git clone https://github.com/o/never.git
}
download_github_release() {
    plugin_name=$1
    repo=$2
    tag=$3
    curl -sSfL --retry 5 \\
        "https://github.com/${repo}/archive/refs/tags/${tag}.zip" -o "${plugin_name}.zip"
}
download_z() {
    download_github_release format_z o/moodle-format_z V405.1.5
}
download_m() {
    curl -sSfL "https://marketplace.moodle.com/api/plugins/theme_m/versions/2026080600/download" -o m.zip
}
download_x
download_y
download_z
download_m
moosh plugin-download -v 3.7 customfield_old
"""

    def test_sources(self):
        sources, legacy, uncalled = check.parse_download_script(self.SAMPLE)
        kinds = {(s.kind, s.component, s.ref) for s in sources}
        self.assertIn(("git-tag", None, "v1.2.3"), kinds)
        self.assertIn(("git-branch", None, "main"), kinds)
        self.assertIn(("github-archive", "format_z", "V405.1.5"), kinds)
        self.assertIn(("marketplace-pin", "theme_m", "2026080600"), kinds)
        self.assertNotIn("never", " ".join(s.repo_url or "" for s in sources))
        self.assertEqual(legacy, {"customfield_old": "3.7"})
        self.assertIn("unused", uncalled)

    def test_real_file(self):
        path = os.path.join(INSTALL, "downloadPlugins.sh")
        if not os.path.exists(path):
            self.skipTest("downloadPlugins.sh fehlt")
        sources, legacy, _ = check.parse_download_script(check.read_text(path))
        self.assertGreaterEqual(len(sources), 1)
        for s in sources:
            self.assertTrue(s.repo_url or s.download_url, s)
            self.assertNotIn("$", (s.ref or "") + (s.repo_url or ""), s)


class VersionSelection(unittest.TestCase):
    PLUGIN = {"versions": [
        {"version": "2024010100", "supportedmoodles": [{"release": "4.5"}]},
        {"version": "2025010100", "supportedmoodles": [{"release": "4.5"}, {"release": "5.0"}]},
        {"version": "2026010100", "supportedmoodles": [{"release": "5.0"}]},
    ]}

    def test_picks_newest_supporting(self):
        self.assertEqual(check.select_directory_version(self.PLUGIN, "4.5")["version"], "2025010100")

    def test_none_when_unsupported(self):
        self.assertIsNone(check.select_directory_version(self.PLUGIN, "3.9"))


class Helpers(unittest.TestCase):
    def test_tag_family(self):
        fam = check.tag_family("V405.1.5")
        self.assertTrue(fam.match("V405.1.6"))
        self.assertFalse(fam.match("V502.2.1"))
        fam = check.tag_family("v9.7.10-stable")
        self.assertTrue(fam.match("v9.7.11-stable"))
        self.assertFalse(fam.match("v10.0.1-stable"))
        self.assertGreater(check.version_tuple("v9.7.11"), check.version_tuple("v9.7.10"))

    def test_license(self):
        self.assertEqual(check.classify_license(GPL_HEADER), "GPL-3.0-or-later")
        self.assertIsNone(check.classify_license("<?php\n$plugin->version = 1;"))
        self.assertEqual(check.classify_license("// GNU General Public License version 3 only"), "GPL-3.0")

    def test_normalized_matching(self):
        self.assertIn(check.norm_text("pdfannotator"), check.norm_text("Moodle PDF Annotator plugin v1.5"))

    def test_repo_url_normalization(self):
        self.assertEqual(check.normalize_repo_url("https://github.com/o/r/tree/MOODLE_500%2B_rc"),
                         "https://github.com/o/r")
        self.assertEqual(check.normalize_repo_url("https://bitbucket.org/dw8/moodle-format_tiles/"),
                         "https://bitbucket.org/dw8/moodle-format_tiles")


class ArtifactChecks(unittest.TestCase):
    CONFIG = {
        "thresholds": {"future_version_tolerance_days": 31},
        "library_map": [{"match": "pdf\\.js", "ecosystem": "npm", "package": "pdfjs-dist"}],
    }

    def tree(self, component="mod_demo", version="2099010100", lib=True):
        files = {
            "demo/version.php": GPL_HEADER + f"$plugin->component = '{component}';\n$plugin->version = {version};\n"
                                             "$plugin->release = '1.0';\n",
            "demo/vendor/other/version.php": "<?php $plugin->component = 'mod_other';",
        }
        if lib:
            files["demo/thirdpartylibs.xml"] = ("<libraries><library><location>js/pdf.js</location><name>pdf.js</name>"
                                                "<version>2.14.34</version><license>Apache</license></library>"
                                                "<library><name>Mystery</name><version>1.0</version></library></libraries>")
        return check.ZipTree(zip_bytes(files))

    def run_artifact(self, tree, component="mod_demo"):
        c = make_checker(self.CONFIG)
        res = check.PluginResult(component, check.Source("directory", component))
        c.fetch_tree = lambda r: tree
        c.check_artifact(res)
        c.results.append(res)
        return c, res

    def test_findings(self):
        _, res = self.run_artifact(self.tree())
        msgs = {(f.severity, f.check) for f in res.findings}
        self.assertIn(("WARN", "version"), msgs)                      # future-dated version
        self.assertEqual(res.metrics["license"], "GPL-3.0-or-later")
        self.assertEqual(len(res.metrics["libraries"]), 2)

    def test_component_mismatch(self):
        _, res = self.run_artifact(self.tree(component="mod_evil"))
        self.assertTrue(any(f.severity == "FAIL" and f.check == "artifact" for f in res.findings))

    def test_osv_hit_is_fail_until_reviewed(self):
        c, res = self.run_artifact(self.tree())
        orig = check.http_get
        check.http_get = lambda *a, **k: json.dumps({"results": [{"vulns": [{"id": "GHSA-test"}]}]}).encode()
        try:
            c.check_osv()
        finally:
            check.http_get = orig
        self.assertTrue(any(f.severity == "FAIL" and "GHSA-test" in f.message for f in res.findings))
        self.assertTrue(any(f.severity == "UNCHECKED" and "Mystery" in f.message for f in res.findings))

    def test_osv_failure_is_unchecked_not_ok(self):
        c, res = self.run_artifact(self.tree())

        def boom(*a, **k):
            raise OSError("network down")
        orig = check.http_get
        check.http_get = boom
        try:
            c.check_osv()
        finally:
            check.http_get = orig
        lib = [f for f in res.findings if f.check == "libraries" and "pdf.js" in f.message]
        self.assertTrue(lib and all(f.severity == "UNCHECKED" for f in lib))


class DetectedLibraries(unittest.TestCase):
    """Libraries the plugin bundles without (correctly) declaring them in thirdpartylibs.xml."""
    CONFIG = {"thresholds": {}, "library_map": [
        {"match": "^jquery ui\\b", "ecosystem": "npm", "package": "jquery-ui"},
        {"match": "^jquery$", "ecosystem": "npm", "package": "jquery"}]}

    def run_osv(self, files, vulnerable=()):
        files = {"demo/version.php": GPL_HEADER + "$plugin->component = 'mod_demo';\n$plugin->version = 2024010100;\n",
                 **files}
        c = make_checker(self.CONFIG)
        res = check.PluginResult("mod_demo", check.Source("directory", "mod_demo"))
        c.fetch_tree = lambda r: check.ZipTree(zip_bytes(files))
        c.check_artifact(res)
        c.results.append(res)
        asked = []

        def fake_osv(url, headers=None, data=None, **k):
            queries = json.loads(data)["queries"]
            asked.extend((q["package"]["name"], q["version"]) for q in queries)
            return json.dumps({"results": [{"vulns": [{"id": "GHSA-test"}]} if q["package"]["name"] in vulnerable
                                           else {} for q in queries]}).encode()
        with patch.object(check, "http_get", fake_osv):
            c.check_osv()
        return res, asked

    def test_banner_finds_undeclared_library_once_per_version(self):
        res, asked = self.run_osv({
            "demo/lib/ui/jquery.ui.core.js": "/*!\n * jQuery UI 1.8.11\n */\n",
            "demo/lib/ui/jquery.ui.accordion.js": "/*\n * jQuery UI Accordion 1.8.11\n */\n",
            "demo/tests/fixtures/jquery.js": "/*! jQuery v1.0.0 */",          # not shipped code
            "demo/amd/src/own.js": "// plain plugin code\n"}, vulnerable=("jquery-ui",))
        self.assertEqual(asked, [("jquery-ui", "1.8.11")])
        hit = [f for f in res.findings if f.check == "vulnerability"]
        self.assertEqual(len(hit), 1)
        self.assertIn("jQuery UI 1.8.11 (npm:jquery-ui, nicht in thirdpartylibs.xml deklariert", hit[0].message)

    def test_declared_version_differing_from_the_file_is_warned_and_both_are_checked(self):
        xml = ("<libraries><library><location>lib/jquery</location><name>jquery</name>"
               "<version>1.4.3</version></library></libraries>")
        res, asked = self.run_osv({"demo/thirdpartylibs.xml": xml,
                                   "demo/lib/jquery/jquery-1.4.3.js": "/*!\n * jQuery JavaScript Library v1.5.2\n */"})
        self.assertEqual(asked, [("jquery", "1.4.3"), ("jquery", "1.5.2")])
        self.assertTrue(any(f.severity == "WARN" and "jquery 1.5.2 in lib/jquery/jquery-1.4.3.js (deklariert: 1.4.3)"
                            in f.message for f in res.findings))

    def test_matching_declaration_is_one_query_without_warning(self):
        xml = ("<libraries><library><location>lib/jquery</location><name>jquery</name>"
               "<version>3.5</version></library></libraries>")
        res, asked = self.run_osv({"demo/thirdpartylibs.xml": xml, "demo/lib/jquery/jquery.js": "/*! jQuery v3.5.0 */"})
        self.assertEqual(asked, [("jquery", "3.5")])
        self.assertFalse(any(f.severity == "WARN" for f in res.findings))

    def test_unknown_banner_is_unchecked_not_ok(self):
        res, asked = self.run_osv({"demo/amd/src/rating.js": "/**\n * Mystery Rating Plugin v1.2.2\n */"})
        self.assertEqual(asked, [])
        self.assertTrue(any(f.severity == "UNCHECKED" and "Mystery Rating Plugin 1.2.2 (amd/src/rating.js)" in f.message
                            for f in res.findings))

    def test_nested_npm_build_uses_locked_runtime_dependencies(self):
        res, asked = self.run_osv({
            "demo/editor/package.json": json.dumps({"dependencies": {"left-pad": "^1.0.0", "unlocked": "^2.0.0"},
                                                    "devDependencies": {"webpack": "5.0.0"}}),
            "demo/editor/package-lock.json": json.dumps({"packages": {"node_modules/left-pad": {"version": "1.3.0"}}}),
            "demo/editor/build/editor.js": "!function(){}()",
            # build tooling of the plugin itself, nothing of it is shipped
            "demo/package.json": json.dumps({"dependencies": {"gulp": "4.0.2"}}),
            "demo/dist/x.js": ""}, vulnerable=("left-pad",))
        self.assertEqual(asked, [("left-pad", "1.3.0")])
        self.assertTrue(any(f.severity == "FAIL" and "editor/package-lock.json" in f.message for f in res.findings))
        self.assertTrue(any(f.severity == "UNCHECKED" and "unlocked (Version unbekannt)" in f.message
                            for f in res.findings))

    def test_composer_installed_packages_without_dev(self):
        installed = {"packages": [{"name": "phpoffice/phpword", "version": "v1.1.0"},
                                  {"name": "phpunit/phpunit", "version": "9.0.0"}],
                     "dev-package-names": ["phpunit/phpunit"]}
        res, asked = self.run_osv({"demo/vendor/composer/installed.json": json.dumps(installed)})
        self.assertEqual(asked, [("phpoffice/phpword", "1.1.0")])


class Vulnerabilities(unittest.TestCase):
    def run_ignore(self, entries, version):
        c = make_checker({"ignored_findings": entries})
        r = check.PluginResult("mod_x", check.Source("directory", "mod_x"), version=version)
        c.vulnerability(r, "CVE-1 (2026-01-01): t")
        c.results = [r]
        c.apply_ignores()
        return c, r.findings[0]

    FIXED = {"component": "mod_x", "check": "vulnerability", "match": "CVE-1", "reason": "fixed",
             "fixed_version": "2026010100", "note": "n"}

    def test_unreviewed_is_fail_by_default(self):
        self.assertEqual(self.run_ignore([], "2026020100")[1].severity, "FAIL")

    def test_fixed_version(self):
        c, old = self.run_ignore([self.FIXED], "2025010100")
        self.assertEqual(old.severity, "FAIL")
        self.assertIn("behoben erst ab 2026010100, ausgeliefert 2025010100", old.message)
        self.assertFalse(any(f.check == "ignore" for f in c.global_findings))     # entry counts as used
        self.assertEqual(self.run_ignore([self.FIXED], "2026020100")[1].severity, "INFO")
        self.assertEqual(self.run_ignore([self.FIXED], None)[1].severity, "FAIL")  # unknown version: no pass

    def test_fixed_uses_artifact_version(self):
        # Both source types prefill the version from metadata. Keep that value above the fix
        # threshold while varying the ZIP between an older vulnerable and a matching fixed build.
        for kind in ("directory", "marketplace-pin"):
            for version, severity in (("2025010100", "FAIL"), ("2026020100", "INFO")):
                with self.subTest(kind=kind, version=version):
                    c = make_checker({"ignored_findings": [self.FIXED]})
                    res = check.PluginResult("mod_x", check.Source(kind, "mod_x"), version="2026020100")
                    tree = check.ZipTree(zip_bytes({"x/version.php": GPL_HEADER +
                        f"$plugin->component = 'mod_x';\n$plugin->version = {version};\n"}))
                    with patch.object(c, "fetch_tree", return_value=tree):
                        c.check_artifact(res)
                    c.vulnerability(res, "CVE-1")
                    c.results = [res]
                    c.apply_ignores()
                    self.assertEqual(res.version, version)
                    self.assertEqual(res.findings[-1].severity, severity)
                    mismatch = [finding for finding in res.findings if finding.check == "artifact"]
                    if version == "2025010100":
                        self.assertTrue(mismatch)
                        self.assertEqual(mismatch[0].severity, "FAIL")
                        self.assertIn("2025010100", mismatch[0].message)
                        self.assertIn("2026020100", mismatch[0].message)
                    else:
                        self.assertFalse(mismatch)

    def test_unreadable_artifact_version_cannot_use_fixed_ignore(self):
        # The arithmetic case starts with a seemingly fixed version but evaluates below the
        # threshold; a parser that accepts only the numeric prefix would incorrectly ignore it.
        for declaration in ("", "$plugin->version = $unknown;", "$plugin->version = 2026020100 - 10000;"):
            with self.subTest(declaration=declaration):
                c = make_checker({"ignored_findings": [self.FIXED]})
                res = check.PluginResult("mod_x", check.Source("directory", "mod_x"), version="2026020100")
                tree = check.ZipTree(zip_bytes({"x/version.php": GPL_HEADER +
                    "$plugin->component = 'mod_x';\n" + declaration}))
                with patch.object(c, "fetch_tree", return_value=tree):
                    c.check_artifact(res)
                c.vulnerability(res, "CVE-1")
                c.results = [res]
                c.apply_ignores()
                self.assertIsNone(res.version)
                self.assertTrue(any(finding.check == "artifact" and finding.severity == "FAIL"
                                    for finding in res.findings))
                self.assertEqual(res.findings[-1].severity, "FAIL")

    def test_download_failure_cannot_use_fixed_ignore(self):
        c = make_checker({"ignored_findings": [self.FIXED]})
        res = check.PluginResult("mod_x", check.Source("directory", "mod_x"), version="2026020100")
        with patch.object(c, "fetch_tree", side_effect=OSError("network down")):
            with self.assertRaises(OSError):
                c.check_artifact(res)
        # run() continues with repository/CVE checks after artifact errors, so a vulnerability
        # can still arrive later and must not be waived using the prefilled metadata version.
        c.vulnerability(res, "CVE-1")
        c.results = [res]
        c.apply_ignores()
        self.assertIsNone(res.version)
        self.assertEqual(res.findings[-1].severity, "FAIL")

    def test_fixed_requires_version_and_only_fixed_takes_one(self):
        for bad in ({**self.FIXED, "fixed_version": "v1.2"}, {k: v for k, v in self.FIXED.items() if k != "fixed_version"},
                    {**self.FIXED, "reason": "risk_accepted"}):
            c, f = self.run_ignore([bad], "2026020100")
            self.assertEqual(f.severity, "FAIL")
            self.assertTrue(any(x.severity == "FAIL" and x.check == "ignore" for x in c.global_findings))

    def test_match_list_ignores_when_any_text_matches(self):
        entry = {"component": "mod_x", "check": "vulnerability", "reason": "false_positive", "note": "n"}
        _, f = self.run_ignore([{**entry, "match": ["CVE-9", "CVE-1"]}], "2026020100")
        self.assertEqual(f.severity, "INFO")
        _, f = self.run_ignore([{**entry, "match": ["CVE-9", "CVE-8"]}], "2026020100")
        self.assertEqual(f.severity, "FAIL")
        c, _ = self.run_ignore([{**entry, "match": []}], "2026020100")
        self.assertTrue(any(x.severity == "FAIL" and x.check == "ignore" for x in c.global_findings))

    def test_entry_for_other_component_does_not_apply(self):
        _, f = self.run_ignore([{"component": "mod_a", "check": "vulnerability", "match": "CVE-1",
                                 "reason": "false_positive", "note": "n"}], "2026020100")
        self.assertEqual(f.severity, "FAIL")

    def test_unused_vulnerability_entry_is_silent_when_cves_were_not_checked(self):
        entry = {"component": "mod_x", "check": "vulnerability", "match": "CVE-9", "reason": "false_positive", "note": "n"}
        c, _ = self.run_ignore([entry], "1")
        self.assertTrue(any(f.check == "ignore" for f in c.global_findings))
        c = make_checker({"ignored_findings": [entry]})
        c.unchecked["cve"] = "kein --cve-dir angegeben"
        c.apply_ignores()
        self.assertFalse(c.global_findings)


class RepoChecks(unittest.TestCase):
    """check_repo against a real local git repository (no network)."""

    @classmethod
    def setUpClass(cls):
        import subprocess
        import tempfile
        cls.tmp = tempfile.mkdtemp(prefix="ph-test-")
        cls.repo = os.path.join(cls.tmp, "upstream")
        os.makedirs(cls.repo)
        env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t",
               "GIT_COMMITTER_EMAIL": "t@t"}

        def g(*args, date=None):
            e = dict(env)
            if date:
                e["GIT_AUTHOR_DATE"] = e["GIT_COMMITTER_DATE"] = date
            subprocess.run(["git", *args], cwd=cls.repo, env=e, check=True, capture_output=True)
        g("init", "-q", "-b", "main")
        for i, (date, tag) in enumerate([("2020-01-01T00:00:00", "v1.0.0"), ("2020-02-01T00:00:00", "v1.0.1"),
                                         ("2020-03-01T00:00:00", "v2.0.0")]):
            with open(os.path.join(cls.repo, "f.txt"), "w") as fh:
                fh.write(str(i))
            g("add", "f.txt")
            g("commit", "-q", "-m", f"c{i}", date=date)
            g("tag", tag, date=date)
        cls.url = "file://" + cls.repo

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def run_repo(self, kind, ref, cfg=None):
        c = make_checker(cfg or {"thresholds": {}}, offline=True, work_dir=os.path.join(self.tmp, "work-" + kind + str(ref)))
        os.makedirs(os.path.join(c.work, "repos"), exist_ok=True)
        res = check.PluginResult("mod_x", check.Source(kind, None, self.url, ref), repo_url=self.url)
        c.check_repo(res)
        return res

    def has(self, res, sev, check_name, text=""):
        return any(f.severity == sev and f.check == check_name and text in f.message for f in res.findings)

    def test_stale_repo_fails(self):
        self.assertTrue(self.has(self.run_repo("git-tag", "v2.0.0"), "FAIL", "maintenance"))

    def test_newer_tag_in_same_line(self):
        res = self.run_repo("git-tag", "v1.0.0")
        self.assertTrue(self.has(res, "WARN", "pin", "v1.0.1"))
        self.assertFalse(self.has(res, "WARN", "pin", "v2.0.0"))

    def test_missing_tag_fails(self):
        self.assertTrue(self.has(self.run_repo("github-archive", "v9.9.9"), "FAIL", "pin"))

    def test_branch_pin_warns(self):
        self.assertTrue(self.has(self.run_repo("git-branch", "main"), "WARN", "pin", "Branch"))

    def test_non_github_repo_is_unchecked(self):
        self.assertTrue(self.has(self.run_repo("git-tag", "v2.0.0"), "UNCHECKED", "github"))

    def test_github_meta_offline_and_without_token_is_not_ok(self):
        c = make_checker({}, offline=True)
        self.assertNotEqual(c.github_meta("https://github.com/o/r").get("status"), "ok")
        c = make_checker({}, offline=False)
        c.token = None
        self.assertNotEqual(c.github_meta("https://github.com/o/r").get("status"), "ok")


class DownloadIntegrity(unittest.TestCase):
    def test_download_errors_are_classified_and_control_exit_code(self):
        url = "https://example.invalid/mod_x.zip"
        cases = [(check.urllib.error.HTTPError(url, status, "download error", {}, None), severity, exit_code)
                 for status, severity, exit_code in ((404, "FAIL", 1), (410, "FAIL", 1),
                                                     (401, "UNCHECKED", 0), (403, "UNCHECKED", 0),
                                                     (429, "UNCHECKED", 0), (500, "UNCHECKED", 0),
                                                     (503, "UNCHECKED", 0))]
        cases += [(check.urllib.error.URLError("network down"), "UNCHECKED", 0),
                  (TimeoutError("timed out"), "UNCHECKED", 0)]
        directory = {"timestamp": int(check.TODAY.timestamp()), "plugins": [{"component": "mod_x", "versions": [
            {"version": "2026010100", "downloadurl": url, "supportedmoodles": [{"release": "4.5"}]}]}]}
        for error, severity, exit_code in cases:
            with self.subTest(error=str(error)):
                c = make_checker({}, moodle_version="4.5.14")
                self.addCleanup(shutil.rmtree, c.work)
                with patch.object(check, "Checker", return_value=c), \
                        patch.object(check, "read_text", return_value=""), \
                        patch.object(check, "read_json", side_effect=[{}, directory]), \
                        patch.object(check, "parse_bash_arrays", return_value=({"moodle_plugin_list": ["mod_x"]}, {})), \
                        patch.object(check, "parse_download_script", return_value=([], {}, [])), \
                        patch.object(check, "http_get", side_effect=error), \
                        patch.dict(os.environ, {"GITHUB_STEP_SUMMARY": ""}), \
                        patch("sys.stdout", new_callable=io.StringIO):
                    result = check.main(["--work-dir", c.work])
                self.assertEqual(result, exit_code)
                self.assertEqual(len(c.results), 1)
                findings = [f for f in c.results[0].findings if f.check == "artifact"]
                self.assertEqual(len(findings), 1)
                self.assertEqual(findings[0].severity, severity)
                self.assertIsNone(c.results[0].version)

    def test_md5_mismatch_fails(self):
        c = make_checker({})
        data = zip_bytes({"x/version.php": "<?php $plugin->component = 'mod_x';"})
        src = check.Source("directory", "mod_x", download_url="https://example.invalid/x.zip", download_md5="0" * 32)
        res = check.PluginResult("mod_x", src)
        orig = check.http_get
        check.http_get = lambda *a, **k: data
        try:
            c.fetch_tree(res)
        finally:
            check.http_get = orig
        self.assertTrue(any(f.severity == "FAIL" and f.check == "integrity" for f in res.findings))


class CveScan(unittest.TestCase):
    def test_rejected_records_are_ignored_and_matches_reported(self):
        import tempfile
        tmp = tempfile.mkdtemp(prefix="ph-cve-")
        try:
            d = os.path.join(tmp, "cves", "2025", "1xxx")
            os.makedirs(d)

            def dump(obj, path):
                with open(path, "w") as fh:
                    json.dump(obj, fh)

            def rec(cve_id, state, text):
                return {"cveMetadata": {"cveId": cve_id, "state": state, "datePublished": "2025-01-01"},
                        "containers": {"cna": {"descriptions": [{"value": text}], "references": []}}}
            dump(rec("CVE-2025-1000", "PUBLISHED", "Moodle PDF Annotator plugin allows XSS"),
                      os.path.join(d, "CVE-2025-1000.json"))
            dump(rec("CVE-2025-1001", "REJECTED", "Moodle pdfannotator duplicate"),
                      os.path.join(d, "CVE-2025-1001.json"))
            dump(rec("CVE-2025-1002", "PUBLISHED", "Moodle core stack trace leak"),
                      os.path.join(d, "CVE-2025-1002.json"))
            c = make_checker({"cve_generic_terms": ["stack"]}, cve_dir=tmp)
            pdf = check.PluginResult("mod_pdfannotator", check.Source("directory", "mod_pdfannotator"))
            stack = check.PluginResult("qtype_stack", check.Source("directory", "qtype_stack"))
            c.results = [pdf, stack]
            c.check_cves()
            ids = " ".join(f.message for f in pdf.findings)
            self.assertIn("CVE-2025-1000", ids)
            self.assertNotIn("CVE-2025-1001", ids)
            self.assertFalse(stack.findings, "generischer Begriff 'stack' darf nicht matchen")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class BashCrosscheck(unittest.TestCase):
    def test_broken_file_returns_none(self):
        import tempfile
        if not shutil.which("bash"):
            self.skipTest("bash fehlt")
        with tempfile.NamedTemporaryFile("w", suffix=".sh", delete=False) as fh:
            fh.write("a=(x\nexit 7\n")
        try:
            self.assertIsNone(check.bash_crosscheck(fh.name, ["a"]))
        finally:
            os.unlink(fh.name)


class Baseline(unittest.TestCase):
    def test_internal_failure_invalidates_baseline(self):
        for severity in ("FAIL", "INFO"):
            with self.subTest(severity=severity):
                c = make_checker({})
                self.addCleanup(shutil.rmtree, c.work)
                c.gfind("FAIL", "internal", "deterministic failure")
                res = check.PluginResult("mod_x", check.Source("directory", "mod_x"))
                res.add("FAIL", "vulnerability", "CVE-2099-1")
                c.results = [res]
                base = {"global_findings": [{"severity": severity, "check": "internal",
                                             "message": "deterministic failure"}],
                        "plugins": [{"component": "mod_x", "findings": [res.findings[0].as_dict()]}]}
                with patch.object(check, "read_json", return_value=base):
                    c.apply_baseline("baseline.json")
                self.assertEqual(c.global_findings[0].severity, "FAIL")
                self.assertEqual(res.findings[0].severity, "FAIL")
                self.assertTrue(any(f.check == "baseline" and f.severity == "WARN" for f in c.global_findings))

    def test_main_fails_when_both_runs_have_the_same_internal_error(self):
        c = make_checker({})
        self.addCleanup(shutil.rmtree, c.work)
        base = {"global_findings": [{"severity": "FAIL", "check": "internal",
                                     "message": "Abbruch: RuntimeError: deterministic failure"}]}
        with patch.object(check, "read_json", side_effect=[{}, base]), \
                patch.object(check.Checker, "run", side_effect=RuntimeError("deterministic failure")), \
                patch.dict(os.environ, {"GITHUB_STEP_SUMMARY": ""}), patch("sys.stdout", new_callable=io.StringIO):
            result = check.main(["--work-dir", c.work, "--baseline", "baseline.json"])
        self.assertEqual(result, 1)

    def test_security_ids_and_versions_are_not_normalized(self):
        # Each pair differs only in digits: the former blanket substitution made their keys
        # identical. Only the first finding exists in the baseline and may be downgraded.
        for old_message, new_message in (
                ("CVE-2025-1000: Moodle demo XSS", "CVE-2026-9000: Moodle demo XSS"),
                ("GHSA-ab12-cd34-ef56: XSS", "GHSA-ab98-cd76-ef54: XSS"),
                ("pdf.js 2.14.34 affected by GHSA-test", "pdf.js 3.0.0 affected by GHSA-test")):
            with self.subTest(message=new_message):
                c = make_checker({})
                res = check.PluginResult("mod_x", check.Source("directory", "mod_x"))
                res.add("FAIL", "vulnerability", old_message)
                res.add("FAIL", "vulnerability", new_message)
                c.results = [res]
                base = {"plugins": [{"component": "mod_x", "findings": [res.findings[0].as_dict()]}]}
                with patch.object(check, "read_json", return_value=base):
                    c.apply_baseline("baseline.json")
                self.assertEqual(res.findings[0].severity, "WARN")
                self.assertEqual(res.findings[1].severity, "FAIL")

    def test_pluginlist_age_is_still_normalized(self):
        old = check.Finding("WARN", "plugins.json", "plugins.json ist 40 Tage alt.")
        new = check.Finding("WARN", "plugins.json", "plugins.json ist 41 Tage alt.")
        # Exercise the saved-report dictionary and live Finding forms of the same global key.
        self.assertEqual(check.Checker.finding_key("*", old.as_dict()), check.Checker.finding_key("*", new))

    def test_known_findings_are_downgraded_new_ones_stay(self):
        import tempfile
        c = make_checker({})
        r = check.PluginResult("mod_x", check.Source("directory", "mod_x"))
        r.add("FAIL", "maintenance", "Letzter Commit vor 800 Tagen - vermutlich unmaintained.")
        r.add("FAIL", "vulnerability", "CVE-2099-1 - unbewertet")
        r.add("FAIL", "vulnerability", "CVE-2099-2 - unbewertet")
        r.add("FAIL", "pin", "Tag `v1` existiert im Repository nicht (mehr).")
        c.results = [r]
        c.gfind("WARN", "plugins.json", "plugins.json ist 41 Tage alt - updatePluginList.sh ausführen.")
        base = {"plugins": [{"component": "mod_x", "findings": [
            {"severity": "FAIL", "check": "maintenance", "message": "Letzter Commit vor 793 Tagen - vermutlich unmaintained."},
            {"severity": "FAIL", "check": "vulnerability", "message": "CVE-2099-2 - unbewertet"},
            {"severity": "FAIL", "check": "pin", "message": "Tag `v1` existiert im Repository nicht (mehr)."}]}],
            "global_findings": [{"severity": "WARN", "check": "plugins.json",
                                 "message": "plugins.json ist 40 Tage alt - updatePluginList.sh ausführen."}]}
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
            json.dump(base, fh)
        try:
            c.apply_baseline(fh.name)
        finally:
            os.unlink(fh.name)
        # known vulnerability and maintenance findings stay visible as WARN, everything else known is INFO
        self.assertEqual([f.severity for f in r.findings], ["WARN", "FAIL", "WARN", "INFO"])
        self.assertEqual(c.global_findings[0].severity, "INFO")
        self.assertEqual(c.overall(), "FAIL")
        self.assertIn("4 Befunde bestanden schon im Basisstand: 2 zu", c.global_findings[-1].message)


class IgnoreList(unittest.TestCase):
    def setup(self, entries):
        c = make_checker({"ignored_findings": entries})
        r = check.PluginResult("mod_x", check.Source("directory", "mod_x"))
        r.add("FAIL", "maintenance", "Letzter Commit vor 800 Tagen - vermutlich unmaintained.")
        r.add("WARN", "pin", "Pin auf Branch `main` statt Tag.")
        other = check.PluginResult("mod_y", check.Source("directory", "mod_y"))
        other.add("WARN", "pin", "Pin auf Branch `main` statt Tag.")
        c.results = [r, other]
        c.gfind("FAIL", "duplicate", "`mod_z` kommt aus mehreren Quellen.")
        c.apply_ignores()
        return c, r, other

    def test_matching_finding_becomes_info_with_reason(self):
        c, r, other = self.setup([{"component": "mod_x", "check": "maintenance", "reason": "risk_accepted",
                                   "note": "stabil, kein Ersatz"}])
        self.assertEqual(r.findings[0].severity, "INFO")
        self.assertIn("war FAIL - Risiko akzeptiert: stabil, kein Ersatz", r.findings[0].message)
        self.assertEqual(r.findings[1].severity, "WARN")              # other check untouched
        self.assertEqual(other.findings[0].severity, "WARN")          # other component untouched
        self.assertFalse(any(f.check == "ignore" for f in c.global_findings))

    def test_match_narrows_and_star_targets_global_findings(self):
        c, r, _ = self.setup([{"component": "mod_x", "check": "pin", "match": "Tag `v1` existiert", "reason":
                               "false_positive", "note": "n"},
                              {"component": "*", "check": "duplicate", "match": "mod_z", "reason": "mitigated",
                               "note": "n"}])
        self.assertEqual(r.findings[1].severity, "WARN")
        self.assertTrue(any(f.severity == "WARN" and f.check == "ignore" for f in c.global_findings))  # unused
        self.assertEqual(c.global_findings[0].severity, "INFO")

    def test_invalid_entry_fails_and_is_not_applied(self):
        for bad in ({"component": "mod_x", "check": "maintenance", "reason": "risk_accepted"},      # no note
                    {"component": "mod_x", "check": "maintenance", "reason": "egal", "note": "n"}):
            c, r, _ = self.setup([bad])
            self.assertEqual(r.findings[0].severity, "FAIL")
            self.assertTrue(any(f.severity == "FAIL" and f.check == "ignore" for f in c.global_findings))


class Duplicates(unittest.TestCase):
    def test_unexpected_duplicate_fails(self):
        c = make_checker({})
        c.results = [check.PluginResult("mod_x", check.Source("directory", "mod_x"), version="1"),
                     check.PluginResult("mod_x", check.Source("git-tag", None, origin="f"), version="2")]
        c.check_duplicates()
        self.assertTrue(any(f.severity == "FAIL" for f in c.global_findings))

    def test_allowed_duplicate_flags_downgrade(self):
        c = make_checker({"allowed_duplicates": {"auth_oidc": "runtime switch"}})
        up = check.PluginResult("auth_oidc", check.Source("directory", "auth_oidc"), version="2024100740")
        fork = check.PluginResult("auth_oidc", check.Source("git-branch", None, origin="f"), version="2024100737")
        c.results = [up, fork]
        c.check_duplicates()
        self.assertFalse(any(f.severity == "FAIL" for f in c.global_findings))
        self.assertTrue(any(f.check == "downgrade" for f in fork.findings))
        self.assertFalse(any(f.check == "downgrade" for f in up.findings))


if __name__ == "__main__":
    unittest.main()
