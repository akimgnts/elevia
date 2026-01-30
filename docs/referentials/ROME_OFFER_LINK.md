ROME Offer Link (Read-Only Enrichment)
======================================

What this does
--------------
- Links France Travail offers (fact_offers.source = "france_travail") to a ROME metier.
- Reads ROME code from fact_offers.payload_json.
- Writes link results to a new additive table offer_rome_link.

What this does NOT do
---------------------
- Does NOT modify fact_offers.
- Does NOT change ingestion, matching, scoring, or inbox logic.
- Does NOT infer or guess ROME codes.
- Does NOT alter the ROME referential tables.

Tables
------
Existing (created by ingest_rome.py):
- dim_rome_metier
- dim_rome_competence
- bridge_rome_metier_competence

New (created by enrichment script):
- offer_rome_link
  - offer_id TEXT PRIMARY KEY
  - rome_code TEXT NULL
  - rome_label TEXT NULL
  - linked_at TEXT NOT NULL

Foreign keys:
- offer_id -> fact_offers(id)
- rome_code -> dim_rome_metier(rome_code)

How it works (deterministic)
----------------------------
1) Read payload_json for each France Travail offer.
2) Extract first valid ROME code:
   - Check explicit paths (romeCode, codeRome, code_rome, rome_code, code_metier, metierRome.code)
   - Then scan nested keys containing "rome" for a value matching format A1234
3) If rome_code exists in dim_rome_metier, link it with label.
4) Otherwise store offer_id with rome_code = NULL.

How to run
----------
From repo root:

python3 apps/api/scripts/enrich_offers_with_rome.py

Expected output:
[ROME_LINK] scanned=<n> linked=<n> skipped=<n>

Read-only accessor (optional)
-----------------------------
- apps/api/src/api/utils/rome_link.py provides get_rome_link(offer_id)
- Not wired into API or matching.
