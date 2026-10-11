# Moodle-Plugin-Health-Check

Prüft jede Woche (und bei PRs, die die Plugin-Liste ändern) alle Plugins, die das Image ausliefert.
Workflow: `.github/workflows/plugin-health-check.yaml`. Ergebnis: Job-Zusammenfassung, Artefakt
`plugin-health-report` (Markdown + JSON) und bei geplanten Läufen ein Issue mit Label `plugin-health`.

## Was geprüft wird

| Bereich | Quelle | Stufe bei Problem |
|---|---|---|
| Plugin fehlt in `plugins.json`, keine Version für die Moodle-Version | `pluginList.sh`, `plugins.json`, `Dockerfile` | FAIL |
| MD5 des Downloads passt nicht zu `plugins.json` | Moodle-Verzeichnis | FAIL |
| Artefakt enthält anderes Plugin als erwartet | `version.php` im ausgelieferten ZIP | FAIL |
| Versionsnummer in der Zukunft | `version.php` | WARN |
| Keine GPL-Kopfzeile | `version.php` | WARN |
| Repo archiviert / kein Commit seit 2 Jahren | Git, GitHub-API | FAIL |
| Kein Commit / kein Release seit 1 Jahr | Git, Verzeichnis | WARN |
| Pin auf Branch statt Tag; neuerer Tag in derselben Release-Linie; Tag existiert nicht | `downloadPlugins.sh` + Git | WARN / WARN / FAIL |
| Neuere Version im Live-Verzeichnis als in `plugins.json` | download.moodle.org | WARN |
| Gleiches Plugin aus zwei Quellen; Versions-Downgrade zwischen ihnen | alle Quellen | FAIL / WARN |
| CVE nennt das Plugin | CVEProject/cvelistV5 | FAIL bis bewertet |
| Veröffentlichtes GitHub-Security-Advisory | GitHub-API | FAIL bis bewertet |
| Gebündelte Bibliothek mit bekannter Lücke | `thirdpartylibs.xml` + OSV | FAIL bis bewertet |

Alles, was nicht geprüft werden konnte (Netzwerk, Bitbucket, Bibliothek ohne OSV-Zuordnung …),
steht als **UNCHECKED** im Bericht. UNCHECKED ist kein Erfolg.

## Bei einem Befund

* **CVE / Advisory / OSV-Treffer:** prüfen. Trifft die Lücke zu, bleibt der Befund FAIL, bis das Plugin
  aktualisiert oder entfernt ist. Sonst Eintrag in `ignored_findings` mit `check: "vulnerability"` und
  der CVE-/GHSA-ID als `match`.
* **Alle anderen Befunde** (veraltetes Plugin, Branch-Pin, Lizenz, Duplikat …), die bewusst bleiben
  sollen: ebenfalls Eintrag in `ignored_findings`.
* **Fehlalarm beim CVE-Abgleich durch zu allgemeinen Namen:** Begriff in `cve_generic_terms`.

### Befunde ignorieren

```json
"ignored_findings": [
  {
    "component": "mod_beispiel",
    "check": "maintenance",
    "match": "Letzter Commit",
    "reason": "risk_accepted",
    "note": "Stabil, kein Ersatz verfügbar. Abgestimmt mit … am 2026-10-11."
  },
  {
    "component": "mod_beispiel",
    "check": "vulnerability",
    "match": "CVE-2026-12345",
    "reason": "fixed",
    "fixed_version": "2026010100",
    "note": "Behoben in Release 4.5.2, siehe Upstream-Commit …"
  }
]
```

* `component` und `check` stehen so im Bericht (`### mod_beispiel`, **maintenance**). Für Befunde aus
  „Übergreifend“ ist `component` `*`.
* `match` (optional) ist ein Textausschnitt der Meldung und grenzt ein, wenn ein Plugin mehrere Befunde
  desselben Checks hat. Keine Zahlen verwenden, die sich ändern („vor 800 Tagen“).
* `reason`: `risk_accepted` (Risiko akzeptiert), `mitigated` (anderweitig mitigiert),
  `false_positive` (auch: nicht betroffen) oder `fixed`. `note` ist Pflicht.
* `fixed_version` (Pflicht bei `fixed`, sonst nicht erlaubt) ist die Versionsnummer aus `version.php`,
  ab der der Fix enthalten ist. Der Befund wird nur ignoriert, solange die ausgelieferte Version
  mindestens so hoch ist; bei älterer oder unbekannter Version bleibt er bestehen.

Ignorierte Befunde werden INFO und bleiben mit ursprünglicher Stufe, Grund und `note` im Bericht.
Ein Eintrag, der auf keinen Befund mehr zutrifft, wird als WARN gemeldet (für `vulnerability` nur,
wenn der CVE-Abgleich gelaufen ist); ein ungültiger Eintrag ist FAIL.

In PRs zählen nur **neue** Befunde: Der Basisstand des Ziel-Branches wird mitgeprüft, dort schon
vorhandene Befunde erscheinen als INFO.

## Lokal ausführen

```bash
python -m unittest discover -s moodle/scripts/ci/plugin_health -p 'test_*.py'
python moodle/scripts/ci/plugin_health/check.py --offline --report-md /tmp/report.md   # nur Git
GITHUB_TOKEN=$(gh auth token) python moodle/scripts/ci/plugin_health/check.py \
  --cve-dir /pfad/zu/cvelistV5 --live-pluglist --report-md /tmp/report.md             # vollständig
```

## Grenzen

* Sonderfälle in `downloadPlugins.sh` werden statisch erkannt (git clone + `target_tag`/`target_branch`,
  GitHub-Archive, Marketplace-URLs, `download_github_release`). Neue Muster dort ergeben eine WARN
  „keine Quelle erkannt“ – dann Parser erweitern.
* Der CVE-Abgleich ist textbasiert (Komponentenname, Plugin-Name, Repo-Name, Aliase). Er findet
  Kandidaten, keine Gewissheit; deshalb die Pflicht zur Bewertung.
* Die Versionen in `thirdpartylibs.xml` sind Herstellerangaben und können falsch sein.
* Bitbucket-Repos (`format_tiles`) erhalten keine GitHub-Metadaten.
