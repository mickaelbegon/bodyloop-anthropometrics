# Research Report — bodyloop-anthropometrics
Date: 2026-09-11
Agent: A

---

## 1. BodyLoop SDK

### API réelle vs documentée dans le prompt
Le SDK Python BodyLoop (`bodyloop-sdk`) est généré automatiquement à partir d'une spécification OpenAPI via l'outil `openapi-python-client`. Le dépôt GitHub indique explicitement que ce SDK sert de **template** pour des SDKs multi-langages (JavaScript, Rust, etc.). L'API documentée dans le prompt est donc partielle — seule une poignée d'endpoints est visible dans le README public.

### Méthodes disponibles
D'après le README et la structure du dépôt, un seul endpoint est documenté publiquement :

| Méthode | Endpoint | Description |
|--------|----------|-------------|
| `get_probands_api_v2_probands_get.sync_detailed` | `GET /api/v2/probands` | Récupère la liste des probands (sujets d'étude) |

Exemple d'utilisation :
```python
from functools import partial
from bodyloop_sdk.client import AuthenticatedClient
from bodyloop_sdk.client.api.probands import get_probands_api_v2_probands_get

client = AuthenticatedClient(
    base_url="https://bodyloop-control-pc",
    verify_ssl=False,
    token="<YOUR_API_TOKEN_HERE>",
    timeout=10.0
)

get_probands = partial(get_probands_api_v2_probands_get.sync_detailed, client=client)
probands_response = get_probands()
print(probands_response.status_code)
```

> **TODO_SCIENTIFIC #1** : L'ensemble complet des endpoints de l'API BodyLoop n'est pas documenté publiquement. Il faut examiner la spécification OpenAPI interne pour connaître tous les endpoints disponibles (mesures anthropométriques, mouvements, données de sessions, etc.).

### Format des réponses (structures de données)
- Les réponses via `.sync_detailed` retournent un objet avec un attribut `status_code`.
- L'entité principale est le **proband** (sujet d'étude) — les champs détaillés ne sont pas documentés dans le README public.
- Le SDK est entièrement généré — les structures de données sont définies dans les modules Python générés dans `src/bodyloop_sdk/`.

### Version actuelle
- Version PyPI : **2026.9.9.6** (publiée le 9 septembre 2026)
- Versionnage sémantique au format `vYYYY.MM.DD.r`
- Python requis : **>= 3.11**
- Licence : MIT

---

## 2. Yeadon

### Version et compatibilité Python 3.11+
- Version PyPI actuelle : **1.5.0** (publiée le 22 juin 2024)
- Python requis : **3.8+** (compatible 3.8, 3.9, 3.10, 3.11, 3.12 — pas encore testé officiellement sur 3.13)
- Compatibilité Python 3.11+ : **confirmée**
- Licence : non précisée dans les sources consultées (à vérifier dans LICENSE.txt du dépôt)

### Les 95 clés de mesures (liste complète)

Les mesures sont organisées en 5 grandes régions. Source : `misc/meastemplate.txt` dans le dépôt GitHub `chrisdembia/yeadon`.

#### TORSE (Ls) — 21 mesures

Niveaux anatomiques :
- `Ls0` centre articulaire de la hanche
- `Ls1` ombilic
- `Ls2` dernière côte antérieure
- `Ls3` mamelon
- `Ls4` centre articulaire de l'épaule
- `Ls5` acromion
- `Ls6` sous le nez
- `Ls7` au-dessus de l'oreille
- `Ls8` sommet de la tête

**Longueurs** (mesurées depuis `Ls0`, sauf Ls6–Ls8 mesurées depuis `Ls5`) :
`Ls1L`, `Ls2L`, `Ls3L`, `Ls4L`, `Ls5L`, `Ls6L`, `Ls7L`, `Ls8L`

**Périmètres** (paramètre de stade) :
`Ls0p`, `Ls1p`, `Ls2p`, `Ls3p`, `Ls5p`, `Ls6p`, `Ls7p`

**Largeurs** :
`Ls0w`, `Ls1w`, `Ls2w`, `Ls3w`, `Ls4w`

**Profondeurs** :
`Ls4d`  *(remplace la largeur au niveau Ls4 car l'articulation de l'épaule rend la largeur difficile à mesurer)*

#### BRAS GAUCHE (La) — 18 mesures

Niveaux anatomiques :
- `La0` centre articulaire de l'épaule
- `La1` mi-bras *(non mesuré — positionné automatiquement à 0,5 × La2L)*
- `La2` centre articulaire du coude
- `La3` périmètre maximal de l'avant-bras
- `La4` centre articulaire du poignet
- `La5` base du pouce
- `La6` articulations (knuckles)
- `La7` ongles

**Longueurs** (depuis `La0`) :
`La2L`, `La3L`, `La4L`

**Longueurs** (depuis `La4`) :
`La5L`, `La6L`, `La7L`

**Périmètres** :
`La0p`, `La1p`, `La2p`, `La3p`, `La4p`, `La5p`, `La6p`, `La7p`

**Largeurs** *(niveaux 0–3 sont des cercles, pas de largeur) * :
`La4w`, `La5w`, `La6w`, `La7w`

#### BRAS DROIT (Lb) — 18 mesures

Mêmes niveaux que le bras gauche (La0→Lb0, etc.)

**Longueurs** (depuis `Lb0`) :
`Lb2L`, `Lb3L`, `Lb4L`

**Longueurs** (depuis `Lb4`) :
`Lb5L`, `Lb6L`, `Lb7L`

**Périmètres** :
`Lb0p`, `Lb1p`, `Lb2p`, `Lb3p`, `Lb4p`, `Lb5p`, `Lb6p`, `Lb7p`

**Largeurs** :
`Lb4w`, `Lb5w`, `Lb6w`, `Lb7w`

#### JAMBE GAUCHE (Lj) — 19 mesures

Niveaux anatomiques :
- `Lj0` centre articulaire de la hanche
- `Lj1` entrejambe
- `Lj2` mi-cuisse *(non mesuré — positionné automatiquement comme moyenne de Lj1L et Lj3L)*
- `Lj3` centre articulaire du genou
- `Lj4` périmètre maximal du mollet
- `Lj5` centre articulaire de la cheville
- `Lj6` talon
- `Lj7` voûte plantaire *(non mesuré — positionné automatiquement comme moyenne de Lj6L et Lj8L)*
- `Lj8` plante (ball of foot)
- `Lj9` ongles de pieds

**Longueurs** (depuis `Lj0`) :
`Lj1L`, `Lj3L`, `Lj4L`, `Lj5L`

**Longueurs** (depuis `Lj5`) :
`Lj6L`, `Lj8L`, `Lj9L`

**Périmètres** *(Lj0p n'est pas mesuré — calculé depuis Ls0p et Ls0w)* :
`Lj1p`, `Lj2p`, `Lj3p`, `Lj4p`, `Lj5p`, `Lj6p`, `Lj7p`, `Lj8p`, `Lj9p`

**Largeurs** *(niveaux 0–5 et 7 sont des cercles)* :
`Lj8w`, `Lj9w`

**Profondeurs** *(stade orienté antéro-postérieurement)* :
`Lj6d`

#### JAMBE DROITE (Lk) — 19 mesures

Mêmes niveaux que la jambe gauche (Lj0→Lk0, etc.)

**Longueurs** (depuis `Lk0`) :
`Lk1L`, `Lk3L`, `Lk4L`, `Lk5L`

**Longueurs** (depuis `Lk5`) :
`Lk6L`, `Lk8L`, `Lk9L`

**Périmètres** *(Lk0p non mesuré — calculé)* :
`Lk1p`, `Lk2p`, `Lk3p`, `Lk4p`, `Lk5p`, `Lk6p`, `Lk7p`, `Lk8p`, `Lk9p`

**Largeurs** :
`Lk8w`, `Lk9w`

**Profondeurs** :
`Lk6d`

**Récapitulatif des 95 mesures :**

| Région | Nb mesures |
|--------|-----------|
| Torse (Ls) | 21 |
| Bras gauche (La) | 18 |
| Bras droit (Lb) | 18 |
| Jambe gauche (Lj) | 19 |
| Jambe droite (Lk) | 19 |
| **Total** | **95** |

### API Python pour construire un Human

```python
import yeadon

# Depuis des fichiers
human = yeadon.Human('measurements.txt', 'configuration.txt')

# Depuis des dictionnaires Python (pas de fichier requis)
human = yeadon.Human(measurements_dict, cfg_dict)

# Accès aux propriétés globales
human.mass              # masse totale en kg
human.center_of_mass    # vecteur position depuis l'origine pelvienne
human.inertia           # tenseur d'inertie autour du centre de masse

# Propriétés par segment (ex: J1 = cuisse gauche)
human.J1.mass
human.J1.center_of_mass
human.J1.inertia
human.J1.pos            # position du segment
human.J1.end_pos        # position terminale
human.J1.rot_mat        # matrice de rotation

# Accès à tous les segments
for seg in human.segments:
    print(seg.mass)

# Méthodes de manipulation
human.set_CFG('name', value)          # modifier un angle articulaire
human.print_properties()              # afficher les données d'inertie
human.draw()                          # rendu 3D (nécessite MayaVi)
human.scale_human_by_mass()           # mise à l'échelle par masse mesurée
human.combine_inertia(solids_list)    # combiner l'inertie de solides sélectionnés
human.inertia_transformed(ref_frame)  # inertie dans un référentiel alternatif
human.write_measurements(filename)    # exporter les mesures
human.write_CFG(filename)             # exporter la configuration
```

### Repères difficiles identifiés

1. **La1 et Lb1** (mi-bras) : non mesuré, positionné automatiquement à `0,5 × La2L`. La mesure de `La1p` doit être prise à cet emplacement calculé.
2. **Lj2 et Lk2** (mi-cuisse) : non mesuré, calculé comme `(Lj1L + Lj3L) / 2`.
3. **Lj7 et Lk7** (voûte plantaire) : non mesuré, calculé comme `(Lj6L + Lj8L) / 2`.
4. **Lj0p / Lk0p** (périmètre de l'aine) : non mesuré, dérivé de `Ls0p` et `Ls0w`.
5. **Ls4d** : profondeur au lieu de largeur au niveau de l'épaule — prise de mesure non intuitive.
6. **Lj6d / Lk6d** (talon) : le stade du talon est orienté à 90° des autres (axe antéro-postérieur).

---

## 3. Hatze

### Équations marquées incorrectes/incomplètes (liste exhaustive)

Le README du dépôt `wspr/hatze-biomech` contient cette déclaration explicite :
> *"Many other calculations, however are still incomplete or, worse, **incorrect**; this shall hopefully be rectified in the coming weeks."*

Les calculs problématiques identifiés dans la liste TODO du README sont :

| Catégorie | Problème documenté |
|----------|-------------------|
| Calculs de paramètres de segments | Incomplets — la majorité des segments |
| Entrées d'angles articulaires | Seulement partiellement implémentées |
| Géométrie des pieds | Insuffisante — référence Dillon (2001) pour les améliorations |
| Géométrie de la tête/mâchoire | Insuffisamment détaillée |
| Genoux et doigts | Absents — pas d'articulation modélisée |
| Modèle dynamique | Pas encore intégré |
| Visualisation des orientations arbitraires | "Still half-baked" (citation exacte du README) |

> **Note** : Le README ne liste pas les équations problématiques par leur numéro dans les publications de Hatze. Les incorrections sont constatées dans l'implémentation mais ne sont pas indexées de manière précise.

### Ce qui peut être automatisé vs ce qui nécessite un audit scientifique

**Peut être automatisé :**
- Tracé géométrique et visualisation
- Transcription et traitement des mesures d'entrée
- Calculs de matrices de rotation
- Interface de saisie des paramètres

**Nécessite un audit scientifique :**
- Tous les calculs de masse et de moments d'inertie (potentiellement incorrects)
- Vérification des paramètres de segments par rapport aux données mesurées
- Tests comparatifs avec les résultats publiés par Hatze
- Comparaison avec les modèles Hanavan et Yeadon (non encore réalisée)

> **TODO_SCIENTIFIC #2** : Avant toute utilisation des calculs d'inertie de `hatze-biomech`, un audit complet équation par équation des publications Hatze (1979, 1980, 1981) est indispensable. Le code est potentiellement incorrect sur plusieurs segments.

### Références bibliographiques citées

1. **H. Hatze (1979)** — *Rapport technique CSIR* sur les paramètres de segments anthropomorphiques
2. **H. Hatze (1980)** — *Journal of Biomechanics*, vol. 13, pp. 833–843 — modèle mathématique
3. **H. Hatze (1981)** — *Rapport technique HOMSIM* — simulateur biomécanique
4. **M. Dillon (2001)** — *Thèse de doctorat*, Queensland University of Technology — biomécanique des amputés du pied

Licence du code : **Apache License v2.0**

---

## 4. BODIESReg

### Interface d'entrée attendue

**Format d'entrée actuel :**
- Fichiers de maillage **OBJ** (format vertex uniquement, avec ou sans couleurs de vertex)
- Maillages dérivés d'IRM acceptés (format nuage de points OBJ)
- Détection automatique des unités (mètres, centimètres, millimètres)
- Entrée via scripts — pas de module Python importable directement

**Mode automatique :** rendu de deux projections 2D orthogonales → détection de keypoints via MediaPipe → combinaison en coordonnées 3D → cinématique inverse → optimisation géométrique

**Mode manuel :** outils interactifs (vertex aligner, pose editor, correspondence selector)

### Ce qu'il faut adapter pour accepter des joints 3D BodyLoop directement

BODIESReg n'accepte pas nativement des coordonnées 3D de joints en entrée. Pour l'adapter :

1. **Supprimer les étapes 1 et 2** du pipeline (projection 2D + détection MediaPipe)
2. **Modifier l'initialisation** dans `utils_python/` pour accepter directement un tableau de coordonnées 3D de joints au lieu d'un fichier OBJ
3. **Appliquer la cinématique inverse** directement sur les joints 3D BodyLoop pour obtenir les paramètres de pose SMPL
4. **Conserver la phase d'optimisation géométrique** si un maillage 3D de référence est disponible
5. **Adapter les modules `pipeline_runner.py`** pour court-circuiter les étapes de vision par ordinateur

> **TODO_SCIENTIFIC #3** : Définir la correspondance exacte entre les joints BodyLoop (format JSON inconnu) et les 24 joints SMPL (convention de nommage / indexation). Cette correspondance est bloquante pour l'adaptation de BODIESReg.

**Points d'entrée Python :**

| Script | Rôle |
|--------|------|
| `scripts/main.py` | Traitement d'un scan ou d'un lot séquentiel |
| `scripts/batch_processor.py` | Traitement parallèle en lots (état redémarrable) |
| `scripts/load_registered_data.py` | Inspection des données enregistrées |
| `scripts/pipeline_runner.py` | Étapes individuelles du pipeline |
| `scripts/post_processor.py` | Extraction de mesures corporelles |

### Dépendances et compatibilité

| Dépendance | Version requise | Notes |
|-----------|----------------|-------|
| Python | 3.10 (recommandé) | |
| PyTorch | 2.8.0 (épinglé) | Requis pour LBFGS validé |
| chumpy | 0.70 | Pour le dépickling des modèles SMPL legacy |
| MediaPipe | — | Modèle `pose_landmarker_heavy.task` requis |
| Open3D | — | Visualisation et géométrie 3D |
| VPoser | 2.0 | Prior de pose (checkpoint requis) |
| Modèles SMPL | v1.1.0, SMPL-H, SMPL-X v1.1 | Fichiers à télécharger séparément |

> **Risque de compatibilité** : PyTorch 2.8.0 est une version très récente (épinglée). Le projet `bodyloop-anthropometrics` cible Python 3.11+ (BodyLoop SDK) — BODIESReg cible Python 3.10. Un environnement séparé pourrait être nécessaire.

---

## 5. SMPL / SMPL-X

### Licence du code vs licence des modèles

**Le code** (`vchoutas/smplx` sur GitHub) : disponible sous licence **non-commerciale pour la recherche scientifique**.

**Les modèles** (fichiers `.pkl` et `.npz` téléchargeables depuis smpl-x.is.tue.mpg.de, mano.is.tue.mpg.de, smpl.is.tue.mpg.de) : soumis à une licence distincte et plus restrictive, nécessitant une inscription préalable.

### Ce qu'on peut redistribuer vs ce qu'on ne peut pas

**Texte exact de la licence concernant la redistribution :**
> *"The Model & Software and the license herein granted shall not be copied, shared, distributed, re-sold, offered for re-sale, transferred or sub-licensed in whole or in part except that you may make one copy for archive purposes only."*

**Utilisation commerciale — texte exact :**
> *"incorporation in a commercial product, use in a commercial service, or production of other artifacts for commercial purposes"* — **explicitement interdit**

**Entraînement de modèles — texte exact :**
> *"train methods/algorithms/neural networks/etc. for commercial, pornographic, military, surveillance, or defamatory use of any kind"* — **explicitement interdit**

**Images des articles** : distribuées sous licence Getty Images — redistribution interdite.

**Licence commerciale** : contacter **ps-license@tue.mpg.de** (Max Planck Innovation GmbH).

**Droit applicable** : droit allemand (Convention des Nations Unies sur la vente internationale exclue).

> **TODO_SCIENTIFIC #4** : Vérifier si l'utilisation des modèles SMPL/SMPL-X dans le contexte du projet `bodyloop-anthropometrics` (usage interne, recherche biomécanique non-commerciale) est conforme à la licence. Si BodyLoop est une entreprise commerciale, l'utilisation est bloquée sans licence commerciale.

### Interface Python

Installation :
```bash
pip install smplx[all]
# ou
git clone https://github.com/vchoutas/smplx
python setup.py install
```

Structure des fichiers de modèles requise :
```
models/
├── smpl/
│   ├── SMPL_FEMALE.pkl
│   ├── SMPL_MALE.pkl
│   └── SMPL_NEUTRAL.pkl
├── smplh/
│   ├── SMPLH_FEMALE.pkl
│   └── SMPLH_MALE.pkl
└── smplx/
    ├── SMPLX_FEMALE.npz
    ├── SMPLX_MALE.npz
    └── SMPLX_NEUTRAL.npz
```

---

## 6. SKEL

### Licence

SKEL est disponible sous **licence non-commerciale pour la recherche scientifique** (similaire à SMPL-X). Le texte exact du LICENSE.txt n'était pas accessible publiquement sans authentification, mais le README indique :
> *"The code and model are available for non-commercial scientific research purposes as defined in LICENSE.txt"*

Pour un usage commercial : contacter **ps-licensing@tue.mpg.de**

Téléchargement des modèles depuis **skel.is.tue.mpg.de** (inscription requise).

### Avantages vs SMPL pour usage biomécanique

| Critère | SMPL | SKEL |
|---------|------|------|
| Sorties | Maillage de surface | Maillage squelettique + maillage de surface + joints anatomiques |
| Joints | 24 joints géométriques | Joints anatomiquement plausibles |
| Anatomie | Aucune représentation squelettique | Structure squelettique intégrée |
| Différentiabilité | Oui | Oui |
| Paramètres de forme | `betas` (10D) | `betas` (10D, même espace que SMPL) |
| Paramètres de pose | `theta` (72D) | `pose` (46D — angles en radians) |
| Compatibilité données | Mocap, SMPL | Mocap, SMPL, séquences AMASS |
| Utilisation biomécanique | Indirecte (via BODIESReg) | Directe (joints anatomiques en sortie) |
| Python version requise | 3.x | 3.12+ (mis à jour août 2025) |

**Avantages clés de SKEL pour `bodyloop-anthropometrics` :**
- Sortie directe de **positions de joints anatomiques** sans post-traitement
- Pose paramétrisée par 46 angles articulaires (plus proche d'une représentation biomécanique qu'un vecteur 72D)
- Framework différentiable pour le fitting aux données de capture de mouvement
- Compatible avec les séquences AMASS pour validation

> **TODO_SCIENTIFIC #5** : Déterminer si SKEL est suffisamment précis pour remplacer ou compléter Yeadon/Hatze pour les calculs d'inertie. SKEL donne des positions de joints mais pas de masses/inerties de segments.

---

## 7. Dépendances Python recommandées

Liste des packages avec versions minimales pour `pyproject.toml` :

```toml
[project]
name = "bodyloop-anthropometrics"
requires-python = ">=3.11"

[project.dependencies]
# BodyLoop SDK
bodyloop-sdk = ">=2026.9.9.6"

# Modèle inertiel de Yeadon
yeadon = ">=1.5.0"

# Calcul numérique (requis par yeadon)
numpy = ">=1.24.0"
pyyaml = ">=6.0"

# SMPL-X (code uniquement — modèles téléchargés séparément)
smplx = {extras = ["all"], version = ">=0.1.28"}

# Apprentissage profond (requis par SMPL-X et BODIESReg)
torch = ">=2.0.0"  # NOTE: BODIESReg épingle 2.8.0 — vérifier compatibilité

# Optionnel — visualisation SKEL
# aitviewer = ">=..."  # Linux uniquement pour la visualisation complète

[project.optional-dependencies]
dev = [
    "pytest>=7.0",
    "pytest-cov>=4.0",
]
```

> **Note sur torch** : BODIESReg épingle PyTorch 2.8.0 pour valider l'optimiseur LBFGS. Un environnement dédié pour BODIESReg est recommandé si la version de PyTorch dans le projet principal est différente.

> **Note sur MPI mesh** : la dépendance `mpi-mesh` de SKEL (pour la visualisation) est **Linux uniquement** — elle ne sera pas listée comme dépendance principale sous Windows.

---

## 8. Décisions scientifiques bloquantes (TODO_SCIENTIFIC)

| # | Décision | Référence |
|---|---------|-----------|
| 1 | L'ensemble complet des endpoints BodyLoop API n'est pas documenté publiquement. Obtenir et analyser la spécification OpenAPI interne pour connaître le format exact des données anthropométriques renvoyées. | § 1. BodyLoop SDK |
| 2 | Audit complet équation par équation du code `hatze-biomech` vs les publications Hatze (1979, 1980, 1981). Le README reconnaît des incorrections sans les indexer. Avant utilisation de tout calcul d'inertie issu de ce code, une validation scientifique est indispensable. | § 3. Hatze |
| 3 | Définir la correspondance exacte entre les joints 3D du SDK BodyLoop (format et indexation inconnus) et les 24 joints SMPL ainsi que les joints anatomiques de SKEL. Cette correspondance est bloquante pour tout pipeline de fitting. | § 4. BODIESReg |
| 4 | Vérifier la conformité d'utilisation des modèles SMPL/SMPL-X avec leur licence non-commerciale dans le contexte du projet. Si BodyLoop est une entité commerciale, une licence commerciale est obligatoire. Contacter ps-license@tue.mpg.de. | § 5. SMPL-X |
| 5 | Évaluer si SKEL peut remplacer ou compléter Yeadon pour les calculs d'inertie segmentaire. SKEL produit des joints anatomiques mais pas de masses ni de tenseurs d'inertie de segments. | § 6. SKEL |
| 6 | Valider que le modèle Yeadon (1.5.0) reste l'état de l'art pour l'estimation des propriétés inertielles à partir de mesures anthropométriques, ou identifier une alternative plus récente (post-2010). | § 2. Yeadon |

---

## 9. Points de risque et incompatibilités identifiés

### Risques de licence
- Les modèles SMPL, SMPL-X, et SKEL sont tous sous **licence non-commerciale** — leur utilisation dans un produit BodyLoop commercial est une violation contractuelle.
- Les images des publications SMPL-X sont sous licence Getty Images — non redistribuables.

### Incompatibilités de versions Python
- **BodyLoop SDK** : Python >= 3.11
- **BODIESReg** : Python 3.10 recommandé (pas de support 3.11+ confirmé)
- **SKEL** : Python 3.12+ (mis à jour août 2025)
- **Yeadon** : Python 3.8–3.12

→ Il est probablement impossible d'avoir tous ces composants dans le même environnement Python. Des **environnements virtuels séparés** ou des **conteneurs Docker** sont nécessaires.

### Incompatibilités de dépendances PyTorch
- BODIESReg épingle **PyTorch 2.8.0**
- SKEL et SMPL-X fonctionnent avec des versions plus récentes
- Ces conflits nécessitent des environnements séparés

### Fonctionnalités manquantes dans BODIESReg
- BODIESReg n'accepte pas de joints 3D en entrée directe — **adaptation custom requise**
- Pas d'API Python importable — **scripts uniquement**
- Dépendance à MediaPipe pour le mode automatique (modèle ~30 Mo à télécharger séparément)

### Données manquantes pour Yeadon
- Les 95 mesures nécessitent des protocoles de mesure anthropométrique standardisés (réf. Yeadon 1989-ii)
- Certaines mesures sont calculées implicitement (La1, Lj2, Lj7, etc.) — le protocole de capture doit en tenir compte

### Fiabilité incertaine de Hatze
- Le code `hatze-biomech` est explicitement marqué comme contenant des **erreurs potentielles** dans ses calculs d'inertie
- À utiliser uniquement après audit scientifique approfondi (cf. TODO_SCIENTIFIC #2)

---

## 10. Recommandations pour l'architecture

### Architecture recommandée en couches

```
┌─────────────────────────────────────────────────────┐
│  Interface BodyLoop (bodyloop-sdk)                  │
│  → Récupération des données brutes (API REST)       │
└────────────────────┬────────────────────────────────┘
                     │ données probands + captures
┌────────────────────▼────────────────────────────────┐
│  Couche d'adaptation (bodyloop-anthropometrics)     │
│  → Mapping joints BodyLoop ↔ conventions Yeadon     │
│  → Conversion unités et référentiels                │
└──────┬──────────────────────────────────┬───────────┘
       │ mesures anthropométriques        │ joints 3D
┌──────▼──────────┐              ┌────────▼──────────┐
│  Yeadon 1.5.0   │              │  SKEL / BODIESReg │
│  → 95 mesures   │              │  → Fitting SMPL   │
│  → masse/inertie│              │  → Joints anatom. │
└─────────────────┘              └────────────────────┘
```

### Séquence de développement recommandée

1. **Phase 1 — Exploration API BodyLoop** : Obtenir la spécification OpenAPI complète, identifier les endpoints anthropométriques réels (pas seulement `/api/v2/probands`)
2. **Phase 2 — Pipeline Yeadon** : Mapper les données BodyLoop vers les 95 clés Yeadon, valider sur des données réelles
3. **Phase 3 — Audit Hatze** : Si les calculs Hatze sont nécessaires, effectuer l'audit équation par équation
4. **Phase 4 — Intégration SMPL** : Évaluer SKEL vs BODIESReg pour le fitting du corps 3D, résoudre les questions de licence
5. **Phase 5 — Validation croisée** : Comparer les sorties Yeadon, Hatze et SKEL sur les mêmes sujets

### Choix de modèle pour les propriétés inertielles

| Option | Maturité | Précision | Complexité intégration | Licence |
|--------|----------|-----------|----------------------|---------|
| **Yeadon** | Production (v1.5.0) | Élevée (validée 1989) | Faible | À vérifier |
| **Hatze** | Prototype (bugs connus) | Potentiellement élevée | Haute (audit requis) | Apache 2.0 |
| **SKEL** | Recherche active | Non validée pour inertie | Moyenne | Non-commerciale |

**Recommandation** : utiliser **Yeadon** comme baseline pour les propriétés inertielles (robuste, bien documenté, Python 3.11+ compatible), et **SKEL** pour la visualisation et les positions de joints anatomiques si la licence le permet.

---

*Rapport généré par Agent A — Sources : GitHub (BodyLoop SDK, yeadon, hatze-biomech, BODIESReg, smplx, SKEL), PyPI (bodyloop-sdk, yeadon), yeadon.readthedocs.io, smpl-x.is.tue.mpg.de. Certaines URLs GitHub de fichiers bruts ont retourné HTTP 404 (meastemplate.txt récupéré via l'API GitHub).*
