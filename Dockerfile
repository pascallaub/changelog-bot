# 1. Offizielles Python-Image verwenden
FROM python:3.10-slim

# 2. Arbeitsverzeichnis im Container erstellen
WORKDIR /app

# 3. Skripte ins Image kopieren
COPY .github/scripts/ ./scripts/

# 4. Python-Abhängigkeiten installieren
RUN pip install openai gitpython

# 5. Umgebungsvariable für OpenAI vorbereiten
ENV OPENAI_API_KEY=""

# 6. Standardbefehl im Container
CMD ["bash", "-c", "python scripts/changelogAI.py && python scripts/readmeAI.py"]
