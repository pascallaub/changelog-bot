import os
import subprocess
from datetime import datetime
from openai import OpenAI
from git import Repo, GitCommandError

# --- OpenAI Client Initialisierung ---
try:
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    if not client.api_key:
        raise ValueError("OpenAI API Key nicht gefunden. Stelle sicher, dass das OPENAI_API_KEY Secret im Workflow gesetzt ist.")
except Exception as e:
    print(f"Fehler beim Initialisieren des OpenAI Clients: {e}")
    exit(1)

# --- Git Repo Initialisierung ---
try:
    repo = Repo(".")
    current_branch = repo.active_branch.name
    print(f"Aktiver Branch: {current_branch}")
except Exception as e:
    print(f"Fehler beim Initialisieren des Git Repos: {e}")
    exit(1)

# --- Hilfsfunktion zum Ausführen von Befehlen ---
def run(cmd):
    try:
        return subprocess.check_output(cmd, shell=True, text=True, stderr=subprocess.PIPE).strip()
    except subprocess.CalledProcessError as e:
        print(f"Fehler beim Ausführen von '{cmd}': {e.stderr}")
        return None

# --- Hole Commit-Nachrichten aus dem Push ---
def get_push_commits(repo, branch_name):
    commits_info = []
    try:
        before_sha = os.getenv('GITHUB_EVENT_BEFORE')
        after_sha = os.getenv('GITHUB_EVENT_AFTER')

        if not before_sha or not after_sha or before_sha == '0000000000000000000000000000000000000000':
            print("Warnung: Konnte keine 'before'/'after' SHAs finden oder erster Push. Nehme die letzten 5 Commits.")
            commits = list(repo.iter_commits(branch_name, max_count=5))
        else:
            print(f"Analysiere Commits zwischen {before_sha[:7]} und {after_sha[:7]}")
            try:
                # Stelle sicher, dass der 'before' Commit lokal existiert
                repo.commit(before_sha)
                # Hole die Commits im Bereich
                commits = list(repo.iter_commits(f"{before_sha}..{after_sha}"))
            except GitCommandError:
                print(f"Warnung: Konnte 'before' Commit {before_sha} nicht finden. Nehme die letzten 5 Commits als Fallback.")
                commits = list(repo.iter_commits(branch_name, max_count=5))
            except ValueError as ve: # Fängt Fehler ab, wenn SHAs ungültig sind
                 print(f"Fehler beim Verarbeiten der Commit SHAs ({before_sha}, {after_sha}): {ve}. Nehme die letzten 5 Commits.")
                 commits = list(repo.iter_commits(branch_name, max_count=5))


        if not commits:
            print("Keine neuen Commits in diesem Push gefunden.")
            return None

        # Filtere Merge-Commits und sammle relevante Nachrichten
        non_merge_commits_count = 0
        for commit in reversed(commits): # Älteste zuerst
            # Prüfe, ob es ein Merge-Commit ist (mehr als 1 Parent)
            is_merge = len(commit.parents) > 1
            message_first_line = commit.message.strip().splitlines()[0]
            author_name = commit.author.name

            # Ignoriere typische, nicht informative Merge-Nachrichten
            ignore_merge_message = is_merge and (
                message_first_line.startswith("Merge branch") or
                message_first_line.startswith("Merge pull request")
            )

            if not ignore_merge_message:
                commits_info.append(f"- {message_first_line} ({author_name})")
                if not is_merge:
                    non_merge_commits_count += 1

        # Wenn nur Merge-Commits (oder gar keine relevanten) gefunden wurden, gib eine spezielle Info zurück
        if not commits_info:
             if any(len(c.parents) > 1 for c in commits): # Prüfe, ob überhaupt Merge Commits da waren
                  print("Nur Merge-Commits ohne informative Nachrichten gefunden.")
                  # Optional: Gib eine Standardnachricht zurück, die die AI interpretieren kann
                  return "Nur Merge-Commits ohne spezifische Änderungsdetails."
             else:
                  print("Keine relevanten Commit-Nachrichten gefunden.")
                  return None # Keine Commits -> Kein Changelog-Eintrag

        print(f"Gefundene relevante Commit-Nachrichten: {len(commits_info)}")
        return "\n".join(commits_info)

    except Exception as e:
        print(f"Fehler beim Abrufen der Commit-Nachrichten: {e}")
        # Optional: Logge den Traceback für detailliertere Fehlersuche
        # import traceback
        # traceback.print_exc()
        return None

# --- OpenAI-Anfrage ---
def ask_openai(prompt: str) -> str:
    if not prompt:
        print("OpenAI Prompt ist leer. Überspringe Anfrage.")
        return "Keine Änderungen zum Dokumentieren gefunden."
    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "Du bist ein technischer Dokumentationsassistent. Erstelle einen sachlichen, aber community-freundlichen Changelog-Eintrag basierend auf den bereitgestellten Commit-Nachrichten."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.5
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"Fehler bei der OpenAI-Anfrage: {e}")
        return f"Fehler bei der Generierung des Changelog-Eintrags: {e}"

# --- Changelog schreiben ---
def write_changelog(content: str):
    today = datetime.today().strftime("%Y-%m-%d")
    entry_header = f"## [{today}]"
    full_entry = f"{entry_header}\n\n{content}\n"

    try:
        try:
            with open("CHANGELOG.md", "r") as f:
                existing_content = f.read()
        except FileNotFoundError:
            existing_content = ""
            print("CHANGELOG.md nicht gefunden, wird neu erstellt.")

        with open("CHANGELOG.md", "w") as f:
            f.write(full_entry + "\n" + existing_content)
        print("CHANGELOG.md erfolgreich aktualisiert.")

    except IOError as e:
        print(f"Fehler beim Schreiben der CHANGELOG.md: {e}")

# --- Hauptlogik ---
def main():
    print("Sammle Commit-Nachrichten für den Changelog...")
    commit_messages = get_push_commits(repo, current_branch)

    if not commit_messages or commit_messages == "Nur Merge-Commits ohne spezifische Änderungsdetails.":
        print(f"Keine ausreichenden Commit-Nachrichten für einen detaillierten Changelog gefunden. Status: {commit_messages}")
        # Optional: Schreibe einen Platzhalter oder nichts
        # write_changelog("Technische Updates und Merges ohne detaillierte Commit-Nachrichten.")
        return

    # Verbesserter Prompt
    prompt = f"""
Erstelle einen Changelog-Eintrag für heute, basierend auf den folgenden Commit-Nachrichten.
Konzentriere dich darauf, die *tatsächlichen Änderungen* (neue Features, Bugfixes, Verbesserungen, Refactorings) zusammenzufassen, die durch diese Commits eingeführt wurden.
Ignoriere generische Merge-Informationen und beschreibe stattdessen, *was* durch die Commits erreicht wurde.
Formuliere es für ein öffentliches Devlog – klar, verständlich und auf den Nutzen für das Projekt fokussiert.

Commits:
{commit_messages}

Struktur des Eintrags:
- **Zusammenfassung:** Ein kurzer Überblick über die wichtigsten Änderungen in diesem Update.
- **Details:** (Optional) Gehe auf 1-3 signifikante Änderungen genauer ein, falls die Commit-Nachrichten genug Informationen bieten. Erkläre kurz das *Warum* oder den *Nutzen*.
- **Sonstiges:** (Optional) Erwähne kleinere Fixes oder Refactorings, falls vorhanden.

Vermeide es, nur die Commit-Nachrichten aufzulisten. Synthetisiere die Informationen zu einem kohärenten Text.
"""
    print("Generiere Changelog-Eintrag mit OpenAI...")
    changelog_content = ask_openai(prompt)

    if "Fehler bei der Generierung" in changelog_content or not changelog_content.strip():
        print(f"Überspringe das Schreiben des Changelogs aufgrund des Inhalts oder Fehlers: {changelog_content}")
    else:
        print("Schreibe Changelog-Eintrag...")
        write_changelog(changelog_content)

    print("Changelog-Skript abgeschlossen.")

if __name__ == "__main__":
    main()