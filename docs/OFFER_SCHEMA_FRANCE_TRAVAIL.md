# OFFER SCHEMA — France Travail (fact_offers.parquet)

Objectif : ce schéma est le CONTRAT pour `scripts/normalize_offers.py`.
Le script lit `data/raw/offres_*.json` et produit :
- `data/processed/fact_offers.parquet` (latest)
- `data/processed/snapshots/offers_YYYY-MM-DD.parquet` (snapshot du jour)

## Champs OBLIGATOIRES (Backbone)

- offer_uid : "ft_" + id
- offer_id : id
- job_title : intitule
- created_at : dateCreation
- updated_at : dateActualisation
- rome_code : romeCode (nullable)
- rome_label : romeLibelle (nullable)
- contract_type : typeContrat (nullable)
- company_name : entreprise.nom sinon "Non renseigné"
- location_label : lieuTravail.libelle (nullable)
- postal_code : lieuTravail.codePostal (nullable)
- lat : lieuTravail.latitude (nullable float)
- lon : lieuTravail.longitude (nullable float)

## Champs OPTIONNELS (si présent sinon null)

- salary_raw : salaire.libelle sinon salaire.commentaire sinon null
- experience_label : experienceLibelle
- qualification : qualificationLibelle
- duration_work : dureeTravailLibelle
- secteur_activite : secteurActiviteLibelle
- competences_labels : competences[].libelle
- competences_codes : competences[].code
- formations_labels : formations[].niveauLibelle

## Champs EXCLUS du Parquet principal (restent dans le RAW)

- description
- contact
- agence
- contexteTravail
- qualitesProfessionnelles
- tout autre champ nested non listé ci-dessus

## Règles

- Le RAW est immutable : jamais modifié.
- Le Parquet ne contient QUE les champs backbone + optionnels listés.
- Aucune invention : si un champ n'existe pas, on met null (sauf company_name).
