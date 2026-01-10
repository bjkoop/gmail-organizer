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

    # Heuristic grouping to enforce strict hierarchy
    def matches_any(s, patterns):
        return any(re.search(p, s, re.IGNORECASE) for p in patterns)

    retention_patterns = [r"retent", r"retention", r"bewaar", r"bewaren", r"archief", r"archive"]
    group_patterns = [r"^work$", r"werk", r"^private$", r"priv[eé]", r"\bRUG\b"]
    optional_flags = []

    retention_candidates = [l for l in available_labels if matches_any(l, retention_patterns)]
    group_candidates = [l for l in available_labels if matches_any(l, group_patterns)]
    # System flags (present exactly like these names), plus CATEGORY_*
    for l in available_labels:
        if l == "STARRED" or l == "IMPORTANT" or l.startswith("CATEGORY_"):
            optional_flags.append(l)

    # Build explicit, constrained instruction for strict selection
    prompt = (
        "Je bent een e-mailopruimassistent. Beoordeel ALLEEN deze ene mail en geef een kort advies.\n"
        "Kies een actie en labels volgens deze STRIKTE hiërarchie:\n"
        "1) Eerst EXACT ÉÉN retentie-label (uit: " + ", ".join(retention_candidates or ["GEEN"]) + ")\n"
        "2) Daarna EXACT ÉÉN label uit werk/privé/RUG (uit: " + ", ".join(group_candidates or ["GEEN"]) + ")\n"
        "3) Optioneel ÉÉN extra vlag-label (uit: " + ", ".join(optional_flags or ["GEEN"]) + ")\n"
        "Selecteer labels ALLEEN uit de bovenstaande lijsten. Gebruik maximaal één per categorie.\n"
        "Als een categorie geen geschikte label heeft, vul die in als GEEN.\n"
        "Als een email niet belangrijk is, kies dan VERWIJDEREN als actie. De bedoeling is immers om de mailbox op te ruimen.\n"
        "Geef altijd een korte onderbouwing voor je keuze. \n\n"
        f"Afzender: {sender}\n"
        f"Onderwerp: {subject}\n"
        f"Huidige labels: {current_labels_text}\n"
        f"Beschikbare labels: {labels_text}\n\n"
        "Inhoud:\n"
        f"{body_text}\n\n"
        "Antwoord met ÉÉN regel in het Nederlands, exact dit formaat (zonder extra tekst):\n"
        "Actie: VERWIJDEREN | ARCHIVEREN | BEWAREN; Retentie: <LABEL|GEEN>; Groep: <LABEL|GEEN>; Extra: <LABEL|GEEN>"
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
