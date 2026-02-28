from profile.profile_cluster import detect_profile_cluster


def test_profile_cluster_data_it_dominant():
    skills = [
        "analyse de données",
        "python",
        "sql",
        "informatique décisionnelle",
        "exploration de données",
        "programmation informatique",
        "cycle de développement logiciel",
        "etl",
        "business intelligence",
        "machine learning",
        "data analyst",
        "data engineer",
        "data scientist",
        "bi",
        "data analysis",
    ]
    result = detect_profile_cluster(skills)
    assert result["dominant_cluster"] == "DATA_IT"
    assert result["dominance_percent"] > 50
    assert result["note"] is None


def test_profile_cluster_marketing_dominant():
    skills = [
        "marketing",
        "communication",
        "crm",
        "sales",
        "vente",
        "business development",
        "prospection",
        "relation client",
        "gestion de la relation client",
        "seo",
        "social media",
        "growth",
        "marketing digital",
        "marketing analyst",
        "argumentaire de vente",
    ]
    result = detect_profile_cluster(skills)
    assert result["dominant_cluster"] == "MARKETING_SALES"
    assert result["dominance_percent"] > 50
    assert result["note"] is None


def test_profile_cluster_transversal():
    skills = [
        "analyse de données",
        "python",
        "sql",
        "business intelligence",
        "exploration de données",
        "data analyst",
        "marketing",
        "communication",
        "crm",
        "sales",
        "prospection",
        "marketing analyst",
        "finance",
        "audit",
        "comptabilité",
        "legal",
        "juridique",
        "logistique",
    ]
    result = detect_profile_cluster(skills)
    assert result["dominant_cluster"] in {"DATA_IT", "MARKETING_SALES", "FINANCE_LEGAL", "SUPPLY_OPS"}
    assert result["dominance_percent"] < 50
    assert result["note"] == "TRANSVERSAL"
