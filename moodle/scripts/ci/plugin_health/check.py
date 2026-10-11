#!/usr/bin/env python3
"""Health check for the third-party Moodle plugins that dbp-moodle ships.

Reads the plugin set the image build actually uses (pluginList.sh, plugins.json and the custom
download logic in downloadPlugins.sh), fetches every plugin the way the build does, and checks:

* the shipped artifact: component name, version number, license header and bundled third-party
  libraries, declared in thirdpartylibs.xml or detected in the files (looked up in OSV)
* the upstream repository: archived state, activity, releases, published security advisories
* known CVEs (CVEProject/cvelistV5 checkout) that mention the plugin
* consistency: pins that are behind newer releases, branch pins, stale plugins.json, components
  shipped from two sources with a version downgrade between them

Findings can be put on an ignore list (config.json, ignored_findings) with a reason and a note; they
stay in the report as INFO. Vulnerability hits are FAIL until they are on that list.

Every check that could not run is reported as UNCHECKED, never as OK. Standard library only.
Nothing from the checked repositories is executed, except pluginList.sh in the optional bash
cross-check (the image build sources the same file).
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import io
import json
import os
import re
import shlex
import subprocess
import sys
import time
import urllib.error
import urllib.request
import zipfile
from dataclasses import dataclass, field

SEVERITIES = ["OK", "INFO", "UNCHECKED", "WARN", "FAIL"]
SEV_RANK = {s: i for i, s in enumerate(SEVERITIES)}
TODAY = dt.datetime.now(dt.timezone.utc)
IGNORE_REASONS = {"risk_accepted": "Risiko akzeptiert", "mitigated": "anderweitig mitigiert",
                  "false_positive": "False Positive", "fixed": "behoben"}
# checks whose findings stay WARN in a pull request even if the base branch already has them
BASELINE_KEEP_WARN = {"vulnerability", "maintenance"}
HTTP_TIMEOUT = 60
# "/*! jQuery UI 1.8.11" style banner at the top of a bundled script: (name, version)
BANNER_RE = re.compile(r"/\*[!*]?[\s*]*(?:@(?:license|preserve)\s+)?([A-Za-z][\w.@/ -]{1,40}?)[\s,-]+v?(\d+\.\d+(?:\.\d+)?)\b")
BANNER_HEAD = 2000
USER_AGENT = "dbp-moodle-plugin-health-check"


# --------------------------------------------------------------------------------------------
# Data model
# --------------------------------------------------------------------------------------------
@dataclass
class Finding:
    severity: str
    check: str
    message: str

    def as_dict(self):
        return {"severity": self.severity, "check": self.check, "message": self.message}


@dataclass
class Source:
    """One way a component reaches the image."""
    kind: str                  # directory | marketplace-pin | git-tag | git-branch | github-archive
    component: str | None      # known up front for directory/marketplace sources
    repo_url: str | None = None
    ref: str | None = None
    moodle_release: str | None = None
    download_url: str | None = None
    download_md5: str | None = None
    origin: str = ""           # where in the build scripts this source was defined


@dataclass
class PluginResult:
    component: str
    source: Source
    release: str | None = None
    version: str | None = None
    repo_url: str | None = None
    metrics: dict = field(default_factory=dict)
    findings: list = field(default_factory=list)

    def add(self, severity, check, message):
        self.findings.append(Finding(severity, check, message))

    @property
    def worst(self):
        if not self.findings:
            return "OK"
        return max((f.severity for f in self.findings), key=lambda s: SEV_RANK[s])


# --------------------------------------------------------------------------------------------
# Parsing the build scripts (static, nothing is executed)
# --------------------------------------------------------------------------------------------
def parse_bash_arrays(text: str):
    """Return ({name: [items]}, {name: [(commented_component, comment_text)]}).

    Supports the forms used in pluginList.sh: multi-line arrays with whole-line and trailing
    comments, single-line arrays, "${other[@]}" references and += appends. Anything else is
    left alone; the bash cross-check catches what this parser misses.
    """
    arrays: dict[str, list[str]] = {}
    commented: dict[str, list[tuple[str, str]]] = {}
    cur = None
    for raw in text.splitlines():
        line = raw.strip()
        if cur is None:
            m = re.match(r"^([A-Za-z_]\w*)(\+?)=\((.*)$", line)
            if not m:
                continue
            cur = m.group(1)
            if not m.group(2) or cur not in arrays:
                arrays.setdefault(cur, [])
                if not m.group(2):
                    arrays[cur] = []
            commented.setdefault(cur, [])
            line = m.group(3).strip()
            if not line:
                continue
        if line.startswith("#"):
            cm = re.match(r"#\s*([a-z][a-z0-9]*_[a-z0-9_]+)\b\s*(.*)", line)
            if cm:
                commented[cur].append((cm.group(1), cm.group(2).strip()))
            continue
        code = re.split(r"\s#", " " + line, maxsplit=1)[0].strip()
        closing = code.endswith(")")
        if closing:
            code = code[:-1]
        for tok in shlex.split(code, comments=False):
            arrays[cur].append(tok)
        if closing:
            cur = None
    # Expand ${name[@]} references (definition order is enough for this file's structure).
    def expand(name, seen=()):
        out = []
        for item in arrays.get(name, []):
            m = re.fullmatch(r"\$\{(\w+)\[@\]\}", item)
            if m:
                if m.group(1) in seen:
                    raise ValueError(f"circular array reference {m.group(1)}")
                out.extend(expand(m.group(1), seen + (name,)))
            else:
                out.append(item)
        return out
    return {n: expand(n) for n in arrays}, commented


def bash_crosscheck(plugin_list_path: str, names: list[str]):
    """Source pluginList.sh in a clean bash and return the arrays as bash sees them."""
    script = f'source "{plugin_list_path}" >/dev/null 2>&1 || exit 3\n'
    for n in names:
        script += f'printf "%s\\0" "{n}"; printf "%s\\n" "${{{n}[@]}}"; printf "\\0"\n'
    r = subprocess.run(["bash", "--noprofile", "--norc", "-c", script], capture_output=True,
                       text=True, timeout=30, env={"PATH": "/usr/bin:/bin"})
    if r.returncode != 0:
        return None
    parts = r.stdout.split("\0")
    result = {}
    for i in range(0, len(parts) - 1, 2):
        result[parts[i]] = [x for x in parts[i + 1].split("\n") if x]
    return result


def parse_download_script(text: str):
    """Extract the custom (non-directory) plugin sources from downloadPlugins.sh."""
    sources: list[Source] = []
    functions = {m.group(1): m.group(2) for m in
                 re.finditer(r"^(\w+)\s*\(\)\s*\{(.*?)^\}", text, re.S | re.M)}
    top_level = re.sub(r"^(\w+)\s*\(\)\s*\{.*?^\}", "", text, flags=re.S | re.M)
    called = set()
    for line in top_level.splitlines():
        m = re.match(r"^\s*([A-Za-z_]\w*)\b", line)
        if m and m.group(1) in functions:
            called.add(m.group(1))
    # functions called from other called functions (one level is enough here)
    for f in list(called):
        for g in functions:
            if re.search(rf"^\s*{g}\b", functions[f], re.M):
                called.add(g)

    def assignments(body):
        return {m.group(1): m.group(2) for m in
                re.finditer(r'^\s*(\w+)="?([^"\s]+)"?', body, re.M)}

    def subst(value, env):
        return re.sub(r"\$\{?(\w+)\}?", lambda m: env.get(m.group(1), m.group(0)), value)

    helper_release = None
    for fname, body in functions.items():
        if re.search(r'curl\b.{0,200}?github\.com/\$\{repo\}/archive/refs/tags/\$\{tag\}', body, re.S):
            helper_release = fname
    for fname in sorted(called):
        body = functions[fname]
        env = assignments(body)
        m = re.search(r"git clone\s+(\S+)", body)
        if m:
            url = subst(m.group(1), env)
            if "target_tag" in env:
                sources.append(Source("git-tag", None, url, env["target_tag"], origin=fname))
            elif "target_branch" in env:
                sources.append(Source("git-branch", None, url, env["target_branch"], origin=fname))
            else:
                sources.append(Source("git-branch", None, url, None, origin=fname))
            continue
        for um in re.finditer(r"https://marketplace\.moodle\.com/api/plugins/(\w+)/versions/(\d+)/download", body):
            sources.append(Source("marketplace-pin", um.group(1), download_url=um.group(0),
                                  ref=um.group(2), origin=fname))
        for um in re.finditer(r'https://github\.com/([\w.-]+/[\w.-]+)/archive/refs/tags/([^"\s]+?)\.zip', body):
            repo, tag = um.group(1), subst(um.group(2), env)
            if "$" in repo:
                continue  # generic helper, handled through its call sites
            sources.append(Source("github-archive", None, f"https://github.com/{repo}", tag, origin=fname))
        if helper_release:
            for cm in re.finditer(rf"^\s*{helper_release}\s+(\w+)\s+([\w.-]+/[\w.-]+)\s+(\S+)", body, re.M):
                sources.append(Source("github-archive", cm.group(1), f"https://github.com/{cm.group(2)}",
                                      cm.group(3), origin=fname))
    legacy = {m.group(2): m.group(1) for m in
              re.finditer(r"moosh\s+plugin-download\s+-v\s+([\d.]+)\s+(\w+)", text)}
    uncalled = sorted(set(functions) - called)
    return sources, legacy, uncalled


def parse_moodle_version(dockerfile_text: str):
    m = re.search(r'MOODLE_VERSION:-"?([\d.]+)"?', dockerfile_text) or \
        re.search(r'MOODLE_VERSION="?([\d.]+)"?', dockerfile_text)
    return m.group(1) if m else None


def select_directory_version(plugin: dict, moodle_release: str):
    """Highest version whose supportedmoodles contains moodle_release.

    Assumption: this mirrors "moosh plugin-download -v <release>", which takes the newest version
    that declares support for the requested release.
    """
    candidates = [v for v in plugin.get("versions", [])
                  if any(str(sm.get("release")) == moodle_release for sm in v.get("supportedmoodles", []))]
    if not candidates:
        return None
    return max(candidates, key=lambda v: int(str(v.get("version", "0")) or 0))


def normalize_repo_url(url: str | None):
    if not url:
        return None
    url = url.strip().rstrip("/")
    url = re.sub(r"\.git$", "", url)
    url = re.sub(r"^(https://(?:github\.com|bitbucket\.org)/[^/]+/[^/]+)/.*$", r"\1", url)
    return url


# --------------------------------------------------------------------------------------------
# Small helpers
# --------------------------------------------------------------------------------------------
def http_get(url, headers=None, data=None, retries=3, delay=5):
    hdrs = {"User-Agent": USER_AGENT}
    hdrs.update(headers or {})
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, data=data, headers=hdrs)
            with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as resp:
                return resp.read()
        except urllib.error.HTTPError as e:
            last = e
            if e.code in (401, 403, 404, 410, 422):
                raise
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            last = e
        time.sleep(delay * (attempt + 1))
    raise last


def git(args, cwd=None, timeout=600):
    r = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, errors="replace",
                       timeout=timeout, env={**os.environ, "GIT_TERMINAL_PROMPT": "0"})
    if r.returncode != 0:
        raise RuntimeError(f"git {' '.join(args[:2])} failed: {r.stderr.strip()[:300]}")
    return r.stdout


def slug(url):
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", url.split("://", 1)[-1])


def version_to_date(version: str):
    m = re.match(r"^(\d{4})(\d{2})(\d{2})", str(version))
    if not m:
        return None
    try:
        return dt.datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)), tzinfo=dt.timezone.utc)
    except ValueError:
        return None


def tag_family(tag: str):
    """Regex matching later releases of the same line: every number but the first is a wildcard."""
    parts = re.split(r"(\d+)", tag)
    out, seen_number = "", False
    for p in parts:
        if p.isdigit():
            out += p if not seen_number else r"\d+"
            seen_number = True
        else:
            out += re.escape(p)
    return re.compile("^" + out + "$")


def version_tuple(tag: str):
    return tuple(int(x) for x in re.findall(r"\d+", tag))


def classify_license(version_php: str | None):
    if not version_php:
        return None
    text = re.sub(r"^\s*(//|\*|/\*\*?)\s?", "", version_php, flags=re.M)
    text = re.sub(r"\s+", " ", text)
    if re.search(r"either version 3 of the License, or \(at your option\) any later version", text):
        return "GPL-3.0-or-later"
    if re.search(r"GNU General Public License", text, re.I) and "version 3" in text:
        return "GPL-3.0"
    if re.search(r"GNU General Public License", text, re.I):
        return "GPL (version unklar)"
    return None


def read_text(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def read_json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def norm_text(s: str):
    return re.sub(r"[^a-z0-9]", "", s.lower())


# --------------------------------------------------------------------------------------------
# Source trees: read-only access to a ZIP or a checked-out directory
# --------------------------------------------------------------------------------------------
class Tree:
    def files(self):
        raise NotImplementedError

    def read(self, path):
        raise NotImplementedError

    def plugin_roots(self):
        """[(root_path, component, version_php_text)] for every version.php declaring a component."""
        roots = []
        for f in self.files():
            if f == "version.php" or f.endswith("/version.php"):
                if f.count("/") > 4:
                    continue
                txt = self.read(f) or ""
                m = re.search(r"\$plugin->component\s*=\s*['\"]([a-z0-9_]+)['\"]", txt)
                if m:
                    roots.append((f[: -len("version.php")], m.group(1), txt))
        roots.sort(key=lambda r: r[0].count("/"))
        return roots


class ZipTree(Tree):
    MAX_MEMBER = 50 * 1024 * 1024

    def __init__(self, data: bytes):
        self.zf = zipfile.ZipFile(io.BytesIO(data))
        self.names = [n for n in self.zf.namelist() if not n.endswith("/")]

    def files(self):
        return self.names

    def read(self, path):
        try:
            info = self.zf.getinfo(path)
        except KeyError:
            return None
        if info.file_size > self.MAX_MEMBER:
            return None
        return self.zf.read(info).decode("utf-8", errors="replace")


class DirTree(Tree):
    def __init__(self, root):
        self.root = root
        self._files = []
        for d, dirs, fs in os.walk(root):
            dirs[:] = [x for x in dirs if x != ".git"]
            for f in fs:
                p = os.path.join(d, f)
                if not os.path.islink(p):
                    self._files.append(os.path.relpath(p, root))

    def files(self):
        return self._files

    def read(self, path):
        p = os.path.join(self.root, path)
        if not os.path.isfile(p) or os.path.islink(p) or os.path.getsize(p) > 50 * 1024 * 1024:
            return None
        with open(p, encoding="utf-8", errors="replace") as fh:
            return fh.read()


# --------------------------------------------------------------------------------------------
# The checker
# --------------------------------------------------------------------------------------------
class Checker:
    def __init__(self, args, config):
        self.args = args
        self.cfg = config
        self.th = config.get("thresholds", {})
        self.work = os.path.abspath(args.work_dir)
        os.makedirs(os.path.join(self.work, "repos"), exist_ok=True)
        os.makedirs(os.path.join(self.work, "src"), exist_ok=True)
        self.token = os.environ.get("GITHUB_TOKEN")
        self.global_findings: list[Finding] = []
        self.results: list[PluginResult] = []
        self.repo_cache: dict[str, dict] = {}
        self.unchecked: dict[str, str] = {}
        self.downloads = 0

    # ---------------- top level ----------------
    def run(self):
        root = self.args.repo_root
        p_list = os.path.join(root, "moodle/scripts/install/pluginList.sh")
        p_dl = os.path.join(root, "moodle/scripts/install/downloadPlugins.sh")
        p_json = os.path.join(root, "moodle/scripts/install/plugins.json")
        p_docker = os.path.join(root, "moodle/Dockerfile")

        list_text = read_text(p_list)
        arrays, commented = parse_bash_arrays(list_text)
        if not self.args.no_bash_crosscheck:
            names = [n for n in ("plugin_dependency_list", "plugin_list", "legacy_plugin_list",
                                 "moodle_plugin_list", "plugin_list_components") if n in arrays]
            seen = bash_crosscheck(os.path.abspath(p_list), names)
            if seen is None:
                self.gfind("FAIL", "parser", "pluginList.sh lässt sich in bash nicht sourcen.")
            else:
                for n in names:
                    if seen.get(n) != arrays.get(n):
                        self.gfind("FAIL", "parser",
                                   f"Statischer Parser und bash lesen `{n}` unterschiedlich - Parser anpassen. "
                                   f"Nur bash: {sorted(set(seen.get(n, [])) - set(arrays.get(n, [])))}, "
                                   f"nur Parser: {sorted(set(arrays.get(n, [])) - set(seen.get(n, [])))}")

        moodle_version = self.args.moodle_version or parse_moodle_version(read_text(p_docker))
        if not moodle_version:
            self.gfind("FAIL", "config", "MOODLE_VERSION nicht im Dockerfile gefunden; --moodle-version angeben.")
            return
        self.moodle_version = moodle_version
        major_minor = ".".join(moodle_version.split(".")[:2])
        self.major_minor = major_minor

        plugins_json = read_json(p_json)
        self.check_pluginlist_age(plugins_json)
        directory = {p["component"]: p for p in plugins_json.get("plugins", [])}

        dl_sources, legacy, uncalled = parse_download_script(read_text(p_dl))
        for f in uncalled:
            self.gfind("INFO", "build-script", f"Funktion `{f}` in downloadPlugins.sh wird nicht aufgerufen.")

        live = self.fetch_live_pluglist() if self.args.live_pluglist else None

        # Directory sources: dependencies, main list and legacy list
        legacy_list = arrays.get("legacy_plugin_list", [])
        for comp in arrays.get("moodle_plugin_list", []) + legacy_list:
            # legacy plugins are fetched with an explicit "moosh plugin-download -v <release>"
            release = legacy.get(comp) if comp in legacy_list else major_minor
            src = Source("directory", comp, moodle_release=release, origin="pluginList.sh")
            res = PluginResult(comp, src)
            self.results.append(res)
            entry = directory.get(comp)
            if not entry:
                res.add("FAIL", "directory", "Kein Eintrag in plugins.json - updatePluginList.sh ausführen.")
                continue
            if release is None:
                res.add("FAIL", "directory", "Legacy-Plugin ohne erkennbares `moosh plugin-download -v`.")
                continue
            ver = select_directory_version(entry, release)
            if not ver:
                res.add("FAIL", "directory", f"Keine Version in plugins.json unterstützt Moodle {release}.")
                continue
            src.download_url, src.download_md5 = ver.get("downloadurl"), ver.get("downloadmd5")
            res.release, res.version = ver.get("release"), str(ver.get("version"))
            newest = max(entry.get("versions", []), key=lambda v: int(str(v.get("version", "0")) or 0))
            if int(newest.get("version", 0)) > int(ver.get("version", 0)):
                supported = ", ".join(str(s.get("release")) for s in newest.get("supportedmoodles", []))
                res.add("INFO", "version-selection",
                        f"Neuere Version {newest.get('release')} ({newest.get('version')}) existiert, ist aber nur "
                        f"für Moodle {supported} freigegeben - ausgeliefert wird die neueste für {release}.")
            res.repo_url = normalize_repo_url(entry.get("source") or ver.get("vcsrepositoryurl"))
            res.metrics["directory_name"] = entry.get("name")
            res.metrics["directory_last_release"] = entry.get("timelastreleased")
            if comp in arrays.get("legacy_plugin_list", []):
                res.add("WARN", "legacy", f"Wird für Moodle {release} geladen, nicht für {major_minor} "
                                          f"(legacy_plugin_list).")
            if live:
                self.compare_live(res, live.get(comp), release)

        # Custom sources from downloadPlugins.sh
        for src in dl_sources:
            if src.kind == "marketplace-pin":
                entry = directory.get(src.component)
                res = PluginResult(src.component, src, version=src.ref)
                res.repo_url = normalize_repo_url(entry.get("source")) if entry else None
                if entry:
                    match = [v for v in entry.get("versions", []) if str(v.get("version")) == src.ref]
                    if match:
                        res.release = match[0].get("release")
                        src.download_md5 = match[0].get("downloadmd5")
                self.results.append(res)
            else:
                # The real component comes from version.php; until then (or if fetching fails) use a guess
                # from the repo name or the download function so the report stays readable.
                repo_url = normalize_repo_url(src.repo_url)
                guess = src.component
                if not guess:
                    m = re.search(r"moodle-([a-z]+_[a-z0-9_]+)$", repo_url or "")
                    guess = f"{m.group(1)}?" if m else f"?{src.origin}"
                res = PluginResult(guess, src, repo_url=repo_url)
                self.results.append(res)

        # Fetch + check every source
        for res in self.results:
            if res.findings and res.worst == "FAIL" and res.source.kind == "directory" and not res.version:
                continue
            try:
                self.check_artifact(res)
            except urllib.error.HTTPError as e:
                severity = "FAIL" if e.code in (404, 410) else "UNCHECKED"
                res.add(severity, "artifact", f"Artefakt nicht abrufbar: {e}")
            except Exception as e:  # report, never hide
                res.add("UNCHECKED", "artifact", f"Artefakt nicht prüfbar: {e}")
            if res.repo_url:
                try:
                    self.check_repo(res)
                except Exception as e:
                    res.add("UNCHECKED", "repo", f"Repository nicht prüfbar: {e}")
            else:
                res.add("UNCHECKED", "repo", "Kein Quell-Repository bekannt.")

        self.check_custom_coverage(commented)
        self.check_duplicates()
        if self.args.cve_dir:
            try:
                self.check_cves()
            except Exception as e:
                message = f"CVE-Abgleich fehlgeschlagen: {e}"
                self.unchecked["cve"] = message
                self.gfind("UNCHECKED", "cve", message)
        else:
            self.unchecked["cve"] = "kein --cve-dir angegeben"
        self.check_osv()

    def gfind(self, severity, check, message):
        self.global_findings.append(Finding(severity, check, message))

    # ---------------- plugins.json / live list ----------------
    def check_pluginlist_age(self, plugins_json):
        ts = plugins_json.get("timestamp")
        if not ts:
            self.gfind("WARN", "plugins.json", "plugins.json hat keinen Zeitstempel.")
            return
        age = (TODAY - dt.datetime.fromtimestamp(int(ts), dt.timezone.utc)).days
        if age > self.th.get("pluginsjson_max_age_days", 30):
            self.gfind("WARN", "plugins.json", f"plugins.json ist {age} Tage alt - updatePluginList.sh ausführen.")
        else:
            self.gfind("INFO", "plugins.json", f"plugins.json ist {age} Tage alt.")

    def fetch_live_pluglist(self):
        url = "https://download.moodle.org/api/1.3/pluglist.php"
        for attempt in range(5):
            try:
                data = json.loads(http_get(url, retries=2))
                if len(data.get("plugins", [])) > 2000:
                    return {p["component"]: p for p in data["plugins"]}
            except Exception:
                pass
            time.sleep(5)
        self.unchecked["live-pluglist"] = "Live-Verzeichnis nicht (vollständig) abrufbar"
        return None

    def compare_live(self, res, live_entry, release):
        if not live_entry:
            res.add("FAIL", "directory", "Im Live-Verzeichnis nicht mehr vorhanden - zurückgezogen?")
            return
        ver = select_directory_version(live_entry, release)
        if ver and int(str(ver.get("version", "0")) or 0) > int(res.version or "0"):
            res.add("WARN", "outdated", f"Neuere Version im Verzeichnis: {ver.get('release')} "
                                        f"({ver.get('version')}), ausgeliefert wird {res.release} ({res.version}).")

    # ---------------- artifact ----------------
    def fetch_tree(self, res):
        src = res.source
        if src.kind in ("directory", "marketplace-pin"):
            if self.args.offline:
                raise RuntimeError("Offline-Modus: Download übersprungen")
            if not src.download_url:
                raise RuntimeError("keine Download-URL")
            cache = os.path.join(self.work, "zips", slug(src.download_url) + ".zip")
            if os.path.isfile(cache):
                with open(cache, "rb") as fh:
                    data = fh.read()
            else:
                if self.downloads and self.downloads % 15 == 0:
                    time.sleep(60)  # same pacing as downloadPlugins.sh
                self.downloads += 1
                data = http_get(src.download_url, retries=4, delay=10)
                time.sleep(self.args.download_delay)
            md5 = hashlib.md5(data).hexdigest()
            if src.download_md5 and md5 != src.download_md5:
                res.add("FAIL", "integrity", f"MD5 des Downloads ({md5}) passt nicht zu plugins.json "
                                             f"({src.download_md5}).")
                if os.path.isfile(cache):
                    os.unlink(cache)
            elif not os.path.isfile(cache):
                os.makedirs(os.path.dirname(cache), exist_ok=True)
                with open(cache, "wb") as fh:
                    fh.write(data)
            return ZipTree(data)
        if src.kind == "github-archive":
            if self.args.offline:
                # same content as the tag; fetch it with git instead of HTTP
                return self.checkout(src.repo_url, src.ref)
            m = re.match(r"https://github\.com/([^/]+/[^/]+)", src.repo_url)
            data = http_get(f"https://github.com/{m.group(1)}/archive/refs/tags/{src.ref}.zip", retries=4)
            return ZipTree(data)
        return self.checkout(src.repo_url, src.ref)

    def checkout(self, url, ref):
        dest = os.path.join(self.work, "src", slug(url) + "@" + slug(ref or "HEAD"))
        if not os.path.isdir(dest):
            args = ["clone", "-q", "--depth", "1"]
            if ref:
                args += ["--branch", ref]
            git(args + [url, dest])
        return DirTree(dest)

    def check_artifact(self, res):
        expected_version = res.version
        # Clear metadata before fetching: even a download failure must leave fixed-version
        # ignores without a trusted version, rather than falling back to directory metadata.
        res.version = None
        tree = self.fetch_tree(res)
        roots = tree.plugin_roots()
        if not roots:
            res.add("FAIL", "artifact", "Keine version.php mit $plugin->component gefunden.")
            return
        root, component, vphp = roots[0]
        if "?" in res.component:  # placeholder until version.php is known
            res.component = component
        elif component != res.component:
            res.add("FAIL", "artifact", f"Artefakt enthält `{component}` statt `{res.component}`.")
        # Require a complete numeric assignment; accepting the prefix of an expression such as
        # "2026020100 - 10000" would invent a version. Never execute PHP from downloaded plugins.
        m = re.search(r"\$plugin->version\s*=\s*([0-9]+(?:\.[0-9]+)?)\s*;", vphp)
        if m:
            # A different component's version cannot establish that this plugin contains a fix.
            if component == res.component:
                res.version = m.group(1)
            if expected_version is not None and str(expected_version) != m.group(1):
                res.add("FAIL", "artifact", f"Version im Artefakt ({m.group(1)}) passt nicht zu den "
                                             f"Metadaten ({expected_version}).")
            vdate = version_to_date(m.group(1))
            if vdate and (vdate - TODAY).days > self.th.get("future_version_tolerance_days", 31):
                res.add("WARN", "version", f"Versionsnummer {m.group(1)} liegt in der Zukunft. Spätere "
                                           f"reguläre Releases mit kleinerer Nummer lassen sich nicht installieren.")
        else:
            res.add("FAIL", "artifact", "Keine auswertbare $plugin->version in version.php gefunden.")
        rm = re.search(r"\$plugin->release\s*=\s*['\"]([^'\"]+)['\"]", vphp)
        if rm and not res.release:
            res.release = rm.group(1)
        lic = classify_license(vphp)
        res.metrics["license"] = lic
        if lic is None:
            res.add("WARN", "license", "Keine GPL-Lizenz-Kopfzeile in version.php.")
        elif lic != "GPL-3.0-or-later":
            res.add("INFO", "license", f"Lizenz-Kopfzeile: {lic}.")
        self.collect_libraries(res, tree, root)

    def collect_libraries(self, res, tree, root):
        xml = tree.read(root + "thirdpartylibs.xml")
        libs = []
        if xml:
            for block in re.findall(r"<library>(.*?)</library>", xml, re.S):
                def g(tag):
                    m = re.search(rf"<{tag}>(.*?)</{tag}>", block, re.S)
                    return re.sub(r"\s+", " ", m.group(1)).strip() if m else ""
                libs.append({"name": g("name"), "version": g("version"), "license": g("license"),
                             "location": g("location")})
        res.metrics["libraries"] = libs
        res.metrics["detected_libraries"] = self.detect_libraries(tree, root)

    def detect_libraries(self, tree, root):
        """Bundled libraries found in the artifact itself, whether or not thirdpartylibs.xml lists them.

        Three sources: version banners at the top of scripts, the runtime dependencies of a nested
        npm build (package.json next to its build/ or dist/ output) and Composer's installed.json.
        A package.json at the plugin root is skipped: there the dependencies are mostly build tooling.
        """
        found, files = {}, [f for f in tree.files() if f.startswith(root) and "__MACOSX/" not in f]

        def add(name, version, path, ecosystem=None, package=None):
            found.setdefault((name, version, ecosystem), {"name": name, "version": version, "file": path[len(root):],
                                                          "ecosystem": ecosystem, "package": package})

        def load(path):
            try:
                return json.loads(tree.read(path) or "")
            except ValueError:
                return None

        for f in files:
            rel = f[len(root):]
            if rel.endswith(".js") and not re.search(r"(^|/)(tests?|node_modules)/", rel):
                for m in BANNER_RE.finditer((tree.read(f) or "")[:BANNER_HEAD]):
                    name = re.sub(r"\s+", " ", re.sub(r"(?i)\s+JavaScript Library$", "", m.group(1).strip()))
                    add(name, m.group(2), f)
            elif rel.endswith("/package.json") and "node_modules/" not in rel:
                base = f[:-len("package.json")]
                if not any(x.startswith((base + "build/", base + "dist/")) for x in files):
                    continue
                deps = (load(f) or {}).get("dependencies")
                lock = load(base + "package-lock.json") or {}
                for pkg, wanted in (deps.items() if isinstance(deps, dict) else []):
                    locked = (lock.get("packages", {}).get("node_modules/" + pkg) or
                              lock.get("dependencies", {}).get(pkg) or {}).get("version")
                    exact = wanted if re.fullmatch(r"\d+(\.\d+)+", str(wanted)) else None
                    add(pkg, locked or exact, base + ("package-lock.json" if locked else "package.json"), "npm", pkg)
            elif rel.endswith("vendor/composer/installed.json"):
                data = load(f)
                packages = data.get("packages", []) if isinstance(data, dict) else data or []
                dev = set(data.get("dev-package-names", [])) if isinstance(data, dict) else set()
                for pkg in packages:
                    if isinstance(pkg, dict) and pkg.get("name") and pkg["name"] not in dev:
                        m = re.match(r"v?(\d+(\.\d+)+)", str(pkg.get("version", "")))
                        add(pkg["name"], m.group(1) if m else None, f, "Packagist", pkg["name"])
        return sorted(found.values(), key=lambda d: (d["file"], d["name"], d["version"] or ""))

    # ---------------- repository ----------------
    def repo_data(self, url):
        if url in self.repo_cache:
            return self.repo_cache[url]
        data = {"url": url}
        dest = os.path.join(self.work, "repos", slug(url))
        if not os.path.isdir(dest):
            git(["clone", "-q", "--bare", "--filter=blob:none", url, dest])
        log = git(["--git-dir", dest, "log", "--all", "--no-merges", "--format=%cI"])
        dates = [dt.datetime.fromisoformat(x) for x in log.split()]
        data["last_commit"] = max(dates) if dates else None
        data["commits_12m"] = sum(1 for d in dates if (TODAY - d).days <= 365)
        data["active_months_24m"] = len({(d.year, d.month) for d in dates if (TODAY - d).days <= 730})
        tags = []
        for line in git(["--git-dir", dest, "for-each-ref", "--format=%(refname:short)|%(creatordate:iso-strict)",
                         "refs/tags"]).splitlines():
            name, _, date = line.partition("|")
            try:
                tags.append((name, dt.datetime.fromisoformat(date)))
            except ValueError:
                continue
        data["tags"] = tags
        rel_re = re.compile(self.cfg.get("prerelease_tag_regex", r"(?i)(rc\d*$|-rc|beta|alpha|dev|test)"))
        releases = [t for t in tags if not rel_re.search(t[0])]
        data["release_tags_12m"] = len({t[1].date() for t in releases if (TODAY - t[1]).days <= 365})
        data["latest_release_tag"] = max(releases, key=lambda t: t[1]) if releases else None
        data["git_dir"] = dest
        data["github"] = self.github_meta(url)
        self.repo_cache[url] = data
        return data

    def github_meta(self, url):
        m = re.match(r"https://github\.com/([^/]+)/([^/]+)$", url)
        if not m:
            return {"status": "kein GitHub-Repo"}
        if self.args.offline:
            return {"status": "offline"}
        if not self.token:
            return {"status": "kein GITHUB_TOKEN"}
        owner, repo = m.groups()
        hdr = {"Authorization": f"Bearer {self.token}", "Accept": "application/vnd.github+json",
               "X-GitHub-Api-Version": "2022-11-28"}
        out = {"status": "ok"}
        try:
            meta = json.loads(http_get(f"https://api.github.com/repos/{owner}/{repo}", hdr))
            out.update(archived=meta.get("archived"), disabled=meta.get("disabled"),
                       full_name=meta.get("full_name"), open_issues=meta.get("open_issues_count"),
                       license=(meta.get("license") or {}).get("spdx_id"))
            full = meta.get("full_name", f"{owner}/{repo}")
            adv = json.loads(http_get(f"https://api.github.com/repos/{full}/security-advisories"
                                      f"?state=published&per_page=100", hdr))
            out["advisories"] = [{"id": a.get("ghsa_id"), "cve": a.get("cve_id"), "summary": a.get("summary"),
                                  "severity": a.get("severity"), "published": a.get("published_at"),
                                  "url": a.get("html_url")} for a in adv]
        except Exception as e:
            out["status"] = f"API-Fehler: {e}"
        return out

    def check_repo(self, res):
        d = self.repo_data(res.repo_url)
        res.metrics.update(last_commit=d["last_commit"].date().isoformat() if d["last_commit"] else None,
                           commits_12m=d["commits_12m"], active_months_24m=d["active_months_24m"],
                           release_tags_12m=d["release_tags_12m"],
                           latest_tag=(f"{d['latest_release_tag'][0]} ({d['latest_release_tag'][1].date()})"
                                       if d["latest_release_tag"] else None))
        if d["last_commit"]:
            age = (TODAY - d["last_commit"]).days
            if age > self.th.get("stale_fail_days", 730):
                res.add("FAIL", "maintenance", f"Letzter Commit vor {age} Tagen - vermutlich unmaintained.")
            elif age > self.th.get("stale_warn_days", 365):
                res.add("WARN", "maintenance", f"Letzter Commit vor {age} Tagen.")
        # releases: tags or directory release, whichever is newer
        last_rel = d["latest_release_tag"][1] if d["latest_release_tag"] else None
        dir_ts = res.metrics.get("directory_last_release")
        if dir_ts:
            dir_dt = dt.datetime.fromtimestamp(int(dir_ts), dt.timezone.utc)
            last_rel = max(filter(None, [last_rel, dir_dt]))
        if last_rel and (TODAY - last_rel).days > self.th.get("no_release_warn_days", 365):
            res.add("WARN", "maintenance",
                    f"Letztes Release vor {(TODAY - last_rel).days} Tagen ({last_rel.date()}).")
        elif not last_rel:
            res.add("INFO", "maintenance", "Keine Release-Tags und kein Verzeichnis-Datum.")
        # pinned refs
        src = res.source
        if src.kind == "git-branch":
            res.add("WARN", "pin", f"Pin auf Branch `{src.ref or 'Default'}` statt Tag - Build nicht "
                                   f"reproduzierbar, Änderungen kommen ungeprüft ins Image.")
        if src.kind in ("git-tag", "github-archive") and src.ref:
            fam = tag_family(src.ref)
            pinned = version_tuple(src.ref)
            newer = sorted((t for t in d["tags"] if fam.match(t[0]) and version_tuple(t[0]) > pinned),
                           key=lambda t: version_tuple(t[0]))
            if newer:
                res.add("WARN", "pin", f"Gepinnt auf `{src.ref}`, neuer in derselben Linie: "
                                       f"`{newer[-1][0]}` ({newer[-1][1].date()}).")
            if src.ref not in {t[0] for t in d["tags"]}:
                res.add("FAIL", "pin", f"Tag `{src.ref}` existiert im Repository nicht (mehr).")
        gh = d["github"]
        if gh.get("status") != "ok":
            res.add("UNCHECKED", "github", f"GitHub-Metadaten nicht geprüft ({gh.get('status')}).")
        else:
            res.metrics.update(open_issues=gh.get("open_issues"), repo_license=gh.get("license"))
            if gh.get("archived"):
                res.add("FAIL", "maintenance", "Repository ist archiviert.")
            if gh.get("full_name") and gh["full_name"].lower() not in res.repo_url.lower():
                res.add("INFO", "repo", f"Repository wurde umbenannt/verschoben nach {gh['full_name']}.")
            for a in gh.get("advisories", []):
                ids = a["id"] + (f" / {a['cve']}" if a.get("cve") else "")
                self.vulnerability(res, f"GitHub-Advisory {ids} ({a.get('severity')}): "
                                        f"{a.get('summary')} - {a.get('url')}")

    # ---------------- cross-source checks ----------------
    def check_custom_coverage(self, commented):
        resolved = {r.component.rstrip("?") for r in self.results if r.source.kind != "directory"}
        for comp, note in commented.get("plugin_list", []):
            if comp not in resolved:
                self.gfind("WARN", "build-script",
                           f"`{comp}` ist in pluginList.sh als Sonderfall kommentiert, aber in "
                           f"downloadPlugins.sh wurde keine Quelle dafür erkannt.")

    def check_duplicates(self):
        by_comp: dict[str, list[PluginResult]] = {}
        for r in self.results:
            by_comp.setdefault(r.component, []).append(r)
        allowed = self.cfg.get("allowed_duplicates", {})
        for comp, rs in by_comp.items():
            if len(rs) < 2 or "?" in comp:
                continue
            desc = ", ".join(f"{r.source.kind}:{r.source.origin} ({r.version})" for r in rs)
            if comp not in allowed:
                self.gfind("FAIL", "duplicate", f"`{comp}` kommt aus mehreren Quellen: {desc}.")
                continue
            self.gfind("INFO", "duplicate", f"`{comp}` aus mehreren Quellen (gewollt: {allowed[comp]}): {desc}.")
            versions = [(int(float(r.version)), r) for r in rs if r.version and re.fullmatch(r"[\d.]+", r.version)]
            if len(versions) >= 2:
                lo, hi = min(versions, key=lambda x: x[0]), max(versions, key=lambda x: x[0])
                if lo[0] != hi[0]:
                    lo[1].add("WARN", "downgrade",
                              f"Version {lo[0]} ist kleiner als {hi[0]} aus Quelle {hi[1].source.kind}. Ein Wechsel "
                              f"von dort auf diese Quelle ist ein Downgrade, den Moodle verweigert; außerdem fehlen "
                              f"ihr womöglich Fixes der neueren Version.")

    # ---------------- CVEs ----------------
    def cve_terms(self, res):
        comp = res.component
        terms = {comp.lower()}
        plugin = comp.split("_", 1)[1] if "_" in comp else comp
        if len(plugin) >= self.cfg.get("cve_min_term_length", 5) and plugin not in self.cfg.get("cve_generic_terms", []):
            terms.add(plugin)
        name = res.metrics.get("directory_name")
        if name and len(norm_text(name)) >= 8:
            terms.add(name)
        if res.repo_url:
            terms.add(res.repo_url.rstrip("/").split("/")[-1])
        terms.update(self.cfg.get("cve_aliases", {}).get(comp, []))
        return {norm_text(t) for t in terms if norm_text(t)}

    def check_cves(self):
        base = os.path.join(self.args.cve_dir, "cves")
        if not os.path.isdir(base):
            raise RuntimeError(f"{base} fehlt")
        files = []
        r = subprocess.run(["grep", "-rlis", "moodle", base], capture_output=True, text=True, timeout=1800)
        files = [f for f in r.stdout.splitlines() if f.endswith(".json")]
        if not files:
            raise RuntimeError("keine Moodle-bezogenen CVE-Datensätze gefunden - Checkout unvollständig?")
        records = []
        for f in files:
            try:
                j = read_json(f)
            except Exception:
                continue
            cna = j.get("containers", {}).get("cna", {})
            meta = j.get("cveMetadata", {})
            if meta.get("state") == "REJECTED":
                continue
            desc = " ".join(d.get("value", "") for d in cna.get("descriptions", []))
            refs = [x.get("url", "") for x in cna.get("references", [])]
            affected = " ".join(f"{a.get('vendor', '')} {a.get('product', '')} {a.get('packageName', '')}"
                                for a in cna.get("affected", []))
            scores = [v.get("baseScore") for mt in cna.get("metrics", []) for v in mt.values()
                      if isinstance(v, dict) and "baseScore" in v]
            records.append({"id": meta.get("cveId"), "published": (meta.get("datePublished") or "")[:10],
                            "title": cna.get("title") or desc[:120], "norm": norm_text(
                                " ".join([cna.get("title", ""), desc, affected, " ".join(refs)])),
                            "score": max(scores) if scores else None, "refs": refs[:3]})
        self.gfind("INFO", "cve", f"{len(records)} Moodle-bezogene CVE-Datensätze abgeglichen.")
        for res in self.results:
            if "?" in res.component:
                continue
            terms = self.cve_terms(res)
            for rec in records:
                if any(t in rec["norm"] for t in terms):
                    score = f"CVSS {rec['score']}" if rec["score"] else "ohne CVSS"
                    self.vulnerability(res, f"{rec['id']} ({rec['published']}, {score}): {rec['title'][:160]}"
                                                f" - https://www.cve.org/CVERecord?id={rec['id']}")

    def vulnerability(self, res, text):
        res.add(self.cfg.get("unreviewed_vulnerability_severity", "FAIL"), "vulnerability",
                f"{text} - **unbewertet**: prüfen und in config.json unter ignored_findings eintragen.")

    # ---------------- bundled libraries via OSV ----------------
    def check_osv(self):
        mapping = [(re.compile(m["match"], re.I), m["ecosystem"], m["package"])
                   for m in self.cfg.get("library_map", [])]
        queries, owners = [], []

        def same_version(a, b):  # 1.15 and 1.15.0 are the same release
            a, b = ([int(x) for x in v.split(".") if x.isdigit()] for v in (a, b))
            size = max(len(a), len(b))
            return a + [0] * (size - len(a)) == b + [0] * (size - len(b))

        for res in self.results:
            unmapped, seen, declared = [], set(), {}
            for lib in res.metrics.get("libraries", []):
                hit = next(((eco, pkg) for rx, eco, pkg in mapping
                            if rx.search(lib["name"]) or rx.search(lib["location"])), None)
                ver = re.sub(r"^[vV]", "", lib["version"].strip())
                if not hit or not re.match(r"^\d+(\.\d+)*", ver):
                    entry = f"{lib['name'] or '(ohne Namen)'} ({lib['location'] or 'ohne Ortsangabe'})"
                    if entry not in unmapped:
                        unmapped.append(entry)
                    continue
                ver = re.match(r"^\d+(\.\d+)*", ver).group(0)
                declared.setdefault(hit, []).append(ver)
                if (hit, ver) in seen:  # e.g. pdf.js, pdf.worker.js, pdf_viewer.js = one package
                    continue
                seen.add((hit, ver))
                queries.append({"package": {"ecosystem": hit[0], "name": hit[1]}, "version": ver})
                owners.append((res, f"{lib['name']} {ver} ({hit[0]}:{hit[1]})"))
            # one finding per library, so that each can be put on the ignore list on its own
            for entry in unmapped:
                res.add("UNCHECKED", "libraries", f"Bibliothek ohne OSV-Zuordnung: {entry}")
            # Libraries found in the artifact itself. The same package and version as a declared
            # library is one query; a different version means thirdpartylibs.xml is wrong.
            undeclared, skew = [], []
            # shortest name first: "jQuery UI" labels the finding, not "jQuery UI Effects Blind"
            for lib in sorted(res.metrics.get("detected_libraries", []), key=lambda d: len(d["name"])):
                hit = (lib["ecosystem"], lib["package"]) if lib["package"] else next(
                    ((eco, pkg) for rx, eco, pkg in mapping if rx.search(lib["name"])), None)
                ver = lib["version"]
                if not hit or not ver:
                    entry = f"{lib['name']} {ver or '(Version unbekannt)'} ({lib['file']})"
                    if entry not in undeclared:
                        undeclared.append(entry)
                    continue
                if hit in declared and not any(same_version(ver, d) for d in declared[hit]):
                    entry = f"{hit[1]} {ver} in {lib['file']} (deklariert: {', '.join(sorted(set(declared[hit])))})"
                    if not any(e.startswith(f"{hit[1]} {ver} in ") for e in skew):
                        skew.append(entry)
                if any(h == hit and same_version(ver, v) for h, v in seen):
                    continue
                seen.add((hit, ver))
                queries.append({"package": {"ecosystem": hit[0], "name": hit[1]}, "version": ver})
                owners.append((res, f"{lib['name']} {ver} ({hit[0]}:{hit[1]}, nicht in thirdpartylibs.xml "
                                    f"deklariert, erkannt in {lib['file']})"))
            if skew:
                res.add("WARN", "libraries", "thirdpartylibs.xml nennt eine andere Version als das Artefakt enthält: " +
                        "; ".join(skew[:8]) + (" …" if len(skew) > 8 else ""))
            for entry in undeclared:
                res.add("UNCHECKED", "libraries", f"Nicht deklarierte Bibliothek ohne OSV-Zuordnung: {entry}")
        if not queries:
            return
        if self.args.offline:
            for res, label in owners:
                res.add("UNCHECKED", "libraries", f"{label}: OSV im Offline-Modus nicht abgefragt.")
            return
        try:
            results = []
            for i in range(0, len(queries), 500):
                body = json.dumps({"queries": queries[i:i + 500]}).encode()
                results += json.loads(http_get("https://api.osv.dev/v1/querybatch",
                                               {"Content-Type": "application/json"}, data=body))["results"]
        except Exception as e:
            for res, label in owners:
                res.add("UNCHECKED", "libraries", f"{label}: OSV-Abfrage fehlgeschlagen ({e}).")
            return
        for (res, label), r in zip(owners, results):
            vulns = r.get("vulns", [])
            if not vulns:
                res.add("OK", "libraries", f"{label}: keine bekannten Schwachstellen in OSV.")
                continue
            ids = [v["id"] for v in vulns]
            for vid in ids:
                self.vulnerability(res, f"{label} ist laut OSV betroffen von {vid} - https://osv.dev/vulnerability/{vid}")

    # ---------------- ignore list ----------------
    def apply_ignores(self):
        """Findings matching an entry in ignored_findings are downgraded to INFO; the reason stays visible."""
        rules = []
        for i, e in enumerate(self.cfg.get("ignored_findings", [])):
            # The final two conditions require a numeric fixed_version exactly when reason is
            # fixed; even an empty or malformed fixed_version is forbidden on other reasons.
            if not isinstance(e, dict) or not all(isinstance(e.get(k), str) and e[k].strip()
                                                  for k in ("component", "check", "note")) \
                    or e.get("reason") not in IGNORE_REASONS or not isinstance(e.get("match", ""), str) \
                    or (e["reason"] == "fixed") != bool(re.fullmatch(r"\d+", str(e.get("fixed_version", "")))) \
                    or ("fixed_version" in e) != (e["reason"] == "fixed"):
                self.gfind("FAIL", "ignore", f"ignored_findings[{i}] ist ungültig und wird nicht angewendet: "
                                             f"`component`, `check`, `note` und `reason` "
                                             f"({'/'.join(IGNORE_REASONS)}) sind Pflicht, bei `fixed` (und nur "
                                             f"dort) zusätzlich `fixed_version` als Moodle-Versionsnummer.")
                continue
            rules.append([e, 0])
        targets = [(r.component, r.version, f) for r in self.results for f in r.findings]
        targets += [("*", None, f) for f in self.global_findings]
        for component, version, f in targets:
            if SEV_RANK[f.severity] < SEV_RANK["UNCHECKED"]:
                continue
            for rule in rules:
                e = rule[0]
                if e["component"] == component and e["check"] == f.check and e.get("match", "") in f.message:
                    # A matching fixed rule is still in use when the shipped version is too old;
                    # count it before the version gate to avoid a misleading unused-rule warning.
                    rule[1] += 1
                    reason = IGNORE_REASONS[e["reason"]]
                    if e["reason"] == "fixed":
                        # only holds for shipped versions that contain the fix
                        reason += f" ab {e['fixed_version']}"
                        if not re.fullmatch(r"\d+", str(version or "")) or int(version) < int(e["fixed_version"]):
                            f.message += (f" Laut ignored_findings behoben erst ab {e['fixed_version']}, "
                                          f"ausgeliefert {version or '?'}. {e['note']}")
                            break
                    f.message = f"(ignoriert, war {f.severity} - {reason}: {e['note']}) {f.message}"
                    f.severity = "INFO"
                    break
        vulns_checked = not self.args.offline and "cve" not in self.unchecked
        for e, hits in rules:
            if not hits and (e["check"] != "vulnerability" or vulns_checked):
                match = f", match „{e['match']}“" if e.get("match") else ""
                self.gfind("WARN", "ignore", f"ignored_findings-Eintrag `{e['component']}` / `{e['check']}`{match} "
                                             f"trifft auf keinen Befund zu - Eintrag entfernen oder anpassen.")

    # ---------------- baseline (pull requests) ----------------
    @staticmethod
    def finding_key(component, f):
        # Baseline reports contain JSON dictionaries; current findings are dataclass instances.
        check_name = f["check"] if isinstance(f, dict) else f.check
        message = f["message"] if isinstance(f, dict) else f.message
        # Only elapsed age may drift without creating a new finding. Normalizing every number
        # would also collapse distinct CVE/GHSA IDs and affected package versions onto one key.
        if check_name == "maintenance":
            message = re.sub(r"(?<=vor )\d+(?= Tagen\b)", "#", message)
        elif check_name == "plugins.json":
            message = re.sub(r"(?<=ist )\d+(?= Tage alt\b)", "#", message)
        return (component, check_name, message)

    def apply_baseline(self, path):
        """Findings already present in the baseline report no longer fail the run.

        They are downgraded to INFO, except vulnerability and maintenance findings: those stay
        visible as WARN, because they need attention no matter which change introduced them.
        Internal failures are never downgraded and invalidate a baseline report.
        """
        base = read_json(path)
        base_findings = base.get("global_findings", []) + [
            f for plugin in base.get("plugins", []) for f in plugin["findings"]]
        if any(f["check"] == "internal" for f in base_findings):
            self.gfind("WARN", "baseline", "Basisbericht enthält interne Fehler und wird nicht verwendet "
                                          "- alle Befunde zählen voll.")
            return
        known = {self.finding_key(p["component"], f) for p in base.get("plugins", []) for f in p["findings"]}
        known |= {self.finding_key("*", f) for f in base.get("global_findings", [])}
        targets = [(r.component, f) for r in self.results for f in r.findings]
        targets += [("*", f) for f in self.global_findings]
        counts = {"INFO": 0, "WARN": 0}
        for component, f in targets:
            if f.check != "internal" and SEV_RANK[f.severity] >= SEV_RANK["WARN"] \
                    and self.finding_key(component, f) in known:
                f.severity = "WARN" if f.check in BASELINE_KEEP_WARN else "INFO"
                f.message = "(bereits im Basisstand) " + f.message
                counts[f.severity] += 1
        self.gfind("INFO", "baseline", f"{counts['INFO'] + counts['WARN']} Befunde bestanden schon im Basisstand: "
                                       f"{counts['WARN']} zu Schwachstellen und Wartung bleiben WARN, "
                                       f"{counts['INFO']} sind hier nur INFO.")

    # ---------------- reporting ----------------
    def overall(self):
        sev = [f.severity for f in self.global_findings] + [r.worst for r in self.results]
        return max(sev, key=lambda s: SEV_RANK[s]) if sev else "OK"

    def report_json(self):
        return {
            "generated": TODAY.isoformat(), "moodle_version": getattr(self, "moodle_version", None),
            "overall": self.overall(), "unchecked": self.unchecked,
            "global_findings": [f.as_dict() for f in self.global_findings],
            "plugins": [{"component": r.component, "source": r.source.kind, "origin": r.source.origin,
                         "ref": r.source.ref, "release": r.release, "version": r.version, "repo": r.repo_url,
                         "worst": r.worst, "metrics": {k: v for k, v in r.metrics.items()},
                         "findings": [f.as_dict() for f in r.findings]} for r in self.results],
        }

    def report_md(self):
        icon = {"OK": "✅", "INFO": "ℹ️", "UNCHECKED": "❔", "WARN": "⚠️", "FAIL": "❌"}
        L = [f"# Moodle-Plugin-Health-Check", "",
             f"Stand {TODAY:%Y-%m-%d %H:%M} UTC · Moodle {getattr(self, 'moodle_version', '?')} · "
             f"Gesamt: {icon[self.overall()]} **{self.overall()}**", ""]
        counts = {s: sum(1 for r in self.results if r.worst == s) for s in SEVERITIES}
        L.append(" · ".join(f"{icon[s]} {s}: {counts[s]}" for s in reversed(SEVERITIES) if counts[s]))
        L.append("")
        if self.global_findings:
            L += ["## Übergreifend", ""]
            for f in sorted(self.global_findings, key=lambda f: -SEV_RANK[f.severity]):
                L.append(f"- {icon[f.severity]} **{f.check}**: {f.message}")
            L.append("")
        if self.unchecked:
            L += ["## Nicht durchgeführte Prüfungen", ""]
            L += [f"- ❔ {k}: {v}" for k, v in self.unchecked.items()]
            L.append("")
        L += ["## Übersicht", "",
              "| Status | Plugin | Quelle | Version | Repo | Letzter Commit | Commits 12 M. | Releases 12 M. | Lizenz |",
              "|---|---|---|---|---|---|---|---|---|"]
        for r in sorted(self.results, key=lambda r: (-SEV_RANK[r.worst], r.component)):
            m = r.metrics
            src = r.source.kind + (f" `{r.source.ref}`" if r.source.ref and r.source.kind != "directory" else "")
            repo = f"[{r.repo_url.split('/', 3)[-1]}]({r.repo_url})" if r.repo_url else "-"
            L.append(f"| {icon[r.worst]} | `{r.component}` | {src} | {r.release or '-'} ({r.version or '?'}) | {repo} | "
                     f"{m.get('last_commit', '-')} | {m.get('commits_12m', '-')} | {m.get('release_tags_12m', '-')} | "
                     f"{m.get('license') or '-'} |")
        L.append("")
        L += ["## Befunde je Plugin", ""]
        for r in sorted(self.results, key=lambda r: (-SEV_RANK[r.worst], r.component)):
            shown = [f for f in r.findings if f.severity != "OK"]
            if not shown:
                continue
            L.append(f"### {icon[r.worst]} `{r.component}` ({r.source.kind}{', ' + r.source.origin if r.source.origin else ''})")
            for f in sorted(shown, key=lambda f: -SEV_RANK[f.severity]):
                L.append(f"- {icon[f.severity]} **{f.check}**: {f.message}")
            L.append("")
        L += ["---", "Legende: ❌ FAIL bricht den Lauf ab · ⚠️ WARN · ❔ UNCHECKED = Prüfung nicht möglich, "
              "**kein** Freibrief · ℹ️ INFO. Bewertete und bewusst ignorierte Befunde "
              "stehen in `moodle/scripts/ci/plugin_health/config.json` (ignored_findings)."]
        return "\n".join(L)


# --------------------------------------------------------------------------------------------
def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    here = os.path.dirname(os.path.abspath(__file__))
    ap.add_argument("--repo-root", default=os.path.abspath(os.path.join(here, "../../../..")))
    ap.add_argument("--config", default=os.path.join(here, "config.json"))
    ap.add_argument("--work-dir", default=os.path.join(os.getcwd(), ".plugin-health"))
    ap.add_argument("--moodle-version", help="überschreibt MOODLE_VERSION aus dem Dockerfile")
    ap.add_argument("--cve-dir", help="Checkout von CVEProject/cvelistV5 (Verzeichnis mit cves/)")
    ap.add_argument("--live-pluglist", action="store_true", help="plugins.json gegen das Live-Verzeichnis prüfen")
    ap.add_argument("--offline", action="store_true", help="nur git, keine HTTP-Abrufe (lokaler Test)")
    ap.add_argument("--no-bash-crosscheck", action="store_true")
    ap.add_argument("--download-delay", type=float, default=2.0)
    ap.add_argument("--report-md")
    ap.add_argument("--report-json")
    ap.add_argument("--fail-level", default=None, choices=SEVERITIES)
    ap.add_argument("--baseline", help="JSON-Bericht des Basisstands; dort schon vorhandene Befunde werden INFO "
                                     "(Schwachstellen und Wartung: WARN)")
    args = ap.parse_args(argv)

    config = read_json(args.config)
    checker = Checker(args, config)
    try:
        checker.run()
    except Exception as e:
        checker.gfind("FAIL", "internal", f"Abbruch: {type(e).__name__}: {e}")
    checker.apply_ignores()
    if args.baseline:
        try:
            checker.apply_baseline(args.baseline)
        except Exception as e:
            checker.gfind("WARN", "baseline", f"Basisbericht nicht lesbar ({e}) - alle Befunde zählen voll.")
    md = checker.report_md()
    if args.report_md:
        with open(args.report_md, "w", encoding="utf-8") as fh:
            fh.write(md)
    if args.report_json:
        with open(args.report_json, "w", encoding="utf-8") as fh:
            fh.write(json.dumps(checker.report_json(), indent=1, default=str))
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as fh:
            fh.write(md[:900_000] + "\n")
    print(md)
    fail_level = args.fail_level or config.get("fail_level", "FAIL")
    return 1 if SEV_RANK[checker.overall()] >= SEV_RANK[fail_level] else 0


if __name__ == "__main__":
    sys.exit(main())
