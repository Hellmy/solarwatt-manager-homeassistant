# Entwicklung der SOLARWATT-Manager-Integration

Diese Anleitung beschreibt den Entwicklungsablauf für die Integration: Home Assistant Core aus dem offiziellen Development Container starten und API-Änderungen zunächst mit lokalen, netzwerkunabhängigen Tests absichern.

## Voraussetzungen

Für die Entwicklungsumgebung benötigst du:

- Visual Studio Code mit der Erweiterung **Dev Containers**
- Docker
- Git

Die Dev-Container-Konfiguration in diesem Repository baut auf dem offiziellen Home-Assistant-Core-Development-Container auf.

Öffne dieses Repository in VS Code und wähle **Reopen in Container**. Beim ersten Start wird `home-assistant/core` im Nachbarordner `../home-assistant-core` geklont, der Container gebaut und Core eingerichtet. Der erste Start kann daher einige Minuten dauern. Der Checkout und die Core-Testkonfiguration bleiben außerhalb dieses Integrations-Repositories erhalten.

## Home Assistant starten

Nach dem Container-Setup ist die Integration automatisch mit der Core-Testinstanz verlinkt. In VS Code über **Tasks: Run Task** die Aufgabe **Run Home Assistant Core** starten und <http://localhost:8123> öffnen. Richte eine separate Testinstanz ein und füge die Integration über **Einstellungen → Geräte & Dienste → Integration hinzufügen** hinzu.

Die lokalen Integrationstests lassen sich über **Tasks: Run Task → Run Integration Tests** ausführen.

Änderungen an Python-Modulen benötigen in der Regel einen Neustart des laufenden Home Assistant Core. Verwende für Tests mit Portalzugang ein Testkonto und speichere keine Zugangsdaten, Tokens oder personenbezogenen API-Antworten im Repository.

## API erweitern

Die Datenquelle bestimmt den Einstiegspunkt:

| Bereich | Zuständigkeit |
| --- | --- |
| Lokale Manager-API und Umwandlung der HEMS-Konfigurator-Antworten | `custom_components/solarwatt_manager/hems_api.py` |
| KiwiGrid-HEMS-v12-Login, Endpunkte und Antwort-Mapping | `custom_components/solarwatt_manager/hems_client.py` |
| Abruf, Polling, Cache und Zusammenführung der Daten | `custom_components/solarwatt_manager/coordinator.py` |
| Sensoren und deren Home-Assistant-Metadaten | `custom_components/solarwatt_manager/sensor.py`, `sensor_meta.py` und `translations/` |

Für einen neuen Datenpunkt oder Endpunkt:

1. Prüfe, ob der Client bereits einen passenden Endpunkt oder Mapper anbietet.
2. Ergänze den Endpunkt im zuständigen Client. Netzwerkzugriffe bleiben asynchron und laufen über die vorhandene Session und Fehlerbehandlung.
3. Wandle die Antwort in die vorhandene interne Item-/Thing-Struktur um. Entitäten sollen keine eigenen HTTP-Aufrufe durchführen.
4. Binde den Abruf im Coordinator ein. Nutze dessen Polling und Cache, damit parallele Sensoren keinen doppelten API-Aufruf auslösen.
5. Ergänze bei neuen Entitäten passende Metadaten und Übersetzungen. Bestehende `unique_id`s und Entity-Namen nicht ohne zwingenden Grund ändern.
6. Schreibe Regressionstests für gültige, fehlende und fehlerhafte Antwortfelder.

## Lokal testen

Die API- und Mappingtests benötigen keinen laufenden Home Assistant und rufen keine echte SOLARWATT- oder KiwiGrid-API auf. Sie verwenden Testdaten und Fake-Clients beziehungsweise Fake-Sessions.

Das Projekt benötigt Python 3.13 oder neuer. Richte eine virtuelle Umgebung ein und installiere die Testextras:

```bash
python3.13 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[test]"
```

Gezielte Tests für die API:

```bash
pytest -q tests/test_hems_api.py
pytest -q tests/test_hems_client.py
pytest -q tests/test_coordinator.py
```

Die Testdateien decken unterschiedliche Ebenen ab:

- `tests/test_hems_api.py`: Umwandlung lokaler HEMS-Konfigurator-Daten und berechnete Energy-Overview-Werte
- `tests/test_hems_client.py`: KiwiGrid-Endpoint-Pfade, Parameter, Antwort-Mapping und Fehlerverhalten mit simulierten Antworten
- `tests/test_coordinator.py`: Einbindung in Polling, Cache und Coordinator-Snapshot

Vor dem Abschluss kannst du die gesamte Suite und die konfigurierten Qualitätsprüfungen starten:

```bash
pytest -q
ruff check custom_components/solarwatt_manager tests
mypy
```

## Wann brauche ich echte API-Daten?

Für die meisten Änderungen reichen anonymisierte Beispielantworten als Testdaten. Ein Live-Test in der HA-Testinstanz ist sinnvoll, wenn du beispielsweise Authentifizierung, ein neues Portalverhalten oder die tatsächliche Geräteerkennung überprüfst. Verwende dafür deine eigene Testinstanz und echte, lokal konfigurierte Zugangsdaten; übernimm keine Zugangsdaten oder Tokens in Quellcode, Logs oder Fixtures.
