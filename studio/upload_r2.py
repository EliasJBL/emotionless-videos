"""Envoie une vidéo dans le bucket Cloudflare R2 et affiche son URL publique.

Variables d'environnement (secrets de l'environnement Claude Code, jamais dans le dépôt) :
  R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_ENDPOINT (https://<account_id>.r2.cloudflarestorage.com)
  R2_BUCKET (défaut : emotionless-videos), R2_PUBLIC_URL (défaut : l'URL r2.dev du bucket)

Usage :
  python3 studio/upload_r2.py check                  # vérifie identifiants + accès réseau, n'envoie rien
  python3 studio/upload_r2.py put out/<id>.mp4       # envoie dans videos/<id>.mp4, affiche l'URL publique
  python3 studio/upload_r2.py prune [jours=28]       # supprime les vidéos plus vieilles que N jours
Dépendance : pip install boto3
"""
import os, sys, datetime, urllib.request

PUBLIC = os.environ.get("R2_PUBLIC_URL", "https://pub-36aa0d0b37534188aa7554e74fd22d90.r2.dev").rstrip("/")
BUCKET = os.environ.get("R2_BUCKET", "emotionless-videos")

def client():
    missing = [k for k in ("R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_ENDPOINT") if not os.environ.get(k)]
    if missing:
        sys.exit("Variables manquantes : " + ", ".join(missing))
    import boto3
    from botocore.config import Config
    return boto3.client("s3", endpoint_url=os.environ["R2_ENDPOINT"], region_name="auto",
                        aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
                        aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
                        config=Config(signature_version="s3v4", retries={"max_attempts": 3}))

def public_ok(url):
    try:
        # Cloudflare refuse le User-Agent par défaut « Python-urllib » (403) : on en fixe un.
        req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "emotionless-pipeline/1.0"})
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status == 200
    except Exception as e:
        print(f"(vérification HTTP impossible depuis cette machine : {e})")
        return None

def main():
    a = sys.argv[1:]
    if not a: sys.exit(__doc__)
    s3 = client()
    if a[0] == "check":
        s3.list_objects_v2(Bucket=BUCKET, MaxKeys=1)
        print(f"OK : accès au bucket {BUCKET}. URL publique : {PUBLIC}")
    elif a[0] == "put":
        path = a[1]
        key = "videos/" + os.path.basename(path)
        s3.upload_file(path, BUCKET, key, ExtraArgs={"ContentType": "video/mp4", "CacheControl": "public, max-age=86400"})
        url = f"{PUBLIC}/{key}"
        ok = public_ok(url)
        print(url)
        if ok is False:
            sys.exit("Envoyé, mais l'URL publique ne répond pas 200.")
    elif a[0] == "prune":
        days = int(a[1]) if len(a) > 1 else 28
        lim = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=days)
        old = [o["Key"] for o in s3.list_objects_v2(Bucket=BUCKET, Prefix="videos/").get("Contents", []) if o["LastModified"] < lim]
        for k in old:
            s3.delete_object(Bucket=BUCKET, Key=k)
        print(f"{len(old)} vidéo(s) supprimée(s)")

if __name__ == "__main__":
    main()
