from __future__ import annotations

import json
from pathlib import Path
from statistics import mean

from compass.pipeline import build_parse_file_response_payload
from compass.pipeline.contracts import ParseFilePipelineRequest
from compass.canonical.canonical_store import get_canonical_store, normalize_canonical_key

REPO_ROOT = Path(__file__).resolve().parents[3]
MANIFEST_PATH = REPO_ROOT / 'apps' / 'api' / 'data' / 'eval' / 'synthetic_cv_dataset_v1_manifest.json'


store = get_canonical_store()
FALSE_POSITIVE_GUARD_LABELS = {
    'machine learning',
    'data science',
    'advanced analytics',
}

DOMAIN_EXPECTATION_MAP = {
    'Business / Sales': 'sales',
    'Supply Chain / Procurement': 'supply_chain',
    'Supply Chain / Operations': 'supply_chain',
    'Marketing / Communication': 'marketing',
    'Finance / Controlling': 'finance',
    'Finance / Accounting': 'finance',
    'HR / Generalist': 'hr',
}


def normalize_label(value: str) -> str:
    return normalize_canonical_key(value or '')


def resolve_expected_to_canonical(skill: str) -> tuple[str | None, str]:
    key = normalize_label(skill)
    if not key:
        return None, key
    cid = store.alias_to_id.get(key)
    if cid:
        return cid, key
    for candidate_id, skill_entry in store.id_to_skill.items():
        label_key = normalize_label(str(skill_entry.get('label') or ''))
        if label_key == key:
            return candidate_id, key
    return None, key


def main() -> int:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding='utf-8'))
    results = []
    for item in manifest:
        cv_text = Path(item['path']).read_text(encoding='utf-8')
        payload = build_parse_file_response_payload(ParseFilePipelineRequest(request_id='synthetic-eval', raw_filename=item['name'], content_type='text/plain', file_bytes=cv_text.encode('utf-8'), enrich_llm=0))
        preserved = payload.get('preserved_explicit_skills') or []
        summary = payload.get('profile_summary_skills') or []
        canonical = payload.get('canonical_skills') or []
        dropped = payload.get('dropped_by_priority') or []
        structured_units = payload.get('structured_signal_units') or []
        top_signal_units = payload.get('top_signal_units') or []
        structured_stats = payload.get('structured_signal_stats') or {}

        preserved_labels = {normalize_label(entry.get('label') or '') for entry in preserved}
        summary_labels = {normalize_label(entry.get('label') or '') for entry in summary}
        canonical_ids = {entry.get('canonical_id') for entry in canonical if entry.get('canonical_id')}
        canonical_labels = {normalize_label(entry.get('label') or '') for entry in canonical if entry.get('label')}
        expected_label_keys = {normalize_label(skill) for skill in item['expected_core_skills']}
        false_positive_labels = sorted(
            label
            for label in canonical_labels
            if label in FALSE_POSITIVE_GUARD_LABELS and label not in expected_label_keys
        )

        expected_rows = []
        preserved_hits = 0
        summary_hits = 0
        canonical_hits = 0
        for skill in item['expected_core_skills']:
            cid, key = resolve_expected_to_canonical(skill)
            in_preserved = key in preserved_labels
            in_summary = key in summary_labels
            in_canonical = (cid in canonical_ids) if cid else (key in canonical_labels)
            if in_preserved:
                preserved_hits += 1
            if in_summary:
                summary_hits += 1
            if in_canonical:
                canonical_hits += 1
            expected_rows.append({
                'skill': skill,
                'canonical_id': cid,
                'preserved_hit': in_preserved,
                'summary_hit': in_summary,
                'canonical_hit': in_canonical,
            })

        expected_domain = DOMAIN_EXPECTATION_MAP.get(item['domain'])
        top_domains = [entry.get('domain') for entry in top_signal_units if entry.get('domain')]
        domain_detection_hit = bool(expected_domain and expected_domain in top_domains)
        top_signal_relevance = 0
        if top_signal_units:
            expected_tokens = {normalize_label(skill) for skill in item['expected_core_skills']}
            relevant = 0
            for signal in top_signal_units:
                combined = ' '.join(
                    str(signal.get(field) or '')
                    for field in ('raw_text', 'object', 'action_object_text')
                )
                normalized = normalize_label(combined)
                if any(token and token in normalized for token in expected_tokens):
                    relevant += 1
            top_signal_relevance = round(relevant / len(top_signal_units), 3)

        results.append({
            'candidate_name': item['candidate_name'],
            'title': item['title'],
            'domain': item['domain'],
            'layout_type': item['layout_type'],
            'difficulty': item['difficulty'],
            'expected_core_skill_count': len(item['expected_core_skills']),
            'preserved_hit_count': preserved_hits,
            'summary_hit_count': summary_hits,
            'canonical_hit_count': canonical_hits,
            'preserved_hit_rate': round(preserved_hits / len(item['expected_core_skills']), 3),
            'summary_hit_rate': round(summary_hits / len(item['expected_core_skills']), 3),
            'canonical_hit_rate': round(canonical_hits / len(item['expected_core_skills']), 3),
            'priority_stats': payload.get('priority_stats') or {},
            'expected_skill_results': expected_rows,
            'preserved_explicit_skills': [entry.get('label') for entry in preserved],
            'profile_summary_skills': [entry.get('label') for entry in summary],
            'canonical_skills': [entry.get('label') for entry in canonical if entry.get('label')],
            'structured_unit_count': len(structured_units),
            'mapping_inputs_count': int(payload.get('mapping_inputs_count') or 0),
            'structured_units_promoted_count': int(structured_stats.get('structured_units_promoted_count') or 0),
            'structured_units_rejected_count': int(structured_stats.get('structured_units_rejected_count') or 0),
            'generic_skill_ratio': structured_stats.get('generic_skill_ratio', 0.0),
            'domain_detection_hit': domain_detection_hit,
            'top_signal_relevance': top_signal_relevance,
            'top_signal_units': top_signal_units,
            'dropped_count': len(dropped),
            'false_positive_labels': false_positive_labels,
            'false_positive_count': len(false_positive_labels),
        })

    aggregate = {
        'cv_count': len(results),
        'avg_preserved_hit_rate': round(mean(item['preserved_hit_rate'] for item in results), 3),
        'avg_summary_hit_rate': round(mean(item['summary_hit_rate'] for item in results), 3),
        'avg_canonical_hit_rate': round(mean(item['canonical_hit_rate'] for item in results), 3),
        'avg_preserved_count': round(mean((item['priority_stats'].get('preserved_count') or 0) for item in results), 2),
        'avg_dropped_count': round(mean(item['dropped_count'] for item in results), 2),
        'avg_structured_unit_count': round(mean(item['structured_unit_count'] for item in results), 2),
        'avg_mapping_inputs_count': round(mean(item['mapping_inputs_count'] for item in results), 2),
        'avg_structured_units_promoted_count': round(mean(item['structured_units_promoted_count'] for item in results), 2),
        'avg_structured_units_rejected_count': round(mean(item['structured_units_rejected_count'] for item in results), 2),
        'avg_generic_skill_ratio': round(mean(float(item['generic_skill_ratio'] or 0.0) for item in results), 3),
        'domain_detection_accuracy': round(mean(1.0 if item['domain_detection_hit'] else 0.0 for item in results), 3),
        'avg_top_signal_relevance': round(mean(float(item['top_signal_relevance'] or 0.0) for item in results), 3),
        'false_positive_count': sum(item['false_positive_count'] for item in results),
    }
    output = {'aggregate': aggregate, 'results': results}
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
