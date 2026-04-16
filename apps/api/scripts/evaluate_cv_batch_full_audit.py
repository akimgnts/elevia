from __future__ import annotations

import csv
import io
import json
import re
import signal
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from api.main import app
from api.utils.pdf_text import PdfTextError, extract_text_from_pdf
from api.utils.inbox_catalog import load_catalog_offers
from compass.explainability.explanation_builder import build_offer_explanation
from compass.explainability.semantic_explanation_builder import build_semantic_explainability
from compass.extraction.precanonical_recovery import build_precanonical_recovery
from compass.offer.offer_intelligence import build_offer_intelligence, is_role_domain_compatible
from compass.pipeline.contracts import ParseFilePipelineRequest
from compass.pipeline.profile_parse_pipeline import build_parse_file_response_payload
from compass.profile_structurer import structure_profile_text_v1
from compass.scoring.scoring_v2 import build_scoring_v2
from compass.scoring.scoring_v3 import build_scoring_v3
from matching import MatchingEngine
from matching.extractors import extract_profile

REPO_ROOT = Path(__file__).resolve().parents[3]
CV_DIR = Path('/Users/akimguentas/Downloads/cvtest')
OUT_DIR = REPO_ROOT / 'apps' / 'api' / 'data' / 'eval'
OUT_JSON = OUT_DIR / 'cv_batch_full_audit.json'
OUT_CSV = OUT_DIR / 'cv_batch_full_audit.csv'
OUT_MD = OUT_DIR / 'cv_batch_full_audit_report.md'
SUPPORTED_SUFFIXES = {'.pdf', '.txt'}
GENERIC_VERBS = {'faire', 'travailler', 'participer', 'aider', 'assister'}
MIN_MATCHING_SCORE = 10
GATED_BASE_CANDIDATES = 20
TOP_CANDIDATES_FOR_SEMANTIC = 10


class AuditTimeout(Exception):
    pass


def _slug(value: str) -> str:
    return ''.join(ch.lower() if ch.isalnum() else '-' for ch in str(value)).strip('-') or 'cv'


def _normalize(text: Any) -> str:
    return re.sub(r'\s+', ' ', str(text or '')).strip().lower()


def _sample(values: list[Any], limit: int = 5) -> list[Any]:
    return values[:limit]


def _timeout_handler(signum, frame):  # type: ignore[no-untyped-def]
    raise AuditTimeout('timeout')


def _with_timeout(seconds: int, fn, *args, **kwargs):  # type: ignore[no-untyped-def]
    previous = signal.signal(signal.SIGALRM, _timeout_handler)
    signal.alarm(seconds)
    try:
        return fn(*args, **kwargs)
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, previous)


def _content_type_for_path(path: Path) -> str:
    if path.suffix.lower() == '.pdf':
        return 'application/pdf'
    if path.suffix.lower() == '.txt':
        return 'text/plain'
    if path.suffix.lower() == '.docx':
        return 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    return 'application/octet-stream'


def _pdf_page_count(data: bytes) -> int:
    try:
        from pypdf import PdfReader  # type: ignore
    except Exception:
        return 0
    try:
        return len(PdfReader(io.BytesIO(data)).pages)
    except Exception:
        return 0


def _inventory_file(path: Path) -> dict[str, Any]:
    suffix = path.suffix.lower()
    data = path.read_bytes()
    pages = _pdf_page_count(data) if suffix == '.pdf' else 0
    text = ''
    status = 'failed'
    text_extracted = False
    error = None
    if suffix == '.pdf':
        try:
            text = extract_text_from_pdf(data)
            text_extracted = bool(text.strip())
            status = 'ok' if text_extracted else 'partial'
        except PdfTextError as exc:
            error = {'code': exc.code, 'message': exc.message}
            status = 'failed'
        except Exception as exc:
            error = {'code': type(exc).__name__, 'message': str(exc)}
            status = 'failed'
    elif suffix == '.txt':
        try:
            text = path.read_text(encoding='utf-8', errors='ignore')
            text_extracted = bool(text.strip())
            status = 'ok' if text_extracted else 'partial'
        except Exception as exc:
            error = {'code': type(exc).__name__, 'message': str(exc)}
            status = 'failed'
    else:
        status = 'failed'
        error = {'code': 'UNSUPPORTED_FILE', 'message': f'Unsupported suffix: {suffix}'}

    return {
        'file': path.name,
        'path': str(path),
        'type': suffix.lstrip('.'),
        'size_bytes': path.stat().st_size,
        'pages': pages,
        'text_extracted': text_extracted,
        'text_length': len(text),
        'status': status,
        'error': error,
        'text_preview': text[:500],
        '_text': text,
    }


def _safe_parse(path: Path) -> dict[str, Any]:
    return build_parse_file_response_payload(
        ParseFilePipelineRequest(
            request_id=f'cv-batch:{path.name}',
            raw_filename=path.name,
            content_type=_content_type_for_path(path),
            file_bytes=path.read_bytes(),
            enrich_llm=0,
        )
    )


def _build_persisted_analyze_profile(parse_result: dict[str, Any]) -> dict[str, Any]:
    profile = dict(parse_result.get('profile') or {})
    if isinstance(parse_result.get('canonical_skills'), list):
        profile['canonical_skills'] = parse_result['canonical_skills']
    if isinstance(parse_result.get('canonical_skills_count'), int):
        profile['canonical_skills_count'] = parse_result['canonical_skills_count']
    if isinstance(parse_result.get('enriched_signals'), list):
        profile['enriched_signals'] = parse_result['enriched_signals']
    if isinstance(parse_result.get('concept_signals'), list):
        profile['concept_signals'] = parse_result['concept_signals']
    if parse_result.get('profile_intelligence') and not profile.get('profile_intelligence'):
        profile['profile_intelligence'] = parse_result['profile_intelligence']
    if parse_result.get('profile_intelligence_ai_assist') and not profile.get('profile_intelligence_ai_assist'):
        profile['profile_intelligence_ai_assist'] = parse_result['profile_intelligence_ai_assist']
    return profile


def _unique_strings(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        trimmed = str(value or '').strip()
        if not trimmed:
            continue
        if trimmed in seen:
            continue
        seen.add(trimmed)
        result.append(trimmed)
    return result


def _build_matching_profile(profile: dict[str, Any], profile_id: str) -> dict[str, Any]:
    explicit_skills = profile.get('matching_skills') if isinstance(profile.get('matching_skills'), list) else profile.get('skills') if isinstance(profile.get('skills'), list) else []
    unmapped_skills = []
    if isinstance(profile.get('unmapped_skills_high_confidence'), list):
        unmapped_skills = [str(item.get('raw_skill') or '') for item in profile.get('unmapped_skills_high_confidence') if isinstance(item, dict)]
    detected_tools: list[str] = []
    capabilities = []
    if isinstance(profile.get('detected_capabilities'), list):
        for cap in profile['detected_capabilities']:
            if not isinstance(cap, dict):
                continue
            name = str(cap.get('name') or '').strip()
            if name:
                capabilities.append(name)
            detected_tools.extend(str(tool).strip() for tool in (cap.get('tools_detected') or []) if str(tool).strip())

    matching_skills = _unique_strings([*explicit_skills, *unmapped_skills, *detected_tools])
    matching_skills = sorted(_normalize(skill) for skill in matching_skills if _normalize(skill))
    skills_source = 'user' if matching_skills else 'none'
    capabilities_only = _unique_strings(capabilities)
    if not matching_skills and capabilities_only:
        matching_skills = sorted(_normalize(skill) for skill in capabilities_only if _normalize(skill))
        skills_source = 'capabilities_only'

    return {
        'id': profile_id,
        'matching_skills': matching_skills,
        'skills_uri': profile.get('skills_uri') if isinstance(profile.get('skills_uri'), list) else None,
        'capabilities': sorted(_normalize(cap) for cap in capabilities_only if _normalize(cap)),
        'languages': profile.get('languages') or [],
        'education': profile.get('education'),
        'education_summary': profile.get('education_summary'),
        'preferred_countries': profile.get('preferred_countries') or [],
        'detected_capabilities': profile.get('detected_capabilities'),
        'skills_source': skills_source,
        'canonical_skills': profile.get('canonical_skills') if isinstance(profile.get('canonical_skills'), list) else None,
        'canonical_skills_count': profile.get('canonical_skills_count') if isinstance(profile.get('canonical_skills_count'), int) else None,
        'enriched_signals': profile.get('enriched_signals') if isinstance(profile.get('enriched_signals'), list) else None,
        'concept_signals': profile.get('concept_signals') if isinstance(profile.get('concept_signals'), list) else None,
        'profile_intelligence': profile.get('profile_intelligence') if isinstance(profile.get('profile_intelligence'), dict) else None,
        'profile_intelligence_ai_assist': profile.get('profile_intelligence_ai_assist') if isinstance(profile.get('profile_intelligence_ai_assist'), dict) else None,
        'metadata': {
            'source': 'profileMatchingV1',
            'skills_source': skills_source,
            'canonical_skills_count': profile.get('canonical_skills_count') if isinstance(profile.get('canonical_skills_count'), int) else 0,
            'enriched_signal_count': len(profile.get('enriched_signals') or []),
            'concept_signal_count': len(profile.get('concept_signals') or []),
        },
    }


def _canonical_skill_labels(parse_result: dict[str, Any]) -> list[str]:
    labels: list[str] = []
    for item in parse_result.get('canonical_skills') or []:
        if isinstance(item, dict):
            label = item.get('canonical_label') or item.get('label') or item.get('raw')
            if label:
                labels.append(str(label))
    return labels


def _sample_signal_text(values: list[dict[str, Any]] | list[Any], key_order: tuple[str, ...] = ('concept', 'normalized', 'raw', 'label')) -> list[str]:
    out: list[str] = []
    for item in values or []:
        if isinstance(item, dict):
            value = None
            for key in key_order:
                if item.get(key):
                    value = item.get(key)
                    break
            if value:
                out.append(str(value))
        elif item:
            out.append(str(item))
    return out


def _classify_pipeline(inventory: dict[str, Any], parse_result: dict[str, Any], matching_profile: dict[str, Any]) -> tuple[str, list[str]]:
    reasons: list[str] = []
    if not inventory.get('text_extracted') or inventory.get('text_length', 0) == 0:
        return 'TEXT_FAILURE', ['no_text_extracted']

    raw_detected = int(parse_result.get('raw_detected') or 0)
    canonical_count = int(parse_result.get('canonical_skills_count') or parse_result.get('canonical_count') or 0)
    enriched_count = len(parse_result.get('enriched_signals') or [])
    concept_count = len(parse_result.get('concept_signals') or [])
    matching_count = len(matching_profile.get('matching_skills') or [])

    if raw_detected == 0 and not (parse_result.get('skills_raw') or parse_result.get('raw_tokens')):
        return 'RAW_EXTRACTION_FAILURE', ['text_extracted_but_no_raw_skills']

    if raw_detected > 0 and canonical_count == 0 and (enriched_count > 0 or concept_count > 0):
        return 'ENRICHED_ONLY', ['canonical_zero_but_enriched_present']

    if raw_detected > 0 and canonical_count <= max(1, raw_detected // 10) and (enriched_count > canonical_count or concept_count > 0):
        reasons.append('canonical_mapping_thin_vs_raw')
        return 'CANONICAL_COLLAPSE', reasons

    if (parse_result.get('canonical_skills') or parse_result.get('enriched_signals') or parse_result.get('concept_signals')) and matching_count == 0:
        return 'FRONTEND_PROFILE_DEGRADATION', ['rich_parse_but_empty_matching_profile']

    return 'GOOD_PARSE', reasons


def _coherent_offer(item: dict[str, Any]) -> bool:
    semantic = item.get('semantic_explainability') or {}
    role_alignment = ((semantic.get('role_alignment') or {}).get('alignment') or '').lower()
    shared_domains = list(((semantic.get('domain_alignment') or {}).get('shared_domains') or []))
    return role_alignment == 'high' or (role_alignment == 'medium' and bool(shared_domains))


def _false_positive_offer(item: dict[str, Any]) -> bool:
    semantic = item.get('semantic_explainability') or {}
    role_alignment = ((semantic.get('role_alignment') or {}).get('alignment') or '').lower()
    shared_domains = list(((semantic.get('domain_alignment') or {}).get('shared_domains') or []))
    matched_signals = list(((semantic.get('signal_alignment') or {}).get('matched_signals') or []))
    return role_alignment == 'low' and not shared_domains and len(matched_signals) <= 1


def _matching_payload_profile(parse_result: dict[str, Any], file_stem: str) -> dict[str, Any]:
    persisted = _build_persisted_analyze_profile(parse_result)
    return _build_matching_profile(persisted, profile_id=_slug(file_stem))


def _structured_profile_for_apply_pack(cv_text: str, parse_result: dict[str, Any], file_stem: str) -> dict[str, Any]:
    structured = structure_profile_text_v1(cv_text, debug=True)
    education_values: list[str] = []
    for edu in structured.education:
        parts = [edu.degree, edu.field, edu.institution]
        label = ' — '.join(part for part in parts if part)
        if label:
            education_values.append(label)
    languages = parse_result.get('profile', {}).get('languages') or []
    skills = list(parse_result.get('profile', {}).get('skills') or parse_result.get('skills_canonical') or parse_result.get('skills_raw') or [])
    return {
        'id': _slug(file_stem),
        'name': file_stem,
        'skills': [str(skill) for skill in skills[:20]],
        'experiences': [exp.model_dump() for exp in structured.experiences],
        'education': education_values,
        'languages': [str(lang) for lang in languages if str(lang).strip()],
        'cv_quality': structured.cv_quality.model_dump(),
        'structured_sections': structured.extracted_sections or {},
        'extracted_tools': structured.extracted_tools,
    }


def _apply_pack_status(document: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    doc = document.get('document') or {}
    cv = doc.get('cv') or {}
    debug = doc.get('debug') or {}
    experiences = list(cv.get('experiences') or [])
    bullets = [bullet for exp in experiences for bullet in (exp.get('bullets') or [])]
    verbs = []
    for bullet in bullets:
        first = str(bullet).strip().split(' ')[0].lower() if str(bullet).strip() else ''
        verbs.append(first)
    generic_hits = [verb for verb in verbs if verb in GENERIC_VERBS]
    matched_keywords = list(((doc.get('ats_notes') or {}).get('matched_keywords') or []))
    has_debug = bool(debug.get('experience_scores')) and bool(debug.get('selected_verbs'))
    layout_ok = cv.get('layout') == 'single_column'

    audit = {
        'experience_count': len(experiences),
        'bullets_count': len(bullets),
        'matched_keywords_count': len(matched_keywords),
        'has_debug': has_debug,
        'layout': cv.get('layout'),
        'generic_verb_hits': generic_hits,
        'selected_experience_titles': [exp.get('role') for exp in experiences],
        'skills': list(cv.get('skills') or []),
    }

    if not experiences or not bullets or not layout_ok:
        return 'BROKEN', audit
    if has_debug and len(experiences) >= 2 and len(matched_keywords) >= 2 and not generic_hits:
        return 'STRONG', audit
    if has_debug and len(experiences) >= 1 and not generic_hits:
        return 'USABLE', audit
    return 'WEAK', audit


def _call_inbox(client: TestClient, file_stem: str, matching_profile: dict[str, Any]) -> dict[str, Any]:
    raise NotImplementedError('Use _call_inbox_equivalent_backend')


def _build_matching_runtime() -> dict[str, Any]:
    catalog = load_catalog_offers()
    engine = MatchingEngine(catalog)
    return {
        'catalog': catalog,
        'engine': engine,
        'offer_intelligence_cache': {},
    }


def _call_inbox_equivalent_backend(runtime: dict[str, Any], file_stem: str, matching_profile: dict[str, Any]) -> dict[str, Any]:
    catalog = runtime['catalog']
    engine: MatchingEngine = runtime['engine']
    offer_intelligence_cache: dict[str, dict[str, Any]] = runtime['offer_intelligence_cache']

    try:
        extracted = extract_profile(matching_profile)
    except Exception as exc:
        return {
            'status_code': 500,
            'ok': False,
            'error': f'extract_profile_failed:{type(exc).__name__}:{exc}',
        }

    profile_intelligence = matching_profile.get('profile_intelligence') or {}
    base_rows: list[dict[str, Any]] = []
    for offer in catalog:
        offer_id = str(offer.get('id') or '')
        if not offer_id:
            continue
        result = engine.score_offer(extracted, offer)
        if int(result.score or 0) < MIN_MATCHING_SCORE:
            continue
        base_rows.append({
            'offer': offer,
            'offer_id': offer_id,
            'score': int(result.score or 0),
            'match_debug': result.match_debug or {},
        })
    base_rows.sort(key=lambda row: row['score'], reverse=True)
    scored_rows = base_rows[:GATED_BASE_CANDIDATES]
    gated_candidates: list[dict[str, Any]] = []
    gated_out = 0
    for row in scored_rows:
        offer_id = row['offer_id']
        offer_intelligence = offer_intelligence_cache.get(offer_id)
        if offer_intelligence is None:
            offer_intelligence = build_offer_intelligence(offer=row['offer'])
            offer_intelligence_cache[offer_id] = offer_intelligence
        if profile_intelligence and not is_role_domain_compatible(
            profile_intelligence=profile_intelligence,
            offer_intelligence=offer_intelligence,
        ):
            gated_out += 1
            continue
        row['offer_intelligence'] = offer_intelligence
        gated_candidates.append(row)

    semantic_rows: list[dict[str, Any]] = []
    for row in gated_candidates[:TOP_CANDIDATES_FOR_SEMANTIC]:
        offer = row['offer']
        offer_labels = [
            skill.get('label') if isinstance(skill, dict) else str(skill)
            for skill in (offer.get('skills_display') or offer.get('skills') or [])
        ]
        profile_labels = list(matching_profile.get('matching_skills') or matching_profile.get('skills') or [])
        explanation = build_offer_explanation(
            row['match_debug'],
            score=row['score'],
            confidence=None,
            profile_effective_skills=profile_labels,
            job_required_skills=offer_labels,
        )
        semantic = build_semantic_explainability(
            profile_intelligence=profile_intelligence,
            offer_intelligence=row['offer_intelligence'],
            explanation=explanation,
        )
        scoring_v2 = build_scoring_v2(
            profile_intelligence=profile_intelligence,
            offer_intelligence=row['offer_intelligence'],
            semantic_explainability=semantic,
            matching_score=float(row['score']) / 100.0,
        )
        scoring_v3 = build_scoring_v3(
            profile_intelligence=profile_intelligence,
            offer_intelligence=row['offer_intelligence'],
            semantic_explainability=semantic,
            explanation=explanation,
            matching_score=float(row['score']) / 100.0,
        )
        semantic_rows.append({
            'offer_id': row['offer_id'],
            'title': offer.get('title'),
            'company': offer.get('company'),
            'score': row['score'],
            'matched_skills': list(explanation.get('strengths') or []),
            'missing_skills': list(explanation.get('gaps') or []),
            'offer_cluster': offer.get('offer_cluster'),
            'explanation': explanation,
            'offer_intelligence': row['offer_intelligence'],
            'semantic_explainability': semantic,
            'scoring_v2': scoring_v2,
            'scoring_v3': scoring_v3,
        })

    semantic_rows.sort(
        key=lambda item: (
            int(((item.get('scoring_v3') or {}).get('score_pct')) or -1),
            int(item.get('score') or 0),
        ),
        reverse=True,
    )
    top5 = semantic_rows[:5]
    return {
        'status_code': 200,
        'ok': True,
        'offers_count': len(gated_candidates),
        'total_matched': len(gated_candidates),
        'gated_out_count': gated_out,
        'base_candidate_count': len(base_rows),
        'top5': [
            {
                'offer_id': item.get('offer_id'),
                'title': item.get('title'),
                'company': item.get('company'),
                'score': item.get('score'),
                'score_v2': ((item.get('scoring_v2') or {}).get('score_pct')),
                'score_v3': ((item.get('scoring_v3') or {}).get('score_pct')),
                'offer_role': ((item.get('offer_intelligence') or {}).get('dominant_role_block')),
                'offer_domains': ((item.get('offer_intelligence') or {}).get('dominant_domains') or []),
                'role_alignment': (((item.get('semantic_explainability') or {}).get('role_alignment') or {}).get('alignment')),
                'shared_domains': (((item.get('semantic_explainability') or {}).get('domain_alignment') or {}).get('shared_domains') or []),
                'alignment_summary': ((item.get('semantic_explainability') or {}).get('alignment_summary')),
                'summary_reason': ((item.get('explanation') or {}).get('summary_reason')),
            }
            for item in top5
        ],
        'top5_titles': [item.get('title') for item in top5],
        'top5_score_v3': [((item.get('scoring_v3') or {}).get('score_pct')) for item in top5],
        'coherent_top5_count': sum(1 for item in top5 if _coherent_offer(item)),
        'false_positive_top5_count': sum(1 for item in top5 if _false_positive_offer(item)),
        'pool_empty': len(gated_candidates) == 0,
        'raw_response_shape': {
            'keys': ['profile_id', 'items', 'total_matched'],
            'item_keys_sample': sorted(list(top5[0].keys())) if top5 else [],
            'mode': f'equivalent_backend_top{GATED_BASE_CANDIDATES}_base_candidates',
        },
        'items': semantic_rows,
    }


def _evaluate_apply_pack(client: TestClient, file_stem: str, parse_result: dict[str, Any], inbox_result: dict[str, Any], cv_text: str) -> dict[str, Any]:
    if not inbox_result.get('ok'):
        return {'status': 'BROKEN', 'reason': 'inbox_failed', 'evaluations': []}

    structured_profile = _structured_profile_for_apply_pack(cv_text, parse_result, file_stem)
    coherent_items = [item for item in inbox_result.get('items') or [] if _coherent_offer(item)]
    chosen = coherent_items[:1]
    if not chosen:
        return {'status': 'BROKEN', 'reason': 'no_coherent_offer_for_apply_pack', 'evaluations': []}

    evaluations = []
    best_status_rank = {'BROKEN': 0, 'WEAK': 1, 'USABLE': 2, 'STRONG': 3}
    best_status = 'BROKEN'

    for item in chosen:
        offer_id = item.get('offer_id')
        response = client.post(
            '/documents/cv/for-offer',
            json={
                'offer_id': offer_id,
                'profile': {
                    'id': structured_profile['id'],
                    'skills': structured_profile['skills'],
                    'experiences': structured_profile['experiences'],
                    'education': structured_profile['education'],
                    'languages': structured_profile['languages'],
                    'name': structured_profile['name'],
                },
                'lang': 'fr',
                'context': {
                    'matched_skills': item.get('matched_skills') or [],
                    'missing_skills': item.get('missing_skills') or [],
                    'offer_cluster': item.get('offer_cluster'),
                },
            },
        )
        if response.status_code != 200:
            evaluations.append({
                'offer_id': offer_id,
                'title': item.get('title'),
                'status': 'BROKEN',
                'http_status': response.status_code,
                'error': response.text[:500],
            })
            continue
        body = response.json()
        status, audit = _apply_pack_status(body)
        if best_status_rank[status] > best_status_rank[best_status]:
            best_status = status
        evaluations.append({
            'offer_id': offer_id,
            'title': item.get('title'),
            'status': status,
            'preview_excerpt': (body.get('preview_text') or '')[:600],
            'document_debug': body.get('document', {}).get('debug') or {},
            'audit': audit,
        })

    return {
        'status': best_status,
        'reason': None,
        'structured_profile': {
            'experience_count': len(structured_profile['experiences']),
            'education_count': len(structured_profile['education']),
            'skills_count': len(structured_profile['skills']),
            'cv_quality': structured_profile['cv_quality'],
        },
        'evaluations': evaluations,
    }


def _sector_from_parse(parse_result: dict[str, Any]) -> str:
    intel = parse_result.get('profile_intelligence') or {}
    domains = list(intel.get('dominant_domains') or [])
    if domains:
        return domains[0]
    role = str(intel.get('dominant_role_block') or '').strip()
    return role or 'unknown'


def _audit_one_file(client: TestClient, runtime: dict[str, Any], inventory: dict[str, Any]) -> dict[str, Any]:
    base = {k: v for k, v in inventory.items() if not k.startswith('_')}
    if inventory['type'] not in {'pdf', 'txt'} or not inventory['text_extracted']:
        base['classification'] = 'TEXT_FAILURE'
        base['pipeline'] = None
        base['matching'] = None
        base['apply_pack'] = None
        return base

    try:
        parse_result = _with_timeout(45, _safe_parse, Path(inventory['path']))
    except AuditTimeout:
        base['classification'] = 'TEXT_FAILURE'
        base['pipeline'] = {'error': 'parse_timeout', 'error_detail': 'parse stage exceeded timeout'}
        base['matching'] = None
        base['apply_pack'] = None
        return base
    except Exception as exc:
        base['classification'] = 'TEXT_FAILURE'
        base['pipeline'] = {'error': type(exc).__name__, 'error_detail': str(exc)}
        base['matching'] = None
        base['apply_pack'] = None
        return base

    matching_profile = _matching_payload_profile(parse_result, Path(inventory['path']).stem)
    classification, classification_reasons = _classify_pipeline(inventory, parse_result, matching_profile)

    try:
        structured = _with_timeout(20, structure_profile_text_v1, inventory['_text'], debug=True)
    except AuditTimeout:
        structured = structure_profile_text_v1('', debug=False)
    precanonical_recovery = build_precanonical_recovery(inventory['_text'])
    parsed_pipeline = {
        'extraction': {
            'text_length': len(inventory['_text']),
            'sections_detected': sorted(list((structured.extracted_sections or {}).keys())),
            'cv_quality': structured.cv_quality.model_dump(),
        },
        'precanonical_recovery': {
            'candidate_phrases_count': int((precanonical_recovery.get('stats') or {}).get('candidate_phrases_count', 0)),
            'relevant_phrases_count': int((precanonical_recovery.get('stats') or {}).get('relevant_phrases_count', 0)),
            'relevant_phrases_sample': _sample(list(precanonical_recovery.get('relevant_phrases') or []), 8),
        },
        'skill_extraction': {
            'raw_skill_candidates_count': int(parse_result.get('raw_detected') or 0),
            'raw_skill_candidates_sample': _sample([str(s) for s in (parse_result.get('skills_raw') or [])], 8),
            'raw_tokens_sample': _sample([str(s) for s in (parse_result.get('raw_tokens') or [])], 8),
        },
        'canonicalisation': {
            'canonical_skills_count': int(parse_result.get('canonical_skills_count') or parse_result.get('canonical_count') or 0),
            'canonical_skills_sample': _sample(_canonical_skill_labels(parse_result), 8),
            'unresolved_count': int(parse_result.get('skills_unmapped_count') or 0),
            'near_match_count': int(parse_result.get('skill_proximity_count') or 0),
            'dropped_noise_count': int(parse_result.get('filtered_out') or 0),
        },
        'enriched': {
            'enriched_signals_count': len(parse_result.get('enriched_signals') or []),
            'enriched_signals_sample': _sample(_sample_signal_text(parse_result.get('enriched_signals') or []), 8),
        },
        'concept': {
            'concept_signals_count': len(parse_result.get('concept_signals') or []),
            'concept_signals_sample': _sample(_sample_signal_text(parse_result.get('concept_signals') or []), 8),
        },
        'profile_intelligence': {
            'dominant_role_block': (parse_result.get('profile_intelligence') or {}).get('dominant_role_block'),
            'secondary_role_blocks': (parse_result.get('profile_intelligence') or {}).get('secondary_role_blocks') or [],
            'dominant_domains': (parse_result.get('profile_intelligence') or {}).get('dominant_domains') or [],
            'top_profile_signals': (parse_result.get('profile_intelligence') or {}).get('top_profile_signals') or [],
            'summary': (parse_result.get('profile_intelligence') or {}).get('profile_summary'),
        },
        'persisted_profile_shape': {
            'profile_keys': sorted(list((_build_persisted_analyze_profile(parse_result)).keys())),
            'matching_profile_keys': sorted(list(matching_profile.keys())),
            'matching_skills_count': len(matching_profile.get('matching_skills') or []),
            'skills_uri_count': len(matching_profile.get('skills_uri') or []),
            'canonical_preserved': bool(matching_profile.get('canonical_skills')),
            'enriched_preserved': bool(matching_profile.get('enriched_signals')),
            'concept_preserved': bool(matching_profile.get('concept_signals')),
            'profile_intelligence_preserved': bool(matching_profile.get('profile_intelligence')),
            'rich_or_degraded': 'rich' if any([
                bool(matching_profile.get('canonical_skills')),
                bool(matching_profile.get('enriched_signals')),
                bool(matching_profile.get('concept_signals')),
                bool(matching_profile.get('profile_intelligence')),
            ]) else 'degraded',
        },
        'classification_reasons': classification_reasons,
    }

    try:
        inbox_result = _with_timeout(90, _call_inbox_equivalent_backend, runtime, Path(inventory['path']).stem, matching_profile)
    except AuditTimeout:
        inbox_result = {
            'status_code': 500,
            'ok': False,
            'error': 'matching_timeout',
            'offers_count': 0,
            'total_matched': 0,
            'pool_empty': True,
            'top5': [],
            'top5_titles': [],
            'top5_score_v3': [],
            'coherent_top5_count': 0,
            'false_positive_top5_count': 0,
            'raw_response_shape': {'mode': 'matching_timeout'},
        }
    if classification != 'TEXT_FAILURE':
        try:
            apply_pack = _with_timeout(
                45,
                _evaluate_apply_pack,
                client,
                Path(inventory['path']).stem,
                parse_result,
                inbox_result,
                inventory['_text'],
            )
        except AuditTimeout:
            apply_pack = {'status': 'BROKEN', 'reason': 'apply_pack_timeout', 'evaluations': []}
    else:
        apply_pack = None

    base.update({
        'classification': classification,
        'sector': _sector_from_parse(parse_result),
        'pipeline': parsed_pipeline,
        'matching': {
            k: v for k, v in inbox_result.items() if k != 'items'
        },
        'apply_pack': apply_pack,
    })
    return base


def _score_bucket(score: int | None) -> str:
    if score is None:
        return 'none'
    if score > 70:
        return '>70'
    if score >= 50:
        return '50-70'
    return '<50'


def _metrics_from_audits(audits: list[dict[str, Any]]) -> dict[str, Any]:
    exploitable = [item for item in audits if item.get('classification') != 'TEXT_FAILURE']
    top_scores = []
    for item in exploitable:
        top = (item.get('matching') or {}).get('top5_score_v3') or []
        top_score = next((score for score in top if isinstance(score, int)), None)
        top_scores.append({'file': item['file'], 'score': top_score, 'sector': item.get('sector') or 'unknown'})

    buckets = Counter(_score_bucket(entry['score']) for entry in top_scores)
    low_scored_sectors = Counter(entry['sector'] for entry in top_scores if entry['score'] is not None and entry['score'] < 50)
    matching_timeout_files = [item['file'] for item in exploitable if (item.get('matching') or {}).get('error') == 'matching_timeout']
    pool_empty = [
        item['file']
        for item in exploitable
        if (item.get('matching') or {}).get('pool_empty') and (item.get('matching') or {}).get('error') != 'matching_timeout'
    ]
    false_positive_counts = {item['file']: (item.get('matching') or {}).get('false_positive_top5_count', 0) for item in exploitable}
    apply_status = Counter((item.get('apply_pack') or {}).get('status') or 'NOT_RUN' for item in audits)
    classifications = Counter(item.get('classification') or 'UNKNOWN' for item in audits)
    sectors = Counter(item.get('sector') or 'unknown' for item in audits)

    return {
        'tested_count': len(audits),
        'exploitable_count': len(exploitable),
        'failed_count': len([item for item in audits if item.get('classification') == 'TEXT_FAILURE']),
        'represented_sectors': sorted(sectors.keys()),
        'classification_counts': dict(classifications),
        'sector_counts': dict(sectors),
        'score_buckets': dict(buckets),
        'matching_timeout_files': matching_timeout_files,
        'pool_empty_files': pool_empty,
        'false_positive_top5_counts': false_positive_counts,
        'apply_pack_status_counts': dict(apply_status),
        'low_scored_sectors': dict(low_scored_sectors),
        'average_top_score_v3': round(statistics.mean([entry['score'] for entry in top_scores if isinstance(entry['score'], int)]), 1) if any(isinstance(entry['score'], int) for entry in top_scores) else None,
    }


def _top_critical_failures(audits: list[dict[str, Any]]) -> list[str]:
    failures: list[str] = []
    if any(item.get('classification') == 'TEXT_FAILURE' for item in audits):
        failures.append('Certains CV ne passent pas la phase texte, ce qui coupe toute la pipeline en amont.')
    if any(item.get('classification') == 'CANONICAL_COLLAPSE' for item in audits):
        failures.append('La canonicalisation s’effondre sur une partie des CV malgré un signal brut présent.')
    if any((item.get('matching') or {}).get('error') == 'matching_timeout' for item in audits if item.get('matching')):
        failures.append('La pipeline de matching Inbox timeoute encore sur certains CV réels, ce qui bloque le produit avant même le scoring final.')
    if any((item.get('matching') or {}).get('pool_empty') for item in audits if item.get('matching')):
        failures.append('Inbox retourne des pools vides sur des CV exploitables, signe d’un problème de matching/gating/pool offre.')
    if any((item.get('matching') or {}).get('false_positive_top5_count', 0) > 0 for item in audits if item.get('matching')):
        failures.append('Le top 5 remonte encore des faux positifs visibles sur certains profils.')
    if any(((item.get('apply_pack') or {}).get('status') in {'WEAK', 'BROKEN'}) for item in audits):
        failures.append('Le moteur Apply Pack ne produit pas encore un CV miroir crédible sur tous les profils exploitables.')
    while len(failures) < 5:
        failures.append('Pas de cinquième rupture supplémentaire clairement distincte observée sur ce batch.')
    return failures[:5]


def _already_good(audits: list[dict[str, Any]]) -> list[str]:
    good: list[str] = []
    if any(item.get('classification') == 'GOOD_PARSE' for item in audits):
        good.append('La pipeline parse correctement une partie significative des vrais CV et garde des signaux enrichis + concepts.')
    if any((item.get('matching') or {}).get('offers_count', 0) > 0 for item in audits if item.get('matching')):
        good.append('Inbox remonte bien des offres sur les profils exploitables ; le produit ne part pas de zéro réel.')
    if any(((item.get('apply_pack') or {}).get('status') in {'STRONG', 'USABLE'}) for item in audits):
        good.append('Le moteur CV Apply Pack produit déjà des sorties ATS structurées et auditées sur certains cas réels.')
    if any(((item.get('pipeline') or {}).get('persisted_profile_shape') or {}).get('rich_or_degraded') == 'rich' for item in audits if item.get('pipeline')):
        good.append('Le profil persistant conserve maintenant les couches riches utiles à Inbox.')
    return good


def _mvp_action_plan(audits: list[dict[str, Any]]) -> list[dict[str, str]]:
    actions: list[dict[str, str]] = []
    if any(item.get('classification') == 'TEXT_FAILURE' for item in audits):
        actions.append({'fix': 'Stabiliser l’extraction texte PDF', 'pourquoi': 'Sans texte, aucune couche aval ne peut fonctionner.', 'où': 'apps/api/src/api/utils/pdf_text.py + pipeline d’ingestion fichier', 'priorité': 'P1'})
    if any(item.get('classification') in {'CANONICAL_COLLAPSE', 'ENRICHED_ONLY'} for item in audits):
        actions.append({'fix': 'Corriger les pertes entre raw skills et canonicalisation', 'pourquoi': 'Des signaux métier réels sont détectés puis perdus avant matching.', 'où': 'apps/api/src/compass/extraction/* + canonical mapping', 'priorité': 'P1'})
    if any((item.get('matching') or {}).get('error') == 'matching_timeout' for item in audits if item.get('matching')):
        actions.append({'fix': 'Supprimer les timeouts Inbox sur profils réels', 'pourquoi': 'Le produit reste non testable si le matching ne termine pas sur une partie du dataset.', 'où': 'apps/api/src/api/routes/inbox.py + chemin de gating / intelligence offre', 'priorité': 'P1'})
    if any((item.get('matching') or {}).get('pool_empty') for item in audits if item.get('matching')):
        actions.append({'fix': 'Fiabiliser le pool Inbox sur profils réels', 'pourquoi': 'Un pool vide empêche l’évaluation produit même quand le parsing est exploitable.', 'où': 'apps/api/src/api/routes/inbox.py + gating/pool offer path', 'priorité': 'P1'})
    if any((item.get('matching') or {}).get('false_positive_top5_count', 0) > 0 for item in audits if item.get('matching')):
        actions.append({'fix': 'Nettoyer les faux positifs visibles du top 5', 'pourquoi': 'Le produit reste trompeur si les premiers résultats métier sont incohérents.', 'où': 'offer intelligence + gate calibration déjà en place', 'priorité': 'P2'})
    if any(((item.get('apply_pack') or {}).get('status') in {'WEAK', 'BROKEN'}) for item in audits):
        actions.append({'fix': 'Renforcer la matière d’entrée du moteur CV pour les profils réels', 'pourquoi': 'Sans expériences structurées crédibles, Apply Pack reste faible.', 'où': 'bridge profile_structurer -> documents/apply_pack input', 'priorité': 'P2'})
    return actions[:5]


def _final_verdict(audits: list[dict[str, Any]], metrics: dict[str, Any]) -> str:
    if any(item.get('classification') == 'TEXT_FAILURE' for item in audits):
        return 'NEEDS PARSING FIX FIRST'
    if metrics.get('matching_timeout_files') or metrics.get('pool_empty_files'):
        return 'NEEDS MATCHING FIX FIRST'
    if any(item.get('classification') in {'CANONICAL_COLLAPSE', 'ENRICHED_ONLY', 'FRONTEND_PROFILE_DEGRADATION'} for item in audits):
        return 'NEEDS FINAL INTEGRATION PASS'
    return 'READY FOR MVP TESTING'


def _build_markdown_report(audits: list[dict[str, Any]], metrics: dict[str, Any]) -> str:
    top_scores = []
    for item in audits:
        matching = item.get('matching') or {}
        top_scores.append((item['file'], next((score for score in (matching.get('top5_score_v3') or []) if isinstance(score, int)), None)))

    lines: list[str] = []
    verdict = _final_verdict(audits, metrics)
    reliable = 'globalement fiable' if verdict == 'READY FOR MVP TESTING' else 'pas encore globalement fiable'
    lines.append('# CV Batch Full Audit Report')
    lines.append('')
    lines.append('## 1. Executive verdict')
    lines.append(f"La pipeline sur vrais CV est {reliable} pour un test sérieux du MVP.")
    lines.append('')
    lines.append('## 2. Dataset summary')
    lines.append(f"- nombre de CV testés : {metrics['tested_count']}")
    lines.append(f"- nombre exploitables : {metrics['exploitable_count']}")
    lines.append(f"- nombre en échec : {metrics['failed_count']}")
    lines.append(f"- secteurs représentés : {', '.join(metrics['represented_sectors'])}")
    lines.append('')
    lines.append('## 3. Stage-by-stage results')
    lines.append('| file | text_extracted | raw_skills | canonical | enriched | concept | inbox_offers | top_score_v3 | apply_pack_status |')
    lines.append('| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |')
    for item in audits:
        pipeline = item.get('pipeline') or {}
        matching = item.get('matching') or {}
        apply_pack = item.get('apply_pack') or {}
        lines.append(
            f"| {item['file']} | {item['text_extracted']} | {((pipeline.get('skill_extraction') or {}).get('raw_skill_candidates_count') if pipeline else 0) or 0} | {((pipeline.get('canonicalisation') or {}).get('canonical_skills_count') if pipeline else 0) or 0} | {((pipeline.get('enriched') or {}).get('enriched_signals_count') if pipeline else 0) or 0} | {((pipeline.get('concept') or {}).get('concept_signals_count') if pipeline else 0) or 0} | {(matching.get('offers_count') if matching else 0) or 0} | {next((score for score in (matching.get('top5_score_v3') or []) if isinstance(score, int)), None)} | {(apply_pack.get('status') or 'NOT_RUN')} |"
        )
    lines.append('')
    lines.append('## 4. Parsing findings')
    for item in audits:
        if not item.get('pipeline'):
            continue
        pipeline = item['pipeline']
        lines.append(f"- `{item['file']}` — classification `{item['classification']}` ; raw={pipeline['skill_extraction']['raw_skill_candidates_count']} canonical={pipeline['canonicalisation']['canonical_skills_count']} enriched={pipeline['enriched']['enriched_signals_count']} concept={pipeline['concept']['concept_signals_count']}")
    lines.append('')
    lines.append('## 5. Matching findings')
    for item in audits:
        matching = item.get('matching') or {}
        if not matching:
            continue
        lines.append(f"- `{item['file']}` — offers={matching.get('offers_count', 0)} ; top5 coherent={matching.get('coherent_top5_count', 0)}/5 ; false positives={matching.get('false_positive_top5_count', 0)} ; pool_empty={matching.get('pool_empty')} ; error={matching.get('error')}")
    lines.append('')
    lines.append('## 6. Scoring findings')
    lines.append(f"- répartition top score v3 : {json.dumps(metrics['score_buckets'], ensure_ascii=False)}")
    if metrics.get('low_scored_sectors'):
        lines.append(f"- secteurs sous-évalués observés : {json.dumps(metrics['low_scored_sectors'], ensure_ascii=False)}")
    else:
        lines.append('- pas de sous-évaluation sectorielle nette détectée sur ce batch.')
    lines.append('')
    lines.append('## 7. Apply pack findings')
    for item in audits:
        ap = item.get('apply_pack') or {}
        lines.append(f"- `{item['file']}` — status={ap.get('status') or 'NOT_RUN'}")
    lines.append('')
    lines.append('## 8. Top 5 critical failures')
    for failure in _top_critical_failures(audits):
        lines.append(f'- {failure}')
    lines.append('')
    lines.append('## 9. What is already good')
    for good in _already_good(audits):
        lines.append(f'- {good}')
    lines.append('')
    lines.append('## 10. MVP action plan')
    for action in _mvp_action_plan(audits):
        lines.append(f"- fix: {action['fix']} | pourquoi: {action['pourquoi']} | où: {action['où']} | priorité: {action['priorité']}")
    lines.append('')
    lines.append('## 11. Final verdict')
    lines.append(verdict)
    lines.append('')
    return '\n'.join(lines)


def _write_interim_outputs(inventories: list[dict[str, Any]], audits: list[dict[str, Any]]) -> None:
    metrics = _metrics_from_audits(audits)
    output = {
        'source_dir': str(CV_DIR),
        'generated_at': __import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat(),
        'inventories': [{k: v for k, v in item.items() if not k.startswith('_')} for item in inventories if item['file'] != '.DS_Store'],
        'audits': audits,
        'metrics': metrics,
        'top_critical_failures': _top_critical_failures(audits),
        'what_is_already_good': _already_good(audits),
        'mvp_action_plan': _mvp_action_plan(audits),
        'final_verdict': _final_verdict(audits, metrics),
    }
    OUT_JSON.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding='utf-8')


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    client = TestClient(app, raise_server_exceptions=False)
    print('[audit] building matching runtime', flush=True)
    runtime = _build_matching_runtime()

    inventories = []
    for path in sorted(CV_DIR.iterdir(), key=lambda p: p.name.lower()):
        if not path.is_file():
            continue
        if path.name.startswith('.'):
            if path.name != '.DS_Store':
                inventories.append(_inventory_file(path))
            continue
        inventories.append(_inventory_file(path))

    audits = []
    for inventory in inventories:
        if inventory['file'] == '.DS_Store':
            continue
        print(f"[audit] {inventory['file']}", flush=True)
        audit = _audit_one_file(client, runtime, inventory)
        print(
            f"[done] {inventory['file']} class={audit.get('classification')} offers={((audit.get('matching') or {}).get('offers_count'))}",
            flush=True,
        )
        audits.append(audit)
        _write_interim_outputs(inventories, audits)
    metrics = _metrics_from_audits(audits)

    output = json.loads(OUT_JSON.read_text(encoding='utf-8'))

    with OUT_CSV.open('w', encoding='utf-8', newline='') as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=[
                'file', 'type', 'pages', 'text_extracted', 'text_length', 'classification', 'sector',
                'raw_skills', 'canonical', 'enriched', 'concept', 'inbox_offers', 'top_score_v3', 'apply_pack_status'
            ],
        )
        writer.writeheader()
        for item in audits:
            pipeline = item.get('pipeline') or {}
            matching = item.get('matching') or {}
            apply_pack = item.get('apply_pack') or {}
            writer.writerow({
                'file': item['file'],
                'type': item['type'],
                'pages': item['pages'],
                'text_extracted': item['text_extracted'],
                'text_length': item['text_length'],
                'classification': item.get('classification'),
                'sector': item.get('sector'),
                'raw_skills': ((pipeline.get('skill_extraction') or {}).get('raw_skill_candidates_count') if pipeline else 0) or 0,
                'canonical': ((pipeline.get('canonicalisation') or {}).get('canonical_skills_count') if pipeline else 0) or 0,
                'enriched': ((pipeline.get('enriched') or {}).get('enriched_signals_count') if pipeline else 0) or 0,
                'concept': ((pipeline.get('concept') or {}).get('concept_signals_count') if pipeline else 0) or 0,
                'inbox_offers': (matching.get('offers_count') if matching else 0) or 0,
                'top_score_v3': next((score for score in (matching.get('top5_score_v3') or []) if isinstance(score, int)), None),
                'apply_pack_status': apply_pack.get('status') or 'NOT_RUN',
            })

    OUT_MD.write_text(_build_markdown_report(audits, metrics), encoding='utf-8')

    print(json.dumps({
        'json': str(OUT_JSON),
        'csv': str(OUT_CSV),
        'markdown': str(OUT_MD),
        'tested': metrics['tested_count'],
        'exploitable': metrics['exploitable_count'],
        'failed': metrics['failed_count'],
        'final_verdict': output['final_verdict'],
    }, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
