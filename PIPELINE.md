# Pipeline vidéo Emotionless — mode d'emploi de la tâche planifiée (v2 : chatte qui parle)

Chaque passage produit **2 vidéos** et les dépose en **brouillons** dans Buffer (TikTok + Instagram).
JBL relit et valide les brouillons dans l'app Buffer. Rien n'est publié sans lui.

## Où travailler

- **Sur le PC Windows de JBL** (cas normal) : le dépôt est déjà cloné dans `C:\emotionless\emotionless-videos`. Ouvrir un terminal (PowerShell) dans ce dossier, faire `git pull`, travailler là. Python, ffmpeg et git sont installés (voir `SETUP-WINDOWS.md`). Les commandes `python3` ci-dessous s'écrivent `python` sous Windows.
- **Ailleurs** (session cloud) : ajouter le dépôt `EliasJBL/emotionless-videos` avec accès push (outil add_repo), le cloner, installer `pillow numpy` si besoin.

## Constantes

| Quoi | Valeur |
|---|---|
| Hébergement | **Cloudflare R2** : `https://pub-36aa0d0b37534188aa7554e74fd22d90.r2.dev/videos/<id>.mp4` via `studio/upload_r2.py` (identifiants dans les variables d'environnement `R2_*`, jamais dans le dépôt). Secours seulement si R2 échoue : GitHub Pages `https://eliasjbl.github.io/emotionless-videos/videos/<id>.mp4`. |
| Voix | ElevenLabs Nina — `KJQQsXoF7bILneDTYLOG`, modèle `eleven_v4`, **1 seule prise** (`generations_count: 1`) |
| Lip-sync | ElevenLabs `heygen-avatar6-turbo`, image de départ = nœud `d4PjCzuk3RvqjipXTdJe` (chatte au bureau, vertical) |
| Flow ElevenLabs | `M1Iu3QBiuA7YmZmw6Oel` (tout se fait sur ce flow) |
| Organisation Buffer | « My organization » — `6b08ba93d593469888bb01bf` |
| Canaux Buffer autorisés | **TikTok emotionless.app — `6b08bfc48541f09ecbb834c6`** (+ Instagram emotionless.app quand il sera branché : son id sera ajouté ici). **Ne jamais poster sur un autre canal** : l'organisation contient aussi les comptes de clipping de JBL (Straight Talk On Love, straighttalkformen). |
| Vidéos par passage | 2 |
| Budget | ~4 900 crédits par vidéo. **Avant de générer** : `account_get_usage` ; s'il reste moins de 12 000 crédits, s'arrêter et prévenir JBL. |

## Règles de contenu (non négociables)

- La mascotte est **une chatte trader** : elle enseigne une **méthode** (risque, psychologie, routine, revue, exécution), **jamais une position**.
- Interdit : signal, « achète / vends », actif + direction + prix, promesse de gain, capture de profits, chiffres présentés comme des statistiques réelles. Les chiffres sont des exemples de calcul (1 %, 3R…).
- Tutoiement, phrases courtes. **Voix entre 12 et 15 secondes** (le lip-sync coûte à la seconde), 6 à 8 lignes.
- Première ligne : scène `cat` qui accroche (question ou douleur). Dernière ligne : scène `cat` qui conclut (la règle, calme).
- 2 à 3 lignes `viz` au milieu (la chatte reste visible en fond, floutée).
- Une vidéo sur quatre maximum mentionne l'app dans le `cta`. Les autres : `cta` = « Suis le compte pour le _prochain tip._ »

## Étapes

1. **Choisir les tips** : `tips/bank.json` moins ceux listés dans `tips/used.json` ; prendre les 2 premiers non utilisés. Si la banque est épuisée, écrire 10 nouveaux tips dans le même format (mêmes règles) avant de continuer.
2. **Écrire la spec** `specs/<AAAA-MM-JJ>-<tip_id>.json` (format ci-dessous). `id` = nom du fichier sans `.json`. Mettre `"talk": "out/<id>-talk.mp4"`.
3. **Voix** : `creative_generate_speech` (voix, modèle, flow ci-dessus, `generations_count: 1`). Le prompt = les `text` des lignes dans l'ordre, chacun précédé d'une balise d'intention (`[playful, knowing]`, `[firm]`, `[calm, sure]`, `[warm, mischievous]`, `[shocked]`…). Noter le `node_id` renvoyé. Attendre ~20 s puis **un** appel `creative_get_flow_run_status` ; télécharger le mp3 en `out/<id>.mp3`. Vérifier la durée (`ffprobe`) : si elle dépasse 15,5 s, raccourcir le texte et régénérer **une** fois.
4. **Lip-sync** : `creative_generate_video` avec `model_id: "heygen-avatar6-turbo"`, `flow_id` ci-dessus, `connect_from: ["d4PjCzuk3RvqjipXTdJe", "<node_id de la voix>"]`, prompt de jeu court (ex. « Playful, expressive delivery with natural head tilts, ear twitches and paw gestures, engaged eye contact. »). Attendre ~2 min, puis `creative_get_flow_run_status` ; télécharger le mp4 en `out/<id>-talk.mp4`. Ne jamais relancer une génération pour « réessayer ».
5. **Contrôle** : `python3 studio/engine2.py check specs/<id>.json out/<id>.png --vo out/<id>.mp3`, puis **regarder l'image**. Vérifier que chaque ligne s'affiche au bon moment et que rien ne déborde. Corriger la spec si besoin (jamais la voix).
6. **Rendu** : `python3 studio/engine2.py render specs/<id>.json out/<id>.mp4 --vo out/<id>.mp3`.
7. **Hébergement** : `pip install boto3` si besoin, puis `python3 studio/upload_r2.py put out/<id>.mp4` → l'URL affichée est l'URL publique de la vidéo. Lancer aussi `python3 studio/upload_r2.py prune 28`. Ajouter l'id à `tips/used.json`, puis commit + push sur `main` de la spec et de `tips/used.json` **uniquement** (plus de mp4 dans le dépôt). **Secours** si R2 échoue (variables absentes, réseau refusé) : copier la vidéo dans `docs/videos/<id>.mp4`, commit + push, attendre ~2 min, utiliser l'URL GitHub Pages, et signaler l'échec R2 dans le compte rendu.
8. **Buffer** : pour chaque vidéo, sur **chaque canal autorisé du tableau ci-dessus, et seulement ceux-là** (vérifier avec `list_channels` que l'id existe toujours et n'est pas déconnecté) :
   - `create_post` avec `saveToDraft: true`, `schedulingType: "automatic"`, `text` = la légende, `assets: [{video: {url: <URL publique de l'étape 7>}}]`.
   - Instagram : `metadata.instagram = {type: "reel", shouldShareToFeed: true, isAiGenerated: true}`.
   - TikTok : `metadata.tiktok = {isAiGenerated: true}`.
   - Si Buffer refuse l'URL (vidéo pas encore servie), attendre 2 min et réessayer **une** fois.
   - Légende (`text`) = le champ `caption` de la spec : une question qui fait commenter, 3 à 5 hashtags, pas de lien (le lien est dans la bio). JBL peut la retoucher dans le brouillon avant de valider.
9. **Compte rendu** : message court à JBL : les 2 sujets, les légendes, les crédits restants, « brouillons prêts dans Buffer, à valider », et tout problème (canal manquant, Pages pas actif, échec).

## Format de spec

```json
{
  "id": "2026-12-01-risque-1pct",
  "talk": "out/2026-12-01-risque-1pct-talk.mp4",
  "hook": "Pourquoi ton compte *fond*, en 15 secondes.",
  "kicker": "Gestion du risque",
  "cta": "Suis le compte pour le _prochain tip._",
  "caption": "Question qui fait commenter 👇 #trading #psychologietrading #trader #daytrading",
  "lines": [
    {"text": "texte lu par la voix", "display": "texte affiché, *orange* = erreur, _bleu_ = règle", "scene": "cat"},
    {"text": "...", "scene": "viz", "kit": "counter", "data": {"label": "Risque par trade", "value": "3 %", "tone": "tilt"}}
  ]
}
```

- `text` : écrit comme on le dit (« trois pour cent »). `display` (optionnel) : version écran avec chiffres (« *3 %* »).
- Kits (`scene: "viz"`) ; une ligne `viz` sans `kit` garde le schéma précédent :
  - `counter` : `{label, value, tone, sub?}` — gros chiffre qui défile.
  - `bars` : `{items: [{label, value (nombre), display, tone}]}` — barres horizontales (max 5).
  - `candles` : `{trend: "down"|"up"|"range", mark?, tone}` — bougies avec étiquette finale.
  - `checklist` : `{items: [{text, ok}]}` — règles ✓ / ✗ (max 5, texte court).
  - `compare` : `{left: {label, value, tone, sub}, right: {...}}` — deux colonnes.
- `tone` : `tilt` (orange, erreur) ou `calm` (bleu, règle) ou `line` (gris).

## Horaires et suivi des résultats

- **Heure de publication** : lire `experiment/horaires.json`, prendre l'entrée dont la période contient la date du jour (Europe/Paris), publier à son `heure` (`mode: "customScheduled"`, `dueAt` avec l'offset de Paris). Hors liste : 17:30.
- **Tableau de suivi** (Sheet Claude Docs `bdacf136-da35-4875-9421-d92f258b0114`, nœud `4cd16cf9-4629`, onglet `Publications`, colonnes A Semaine · B Date · C Heure · D Sujet · E Vues · F Likes · G Comm. · H Partages · I Temps moyen (s) · J Durée (s) · K % regardé (formule) · L Engagement (formule) · M Légende). Avant toute écriture : `guide(items=["topic.sheets"])` puis `readSheets` et `readCells` pour avoir la révision.
  1. Pour la vidéo du jour : remplir sa ligne (si une ligne « (vidéo auto du jour) » existe à cette date, la compléter ; sinon en ajouter une sous la dernière, avec les formules K et L recopiées) : semaine, date, heure, sujet, durée, légende.
  2. Résultats : `list_posts` Buffer (canal TikTok emotionless.app, `includeMetrics: true`, publiés depuis 14 jours) ; pour chaque post publié depuis plus de 24 h, écrire dans sa ligne (même date et heure) : vues (`views`), likes (`reactions`), commentaires, partages, temps moyen (`averageTimeWatched`). Ne jamais toucher aux colonnes K et L ni aux lignes déjà remplies par JBL à la main sans raison.
