# AGENTS.md — Guide pour les agents IA

## Séparation ingénierie / science

Ce projet comporte deux types de tâches :

### Ingénierie (automatisable)
- Client API BodyLoop
- Parsing GLB/glTF
- Infrastructure CLI
- Tests unitaires
- Export de données

### Science (nécessite validation humaine)
- Choix des densités segmentaires
- Transcription et vérification des équations Hatze (voir `docs/SCIENCE_DECISIONS.md`)
- Définitions anatomiques des repères Yeadon
- Traitement du volume pulmonaire
- Poids de la fonction objectif pour le fitting SMPL

## Marqueurs dans le code

- `# TODO_SCIENTIFIC: <raison>` : décision scientifique bloquante
- `# TODO_VALIDATE: <raison>` : nécessite vérification contre publication originale
- `# ASSUMPTION: <raison>` : hypothèse documentée

## Règles invariables

1. Ne jamais utiliser les poids de skinning pour répartir la masse
2. Ne jamais imputer silencieusement une mesure manquante
3. Toute mesure doit avoir une provenance explicite (`Measurement.source`)
4. Ne jamais afficher ou logger les tokens BodyLoop
5. Les unités internes sont : mètres, kilogrammes, radians
6. Enregistrer les versions du SDK, API, presets et modèles dans manifest.json

## Répartition des agents

| Agent | Responsabilité |
|-------|---------------|
| Agent A | Documentation (`docs/`) |
| Agent B | Scaffold complet du projet (ce fichier) |
| Agent C | Sous-paquet `bodyloop_anthropometrics/api/` |

## Convention de commit

Les messages de commit suivent Conventional Commits :
- `feat:` — nouvelle fonctionnalité
- `fix:` — correction de bug
- `docs:` — documentation uniquement
- `test:` — ajout ou correction de tests
- `refactor:` — refactorisation sans changement de comportement
- `chore:` — maintenance (CI, dépendances)

## Sécurité

- Ne jamais committer de tokens, clés API, ou données patient
- Les fichiers `.env` sont dans `.gitignore`
- Les fixtures de test utilisent exclusivement des données synthétiques
