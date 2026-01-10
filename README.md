# gmail-organizer
Organize and manage your Gmail inbox.

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

### Features

- Centraal venster: onderwerp, afzender, datum, en content
- Boven: Label (met pop-up), Archiveer, Verwijder
- Onder: Vorige, Volgende met teller (bijv. 2/42)
- Label pop-up toont alle gebruikerslabels, en selecteert bestaande labels van de mail
- Deselecteren verwijdert labels; OK bevestigt, Annuleren sluit zonder wijzigingen
