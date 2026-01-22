#!/usr/bin/env python3
import json
from pathlib import Path
from datetime import datetime
import pandas as pd

RAW_DIR = Path("data/raw")
OUT_DIR = Path("data/processed")
OUT_DIR.mkdir(parents=True, exist_ok=True)

def safe_get(d, path, default=None):
    cur = d
    for key in path:
        if not isinstance(cur, dict) or key not in cur:
            return default
        cur = cur[key]
    return cur

def normalize_offer(o):
    offer_id = o.get("id")
    offer_uid = f"ft_{offer_id}" if offer_id else None

    salaire_libelle = safe_get(o, ["salaire", "libelle"])
    salaire_commentaire = safe_get(o, ["salaire", "commentaire"])
    salary_raw = salaire_libelle or salaire_commentaire

    competences = o.get("competences") or []
    formations = o.get("formations") or []

    return {
        # Backbone
        "offer_uid": offer_uid,
        "offer_id": offer_id,
        "job_title": o.get("intitule"),
        "created_at": o.get("dateCreation"),
        "updated_at": o.get("dateActualisation"),
        "rome_code": o.get("romeCode"),
        "rome_label": o.get("romeLibelle"),
        "contract_type": o.get("typeContrat"),
        "company_name": safe_get(o, ["entreprise", "nom"], "Non renseigné"),
        "location_label": safe_get(o, ["lieuTravail", "libelle"]),
        "postal_code": safe_get(o, ["lieuTravail", "codePostal"]),
        "lat": safe_get(o, ["lieuTravail", "latitude"]),
        "lon": safe_get(o, ["lieuTravail", "longitude"]),

        # Optionnels
        "salary_raw": salary_raw,
        "experience_label": o.get("experienceLibelle"),
        "qualification": o.get("qualificationLibelle"),
        "duration_work": o.get("dureeTravailLibelle"),
        "secteur_activite": o.get("secteurActiviteLibelle"),
        "competences_labels": [
            c.get("libelle") for c in competences
            if isinstance(c, dict) and c.get("libelle")
        ],
        "competences_codes": [
            c.get("code") for c in competences
            if isinstance(c, dict) and c.get("code")
        ],
        "formations_labels": [
            f.get("niveauLibelle") for f in formations
            if isinstance(f, dict) and f.get("niveauLibelle")
        ],
    }

def main():
    files = sorted(RAW_DIR.glob("offres_*.json"))
    if not files:
        raise SystemExit("❌ Aucun fichier raw trouvé: data/raw/offres_*.json")

    rows = []
    for fp in files:
        with open(fp, "r", encoding="utf-8") as f:
            data = json.load(f)

        resultats = data.get("resultats") or []
        for o in resultats:
            rows.append(normalize_offer(o))

    df = pd.DataFrame(rows)

    # Nettoyage minimal
    df = df.dropna(subset=["offer_id"])              # garder seulement ce qui a un id
    df = df.drop_duplicates(subset=["offer_uid"])    # 1 ligne par offre (pour l’instant)

    # 1) CSV (debug facile)
    out_csv = OUT_DIR / "fact_offers.csv"
    df.to_csv(out_csv, index=False)
    print(f"✅ OK: {len(df)} offres normalisées -> {out_csv}")

    # 2) SNAPSHOT + LATEST (Parquet)
    snapshots_dir = OUT_DIR / "snapshots"
    snapshots_dir.mkdir(parents=True, exist_ok=True)

    today = datetime.now().strftime("%Y-%m-%d")
    snapshot_path = snapshots_dir / f"offers_{today}.parquet"
    latest_path = OUT_DIR / "fact_offers.parquet"

    df.to_parquet(snapshot_path, index=False)
    df.to_parquet(latest_path, index=False)

    print(f"✅ Snapshot écrit -> {snapshot_path}")
    print(f"✅ Latest écrit -> {latest_path}")

if __name__ == "__main__":
    main()
