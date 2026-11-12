
import streamlit as st
import pdfplumber
import pandas as pd
import re
import plotly.express as px
from transformers import pipeline
from database import (
    enregistrer_depenses,
    consulter_depenses,
    creer_table_membres,
    ajouter_membre,
    consulter_membres,
    supprimer_membre,
    consulter_membres_historique,
    creer_table_budgets,
    enregistrer_budget,
    consulter_budgets,
)
st.set_page_config(page_title="Mona | Dépenses", page_icon="M", layout="wide")

creer_table_membres()
creer_table_budgets()

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Serif+Display&family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');
html, body, .stApp, [data-testid="stSidebar"], .stMarkdown, p, label, button, input, textarea {
  font-family: 'Plus Jakarta Sans', sans-serif !important;
}
h1, h2, h3, h4, h5, h6 {
  font-family: 'DM Serif Display', Georgia, serif !important;
  font-weight: 400 !important;
  letter-spacing: -0.025em !important;
  color: #302B3B !important;
}
[data-testid="stAppViewContainer"] { background: #FAF9F7; }
[data-testid="stSidebar"] { background: #F0EDF2; }
[data-testid="stSidebar"] h1 { font-family: 'DM Serif Display', Georgia, serif !important; font-size: 2.1rem !important; }
div.stButton > button { border-radius: 10px; }
[data-testid="stDataFrame"] { border-radius: 12px; overflow: hidden; }
</style>
""", unsafe_allow_html=True)

st.sidebar.title("mona.")
st.sidebar.caption("Gestion des dépenses")
page = st.sidebar.radio("Navigation", ["Vue d'ensemble", "Importer un relevé", "Budgets", "Membres du ménage"])

if page == "Vue d'ensemble":
    st.title("Vue d'ensemble")
    st.caption("Comprenez vos dépenses, simplement.")
elif page == "Importer un relevé":
    st.title("Importer un relevé")
    st.caption("Analyse et catégorisation automatique de vos transactions.")
elif page == "Budgets":
    st.title("Budgets")
    st.caption("Suivez vos objectifs mensuels.")
else:
    st.title("Membres du ménage")
    st.caption("Gérez les personnes associées à vos dépenses.")

if page == "Membres du ménage":
    st.subheader("Personnes du ménage")

    nouveau_membre = st.text_input("Prénom du nouveau membre")

    if st.button("Ajouter un membre"):
        if nouveau_membre.strip():
            ajouter_membre(nouveau_membre.strip())
            st.success("Membre ajouté avec succès !")
        else:
            st.warning("Veuillez saisir un prénom.")

    st.write("**Membres du ménage :**")

    membres = consulter_membres()

    if membres:
        for membre in membres:
            st.write(membre)
    else:
        st.info("Aucun membre enregistré pour le moment.")

    st.write("**Supprimer un membre :**")

    membres = consulter_membres()

    if membres:
        membre_a_supprimer = st.selectbox(
            "Sélectionnez un membre",
            membres
        )

        if st.button("Supprimer le membre"):
            supprimer_membre(membre_a_supprimer)
            st.rerun()

if page == "Budgets":
    st.subheader("Budgets mensuels")
    st.write("Définissez un budget mensuel pour chaque catégorie de dépenses.")

    categorie_budget = st.selectbox("Catégorie", [
        "Épicerie", "Restaurants", "Transport", "Logement",
        "Santé", "Abonnements", "Magasinage", "Autres"
    ])
    montant_budget = st.number_input("Budget mensuel ($)", min_value=0.0, step=10.0)

    if st.button("Enregistrer le budget"):
        if montant_budget > 0:
            enregistrer_budget(categorie_budget, montant_budget)
            st.success("Budget enregistré avec succès !")
        else:
            st.warning("Veuillez saisir un montant supérieur à 0.")

    st.write("**Budgets mensuels enregistrés :**")
    budgets = consulter_budgets()
    depenses_mois = consulter_depenses()
    depenses_mois["date"] = pd.to_datetime(depenses_mois["date"], dayfirst=True, errors="coerce")
    aujourdhui = pd.Timestamp.today()
    depenses_mois = depenses_mois[
        depenses_mois["date"].dt.to_period("M") == aujourdhui.to_period("M")
    ]

    if not budgets.empty:
        suivi_budgets = budgets.copy()
        depenses_par_categorie = depenses_mois.groupby("categorie")["montant"].sum()
        suivi_budgets["Dépensé ($)"] = (
            suivi_budgets["categorie"].map(depenses_par_categorie).fillna(0)
        )
        suivi_budgets["Restant ($)"] = suivi_budgets["montant"] - suivi_budgets["Dépensé ($)"]
        suivi_budgets = suivi_budgets.rename(columns={
            "categorie": "Catégorie", "montant": "Budget ($)"
        })
        st.dataframe(suivi_budgets.round(2), width="stretch", hide_index=True)
        st.write("**Progression des budgets :**")
        for _, ligne in suivi_budgets.iterrows():
            categorie = ligne["Catégorie"]
            budget = ligne["Budget ($)"]
            depense = ligne["Dépensé ($)"]
            progression = depense / budget if budget > 0 else 0
            st.write(f"{categorie} — {progression:.0%} du budget utilisé")
            st.progress(min(max(progression, 0.0), 1.0))
    else:
        st.info("Aucun budget enregistré pour le moment.")


# On charge le modèle d'IA une seule fois.
# Streamlit conserve le modèle en mémoire entre les interactions.
@st.cache_resource
def charger_modele():
    return pipeline(
        "text-classification",
        model="fahadkamraan/transaction-categorizer"
    )


# On définit les catégories proposées à l'utilisateur.
categories = [
    "Épicerie",
    "Restaurants",
    "Transport",
    "Logement",
    "Santé",
    "Abonnements",
    "Magasinage",
    "Autres"
]


# On associe les catégories anglaises du modèle
# aux catégories françaises de notre application.
correspondances = {
    "Entertainment": "Autres",
    "Shopping": "Magasinage",
    "Subscription": "Abonnements",
    "Restaurants": "Restaurants",
    "Transportation": "Transport",
    "Healthcare": "Santé",
    "Utilities": "Logement"
}


# Cette fonction demande à l'IA de catégoriser une dépense.
def categoriser_depense(description, modele):

    resultat = modele(description)[0]

    categorie_anglaise = resultat["label"]

    categorie_francaise = correspondances.get(
        categorie_anglaise,
        "Autres"
    )

    score_confiance = resultat["score"]

    return categorie_francaise, score_confiance

if page == "Importer un relevé":
    st.subheader("Importer un relevé bancaire")

    st.write("Sélectionnez le membre du ménage concerné par ce relevé.")

    membres_import = consulter_membres()
    if not membres_import:
        st.warning("Ajoutez d’abord un membre dans « Membres du ménage ».")
        st.stop()
    membre_selectionne = st.selectbox("Membre du ménage", membres_import)

    fichier = st.file_uploader(
        "Choisissez un relevé bancaire au format PDF",
        type=["pdf"]
    )


    # On attend qu'un fichier soit importé avant de continuer.
    if fichier is not None:

        st.success("Votre fichier PDF a bien été importé !")

        texte = ""

        # On extrait le texte du PDF.
        with pdfplumber.open(fichier) as pdf:

            st.write("Nombre de pages du PDF :", len(pdf.pages))

            # On lit toutes les pages du document.
            for page_pdf in pdf.pages:
                texte_page = page_pdf.extract_text()

                if texte_page:
                    texte += texte_page + "\n"

        if texte:
            st.success("Du texte a bien été détecté dans le PDF !")
            st.text_area("Texte extrait", texte, height=250)
        else:
            st.warning("Aucun texte détecté dans le PDF.")

        # On prépare la liste des transactions.
        transactions = []

        for ligne in texte.split("\n"):

            resultat = re.match(
                r"^(\d{2}/\d{2}/\d{4})\s+(.+?)\s+(-?\d+,\d{2})$",
                ligne.strip()
            )

            if resultat:

                date = resultat.group(1)
                description = resultat.group(2)
                montant = float(
                    resultat.group(3).replace(",", ".")
                )

                transactions.append({
                    "Date": date,
                    "Description": description,
                    "Montant ($)": montant
                })

        df = pd.DataFrame(
            transactions,
            columns=["Date", "Description", "Montant ($)"]
        )

        st.subheader("Transactions extraites du relevé")
        st.dataframe(df, hide_index=True, width="stretch")

        if not df.empty:

            # Dans notre PDF fictif, les montants négatifs
            # correspondent aux dépenses.
            depenses = df[df["Montant ($)"] < 0].copy()

            depenses["Montant ($)"] = depenses["Montant ($)"].abs()

            if not depenses.empty:

                st.subheader("Dépenses identifiées")
                st.dataframe(depenses, hide_index=True, width="stretch")

                total_depenses = depenses["Montant ($)"].sum()

                st.metric(
                    "Total des dépenses",
                    f"{total_depenses:.2f} $"
                )

                # On lance le modèle d'IA.
                with st.spinner("L'IA analyse vos dépenses..."):
                    modele = charger_modele()

                    resultats_ia = depenses["Description"].apply(
                        lambda description: categoriser_depense(
                            description,
                            modele
                        )
                    )

                    depenses["Catégorie"] = resultats_ia.apply(
                        lambda resultat: resultat[0]
                    )

                st.subheader("Catégorisation des dépenses")

                st.write(
                    "L'IA propose une catégorie pour chaque dépense. "
                    "Vous pouvez corriger les résultats si nécessaire."
                )

                # L'utilisateur peut corriger les catégories proposées.
                depenses_modifiees = st.data_editor(
                    depenses,
                    hide_index=True,
                    width="stretch",
                    column_config={
                        "Catégorie": st.column_config.SelectboxColumn(
                            "Catégorie",
                            options=categories,
                            required=True
                        )
                    },
                    disabled=[
                        "Date",
                        "Description",
                        "Montant ($)"
                    ]
                )

                if st.button("Valider et enregistrer les dépenses"):
                    depenses_a_enregistrer = depenses_modifiees.rename(
                        columns={"Montant ($)": "Montant"}
                    )
                    depenses_a_enregistrer["Membre"] = membre_selectionne
                    nombre = enregistrer_depenses(depenses_a_enregistrer)

                    if nombre > 0:
                        st.success(f"{nombre} nouvelle(s) dépense(s) enregistrée(s) !")
                    else:
                        st.info("Toutes ces dépenses sont déjà enregistrées.")

            else:
                st.warning("Aucune dépense détectée dans le relevé.")

        else:
                st.warning("Aucune transaction trouvée dans le relevé.")
    st.divider()

if page == "Vue d'ensemble":
    st.markdown("### Votre activité")
    st.write("Retrouvez toutes les dépenses de votre ménage en un coup d'œil.")
    st.divider()
    tous_les_membres = sorted(set(
        consulter_membres() + consulter_membres_historique()
    ))

    filtre_membre = st.selectbox(
        "Afficher les dépenses de :",
        ["Tout le ménage", "Non attribué"] + tous_les_membres,
        key="filtre_historique"
    )

    historique = consulter_depenses()

    # Filtre par mois
    historique["date_convertie"] = pd.to_datetime(
        historique["date"], dayfirst=True, errors="coerce"
    )

    mois_disponibles = sorted(
        historique["date_convertie"].dropna().dt.to_period("M").unique(),
        reverse=True
    )

    choix_mois = st.selectbox(
        "Période à analyser",
        ["Tous les mois"] + [str(mois) for mois in mois_disponibles]
    )

    if choix_mois != "Tous les mois":
        historique = historique[
            historique["date_convertie"].dt.to_period("M").astype(str) == choix_mois
        ]

    historique = historique.drop(columns=["date_convertie"])


    if filtre_membre != "Tout le ménage":
        historique = historique[historique["membre"] == filtre_membre]

    if not historique.empty:

        
        # Indicateurs du tableau de bord
        total_historique = historique["montant"].sum()
        nombre_transactions = len(historique)

        depenses_categories = historique.groupby("categorie")["montant"].sum()
        categorie_principale = depenses_categories.idxmax()

       
        # Budget mensuel de l'ensemble du ménage
        budgets_dashboard = consulter_budgets()
        budget_total = budgets_dashboard["montant"].sum()

        # On récupère toutes les dépenses, sans filtre par membre
        toutes_depenses = consulter_depenses()

        dates_budget = pd.to_datetime(
            toutes_depenses["date"],
            dayfirst=True,
            errors="coerce"
        )

        # Mois utilisé pour calculer le budget
        if choix_mois == "Tous les mois":
            mois_budget = pd.Timestamp.today().to_period("M")
        else:
            mois_budget = pd.Period(choix_mois, freq="M")

        depenses_mois = toutes_depenses[
            dates_budget.dt.to_period("M") == mois_budget
        ]

        # On compte uniquement les catégories ayant un budget
        categories_budget = budgets_dashboard["categorie"].tolist()

        depenses_budget = depenses_mois[
            depenses_mois["categorie"].isin(categories_budget)
        ]

        budget_restant = budget_total - depenses_budget["montant"].sum()

        texte_budget = (
            f"{budget_restant:,.2f} $"
            if not budgets_dashboard.empty
            else "Non défini"
        )

        # Fonction pour créer une carte
        def carte_dashboard(titre, valeur, couleur, texte, icone):
            st.markdown(
                f"""
                <div style="
                    background:{couleur};
                    color:#302B3B;
                    border-radius:18px;
                    padding:22px;
                    height:165px;
                    box-sizing:border-box;
                    display:flex;
                    flex-direction:column;
                    justify-content:space-between;
                    overflow:hidden;
                ">
                    <div style="display:flex;justify-content:space-between;align-items:center;">
                        <span style="font-size:14px;opacity:0.85;">{titre}</span>
                        <span style="font-size:12px;opacity:0.5;letter-spacing:1px;">{icone}</span>
                    </div>
                    <div>
                        <div style="font-size:clamp(19px,2vw,28px);
                                    font-weight:750;line-height:1.2;
                                    overflow-wrap:anywhere;">
                            {valeur}
                        </div>
                        <div style="font-size:12px;opacity:0.75;margin-top:7px;">
                            {texte}
                        </div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )

        # Quatre cartes sur deux colonnes
        col1, col2 = st.columns(2, gap="small")

        with col1:
            carte_dashboard(
                "Dépenses totales",
                f"{total_historique:,.2f} $",
                "#DCD5E9",
                "Dépenses de la sélection",
                "01"
            )

        with col2:
            carte_dashboard(
                "Budget restant",
                texte_budget,
                "#DDEAE5",
                "Budgets mensuels du ménage",
                "02"
            )
        st.write("")
        col3, col4 = st.columns(2, gap="small")

        with col3:
            carte_dashboard(
                "Catégorie principale",
                categorie_principale,
                "#F0DFE6",
                "Catégorie la plus dépensière",
                "03"
            )

        with col4:
            carte_dashboard(
                "Transactions",
                str(nombre_transactions),
                "#F0E4C5",
                "Dans votre historique",
                "04"
            )

        st.write("")
        
        # Graphiques des dépenses
        st.markdown("### Analyse des dépenses")

        palette = [
            "#493D73", "#638D88", "#D58B80", "#C5A0B8",
            "#D7B56D", "#8C9DB8", "#9D8478", "#A9BFA9"
        ]

        donnees_graphique = (
            historique.groupby("categorie", as_index=False)["montant"]
            .sum()
            .sort_values("montant", ascending=False)
        )

        col_graph1, col_graph2 = st.columns(2, gap="medium")

        with col_graph1:
            fig_anneau = px.pie(
                donnees_graphique,
                names="categorie",
                values="montant",
                hole=0.65,
                color_discrete_sequence=palette
            )
            fig_anneau.update_traces(
                textinfo="percent",
                textposition="inside"
            )
            fig_anneau.update_layout(
                title="Répartition par catégorie",
                height=380,
                margin=dict(l=10, r=10, t=55, b=10),
                paper_bgcolor="rgba(0,0,0,0)",
                font_color="#292638",
                legend=dict(orientation="h", y=-0.15)
            )
            st.plotly_chart(fig_anneau, width="stretch")

        with col_graph2:
            fig_barres = px.bar(
                donnees_graphique,
                x="montant",
                y="categorie",
                orientation="h",
                color="categorie",
                color_discrete_sequence=palette
            )
            fig_barres.update_layout(
                title="Dépenses par catégorie",
                height=380,
                showlegend=False,
                margin=dict(l=10, r=10, t=55, b=10),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font_color="#292638",
                xaxis_title="Montant ($)",
                yaxis_title=""
            )
            st.plotly_chart(fig_barres, width="stretch")

        # Historique des transactions
        st.markdown("### Historique des transactions")

        historique_affichage = historique.rename(columns={
            "date": "Date",
            "description": "Description",
            "montant": "Montant ($)",
            "categorie": "Catégorie",
            "membre": "Membre"
        })

        st.dataframe(
            historique_affichage,
            hide_index=True,
            width="stretch",
            height=320
        )

    else:
        st.info("Aucune dépense enregistrée pour le moment.")