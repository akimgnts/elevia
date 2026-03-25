from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from fastapi.testclient import TestClient

from api.main import app
from api.routes import inbox as inbox_routes
from api.routes import offers as offers_routes
from compass.scoring.scoring_v2 import build_scoring_v2
from compass.scoring.scoring_v3 import build_scoring_v3


def _profile(**overrides):
    payload = {
        'dominant_role_block': 'finance_ops',
        'secondary_role_blocks': ['business_analysis'],
        'dominant_domains': ['finance', 'data'],
        'top_profile_signals': ['reporting', 'audit', 'analyse financiere', 'sql'],
    }
    payload.update(overrides)
    return payload


def _offer(**overrides):
    payload = {
        'dominant_role_block': 'finance_ops',
        'secondary_role_blocks': ['business_analysis'],
        'dominant_domains': ['finance'],
        'top_offer_signals': ['reporting', 'audit', 'budget'],
        'required_skills': ['reporting', 'audit', 'vba', 'modelisation financiere'],
        'optional_skills': ['power bi', 'sql'],
    }
    payload.update(overrides)
    return payload


def _semantic(**overrides):
    payload = {
        'role_alignment': {
            'profile_role': 'finance_ops',
            'offer_role': 'finance_ops',
            'alignment': 'high',
        },
        'domain_alignment': {
            'shared_domains': ['finance'],
            'profile_only_domains': ['data'],
            'offer_only_domains': [],
        },
        'signal_alignment': {
            'matched_signals': ['reporting', 'audit'],
            'missing_core_signals': ['vba'],
        },
        'alignment_summary': 'Ton profil et ce poste sont alignes sur la finance.',
    }
    payload.update(overrides)
    return payload


def _explanation(**overrides):
    payload = {
        'score': 74,
        'fit_label': 'Bon potentiel',
        'summary_reason': 'Match coherent',
        'strengths': ['reporting', 'audit'],
        'gaps': ['vba'],
        'blockers': [],
        'next_actions': ['Renforcer VBA'],
    }
    payload.update(overrides)
    return payload


def test_same_metier_same_domain_with_moderate_gaps_is_clearly_positive():
    result = build_scoring_v3(
        profile_intelligence=_profile(),
        offer_intelligence=_offer(),
        semantic_explainability=_semantic(),
        explanation=_explanation(),
        matching_score=68,
    )

    assert result is not None
    assert result['components']['role_alignment'] == 1.0
    assert result['components']['domain_alignment'] >= 0.8
    assert result['score_pct'] >= 72
    assert 'Alignement métier fort' in result['summary']


def test_wrong_metier_with_tool_overlap_stays_low():
    result = build_scoring_v3(
        profile_intelligence=_profile(
            dominant_role_block='data_analytics',
            secondary_role_blocks=['software_it'],
            dominant_domains=['data'],
            top_profile_signals=['sql', 'python', 'excel'],
        ),
        offer_intelligence=_offer(
            dominant_role_block='sales_business_dev',
            secondary_role_blocks=['marketing_communication'],
            dominant_domains=['sales'],
            top_offer_signals=['crm', 'prospection', 'excel'],
            required_skills=['crm', 'prospection', 'excel'],
            optional_skills=['sql'],
        ),
        semantic_explainability=_semantic(
            role_alignment={
                'profile_role': 'data_analytics',
                'offer_role': 'sales_business_dev',
                'alignment': 'low',
            },
            domain_alignment={
                'shared_domains': [],
                'profile_only_domains': ['data'],
                'offer_only_domains': ['sales'],
            },
            signal_alignment={
                'matched_signals': ['excel'],
                'missing_core_signals': ['crm', 'prospection'],
            },
        ),
        explanation=_explanation(gaps=['crm'], blockers=['prospection']),
        matching_score=76,
    )

    assert result is not None
    assert result['components']['role_alignment'] <= 0.1
    assert result['score_pct'] <= 30


def test_transition_profile_stays_medium_and_promising():
    result = build_scoring_v3(
        profile_intelligence=_profile(
            dominant_role_block='business_analysis',
            secondary_role_blocks=['finance_ops', 'project_ops'],
            dominant_domains=['business', 'finance'],
            top_profile_signals=['reporting', 'analyse financiere', 'coordination'],
        ),
        offer_intelligence=_offer(
            dominant_role_block='finance_ops',
            secondary_role_blocks=['business_analysis'],
            dominant_domains=['finance'],
        ),
        semantic_explainability=_semantic(
            role_alignment={
                'profile_role': 'business_analysis',
                'offer_role': 'finance_ops',
                'alignment': 'medium',
            },
            domain_alignment={
                'shared_domains': ['finance'],
                'profile_only_domains': ['business'],
                'offer_only_domains': [],
            },
            signal_alignment={
                'matched_signals': ['reporting'],
                'missing_core_signals': ['audit'],
            },
        ),
        explanation=_explanation(gaps=['audit']),
        matching_score=52,
    )

    assert result is not None
    assert 50 <= result['score_pct'] <= 72
    assert result['components']['role_alignment'] >= 0.55


def test_critical_required_gaps_still_reduce_score():
    no_gap = build_scoring_v3(
        profile_intelligence=_profile(),
        offer_intelligence=_offer(),
        semantic_explainability=_semantic(signal_alignment={'matched_signals': ['reporting', 'audit'], 'missing_core_signals': []}),
        explanation=_explanation(gaps=[]),
        matching_score=82,
    )
    with_gap = build_scoring_v3(
        profile_intelligence=_profile(),
        offer_intelligence=_offer(required_skills=['reporting', 'audit', 'vba', 'modelisation financiere']),
        semantic_explainability=_semantic(signal_alignment={'matched_signals': ['reporting'], 'missing_core_signals': ['audit', 'vba', 'modelisation financiere']}),
        explanation=_explanation(gaps=['vba', 'modelisation financiere'], blockers=['audit']),
        matching_score=82,
    )

    assert no_gap is not None and with_gap is not None
    assert with_gap['components']['gap_penalty'] > no_gap['components']['gap_penalty']
    assert with_gap['score'] < no_gap['score']


def test_scoring_v3_is_more_faithful_than_v2_on_semantic_fit_and_false_positive_control():
    strong_fit_v2 = build_scoring_v2(
        profile_intelligence=_profile(
            dominant_role_block='supply_chain_ops',
            secondary_role_blocks=['project_ops', 'business_analysis'],
            dominant_domains=['supply_chain', 'operations'],
            top_profile_signals=['logistique', 'coordination transport', 'reporting'],
        ),
        offer_intelligence=_offer(
            dominant_role_block='supply_chain_ops',
            secondary_role_blocks=['project_ops'],
            dominant_domains=['supply_chain', 'operations'],
            top_offer_signals=['logistique', 'transport operations', 'reporting'],
            required_skills=['logistique', 'transport operations', 'supply chain'],
            optional_skills=['excel'],
        ),
        semantic_explainability={
            'role_alignment': {'profile_role': 'supply_chain_ops', 'offer_role': 'supply_chain_ops', 'alignment': 'high'},
            'domain_alignment': {'shared_domains': ['supply_chain', 'operations'], 'profile_only_domains': [], 'offer_only_domains': []},
            'signal_alignment': {'matched_signals': ['logistique', 'reporting'], 'missing_core_signals': ['transport operations']},
            'alignment_summary': 'Alignement supply chain.',
        },
        matching_score=54,
    )
    strong_fit_v3 = build_scoring_v3(
        profile_intelligence=_profile(
            dominant_role_block='supply_chain_ops',
            secondary_role_blocks=['project_ops', 'business_analysis'],
            dominant_domains=['supply_chain', 'operations'],
            top_profile_signals=['logistique', 'coordination transport', 'reporting'],
        ),
        offer_intelligence=_offer(
            dominant_role_block='supply_chain_ops',
            secondary_role_blocks=['project_ops'],
            dominant_domains=['supply_chain', 'operations'],
            top_offer_signals=['logistique', 'transport operations', 'reporting'],
            required_skills=['logistique', 'transport operations', 'supply chain'],
            optional_skills=['excel'],
        ),
        semantic_explainability={
            'role_alignment': {'profile_role': 'supply_chain_ops', 'offer_role': 'supply_chain_ops', 'alignment': 'high'},
            'domain_alignment': {'shared_domains': ['supply_chain', 'operations'], 'profile_only_domains': [], 'offer_only_domains': []},
            'signal_alignment': {'matched_signals': ['logistique', 'reporting'], 'missing_core_signals': ['transport operations']},
            'alignment_summary': 'Alignement supply chain.',
        },
        explanation=_explanation(gaps=['transport operations']),
        matching_score=54,
    )

    false_positive_v2 = build_scoring_v2(
        profile_intelligence=_profile(
            dominant_role_block='data_analytics',
            secondary_role_blocks=['software_it'],
            dominant_domains=['data'],
            top_profile_signals=['sql', 'excel', 'power bi'],
        ),
        offer_intelligence=_offer(
            dominant_role_block='sales_business_dev',
            secondary_role_blocks=['marketing_communication'],
            dominant_domains=['sales'],
            top_offer_signals=['crm', 'excel', 'reporting'],
            required_skills=['crm', 'prospection', 'excel'],
            optional_skills=['sql'],
        ),
        semantic_explainability={
            'role_alignment': {'profile_role': 'data_analytics', 'offer_role': 'sales_business_dev', 'alignment': 'low'},
            'domain_alignment': {'shared_domains': [], 'profile_only_domains': ['data'], 'offer_only_domains': ['sales']},
            'signal_alignment': {'matched_signals': ['excel'], 'missing_core_signals': ['crm', 'prospection']},
            'alignment_summary': 'Recouvrement faible.',
        },
        matching_score=72,
    )
    false_positive_v3 = build_scoring_v3(
        profile_intelligence=_profile(
            dominant_role_block='data_analytics',
            secondary_role_blocks=['software_it'],
            dominant_domains=['data'],
            top_profile_signals=['sql', 'excel', 'power bi'],
        ),
        offer_intelligence=_offer(
            dominant_role_block='sales_business_dev',
            secondary_role_blocks=['marketing_communication'],
            dominant_domains=['sales'],
            top_offer_signals=['crm', 'excel', 'reporting'],
            required_skills=['crm', 'prospection', 'excel'],
            optional_skills=['sql'],
        ),
        semantic_explainability={
            'role_alignment': {'profile_role': 'data_analytics', 'offer_role': 'sales_business_dev', 'alignment': 'low'},
            'domain_alignment': {'shared_domains': [], 'profile_only_domains': ['data'], 'offer_only_domains': ['sales']},
            'signal_alignment': {'matched_signals': ['excel'], 'missing_core_signals': ['crm', 'prospection']},
            'alignment_summary': 'Recouvrement faible.',
        },
        explanation=_explanation(gaps=['crm'], blockers=['prospection']),
        matching_score=72,
    )

    assert strong_fit_v2 is not None and strong_fit_v3 is not None
    assert false_positive_v2 is not None and false_positive_v3 is not None
    assert strong_fit_v3['score_pct'] > strong_fit_v2['score_pct']
    assert false_positive_v3['score_pct'] <= false_positive_v2['score_pct']


def test_scoring_v3_is_deterministic_and_exposed_additively(monkeypatch, tmp_path):
    result_one = build_scoring_v3(
        profile_intelligence=_profile(),
        offer_intelligence=_offer(),
        semantic_explainability=_semantic(),
        explanation=_explanation(),
        matching_score=84,
    )
    result_two = build_scoring_v3(
        profile_intelligence=_profile(),
        offer_intelligence=_offer(),
        semantic_explainability=_semantic(),
        explanation=_explanation(),
        matching_score=84,
    )
    assert result_one == result_two

    client = TestClient(app)
    offer = {
        'title': 'VIE - Finance - LVMH Allemagne',
        'description': 'Missions principales : Produire des analyses et reportings réguliers. Profil recherché : Compétences : comptabilité, audit, Excel, modélisation financière',
        'skills': ['comptabilité', 'audit', 'Excel', 'modélisation financière', 'reporting'],
        'skills_display': [{'label': 'comptabilité'}, {'label': 'audit'}, {'label': 'Excel'}],
        'id': 'offer-finance-v3',
        'source': 'business_france',
        'company': 'LVMH',
        'country': 'Allemagne',
        'city': 'Frankfurt',
        'publication_date': '2026-03-20',
    }
    monkeypatch.setattr(inbox_routes, 'load_catalog_offers', lambda: [offer])
    monkeypatch.setattr(inbox_routes, 'load_catalog_offers_filtered', lambda **kwargs: [offer])
    monkeypatch.setattr(inbox_routes, 'count_catalog_offers_filtered', lambda **kwargs: 1)

    inbox_resp = client.post('/inbox', json={
        'profile_id': 'scoring-v3',
        'profile': {
            'skills': ['audit', 'excel', 'reporting'],
            'profile_intelligence': {
                'dominant_role_block': 'finance_ops',
                'secondary_role_blocks': ['business_analysis'],
                'dominant_domains': ['finance'],
                'top_profile_signals': ['audit', 'reporting', 'excel'],
                'profile_summary': 'Profil orienté finance opérationnelle.',
            },
        },
        'min_score': 0,
        'limit': 1,
    })
    assert inbox_resp.status_code == 200
    item = inbox_resp.json()['items'][0]
    assert item['scoring_v2']['score_pct'] >= 0
    assert item['scoring_v3']['score_pct'] >= 0
    assert item['scoring_v3']['summary']

    db_path = tmp_path / 'offers.db'
    conn = sqlite3.connect(db_path)
    conn.execute('''
        CREATE TABLE fact_offers (
            id TEXT PRIMARY KEY,
            source TEXT,
            title TEXT,
            description TEXT,
            company TEXT,
            city TEXT,
            country TEXT,
            publication_date TEXT,
            contract_duration INTEGER,
            start_date TEXT
        )
    ''')
    conn.execute('''
        CREATE TABLE fact_offer_skills (
            offer_id TEXT NOT NULL,
            skill TEXT NOT NULL,
            skill_uri TEXT,
            source TEXT NOT NULL,
            confidence REAL,
            created_at TEXT NOT NULL,
            PRIMARY KEY (offer_id, skill)
        )
    ''')
    conn.execute('''
        INSERT INTO fact_offers (id, source, title, description, company, city, country, publication_date, contract_duration, start_date)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        'offer-finance-v3', 'business_france', 'VIE - Finance - LVMH Allemagne',
        'Produire des analyses et reportings réguliers. Compétences : comptabilité, audit, Excel, modélisation financière.',
        'LVMH', 'Frankfurt', 'Allemagne', '2026-03-20', 12, '2026-04-01'
    ))
    conn.executemany('''
        INSERT INTO fact_offer_skills (offer_id, skill, skill_uri, source, confidence, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', [
        ('offer-finance-v3', 'audit', None, 'esco', 1.0, '2026-03-20T00:00:00Z'),
        ('offer-finance-v3', 'reporting', None, 'esco', 1.0, '2026-03-20T00:00:00Z'),
        ('offer-finance-v3', 'Excel', None, 'esco', 1.0, '2026-03-20T00:00:00Z'),
    ])
    conn.commit()
    conn.close()

    monkeypatch.setattr(offers_routes, 'DB_PATH', db_path)
    detail_resp = client.get('/offers/offer-finance-v3/detail', params=[
        ('profile_role_block', 'finance_ops'),
        ('profile_secondary_role_blocks', 'business_analysis'),
        ('profile_domains', 'finance'),
        ('profile_signals', 'audit'),
        ('profile_signals', 'reporting'),
        ('profile_summary', 'Profil orienté finance opérationnelle.'),
        ('matching_score', '84'),
    ])
    assert detail_resp.status_code == 200
    body = detail_resp.json()
    assert body['scoring_v2']['score_pct'] >= 0
    assert body['scoring_v3']['score_pct'] >= 0
    assert body['scoring_v3']['summary']
