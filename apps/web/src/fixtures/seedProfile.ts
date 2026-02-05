/**
 * Profil seed pour Akim Guentas - Testing Week V0
 *
 * Ce profil est la source de vérité pour les tests matching.
 * Il est compatible avec extract_profile() du backend.
 *
 * Usage:
 *   import { SEED_PROFILE } from '../fixtures/seedProfile';
 *   useProfileStore.getState().setUserProfile(SEED_PROFILE);
 */

export const SEED_PROFILE = {
  id: "akim_guentas_v0",

  // Skills normalisées - signal principal (70% du score)
  // Inclut variantes FR/EN pour maximiser les matches
  skills: [
    // Signal fort - cœur de métier
    "analyse de données",
    "data analysis",
    "data analyst",
    "analyst",
    "normalisation",
    "indicateurs",
    "kpi",
    "reporting",

    // Outils BI
    "power bi",
    "powerbi",
    "tableau",
    "excel",
    "tableur",

    // Tech
    "python",
    "sql",
    "api",
    "json",
    "csv",

    // Automatisation
    "automatisation",
    "make",

    // Décisionnel
    "aide à la décision",
    "business intelligence",
    "bi",
  ],

  // Langues (15% du score)
  languages: [
    "français",
    "anglais",
  ],

  // Niveau d'études (10% du score) - ordinal 4 (bac+5)
  education: "bac+5",

  // Pays préférés (5% du score) - vide = accepte tout
  preferred_countries: [] as string[],
};

/**
 * Profil avec préférences géographiques (variante pour tests)
 */
export const SEED_PROFILE_GEO = {
  ...SEED_PROFILE,
  id: "akim_guentas_v0_geo",
  preferred_countries: [
    "france",
    "allemagne",
    "belgique",
    "pays-bas",
    "royaume-uni",
    "suisse",
  ],
};

/**
 * Ce que le profil NE MATCHE PAS (pour comprendre les plafonds)
 *
 * - Software engineering / dev logiciel → skills absentes
 * - Data science ML/DL → skills absentes
 * - Marketing opérationnel → skills absentes
 * - Chef de projet généraliste → skills partielles
 *
 * Si une offre demande ces skills, le score skills sera bas,
 * donc le score total plafonné à ~30% (langues + études + pays).
 */
export const PROFILE_EXCLUSIONS = [
  "software engineer",
  "développeur logiciel",
  "backend developer",
  "frontend developer",
  "data scientist",
  "machine learning",
  "deep learning",
  "tensorflow",
  "pytorch",
  "marketing opérationnel",
  "community manager",
  "chef de projet généraliste",
];
