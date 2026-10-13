#!/usr/bin/env python3
"""Recipe Lab 레시피를 사진에 적용하는 변환기.

Recipe Lab(https://github.com/voxivoid/recipe-lab-sony-pmca, MIT)의 레시피는 LUT가 아니라 Sony 카메라
설정값(Creative Style, 채도/대비/선명도, 화이트밸런스와 미세조정, 노출 보정, DRO, Picture Effect)이다.
이 프로그램은 그 설정값 하나하나를 근사적인 이미지 연산으로 옮겨, 이미 찍힌 JPG에 다시 적용한다.

전제: 입력 사진은 '카메라 기본(Standard) 룩 + 자동 WB'로 찍힌 것으로 본다. 그래서 FACTORY (ST) 레시피는
원본을 그대로 돌려주고, 다른 레시피는 그 기준에서 얼마나 달라지는지만 적용한다.

사용 예:
  python3 recipefilter.py list
  python3 recipefilter.py apply photo.jpg -r leica-classic
  python3 recipefilter.py apply photo.jpg -r leica-classic -r kodak-portra-400 -o out/
  python3 recipefilter.py apply photo.jpg -r all -o out/ --strength 0.8
  python3 recipefilter.py sheet photo.jpg -o sheet.jpg [--group Leica]
  python3 recipefilter.py lut -r all -o luts/
"""
import argparse
import json
import math
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_RECIPES = os.path.join(HERE, "..", "app", "recipes.json")

# ---------------------------------------------------------------- Creative Style 기준 룩
# sat: 채도 배율, con: 대비 곡선 세기(-1..1), gamma: 중간톤(>1 어둡게), tint: 감마 공간 RGB 배율,
# hues: (중심 hue°, 폭°, 추가 채도) 특정 색만 더/덜, sharp: 선명도 슬라이더 보정, mono/sepia
STYLES = {
    "standard":  dict(),
    "vivid":     dict(sat=1.32, con=0.12),
    "neutral":   dict(sat=0.80, con=-0.10, sharp=-0.5),
    "portrait":  dict(sat=0.92, con=-0.06, gamma=0.98, tint=(1.01, 1.0, 0.99), hues=[(25, 30, -0.08)], sharp=-0.5),
    "landscape": dict(sat=1.18, con=0.10, hues=[(110, 50, 0.15), (215, 45, 0.15)], sharp=0.5),
    "clear":     dict(sat=1.06, con=0.06, gamma=0.97, tint=(0.99, 1.0, 1.01)),
    "deep":      dict(sat=1.15, con=0.10, gamma=1.08),
    "light":     dict(sat=0.88, con=-0.14, gamma=0.90),
    "sunset":    dict(sat=1.12, con=0.05, tint=(1.04, 1.0, 0.92), hues=[(20, 40, 0.20)]),
    "night":     dict(sat=0.85, con=0.06, gamma=1.12),
    "autumn":    dict(sat=1.10, con=0.04, tint=(1.02, 1.0, 0.97), hues=[(15, 35, 0.30), (45, 30, 0.20)]),
    "mono":      dict(mono=True),
    "sepia":     dict(mono=True, sepia=True),
}

SAT_STEP = 0.10        # 채도 슬라이더 한 칸 = ±10%
CON_STEP = 0.10        # 대비 슬라이더 한 칸 = 곡선 세기 ±0.10
SHARP_STEP = 0.35      # 선명도 슬라이더 한 칸 = 언샤프 마스크 양
AB_MIRED_STEP = 5.0    # WB A-B 미세조정 한 칸 = 5 mired
GM_STEP = 0.025        # WB G-M 미세조정 한 칸 = 녹색 채널 ±2.5%
SCENE_KELVIN = 5500    # 켈빈 고정 레시피에서 가정하는 촬영 광원(자동 WB로 중립화된 주광)
DRO_LIFT = {"off": -0.06, 1: -0.03, 2: -0.015, "auto": 0.0, 3: 0.03, 4: 0.06, 5: 0.09}

LUMA = np.array([0.299, 0.587, 0.114], dtype=np.float32)


# ---------------------------------------------------------------- 색 공간 도우미
def srgb_to_lin(c):
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def lin_to_srgb(c):
    c = np.clip(c, 0, None)
    return np.where(c <= 0.0031308, c * 12.92, 1.055 * np.power(c, 1 / 2.4) - 0.055)


def kelvin_to_lin_rgb(t):
    """흑체 광원 t(K)의 흰색을 선형 sRGB로 (Kang et al. 2002 xy 근사)."""
    t = float(np.clip(t, 1667, 25000))
    if t <= 4000:
        x = -0.2661239e9 / t**3 - 0.2343589e6 / t**2 + 0.8776956e3 / t + 0.179910
    else:
        x = -3.0258469e9 / t**3 + 2.1070379e6 / t**2 + 0.2226347e3 / t + 0.240390
    if t <= 2222:
        y = -1.1063814 * x**3 - 1.34811020 * x**2 + 2.18555832 * x - 0.20219683
    elif t <= 4000:
        y = -0.9549476 * x**3 - 1.37418593 * x**2 + 2.09137015 * x - 0.16748867
    else:
        y = 3.0817580 * x**3 - 5.87338670 * x**2 + 3.75112997 * x - 0.37001483
    X, Y, Z = x / y, 1.0, (1 - x - y) / y
    m = np.array([[3.2406, -1.5372, -0.4986], [-0.9689, 1.8758, 0.0415], [0.0557, -0.2040, 1.0570]])
    return m @ np.array([X, Y, Z])


def wb_gains(r):
    """레시피의 WB 설정이 '자동 WB로 중립화된 사진'에 더하는 채널 배율(선형, G=1)."""
    scene = kelvin_to_lin_rgb(SCENE_KELVIN)
    target_k = r["kelvin"] if r.get("wb") == "kelvin" and r.get("kelvin") else SCENE_KELVIN
    # A(+)는 따뜻하게: 광원이 더 높은 색온도라고 착각한 것과 같다 → mired를 낮춘다
    mired = 1e6 / target_k - AB_MIRED_STEP * r.get("wb_amber_blue", 0)
    set_white = kelvin_to_lin_rgb(1e6 / mired)
    g = scene / set_white
    g = g / g[1]
    g[1] *= 1 + GM_STEP * r.get("wb_green_magenta", 0)
    return g


def hue_deg(rgb):
    r, g, b = rgb[:, 0], rgb[:, 1], rgb[:, 2]
    return (np.degrees(np.arctan2(np.sqrt(3) * (g - b), 2 * r - g - b)) + 360) % 360


def contrast_curve(x, k):
    """k>0: smoothstep S곡선 쪽으로, k<0: 역 smoothstep(평평하게) 쪽으로. 양 끝(0,1)은 고정."""
    if abs(k) < 1e-6:
        return x
    x = np.clip(x, 0, 1)
    if k > 0:
        s = x * x * (3 - 2 * x)
    else:
        s = 0.5 - np.sin(np.arcsin(np.clip(1 - 2 * x, -1, 1)) / 3)
    return x + min(abs(k), 1.0) * (s - x)


def dro_curve(y, dro):
    s = DRO_LIFT.get(dro, 0.0)
    out = y + s * y * (1 - y) ** 2 * 6.75
    if isinstance(dro, int) and dro > 3:  # 높은 레벨은 하이라이트도 살짝 눌러준다
        out -= 0.02 * (dro - 3) * y * y * (1 - y) * 6.75
    return out


# ---------------------------------------------------------------- 색 변환(픽셀 단위) — LUT로 구울 수 있는 부분
def color_transform(rgb, r):
    """rgb: (N,3) float32 sRGB 0..1 → 레시피 적용 결과."""
    rgb = rgb.astype(np.float32)
    lin = srgb_to_lin(rgb)
    gains = wb_gains(r) * (2.0 ** r.get("ev", 0))
    lin = lin * gains.astype(np.float32)
    if gains.max() > 1.001:  # 밝아지는 쪽이면 하이라이트를 부드럽게 말아준다
        knee = 0.85
        lin = np.where(lin > knee, knee + (1 - knee) * np.tanh((lin - knee) / (1 - knee)), lin)
    g = np.clip(lin_to_srgb(lin), 0, 1)

    dro = r.get("dro", "auto")
    if dro != "auto":
        y = g @ LUMA
        y2 = np.clip(dro_curve(y, dro), 0, 1)
        g = np.clip(g * (y2 / np.maximum(y, 1e-4))[:, None], 0, 1)

    pe = r.get("picture_effect", "off")
    if pe != "off":  # Picture Effect가 켜지면 카메라는 Creative Style을 무시한다
        return np.clip(picture_effect(g, pe, r.get("effect_sub", 0)), 0, 1)

    st = STYLES[r.get("style", "standard")]
    if "tint" in st:
        g = g * np.array(st["tint"], dtype=np.float32)
    if st.get("gamma", 1.0) != 1.0:
        g = np.power(np.clip(g, 0, 1), st["gamma"])
    y = g @ LUMA
    if st.get("mono"):
        g = np.repeat(y[:, None], 3, axis=1)
    else:
        sat = st.get("sat", 1.0) * max(0.0, 1 + SAT_STEP * r.get("saturation", 0))
        per_px = np.full(len(g), sat, dtype=np.float32)
        if st.get("hues"):
            h = hue_deg(g)
            for center, width, amount in st["hues"]:
                d = np.abs((h - center + 180) % 360 - 180)
                per_px += sat * amount * np.clip(1 - d / width, 0, 1)
        g = y[:, None] + (g - y[:, None]) * per_px[:, None]
    g = contrast_curve(np.clip(g, 0, 1), st.get("con", 0.0) + CON_STEP * r.get("contrast", 0))
    if st.get("sepia"):
        y = g[:, 0]
        g = np.stack([y * 1.07 + 0.02, y * 0.97 + 0.01, y * 0.80], axis=1)
    return np.clip(g, 0, 1)


def picture_effect(g, pe, sub):
    y = g @ LUMA
    if pe == "rough-mono":  # 고대비 흑백 (입자는 공간 단계에서)
        m = contrast_curve(contrast_curve(y, 0.8), 0.4)
        return np.repeat(m[:, None], 3, axis=1)
    if pe == "retro-photo":  # 바랜 색 + 세피아 + 들뜬 검정
        faded = y[:, None] + (g - y[:, None]) * 0.45
        sep = np.stack([y * 1.07 + 0.02, y * 0.97 + 0.01, y * 0.80], axis=1)
        out = faded * 0.65 + sep * 0.35
        out = contrast_curve(out, -0.25)
        return out * 0.92 + 0.06
    if pe == "soft-high-key":  # 밝고 낮은 대비, 색조(0 파랑 / 1 분홍 / 2 초록)
        tint = [(0.94, 1.0, 1.08), (1.07, 0.96, 1.02), (0.96, 1.06, 0.97)][sub if 0 <= sub < 3 else 0]
        out = y[:, None] + (g - y[:, None]) * 0.7
        out = contrast_curve(np.power(np.clip(out, 0, 1), 0.75), -0.35) * 0.9 + 0.1
        return out * np.array(tint, dtype=np.float32)
    if pe == "pop-color":
        out = y[:, None] + (g - y[:, None]) * 1.7
        return contrast_curve(np.clip(out, 0, 1), 0.2)
    if pe == "toy-camera":  # 비네팅은 공간 단계에서
        tint = [(1, 1, 1), (0.92, 1.0, 1.1), (1.1, 1.0, 0.88), (0.95, 1.08, 0.95), (1.08, 0.92, 1.06)][sub if 0 <= sub < 5 else 0]
        out = y[:, None] + (g - y[:, None]) * 1.3
        return contrast_curve(np.clip(out, 0, 1), 0.3) * np.array(tint, dtype=np.float32)
    if pe == "posterization":
        src = np.repeat(y[:, None], 3, axis=1) if sub == 1 else g
        return np.round(src * 3) / 3
    if pe == "part-color":
        center = [0, 120, 225, 55][sub if 0 <= sub < 4 else 0]
        d = np.abs((hue_deg(g) - center + 180) % 360 - 180)
        keep = np.clip(1 - (d - 20) / 20, 0, 1)[:, None]
        return y[:, None] + (g - y[:, None]) * keep
    print(f"경고: Picture Effect '{pe}'는 아직 근사식이 없어 색 변환만 건너뜁니다", file=sys.stderr)
    return g


# ---------------------------------------------------------------- 3D LUT
def build_lut(r, size=33):
    ax = np.linspace(0, 1, size, dtype=np.float32)
    b, g, rr = np.meshgrid(ax, ax, ax, indexing="ij")  # .cube 순서: R이 가장 빠르게 변한다
    grid = np.stack([rr.ravel(), g.ravel(), b.ravel()], axis=1)
    return color_transform(grid, r).reshape(size, size, size, 3)  # [b][g][r]


def apply_lut(rgb, lut):
    """rgb (N,3) 0..1 에 [b][g][r] 3D LUT를 삼선형 보간으로 적용."""
    n = lut.shape[0]
    p = np.clip(rgb, 0, 1) * (n - 1)
    i0 = np.minimum(np.floor(p).astype(np.int32), n - 2)
    f = p - i0
    r0, g0, b0 = i0[:, 0], i0[:, 1], i0[:, 2]
    fr, fg, fb = f[:, 0:1], f[:, 1:2], f[:, 2:3]
    out = np.zeros_like(rgb, dtype=np.float32)
    for db in (0, 1):
        wb = fb if db else 1 - fb
        for dg in (0, 1):
            wg = fg if dg else 1 - fg
            for dr in (0, 1):
                wr = fr if dr else 1 - fr
                out += lut[b0 + db, g0 + dg, r0 + dr] * (wb * wg * wr)
    return out


def write_cube(path, r, size=33):
    lut = build_lut(r, size)
    with open(path, "w") as f:
        f.write(f'TITLE "{r["name"]}"\n# Recipe Lab recipe approximation (voxivoid/recipe-lab-sony-pmca, MIT)\n')
        f.write(f"LUT_3D_SIZE {size}\nDOMAIN_MIN 0 0 0\nDOMAIN_MAX 1 1 1\n")
        for v in lut.reshape(-1, 3):
            f.write(f"{v[0]:.6f} {v[1]:.6f} {v[2]:.6f}\n")


# ---------------------------------------------------------------- 이미지 전체 처리
def sharp_amount(r):
    if r.get("picture_effect", "off") != "off":
        return 0.0
    return SHARP_STEP * r.get("sharpness", 0) + 0.35 * STYLES[r.get("style", "standard")].get("sharp", 0)


def apply_recipe(img, r, strength=1.0, seed=0):
    """PIL RGB 이미지에 레시피를 적용해 PIL 이미지를 돌려준다."""
    lut = build_lut(r, 48)
    w, h = img.size
    src = np.asarray(img, dtype=np.uint8)
    out = np.empty_like(src)
    pe = r.get("picture_effect", "off")
    scale = max(w, h) / 3000.0
    rng = np.random.default_rng(seed)
    step = max(1, 4_000_000 // w)  # 약 400만 화소씩 나눠 처리 (5천만 화소 사진도 메모리 걱정 없이)
    for y0 in range(0, h, step):
        block = src[y0:y0 + step].reshape(-1, 3).astype(np.float32) / 255.0
        res = apply_lut(block, lut).reshape(-1, w, 3)
        if pe == "toy-camera":
            yy = (np.arange(y0, y0 + res.shape[0]) - h / 2) / (h / 2)
            xx = (np.arange(w) - w / 2) / (w / 2)
            d2 = yy[:, None] ** 2 + xx[None, :] ** 2
            res *= np.clip(1 - 0.35 * d2 ** 1.2, 0, 1)[:, :, None]
        out[y0:y0 + step] = np.clip(res * 255 + 0.5, 0, 255).astype(np.uint8)
    res_img = Image.fromarray(out, "RGB")

    if pe == "rough-mono":  # 거친 흑백: 해상도에 맞춘 입자
        gw, gh = max(1, int(w / max(1.0, 1.4 * scale))), max(1, int(h / max(1.0, 1.4 * scale)))
        noise = rng.normal(0, 18, (gh, gw)).astype(np.float32)
        noise_img = Image.fromarray(np.clip(noise + 128, 0, 255).astype(np.uint8), "L").resize((w, h), Image.BILINEAR)
        a = np.asarray(res_img, dtype=np.int16) + (np.asarray(noise_img, dtype=np.int16) - 128)[:, :, None]
        res_img = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8), "RGB")

    amt = sharp_amount(r)
    radius = 1.2 * max(1.0, scale)
    if amt > 0.01:
        res_img = res_img.filter(ImageFilter.UnsharpMask(radius=radius, percent=int(amt * 100), threshold=2))
    elif amt < -0.01:
        res_img = Image.blend(res_img, res_img.filter(ImageFilter.GaussianBlur(radius * 0.8)), min(1.0, -amt))

    if strength < 1.0:
        res_img = Image.blend(img, res_img, max(0.0, strength))
    return res_img


def load_image(path):
    img = Image.open(path)
    exif = img.getexif()
    icc = img.info.get("icc_profile")
    img = ImageOps.exif_transpose(img).convert("RGB")
    if 0x0112 in exif:
        exif[0x0112] = 1  # 회전은 이미 픽셀에 반영했다
    return img, exif, icc


def save_image(img, path, exif=None, icc=None, quality=95):
    kw = {}
    ext = os.path.splitext(path)[1].lower()
    if ext in (".jpg", ".jpeg"):
        kw.update(quality=quality, subsampling=0)
    if exif is not None and ext in (".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff"):
        kw["exif"] = exif.tobytes()
    if icc:
        kw["icc_profile"] = icc
    img.save(path, **kw)


# ---------------------------------------------------------------- 레시피 관리 / CLI
def load_recipes(path=DEFAULT_RECIPES, extra=None):
    recipes = json.load(open(path, encoding="utf-8"))["recipes"]
    for p in extra or []:
        data = json.load(open(p, encoding="utf-8"))
        recipes += data["recipes"] if isinstance(data, dict) else data
    return {r["id"]: r for r in recipes}


def pick(recipes, names, group=None):
    if not names or "all" in names:
        chosen = list(recipes.values())
    else:
        chosen = []
        for n in names:
            if n in recipes:
                chosen.append(recipes[n])
                continue
            hits = [r for r in recipes.values() if n.lower() in r["name"].lower() or n.lower() in r["id"]]
            if not hits:
                sys.exit(f"레시피를 찾을 수 없습니다: {n}  (python3 recipefilter.py list 로 확인)")
            chosen += hits
    if group:
        chosen = [r for r in chosen if r["group"].lower().startswith(group.lower())]
    return chosen


def cmd_list(a, recipes):
    cur = None
    for r in pick(recipes, None, a.group):
        if r["group"] != cur:
            cur = r["group"]
            print(f"\n[{cur}]")
        bits = [r["style"], f"채도{r['saturation']:+d} 대비{r['contrast']:+d} 선명{r['sharpness']:+d}"]
        if r["wb"] == "kelvin":
            bits.append(f"{r['kelvin']}K")
        if r["wb_amber_blue"]:
            bits.append(("A" if r["wb_amber_blue"] > 0 else "B") + str(abs(r["wb_amber_blue"])))
        if r["wb_green_magenta"]:
            bits.append(("G" if r["wb_green_magenta"] > 0 else "M") + str(abs(r["wb_green_magenta"])))
        if r["ev"]:
            bits.append(f"EV{r['ev']:+.1f}")
        if r["dro"] != "auto":
            bits.append(f"DRO {r['dro']}")
        if r["picture_effect"] != "off":
            bits.append(f"효과 {r['picture_effect']}")
        print(f"  {r['id']:<36} {' · '.join(bits)}")


def cmd_apply(a, recipes):
    chosen = pick(recipes, a.recipe, a.group)
    for path in a.inputs:
        img, exif, icc = load_image(path)
        base, ext = os.path.splitext(os.path.basename(path))
        ext = a.format or (ext if ext.lower() in (".jpg", ".jpeg", ".png", ".tif", ".tiff", ".webp") else ".jpg")
        for r in chosen:
            res = apply_recipe(img, r, a.strength)
            if a.output and (len(chosen) > 1 or len(a.inputs) > 1 or os.path.isdir(a.output) or a.output.endswith("/")):
                os.makedirs(a.output, exist_ok=True)
                dst = os.path.join(a.output, f"{base}_{r['id']}{ext}")
            else:
                dst = a.output or os.path.join(os.path.dirname(path) or ".", f"{base}_{r['id']}{ext}")
            save_image(res, dst, exif, icc, a.quality)
            print(dst)


def cmd_sheet(a, recipes):
    chosen = pick(recipes, a.recipe, a.group)
    img, _, _ = load_image(a.input)
    img.thumbnail((a.thumb, a.thumb))
    tw, th = img.size
    cols = a.cols or min(len(chosen), 6)
    rows = math.ceil(len(chosen) / cols)
    label_h = 22
    sheet = Image.new("RGB", (cols * (tw + 8) + 8, rows * (th + label_h + 8) + 8), (24, 24, 24))
    draw = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.load_default(size=14)
    except TypeError:
        font = ImageFont.load_default()
    for i, r in enumerate(chosen):
        x, y = 8 + (i % cols) * (tw + 8), 8 + (i // cols) * (th + label_h + 8)
        sheet.paste(apply_recipe(img, r), (x, y))
        draw.text((x + 2, y + th + 3), r["name"][: max(8, tw // 8)], fill=(230, 230, 230), font=font)
    sheet.save(a.output, quality=90)
    print(a.output)


def cmd_lut(a, recipes):
    os.makedirs(a.output, exist_ok=True)
    for r in pick(recipes, a.recipe, a.group):
        if r["picture_effect"] in ("rough-mono", "toy-camera"):
            note = " (입자/비네팅은 LUT에 담기지 않음)"
        else:
            note = ""
        dst = os.path.join(a.output, f"{r['id']}.cube")
        write_cube(dst, r, a.size)
        print(dst + note)


def main(argv=None):
    p = argparse.ArgumentParser(description="Recipe Lab 레시피 사진 변환기")
    p.add_argument("--recipes", action="append", help="사용자 레시피 JSON 추가 (여러 번 가능)")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("list", help="레시피 목록")
    s.add_argument("--group")

    s = sub.add_parser("apply", help="사진에 레시피 적용")
    s.add_argument("inputs", nargs="+")
    s.add_argument("-r", "--recipe", action="append", required=True, help="레시피 id 또는 이름 일부, 'all' 가능")
    s.add_argument("-o", "--output", help="출력 파일 또는 폴더")
    s.add_argument("--group", help="브랜드로 거르기 (예: Leica, Kodak)")
    s.add_argument("--strength", type=float, default=1.0, help="0..1, 원본과 섞는 비율")
    s.add_argument("--quality", type=int, default=95)
    s.add_argument("--format", help="출력 확장자 (.jpg/.png/.tif)")

    s = sub.add_parser("sheet", help="여러 레시피를 한 장에 비교")
    s.add_argument("input")
    s.add_argument("-o", "--output", default="sheet.jpg")
    s.add_argument("-r", "--recipe", action="append")
    s.add_argument("--group")
    s.add_argument("--thumb", type=int, default=320)
    s.add_argument("--cols", type=int)

    s = sub.add_parser("lut", help=".cube 3D LUT로 내보내기 (Lightroom/VN/Snapseed 등에서 사용)")
    s.add_argument("-r", "--recipe", action="append")
    s.add_argument("-o", "--output", default="luts")
    s.add_argument("--group")
    s.add_argument("--size", type=int, default=33)

    a = p.parse_args(argv)
    recipes = load_recipes(extra=a.recipes)
    {"list": cmd_list, "apply": cmd_apply, "sheet": cmd_sheet, "lut": cmd_lut}[a.cmd](a, recipes)


if __name__ == "__main__":
    main()
