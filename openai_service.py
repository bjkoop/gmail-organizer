from openai import AzureOpenAI
import json
import re
from config import (
    AZURE_OPENAI_API_KEY,
    AZURE_OPENAI_ENDPOINT,
    AZURE_OPENAI_MODEL_DEPLOYMENT,
    AZURE_OPENAI_API_VERSION,
)

client = AzureOpenAI(
    api_key=AZURE_OPENAI_API_KEY,
    api_version=AZURE_OPENAI_API_VERSION,
    azure_endpoint=AZURE_OPENAI_ENDPOINT,
)


def get_mail_recommendation(sender, subject, body_text, available_labels, current_labels):
    """
    Vraag GPT-5 om een aanbeveling met volledige inhoud en labels.

    Args:
        sender: Afzender
        subject: Onderwerp
        body_text: Volledige mailinhoud (plain + gestript HTML)
        available_labels: Beschikbare gebruikerslabels
        current_labels: Huidige labels op de mail

    Returns:
        Tekstuele aanbeveling van de AI
    """

    labels_text = ", ".join(available_labels) if available_labels else "(geen)"
    current_labels_text = ", ".join(current_labels) if current_labels else "(geen)"

    prompt = (
        "Je bent een e-mailopruimassistent. Beoordeel ALLEEN deze ene mail en geef een zo kort mogelijk advies gericht op inbox opruimen.\n"
        "Als de mail zonder risico weg kan, kies: VERWIJDEREN. Anders: ARCHIVEREN, LABEL: <naam>, of BEWAREN.\n\n"
        f"Afzender: {sender}\n"
        f"Onderwerp: {subject}\n"
        f"Huidige labels: {current_labels_text}\n"
        f"Beschikbare labels: {labels_text}\n\n"
        "Inhoud:\n"
        f"{body_text}\n\n"
        "Antwoord met één korte regel in het Nederlands, zonder extra uitleg.\n"
        "Formaat: Actie: VERWIJDEREN | ARCHIVEREN | LABEL: <naam> | BEWAREN."
        "Let op! Bij ARCHIVEREN is een label verplicht."
        "Indien de mail niet belangrijk is, geef dan VERWIJDEREN als advies."
    )

    try:
        response = client.chat.completions.create(
            model=AZURE_OPENAI_MODEL_DEPLOYMENT,
            messages=[
                {"role": "user", "content": prompt},
            ],
            max_completion_tokens=2000,
        )

        if response.choices and len(response.choices) > 0:
            content = response.choices[0].message.content
            return content if content else "Geen aanbeveling ontvangen"
        else:
            return "Geen aanbeveling ontvangen (geen choices)"

    except Exception as e:
        print(f"Debug - Exception: {type(e).__name__}: {e}")
        return f"Fout bij OpenAI call: {e}"
