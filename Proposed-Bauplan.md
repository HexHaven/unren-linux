# Bauplan — UnRen-forall Linux Fork

**Arbeitstitel:** `UnRen-forall-linux`
**Upstream:** `Lurmel/UnRen-forall`
**Lizenz:** GNU GPL v3 or later
**Primärplattform:** Native Linux
**Ziel:** Funktional weitgehend kompatibler, wartbarer Linux-Port von UnRen-forall ohne Windows-Batch-Abhängigkeit.

---

# 1. Ausgangslage

`UnRen-forall` ist derzeit primär als Windows-Batch-Toolkit aufgebaut.

Der Upstream stellt aktuell unter anderem bereit:

* `UnRen-forall.bat` als Launcher
* `UnRen-legacy.bat` für Ren'Py ≤ 7
* `UnRen-current.bat` für Ren'Py ≥ 8
* automatische Ren'Py-Versionserkennung
* RPA-Extraktion
* RPYC-Decompilation
* Unterstützung verschiedener Python-/Ren'Py-Generationen
* Konfiguration
* mehrsprachige Benutzeroberfläche
* Update-/Changelog-Handling

Der Upstream beschreibt explizit Support für Ren'Py 6, Ren'Py 7 sowie neuere Ren'Py-8-Versionen und enthält bereits Python-basierte interne Komponenten.

Weiterhin verwendet bzw. integriert das Projekt Werkzeuge beziehungsweise Logik rund um `rpatool` und `unrpyc`.

Der Linux-Port soll diese Funktionalität erhalten, aber die Windows-spezifische Batch-Orchestrierung vollständig aus dem eigentlichen Core entfernen.

---

# 2. Zielbild

Der Fork soll langfristig nicht wie folgt aussehen:

```text
UnRen-forall.bat
        ↓
UnRen-forall.sh
```

also als möglichst direkte Batch→Bash-Übersetzung.

Stattdessen:

```text
                    unren
                      │
                      ▼
              Linux CLI Launcher
                      │
                      ▼
              Python Application
                      │
          ┌───────────┼────────────┐
          ▼           ▼            ▼
      Detection     Actions      Config/UI
          │           │
          │      ┌────┴─────┐
          │      ▼          ▼
          │   rpatool     unrpyc
          │
          ▼
      Ren'Py Runtime
```

**Grundprinzip:**

> Python enthält die Programmlogik.
> Shell enthält höchstens Bootstrap- und Packaging-Logik.

Damit wird das Projekt leichter:

* testbar
* wartbar
* portierbar
* upstream-syncbar
* paketierbar
* erweiterbar

---

# 3. Projektziele

## MUST

Der Linux-Fork muss:

* native Linux-Ausführung unterstützen
* keine Wine-Abhängigkeit benötigen
* keine Windows-Batch-Ausführung benötigen
* Ren'Py-Spiele automatisch erkennen
* Ren'Py-Version beziehungsweise Runtime bestimmen
* Ren'Py 6/7 und 8+ soweit technisch möglich behandeln
* `.rpa`-Archive erkennen und extrahieren
* `.rpyc`-Dateien erkennen und dekompilieren
* eingebettete oder mitgelieferte Ren'Py-Python-Runtimes berücksichtigen
* Game-Verzeichnisse sicher erkennen
* Dateipfade mit Leerzeichen korrekt behandeln
* nicht destruktive Defaults verwenden
* Fehler verständlich melden
* GPL-Attribution und Lizenzierung des Upstreams erhalten

## SHOULD

Der Fork sollte:

* vollständig CLI-fähig sein
* interaktiven und non-interaktiven Betrieb unterstützen
* Bash, Zsh, Fish etc. unabhängig funktionieren
* auf Arch/CachyOS, Debian/Ubuntu und Fedora funktionieren
* weitgehend distribution-unabhängig sein
* einen `--dry-run` besitzen
* Backups beziehungsweise sichere Output-Pfade unterstützen
* maschinenlesbare Ausgabe ermöglichen
* reproduzierbare Tests besitzen
* Upstream-Änderungen regelmäßig übernehmen können

## COULD

Später:

* TUI
* Flatpak
* AppImage
* AUR-Paket
* `.deb`
* `.rpm`
* Nix package
* Desktop Entry
* Dateimanager-Integration
* Plugin-System

---

# 4. Nicht-Ziele

Version 1 soll ausdrücklich **nicht** versuchen:

* Wine als Voraussetzung einzubauen
* sämtliche Windows-spezifischen Features exakt nachzubilden
* ein GUI-Framework einzuführen
* Ren'Py selbst neu zu implementieren
* `rpatool` oder `unrpyc` unnötig zu forken
* alle Linux-Distributionen offiziell zu unterstützen
* Windows und Linux gleichzeitig aus einem neuen monolithischen Script zu bedienen

Der ursprüngliche Windows-Upstream bleibt Referenz für das Verhalten.

Der Linux-Fork implementiert dessen **Semantik**, nicht dessen Batch-Architektur.

---

# 5. Vorgeschlagene Repository-Struktur

```text
UnRen-forall-linux/
├── README.md
├── LICENSE
├── CHANGELOG.md
├── pyproject.toml
├── uv.lock
│
├── src/
│   └── unren/
│       ├── __init__.py
│       ├── __main__.py
│       ├── cli.py
│       │
│       ├── core/
│       │   ├── context.py
│       │   ├── paths.py
│       │   ├── config.py
│       │   ├── errors.py
│       │   └── result.py
│       │
│       ├── detection/
│       │   ├── game.py
│       │   ├── renpy.py
│       │   ├── python.py
│       │   └── archives.py
│       │
│       ├── actions/
│       │   ├── extract_rpa.py
│       │   ├── decompile_rpyc.py
│       │   ├── enable_console.py
│       │   ├── enable_devmode.py
│       │   └── cleanup.py
│       │
│       ├── adapters/
│       │   ├── rpatool.py
│       │   ├── unrpyc.py
│       │   └── renpy_runtime.py
│       │
│       ├── ui/
│       │   ├── interactive.py
│       │   ├── output.py
│       │   └── i18n.py
│       │
│       └── update/
│           └── upstream.py
│
├── vendor/
│   ├── README.md
│   └── licenses/
│
├── scripts/
│   └── unren
│
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── fixtures/
│   └── games/
│
├── packaging/
│   ├── arch/
│   ├── flatpak/
│   └── appimage/
│
└── docs/
    ├── ARCHITECTURE.md
    ├── UPSTREAM.md
    ├── PORTING.md
    └── COMPATIBILITY.md
```

---

# 6. Architekturentscheidung: Python als Core

## Entscheidung

Die neue Hauptimplementierung sollte Python sein.

Nicht Bash.

Bash darf lediglich einen optionalen Bootstrap-Wrapper darstellen:

```bash
#!/usr/bin/env bash
exec python3 -m unren "$@"
```

Später sollte selbst dieser Wrapper durch einen Python Package Entry Point ersetzt werden:

```toml
[project.scripts]
unren = "unren.cli:main"
```

Dadurch reicht:

```bash
unren
```

## Begründung

Der Upstream verwendet intern bereits Python-bezogene Mechanismen und erkennt verschiedene Python-Versionen.

Python löst außerdem mehrere Probleme, die ein Bash-Port nur verschieben würde:

* Dateipfadbehandlung
* semantische Versionsvergleiche
* strukturierte Konfiguration
* Unicode
* Tests
* subprocess management
* temporäre Dateien
* Archivoperationen
* Fehlerbehandlung
* JSON-Ausgabe
* Cross-Distro-Portabilität

---

# 7. CLI-Design

Vorgeschlagene Oberfläche:

```bash
unren [GLOBAL OPTIONS] COMMAND [OPTIONS]
```

Beispiele:

```bash
unren detect /path/to/game
```

```bash
unren extract /path/to/game
```

```bash
unren decompile /path/to/game
```

```bash
unren console enable /path/to/game
```

```bash
unren devmode enable /path/to/game
```

```bash
unren all /path/to/game
```

Ohne Subcommand:

```bash
unren /path/to/game
```

kann der interaktive Modus starten.

Globale Optionen:

```text
--dry-run
--verbose
--quiet
--json
--no-color
--backup
--output PATH
--config PATH
--language LANG
--version
--help
```

---

# 8. Game Detection

Die Erkennung darf nicht ausschließlich vom aktuellen Working Directory abhängen.

Der Detector sollte Indizien prüfen wie:

```text
game/
renpy/
lib/
*.sh
*.py
*.rpa
*.rpyc
```

und daraus einen strukturierten Kontext erzeugen:

```python
GameContext(
    root=...,
    game_dir=...,
    renpy_dir=...,
    runtime=...,
    renpy_version=...,
    python_version=...,
)
```

Wichtig:

**Detection führt niemals Veränderungen durch.**

Sie ist read-only.

---

# 9. Ren'Py-Versionserkennung

Die aktuelle Upstream-Trennung:

```text
Ren'Py <= 7  → legacy
Ren'Py >= 8  → current
```

soll semantisch erhalten bleiben. Der aktuelle README dokumentiert diese Aufteilung ausdrücklich.

Im neuen Core sollte daraus jedoch werden:

```python
class RenPyGeneration(Enum):
    LEGACY = "legacy"
    CURRENT = "current"
    UNKNOWN = "unknown"
```

Versionserkennung in Prioritätsreihenfolge:

1. Ren'Py-Metadaten
2. Runtime-Struktur
3. Python-Version der mitgelieferten Runtime
4. bekannte Library-Strukturen
5. heuristische Detection

Keine erkannte Version:

```text
UNKNOWN
```

statt blind eine Variante anzunehmen.

**Fail closed.**

---

# 10. Python Runtime Strategy

Eine der schwierigsten Stellen des Ports wird nicht Bash sein, sondern die Python-/Ren'Py-Kompatibilität.

Ren'Py-Generationen verwenden unterschiedliche Python-Versionen.

Deshalb brauchen wir einen Runtime Resolver:

```text
System Python
     │
     ├─ suitable → verwenden
     │
     └─ unsuitable
           │
           ▼
   Ren'Py bundled runtime
```

Der Resolver sollte dokumentieren:

```python
PythonRuntime(
    executable=...,
    version=...,
    source="system" | "renpy",
)
```

Nicht einfach:

```bash
python
```

oder:

```bash
python3
```

aufrufen und hoffen, dass die Dämonen gnädig sind.

---

# 11. RPA Extraction

RPA-Logik wird über einen Adapter abstrahiert:

```python
class RpaExtractor:
    def inspect(...)
    def extract(...)
```

Die konkrete Implementation kann vorhandenes `rpatool` benutzen.

Der Upstream integriert bereits `rpatool`-basierte Funktionalität.

Damit bleibt die Anwendung unabhängig davon, ob später:

* vendored `rpatool`
* systemweites `rpatool`
* Python-Modul
* eigener kompatibler Backend-Adapter

verwendet wird.

---

# 12. RPYC Decompilation

Analog:

```python
class RpycDecompiler:
    def inspect(...)
    def decompile(...)
```

Backend zunächst:

```text
unrpyc
```

Da der Upstream bereits aktiv unterschiedliche `unrpyc`-Generationen integriert beziehungsweise aktualisiert, sollte diese Abhängigkeit explizit versioniert werden.

Keine undokumentierten Vendor-Blobs.

Für jede vendorte Komponente:

```text
Name
Version
Upstream URL
Commit/Tag
Lizenz
lokale Patches
```

in:

```text
vendor/README.md
```

festhalten.

---

# 13. Konfiguration

Keine Shell-Dateien sourcen.

Stattdessen:

```text
~/.config/unren/config.toml
```

Beispiel:

```toml
language = "de"
backup = true
color = true
interactive = true

[extract]
overwrite = false

[decompile]
overwrite = false

[updates]
check = true
```

Alternativ projektlokal:

```text
.unren.toml
```

Priorität:

```text
CLI
 ↓
Project config
 ↓
User config
 ↓
Defaults
```

---

# 14. Sichere Dateimodifikation

Bei jeder verändernden Operation gelten folgende Regeln:

## Default

Vorhandene Quelldateien möglichst nicht überschreiben.

Beispiel:

```text
game/scripts.rpa
```

wird extrahiert nach:

```text
game/unren-extracted/
```

oder in einen explizit angegebenen Output-Pfad.

## Optional

```bash
unren extract --in-place
```

muss bewusst angefordert werden.

## Backup

Vor Änderungen:

```text
foo.rpy
→
foo.rpy.unren-backup
```

oder zentral:

```text
.unren/backups/<timestamp>/
```

---

# 15. Dry-Run

Pflichtfeature:

```bash
unren all --dry-run /games/foo
```

Ausgabe beispielsweise:

```text
Detected:
  Ren'Py: 8.3.4
  Python: 3.12
  Archives: 4
  RPYC files: 73

Would:
  extract archive.rpa
  extract scripts.rpa
  decompile 73 RPYC files

No files changed.
```

Das macht das Tool erheblich sicherer und erleichtert Debugging.

---

# 16. Interaktiver Modus

Der ursprüngliche Menücharakter darf erhalten bleiben.

Beispiel:

```text
UnRen for Linux

Game:
  /games/MyRenPyGame

Detected:
  Ren'Py 8.3
  Python 3.12

[1] Extract RPA archives
[2] Decompile RPYC files
[3] Enable developer mode
[4] Enable console
[5] Run all common operations
[6] Diagnostics
[Q] Quit
```

Aber:

> Menü und Core müssen voneinander getrennt sein.

Das Menü darf lediglich dieselben Commands aufrufen, die auch direkt über CLI verfügbar sind.

---

# 17. Internationalisierung

Die Übersetzungen aus dem bisherigen Batchcode sollten nicht einfach in Python-Variablen übertragen werden.

Stattdessen:

```text
locales/
├── de.json
├── en.json
├── es.json
├── fr.json
├── it.json
├── ru.json
└── zh.json
```

Beispiel:

```json
{
  "detect.python": "Python-Installation wird geprüft",
  "extract.start": "Archive werden extrahiert"
}
```

Fallback:

```text
requested language
      ↓
English
```

Keine fehlende Übersetzung darf die Anwendung abbrechen.

---

# 18. Diagnostics

Neuer Command:

```bash
unren doctor /path/to/game
```

Beispiel:

```text
UnRen Diagnostics

OS:
  Linux 6.18
  x86_64

Game:
  Valid Ren'Py layout

Ren'Py:
  8.3.4

Python:
  bundled: 3.12.4
  system:  3.13.5

Tools:
  rpatool: available
  unrpyc: compatible

Permissions:
  game/: writable

Result:
  READY
```

Maschinenlesbar:

```bash
unren doctor --json
```

---

# 19. Logging

Normale CLI-Ausgabe:

```text
INFO
WARNING
ERROR
```

Debug:

```bash
unren --verbose ...
```

Keine absoluten User-Pfade oder sonstige potentiell sensible lokale Informationen ungefragt in Telemetrie senden.

Idealerweise:

> überhaupt keine Telemetrie.

---

# 20. Dependency Strategy

Der Core sollte möglichst wenige externe Python-Abhängigkeiten besitzen.

Kandidaten:

```text
Python >= 3.10
```

Optional:

```text
platformdirs
rich
```

CLI möglichst Standardbibliothek oder leichtgewichtig.

Nicht direkt ein Framework-Monster heraufbeschwören, nur damit drei Menüpunkte lila funkeln.

---

# 21. Packaging

## Phase 1

```bash
pipx install .
```

beziehungsweise:

```bash
uv tool install .
```

## Phase 2

Arch Linux:

```text
PKGBUILD
```

Ziel:

```bash
paru -S unren-forall-linux
```

oder zunächst:

```bash
paru -S unren-forall-linux-git
```

## Phase 3

AppImage beziehungsweise Flatpak nur wenn echter Bedarf besteht.

Für ein CLI-Werkzeug ist ein normales Python-/Distribution-Paket zunächst deutlich sauberer.

---

# 22. Linux-Supportmatrix

Initial offiziell testen:

| Distribution         | Status       |
| -------------------- | ------------ |
| Arch Linux / CachyOS | Tier 1       |
| Debian Stable        | Tier 1       |
| Ubuntu LTS           | Tier 1       |
| Fedora               | Tier 1       |
| openSUSE             | Tier 2       |
| NixOS                | Tier 2       |
| Alpine               | Experimental |

Arch/CachyOS darf primärer Entwicklungs-Host sein.

Tests dürfen aber nicht davon ausgehen, dass:

```text
pacman
bash
GNU readlink
GNU sed
```

immer vorhanden sind.

Python übernimmt deshalb die Portabilitätsschicht.

---

# 23. Teststrategie

## Unit Tests

Testen:

* Version Parsing
* Game Detection
* Python Runtime Detection
* Ren'Py Generation Detection
* Config Loading
* Path Handling
* Backup Logic
* RPA Detection
* RPYC Detection

## Fixture Tests

Synthetic games:

```text
tests/fixtures/
├── renpy6/
├── renpy7/
├── renpy8/
├── renpy8-python312/
├── malformed/
└── empty/
```

Keine urheberrechtlich problematischen echten Spiele in das Repository übernehmen.

## Integration Tests

Kommandos:

```bash
unren detect
unren doctor
unren extract
unren decompile
```

gegen minimale Testprojekte ausführen.

---

# 24. CI

GitHub Actions:

```text
lint
typecheck
unit-test
integration-test
package-build
```

Matrix beispielsweise:

```text
ubuntu-latest
Python 3.10
Python 3.11
Python 3.12
Python 3.13
```

Zusätzliche Container-Tests:

```text
debian
fedora
archlinux
```

---

# 25. Upstream-Synchronisation

Der Fork sollte seine Herkunft technisch sichtbar behalten.

Remotes:

```bash
origin    <Linux-Fork>
upstream  https://github.com/Lurmel/UnRen-forall.git
```

Dokument:

```text
docs/UPSTREAM.md
```

enthält:

```text
Last reviewed upstream commit:
Upstream version:
Port version:
Known behavioral differences:
Pending upstream changes:
```

Wichtig:

Nicht versuchen, Batch-Dateien automatisch zu mergen.

Stattdessen Änderungen semantisch klassifizieren:

```text
upstream change
       │
       ├─ UI-only
       ├─ translation
       ├─ detection logic
       ├─ rpatool update
       ├─ unrpyc update
       ├─ Ren'Py compatibility
       └─ Windows-only
```

Nur relevante Änderungen werden in die Linux-Implementation übertragen.

---

# 26. Versionierung

Linux-Fork unabhängig versionieren:

```text
1.0.0
```

Zusätzlich festhalten:

```text
Based on UnRen-forall 0.77
Legacy compatibility baseline 9.7.60
Current compatibility baseline 9.7.80
```

Die Upstream-Versionen sollten nicht als eigene Linux-Version missbraucht werden.

---

# 27. Lizenz und Attribution

Der Upstream verwendet GNU GPL Version 3 oder später.

Der Fork muss entsprechend:

* GPL-kompatibel bleiben
* LICENSE beibehalten
* Copyright-Vermerke erhalten
* eigene Änderungen kenntlich machen
* Source Code verfügbar halten
* Lizenzen vendorter Komponenten dokumentieren

README:

```text
UnRen-forall-linux is a Linux-focused fork/port of
Lurmel/UnRen-forall.

Original project:
https://github.com/Lurmel/UnRen-forall

Original author:
JoeLurmel

This project is distributed under the GNU GPL v3 or later.
```

---

# 28. Sicherheitsgrenze

Das Tool bearbeitet ausschließlich vom Benutzer angegebene lokale Dateien.

Keine Mechanismen einführen für:

* DRM-Umgehung
* automatische Beschaffung geschützter Inhalte
* Remote-Downloads von Spielressourcen
* automatisches Patchen unbekannter Binaries

Wie beim Upstream sollte klar dokumentiert bleiben, dass Modifikation beziehungsweise Extraktion nur dort erfolgen soll, wo der Benutzer dazu berechtigt ist.

---

# 29. Milestone 0 — Upstream Archaeology

**Ziel:** Verhalten vollständig verstehen, bevor portiert wird.

Aufgaben:

* `UnRen-forall.bat` analysieren
* `UnRen-legacy.bat` analysieren
* `UnRen-current.bat` analysieren
* eingebettete Python-Skripte extrahieren
* alle Commands inventarisieren
* alle externen Tools inventarisieren
* alle Environment-Variablen inventarisieren
* Legacy-/Current-Unterschiede dokumentieren
* sämtliche Windows-spezifischen Mechanismen markieren

Ergebnis:

```text
docs/UPSTREAM-BEHAVIOR.md
```

mit Matrix:

```text
Feature
Windows implementation
Linux replacement
Portable core?
Priority
Test available?
```

**Exit Criterion:**

Jedes relevante Upstream-Feature ist klassifiziert.

---

# 30. Milestone 1 — Linux Core Skeleton

Implementieren:

```text
Python package
CLI
GameContext
Path handling
Config
Logging
Errors
Detection
```

Commands:

```bash
unren --version
unren detect
unren doctor
```

Noch keine Dateiveränderungen.

**Exit Criterion:**

Mindestens Ren'Py-6/7/8-Testfixtures werden zuverlässig erkannt.

---

# 31. Milestone 2 — RPA Extraction

Implementieren:

```text
RPA discovery
rpatool adapter
Output management
Overwrite protection
Backup logic
dry-run
```

Tests:

```text
RPA v2
RPA v3
multiple archives
spaces in paths
Unicode paths
read-only source
```

**Exit Criterion:**

RPA-Extraktion ist funktional und reproduzierbar getestet.

---

# 32. Milestone 3 — RPYC Decompilation

Implementieren:

```text
RPYC discovery
unrpyc adapter
runtime selection
Ren'Py generation compatibility
output handling
dry-run
```

Besonderes Augenmerk:

```text
Python 2-era Ren'Py
Python 3-era Ren'Py
Python 3.12-era Ren'Py
```

**Exit Criterion:**

Legacy und Current besitzen dokumentierte, getestete Decompilation Paths.

---

# 33. Milestone 4 — Remaining UnRen Features

Portiere alle verbleibenden Upstream-Funktionen einzeln.

Für jedes Feature:

```text
OBSERVE
→ SPECIFY
→ IMPLEMENT
→ TEST
→ COMPARE
```

Keine Feature-Portierung ausschließlich anhand des Namens.

Immer das tatsächliche Batch-Verhalten untersuchen.

---

# 34. Milestone 5 — Interactive UI + i18n

Implementieren:

* interaktives Menü
* Übersetzungsdateien
* Language Detection
* Fallback
* Farbausgabe
* `NO_COLOR`
* non-interactive parity

**Exit Criterion:**

Jede Aktion kann sowohl über Menü als auch CLI ausgeführt werden.

---

# 35. Milestone 6 — Packaging

Bereitstellen:

```text
pipx
uv tool
Arch PKGBUILD
```

Optional danach:

```text
AUR
AppImage
Flatpak
```

**Exit Criterion:**

Fresh installation → `unren doctor` funktioniert ohne manuelle Repo-Manipulation.

---

# 36. Milestone 7 — Release Candidate

Testmatrix:

```text
Ren'Py 6
Ren'Py 7
Ren'Py 8
Ren'Py 8 + Python 3.12

Arch
Debian
Ubuntu
Fedora
```

Zusätzlich:

```text
paths with spaces
Unicode filenames
read-only filesystem
missing Python
missing backend
corrupt RPA
corrupt RPYC
unknown Ren'Py
```

Release erst bei deterministischem Fehlerverhalten.

---

# 37. Milestone 8 — Upstream Tracking

Automatisierter GitHub-Workflow:

```text
weekly
```

prüft:

```text
Lurmel/UnRen-forall main
```

auf neue Commits beziehungsweise Releases.

Er soll **nicht automatisch Code übernehmen**.

Nur Issue erzeugen:

```text
Upstream update detected

Previous:
<sha>

Current:
<sha>

Changed files:
...

Requires compatibility review.
```

Damit bleibt der Linux-Fork synchronisierbar, ohne Batch-Änderungen blind einzuschleusen.

---

# 38. Definition of Done für v1.0

`UnRen-forall-linux 1.0` gilt als fertig, wenn:

* [ ] vollständig native Linux-Ausführung
* [ ] kein Wine
* [ ] keine `.bat`-Runtime-Abhängigkeit
* [ ] Game Detection
* [ ] Ren'Py Generation Detection
* [ ] Python Runtime Detection
* [ ] RPA Extraction
* [ ] RPYC Decompilation
* [ ] relevante übrige Upstream-Funktionen
* [ ] Legacy Ren'Py Support dokumentiert
* [ ] Current Ren'Py Support dokumentiert
* [ ] `--dry-run`
* [ ] Backup-/Overwrite-Schutz
* [ ] interaktiver Modus
* [ ] non-interaktive CLI
* [ ] deutsche und englische Übersetzung
* [ ] übrige Upstream-Sprachen soweit sinnvoll übernommen
* [ ] `unren doctor`
* [ ] Unit Tests
* [ ] Integration Tests
* [ ] CI
* [ ] Arch/CachyOS getestet
* [ ] Debian/Ubuntu getestet
* [ ] Fedora getestet
* [ ] GPL-Attribution korrekt
* [ ] Third-Party-Lizenzen dokumentiert
* [ ] Upstream-Sync-Prozess dokumentiert

---

# 39. Empfohlener Entwicklungsgrundsatz

Die wichtigste Architekturregel des Forks lautet:

> **Port behavior, not Batch code.**

`UnRen-forall` bleibt die funktionale Referenz.

Die Windows-spezifische Implementierung wird jedoch nicht zum Fundament des Linux-Ports.

Statt:

```text
BAT
 ↓
Bash
```

bauen wir:

```text
Upstream behavior
       │
       ▼
Portable specification
       │
       ▼
Python Core
       │
   ┌───┴────┐
   ▼        ▼
Linux CLI   Interactive UI
```

Damit entsteht aus dem ursprünglichen Windows-Script ein tatsächlich wartbares Linux-Tool, statt eines zweiten Betriebssystem-Skriptes, dessen 300-Kilobyte-Bash-Dämon irgendwann bei Vollmond gepflegt werden muss.

---

# 40. Empfohlene erste Umsetzung

Die konkrete Arbeit sollte mit **Milestone 0** beginnen.

Noch bevor Code geschrieben wird:

1. kompletten `UnRen-forall.bat` untersuchen,
2. `UnRen-legacy.bat` und `UnRen-current.bat` vergleichen,
3. eingebettete Python-Komponenten identifizieren,
4. alle verfügbaren Aktionen extrahieren,
5. externe Projekte und deren Versionen identifizieren,
6. Windows-spezifische und portable Teile trennen,
7. daraus eine Feature-/Parity-Matrix erstellen.

Erst diese Matrix wird zur kanonischen Spezifikation des Linux-Forks.

Damit basiert der Port auf beobachtetem Upstream-Verhalten statt auf Annahmen.
