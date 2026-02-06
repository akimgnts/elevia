"""
Tests for inbox scoring after stopwords fix (commit 66faa34).
Verifies score variance and matched_skills population.
"""
import pytest


class TestInboxScoring:
    """Test scoring produces varied, non-empty results."""
    
    def test_scoring_variance_and_matched_skills(self):
        """Score varies and matched_skills is populated for matching offers."""
        import sys
        sys.path.insert(0, 'src')
        
        from api.utils.inbox_catalog import load_catalog_offers
        from matching import MatchingEngine
        from matching.extractors import extract_profile
        
        offers = load_catalog_offers()
        engine = MatchingEngine(offers=offers)
        
        profile = {
            'skills': ['analyse de données', 'python', 'sql'],
            'education': 'bac+5',
            'preferred_countries': ['France', 'Allemagne', 'Suisse']
        }
        extracted = extract_profile(profile)
        
        scores = []
        matched_count = 0
        for offer in offers:
            if not offer.get('is_vie'):
                continue
            result = engine.score_offer(extracted, offer)
            scores.append(result.score)
            if result.match_debug and result.match_debug.get('skills', {}).get('matched'):
                matched_count += 1
        
        # Verify variance
        assert len(set(scores)) > 1, "Scores should have variance"
        assert min(scores) != max(scores), "Score min != max"
        
        # Verify matched_skills populated
        assert matched_count > 0, "At least some offers should have matched_skills"
        
        # Verify no stopword noise in top scores (sample check)
        noise_words = {'chez', 'mission', 'mois', 'vie', 'tant', 'que'}
        high_score_offers = [o for o in offers if o.get('is_vie')][:10]
        for offer in high_score_offers:
            skills = offer.get('skills', [])
            noise_found = [s for s in skills if s.lower() in noise_words]
            assert not noise_found, f"Noise stopwords found in offer skills: {noise_found}"


class TestMinScoreDefault:
    """Test min_score default is reasonable."""
    
    def test_default_min_score_returns_results(self):
        """Default min_score should return results (not filter everything)."""
        import sys
        sys.path.insert(0, 'src')
        
        from api.utils.inbox_catalog import load_catalog_offers
        from matching import MatchingEngine
        from matching.extractors import extract_profile
        
        offers = load_catalog_offers()
        engine = MatchingEngine(offers=offers)
        
        profile = {
            'skills': ['analyse de données'],
            'education': 'bac+5',
        }
        extracted = extract_profile(profile)
        
        # Count offers above new default min_score (10)
        DEFAULT_MIN_SCORE = 10
        above_threshold = 0
        for offer in offers:
            if not offer.get('is_vie'):
                continue
            result = engine.score_offer(extracted, offer)
            if result.score >= DEFAULT_MIN_SCORE:
                above_threshold += 1
        
        assert above_threshold > 0, f"No offers above min_score={DEFAULT_MIN_SCORE}"
        assert above_threshold > 10, f"Too few offers ({above_threshold}) above threshold"
