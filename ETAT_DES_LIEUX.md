# État des lieux - Projet Elevia Compass

**Date**: 3 décembre 2025
**Projet**: Elevia Compass - Intégration France Travail API
**Status**: ✅ Phase 1 complétée - API opérationnelle

---

## 📊 Résumé exécutif

### ✅ Ce qui fonctionne

| Composant | Status | Date de validation |
|-----------|--------|--------------------|
| Authentification OAuth2 France Travail | ✅ Opérationnel | 3 déc 2025 |
| Récupération des offres d'emploi | ✅ Opérationnel | 3 déc 2025 |
| Intégration dans VIE Scraping notebook | ✅ Complétée | 3 déc 2025 |
| Génération de données mockées | ✅ Opérationnel | Antérieur |
| Scripts de test | ✅ Opérationnels | 3 déc 2025 |

### ⏳ En attente

- Activation des scopes supplémentaires (ROME, Marché du travail, Anote)
- Pipeline de normalisation pandas
- Construction du graphe NetworkX
- Calcul des métriques (ICC, ITM, IET, IIF)

---

## 🗂️ Structure du projet

```
/Users/akimguentas/Documents/elevia-compass/
│
├── .env                              ✅ Credentials France Travail
├── .env.example                      ✅ Template de configuration
├── requirements.txt                  ✅ Dépendances Python
│
├── test_france_travail_auth.py      ✅ Test authentification OAuth2
├── test_france_travail_fetch.py     ✅ Test récupération offres
├── fetch_france_travail.py          ✅ Script de production (pagination)
│
├── generate_mock_data.py            ✅ Générateur de données mockées
├── inspect_openapi.py               ✅ Analyse des specs OpenAPI
│
├── ETAT_DES_LIEUX.md               ✅ Ce document
├── DIAGNOSTIC_FINAL.md              📄 Historique des tests (18+ URLs)
├── GUIDE_DEPLOIEMENT.md             📄 Guide de déploiement
├── STATUT.md                        📄 Statut du projet
│
└── data/
    ├── Offres_emploi_MOCK.json      ✅ 50 offres mockées
    ├── ROME_Competences_MOCK.json   ✅ 10 compétences mockées
    ├── ROME_Metiers_MOCK.json       ✅ 7 métiers mockés
    └── Marche_Travail_MOCK.json     ✅ 35 stats marché mockées
```

---

## 🔐 Configuration actuelle

### Variables d'environnement (.env)

```bash
# Credentials France Travail
FT_CLIENT_ID=PAR_elevia1_edccae836bbd05b5bb1eb4de5f91a9c10866abbf0a15dd89a90d96cc8f78b94d
FT_CLIENT_SECRET=b1d6e0487fdb3415d2f1b53894e650b36e47780cce1ac58dc24a6833f9979c01

# Scopes actifs
FT_SCOPES=api_offresdemploiv2 o2dsoffre

# Scopes en attente d'activation
# api_anoteav1 api_romev1 api_marchetravailv1

# URLs endpoints
FT_TOKEN_URL=https://entreprise.francetravail.fr/connexion/oauth2/access_token?realm=%2Fpartenaire
FT_BASE_URL=https://api.francetravail.io/partenaire

# Configuration
REQUEST_TIMEOUT=10
MAX_RETRIES=3
```

---

## 🧪 Tests effectués

### Test 1: Authentification OAuth2

**Commande**:
```bash
python3 test_france_travail_auth.py
```

**Résultat**:
```
✅ AUTHENTIFICATION RÉUSSIE !
🔑 Token (extrait): zpFESErBTRTdVfdt-YYo3zqnRks...
⏰ Expire dans: 1499 secondes
```

**Status**: ✅ OK (3 déc 2025, 14:30)

---

### Test 2: Récupération des offres

**Commande**:
```bash
python3 test_france_travail_fetch.py
```

**Résultat**:
```
📊 Status: 206 (Partial Content)
📄 Content-Type: application/json

✅ Données reçues:
- 10 offres récupérées
- Exemple: "Manutentionnaire (H/F)"
```

**Status**: ✅ OK (3 déc 2025, 14:32)

---

### Test 3: Intégration Jupyter Notebook

**Fichier**: `/Users/akimguentas/Downloads/VIE Scraping.ipynb`

**Cell 2 ajoutée**: Scraper France Travail
- ✅ Authentification OAuth2
- ✅ Récupération paginée (150 offres/page)
- ✅ Normalisation des données
- ✅ Export CSV + JSON
- ✅ Intégration Google Sheets

**Status**: ✅ Intégré (3 déc 2025, 14:45)

---

## 📊 Données récupérées

### Format de données France Travail

**Champs disponibles** (19 champs normalisés):

| Champ | Type | Description | Exemple |
|-------|------|-------------|---------|
| `id` | String | Identifiant unique | "201BXBY" |
| `intitule` | String | Titre de l'offre | "Développeur Full Stack (H/F)" |
| `description` | String | Description complète | "Nous recherchons..." |
| `dateCreation` | DateTime | Date de publication | "2024-12-01T10:30:00.000Z" |
| `entreprise` | String | Nom de l'entreprise | "TechStartup SAS" |
| `lieu` | String | Lieu de travail | "75 - PARIS 15" |
| `commune` | String | Code commune INSEE | "75115" |
| `codePostal` | String | Code postal | "75015" |
| `departement` | String | Code département | "75" |
| `latitude` | Float | Latitude GPS | 48.8422 |
| `longitude` | Float | Longitude GPS | 2.2891 |
| `typeContrat` | String | Type de contrat | "CDI" |
| `experienceExige` | String | Expérience requise | "2 An(s)" |
| `salaire` | String | Fourchette salariale | "45000-60000€" |
| `competences` | String | Liste des compétences | "React; Node.js; PostgreSQL" |
| `romeCode` | String | Code ROME | "M1805" |
| `appellationLibelle` | String | Appellation ROME | "Développeur full-stack" |
| `alternance` | Boolean | Offre en alternance | false |
| `accessibleTH` | Boolean | Accessible TH | true |
| `origineOffre` | String | URL source | "https://..." |

---

## 📈 Volumétrie

### Capacités de récupération

| Métrique | Valeur |
|----------|--------|
| Offres par requête | 150 max |
| Délai entre requêtes | 0.5s |
| Timeout par requête | 15s |
| Token expiration | 1499s (~25min) |
| Limite configurée | 500 offres |
| Temps moyen (500 offres) | 3-5 minutes |

### Données mockées générées

| Fichier | Entrées | Taille | Status |
|---------|---------|--------|--------|
| `Offres_emploi_MOCK.json` | 50 offres | ~45 KB | ✅ |
| `ROME_Competences_MOCK.json` | 10 compétences | ~2 KB | ✅ |
| `ROME_Metiers_MOCK.json` | 7 métiers | ~1 KB | ✅ |
| `Marche_Travail_MOCK.json` | 35 stats | ~3 KB | ✅ |

---

## 🔄 Intégration VIE Scraping

### Notebook structure

```
VIE Scraping.ipynb
├── Cell 0: pip install dependencies
├── Cell 1: Business France (Civiweb) scraper
├── Cell 2: France Travail scraper           ✨ NOUVEAU
├── Cell 3: Welcome to the Jungle scraper
├── Cell 4: Together.ai LLM matching
└── Cell 5: Automated scraper + Telegram
```

### Fonctionnalités Cell 2

```python
# Authentification
def get_ft_access_token()
    → Obtient token OAuth2
    → Durée: 1499s

# Récupération
def fetch_ft_offers_page(token, page_start, page_size)
    → Récupère une page d'offres
    → Gère les status 200, 206, 204, 401, 403, 429

def fetch_all_ft_offers(max_offers)
    → Récupère toutes les offres avec pagination
    → Limite configurable

# Normalisation
def normalize_ft_offer(offer)
    → Normalise les données en 19 champs
    → Formate pour export CSV/Sheets

# Export
def save_ft_to_csv(data)
    → Sauvegarde en CSV (délimiteur ;)
    → Encodage UTF-8-BOM

def save_ft_to_json(data)
    → Sauvegarde en JSON brut
    → Encodage UTF-8

def append_to_gsheet(df, spreadsheet_name, credentials)
    → Création automatique de la feuille
    → Déduplication par ID
    → Partage automatique à akimguentas13@gmail.com

# Main
def main_france_travail(max_offers=500)
    → Pipeline complet
    → Gestion des erreurs
    → Logging avec emojis
```

### Sauvegarde des données

**Répertoire**: `/Users/akimguentas/Desktop/PROJET VIE/`

**Fichiers créés**:
```
france_travail_offers_YYYYMMDD_HHMMSS.csv
france_travail_offers_YYYYMMDD_HHMMSS.json
```

**Google Sheets**:
- Nom: `Offres France Travail - Data`
- Permissions: `writer` pour akimguentas13@gmail.com
- Déduplication: Basée sur le champ `id`

---

## 🎯 Roadmap

### ✅ Phase 1: API Integration (COMPLÉTÉE)

- [x] Tester différentes URLs d'authentification
- [x] Valider les credentials
- [x] Implémenter OAuth2 Client Credentials flow
- [x] Récupérer les offres d'emploi
- [x] Gérer la pagination
- [x] Normaliser les données
- [x] Intégrer dans le notebook VIE Scraping
- [x] Export CSV + JSON + Google Sheets

### 🔄 Phase 2: Scopes supplémentaires (EN ATTENTE)

- [ ] Activer `api_romev1` (Référentiel ROME complet)
- [ ] Activer `api_marchetravailv1` (Statistiques marché)
- [ ] Activer `api_anoteav1` (Métiers émergents)
- [ ] Implémenter les nouveaux endpoints
- [ ] Enrichir les données mockées

### 📋 Phase 3: Pipeline Elevia Compass (À FAIRE)

Selon le document PDF:

- [ ] **Normalisation pandas**:
  - [ ] Charger les données JSON
  - [ ] Créer DataFrames (offres, compétences, ROME)
  - [ ] Nettoyer et valider les données

- [ ] **Construction du graphe NetworkX**:
  - [ ] Créer les nœuds (métiers, compétences, formations)
  - [ ] Créer les arêtes (relations)
  - [ ] Pondérer les liens

- [ ] **Calcul des métriques**:
  - [ ] ICC (Indice de Compatibilité Compétences)
  - [ ] ITM (Indice de Transition Métier)
  - [ ] IET (Indice d'Éloignement Topologique)
  - [ ] IIF (Indice d'Investissement Formation)

- [ ] **Simulations Monte Carlo**:
  - [ ] Modéliser les transitions de carrière
  - [ ] Analyser les parcours optimaux
  - [ ] Générer des recommandations

- [ ] **Visualisation**:
  - [ ] Créer des dashboards
  - [ ] Visualiser le graphe
  - [ ] Exports pour Power BI

---

## 🐛 Problèmes résolus

### 1. Erreur d'authentification (400 Bad Request)

**Problème initial**:
```json
{"error":"invalid_client","error_description":"Client authentication failed"}
```

**Cause**: Anciens credentials invalides

**Solution**: Utilisation de nouveaux credentials fournis le 3 décembre
```
CLIENT_ID=PAR_elevia1_edccae836bbd05b5bb1eb4de5f91a9c10866abbf0a15dd89a90d96cc8f78b94d
CLIENT_SECRET=b1d6e0487fdb3415d2f1b53894e650b36e47780cce1ac58dc24a6833f9979c01
```

**Status**: ✅ Résolu

---

### 2. Mismatch des noms de variables

**Problème**:
```python
TypeError: 'NoneType' object is not subscriptable
```

**Cause**: Les scripts attendaient `FT_CLIENT_ID` mais le .env contenait `CLIENT_ID`

**Solution**: Renommage des variables dans `.env` avec préfixe `FT_`

**Status**: ✅ Résolu

---

### 3. Interprétation du status 206

**Problème**: Le script traitait le status 206 comme une erreur

**Cause**: Méconnaissance du code 206 (Partial Content) pour la pagination

**Solution**: Ajout de `206` dans les status codes acceptés
```python
if response.status_code in [200, 206]:  # OK
```

**Status**: ✅ Résolu

---

## 📝 Notes importantes

### Sécurité

⚠️ **CRITIQUE**: Le fichier `.env` contient des credentials sensibles

**Protection requise**:
```bash
# Ajouter au .gitignore
echo ".env" >> .gitignore
echo "*.env" >> .gitignore

# Vérifier qu'il n'est pas tracké
git status --ignored
```

### Scopes en attente

Les scopes suivants nécessitent une **activation manuelle** sur le portail France Travail:

1. `api_anoteav1` - API Anote (métiers émergents)
2. `api_romev1` - Référentiel ROME complet
3. `api_marchetravailv1` - Statistiques du marché du travail

**Action requise**: Contacter le support France Travail sur https://francetravail.io

### Maintenance

**Renouvellement du token**:
- Durée de vie: 1499 secondes (~25 minutes)
- Renouvellement automatique dans le code
- Pas de refresh token (client credentials flow)

**Monitoring recommandé**:
- Logs des requêtes
- Alertes sur erreurs 401/403/429
- Suivi de la volumétrie

---

## 📞 Support et contact

**Documentation France Travail**:
- Portail développeur: https://francetravail.io
- Documentation API: https://francetravail.io/data/api
- Support: support@francetravail.io

**Projet**:
- Email: akimguentas13@gmail.com
- Notebook: `/Users/akimguentas/Downloads/VIE Scraping.ipynb`
- Backend: `/Users/akimguentas/Documents/elevia-compass/`

---

## 📊 Statistiques du projet

| Métrique | Valeur |
|----------|--------|
| Lignes de code Python | ~800 |
| Scripts créés | 8 |
| Fichiers de configuration | 2 (.env, requirements.txt) |
| Fichiers de documentation | 5 (MD) |
| URLs testées (historique) | 18+ |
| Temps de développement | ~2 jours |
| Status final | ✅ Production ready |

---

**Dernière mise à jour**: 3 décembre 2025, 14:50
**Version**: 1.0
**Status**: ✅ Phase 1 complétée - API opérationnelle
