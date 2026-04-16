#!/usr/bin/env python3
"""
scrape_business_france_azure.py - Business France VIE Scraper (Azure / Civiweb)
================================================================================

Scrape les offres VIE depuis l'API publique Civiweb Azure :
  - Search : POST https://civiweb-api-prd.azurewebsites.net/api/Offers/search
  - Detail : GET  https://civiweb-api-prd.azurewebsites.net/api/Offers/details/{id}

Produit un JSONL 100% compatible ingest_business_france.py :
  Chaque ligne = {"run_id": "...", "fetched_at": "...", "source_url": "...", "payload": {...}}

Usage (cron-friendly, aucun input interactif) :
    python3 apps/api/scripts/scrape_business_france_azure.py
    python3 apps/api/scripts/scrape_business_france_azure.py --max-offers 200
    python3 apps/api/scripts/scrape_business_france_azure.py --sample
    python3 apps/api/scripts/scrape_business_france_azure.py --test

Variables d'environnement :
    BF_AZURE_MAX_OFFERS      Limite totale d'offres (défaut : illimité, cap sécurité : 5000)
    BF_AZURE_MAX_WORKERS     Threads parallèles pour les détails (défaut : 2, max : 3)
    BF_AZURE_SLEEP_SEC       Pause entre batches en secondes (défaut : 2.0)
    BF_AZURE_BATCH_SIZE      Offres par page de recherche (défaut : 50)
    BF_AZURE_SKIP_DETAILS    Si "1", ingère les offres catalog sans détail enrichi

Codes de sortie :
    0  Succès (au moins MIN_OFFERS_SUCCESS offres écrites)
    1  Erreur fatale (réseau, DB, abort threshold)
    2  Succès partiel (offres récupérées mais sous le seuil MIN_OFFERS_SUCCESS)

Sécurités actives :
    - Retry max 3, backoff exponentiel [2s, 4s, 8s] + jitter [0, 1s]
    - Abort si taux d'erreur > 30 % après 10 requêtes minimum
    - max_workers ≤ 3 (hard cap anti-saturation)
    - Safety cap 5000 offres max par run
    - Never overwrite : un run_id unique par run, le fichier existant → exit(1)
    - Aucun secret hardcodé, aucune credential

INTERDIT :
    - apps/api/src/matching/* (scoring core)
    - idf.py, weights_*, Fβ
    - Schéma DB (fact_offers, fact_offer_skills)
"""

import argparse
import concurrent.futures
import json
import os
import random
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

try:
    import requests
except ImportError:
    print(json.dumps({"step": "init", "status": "error",
                      "error": "requests not installed — pip install requests"}),
          flush=True)
    sys.exit(1)

from api.utils.raw_offers_pg import persist_raw_offers

# ==============================================================================
# PATHS (anchored to repo root — jamais relatif au CWD)
# ==============================================================================
API_ROOT   = Path(__file__).parent.parent
DATA_DIR   = API_ROOT / "data"
RAW_BF_DIR = DATA_DIR / "raw" / "business_france"

# ==============================================================================
# CONFIGURATION (tout configurable via env, jamais hardcodé)
# ==============================================================================

SEARCH_API_URL  = os.environ.get(
    "BF_AZURE_SEARCH_URL",
    "https://civiweb-api-prd.azurewebsites.net/api/Offers/search",
)
DETAILS_API_URL = os.environ.get(
    "BF_AZURE_DETAILS_URL",
    "https://civiweb-api-prd.azurewebsites.net/api/Offers/details",
)
OFFER_BASE_URL = "https://mon-vie-via.businessfrance.fr/offres/"

# Limites — la cap de sécurité ne peut PAS être dépassée quelle que soit la valeur env
SAFETY_CAP_OFFERS   = 5_000
MAX_OFFERS          = min(
    int(os.environ.get("BF_AZURE_MAX_OFFERS", "0") or "0") or SAFETY_CAP_OFFERS,
    SAFETY_CAP_OFFERS,
)
BATCH_SIZE          = min(int(os.environ.get("BF_AZURE_BATCH_SIZE", "50")), 100)
SLEEP_SEC           = max(float(os.environ.get("BF_AZURE_SLEEP_SEC", "2.0")), 0.5)
MAX_WORKERS         = min(int(os.environ.get("BF_AZURE_MAX_WORKERS", "2")), 3)
SKIP_DETAILS        = os.environ.get("BF_AZURE_SKIP_DETAILS", "0").strip() == "1"

# Resilience
TIMEOUT_SEC         = 30
BACKOFF_SCHEDULE    = [2.0, 4.0, 8.0]
MAX_RETRIES         = 3
ABORT_THRESHOLD_PCT = 30.0
ABORT_MIN_SAMPLE    = 10
MIN_OFFERS_SUCCESS  = 10   # seuil en dessous duquel on sort en code 2

# Headers — statiques, navigation publique, aucun secret
HEADERS: Dict[str, str] = {
    "Accept":          "application/json, text/plain, */*",
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
    "Connection":      "keep-alive",
    "Content-Type":    "application/json;charset=UTF-8",
    "Origin":          "https://mon-vie-via.businessfrance.fr",
    "Referer":         "https://mon-vie-via.businessfrance.fr/",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/134.0.0.0 Safari/537.36"
    ),
}

# Payload de recherche par défaut (toutes offres, pas de filtre)
DEFAULT_SEARCH_PAYLOAD: Dict[str, Any] = {
    "query":              "",
    "activitySectorId":   [],
    "missionsTypesIds":   [],
    "missionsDurations":  [],
    "gerographicZones":   [],
    "countriesIds":       [],
    "studiesLevelId":     [],
    "companiesSizes":     [],
    "specializationsIds": [],
    "entreprisesIds":     [0],
    "missionStartDate":   None,
}


# ==============================================================================
# STRUCTURED LOGGER — JSON stdout, Railway-compatible
# ==============================================================================

class StructuredLogger:
    """Émet des lignes JSON structurées vers stdout (compatible Railway/cron)."""

    def __init__(self, job_name: str, run_id: str) -> None:
        self.job_name = job_name
        self.run_id   = run_id

    def log(
        self,
        step: str,
        status: str,
        duration_ms: Optional[int]   = None,
        offers_processed: Optional[int] = None,
        error: Optional[str]         = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        entry: Dict[str, Any] = {
            "timestamp":        datetime.now(timezone.utc).isoformat(),
            "job_name":         self.job_name,
            "run_id":           self.run_id,
            "step":             step,
            "status":           status,
            "duration_ms":      duration_ms,
            "offers_processed": offers_processed,
            "error":            error,
        }
        if extra:
            entry.update(extra)
        entry = {k: v for k, v in entry.items() if v is not None}
        print(json.dumps(entry, ensure_ascii=False), flush=True)
        return entry


# ==============================================================================
# RESILIENCE
# ==============================================================================

class AbortScrapeError(RuntimeError):
    """Levée quand le taux d'erreur dépasse ABORT_THRESHOLD_PCT."""


def _check_abort(counter: Dict[str, int]) -> None:
    total  = counter.get("total", 0)
    failed = counter.get("failed", 0)
    if total >= ABORT_MIN_SAMPLE and (failed / total * 100) > ABORT_THRESHOLD_PCT:
        rate = failed / total * 100
        raise AbortScrapeError(
            f"Abort: {failed}/{total} requêtes échouées ({rate:.1f}% > {ABORT_THRESHOLD_PCT}%)"
        )


def _fetch(
    method: str,
    url: str,
    session: requests.Session,
    counter: Dict[str, int],
    logger: StructuredLogger,
    *,
    json_body: Optional[Dict] = None,
    extra_headers: Optional[Dict[str, str]] = None,
) -> Optional[requests.Response]:
    """
    Exécute une requête HTTP avec retry exponentiel.

    - 403 : pas de retry, comptabilise l'erreur
    - 429 : respecte Retry-After, puis retry
    - 5xx / Timeout / ConnectionError : retry max 3x avec backoff + jitter
    - Lève AbortScrapeError si taux d'erreur > seuil
    """
    hdrs = dict(HEADERS)
    if extra_headers:
        hdrs.update(extra_headers)

    last_err: Optional[str] = None

    for attempt, backoff in enumerate(BACKOFF_SCHEDULE[:MAX_RETRIES], start=1):
        try:
            if method.upper() == "POST":
                resp = session.post(url, headers=hdrs, json=json_body, timeout=TIMEOUT_SEC)
            else:
                resp = session.get(url, headers=hdrs, timeout=TIMEOUT_SEC)

            # 403 — bot detection, pas de retry
            if resp.status_code == 403:
                counter["total"]  += 1
                counter["failed"] += 1
                logger.log("http_error", "error",
                           error="HTTP 403 Forbidden",
                           extra={"catalog_source": "BF_AZURE", "url": url,
                                  "status_code": 403, "attempt": attempt})
                _check_abort(counter)
                return None

            # 429 — rate limit, respecte Retry-After
            if resp.status_code == 429:
                retry_after = int(resp.headers.get("Retry-After", backoff * 2))
                sleep_sec   = min(retry_after, 60)
                logger.log("http_error", "error",
                           error=f"HTTP 429 Rate Limited — sleep {sleep_sec}s",
                           extra={"catalog_source": "BF_AZURE", "url": url,
                                  "status_code": 429, "attempt": attempt})
                time.sleep(sleep_sec)
                continue

            # 5xx — retry
            if resp.status_code >= 500:
                jitter     = random.uniform(0.0, 1.0)
                sleep_total = backoff + jitter
                logger.log("http_error", "error",
                           error=f"HTTP {resp.status_code}",
                           extra={"catalog_source": "BF_AZURE", "url": url,
                                  "status_code": resp.status_code,
                                  "attempt": attempt, "backoff_sec": round(sleep_total, 2)})
                last_err = f"HTTP {resp.status_code}"
                time.sleep(sleep_total)
                continue

            # Succès
            counter["total"] += 1
            return resp

        except requests.exceptions.Timeout:
            jitter      = random.uniform(0.0, 1.0)
            sleep_total = backoff + jitter
            logger.log("http_error", "error",
                       error=f"Timeout après {TIMEOUT_SEC}s",
                       extra={"catalog_source": "BF_AZURE", "url": url,
                              "attempt": attempt, "backoff_sec": round(sleep_total, 2)})
            last_err = "Timeout"
            time.sleep(sleep_total)

        except requests.exceptions.ConnectionError as exc:
            jitter      = random.uniform(0.0, 1.0)
            sleep_total = backoff + jitter
            logger.log("http_error", "error",
                       error=f"ConnectionError: {exc}",
                       extra={"catalog_source": "BF_AZURE", "url": url,
                              "attempt": attempt, "backoff_sec": round(sleep_total, 2)})
            last_err = str(exc)
            time.sleep(sleep_total)

    # Toutes tentatives épuisées
    counter["total"]  += 1
    counter["failed"] += 1
    logger.log("http_error", "error",
               error=f"Toutes les {MAX_RETRIES} tentatives épuisées : {last_err}",
               extra={"catalog_source": "BF_AZURE", "url": url, "attempt": MAX_RETRIES})
    _check_abort(counter)
    return None


# ==============================================================================
# CATALOG — recherche paginée
# ==============================================================================

def fetch_catalog(
    session: requests.Session,
    counter: Dict[str, int],
    logger: StructuredLogger,
    max_offers: int,
) -> Tuple[List[Dict[str, Any]], int]:
    """
    Récupère la liste paginée des offres via POST /search.

    Retourne (offers_list, total_count_annoncé).
    """
    all_offers: List[Dict[str, Any]] = []
    total_count: Optional[int]       = None
    skip = 0
    page = 0

    while len(all_offers) < max_offers:
        remaining   = max_offers - len(all_offers)
        page_limit  = min(BATCH_SIZE, remaining)

        payload = {
            **DEFAULT_SEARCH_PAYLOAD,
            "limit": page_limit,
            "skip":  skip,
        }

        resp = _fetch("POST", SEARCH_API_URL, session, counter, logger, json_body=payload)
        if resp is None:
            break

        try:
            data = resp.json()
        except (ValueError, json.JSONDecodeError):
            logger.log("parse_error", "error",
                       error="Réponse search non-JSON",
                       extra={"catalog_source": "BF_AZURE", "page": page})
            counter["failed"] += 1
            _check_abort(counter)
            break

        if total_count is None and "count" in data:
            total_count = int(data["count"])

        batch: List[Dict[str, Any]] = []
        if isinstance(data.get("result"), list):
            batch = data["result"]
        elif isinstance(data, list):
            batch = data

        all_offers.extend(batch)

        logger.log("page_fetched", "success",
                   extra={
                       "catalog_source":       "BF_AZURE",
                       "page_num":             page,
                       "offers_found_on_page": len(batch),
                       "cumulative_total":     len(all_offers),
                       "api_total":            total_count,
                   })

        if len(batch) < page_limit:
            break  # Fin de catalogue

        skip += len(batch)
        page += 1

        if page > 0 and page < (max_offers // BATCH_SIZE + 1):
            time.sleep(SLEEP_SEC)

    return all_offers, (total_count or len(all_offers))


# ==============================================================================
# DÉTAILS — enrichissement parallèle
# ==============================================================================

def _fetch_one_detail(
    offer_id: Any,
    session: requests.Session,
    counter: Dict[str, int],
    logger: StructuredLogger,
) -> Optional[Dict[str, Any]]:
    """Récupère le détail d'une offre par ID (GET /details/{id})."""
    url  = f"{DETAILS_API_URL}/{offer_id}"
    resp = _fetch("GET", url, session, counter, logger)

    if resp is None:
        logger.log("detail_fetched", "error",
                   extra={"catalog_source": "BF_AZURE",
                          "offer_id": offer_id, "http_status": 0})
        return None

    try:
        detail = resp.json()
    except (ValueError, json.JSONDecodeError):
        logger.log("detail_fetched", "error",
                   extra={"catalog_source": "BF_AZURE",
                          "offer_id": offer_id, "http_status": resp.status_code})
        return None

    logger.log("detail_fetched", "ok",
               extra={"catalog_source": "BF_AZURE",
                      "offer_id": offer_id, "http_status": resp.status_code})
    return detail if isinstance(detail, dict) else None


def enrich_with_details(
    catalog_offers: List[Dict[str, Any]],
    session: requests.Session,
    counter: Dict[str, int],
    logger: StructuredLogger,
) -> List[Dict[str, Any]]:
    """
    Enrichit chaque offre catalog avec son détail (GET /details/{id}).

    - Parallèle par batch de 20, max_workers≤3
    - Pause SLEEP_SEC entre batches
    - En cas d'échec détail, conserve l'offre catalog (dégradation gracieuse)
    """
    enriched: List[Dict[str, Any]] = []
    detail_batch_size = 20
    total = len(catalog_offers)
    total_batches = (total + detail_batch_size - 1) // detail_batch_size

    for i in range(0, total, detail_batch_size):
        batch      = catalog_offers[i : i + detail_batch_size]
        batch_num  = i // detail_batch_size + 1
        logger.log("detail_batch_start", "info",
                   extra={"catalog_source": "BF_AZURE",
                          "batch": batch_num, "total_batches": total_batches,
                          "batch_size": len(batch)})

        with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            future_to_offer: Dict[concurrent.futures.Future, Dict] = {
                executor.submit(
                    _fetch_one_detail,
                    offer.get("id"),
                    session,
                    counter,
                    logger,
                ): offer
                for offer in batch
            }

            for future in concurrent.futures.as_completed(future_to_offer):
                catalog_offer = future_to_offer[future]
                try:
                    detail = future.result()
                except AbortScrapeError:
                    raise  # remonte immédiatement
                except Exception as exc:
                    logger.log("detail_parse_error", "error",
                               error=str(exc),
                               extra={"catalog_source": "BF_AZURE",
                                      "offer_id": catalog_offer.get("id")})
                    counter["failed"] += 1
                    detail = None

                # Fusion : détail > catalog en cas de conflit
                merged = {**catalog_offer}
                if detail:
                    merged.update(detail)
                enriched.append(merged)

        logger.log("detail_batch_done", "success",
                   offers_processed=len(enriched),
                   extra={"catalog_source": "BF_AZURE", "batch": batch_num})

        if i + detail_batch_size < total:
            time.sleep(SLEEP_SEC)

    return enriched


# ==============================================================================
# NORMALISATION — mapping champs Civiweb → aliases ingesteur
# ==============================================================================

def normalize_payload(raw: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalise un dict brut Civiweb Azure en payload compatible ingest_business_france.py.

    Mapping exact des champs Civiweb (validé sur l'API réelle) :
      missionTitle       → title       (alias ingesteur: title/intitule/poste/name)
      missionDescription → description (alias ingesteur: description/descriptif/...)
      organizationName   → company     (alias ingesteur: company/entreprise/...)
      cityName           → city        (alias ingesteur: city/ville/...)
      countryName        → country     (alias ingesteur: country/pays/...)
      creationDate       → publicationDate
      missionDuration    → contractDuration
      missionStartDate   → startDate
      reference          → référence alternative pour ID (ex: VIE237189)

    Stratégie : on AJOUTE les clés canoniques sans écraser les clés natives.
    L'ingesteur voit à la fois les clés Civiweb natives ET les aliases →
    extract_field() trouvera toujours ce qu'il cherche.

    Note API : search et detail retournent les mêmes champs.
    --skip-details économise 100% des appels details sans perte de données.
    """
    out: Dict[str, Any] = dict(raw)  # Conserver TOUS les champs natifs

    def _pick(*keys: str) -> Any:
        for k in keys:
            v = raw.get(k)
            if v is not None and str(v).strip() not in ("", "None", "null"):
                return v
        return None

    # Mapping Civiweb → aliases attendus par extract_field() dans l'ingesteur
    if not out.get("title"):
        out["title"] = _pick("missionTitle") or ""

    if not out.get("description"):
        # missionDescription = description de mission, missionProfile = profil recherché
        desc  = _pick("missionDescription") or ""
        profil = _pick("missionProfile") or ""
        out["description"] = desc + ("\n\nProfil :\n" + profil if profil and profil != desc else "")

    if not out.get("company"):
        out["company"] = _pick("organizationName") or ""

    if not out.get("city"):
        out["city"] = _pick("cityName", "cityNameEn", "cityAffectation") or ""

    if not out.get("country"):
        out["country"] = _pick("countryName", "countryNameEn") or ""

    if not out.get("publicationDate"):
        out["publicationDate"] = _pick("creationDate", "startBroadcastDate")

    if not out.get("contractDuration"):
        out["contractDuration"] = _pick("missionDuration")

    if not out.get("startDate"):
        out["startDate"] = _pick("missionStartDate")

    # Lien direct (pour audit et déduplication)
    if out.get("id") and not out.get("offerUrl"):
        out["offerUrl"] = f"{OFFER_BASE_URL}{out['id']}"

    # Source tag explicite (tracabilité audit)
    out["bf_source"] = "BF_AZURE"

    return out


# ==============================================================================
# SAMPLE MODE — données synthétiques pour smoke test / cron staging
# ==============================================================================

def generate_sample_offers(n: int = 5) -> List[Dict[str, Any]]:
    """Génère n offres synthétiques pour --sample (aucun appel réseau)."""
    now = datetime.now(timezone.utc).isoformat()
    sectors = [
        ("Data / BI", ["python", "SQL", "data engineering", "gestion de projets"]),
        ("Finance", ["modélisation financière", "Excel", "reporting", "audit"]),
        ("Marketing", ["marketing digital", "CRM", "réseaux sociaux"]),
        ("Ingénierie", ["mécanique", "CAO", "R&D", "normes ISO"]),
        ("Supply Chain", ["supply chain", "Lean", "SAP", "logistique"]),
    ]
    companies = ["TotalEnergies", "BNP Paribas", "Airbus", "L'Oréal", "Capgemini"]
    countries = ["Allemagne", "États-Unis", "Japon", "Brésil", "Singapour"]
    cities    = ["Berlin", "New York", "Tokyo", "São Paulo", "Singapour"]

    offers = []
    for i in range(n):
        sector, skills = sectors[i % len(sectors)]
        offers.append({
            "id":               f"SAMPLE-{i + 1:04d}",
            "title":            f"VIE - {sector} - {companies[i % len(companies)]}",
            "description":      (
                f"Mission VIE en {sector} chez {companies[i % len(companies)]}. "
                f"Compétences : {', '.join(skills)}."
            ),
            "company":          companies[i % len(companies)],
            "companyName":      companies[i % len(companies)],
            "city":             cities[i % len(cities)],
            "country":          countries[i % len(countries)],
            "publicationDate":  now[:10],
            "contractDuration": 12 + (i * 3),
            "startDate":        "2026-04-01",
            "missionDuration":  12 + (i * 3),
            "competences":      skills,
            "sourceLabel":      "BF_AZURE_SAMPLE",
        })
    return offers


# ==============================================================================
# ENDPOINT VIABILITY TEST
# ==============================================================================

def test_endpoint_viability() -> bool:
    """Teste l'API Civiweb Azure et affiche un diagnostic détaillé."""
    print("=" * 60)
    print("CIVIWEB AZURE — ENDPOINT VIABILITY TEST")
    print("=" * 60)
    print(f"Search URL : {SEARCH_API_URL}")
    print(f"Details URL: {DETAILS_API_URL}")
    print()

    session = requests.Session()
    payload = {**DEFAULT_SEARCH_PAYLOAD, "limit": 3, "skip": 0}

    try:
        resp = session.post(SEARCH_API_URL, headers=HEADERS,
                            json=payload, timeout=TIMEOUT_SEC)
        print(f"HTTP Status   : {resp.status_code}")
        print(f"Content-Type  : {resp.headers.get('Content-Type', 'N/A')}")

        if resp.status_code in (401, 403):
            print("[ERROR] Accès refusé — vérifier les headers Origin/Referer")
            return False
        if resp.status_code == 429:
            print("[ERROR] Rate limited")
            return False
        if resp.status_code >= 400:
            print(f"[ERROR] HTTP {resp.status_code}")
            print(f"Réponse : {resp.text[:300]}")
            return False

        data = resp.json()
        total = data.get("count", "N/A")
        results = data.get("result", [])
        print(f"Total offres  : {total}")
        print(f"Offres page 0 : {len(results)}")
        if results:
            first = results[0]
            print(f"Champs dispo  : {list(first.keys())[:10]}")
            print(f"Exemple ID    : {first.get('id')}")
            print(f"Exemple titre : {first.get('title', first.get('intituleMission', 'N/A'))}")

        print()
        print("[VIABILITY] PASS — API accessible")
        return True

    except requests.exceptions.Timeout:
        print(f"[ERROR] Timeout après {TIMEOUT_SEC}s")
        return False
    except requests.exceptions.ConnectionError as exc:
        print(f"[ERROR] Connexion échouée : {exc}")
        return False
    except Exception as exc:
        print(f"[ERROR] Inattendu : {exc}")
        return False
    finally:
        session.close()


# ==============================================================================
# ÉCRITURE JSONL — format envelope obligatoire pour ingest_business_france.py
# ==============================================================================

def write_raw_jsonl(
    offers: List[Dict[str, Any]],
    run_id: str,
    fetched_at: str,
    logger: StructuredLogger,
) -> Path:
    """
    Écrit les offres en format envelope JSONL dans RAW_BF_DIR.

    Format de chaque ligne (OBLIGATOIRE pour ingest_business_france.py) :
      {"run_id": "...", "fetched_at": "...", "source_url": "...", "payload": {...}}

    L'ingesteur lit : record.get("payload", {})
    → un objet offer nu silencieusement produit un enregistrement vide.

    Nom du fichier : bf_azure_<run_id>.jsonl
    Never overwrite : exit(1) si le fichier existe déjà.
    """
    RAW_BF_DIR.mkdir(parents=True, exist_ok=True)

    filename = f"bf_azure_{run_id}.jsonl"
    raw_file = RAW_BF_DIR / filename

    if raw_file.exists():
        logger.log("write_error", "error",
                   error=f"Fichier déjà existant : {raw_file} — run_id collision",
                   extra={"catalog_source": "BF_AZURE"})
        sys.exit(1)

    with open(raw_file, "w", encoding="utf-8") as fh:
        for offer in offers:
            envelope = {
                "run_id":     run_id,
                "fetched_at": fetched_at,
                "source_url": SEARCH_API_URL,
                "payload":    offer,
            }
            fh.write(json.dumps(envelope, ensure_ascii=False) + "\n")

    size_kb = raw_file.stat().st_size / 1024
    logger.log("file_written", "success",
               offers_processed=len(offers),
               extra={
                   "catalog_source": "BF_AZURE",
                   "output_file":    raw_file.name,
                   "output_path":    str(raw_file),
                   "size_kb":        round(size_kb, 1),
               })
    return raw_file


# ==============================================================================
# MAIN — cron-friendly, aucun input interactif
# ==============================================================================

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Business France VIE Scraper — API Azure (Civiweb). Cron-safe.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--max-offers", type=int, default=0,
        metavar="N",
        help=f"Limite max d'offres (0 = toutes, cap sécurité : {SAFETY_CAP_OFFERS})",
    )
    parser.add_argument(
        "--skip-details", action="store_true",
        help="Ne pas enrichir avec les détails (catalog seul, plus rapide)",
    )
    parser.add_argument(
        "--sample", action="store_true",
        help="Mode test : 5 offres synthétiques, aucun appel réseau",
    )
    parser.add_argument(
        "--test", action="store_true",
        help="Tester la viabilité de l'endpoint seulement",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Exécuter le scrape mais ne pas écrire sur disque",
    )
    args = parser.parse_args()

    # run_id unique et immuable pour ce run
    run_id     = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    logger     = StructuredLogger("scrape_bf_azure", run_id)
    start_time = time.time()

    # ── MODE TEST ──────────────────────────────────────────────────────────────
    if args.test:
        ok = test_endpoint_viability()
        sys.exit(0 if ok else 1)

    # ── Limite effective ───────────────────────────────────────────────────────
    max_offers = args.max_offers or MAX_OFFERS
    max_offers = min(max_offers, SAFETY_CAP_OFFERS)

    skip_details = args.skip_details or SKIP_DETAILS

    logger.log("scraper_start", "started",
               extra={
                   "catalog_source": "BF_AZURE",
                   "max_offers":     max_offers,
                   "skip_details":   skip_details,
                   "max_workers":    MAX_WORKERS,
                   "sleep_sec":      SLEEP_SEC,
                   "sample_mode":    args.sample,
                   "dry_run":        args.dry_run,
               })

    # ── MODE SAMPLE ────────────────────────────────────────────────────────────
    if args.sample:
        raw_offers = generate_sample_offers(5)
        final_offers = [normalize_payload(o) for o in raw_offers]
        logger.log("page_fetched", "success",
                   extra={"catalog_source": "BF_AZURE", "page_num": 0,
                          "offers_found_on_page": len(final_offers),
                          "cumulative_total": len(final_offers), "mode": "sample"})

    # ── MODE LIVE ──────────────────────────────────────────────────────────────
    else:
        session = requests.Session()
        counter: Dict[str, int] = {"total": 0, "failed": 0}

        try:
            # 1. Catalog
            catalog_offers, api_total = fetch_catalog(
                session, counter, logger, max_offers
            )

            if not catalog_offers:
                logger.log("scraper_summary", "error",
                           duration_ms=int((time.time() - start_time) * 1000),
                           offers_processed=0,
                           error="Aucune offre récupérée depuis le catalog",
                           extra={"catalog_source": "BF_AZURE",
                                  "api_total": api_total,
                                  "hint": "Vérifier endpoint avec --test"})
                sys.exit(1)

            # 2. Détails (optionnel)
            if skip_details:
                enriched = catalog_offers
            else:
                enriched = enrich_with_details(catalog_offers, session, counter, logger)

            final_offers = [normalize_payload(o) for o in enriched]

        except AbortScrapeError as exc:
            logger.log("abort", "error",
                       error=str(exc),
                       duration_ms=int((time.time() - start_time) * 1000),
                       extra={
                           "catalog_source":    "BF_AZURE",
                           "reason":            "error_rate_exceeded",
                           "http_errors_count": counter["failed"],
                           "total_attempts":    counter["total"],
                       })
            sys.exit(1)
        finally:
            session.close()

    # ── Validation volume minimum ──────────────────────────────────────────────
    if len(final_offers) < MIN_OFFERS_SUCCESS:
        logger.log("scraper_summary", "warn",
                   duration_ms=int((time.time() - start_time) * 1000),
                   offers_processed=len(final_offers),
                   error=f"Seulement {len(final_offers)} offres — sous le seuil {MIN_OFFERS_SUCCESS}",
                   extra={"catalog_source": "BF_AZURE"})
        sys.exit(2)

    # ── Écriture JSONL ─────────────────────────────────────────────────────────
    if args.dry_run:
        logger.log("dry_run", "success",
                   offers_processed=len(final_offers),
                   extra={"catalog_source": "BF_AZURE",
                          "note": "dry-run — aucun fichier écrit"})
        sys.exit(0)

    scraped_at = datetime.now(timezone.utc).isoformat()
    pg_result = persist_raw_offers("business_france", final_offers, scraped_at)
    if pg_result.error:
        logger.log(
            "persist_raw_offers_pg",
            "warning",
            error=pg_result.error,
            offers_processed=pg_result.persisted,
            extra={"source": "business_france"},
        )
    else:
        logger.log(
            "persist_raw_offers_pg",
            "success",
            offers_processed=pg_result.persisted,
            extra={"source": "business_france"},
        )

    raw_file = write_raw_jsonl(final_offers, run_id, scraped_at, logger)

    # ── Résumé final ───────────────────────────────────────────────────────────
    duration_ms = int((time.time() - start_time) * 1000)
    logger.log("scraper_summary", "success",
               duration_ms=duration_ms,
               offers_processed=len(final_offers),
               extra={
                   "catalog_source":        "BF_AZURE",
                   "total_offers_found":    len(final_offers),
                   "output_file":           raw_file.name,
                   "output_path":           str(raw_file),
               })


if __name__ == "__main__":
    main()
