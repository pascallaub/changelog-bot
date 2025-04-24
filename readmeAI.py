import subprocess
import os
from openai import OpenAI

# --- OpenRouter Client Initialisierung ---
try:
    # Verwende OpenRouter Base URL und API Key
    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=os.getenv("OPENROUTER_API_KEY") # Stelle sicher, dass dies im Workflow gesetzt ist
    )
    if not client.api_key:
        raise ValueError("OpenRouter API Key nicht gefunden. Stelle sicher, dass das OPENROUTER_API_KEY Secret im Workflow gesetzt ist.")
except Exception as e:
    print(f"Fehler beim Initialisieren des OpenRouter Clients: {e}")
    exit(1)


def run(cmd):
    try:
        # Füge stderr=subprocess.PIPE hinzu, um Fehler besser abzufangen
        return subprocess.check_output(cmd, shell=True, text=True, stderr=subprocess.PIPE).strip()
    except subprocess.CalledProcessError as e:
        # Gib den Fehler aus, aber fahre fort (z.B. wenn 'tree' nicht gefunden wird)
        print(f"Fehler beim Ausführen von '{cmd}': {e.stderr}")
        return f"Fehler beim Ausführen von '{cmd}'" # Gib eine Fehlermeldung zurück

def ask_openai(prompt: str) -> str:
    if not prompt or "Fehler beim Ausführen" in prompt: # Prüfe auch auf Fehler von run()
        print("OpenRouter Prompt ist leer oder enthält Fehler. Überspringe Anfrage.")
        return "Keine ausreichenden Projektinformationen für README gefunden."
    try:
        # Wähle Modell und setze Token-Limit
        model_to_use = "openai/gpt-4" # Oder ein anderes verfügbares Modell
        max_tokens_limit = 1000 # Passe dies nach Bedarf und Budget an (unter deinem Credit-Limit)

        print(f"Sende Prompt an OpenRouter (Modell: {model_to_use}, max_tokens: {max_tokens_limit})...")
        response = client.chat.completions.create(
            model=model_to_use,
            messages=[
                {"role": "system", "content": "Du bist ein erfahrener Softwareentwickler. Schreibe eine ausführliche README-Datei für ein GitHub-Projekt. Erkläre Ziel, Installation, Aufbau, Features und wie man beitragen kann."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.5,
            max_tokens=max_tokens_limit # Füge das Token-Limit hinzu
        )

        # Verbesserte Fehlerprüfung
        if response and response.choices and len(response.choices) > 0 and response.choices[0].message:
            print("Erfolgreiche Antwort von OpenRouter erhalten.")
            return response.choices[0].message.content.strip()
        elif response and hasattr(response, 'error') and response.error and 'code' in response.error and response.error['code'] == 402:
             error_message = response.error.get('message', 'Unbekannter Credit-Fehler')
             print(f"OpenRouter Fehler (Code 402 - Insufficient Credits): {error_message}")
             return f"Fehler: Nicht genügend OpenRouter Credits. ({error_message})"
        else:
            print(f"Unerwartete Antwortstruktur von OpenRouter erhalten: {response}")
            return "Fehler: Unerwartete Antwortstruktur von OpenRouter."

    except Exception as e:
        print(f"Fehler bei der OpenRouter-Anfrage: {e}")
        return f"Fehler bei der Generierung des README-Inhalts: {e}"

def get_project_overview():
    # Verwende 'git ls-files' für eine robustere Dateiliste
    # Ignoriere bestimmte Verzeichnisse/Dateien für eine sauberere Übersicht
    print("Sammle Projektstruktur mit 'tree'...")
    structure = run("tree -L 2 --dirsfirst -I '.git|node_modules|__pycache__|dist|build|venv'")
    print("Sammle Dateiliste mit 'git ls-files'...")
    files = run("git ls-files") # Zeigt nur versionierte Dateien an
    if "Fehler beim Ausführen" in structure or "Fehler beim Ausführen" in files:
         return "Fehler beim Sammeln der Projektübersicht."
    return f"Projektstruktur (bis Tiefe 2):\n```\n{structure}\n```\n\nVersionierte Dateien:\n```\n{files}\n```"

def write_readme(content: str):
    try:
        with open("README.md", "w", encoding='utf-8') as f: # Füge encoding hinzu
            f.write(content)
        print("README.md erfolgreich geschrieben.")
    except IOError as e:
        print(f"Fehler beim Schreiben der README.md: {e}")
        raise # Wirf den Fehler weiter, damit der Workflow fehlschlägt

def main():
    print("Sammle Projektübersicht...")
    context = get_project_overview()

    # Verbesserter Prompt für README
    prompt = f"""
Erstelle eine umfassende README.md-Datei für das folgende Projekt.
Die Datei sollte klar strukturiert sein und typische Abschnitte enthalten:
- **Projektname und Kurzbeschreibung:** Was ist das Ziel des Projekts?
- **Features:** Was kann das Projekt? Liste die Hauptfunktionen auf.
- **Projektstruktur:** Eine kurze Erklärung der wichtigsten Ordner und Dateien (basierend auf der untenstehenden Übersicht).
- **Technologie-Stack:** Welche Haupttechnologien werden verwendet (z.B. React, Node.js, Python, AWS DynamoDB)? Leite dies ggf. aus den Dateiendungen ab.
- **Installation / Setup:** Wie kann jemand das Projekt lokal zum Laufen bringen? (Gib allgemeine Schritte an, falls spezifische Details fehlen, z.B. 'npm install', 'pip install -r requirements.txt').
- **Verwendung:** Wie wird das Projekt genutzt? Gibt es Beispielbefehle? (z.B. 'npm start', 'python app.py').
- **Beitragen:** Wie können andere zum Projekt beitragen? (Standardhinweis auf Issues/PRs).
- **Lizenz:** (Optional, z.B. MIT).

Hier ist die Projektübersicht:
{context}

Schreibe die README im Markdown-Format. Sei präzise und informativ.
"""
    print("Generiere README.md mit OpenRouter...")
    content = ask_openai(prompt)

    # Verbesserte Fehlerprüfung vor dem Schreiben
    known_error_indicators = [
        "Fehler bei der Generierung",
        "Fehler: Unerwartete Antwortstruktur",
        "Fehler: Nicht genügend OpenRouter Credits",
        "Keine ausreichenden Projektinformationen"
    ]
    if not content or any(indicator in content for indicator in known_error_indicators):
        print(f"Überspringe das Schreiben des README aufgrund des Inhalts oder Fehlers: {content}")
        exit(1) # Wichtig, damit der Commit-Schritt nicht unnötig läuft

    try:
        write_readme(content)
        print("README-Generierung abgeschlossen. Commit/Push erfolgt durch Workflow.")
    except IOError:
         exit(1)


if __name__ == "__main__":
    main()
