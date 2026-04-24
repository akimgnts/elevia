import importlib


def _resolve(label: str):
    module = importlib.import_module("compass.canonical.weighted_store")
    module = importlib.reload(module)
    store = module.get_weighted_store()
    return module.resolve_weighted_skill(
        label,
        None,
        store=store,
        clamp_min=0.5,
        clamp_max=1.5,
    )


def test_batch1_concepts_resolve_to_core():
    expected = {
        "exploration de données": "skill:data_mining",
        "data exploration": "skill:data_mining",
        "exploratory data analysis": "skill:data_mining",
        "apprentissage automatique": "skill:machine_learning",
        "machine learning": "skill:machine_learning",
        "recruter du personnel": "skill:recruitment",
        "recrutement": "skill:recruitment",
        "recruitment": "skill:recruitment",
        "hiring": "skill:recruitment",
        "gérer les ressources humaines": "skill:human_resources_management",
        "ressources humaines": "skill:human_resources_management",
        "gestion des ressources humaines": "skill:human_resources_management",
        "human resources": "skill:human_resources_management",
        "hr management": "skill:human_resources_management",
        "argumentaire de vente": "skill:sales_pitch",
        "sales pitch": "skill:sales_pitch",
        "pitch commercial": "skill:sales_pitch",
        "méthodes de prospection": "skill:lead_generation",
        "prospection commerciale": "skill:lead_generation",
        "sales prospecting": "skill:lead_generation",
    }

    for label, canonical_id in expected.items():
        result = _resolve(label)
        assert result.canonical_id == canonical_id, label
        assert result.importance_level == "CORE", label


def test_batch1_explicit_exclusions_are_not_core():
    for label in ["machine", "ressources", "humaines", "gestion", "data", "acquisition", "talent"]:
        result = _resolve(label)
        assert result.importance_level != "CORE", label


def test_unrelated_existing_weighted_resolution_is_unchanged():
    data_analysis = _resolve("analyse de données")
    communication = _resolve("communication")

    assert data_analysis.canonical_id == "skill:data_analysis"
    assert data_analysis.importance_level == "CORE"
    assert communication.canonical_id == "skill:communication"
    assert communication.importance_level == "CONTEXT"
