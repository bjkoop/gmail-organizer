# Gmail Organizer

Organize and manage your Gmail inbox with AI-powered recommendations.

## Snelle start

- **Windows:** dubbelklik op `Open Gmail Organizer.bat`
- **macOS:** dubbelklik op `Open Gmail Organizer.command`
- **Linux:** run `./start-gmail-organizer.sh`

De app opent daarna automatisch op `http://127.0.0.1:5000/`.

## Projectstructuur

```markdown
gmail-organizer/
├── app.py                  # Flask web applicatie (web frontend)
├── main.py                 # CLI interface voor inbox processing
├── requirements.txt        # Python dependencies
├── credentials.json        # Google OAuth credentials (niet in git)
├── token.json             # Google OAuth token (niet in git)
├── LICENSE                # Licentie bestand
├── README.md              # Deze documentatie
├── services/              # Service modules
│   ├── __init__.py
│   ├── config.py         # Configuratie settings
│   ├── gmail_service.py  # Gmail API integratie
│   └── openai_service.py # OpenAI API integratie
├── static/                # Frontend static bestanden
│   ├── app.js            # JavaScript voor web UI
│   └── style.css         # CSS styling
└── templates/             # Flask HTML templates
    └── index.html        # Main web UI template
```

## Web Frontend

Run a simple UI to navigate mails, set labels, archive, or delete.

### Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Ensure `credentials.json` is present. On first run, OAuth will open in your browser and create `token.json`.

### Start

```bash
python app.py
```

Open `http://127.0.0.1:5000/`.

### Snel starten (dubbelklik)

- **Windows:** dubbelklik op `Open Gmail Organizer.bat`
- **macOS:** dubbelklik op `Open Gmail Organizer.command`
- **Linux:** run `./start-gmail-organizer.sh`

De launcher start de Flask app en opent automatisch de browser op `http://127.0.0.1:5000/`.

### Features

- Centraal venster: onderwerp, afzender, datum, en content
- Boven: Label (met pop-up), Archiveer, Verwijder
- Onder: Vorige, Volgende met teller (bijv. 2/42)
- Label pop-up toont alle gebruikerslabels, en selecteert bestaande labels van de mail
- Deselecteren verwijdert labels; OK bevestigt, Annuleren sluit zonder wijzigingen
