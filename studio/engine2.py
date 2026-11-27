"""Emotionless — moteur v2 : plans animés de la chatte (clips vidéo IA) + décor vivant + accroche animée.

Différences avec v1 :
- scènes « cat » : un clip vidéo de la chatte (bibliothèque studio/clips/), poussée de caméra, coupe franche entre clips ;
- scènes « viz » : le même décor animé, flouté et assombri, sous les schémas (plus de fond plat) ;
- accroche : mots qui claquent un par un (zoom 1,6 → 1), secousse caméra et flash blanc à l'entrée ;
- flash de 2 images à chaque changement de scène.
Spec identique à v1, plus `clip` par ligne (nom d'un clip de studio/clips/clips.json).
"""
import json, math, os, subprocess, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import engine as E

W, H, FPS, SS, P = E.W, E.H, E.FPS, E.SS, E.P
ROOT = E.ROOT
CLIPS = json.load(open(os.path.join(ROOT, "clips", "clips.json")))

_frames, _blur = {}, {}
def clip_frames(name):
    """Images du clip recadrées en 9:16 (aller-retour pour boucler sans saut)."""
    if name not in _frames:
        c = CLIPS[name]
        vf = f"fps={FPS},crop={c['crop']},scale={W}:{H}:flags=lanczos"
        # Lecture image par image : ne garde jamais tout le flux brut en mémoire (évite l'OOM sur les clips de 15 s).
        pr = subprocess.Popen(["ffmpeg", "-v", "error", "-ss", str(c.get("start", 0)), "-i", os.path.join(ROOT, "clips", c["file"]),
                               "-vf", vf, "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)
        fr, sz = [], W * H * 3
        while True:
            buf = pr.stdout.read(sz)
            if len(buf) < sz: break
            fr.append(Image.frombytes("RGB", (W, H), buf))
        pr.wait()
        _frames[name] = fr if c.get("sync") else fr + fr[-2:0:-1]
    return _frames[name]

def clip_at(name, t):
    """Clip « sync » (lèvres synchronisées sur la voix) : lu au temps réel de la vidéo ; sinon boucle aller-retour."""
    fr = clip_frames(name)
    if CLIPS[name].get("sync"):
        return fr[min(int(t * FPS), len(fr) - 1)]
    return fr[int(t * FPS) % len(fr)]

def blurred_at(name, t):
    fr = clip_frames(name)
    i = min(int(t * FPS), len(fr) - 1) if CLIPS[name].get("sync") else int(t * FPS) % len(fr)
    key = (name, i)
    if key not in _blur:
        im = fr[i].resize((W // 4, H // 4)).filter(ImageFilter.GaussianBlur(6)).resize((W, H))
        im = Image.blend(im, Image.new("RGB", (W, H), E.BG), 0.55)
        if CLIPS[name].get("sync"): return im  # clip lip-sync : chaque image ne sert qu'une fois, pas de cache
        _blur[key] = im
    return _blur[key]

def push(im, k, z0=1.0, z1=1.08, shake=(0, 0)):
    z = z0 + (z1 - z0) * k
    w, h = int(W * z), int(H * z)
    big = im.resize((w, h), Image.BILINEAR)
    x, y = (w - W) // 2 + shake[0], (h - H) // 2 + shake[1]
    return big.crop((x, y, x + W, y + H))

def hook_pop(d, words, t, cy):
    """Accroche : chaque mot arrive grossi puis se pose (par paliers)."""
    fnt, lh, pad = E.F_HOOK, 84, 26
    lines, sp = E.lines_of(d, words, fnt, P(880))
    bw = max(lw for _, lw in lines) / SS + 2 * pad + 8
    bh = len(lines) * lh + 2 * pad - 8
    x0, y0 = 540 - bw / 2, cy - bh / 2
    kb = E.ease(t / 0.18)
    d.rectangle([P(x0), P(y0 + bh * (1 - kb) / 2), P(x0 + bw), P(y0 + bh - bh * (1 - kb) / 2)], fill=(12, 13, 16, 235))
    d.rectangle([P(x0), P(y0), P(x0 + 8), P(y0 + bh * kb)], fill=E.C["tilt"] + (255,))
    i, y = 0, y0 + pad - 6
    for ln, lw in lines:
        x = P(540) - lw / 2
        for w, col, ww in ln:
            st = 0.12 + 0.09 * i
            if t >= st:
                k = E.ease((t - st) / 0.16)
                size = 70 * (1.7 - 0.7 * k)
                f2 = E.font("B800", int(size))
                dx = (d.textlength(w, font=f2) - ww) / 2
                d.text((x - dx, P(y) - (size - 70) * SS * 0.6), w, font=f2, fill=E.C[col])
            x += ww + sp; i += 1
        y += lh

def frame(spec, lines, end, t):
    tq = E.q(t)
    idx = next((i for i, l in enumerate(lines) if l["t0"] <= t < l["t1"]), len(lines) - 1)
    cur = lines[idx]
    clip = cur.get("clip") or spec.get("clip") or next(iter(CLIPS))
    k = (t - cur["t0"]) / max(0.1, cur["t1"] - cur["t0"])
    shake = (0, 0)
    if t < 0.3:
        a = 18 * (1 - t / 0.3)
        shake = (int(a * math.sin(t * 90)), int(a * math.cos(t * 70)))
    if cur.get("scene") == "viz":
        base = push(blurred_at(clip, t), k, 1.04, 1.0)
    else:
        z0 = 1.0 + 0.06 * (idx % 2)                  # alterne plan large / plan serré à chaque coupe
        base = push(clip_at(clip, t), k, z0, z0 + 0.07, shake)
    ov = Image.new("RGBA", (W * SS, H * SS), (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    if cur.get("scene") == "viz":
        name, data = cur["_kit"] if cur["_kit"] else ("counter", {})
        kk = (tq - cur["_kit_t0"]) / 1.2
        seed = sum(map(ord, spec.get("id", "x")))
        (E.kit_candles(d, data, kk, tq, seed) if name == "candles" else E.KIT_FN[name](d, data, kk, tq))
        d.text((P(72), P(200)), spec.get("kicker", "LA RÈGLE").upper(), font=E.F_MONO, fill=E.C["muted"])
        d.rectangle([P(72), P(252), P(1008), P(254)], fill=E.C["line"])
        E.phrase(d, E.parse(cur.get("display", cur["text"])), cur["a"], cur["b"], tq, 500)
    else:
        E.kinetic(d, E.parse(cur.get("display", cur["text"])), cur["a"], cur["b"], tq, 1500)
        if t < min(3.2, lines[0]["t1"] + 0.6) and spec.get("hook"):
            hook_pop(d, E.parse(spec["hook"]), t, 300)
        if cur is lines[-1] and spec.get("cta"):
            hook_pop(d, E.parse(spec["cta"]), t - cur["t0"], 300)
    d.text((P(72), P(140)), "@emotionless.app", font=E.F_MONO_S, fill=(200, 204, 212, 230))
    ov = ov.resize((W, H), Image.LANCZOS)
    base = base.copy()
    base.paste(ov, (0, 0), ov)
    since_cut = t - cur["t0"]
    if idx > 0 and since_cut < 2 / FPS:               # flash de coupe
        base = Image.blend(base, Image.new("RGB", (W, H), (255, 255, 255)), 0.35)
    if t < 2 / FPS:
        base = Image.blend(base, Image.new("RGB", (W, H), (255, 255, 255)), 0.5)
    return base

def use_talk(spec, spec_path):
    """Spec avec `talk` : clip lip-sync de CETTE vidéo (chemin relatif au dépôt ou absolu), lu en synchro."""
    if spec.get("talk"):
        f = spec["talk"]
        if not os.path.isabs(f):
            f = os.path.join(os.path.dirname(ROOT), f)
        CLIPS["_talk"] = {"file": f, "start": 0, "crop": "iw:ih:0:0", "sync": True}
        spec["clip"] = "_talk"
        for l in spec["lines"]:
            l.pop("clip", None)
    return spec

def render(spec_path, out, vo):
    spec = use_talk(json.load(open(spec_path, encoding="utf-8")), spec_path)
    lines, end = E.build(spec, vo)
    tmp = out[:-4] + ".part.mp4"
    p = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                          "-r", str(FPS), "-i", "-", "-i", vo, "-filter_complex",
                          "[0:v]noise=c0s=5:c0f=t+u,format=yuv420p[v];[1:a]apad[a]", "-map", "[v]", "-map", "[a]",
                          "-c:v", "libx264", "-crf", "19", "-preset", "veryfast", "-c:a", "aac", "-b:a", "160k",
                          "-movflags", "+faststart", "-t", f"{end:.3f}", tmp], stdin=subprocess.PIPE)
    for i in range(int(end * FPS)):
        p.stdin.write(frame(spec, lines, end, i / FPS).tobytes())
    p.stdin.close()
    if p.wait() != 0: sys.exit("ffmpeg a échoué")
    os.replace(tmp, out)
    print(json.dumps({"out": out, "duration": round(end, 2)}))

def check(spec_path, out, vo):
    spec = use_talk(json.load(open(spec_path, encoding="utf-8")), spec_path)
    lines, end = E.build(spec, vo)
    ts = [0.15, 0.6] + [(l["a"] + l["b"]) / 2 + 0.3 for l in lines] + [end - 0.2]
    sheet = Image.new("RGB", (216 * len(ts), 384))
    for i, t in enumerate(ts):
        sheet.paste(frame(spec, lines, end, t).resize((216, 384)), (216 * i, 0))
    sheet.save(out)

if __name__ == "__main__":
    a = sys.argv[1:]
    vo = a[a.index("--vo") + 1] if "--vo" in a else os.path.splitext(a[2])[0] + ".mp3"
    {"render": render, "check": check}[a[0]](a[1], a[2], vo)
