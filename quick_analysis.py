#!/usr/bin/env python3
"""
quick_analysis.py
=================
Script rapide pour valider que les données sont exploitables
et afficher quelques statistiques clés.

Usage :
    python quick_analysis.py
"""

import json
from pathlib import Path
from collections import Counter
from typing import List, Dict, Any


def load_all_offers(data_dir: Path) -> List[Dict[str, Any]]:
    """Charge tous les fichiers d'offres JSON."""
    files = sorted(data_dir.glob("offres_*.json"))
    all_offers = []

    print(f"📂 Chargement depuis {data_dir}")
    print(f"   → {len(files)} fichiers trouvés")

    for filepath in files:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict) and "resultats" in data:
                all_offers.extend(data["resultats"])
            elif isinstance(data, list):
                all_offers.extend(data)

    print(f"   → {len(all_offers):,} offres chargées\n")
    return all_offers


def analyze_offers(offers: List[Dict[str, Any]]) -> None:
    """Analyse rapide des offres."""

    print("=" * 70)
    print("📊 ANALYSE RAPIDE - ELEVIA COMPASS")
    print("=" * 70)

    # 1. Volume total
    print(f"\n1️⃣  Volume total : {len(offers):,} offres\n")

    # 2. Types de contrat
    print("2️⃣  Types de contrat :")
    contract_types = Counter(o.get("typeContrat") for o in offers)
    for contract, count in contract_types.most_common(10):
        pct = (count / len(offers)) * 100
        print(f"   • {contract or 'Non renseigné':20s} : {count:5,} ({pct:5.1f}%)")

    # 3. Top métiers ROME
    print("\n3️⃣  Top 15 métiers (ROME) :")
    rome_codes = Counter(
        o.get("romeCode") or o.get("romeCodeROME")
        for o in offers
        if o.get("romeCode") or o.get("romeCodeROME")
    )
    for rome, count in rome_codes.most_common(15):
        pct = (count / len(offers)) * 100
        print(f"   • {rome:10s} : {count:5,} ({pct:5.1f}%)")

    # 4. Localisation
    print("\n4️⃣  Top 15 villes :")
    cities = []
    for o in offers:
        lieu = o.get("lieuTravail", {})
        if isinstance(lieu, dict):
            city = lieu.get("commune") or lieu.get("libelle", "").split(" - ")[-1] if " - " in lieu.get("libelle", "") else None
            if city:
                cities.append(city)

    city_counter = Counter(cities)
    for city, count in city_counter.most_common(15):
        pct = (count / len(offers)) * 100
        print(f"   • {city:30s} : {count:5,} ({pct:5.1f}%)")

    # 5. Départements
    print("\n5️⃣  Top 15 départements :")
    departments = []
    for o in offers:
        lieu = o.get("lieuTravail", {})
        if isinstance(lieu, dict):
            libelle = lieu.get("libelle", "")
            if " - " in libelle:
                dept = libelle.split(" - ")[0].strip()
                departments.append(dept)

    dept_counter = Counter(departments)
    for dept, count in dept_counter.most_common(15):
        pct = (count / len(offers)) * 100
        print(f"   • {dept:10s} : {count:5,} ({pct:5.1f}%)")

    # 6. Salaires
    print("\n6️⃣  Informations salariales :")
    salaries_min = []
    salaries_max = []

    for o in offers:
        sal = o.get("salaire", {})
        if isinstance(sal, dict):
            min_val = sal.get("borneMin")
            max_val = sal.get("borneMax")

            if min_val is not None:
                try:
                    salaries_min.append(float(min_val))
                except (ValueError, TypeError):
                    pass

            if max_val is not None:
                try:
                    salaries_max.append(float(max_val))
                except (ValueError, TypeError):
                    pass

    if salaries_min:
        avg_min = sum(salaries_min) / len(salaries_min)
        print(f"   • Offres avec salaire min : {len(salaries_min)} ({len(salaries_min)/len(offers)*100:.1f}%)")
        print(f"   • Salaire min moyen       : {avg_min:,.0f} €")
    else:
        print("   • Aucune information de salaire minimum")

    if salaries_max:
        avg_max = sum(salaries_max) / len(salaries_max)
        print(f"   • Offres avec salaire max : {len(salaries_max)} ({len(salaries_max)/len(offers)*100:.1f}%)")
        print(f"   • Salaire max moyen       : {avg_max:,.0f} €")
    else:
        print("   • Aucune information de salaire maximum")

    # 7. Entreprises
    print("\n7️⃣  Top 10 entreprises :")
    companies = Counter(
        o.get("entreprise", {}).get("nom")
        for o in offers
        if isinstance(o.get("entreprise"), dict) and o.get("entreprise", {}).get("nom")
    )
    for company, count in companies.most_common(10):
        pct = (count / len(offers)) * 100
        print(f"   • {company:40s} : {count:5,} ({pct:5.1f}%)")

    # 8. Dates de création
    print("\n8️⃣  Distribution temporelle :")
    dates = Counter(
        o.get("dateCreation", "")[:10]  # YYYY-MM-DD
        for o in offers
        if o.get("dateCreation")
    )
    for date, count in sorted(dates.items(), reverse=True)[:10]:
        pct = (count / len(offers)) * 100
        print(f"   • {date} : {count:5,} ({pct:5.1f}%)")

    print("\n" + "=" * 70)
    print("✅ Analyse terminée")
    print("=" * 70)


def main():
    """Fonction principale."""
    data_dir = Path(__file__).parent / "data" / "raw"

    if not data_dir.exists():
        print(f"❌ Erreur : le dossier {data_dir} n'existe pas")
        print("   Exécutez d'abord : python fetchers/fetch_offres.py")
        return

    offers = load_all_offers(data_dir)

    if not offers:
        print("❌ Aucune offre trouvée")
        print("   Exécutez : python fetchers/fetch_offres.py")
        return

    analyze_offers(offers)

    # Suggestions
    print("\n💡 Prochaines étapes :")
    print("   1. Ouvrir le notebook : jupyter notebook analysis_elevia_compass.ipynb")
    print("   2. Consulter le guide  : cat NOTEBOOK_GUIDE.md")
    print("   3. Voir l'architecture : cat ARCHITECTURE_TECHNIQUE.md\n")


if __name__ == "__main__":
    main()
