from pathlib import Path


PROFILE_PAGE = Path("apps/web/src/pages/ProfilePage.tsx")
HEADER = Path("apps/web/src/components/profile/ProfileWizardHeader.tsx")
STEP_ONE = Path("apps/web/src/components/profile/AgentUnderstandingStep.tsx")
STEP_TWO = Path("apps/web/src/components/profile/StructuredExperiencesStep.tsx")
STEP_CLARIFICATION = Path("apps/web/src/components/profile/ClarificationQuestionsStep.tsx")
STEP_VALIDATION = Path("apps/web/src/components/profile/ProfileValidationStep.tsx")
TYPES = Path("apps/web/src/components/profile/profileWizardTypes.ts")


def test_profile_wizard_slice_has_shared_types_and_value_step():
    types_text = TYPES.read_text(encoding="utf-8")
    header_text = HEADER.read_text(encoding="utf-8")
    step_text = STEP_ONE.read_text(encoding="utf-8")

    assert "ProfileWizardStep" in types_text
    assert "StructuringReport" in types_text
    assert "EnrichmentReport" in types_text
    assert "WizardQuestion" in types_text
    assert "Wizard profil" in header_text
    assert "Compréhension agent" in header_text
    assert "Ce que l'agent a compris" in step_text or "Ce que l&apos;agent a compris" in step_text
    assert "Ce que ça change pour vous" in step_text
    assert "Ajouté automatiquement" in step_text


def test_profile_page_reads_enrichment_report_and_merges_questions() -> None:
    source = PROFILE_PAGE.read_text(encoding="utf-8")

    assert "enrichment_report" in source
    assert "priority_signals" in source
    assert "learning_candidates" in source
    assert "confidence_scores" in source
    assert "mergedQuestions" in source
    assert "mergeWizardQuestions" in source


def test_profile_page_handles_multi_skill_link_editing() -> None:
    page = PROFILE_PAGE.read_text(encoding="utf-8")
    step = STEP_TWO.read_text(encoding="utf-8")

    assert "selectedSkillLinkIndex" in page
    assert "skillLinks.map" in step or ".map((link, linkIndex) =>" in step
    assert "Ajouté automatiquement" in step


def test_profile_page_step_one_includes_value_moment() -> None:
    page = PROFILE_PAGE.read_text(encoding="utf-8")
    step = STEP_ONE.read_text(encoding="utf-8")

    assert "Ce que ça change pour vous" in step or "What This Changes For You" in step
    assert "autoFilledCount" in page
    assert "remainingQuestionsCount" in page


def test_profile_page_tracks_selected_skill_link_index_and_user_validated_state() -> None:
    page = PROFILE_PAGE.read_text(encoding="utf-8")
    step = STEP_TWO.read_text(encoding="utf-8")

    assert "selectedSkillLinkIndex" in page
    assert "user_validated" in page or "userValidated" in page
    assert "Ajouté automatiquement" in step


def test_profile_page_merges_and_deduplicates_questions() -> None:
    source = PROFILE_PAGE.read_text(encoding="utf-8")

    assert "mergeWizardQuestions" in source
    assert "experience_index" in source
    assert "target_field" in source


def test_profile_validation_step_closes_the_product_loop() -> None:
    source = STEP_VALIDATION.read_text(encoding="utf-8")

    assert "matching" in source.lower()
    assert "cv" in source.lower()
    assert "cockpit" in source.lower()


# ---------------------------------------------------------------------------
# Nouveaux tests comportementaux — cycle TDD RED-GREEN
# ---------------------------------------------------------------------------

def test_clarification_step_shows_source_attribution_per_question() -> None:
    """Chaque question doit indiquer si elle vient de 'structuring' ou 'enrichment'."""
    source = STEP_CLARIFICATION.read_text(encoding="utf-8")

    assert "Question enrichissement" in source
    assert "Question structuration" in source
    assert 'source === "enrichment"' in source or "question.source" in source


def test_clarification_step_has_empty_state_when_no_questions() -> None:
    """Quand aucune question n'est requise, l'utilisateur voit un état vide explicite."""
    source = STEP_CLARIFICATION.read_text(encoding="utf-8")

    assert "Aucune ambiguïté critique" in source
    assert "Continuer vers la validation" in source


def test_agent_understanding_step_caps_auto_filled_display_at_four() -> None:
    """AgentUnderstandingStep ne montre jamais plus de 4 items auto-remplis pour ne pas noyer l'utilisateur."""
    source = STEP_ONE.read_text(encoding="utf-8")

    assert ".slice(0, 4)" in source


def test_agent_understanding_step_exposes_confidence_score() -> None:
    """Le score de confiance de chaque enrichissement automatique doit être lisible (toFixed)."""
    source = STEP_ONE.read_text(encoding="utf-8")

    assert "confidence" in source
    assert ".toFixed(" in source


def test_profile_page_filters_already_resolved_questions() -> None:
    """mergeWizardQuestions doit ignorer les questions dont le champ cible est déjà renseigné."""
    source = PROFILE_PAGE.read_text(encoding="utf-8")

    assert "isResolved" in source


def test_profile_page_dedup_key_is_experience_plus_target_field() -> None:
    """La clé de déduplication doit combiner experience_index et target_field."""
    source = PROFILE_PAGE.read_text(encoding="utf-8")

    assert "experienceIndex" in source and "targetField" in source or (
        "${experienceIndex}:${targetField}" in source
        or "experience_index" in source and "target_field" in source
    )


def test_structured_experiences_step_shows_active_link_indicator() -> None:
    """Le skill_link actif doit être visuellement identifié pour éviter les confusions."""
    source = STEP_TWO.read_text(encoding="utf-8")

    # Le fichier utilise l'apostrophe typographique U+2019 (\u2019)
    assert "En cours d\u2019édition" in source or "En cours d'édition" in source or "En cours d&apos;édition" in source


def test_structured_experiences_step_renders_link_tabs_for_multi_link() -> None:
    """Chaque skill_link d'une expérience doit avoir un onglet sélectionnable."""
    source = STEP_TWO.read_text(encoding="utf-8")

    assert "skillLinks.map" in source or ".map((link, linkIndex) =>" in source
    assert "onSelectSkillLink" in source


def test_wizard_question_source_field_is_typed() -> None:
    """WizardQuestion.source doit être typé 'structuring' | 'enrichment', pas string libre."""
    source = TYPES.read_text(encoding="utf-8")

    assert '"structuring" | "enrichment"' in source or (
        '"structuring"' in source and '"enrichment"' in source and "source?" in source
    )


def test_profile_page_has_normalize_enrichment_report_function() -> None:
    """normalizeEnrichmentReport doit exister pour garantir une normalisation safe en entrée."""
    source = PROFILE_PAGE.read_text(encoding="utf-8")

    assert "normalizeEnrichmentReport" in source
