#!/usr/bin/env python3
"""
Générateur de données mockées pour tester le pipeline Elevia Compass
Basé sur les specs OpenAPI France Travail
"""
import json
import random
from pathlib import Path
from datetime import datetime, timedelta

DATA_DIR = Path("/Users/akimguentas/Documents/elevia-compass/data")
DATA_DIR.mkdir(exist_ok=True)

# Données de référence
ROME_CODES = ["M1805", "M1806", "M1810", "I1401", "I1301", "J1103", "K2111"]
ROME_LABELS = {
    "M1805": "Études et développement informatique",
    "M1806": "Conseil et maîtrise d'ouvrage en systèmes d'information",
    "M1810": "Production et exploitation de systèmes d'information",
    "I1401": "Maintenance informatique et bureautique",
    "I1301": "Installation et maintenance électronique",
    "J1103": "Médecine généraliste et spécialisée",
    "K2111": "Formation professionnelle"
}

COMPETENCES = [
    {"code": "C001", "libelle": "Python", "type": "savoir-faire"},
    {"code": "C002", "libelle": "SQL", "type": "savoir-faire"},
    {"code": "C003", "libelle": "JavaScript", "type": "savoir-faire"},
    {"code": "C004", "libelle": "Gestion de projet", "type": "savoir-faire"},
    {"code": "C005", "libelle": "Anglais professionnel", "type": "savoir"},
    {"code": "C006", "libelle": "Power BI", "type": "savoir-faire"},
    {"code": "C007", "libelle": "Excel avancé", "type": "savoir-faire"},
    {"code": "C008", "libelle": "Analyse de données", "type": "savoir-faire"},
    {"code": "C009", "libelle": "Communication", "type": "transversal"},
    {"code": "C010", "libelle": "Travail en équipe", "type": "transversal"},
]

VILLES = [
    {"commune": "Paris", "codePostal": "75001", "dept": "75", "region": "11", "lat": 48.8566, "lon": 2.3522},
    {"commune": "Lyon", "codePostal": "69001", "dept": "69", "region": "84", "lat": 45.7640, "lon": 4.8357},
    {"commune": "Marseille", "codePostal": "13001", "dept": "13", "region": "93", "lat": 43.2965, "lon": 5.3698},
    {"commune": "Toulouse", "codePostal": "31000", "dept": "31", "region": "76", "lat": 43.6047, "lon": 1.4442},
    {"commune": "Nantes", "codePostal": "44000", "dept": "44", "region": "52", "lat": 47.2184, "lon": -1.5536},
]

CONTRATS = ["CDI", "CDD", "MIS", "LIB", "FRA"]

def generate_mock_offers(n=50):
    """Génère n offres d'emploi mockées"""
    offers = []

    for i in range(n):
        rome = random.choice(ROME_CODES)
        ville = random.choice(VILLES)
        contrat = random.choice(CONTRATS)

        # Sélectionner 3-7 compétences aléatoires
        nb_comp = random.randint(3, 7)
        competences_offre = random.sample(COMPETENCES, nb_comp)

        offer = {
            "id": f"MOCK{i+1:04d}",
            "intitule": f"{ROME_LABELS[rome]} - Offre {i+1}",
            "description": f"Description détaillée de l'offre {i+1} pour {ROME_LABELS[rome]}",
            "dateCreation": (datetime.now() - timedelta(days=random.randint(0, 90))).isoformat(),
            "romeCode": rome,
            "appellationLibelle": ROME_LABELS[rome],
            "lieuTravail": {
                "libelle": f"{ville['commune']} ({ville['dept']})",
                "commune": ville['commune'],
                "codePostal": ville['codePostal'],
                "departement": ville['dept'],
                "region": ville['region'],
                "latitude": ville['lat'],
                "longitude": ville['lon'],
                "pays": "FR"
            },
            "typeContrat": contrat,
            "typeContratLibelle": {"CDI": "Contrat à durée indéterminée", "CDD": "Contrat à durée déterminée"}.get(contrat, contrat),
            "experienceExige": random.choice(["D", "E", "S"]),  # Débutant/Expérimenté/Spécialisé
            "dureeTravailLibelle": "Temps plein",
            "salaire": {
                "libelle": f"Entre {random.randint(25, 45)}K€ et {random.randint(50, 80)}K€ par an"
            } if random.random() > 0.3 else None,
            "competences": [
                {
                    "code": c["code"],
                    "libelle": c["libelle"],
                    "exigence": random.choice(["EXIGEE", "EXIGEE", "SOUHAITEE"])  # 2/3 exigées
                }
                for c in competences_offre
            ],
            "teletravail": random.choice([None, "Télétravail partiel", "Télétravail total"]),
            "alternance": random.choice([True, False]) if random.random() > 0.8 else False,
        }

        offers.append(offer)

    return {"resultats": offers}

def generate_mock_rome_competences():
    """Génère le référentiel ROME des compétences"""
    return {
        "competences": COMPETENCES
    }

def generate_mock_rome_metiers():
    """Génère le référentiel ROME des métiers"""
    metiers = []

    for code, label in ROME_LABELS.items():
        metiers.append({
            "codeMetier": code,
            "libelleMetier": label,
            "famille": code[0],  # Première lettre
            "domaine": code[:2],  # Deux premières lettres
        })

    return {"metiers": metiers}

def generate_mock_market_data():
    """Génère des données de marché du travail"""
    market_data = []

    for rome in ROME_CODES:
        for ville in VILLES:
            market_data.append({
                "codeROME": rome,
                "zone": ville['dept'],
                "typeZone": "DEPARTEMENT",
                "tension": round(random.uniform(0.5, 2.5), 2),
                "nbOffres": random.randint(50, 500),
                "nbDemandeurs": random.randint(100, 800),
                "ratioOffresDemandeurs": round(random.uniform(0.2, 1.5), 2),
                "evolutionYoY": round(random.uniform(-0.2, 0.3), 3),
            })

    return {"stats": market_data}

def main():
    print("="*80)
    print("🎲 GÉNÉRATION DE DONNÉES MOCKÉES POUR ELEVIA COMPASS")
    print("="*80)

    # 1. Offres d'emploi
    print("\n📊 Génération de 50 offres d'emploi mockées...")
    offers_data = generate_mock_offers(50)
    output_path = DATA_DIR / "Offres_emploi_MOCK.json"
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(offers_data, f, indent=2, ensure_ascii=False)
    print(f"✅ Sauvegardé: {output_path}")
    print(f"   {len(offers_data['resultats'])} offres générées")

    # 2. ROME Compétences
    print("\n🎯 Génération du référentiel ROME Compétences...")
    rome_comp = generate_mock_rome_competences()
    output_path = DATA_DIR / "ROME_Competences_MOCK.json"
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(rome_comp, f, indent=2, ensure_ascii=False)
    print(f"✅ Sauvegardé: {output_path}")
    print(f"   {len(rome_comp['competences'])} compétences")

    # 3. ROME Métiers
    print("\n💼 Génération du référentiel ROME Métiers...")
    rome_metiers = generate_mock_rome_metiers()
    output_path = DATA_DIR / "ROME_Metiers_MOCK.json"
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(rome_metiers, f, indent=2, ensure_ascii=False)
    print(f"✅ Sauvegardé: {output_path}")
    print(f"   {len(rome_metiers['metiers'])} métiers")

    # 4. Marché du travail
    print("\n📈 Génération des données de marché...")
    market_data = generate_mock_market_data()
    output_path = DATA_DIR / "Marche_Travail_MOCK.json"
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(market_data, f, indent=2, ensure_ascii=False)
    print(f"✅ Sauvegardé: {output_path}")
    print(f"   {len(market_data['stats'])} entrées")

    print("\n" + "="*80)
    print("✅ DONNÉES MOCKÉES GÉNÉRÉES AVEC SUCCÈS")
    print("="*80)
    print("\n🎯 Prochaine étape: Lancer le pipeline de normalisation")
    print("   python build_pipeline.py")

if __name__ == '__main__':
    main()
