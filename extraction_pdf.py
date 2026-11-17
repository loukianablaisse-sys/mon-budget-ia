import re
import pdfplumber
import pandas as pd

MOIS = {'janv':1,'jan':1,'feb':2,'fev':2,'févr':2,'mar':3,'mars':3,'apr':4,'avr':4,'may':5,'mai':5,'jun':6,'juin':6,'jul':7,'juil':7,'aug':8,'août':8,'aout':8,'sep':9,'sept':9,'oct':10,'nov':11,'dec':12,'déc':12}
NOMBRE = r'-?\d[\d ]*[,.]\d{2}'


def nombre(texte):
    texte = texte.replace(' ', '').replace('$', '')
    if ',' in texte:
        texte = texte.replace('.', '').replace(',', '.') if texte.rfind(',') > texte.rfind('.') else texte.replace(',', '')
    return float(texte)


def date_normale(jour, mois, annee):
    mois = mois.lower().rstrip('.')
    if mois not in MOIS:
        return None
    annee = int(annee)
    if annee < 100:
        annee += 2000
    return f'{int(jour):02d}/{MOIS[mois]:02d}/{annee}'


def extraire_transactions(fichier):
    with pdfplumber.open(fichier) as pdf:
        pages = [page.extract_text(layout=False) or '' for page in pdf.pages]
    texte = '\n'.join(pages)
    annee_match = re.search(r'\b20\d{2}\b', texte)
    annee_defaut = int(annee_match.group()) if annee_match else None
    transactions = []
    solde_precedent = None

    for ligne in texte.splitlines():
        ligne = ' '.join(ligne.split())
        date = None
        reste = None
        m = re.match(r'^(\d{2})/(\d{2})/(\d{4})\s+(.+)$', ligne)
        if m:
            date = f'{int(m[1]):02d}/{int(m[2]):02d}/{m[3]}'
            reste = m[4]
        else:
            m = re.match(r'^(\d{1,2})\s+([A-Za-zÀ-ÿ]+)\.?\s+(\d{2,4})\s+(.+)$', ligne)
            if m:
                date = date_normale(m[1], m[2], m[3])
                reste = m[4]
            else:
                m = re.match(r'^(\d{1,2})\s+([A-Za-zÀ-ÿ]+)\.?\s+(.+)$', ligne)
                if m and annee_defaut:
                    date = date_normale(m[1], m[2], annee_defaut)
                    reste = m[3]
                else:
                    m = re.match(r'^([A-Za-z]{3})\s+(\d{1,2})\s+(.+)$', ligne)
                    if m and annee_defaut:
                        date = date_normale(m[2], m[1], annee_defaut)
                        reste = m[3]
        if not date or not reste:
            continue
        montant_pattern = r"(?:\d{1,3}(?:[ ,]\d{3})+|\d+)[,.]\d{2}"
        paire = re.match(r"^(.+?)\s+(" + montant_pattern + r")\s*\$?\s+(" + montant_pattern + r")\s*\$?$", reste)
        seul = re.match(r"^(.+?)\s+(-?" + montant_pattern + r")\s*\$?$", reste)
        if paire:
            description = paire[1].strip()
            montant = abs(nombre(paire[2]))
            solde = nombre(paire[3])
            if solde_precedent is not None and abs(abs(solde - solde_precedent) - montant) < 0.02:
                est_depense = solde < solde_precedent
            else:
                est_depense = not bool(re.search(r"\b(RECU|REÇU|CREDIT|CRÉDIT|DEPOT|DÉPÔT|PAYROLL|INTERETS GAGNES|INTEREST CREDIT|REFUND|RETURN)\b", description, re.I))
            solde_precedent = solde
        elif seul:
            description = seul[1].strip()
            montant_brut = nombre(seul[2])
            montant = abs(montant_brut)
            est_depense = montant_brut < 0
        else:
            continue
        if description and est_depense:
            transactions.append({'Date':date,'Description':description,'Montant ($)':montant})
    return pd.DataFrame(transactions, columns=['Date','Description','Montant ($)'])

