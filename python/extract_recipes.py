"""Recipe Lab(voxivoid/recipe-lab-sony-pmca)의 Recipes.java에서 레시피 표를 뽑아 recipes.json으로 저장한다.

사용법: python3 extract_recipes.py <Recipes.java 경로> [출력 json]
원본 저장소: https://github.com/voxivoid/recipe-lab-sony-pmca (MIT License, (c) 2026 André Domingues)
"""
import json
import re
import sys

STYLE = {"STD": "standard", "VIVID": "vivid", "NEUTRAL": "neutral", "PORTRAIT": "portrait",
         "LANDSCAPE": "landscape", "MONO": "mono", "CLEAR": "clear", "DEEP": "deep", "LIGHT": "light",
         "SUNSET": "sunset", "NIGHT": "night", "AUTUMN": "autumn", "SEPIA": "sepia"}
GROUP = {"SONY": "Sony", "FSIM": "Fuji Sim", "FFILM": "Fuji Film", "KODAK": "Kodak", "CINE": "Cine",
         "RICOH": "Ricoh GR", "LEICA": "Leica", "HASSEL": "Hasselblad", "CANIK": "Canon / Nikon",
         "PANOLY": "Pana / Olympus", "OTHER": "Other Stocks", "ILFORD": "Ilford"}
PE = ["off", "toy-camera", "pop-color", "posterization", "retro-photo", "soft-high-key", "part-color",
      "rough-mono", "soft-focus", "hdr-art", "richtone-mono", "miniature", "illust", "watercolor"]
CONST = {"AUTO": 1, "K": 14, "DRO_OFF": 0, "DRO_AUTO": 6}

ROW = re.compile(r'new Recipe\((\w+),\s*"([^"]+)",\s*([^)]*)\)[ \t]*,[ \t]*(?://[ \t]*(.*))?')


def slug(name):
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def parse(src):
    out = []
    for m in ROW.finditer(src):
        group, name, rest, comment = m.groups()
        args = [a.strip() for a in rest.split(",")]
        style = STYLE[args[0]]
        nums = [int(CONST.get(a, a)) for a in args[1:]]
        sat, con, sharp, wb_mode, kelvin, ab, gm = nums[:7]
        pe, ev, dro, sub = (nums[7:] + [0, 0, 6, 0][len(nums) - 7:])[:4]
        out.append({
            "id": slug(name), "name": name, "group": GROUP[group], "style": style,
            "saturation": sat, "contrast": con, "sharpness": sharp,
            "wb": "kelvin" if wb_mode == 14 else "auto", "kelvin": kelvin if wb_mode == 14 else None,
            "wb_amber_blue": ab, "wb_green_magenta": gm,
            "picture_effect": PE[pe], "effect_sub": sub,
            "ev": round(ev / 3, 2), "dro": "auto" if dro == 6 else ("off" if dro == 0 else dro),
            "note": (comment or "").strip() or None,
        })
    return out


if __name__ == "__main__":
    src = open(sys.argv[1], encoding="utf-8").read()
    recipes = parse(src)
    dst = sys.argv[2] if len(sys.argv) > 2 else "recipes.json"
    with open(dst, "w", encoding="utf-8") as f:
        json.dump({"source": "voxivoid/recipe-lab-sony-pmca v1.6.2 (MIT)", "recipes": recipes}, f, ensure_ascii=False, indent=1)
    print(f"{len(recipes)} recipes -> {dst}")
