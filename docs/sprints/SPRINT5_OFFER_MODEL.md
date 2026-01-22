SPRINT5_OFFER_MODEL.md
Définition de l’offre VIE (v1)

Dans Elevia VIE v1, une offre VIE est un objet minimal permettant de déterminer si une opportunité est cohérente avec le profil d’un candidat, indépendamment du discours RH ou des détails contractuels secondaires.

Champs retenus (liste fermée)

Les seuls champs considérés comme faisant partie d’une offre VIE exploitable dans Elevia VIE v1 sont :

offer_uid

title

company_name

country

required_skills

education_level

languages

vie_program

contract_type

Aucun autre champ n’est requis pour décider de la cohérence d’une offre avec un profil candidat.

Champs explicitement exclus

Les champs suivants sont volontairement exclus du périmètre Sprint 5, même s’ils sont présents dans la donnée source :

description longue de l’offre

détail des missions

avantages et bénéfices

salaire ou indemnité

durée du contrat

date de publication

localisation fine (ville, site, bureau)

niveau hiérarchique

promesses RH ou éléments marketing

Ces informations n’apportent pas de clarté supplémentaire au problème produit défini au Sprint 4.

Règle de fermeture

Tout champ non listé dans la section “Champs retenus” est hors périmètre Sprint 5 et ne doit pas être exploité, nettoyé, interprété ou transformé.

Toute logique de normalisation commune et toute source future (APEC, données utilisateurs, partenaires) devront produire ce même objet OfferEleviaV1 avant tout matching