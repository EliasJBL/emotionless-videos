# Pipeline vidéo Emotionless — mode d'emploi de la tâche planifiée

Chaque passage produit **2 vidéos** et les dépose en **brouillons** dans Buffer (TikTok + Instagram).
JBL relit et valide les brouillons dans l'app Buffer. Rien n'est publié sans lui.

## Constantes

| Quoi | Valeur |
|---|---|
| Dépôt | `EliasJBL/emotionless-videos` (ajouter avec accès push, puis cloner) |
| Hébergement | `https://eliasjbl.github.io/emotionless-videos/videos/<id>.mp4` (GitHub Pages, branche `main`, dossier `/docs`) |
| Voix ElevenLabs | Nina — `KJQQsXoF7bILneDTYLOG`, modèle `eleven_v4`, **1 seule prise** (`generations_count: 1`) |
| Flow ElevenLabs | `M1Iu3QBiuA7YmZmw6Oel` |
| Organisation Buffer | « My organization » — `6b08ba93d593469888bb01bf` |
| Vidéos par passage | 2 (offre gratuite Buffer : 10 posts programmés max) |

## Règles de contenu (non négociables)

- La mascotte est **une chatte trader** : elle enseigne une **méthode** (risque, psychologie, routine, revue, exécution), **jamais une position**.
- Interdit : signal, « achète / vends », actif + direction + prix, promesse de gain, capture de profits, chiffres présentés comme des statistiques réelles. Les chiffres sont des exemples de calcul (1 %, 3R…).
- Tutoiement, phrases courtes, 13 à 20 secondes de voix, **6 à 8 lignes**.
- La première ligne est une scène `cat` qui accroche (question ou douleur), la dernière une scène `cat` qui conclut (la règle, calme).
- Au moins 2 lignes `viz` au milieu. Changer de pose au moins 3 fois.
- Une vidéo sur quatre maximum mentionne l'app dans le `cta`. Les autres : `cta` = « Suis le compte pour le prochain tip. »

## Étapes

1. **Choisir les tips** : `tips/bank.json` moins ceux listés dans `tips/used.json` ; prendre les 2 premiers non utilisés. Si la banque est épuisée, écrire 10 nouveaux tips dans le même format (mêmes règles) avant de continuer.
2. **Écrire la spec** `specs/<AAAA-MM-JJ>-<tip_id>.json` (format ci-dessous). `id` = nom du fichier sans `.json`.
3. **Voix** : `creative_generate_speech` (voix, modèle, flow ci-dessus, `generations_count: 1`). Le prompt = les `text` des lignes dans l'ordre, chacun précédé d'une balise d'intention (`[playful, knowing]`, `[firm]`, `[calm, sure]`, `[warm, mischievous]`, `[shocked]`…). Récupérer l'URL avec **un seul** appel `creative_get_flow_run_status` une fois terminé (attendre ~20 s avant), télécharger en `out/<id>.mp3`. Ne jamais relancer une génération pour « réessayer ».
4. **Contrôle** : `python3 studio/engine.py check specs/<id>.json out/<id>.png --vo out/<id>.mp3` puis **regarder l'image**. Vérifier que chaque ligne s'affiche au bon moment (l'alignement imprimé doit suivre l'ordre du texte) et que rien ne déborde. Corriger la spec si besoin (jamais la voix).
5. **Rendu** : `python3 studio/engine.py render specs/<id>.json out/<id>.mp4 --vo out/<id>.mp3`.
6. **Hébergement** : copier `out/<id>.mp4` vers `docs/videos/<id>.mp4` ; ajouter les ids à `tips/used.json` ; supprimer de `docs/videos/` les vidéos de plus de 28 jours ; commit + push sur `main`. Attendre ~2 min (déploiement Pages).
7. **Buffer** : `list_channels` sur l'organisation. Pour chaque vidéo, sur **chaque** canal TikTok et Instagram :
   - `create_post` avec `saveToDraft: true`, `schedulingType: "automatic"`, `text` = la légende, `assets: [{video: {url: <URL Pages>}}]`.
   - Instagram : `metadata.instagram = {type: "reel", shouldShareToFeed: true, isAiGenerated: true}`.
   - TikTok : `metadata.tiktok = {isAiGenerated: true}`.
   - Si Buffer refuse l'URL (vidéo pas encore servie), attendre 2 min et réessayer **une** fois.
8. **Compte rendu** : envoyer à JBL un message court : les 2 sujets, les légendes, le lien des vidéos, et « brouillons prêts dans Buffer, à valider ». Signaler tout problème (crédits ElevenLabs bas, canal manquant, échec).

## Format de spec

```json
{
  "id": "2026-12-01-risque-1pct",
  "hook": "Pourquoi ton compte *fond*, en 15 secondes.",
  "kicker": "Gestion du risque",
  "cta": "Suis le compte pour le _prochain tip._",
  "caption": "Question qui fait commenter 👇 #trading #psychologietrading #trader #daytrading",
  "lines": [
    {"text": "texte lu par la voix", "display": "texte affiché, *orange* = erreur, _bleu_ = règle", "scene": "cat", "pose": "point"},
    {"text": "...", "scene": "viz", "pose": "think", "kit": "counter", "data": {"label": "Risque par trade", "value": "3 %", "tone": "tilt"}}
  ]
}
```

- `text` : écrit comme on le dit (« trois pour cent »). `display` (optionnel) : version écran avec chiffres (« *3 %* »).
- Poses : `point`, `shock`, `confident`, `think`, `facepalm`.
- Kits (`scene: "viz"`) ; une ligne `viz` sans `kit` garde le schéma précédent :
  - `counter` : `{label, value, tone, sub?}` — gros chiffre qui défile.
  - `bars` : `{items: [{label, value (nombre), display, tone}]}` — barres horizontales (max 5).
  - `candles` : `{trend: "down"|"up"|"range", mark?, tone}` — bougies avec étiquette finale.
  - `checklist` : `{items: [{text, ok}]}` — règles ✓ / ✗ (max 5, texte court).
  - `compare` : `{left: {label, value, tone, sub}, right: {...}}` — deux colonnes.
- `tone` : `tilt` (orange, erreur) ou `calm` (bleu, règle) ou `line` (gris).
