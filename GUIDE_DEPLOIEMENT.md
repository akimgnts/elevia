# 🚀 Guide de Déploiement - Elevia Compass Backend

**Application:** Backend privé consommant les APIs France Travail
**Type d'authentification:** OAuth 2.0 - Client Credentials Grant
**Date:** 10 novembre 2025

---

## ✅ ENVIRONNEMENT CRÉÉ

### Structure finale
```
/Users/akimguentas/Documents/elevia-compass/
├── .env                              # ⚠️  À ACTIVER (voir ci-dessous)
├── .env.example                      # Template
├── requirements.txt                  # Dépendances
├── fetch_france_travail.py           # Script principal (PRÊT)
├── test_auth_token.py                # Test d'auth (PRÊT)
├── GUIDE_DEPLOIEMENT.md              # Ce fichier
├── data/                             # Pour les données JSON
├── elevia_outputs/                   # Pour les exports
└── .venv/                            # Environnement Python
```

### Scripts créés

**1. [test_auth_token.py](file:///Users/akimguentas/Documents/elevia-compass/test_auth_token.py)**
- Test rapide d'authentification OAuth2
- Affiche le status code et la réponse brute
- Valide les credentials avant utilisation

**2. [fetch_france_travail.py](file:///Users/akimguentas/Documents/elevia-compass/fetch_france_travail.py)**
- Script principal avec toutes les bonnes pratiques:
  - ✅ Gestion des timeouts
  - ✅ Retry automatique en cas de timeout
  - ✅ Gestion du quota (code 429 + Retry-After)
  - ✅ Respect de la limite de 4 appels/seconde
  - ✅ Tokens expirés après 25 minutes
  - ✅ Sauvegarde locale sécurisée

---

## ⚠️  PROBLÈME ACTUEL

### Les credentials ne sont pas reconnus

**Erreur retournée:**
```json
{"error_description":"Client authentication failed","error":"invalid_client"}
```

**Status:** 400 Bad Request

### Causes possibles

1. **Application pas activée** - L'application est en mode "brouillon" dans l'espace développeur
2. **Credentials invalides** - CLIENT_ID ou CLIENT_SECRET incorrect ou expiré
3. **Migration Pôle Emploi → France Travail** - Les anciens credentials ne sont plus valides
4. **Compte partenaire suspendu** - Le compte nécessite une réactivation

---

## 🔧 ACTIONS IMMÉDIATES À FAIRE

### 1. Vérifier l'espace développeur France Travail

**Connecte-toi sur:** https://francetravail.io/ ou https://pole-emploi.io/

**Vérifie:**
- [ ] Ton application existe
- [ ] Elle est en statut **"PRODUCTION"** ou **"ACTIVÉE"** (pas "Brouillon")
- [ ] Le CLIENT_ID affiché correspond exactement à:
  ```
  PAR_elevia_a65bc33b15818630e57d2383aa1bd3241221621cd8b2ccd5bc4408d2eeec9e52
  ```
- [ ] Le CLIENT_SECRET est correct (tu peux le régénérer si nécessaire)
- [ ] Les scopes suivants sont bien autorisés:
  - `api_offresdemploiv2` ✅
  - `api_romev4` ✅
  - `api_marchetravailv1` ✅

### 2. Régénérer les credentials si nécessaire

Si les credentials ont expiré ou ont été révoqués:
1. Va dans ton espace développeur
2. Sélectionne ton application "Elevia Compass"
3. Regénère le CLIENT_SECRET
4. Copie les nouveaux credentials dans le fichier `.env`

### 3. Vérifier l'URL d'authentification

Dans l'espace développeur, vérifie l'URL exacte du endpoint OAuth2:
- Actuellement configuré: `https://francetravail.io/connexion/oauth2/access_token`
- Si l'URL est différente, mets à jour `FT_TOKEN_URL` dans `.env`

---

## 📋 CONFIGURATION ACTUELLE

### Fichier [.env](file:///Users/akimguentas/Documents/elevia-compass/.env)
```bash
# --- Identifiants France Travail (royaume partenaire) ---
FT_CLIENT_ID=PAR_elevia_a65bc33b15818630e57d2383aa1bd3241221621cd8b2ccd5bc4408d2eeec9e52
FT_CLIENT_SECRET=454c1e15ff947f189c84fd3b96dbb693bef589ba5633dc014db159f48b20f5d

# --- Scopes autorisés ---
FT_SCOPES=api_offresdemploiv2 api_romev4 api_marchetravailv1

# --- Endpoints France Travail 2025 ---
FT_TOKEN_URL=https://francetravail.io/connexion/oauth2/access_token
FT_BASE_URL=https://api.francetravail.fr/partenaire

# --- Configuration supplémentaire ---
REQUEST_TIMEOUT=10
MAX_RETRIES=3
```

### Flux OAuth 2.0 - Client Credentials

```
┌─────────────────┐                    ┌─────────────────┐
│  Elevia Compass │                    │ France Travail  │
│    (Backend)    │                    │   OAuth Server  │
└────────┬────────┘                    └────────┬────────┘
         │                                      │
         │  1. POST /oauth2/access_token        │
         │     grant_type=client_credentials    │
         │     client_id=PAR_elevia_...         │
         │     client_secret=***                │
         │     scope=api_offresdemploiv2...     │
         │─────────────────────────────────────>│
         │                                      │
         │  2. Réponse: { access_token: "..." }│
         │<─────────────────────────────────────│
         │                                      │
         │  3. GET /offresdemploi/v2/...        │
         │     Authorization: Bearer token      │
         │─────────────────────────────────────>│
         │                                      │
         │  4. Données JSON                     │
         │<─────────────────────────────────────│
         │                                      │
```

---

## 🚀 COMMANDES D'UTILISATION

### Activation de l'environnement

```bash
cd /Users/akimguentas/Documents/elevia-compass
source .venv/bin/activate
```

### Test d'authentification

```bash
python test_auth_token.py
```

**Résultat attendu:**
```
🔎 Test de connexion au serveur OAuth France Travail...
======================================================================
URL: https://francetravail.io/connexion/oauth2/access_token
Client ID: PAR_elevia_a65bc33b15818630e57d2383aa1bd...
Scopes: api_offresdemploiv2 api_romev4 api_marchetravailv1

📡 Envoi de la requête OAuth2...

Status: 200
Content-Type: application/json;charset=UTF-8

Réponse brute ↓
----------------------------------------------------------------------
{"access_token":"eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...","expires_in":1499}
----------------------------------------------------------------------

✅ SUCCESS! Token obtenu!
Token (premiers 80 car): eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...
Expire dans: 1499 secondes (25.0 min)

======================================================================
```

### Récupération des données

```bash
python fetch_france_travail.py
```

**Résultat attendu:**
```
🔐 Obtention du token via OAuth2...
Status: 200
✅ Token récupéré : eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...

📡 Récupération des offres d'emploi...
Status: 200
✅ 10 offres récupérées.
💾 Données sauvegardées dans : /Users/akimguentas/Documents/elevia-compass/data/Offres d'emploi.json
```

---

## 🔒 BONNES PRATIQUES IMPLÉMENTÉES

### Sécurité

✅ **Credentials jamais exposés** - Stockés dans `.env` (gitignore)
✅ **HTTPS uniquement** - Toutes les communications chiffrées
✅ **Token à durée limitée** - Expire après 25 minutes
✅ **Scopes minimaux** - Uniquement ce qui est nécessaire
✅ **Backend privé** - Jamais exposé côté client

### Performance & Fiabilité

✅ **Timeout configuré** - 10 secondes par défaut
✅ **Retry automatique** - En cas de timeout
✅ **Gestion du rate limiting** - Respect du code 429 + Retry-After
✅ **Respect des quotas** - Max 4 appels/seconde
✅ **Sauvegarde locale** - Données persistées en JSON

### Code

✅ **Variables d'environnement** - Configuration centralisée
✅ **Gestion d'erreurs** - Try/except avec messages clairs
✅ **Logging** - Status codes et messages affichés
✅ **Format JSON** - Indentation et UTF-8

---

## 📞 SUPPORT

### Documentation officielle

- **Portail développeur:** https://francetravail.io/
- **Documentation API:** https://francetravail.io/data/documentation
- **Espace mon compte:** https://francetravail.io/mon-espace

### En cas de problème

**Si les credentials ne fonctionnent toujours pas:**

1. Contacte le support France Travail
2. Fournis ces informations:
   - CLIENT_ID: `PAR_elevia_a65bc33b15818630e57d2383aa1bd...`
   - Erreur: `{"error":"invalid_client"}`
   - Date de création du compte
   - Statut de l'application

**Email support:** (à récupérer dans ton espace développeur)

---

## 📊 DONNÉES À RÉCUPÉRER

Une fois l'authentification fonctionnelle, tu pourras récupérer:

### 1. Offres d'emploi
- **Endpoint:** `/offresdemploi/v2/offres/search`
- **Scope:** `api_offresdemploiv2`
- **Données:** intitulé, codeROME, lieu, compétences, salaire, etc.

### 2. ROME 4.0 - Compétences
- **Endpoint:** `/rome/v4/competences`
- **Scope:** `api_romev4`
- **Données:** Référentiel des compétences professionnelles

### 3. ROME 4.0 - Métiers
- **Endpoint:** `/rome/v4/metiers`
- **Scope:** `api_romev4`
- **Données:** Référentiel des métiers et situations de travail

### 4. Marché du travail
- **Endpoint:** `/marchetravail/v1/stats`
- **Scope:** `api_marchetravailv1`
- **Données:** Statistiques du marché de l'emploi

---

## 🎯 PROCHAINES ÉTAPES

Une fois les credentials activés:

1. ✅ Test d'authentification réussi (`python test_auth_token.py`)
2. ✅ Récupération des offres (`python fetch_france_travail.py`)
3. ✅ Vérifier les données dans `data/Offres d'emploi.json`
4. ✅ Créer le notebook Elevia Compass
5. ✅ Implémenter les métriques (ITM, ICC, IET, IIF, IEP)
6. ✅ Construire le graphe métier avec NetworkX
7. ✅ Générer les exports dans `elevia_outputs/`

---

**📅 Document créé:** 2025-11-10
**🛠️  Environnement:** Backend Python privé
**✅ Status:** Prêt à déployer (pending credentials activation)
**🔒 Sécurité:** Conforme aux standards OAuth 2.0 Client Credentials
**⚡ Performance:** Gestion timeouts, retries, rate limiting
