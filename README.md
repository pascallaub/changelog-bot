# AI-Powered Changelog & README Generator

Dieses Projekt implementiert einen GitHub Action Workflow, der automatisch einen Changelog (`CHANGELOG.md`) und optional eine initiale README-Datei (`README.md`) für dein Repository generiert, indem es die Commit-Nachrichten mithilfe der OpenAI API analysiert.

## Features

*   **Automatisierte Changelog-Generierung:** Erstellt bei jedem Push zum `main`-Branch einen neuen Eintrag im `CHANGELOG.md`.
*   **AI-Zusammenfassung:** Nutzt OpenAI (GPT-4), um aus Commit-Nachrichten verständliche Changelog-Einträge zu formulieren.
*   **Intelligente Commit-Analyse:** Fokussiert sich auf relevante Änderungen und versucht, generische Merge-Commits zu ignorieren.
*   **Automatische README-Generierung:** Erstellt eine initiale `README.md`, falls noch keine vorhanden ist, basierend auf der Projektstruktur (via `readmeAI.py`).
*   **Automatisches Committen & Pushen:** Die generierten oder aktualisierten Dateien (`CHANGELOG.md`, `README.md`) werden automatisch zurück ins Repository gepusht.
*   **Einfache Integration:** Kann als GitHub Action in anderen Repositories verwendet werden.

## Wie es funktioniert

1.  **Trigger:** Der Workflow wird durch einen `push`-Event auf den `main`-Branch ausgelöst.
2.  **Checkout:** Der Code des Repositories wird ausgecheckt.
3.  **Setup:** Python wird eingerichtet und die benötigten Abhängigkeiten (`openai`, `gitpython`) werden installiert.
4.  **Changelog-Generierung (`changelogAI.py`):**
    *   Das Skript analysiert die Commits, die seit dem letzten Push hinzugekommen sind.
    *   Die relevanten Commit-Nachrichten werden extrahiert.
    *   Ein Prompt wird an die OpenAI API gesendet, um einen zusammenfassenden Changelog-Eintrag zu erstellen.
    *   Der generierte Eintrag wird an den Anfang der `CHANGELOG.md`-Datei geschrieben.
5.  **README-Generierung (`readmeAI.py`):**
    *   Dieses Skript wird nur ausgeführt, wenn noch keine `README.md` im Repository existiert.
    *   Es analysiert die Projektstruktur.
    *   Ein Prompt wird an die OpenAI API gesendet, um eine initiale README-Datei zu erstellen.
    *   Die generierte `README.md` wird im Repository gespeichert.
6.  **Commit & Push:**
    *   Die geänderten oder neu erstellten Dateien (`CHANGELOG.md`, `README.md`) werden committet.
    *   Der Commit wird zurück in den `main`-Branch des Repositories gepusht.

## Setup in deinem Repository

1.  **Workflow-Datei:** Erstelle eine Workflow-Datei unter `.github/workflows/changelogAI.yaml` (oder einem ähnlichen Namen) und kopiere den Inhalt der `changelogAI.yaml` aus diesem Projekt hinein.
2.  **Skripte:** Erstelle das Verzeichnis `.github/scripts/` und kopiere die Python-Skripte (`changelogAI.py`, `readmeAI.py`) aus diesem Projekt dorthin.
3.  **Secrets:**
    *   Gehe zu `Settings` > `Secrets and variables` > `Actions` in deinem Repository.
    *   Erstelle ein neues Repository-Secret namens `OPENAI_API_KEY` und füge deinen OpenAI API-Schlüssel ein.
    *   Das `GITHUB_TOKEN` wird normalerweise automatisch von GitHub Actions bereitgestellt, stelle aber sicher, dass der Workflow die nötigen Berechtigungen hat (siehe Punkt 4).
4.  **Berechtigungen:** Stelle sicher, dass der Workflow Schreibberechtigungen für den Repository-Inhalt hat. Füge dazu den `permissions`-Block in deine Workflow-Datei ein:
    ```yaml
    permissions:
      contents: write
    ```
5.  **Anpassungen (Optional):**
    *   Passe die Python-Version, den OpenAI-Modellnamen (`gpt-4`) oder die Logik zur Commit-Filterung in den Python-Skripten nach Bedarf an.
    *   Ändere den Branch-Namen (`main`) im `on:`-Trigger, falls du einen anderen Hauptbranch verwendest.

## Beitrag

Vorschläge und Beiträge sind willkommen! Bitte erstelle ein Issue oder einen Pull Request, um Änderungen zu diskutieren oder einzureichen.
