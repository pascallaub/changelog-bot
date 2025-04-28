import os
import subprocess
import re
from datetime import datetime
from openai import OpenAI
from git import Repo, GitCommandError, Diff

# --- OpenRouter Client Initialisierung ---
try:
    # Verwende OpenRouter Base URL und API Key
    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=os.getenv("OPENROUTER_API_KEY")
    )
    if not client.api_key:
        raise ValueError("OpenRouter API Key nicht gefunden. Stelle sicher, dass das OPENROUTER_API_KEY Secret im Workflow gesetzt ist.")
except Exception as e:
    print(f"Fehler beim Initialisieren des OpenRouter Clients: {e}")
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

# --- Hole Commit-Nachrichten und Diff-Informationen aus dem Push ---
def get_push_details(repo, branch_name):
    commits_info = []
    diff_summary = "Keine Diff-Informationen verfügbar."
    try:
        before_sha = os.getenv('GITHUB_EVENT_BEFORE')
        after_sha = os.getenv('GITHUB_EVENT_AFTER')

        if not before_sha or not after_sha or before_sha == '0000000000000000000000000000000000000000':
            print("Warnung: Konnte keine 'before'/'after' SHAs finden oder erster Push. Nehme die letzten 5 Commits für Nachrichten.")
            commits = list(repo.iter_commits(branch_name, max_count=5))
        else:
            print(f"Analysiere Commits und Diff zwischen {before_sha[:7]} und {after_sha[:7]}")
            try:
                repo.commit(before_sha)
                repo.commit(after_sha)
                commits = list(repo.iter_commits(f"{before_sha}..{after_sha}"))

                raw_diff = repo.git.diff(f"{before_sha}..{after_sha}", '--stat')
                diff_summary = process_diff_stat(raw_diff)

            except (GitCommandError, ValueError) as e:
                print(f"Warnung: Fehler beim Holen der Commits oder des Diffs ({e}). Nehme letzte 5 Commits für Nachrichten.")
                commits = list(repo.iter_commits(branch_name, max_count=5))

        if not commits:
            print("Keine neuen Commits in diesem Push gefunden.")
            return None, None

        non_merge_commits_count = 0
        for commit in reversed(commits):
            is_merge = len(commit.parents) > 1
            message_first_line = commit.message.strip().splitlines()[0]
            author_name = commit.author.name
            ignore_merge_message = is_merge and (
                message_first_line.startswith("Merge branch") or
                message_first_line.startswith("Merge pull request")
            )
            if not ignore_merge_message:
                commits_info.append(f"- {message_first_line} ({author_name})")
                if not is_merge:
                    non_merge_commits_count += 1

        if not commits_info:
            if any(len(c.parents) > 1 for c in commits):
                print("Nur Merge-Commits ohne informative Nachrichten gefunden.")
                commit_messages_str = "Nur Merge-Commits ohne spezifische Änderungsdetails."
            else:
                print("Keine relevanten Commit-Nachrichten gefunden.")
                commit_messages_str = None
        else:
            commit_messages_str = "\n".join(commits_info)
            print(f"Gefundene relevante Commit-Nachrichten: {len(commits_info)}")

        return commit_messages_str, diff_summary

    except Exception as e:
        print(f"Fehler beim Abrufen der Push-Details: {e}")
        import traceback
        traceback.print_exc()
        return None, None

def process_diff_stat(diff_stat_output: str) -> str:
    """ Verarbeitet die Ausgabe von 'git diff --stat', um eine lesbare Zusammenfassung zu erstellen. """
    if not diff_stat_output:
        return "Keine Änderungen im Diff gefunden."

    lines = diff_stat_output.strip().split('\n')
    summary_line = ""
    if lines and "changed," in lines[-1]:
        summary_line = lines.pop().strip()

    relevant_files = []
    irrelevant_patterns = [
        r'package-lock\.json', r'yarn\.lock', r'\.gitignore', r'\.env',
        r'config\.yml', r'\.github/', r'Pipfile\.lock'
    ]
    for line in lines:
        if line.strip() and not any(re.search(pattern, line) for pattern in irrelevant_patterns):
            relevant_files.append(line.strip())

    if not relevant_files:
        return f"Keine relevanten Code-Änderungen im Diff gefunden. ({summary_line})"

    processed_summary = "Zusammenfassung der geänderten Dateien:\n" + "\n".join(relevant_files)
    if summary_line:
        processed_summary += f"\n\nGesamtstatistik: {summary_line}"
    return processed_summary

# --- OpenAI-Anfrage (jetzt OpenRouter) ---
def ask_openai(prompt: str) -> str:
    if not prompt:
        print("OpenRouter Prompt ist leer. Überspringe Anfrage.")
        return "Keine Änderungen zum Dokumentieren gefunden."
    try:
        model_to_use = "openai/gpt-4"
        max_tokens_limit = 500

        print(f"Sende Prompt an OpenRouter (Modell: {model_to_use}, max_tokens: {max_tokens_limit})...")
        response = client.chat.completions.create(
            model=model_to_use,
            messages=[
                {"role": "system", "content": "Du bist ein technischer Dokumentationsassistent. Erstelle einen sachlichen, aber community-freundlichen Changelog-Eintrag basierend auf den bereitgestellten Commit-Nachrichten."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.5,
            max_tokens=max_tokens_limit
        )

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
    print("Sammle Commit-Nachrichten und Diff-Informationen für den Changelog...")
    commit_messages, diff_summary = get_push_details(repo, current_branch)

    if not commit_messages or commit_messages == "Nur Merge-Commits ohne spezifische Änderungsdetails.":
        print(f"Keine ausreichenden Commit-Nachrichten für einen detaillierten Changelog gefunden. Status: {commit_messages}")
        return

    prompt = f"""
Erstelle einen Changelog-Eintrag für heute, basierend auf den folgenden Commit-Nachrichten und Diff-Informationen.
Konzentriere dich darauf, die *tatsächlichen Änderungen* (neue Features, Bugfixes, Verbesserungen, Refactorings) zusammenzufassen, die durch diese Commits eingeführt wurden.
Ignoriere generische Merge-Informationen und beschreibe stattdessen, *was* durch die Commits erreicht wurde.
Formuliere es für ein öffentliches Devlog – klar, verständlich und auf den Nutzen für das Projekt fokussiert.

Commits:
{commit_messages}

Diff-Zusammenfassung:
{diff_summary}

Struktur des Eintrags:
- **Zusammenfassung:** Ein kurzer Überblick über die wichtigsten Änderungen in diesem Update.
- **Details:** (Optional) Gehe auf 1-3 signifikante Änderungen genauer ein, falls die Commit-Nachrichten genug Informationen bieten. Erkläre kurz das *Warum* oder den *Nutzen*.
- **Sonstiges:** (Optional) Erwähne kleinere Fixes oder Refactorings, falls vorhanden.

Vermeide es, nur die Commit-Nachrichten aufzulisten. Synthetisiere die Informationen zu einem kohärenten Text.
"""
    print("Generiere Changelog-Eintrag mit OpenRouter...")
    changelog_content = ask_openai(prompt)

    known_error_indicators = [
        "Fehler bei der Generierung",
        "Fehler: Unerwartete Antwortstruktur",
        "Fehler: Nicht genügend OpenRouter Credits"
    ]
    if not changelog_content or any(indicator in changelog_content for indicator in known_error_indicators):
        print(f"Überspringe das Schreiben des Changelogs aufgrund des Inhalts oder Fehlers: {changelog_content}")
    else:
        print("Schreibe Changelog-Eintrag...")
        write_changelog(changelog_content)

    print("Changelog-Skript abgeschlossen.")

if __name__ == "__main__":
    main()