from api.utils.skill_display import display_skill_label


def test_display_label_shortening_analysis_dashboard():
    raw = "analyse de données et création de dashboard"
    assert display_skill_label(raw) == "Analyse de données"


def test_display_label_project_management():
    raw = "gestion de projet agile et coordination"
    assert display_skill_label(raw) == "Gestion de projet"


def test_display_label_automation_reduction():
    raw = "mise en place de process d'automatisation"
    assert display_skill_label(raw) == "Automatisation"


def test_display_label_excel_advanced():
    raw = "excel avance tableau croisé analyse"
    assert display_skill_label(raw) == "Excel avancé"


def test_display_label_business_intelligence():
    raw = "business intelligence"
    assert display_skill_label(raw) == "Business Intelligence"


def test_display_label_frontend_override():
    raw = "mettre en œuvre le design front end d’un site web"
    assert display_skill_label(raw) == "Frontend"


def test_display_label_erp_override():
    raw = "gérer le système normalisé de planification des ressources d'une entreprise"
    assert display_skill_label(raw) == "ERP"


def test_display_label_ui_design_override():
    raw = "schéma de conception d’interface utilisateur"
    assert display_skill_label(raw) == "UI Design"
