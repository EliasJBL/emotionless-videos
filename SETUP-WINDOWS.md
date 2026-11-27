# Installation sur le PC Windows (une seule fois)

Ouvrir **PowerShell** et coller les blocs un par un.

## 1. Outils

```powershell
winget install --id Git.Git -e
winget install --id Python.Python.3.12 -e
winget install --id Gyan.FFmpeg -e
```

Fermer puis rouvrir PowerShell (pour que `git`, `python` et `ffmpeg` soient reconnus), puis :

```powershell
python -m pip install pillow numpy
git --version; python --version; ffmpeg -version | Select-Object -First 1
```

## 2. Le dépôt

```powershell
mkdir C:\emotionless
cd C:\emotionless
git clone https://github.com/EliasJBL/emotionless-videos.git
cd emotionless-videos
git config user.name "EliasJBL"
git config user.email "<ton email GitHub>"
```

Faire un premier `git push` de test pour enregistrer la connexion GitHub (une fenêtre de connexion s'ouvre la première fois) :

```powershell
git commit --allow-empty -m "Test connexion depuis le PC"
git push
```

## 3. Test du moteur

```powershell
python studio\engine2.py check specs\test-heygen.json out\chk.png --vo out\test-risque.mp3
```

(`out\` n'est pas dans le dépôt : ce test ne marche qu'après une première vidéo ; sinon passer à l'étape 4.)

## 4. Claude Desktop

- Connecteurs actifs : **ElevenLabs** et **Buffer**.
- Dossier `C:\emotionless` ajouté à Claude Desktop (bouton « Add folder »).
- Tâche planifiée « Emotionless — vidéos de la chatte trader » : activer **Require this computer** puis **l'activer**. Elle suit `PIPELINE.md`.
- Le PC doit être allumé et Claude Desktop ouvert le **dimanche et le mercredi vers 18h30**.
