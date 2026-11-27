"""Emotionless — moteur de montage des vidéos « la chatte trader ».

Une vidéo = un fichier spec JSON (voir specs/EXEMPLE.json) + une voix off (mp3).
Le moteur aligne chaque ligne du script sur la voix (détection des silences),
puis monte : plans du chat (poses), schémas animés (kits), sous-titres mot à mot,
accroche en haut au début, appel à l'action en haut à la fin.

Usage :
  python3 studio/engine.py render specs/<id>.json out/<id>.mp4 [--vo out/<id>.mp3]
  python3 studio/engine.py check  specs/<id>.json out/<id>.png  [--vo ...]   (planche de contrôle)
"""
import json, math, os, re, subprocess, sys, random
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.abspath(__file__))
W, H, FPS, SS = 1080, 1920, 30, 2
BG = (22, 24, 29)                      # fond de la vidéo (le chat est détouré)
C = dict(bg=BG, ink=(22, 24, 29), surface=(35, 38, 46), line=(58, 63, 74), paper=(241, 236, 226),
         muted=(154, 160, 170), tilt=(255, 107, 44), calm=(91, 141, 239))
POSES = ["point", "shock", "confident", "think", "facepalm"]
KITS = ["counter", "bars", "candles", "checklist", "compare"]

def font(n, s): return ImageFont.truetype(os.path.join(ROOT, "fonts", n + ".woff"), s * SS)
F_HOOK, F_CAP, F_BIG, F_MID = font("B800", 70), font("B700", 64), font("B800", 96), font("B800", 80)
F_MONO, F_MONO_S, F_NUM = font("M500", 34), font("M500", 28), font("B800", 210)
def P(v): return int(round(v * SS))
def clamp(x, a=0.0, b=1.0): return max(a, min(b, x))
def ease(x): x = clamp(x); return 1 - (1 - x) ** 3
def mix(a, b, k): return tuple(int(x + (y - x) * clamp(k)) for x, y in zip(a, b))
STEP = 1 / 15
def q(t): return math.floor(t / STEP) * STEP      # animation par paliers (style maison)

# ---------- texte ----------
def parse(text):
    """'Ton compte *fond*' -> [(mot, couleur)] ; *x* = orange (erreur), _x_ = bleu (règle)."""
    out = []
    for m in re.finditer(r"\*([^*]+)\*|_([^_]+)_|([^*_]+)", text):
        seg, col = (m.group(1), "tilt") if m.group(1) else ((m.group(2), "calm") if m.group(2) else (m.group(3), "paper"))
        seg = re.sub(r"(\d) %", "\\1\u00a0%", seg)          # « 3 % » ne se coupe pas
        for w in seg.split(" "):
            if not w: continue
            if out and col == "paper" and re.fullmatch(r"[.,!?:;…]+", w):
                out.append((w, col)); continue
            out.append((w, col))
    # ponctuation collée au mot coloré précédent : « fond, » reste en une pièce
    merged = []
    for w, col in out:
        if merged and re.fullmatch(r"[.,!?:;…]+", w) and not w.startswith(("?", "!", ":", ";")):
            merged[-1] = (merged[-1][0] + w, merged[-1][1])
        elif merged and w in ("?", "!", ":", ";"):
            merged[-1] = (merged[-1][0] + "\u00a0" + w, merged[-1][1])
        else:
            merged.append((w, col))
    return merged

def lines_of(d, words, fnt, maxw):
    lines, cur, curw = [], [], 0
    sp = d.textlength(" ", font=fnt)
    for w, col in words:
        ww = d.textlength(w, font=fnt)
        if cur and curw + sp + ww > maxw:
            lines.append((cur, curw)); cur, curw = [], 0
        curw += (sp if cur else 0) + ww
        cur.append((w, col, ww))
    if cur: lines.append((cur, curw))
    return lines, sp

def block(d, words, fnt, cy, maxw, lh, bar="tilt", pad=26):
    lines, sp = lines_of(d, words, fnt, P(maxw))
    bw = max(lw for _, lw in lines) / SS + 2 * pad + 8
    bh = len(lines) * lh + 2 * pad - 8
    x0, y0 = 540 - bw / 2, cy - bh / 2
    d.rectangle([P(x0), P(y0), P(x0 + bw), P(y0 + bh)], fill=(12, 13, 16, 235))
    d.rectangle([P(x0), P(y0), P(x0 + 8), P(y0 + bh)], fill=C[bar] + (255,))
    y = y0 + pad - 6
    for ln, lw in lines:
        x = P(540) - lw / 2
        for w, col, ww in ln:
            d.text((x, P(y)), w, font=fnt, fill=C[col])
            x += ww + sp
        y += lh

def kinetic(d, words, a0, a1, t, cy):
    """Sous-titre : bloc net, mots qui tombent au rythme de la voix."""
    fnt, lh, pad = F_CAP, 76, 26
    lines, sp = lines_of(d, words, fnt, P(860))
    bw = max(lw for _, lw in lines) / SS + 2 * pad + 8
    bh = len(lines) * lh + 2 * pad - 8
    x0, y0 = 540 - bw / 2, cy - bh / 2
    d.rectangle([P(x0), P(y0), P(x0 + bw), P(y0 + bh)], fill=(12, 13, 16, 230))
    d.rectangle([P(x0), P(y0), P(x0 + 8), P(y0 + bh)], fill=C["tilt"] + (255,))
    total = sum(len(w) for w, _ in words) or 1
    span, acc, y = (a1 - a0) * 0.92, 0, y0 + pad - 6
    for ln, lw in lines:
        x = P(540) - lw / 2
        for w, col, ww in ln:
            st = a0 + span * acc / total - 0.05
            acc += len(w)
            if t >= st:
                d.text((x, P(y + (8 if t - st < 0.07 else 0))), w, font=fnt, fill=C[col])
            x += ww + sp
        y += lh

def phrase(d, words, a0, a1, t, cy):
    """Grande phrase alignée à gauche, mot à mot (segments schéma)."""
    total = sum(len(w) for w, _ in words) or 1
    fnt = F_BIG if total <= 26 else F_MID
    lh = 108 if fnt is F_BIG else 92
    lines, sp = lines_of(d, words, fnt, P(900))
    y, acc, span = cy - len(lines) * lh / 2, 0, (a1 - a0) * 0.9
    for ln, lw in lines:
        x = P(72)
        for w, col, ww in ln:
            st = a0 + span * acc / total - 0.04
            acc += len(w)
            if t >= st:
                d.text((x, P(y + (10 if t - st < 0.1 else 0))), w, font=fnt, fill=C[col])
            x += ww + sp
        y += lh

# ---------- le chat ----------
_cat = {}
def cat_img(pose):
    """Poses détourées (PNG transparent, sans fond ni ombre), recadrées au plus juste."""
    if pose not in _cat:
        _cat[pose] = Image.open(os.path.join(ROOT, "cat", pose + ".png")).convert("RGBA")
    return _cat[pose]

def paste_cat(base, pose, t, t_pose, cx, bottom, height):
    im = cat_img(pose)
    breathe = 1 + 0.012 * math.sin(2 * math.pi * t / 2.4)
    punch = 1 + 0.06 * (1 - ease((t - t_pose) / 0.22)) if t >= t_pose else 1
    s = height / im.height * breathe * punch
    w, h = int(im.width * s), int(im.height * s)
    bob = 6 * math.sin(2 * math.pi * t / 2.4 + 1)
    x, y = int(cx - w / 2), int(bottom - h + bob)
    base.paste(im.resize((w, h), Image.BILINEAR), (x, y), im.resize((w, h), Image.BILINEAR))

# ---------- kits de schéma ----------
def kit_counter(d, data, k, t):
    tone = C[data.get("tone", "tilt")]
    d.text((P(72), P(760)), data.get("label", "").upper(), font=F_MONO, fill=C["muted"])
    val = str(data.get("value", ""))
    m = re.search(r"\d+(?:[.,]\d+)?", val)
    if m and k < 1:
        num = float(m.group(0).replace(",", "."))
        dec = len(m.group(0).split(",")[-1]) if "," in m.group(0) else (len(m.group(0).split(".")[-1]) if "." in m.group(0) else 0)
        cur = num * ease(k / 0.8)
        s = f"{cur:.{dec}f}".replace(".", ",") if dec else str(int(round(cur)))
        val = val[:m.start()] + s + val[m.end():]
    d.text((P(64), P(810)), val, font=F_NUM, fill=tone)
    sub = data.get("sub")
    if sub and k > 0.6:
        d.text((P(72), P(1080)), sub, font=F_MONO, fill=C["paper"])
    d.rectangle([P(72), P(1150), P(72 + 936 * ease(k / 0.9)), P(1158)], fill=tone)

def kit_bars(d, data, k, t):
    items = data.get("items", [])[:5]
    vmax = max([abs(float(i.get("value", 1))) for i in items] + [1e-9])
    y = 780
    for n, it in enumerate(items):
        kk = ease((k - 0.12 * n) / 0.5)
        col = C[it.get("tone", "line")]
        d.text((P(72), P(y)), it.get("label", "").upper(), font=F_MONO_S, fill=C["muted"])
        L = 700 * abs(float(it.get("value", 0))) / vmax * kk
        d.rectangle([P(72), P(y + 44), P(72 + max(L, 4)), P(y + 104)], fill=col)
        if kk >= 1:
            d.text((P(72 + L + 20), P(y + 50)), str(it.get("display", it.get("value"))), font=F_MONO, fill=C["paper"])
        y += 150

def kit_candles(d, data, k, t, seed=7):
    rnd = random.Random(seed)
    trend = {"down": -1, "up": 1}.get(data.get("trend", "down"), 0)
    n, x0, y, cw = 22, 90, 0.0, 40
    shown = int(n * clamp(k / 0.8)) + 1
    vals = []
    for i in range(n):
        o = y; c = y + rnd.uniform(-9, 9) + trend * 4.2; vals.append((o, c)); y = c
    lo, hi = min(min(v) for v in vals) - 12, max(max(v) for v in vals) + 12
    def py(v): return 1320 - (v - lo) / (hi - lo) * 520
    for i, (o, c) in enumerate(vals[:shown]):
        col = C["calm"] if c >= o else C["tilt"]
        x = x0 + i * cw
        d.line([(P(x + 12), P(py(max(o, c) + 4))), (P(x + 12), P(py(min(o, c) - 4)))], fill=col, width=P(2))
        d.rectangle([P(x + 4), P(py(max(o, c))), P(x + 20), P(max(py(min(o, c)), py(max(o, c)) + 3))], fill=col)
    mark = data.get("mark")
    if mark and k >= 0.85:
        i = n - 1; o, c = vals[i]; x = x0 + i * cw
        tone = C[data.get("tone", "tilt")]
        lw = d.textlength(mark, font=F_MONO) / SS
        bx = min(x - lw / 2, 1000 - lw - 20)
        by = py(c) + (40 if trend < 0 else -100)
        d.rectangle([P(bx - 10), P(by - 6), P(bx + lw + 10), P(by + 48)], fill=tone)
        d.text((P(bx), P(by)), mark, font=F_MONO, fill=BG)

def kit_checklist(d, data, k, t):
    y = 780
    for n, it in enumerate(data.get("items", [])[:5]):
        if k < 0.15 * n: break
        ok = it.get("ok", True)
        col = C["calm"] if ok else C["tilt"]
        d.rectangle([P(72), P(y), P(124), P(y + 52)], fill=col)
        if ok:
            d.line([(P(84), P(y + 27)), (P(96), P(y + 40)), (P(114), P(y + 14))], fill=BG, width=P(6))
        else:
            d.line([(P(86), P(y + 12)), (P(110), P(y + 40))], fill=BG, width=P(6))
            d.line([(P(110), P(y + 12)), (P(86), P(y + 40))], fill=BG, width=P(6))
        d.text((P(150), P(y + 2)), it.get("text", ""), font=font("B700", 46), fill=C["paper"])
        y += 100

def kit_compare(d, data, k, t):
    for n, key in enumerate(["left", "right"]):
        it = data.get(key, {})
        kk = ease((k - 0.25 * n) / 0.45)
        if kk <= 0: continue
        x = 72 + 480 * n
        col = C[it.get("tone", "line")]
        d.rectangle([P(x), P(780), P(x + 440), P(784)], fill=col)
        d.text((P(x), P(810)), it.get("label", "").upper(), font=F_MONO_S, fill=C["muted"])
        d.text((P(x), P(860 + 30 * (1 - kk))), str(it.get("value", "")), font=font("B800", 130), fill=col)
        if it.get("sub"):
            d.text((P(x), P(1030)), it["sub"], font=F_MONO_S, fill=C["paper"])

KIT_FN = dict(counter=kit_counter, bars=kit_bars, candles=kit_candles, checklist=kit_checklist, compare=kit_compare)

# ---------- alignement voix / lignes ----------
def duration(path):
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
                                capture_output=True, text=True).stdout.strip())

def align(vo, texts):
    """Découpe la voix en autant de morceaux que de lignes, aux silences les plus longs."""
    dur = duration(vo)
    out = subprocess.run(["ffmpeg", "-hide_banner", "-i", vo, "-af", "silencedetect=noise=-35dB:d=0.12", "-f", "null", "-"],
                         capture_output=True, text=True).stderr
    st = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", out)]
    en = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", out)]
    gaps = [(e - s, s, e) for s, e in zip(st, en) if 0.05 < s and e < dur - 0.05]
    first = en[0] if st and st[0] < 0.05 and en else 0.0
    n = len(texts)
    cuts = sorted(sorted(gaps, reverse=True)[:n - 1], key=lambda g: g[1])
    if len(cuts) < n - 1:                        # pas assez de silences : découpe au prorata des caractères
        tot = sum(len(x) for x in texts); acc = 0; cuts = []
        for x in texts[:-1]:
            acc += len(x); p = first + (dur - first) * acc / tot; cuts.append((0, p, p))
    bounds, a = [], first
    for _, s, e in cuts:
        bounds.append((a, s)); a = e
    last_end = st[-1] if st and st[-1] > a and en and en[-1] >= dur - 0.06 else dur
    bounds.append((a, last_end))
    return bounds, dur

# ---------- rendu ----------
def build(spec, vo):
    lines = spec["lines"]
    bounds, dur = align(vo, [l.get("text", "") for l in lines])
    for l, (a, b) in zip(lines, bounds): l["a"], l["b"] = a, b
    # segments : changement de scène au début du mot qui la déclenche (léger avance)
    for i, l in enumerate(lines):
        l["t0"] = 0.0 if i == 0 else (lines[i - 1]["b"] + l["a"]) / 2
    end = min(dur, lines[-1]["b"] + 0.4)
    for i, l in enumerate(lines):
        l["t1"] = lines[i + 1]["t0"] if i + 1 < len(lines) else end
    kit, kit_t0, last_pose, pose_t = None, 0.0, None, 0.0
    for l in lines:                      # état persistant : kit en cours, changement de pose
        if l.get("scene") == "viz":
            if l.get("kit"):
                kit, kit_t0 = (l["kit"], l.get("data", {})), l["t0"]
            l["_kit"], l["_kit_t0"] = kit, kit_t0
        else:
            kit = None
        pose = l.get("pose", "point")
        if pose != last_pose: pose_t = l["t0"]; last_pose = pose
        l["_pose"], l["_pose_t"] = pose, pose_t
    return lines, end

def grid(d):
    for gx in range(60, W, 60):
        for gy in range(240, 1560, 60):
            d.rectangle([P(gx - 1.5), P(gy - 1.5), P(gx + 1.5), P(gy + 1.5)], fill=(30, 32, 38, 255))

def frame(spec, lines, end, t):
    tq = q(t)
    cur = next((l for l in lines if l["t0"] <= t < l["t1"]), lines[-1])
    base = Image.new("RGB", (W, H), BG)
    ov = Image.new("RGBA", (W * SS, H * SS), (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    seed = sum(map(ord, spec.get("id", "x")))
    if cur.get("scene") == "viz":
        grid(d)
        name, data = cur["_kit"] if cur["_kit"] else ("counter", {})
        KIT_FN[name](d, data, (tq - cur["_kit_t0"]) / 1.2, tq) if name != "candles" else kit_candles(d, data, (tq - cur["_kit_t0"]) / 1.2, tq, seed)
        d.text((P(72), P(200)), spec.get("kicker", "LA RÈGLE").upper(), font=F_MONO, fill=C["muted"])
        d.rectangle([P(72), P(252), P(1008), P(254)], fill=C["line"])
        phrase(d, parse(cur.get("display", cur["text"])), cur["a"], cur["b"], tq, 500)
        paste_cat(base, cur["_pose"], t, cur["_pose_t"], 870, 1740, 380)      # mini-chat en bas à droite
    else:
        paste_cat(base, cur["_pose"], t, cur["_pose_t"], 540, 1400, 960)
        kinetic(d, parse(cur.get("display", cur["text"])), cur["a"], cur["b"], tq, 1510)
        if t < min(3.2, lines[0]["t1"] + 0.6) and spec.get("hook"):
            block(d, parse(spec["hook"]), F_HOOK, 290, 880, 82)
        if cur is lines[-1] and spec.get("cta"):
            block(d, parse(spec["cta"]), F_HOOK, 290, 880, 82, bar="calm")
    d.text((P(72), P(140)), "@emotionless.app", font=F_MONO_S, fill=(120, 126, 136, 255))
    ov = ov.resize((W, H), Image.LANCZOS)
    base.paste(ov, (0, 0), ov)
    return base

def render(spec_path, out, vo):
    spec = json.load(open(spec_path, encoding="utf-8"))
    lines, end = build(spec, vo)
    tmp = out[:-4] + ".part.mp4"
    p = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                          "-r", str(FPS), "-i", "-", "-i", vo, "-filter_complex",
                          "[0:v]noise=c0s=7:c0f=t+u,format=yuv420p[v];[1:a]apad[a]", "-map", "[v]", "-map", "[a]",
                          "-c:v", "libx264", "-crf", "20", "-preset", "veryfast", "-c:a", "aac", "-b:a", "160k",
                          "-movflags", "+faststart", "-t", f"{end:.3f}", tmp], stdin=subprocess.PIPE)
    for i in range(int(end * FPS)):
        p.stdin.write(frame(spec, lines, end, i / FPS).tobytes())
    p.stdin.close()
    if p.wait() != 0: sys.exit("ffmpeg a échoué")
    os.replace(tmp, out)
    print(json.dumps({"out": out, "duration": round(end, 2),
                      "lines": [(round(l["a"], 2), round(l["b"], 2), l["text"][:40]) for l in lines]}, ensure_ascii=False))

def check(spec_path, out, vo):
    spec = json.load(open(spec_path, encoding="utf-8"))
    lines, end = build(spec, vo)
    ts = [0.6] + [(l["a"] + l["b"]) / 2 + 0.3 for l in lines] + [end - 0.2]
    sheet = Image.new("RGB", (216 * len(ts), 384))
    for i, t in enumerate(ts):
        sheet.paste(frame(spec, lines, end, t).resize((216, 384)), (216 * i, 0))
    sheet.save(out)
    print(json.dumps([(round(l["a"], 2), round(l["b"], 2), l["text"][:50]) for l in lines], ensure_ascii=False))

if __name__ == "__main__":
    a = sys.argv[1:]
    vo = a[a.index("--vo") + 1] if "--vo" in a else os.path.splitext(a[2])[0] + ".mp3"
    {"render": render, "check": check}[a[0]](a[1], a[2], vo)
