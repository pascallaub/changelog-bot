import subprocess
import os
from openai import OpenAI

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def run(cmd):
    return subprocess.check_output(cmd, shell=True, text=True).strip()

def ask_openai(prompt: str) -> str:
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "Du bist ein erfahrener Softwareentwickler. Schreibe eine ausführliche README-Datei für ein GitHub-Projekt. Erkläre Ziel, Installation, Aufbau, Features und wie man beitragen kann."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.5
    )
    return response.choices[0].message.content.strip()

def get_project_overview():
    structure = run("tree -L 2 --dirsfirst")
    files = run("ls -lh")
    return f"Projektstruktur:\n{structure}\n\nDateien:\n{files}"

def write_readme(content: str):
    with open("README.md", "w") as f:
        f.write(content)

def commit_and_push(filename, message):
    run(f'git config user.name "{os.getenv("GIT_AUTHOR_NAME")}"')
    run(f'git config user.email "{os.getenv("GIT_AUTHOR_EMAIL")}"')
    run("git add " + filename)
    run(f'git commit -m "{message}"')
    run("git push")

def main():
    if os.path.exists("README.md"):
        print("README.md existiert bereits. Kein neues README wird erstellt.")
        return

    context = get_project_overview()
    prompt = f"Schreibe ein README.md basierend auf dem folgenden Projekt:\n\n{context}"
    content = ask_openai(prompt)
    write_readme(content)
    commit_and_push("README.md", "docs: generate initial README via OpenAI")

if __name__ == "__main__":
    main()
