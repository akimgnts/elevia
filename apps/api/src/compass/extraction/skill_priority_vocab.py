from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SkillPriorityRule:
    label: str
    aliases: tuple[str, ...]
    candidate_type: str
    priority_level: str


P1_RULES: tuple[SkillPriorityRule, ...] = (
    SkillPriorityRule("Python", ("python", "python programmation informatique"), "language", "P1"),
    SkillPriorityRule("SQL", ("sql",), "language", "P1"),
    SkillPriorityRule("Excel", ("excel", "utiliser un logiciel de tableur", "microsoft excel"), "tool", "P1"),
    SkillPriorityRule("Power BI", ("power bi", "powerbi", "power bl"), "tool", "P1"),
    SkillPriorityRule("Tableau", ("tableau",), "tool", "P1"),
    SkillPriorityRule("PostgreSQL", ("postgresql", "postgres", "postgre"), "database", "P1"),
    SkillPriorityRule("Databricks", ("databricks",), "platform", "P1"),
    SkillPriorityRule("Docker", ("docker",), "platform", "P1"),
    SkillPriorityRule("Kubernetes", ("kubernetes", "k8s"), "platform", "P1"),
    SkillPriorityRule("AWS", ("aws", "amazon web services"), "platform", "P1"),
    SkillPriorityRule("Azure", ("azure", "microsoft azure"), "platform", "P1"),
    SkillPriorityRule("GCP", ("gcp", "google cloud platform"), "platform", "P1"),
    SkillPriorityRule("FastAPI", ("fastapi", "fast api"), "framework", "P1"),
    SkillPriorityRule("Flask", ("flask",), "framework", "P1"),
    SkillPriorityRule("React", ("react", "reactjs", "react.js"), "framework", "P1"),
    SkillPriorityRule("Salesforce", ("salesforce",), "platform", "P1"),
    SkillPriorityRule("SAP", ("sap",), "platform", "P1"),
    SkillPriorityRule("Looker Studio", ("looker studio", "google looker studio"), "tool", "P1"),
    SkillPriorityRule("scikit-learn", ("scikit learn", "scikit-learn", "sklearn"), "framework", "P1"),
    SkillPriorityRule("TensorFlow", ("tensorflow",), "framework", "P1"),
    SkillPriorityRule("PyTorch", ("pytorch", "py torch"), "framework", "P1"),
    SkillPriorityRule("OpenCV", ("opencv", "open cv"), "framework", "P1"),
    SkillPriorityRule("JavaScript", ("javascript", "javascript framework"), "language", "P1"),
    SkillPriorityRule("Scala", ("scala",), "language", "P1"),
    SkillPriorityRule("HubSpot", ("hubspot",), "platform", "P1"),
    SkillPriorityRule("WordPress", ("wordpress",), "platform", "P1"),
    SkillPriorityRule("Mailchimp", ("mailchimp",), "platform", "P1"),
    SkillPriorityRule("Canva", ("canva",), "tool", "P1"),
    SkillPriorityRule("PowerPoint", ("powerpoint", "power point", "microsoft powerpoint"), "tool", "P1"),
)


WATCHLIST_RULES: tuple[SkillPriorityRule, ...] = (
    SkillPriorityRule("English", ("english", "anglais", "anglais professionnel", "anglais courant"), "language", "P2"),
    SkillPriorityRule("Audit", ("audit", "audit interne"), "practice", "P2"),
    SkillPriorityRule("Internal Control", ("internal control", "controle interne"), "practice", "P2"),
    SkillPriorityRule("Compliance", ("compliance", "conformite"), "practice", "P2"),
    SkillPriorityRule("Financial Analysis", ("financial analysis", "analyse financiere"), "domain", "P3"),
    SkillPriorityRule("Financial Reporting", ("financial reporting", "reporting financier"), "practice", "P2"),
    SkillPriorityRule("CRM Management", ("crm management", "crm", "gestion de la relation client"), "domain", "P3"),
    SkillPriorityRule("Digital Marketing", ("digital marketing", "marketing digital", "techniques de marketing numerique"), "domain", "P3"),
    SkillPriorityRule("Email Marketing", ("email marketing", "emailing", "campagnes email", "envois emailing"), "practice", "P2"),
    SkillPriorityRule("Supply Chain Management", ("supply chain management", "supply chain"), "domain", "P3"),
    SkillPriorityRule("Procurement", ("procurement", "achat", "purchasing"), "practice", "P2"),
    SkillPriorityRule("Business Intelligence", ("business intelligence", "informatique decisionnelle"), "domain", "P3"),
    SkillPriorityRule("Data Analysis", ("data analysis", "analyse de donnees"), "domain", "P3"),
    SkillPriorityRule("Machine Learning", ("machine learning", "apprentissage automatique"), "domain", "P3"),
    SkillPriorityRule("Cloud Architecture", ("cloud architecture",), "domain", "P3"),
    SkillPriorityRule(
        "Legal Analysis",
        (
            "legal analysis",
            "legal counsel",
            "conseiller juridique",
            "juriste financier",
            "analyse reglementaire",
            "documentation juridique",
        ),
        "domain",
        "P3",
    ),
    SkillPriorityRule("Software API", ("software api", "rest api", "api rest", "api"), "domain", "P3"),
    SkillPriorityRule("DevOps", ("devops",), "domain", "P3"),
    SkillPriorityRule(
        "Natural Language Processing",
        ("nlp", "traitement automatique du langage naturel"),
        "domain",
        "P3",
    ),
    SkillPriorityRule(
        "Data Quality",
        ("data quality", "qualite des donnees"),
        "domain",
        "P3",
    ),
    SkillPriorityRule(
        "Automation",
        ("automation", "workflow automation"),
        "practice",
        "P2",
    ),
    SkillPriorityRule(
        "Query Optimization",
        ("query optimization",),
        "practice",
        "P2",
    ),
    SkillPriorityRule(
        "Lead Qualification",
        ("lead qualification", "qualification de leads", "qualification d opportunites"),
        "practice",
        "P2",
    ),
    SkillPriorityRule(
        "Prospecting",
        ("prospecting", "prospection", "prospection telephonique"),
        "practice",
        "P2",
    ),
    SkillPriorityRule(
        "Sales Follow-up",
        ("sales follow up", "sales follow-up", "suivi portefeuille clients", "suivi de prospects"),
        "practice",
        "P2",
    ),
    SkillPriorityRule(
        "Quote Preparation",
        ("quote preparation", "preparation de devis", "preparation d offres"),
        "practice",
        "P2",
    ),
    SkillPriorityRule(
        "Business Development",
        ("business development", "developpement commercial"),
        "domain",
        "P3",
    ),
    SkillPriorityRule(
        "Market Analysis",
        ("market analysis", "veille marche", "analyses de concurrence"),
        "practice",
        "P2",
    ),
    SkillPriorityRule(
        "Commercial Reporting",
        ("commercial reporting", "reporting commercial"),
        "practice",
        "P2",
    ),
    SkillPriorityRule(
        "Sales Argumentation",
        ("sales argumentation", "argumentaire commercial", "argumentaires marche"),
        "practice",
        "P2",
    ),
    SkillPriorityRule(
        "Internal Communication",
        ("internal communication", "communication interne"),
        "domain",
        "P3",
    ),
    SkillPriorityRule(
        "Content Writing",
        ("content writing", "redaction de contenus"),
        "practice",
        "P2",
    ),
    SkillPriorityRule(
        "Newsletter Production",
        ("newsletter production", "newsletter", "newsletters"),
        "practice",
        "P2",
    ),
    SkillPriorityRule(
        "Event Coordination",
        ("event coordination", "coordination evenementielle"),
        "practice",
        "P2",
    ),
    SkillPriorityRule(
        "Editorial Planning",
        ("editorial planning", "planning editorial", "calendrier editorial"),
        "practice",
        "P2",
    ),
    SkillPriorityRule(
        "Campaign Reporting",
        ("campaign reporting", "reporting de campagne", "reporting mensuel"),
        "practice",
        "P2",
    ),
    SkillPriorityRule(
        "Management Control",
        ("management control", "controle de gestion"),
        "domain",
        "P3",
    ),
    SkillPriorityRule(
        "Budget Tracking",
        ("budget tracking", "suivi budgetaire", "ecarts budget realise", "suivi de budgets"),
        "practice",
        "P2",
    ),
    SkillPriorityRule(
        "Monthly Closing",
        ("monthly closing", "cloture mensuelle"),
        "practice",
        "P2",
    ),
    SkillPriorityRule(
        "Accounts Payable",
        ("accounts payable", "comptabilite fournisseurs"),
        "domain",
        "P3",
    ),
    SkillPriorityRule(
        "Invoice Processing",
        ("invoice processing", "traitement des factures", "controle des factures"),
        "practice",
        "P2",
    ),
    SkillPriorityRule(
        "Reconciliation",
        ("reconciliation", "rapprochement", "rapprochement bancaire", "rapprochement avec commandes et receptions"),
        "practice",
        "P2",
    ),
    SkillPriorityRule(
        "Dispute Handling",
        ("dispute handling", "suivi des litiges", "gestion des litiges"),
        "practice",
        "P2",
    ),
    SkillPriorityRule(
        "Payment Scheduling",
        ("payment scheduling", "preparation des paiements hebdomadaires", "preparation des echeanciers", "suivi paiements"),
        "practice",
        "P2",
    ),
    SkillPriorityRule(
        "HR Administration",
        ("hr administration", "administration du personnel", "suivi rh"),
        "domain",
        "P3",
    ),
    SkillPriorityRule(
        "Recruitment",
        ("recruitment", "recrutement", "entretiens de recrutement", "prequalification telephonique"),
        "practice",
        "P2",
    ),
    SkillPriorityRule(
        "Onboarding",
        ("onboarding", "parcours d onboarding", "support integration"),
        "practice",
        "P2",
    ),
    SkillPriorityRule(
        "Personnel File Management",
        ("personnel file management", "suivi dossiers salaries", "dossiers candidats"),
        "practice",
        "P2",
    ),
    SkillPriorityRule(
        "Training Coordination",
        ("training coordination", "plan de formation"),
        "practice",
        "P2",
    ),
    SkillPriorityRule(
        "ERP Usage",
        ("erp usage", "dans sap", "parametres d approvisionnement"),
        "practice",
        "P2",
    ),
    SkillPriorityRule(
        "Inventory Management",
        ("inventory management", "gestion des stocks", "suivi des stocks"),
        "practice",
        "P2",
    ),
    SkillPriorityRule(
        "Vendor Follow-up",
        ("vendor follow-up", "suivi fournisseurs", "relances fournisseurs"),
        "practice",
        "P2",
    ),
    SkillPriorityRule(
        "Purchase Order Management",
        ("purchase order management", "passation de commandes fournisseurs", "commandes fournisseurs"),
        "practice",
        "P2",
    ),
    SkillPriorityRule(
        "Logistics Coordination",
        ("logistics coordination", "coordination avec les prestataires", "coordinateur logistique"),
        "practice",
        "P2",
    ),
    SkillPriorityRule(
        "Transport Operations",
        ("transport operations", "operations transport", "outil transport", "organisation de tournees"),
        "practice",
        "P2",
    ),
    SkillPriorityRule(
        "Incident Management",
        ("incident management", "incidents de livraison", "traitement d incidents de livraison"),
        "practice",
        "P2",
    ),
    SkillPriorityRule(
        "Operational Coordination",
        ("operational coordination", "coordination production", "coordination entrepot", "coordination operationnelle"),
        "practice",
        "P2",
    ),
    SkillPriorityRule(
        "Reporting",
        ("reporting", "tableaux de suivi", "reporting hebdomadaire"),
        "practice",
        "P2",
    ),
)


WEAK_SIGNAL_RULES: tuple[SkillPriorityRule, ...] = (
    SkillPriorityRule("Communication", ("communication",), "soft_skill", "P4"),
    SkillPriorityRule("Leadership", ("leadership",), "soft_skill", "P4"),
)


ALL_RULES: tuple[SkillPriorityRule, ...] = P1_RULES + WATCHLIST_RULES + WEAK_SIGNAL_RULES


LOCAL_ABSTRACTION_COLLISIONS: dict[str, tuple[str, ...]] = {
    "Python": ("Statistical Programming",),
    "Power BI": ("Business Intelligence",),
    "FastAPI": ("Software API",),
    "PostgreSQL": ("Database Design",),
    "Databricks": ("Data Engineering",),
    "Salesforce": ("CRM Management",),
    "SQL": ("Data Analysis",),
    "Looker Studio": ("Business Intelligence",),
    "Flask": ("Software API",),
    "OpenCV": ("Machine Learning",),
    "JavaScript": ("Frontend Development",),
    "Scala": ("Backend Development",),
    "HubSpot": ("CRM Management",),
    "Mailchimp": ("Email Marketing",),
    "PowerPoint": ("Communication",),
    "SAP": ("ERP Usage",),
}


SUMMARY_DERIVATIONS: dict[str, tuple[str, ...]] = {
    "Power BI": ("Business Intelligence",),
    "FastAPI": ("Software API",),
    "Salesforce": ("CRM Management",),
    "Databricks": ("Data Engineering",),
    "Looker Studio": ("Business Intelligence",),
    "Flask": ("Software API",),
    "OpenCV": ("Machine Learning",),
    "JavaScript": ("Frontend Development",),
    "Scala": ("Backend Development",),
    "HubSpot": ("CRM Management",),
    "Mailchimp": ("Email Marketing",),
    "WordPress": ("Digital Marketing",),
    "SAP": ("ERP Usage",),
}
