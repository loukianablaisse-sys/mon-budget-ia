
import sqlite3
import pandas as pd

# Nom du fichier qui contiendra nos dépenses enregistrées
NOM_BASE = "depenses.db"


# Cette fonction crée notre base de données.
def creer_base():

    # On se connecte à SQLite.
    # Si le fichier n'existe pas, SQLite le crée automatiquement.
    connexion = sqlite3.connect(NOM_BASE)

    curseur = connexion.cursor()

    # On crée une table pour stocker les dépenses.
    curseur.execute("""
        CREATE TABLE IF NOT EXISTS depenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            description TEXT NOT NULL,
            montant REAL NOT NULL,
            categorie TEXT NOT NULL,
            membre TEXT NOT NULL DEFAULT 'Non attribué'
        )
    """)

    # Mettre à jour une ancienne base sans effacer les dépenses déjà enregistrées.
    colonnes = [col[1] for col in curseur.execute("PRAGMA table_info(depenses)")]
    if "membre" not in colonnes:
        curseur.execute("ALTER TABLE depenses ADD COLUMN membre TEXT DEFAULT 'Non attribué'")

    # On enregistre la création de la table.
    connexion.commit()

    # On ferme la connexion.
    connexion.close()


# Créer ou mettre à jour la table au démarrage de l'application.
creer_base()

def enregistrer_depenses(df):
    connexion = sqlite3.connect(NOM_BASE)

    # On récupère les dépenses déjà enregistrées.
    depenses_existantes = pd.read_sql_query(
    "SELECT date, description, montant, membre FROM depenses",
    connexion
)

    # On prépare les nouvelles dépenses.
    nouvelles_depenses = df[
    ["Date", "Description", "Montant", "Catégorie", "Membre"]
].copy()

    nouvelles_depenses.columns = [
    "date",
    "description",
    "montant",
    "categorie",
    "membre"
]

    # On regroupe les dépenses existantes et les nouvelles.
    comparaison = nouvelles_depenses.merge(
    depenses_existantes[
        ["date", "description", "montant", "membre"]
    ],
    on=["date", "description", "montant", "membre"],
    how="left",
    indicator=True
)

    # On conserve uniquement les dépenses qui n'existent pas encore.
    nouvelles_depenses = comparaison[
        comparaison["_merge"] == "left_only"
    ].drop(columns=["_merge"])

    # Éviter aussi les doublons présents dans le même relevé.
    nouvelles_depenses = nouvelles_depenses.drop_duplicates(
        subset=["date", "description", "montant", "membre"]
    )

    # On enregistre uniquement les nouvelles dépenses.
    nouvelles_depenses.to_sql(
        "depenses",
        connexion,
        if_exists="append",
        index=False
    )

    connexion.close()

    return len(nouvelles_depenses)

def consulter_depenses():
    connexion = sqlite3.connect(NOM_BASE)

    df = pd.read_sql_query(
    "SELECT date, description, montant, categorie, membre FROM depenses ORDER BY id DESC",
    connexion
)

    connexion.close()

    return df

def creer_table_membres():
    connexion = sqlite3.connect(NOM_BASE)

    curseur = connexion.cursor()

    curseur.execute("""
        CREATE TABLE IF NOT EXISTS membres (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nom TEXT NOT NULL UNIQUE
        )
    """)

    connexion.commit()
    connexion.close()

def ajouter_membre(nom):
    connexion = sqlite3.connect(NOM_BASE)
    curseur = connexion.cursor()

    curseur.execute(
        "INSERT OR IGNORE INTO membres (nom) VALUES (?)",
        (nom,)
    )

    connexion.commit()
    connexion.close()


def consulter_membres():
    connexion = sqlite3.connect(NOM_BASE)

    membres = pd.read_sql_query(
        "SELECT nom FROM membres ORDER BY nom",
        connexion
    )

    connexion.close()

    return membres["nom"].tolist()

def supprimer_membre(nom):
    connexion = sqlite3.connect(NOM_BASE)
    curseur = connexion.cursor()

    curseur.execute(
        "DELETE FROM membres WHERE nom = ?",
        (nom,)
    )

    connexion.commit()
    connexion.close()

def consulter_membres_historique():
    connexion = sqlite3.connect(NOM_BASE)
    curseur = connexion.cursor()

    curseur.execute("""
        SELECT DISTINCT membre
        FROM depenses
        WHERE membre IS NOT NULL
        AND membre != 'Non attribué'
        ORDER BY membre
    """)

    membres = [ligne[0] for ligne in curseur.fetchall()]

    connexion.close()

    return membres

def creer_table_budgets():
    connexion = sqlite3.connect(NOM_BASE)
    curseur = connexion.cursor()

    curseur.execute("""
        CREATE TABLE IF NOT EXISTS budgets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            categorie TEXT NOT NULL UNIQUE,
            montant REAL NOT NULL
        )
    """)

    connexion.commit()
    connexion.close()

def enregistrer_budget(categorie, montant):
    connexion = sqlite3.connect(NOM_BASE)
    curseur = connexion.cursor()

    curseur.execute("""
        INSERT INTO budgets (categorie, montant)
        VALUES (?, ?)
        ON CONFLICT(categorie)
        DO UPDATE SET montant = excluded.montant
    """, (categorie, montant))

    connexion.commit()
    connexion.close()

    
def consulter_budgets():
    connexion = sqlite3.connect(NOM_BASE)

    budgets = pd.read_sql_query(
        "SELECT categorie, montant FROM budgets ORDER BY categorie",
        connexion
    )

    connexion.close()

    return budgets
    