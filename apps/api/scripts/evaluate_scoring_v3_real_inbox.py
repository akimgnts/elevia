from __future__ import annotations

import importlib.util
import io
import json
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List

from fastapi.testclient import TestClient

from api.main import app
from api.routes.inbox import _ADJACENCY
from api.utils.inbox_catalog import load_catalog_offers
from compass.explainability.explanation_builder import build_offer_explanation
from compass.explainability.semantic_explanation_builder import build_semantic_explainability
from compass.offer.offer_intelligence import build_offer_intelligence, is_role_domain_compatible
from compass.scoring.scoring_v2 import build_scoring_v2
from compass.scoring.scoring_v3 import build_scoring_v3
from matching import MatchingEngine
from matching.extractors import extract_profile
from offer.offer_cluster import detect_offer_cluster
from profile.profile_cluster import detect_profile_cluster

ROOT = Path(__file__).resolve().parents[1]
OUT_PATH = ROOT / 'data' / 'eval' / 'scoring_v3_vs_v2_real_inbox.json'
CATALOG_SLICE = 250
RAW_POOL = 10
TOP_K = 5

_CONCEPT_EVAL_PATH = Path(__file__).with_name('evaluate_concept_signal_value.py')
_SPEC = importlib.util.spec_from_file_location('evaluate_concept_signal_value', _CONCEPT_EVAL_PATH)
if _SPEC is None or _SPEC.loader is None:
    raise RuntimeError(f'Unable to load {_CONCEPT_EVAL_PATH}')
_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)
CV_CASES = _MODULE.CV_CASES


def _slug(value: str) -> str:
    return ''.join(ch.lower() if ch.isalnum() else '-' for ch in value).strip('-')


def _profile_payload(parse_body: Dict[str, Any]) -> Dict[str, Any]:
    profile = dict(parse_body.get('profile') or {})
    if parse_body.get('profile_intelligence') and not profile.get('profile_intelligence'):
        profile['profile_intelligence'] = parse_body['profile_intelligence']
    return profile


def _offer_cluster(offer: Dict[str, Any]) -> str:
    existing = str(offer.get('offer_cluster') or '').strip()
    if existing:
        return existing
    cluster, _, _ = detect_offer_cluster(
        offer.get('title'),
        offer.get('description') or offer.get('display_description'),
        [s.get('label') if isinstance(s, dict) else str(s) for s in (offer.get('skills_display') or offer.get('skills') or [])],
    )
    return cluster or 'OTHER'


def _shared_domains(item: Dict[str, Any]) -> List[str]:
    return list((((item.get('semantic_explainability') or {}).get('domain_alignment') or {}).get('shared_domains') or []))


def _role_alignment(item: Dict[str, Any]) -> str:
    return str((((item.get('semantic_explainability') or {}).get('role_alignment') or {}).get('alignment') or '')).lower()


def _is_correct_metier(item: Dict[str, Any]) -> bool:
    alignment = _role_alignment(item)
    return alignment == 'high' or (alignment == 'medium' and bool(_shared_domains(item)))


def _is_false_positive(item: Dict[str, Any]) -> bool:
    alignment = _role_alignment(item)
    matched = list((((item.get('semantic_explainability') or {}).get('signal_alignment') or {}).get('matched_signals') or []))
    return alignment == 'low' and not _shared_domains(item) and len(matched) <= 1


def _top_relevance_label(item: Dict[str, Any]) -> str:
    if _is_false_positive(item):
        return 'Low'
    if _is_correct_metier(item):
        return 'High'
    return 'Medium'


def _transition_label(items: List[Dict[str, Any]]) -> str:
    transition_count = sum(1 for item in items if _role_alignment(item) == 'medium' and _shared_domains(item))
    if transition_count >= 2:
        return 'Well positioned'
    if transition_count == 1:
        return 'Visible but limited'
    return 'Underestimated'


def _simplify_item(item: Dict[str, Any]) -> Dict[str, Any]:
    semantic = item.get('semantic_explainability') or {}
    return {
        'offer_id': item.get('offer_id'),
        'title': item.get('title'),
        'company': item.get('company'),
        'score': item.get('score'),
        'scoring_v2': ((item.get('scoring_v2') or {}).get('score_pct')),
        'scoring_v3': ((item.get('scoring_v3') or {}).get('score_pct')),
        'role_alignment': ((semantic.get('role_alignment') or {}).get('alignment')),
        'domain_alignment': semantic.get('domain_alignment') or {},
        'top_offer_signals': ((item.get('offer_intelligence') or {}).get('top_offer_signals') or []),
        'required_skills': ((item.get('offer_intelligence') or {}).get('required_skills') or []),
        'semantic_summary': semantic.get('alignment_summary'),
        'offer_role': ((item.get('offer_intelligence') or {}).get('dominant_role_block')),
    }


def _ranked(items: List[Dict[str, Any]], key: str) -> List[Dict[str, Any]]:
    return sorted(items, key=lambda item: (int(((item.get(key) or {}).get('score_pct')) or -1), int(item.get('score') or 0)), reverse=True)


def _position_map(items: List[Dict[str, Any]]) -> Dict[str, int]:
    return {str(item.get('offer_id')): idx + 1 for idx, item in enumerate(items)}


def _raw_pool(scored_rows: List[Dict[str, Any]], profile_cluster: str) -> List[Dict[str, Any]]:
    neighbors = set(_ADJACENCY.get(profile_cluster or '', []))
    strict = []
    neighbor = []
    out = []
    for row in scored_rows:
        if row['offer_cluster'] != 'OTHER' and row['offer_cluster'] == profile_cluster:
            strict.append(row)
        elif row['offer_cluster'] in neighbors:
            neighbor.append(row)
        else:
            out.append(row)
    strict.sort(key=lambda row: (-int(row['score']), row['offer_id']))
    neighbor.sort(key=lambda row: (-int(row['score']), row['offer_id']))
    out.sort(key=lambda row: (-int(row['score']), row['offer_id']))
    if len(strict) >= TOP_K:
        return strict[:RAW_POOL]
    return (strict + neighbor + out)[:RAW_POOL]


def _parse_profile(client: TestClient, case: Dict[str, Any]) -> Dict[str, Any]:
    parse_resp = client.post(
        '/profile/parse-file',
        files={'file': (f"{_slug(case['domain'])}.txt", io.BytesIO(case['cv_text'].encode('utf-8')), 'text/plain')},
    )
    parse_resp.raise_for_status()
    parse_body = parse_resp.json()
    profile = _profile_payload(parse_body)
    extracted = extract_profile(profile)
    profile_cluster = detect_profile_cluster(list(getattr(extracted, 'skills', []))).get('dominant_cluster') or 'OTHER'
    return {
        'case': case,
        'parse_body': parse_body,
        'profile': profile,
        'profile_intelligence': dict(profile.get('profile_intelligence') or {}),
        'extracted': extracted,
        'profile_cluster': profile_cluster,
    }


def _score_catalog(
    engine: MatchingEngine,
    catalog: List[Dict[str, Any]],
    extracted,
    profile_cluster: str,
    profile_intelligence: Dict[str, Any],
    offer_intelligence_map: Dict[str, Dict[str, Any]],
) -> List[Dict[str, Any]]:
    rows = []
    for offer in catalog:
        offer_id = str(offer.get('id') or '')
        offer_intelligence = offer_intelligence_map[offer_id]
        if not is_role_domain_compatible(
            profile_intelligence=profile_intelligence,
            offer_intelligence=offer_intelligence,
        ):
            continue
        result = engine.score_offer(extracted, offer)
        match_debug = result.match_debug or {}
        score_raw = float(match_debug['total']) / 100.0 if isinstance(match_debug, dict) and isinstance(match_debug.get('total'), (int, float)) else float(result.score) / 100.0
        rows.append({
            'offer_id': offer_id,
            'offer': offer,
            'score': result.score,
            'score_raw': round(score_raw, 4),
            'match_debug': match_debug,
            'offer_cluster': _offer_cluster(offer),
        })
    return _raw_pool(rows, profile_cluster)


def _evaluate_profile(parsed: Dict[str, Any], raw_candidates: List[Dict[str, Any]], offer_intelligence_map: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    items = []
    profile = parsed['profile']
    profile_intelligence = parsed['profile_intelligence']
    for row in raw_candidates:
        offer = row['offer']
        offer_id = row['offer_id']
        offer_labels = [s.get('label') if isinstance(s, dict) else str(s) for s in (offer.get('skills_display') or offer.get('skills') or [])]
        profile_labels = list(profile.get('matching_skills') or profile.get('skills') or [])
        explanation = build_offer_explanation(
            row['match_debug'],
            score=row['score'],
            confidence=None,
            profile_effective_skills=profile_labels,
            job_required_skills=offer_labels,
        )
        offer_intelligence = offer_intelligence_map[offer_id]
        semantic = build_semantic_explainability(
            profile_intelligence=profile_intelligence,
            offer_intelligence=offer_intelligence,
            explanation=explanation,
        )
        scoring_v2 = build_scoring_v2(
            profile_intelligence=profile_intelligence,
            offer_intelligence=offer_intelligence,
            semantic_explainability=semantic,
            matching_score=row['score_raw'],
        )
        scoring_v3 = build_scoring_v3(
            profile_intelligence=profile_intelligence,
            offer_intelligence=offer_intelligence,
            semantic_explainability=semantic,
            explanation=explanation,
            matching_score=row['score_raw'],
        )
        items.append({
            'offer_id': offer_id,
            'title': offer.get('title'),
            'company': offer.get('company'),
            'score': row['score'],
            'score_raw': row['score_raw'],
            'offer_intelligence': offer_intelligence,
            'semantic_explainability': semantic,
            'scoring_v2': scoring_v2,
            'scoring_v3': scoring_v3,
        })

    ranked_v2 = _ranked(items, 'scoring_v2')
    ranked_v3 = _ranked(items, 'scoring_v3')
    top_v2 = ranked_v2[:TOP_K]
    top_v3 = ranked_v3[:TOP_K]
    pos_v2 = _position_map(ranked_v2)
    pos_v3 = _position_map(ranked_v3)

    false_positives_v3 = [_simplify_item(item) for item in top_v3 if _is_false_positive(item)]
    downgraded_good_matches = []
    for item in top_v2:
        offer_id = str(item.get('offer_id'))
        if _is_correct_metier(item) and pos_v3.get(offer_id, 10**6) > TOP_K:
            downgraded_good_matches.append(_simplify_item(item))

    return {
        'profile_domain': parsed['case']['domain'],
        'profile_id': _slug(parsed['case']['domain']),
        'profile_role': parsed['profile_intelligence'].get('dominant_role_block'),
        'profile_domains': parsed['profile_intelligence'].get('dominant_domains') or [],
        'parse_summary': parsed['profile_intelligence'].get('profile_summary'),
        'candidate_pool_size': len(items),
        'all_items': [_simplify_item(item) for item in items],
        'top5_v2': [_simplify_item(item) for item in top_v2],
        'top5_v3': [_simplify_item(item) for item in top_v3],
        'analysis_grid': {
            'top1_relevance': {
                'scoring_v2': _top_relevance_label(top_v2[0]) if top_v2 else 'Low',
                'scoring_v3': _top_relevance_label(top_v3[0]) if top_v3 else 'Low',
            },
            'false_positives_in_top5': {
                'scoring_v2': sum(1 for item in top_v2 if _is_false_positive(item)),
                'scoring_v3': sum(1 for item in top_v3 if _is_false_positive(item)),
            },
            'correct_metier_in_top5': {
                'scoring_v2': f"{sum(1 for item in top_v2 if _is_correct_metier(item))}/{len(top_v2)}",
                'scoring_v3': f"{sum(1 for item in top_v3 if _is_correct_metier(item))}/{len(top_v3)}",
            },
            'transition_cases': {
                'scoring_v2': _transition_label(top_v2),
                'scoring_v3': _transition_label(top_v3),
            },
        },
        'ranking_differences': [
            {
                'offer_id': str(item.get('offer_id')),
                'title': item.get('title'),
                'v2_rank': pos_v2.get(str(item.get('offer_id'))),
                'v3_rank': pos_v3.get(str(item.get('offer_id'))),
                'scoring_v2': ((item.get('scoring_v2') or {}).get('score_pct')),
                'scoring_v3': ((item.get('scoring_v3') or {}).get('score_pct')),
                'role_alignment': _role_alignment(item),
                'shared_domains': _shared_domains(item),
            }
            for item in (top_v2 + [row for row in top_v3 if str(row.get('offer_id')) not in {str(x.get('offer_id')) for x in top_v2}])[:10]
        ],
        'failure_cases': {
            'false_positives_introduced_by_v3': false_positives_v3,
            'good_matches_downgraded_by_v3': downgraded_good_matches,
        },
    }


def main() -> None:
    client = TestClient(app)
    catalog = load_catalog_offers()[:CATALOG_SLICE]
    engine = MatchingEngine(catalog)

    print('[eval] parsing profiles', flush=True)
    parsed_profiles = [_parse_profile(client, case) for case in CV_CASES]

    print(f'[eval] precomputing offer intelligence for {len(catalog)} offers', flush=True)
    offer_lookup = {str(offer.get('id') or ''): offer for offer in catalog}
    offer_intelligence_map = {}
    for offer_id, offer in sorted(offer_lookup.items()):
        offer_intelligence_map[offer_id] = build_offer_intelligence(offer=offer)

    print('[eval] scoring raw candidate pools', flush=True)
    raw_candidates_by_profile = []
    for parsed in parsed_profiles:
        candidates = _score_catalog(
            engine,
            catalog,
            parsed['extracted'],
            parsed['profile_cluster'],
            parsed['profile_intelligence'],
            offer_intelligence_map,
        )
        raw_candidates_by_profile.append((parsed, candidates))

    print('[eval] reranking candidate pools with v2/v3', flush=True)
    profiles = [_evaluate_profile(parsed, candidates, offer_intelligence_map) for parsed, candidates in raw_candidates_by_profile]

    top5_v2_all = [item for profile in profiles for item in profile['top5_v2']]
    top5_v3_all = [item for profile in profiles for item in profile['top5_v3']]
    all_items = [item for profile in profiles for item in profile['all_items']]

    improved_cases = 0
    degraded_cases = 0
    for profile in profiles:
        v2_correct = int(profile['analysis_grid']['correct_metier_in_top5']['scoring_v2'].split('/')[0])
        v3_correct = int(profile['analysis_grid']['correct_metier_in_top5']['scoring_v3'].split('/')[0])
        v2_fp = profile['analysis_grid']['false_positives_in_top5']['scoring_v2']
        v3_fp = profile['analysis_grid']['false_positives_in_top5']['scoring_v3']
        if v3_correct > v2_correct or v3_fp < v2_fp:
            improved_cases += 1
        elif v3_correct < v2_correct or v3_fp > v2_fp:
            degraded_cases += 1

    avg_score_diff = mean([
        ((item.get('scoring_v3') or 0) - (item.get('scoring_v2') or 0))
        for item in all_items
        if item.get('scoring_v2') is not None and item.get('scoring_v3') is not None
    ]) if all_items else 0.0

    summary = {
        'top5_correct_metier_pct': {
            'scoring_v2': round(100.0 * sum(1 for item in top5_v2_all if _is_correct_metier(item)) / max(len(top5_v2_all), 1), 1),
            'scoring_v3': round(100.0 * sum(1 for item in top5_v3_all if _is_correct_metier(item)) / max(len(top5_v3_all), 1), 1),
        },
        'top5_false_positive_pct': {
            'scoring_v2': round(100.0 * sum(1 for item in top5_v2_all if _is_false_positive(item)) / max(len(top5_v2_all), 1), 1),
            'scoring_v3': round(100.0 * sum(1 for item in top5_v3_all if _is_false_positive(item)) / max(len(top5_v3_all), 1), 1),
        },
        'average_score_difference_v3_minus_v2': round(avg_score_diff, 2),
        'improved_cases': improved_cases,
        'degraded_cases': degraded_cases,
        'case_count': len(profiles),
    }

    verdict = 'YES' if improved_cases > degraded_cases and summary['top5_correct_metier_pct']['scoring_v3'] >= summary['top5_correct_metier_pct']['scoring_v2'] and summary['top5_false_positive_pct']['scoring_v3'] <= summary['top5_false_positive_pct']['scoring_v2'] else 'MIXED'
    output = {
        'executive_verdict': verdict,
        'catalog_scope': {
            'mode': 'latest_unfiltered_slice_raw_top10_rerank',
            'offer_count': len(catalog),
            'raw_candidate_pool_per_profile': RAW_POOL,
        },
        'profiles': profiles,
        'metrics_summary': summary,
    }
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'artifact': str(OUT_PATH), 'executive_verdict': verdict, 'metrics_summary': summary}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
