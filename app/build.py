"""app/ 소스를 합쳐서 배포용 파일을 만든다.

  web/index.html ......... GitHub Pages로 배포되는 웹앱 (PWA: 홈 화면에 설치, 오프라인 동작)
  android/.../assets/www . 안드로이드 앱 안에 들어가는 같은 화면
  build/artifact.html .... claude.ai 아티팩트용 (문서 뼈대 없음, JSZip은 CDN)

실행: python3 app/build.py   (Pillow 필요: 예시 사진과 아이콘)
"""
import base64, json, os, shutil
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
VERSION = "1.0.0"


def read(name):
    return open(os.path.join(HERE, name), encoding="utf-8").read()


def page(jszip_src):
    recipes = json.load(open(os.path.join(HERE, "recipes.json"), encoding="utf-8"))["recipes"]
    sample = "data:image/jpeg;base64," + base64.b64encode(open(os.path.join(HERE, "sample.jpg"), "rb").read()).decode()
    return (read("app.template.html")
            .replace("/*ENGINE*/", read("engine.js"))
            .replace("/*RECIPES*/", json.dumps(recipes, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/"))
            .replace("/*SAMPLE*/", sample)
            .replace("/*JSZIP*/", jszip_src))


def doc(body, extra_head=""):
    return ('<!doctype html><html lang="ko"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">'
            '<meta name="theme-color" content="#12110f">' + extra_head +
            '<style>*,*::before,*::after{box-sizing:border-box}body{margin:0}img{max-width:100%}[hidden]{display:none!important}</style>'
            '</head><body>' + body + '</body></html>')


def icon(size, maskable=False):
    im = Image.new("RGB", (size, size), (18, 17, 15))
    d = ImageDraw.Draw(im)
    c, s = size / 2, size / 512
    r = (150 if maskable else 190) * s
    d.ellipse([c - r, c - r, c + r, c + r], fill=(233, 166, 64))
    r2 = r * 0.62
    d.ellipse([c - r2, c - r2, c + r2, c + r2], fill=(18, 17, 15))
    for k in range(6):  # 조리개 날 느낌의 작은 구멍들
        import math
        a = k * math.pi / 3
        x, y, rr = c + math.cos(a) * r * 0.81, c + math.sin(a) * r * 0.81, r * 0.09
        d.ellipse([x - rr, y - rr, x + rr, y + rr], fill=(18, 17, 15))
    r3 = r2 * 0.42
    d.ellipse([c - r3, c - r3, c + r3, c + r3], fill=(236, 230, 219))
    return im


def build_web():
    out = os.path.join(ROOT, "web")
    os.makedirs(out, exist_ok=True)
    head = ('<link rel="manifest" href="manifest.webmanifest"><link rel="icon" href="icon-192.png">'
            '<link rel="apple-touch-icon" href="icon-192.png">')
    sw = "<script>if('serviceWorker' in navigator&&location.protocol==='https:')navigator.serviceWorker.register('sw.js');</script>"
    open(os.path.join(out, "index.html"), "w", encoding="utf-8").write(doc(page("jszip.min.js") + sw, head))
    shutil.copy(os.path.join(HERE, "jszip.min.js"), out)
    icon(192).save(os.path.join(out, "icon-192.png"))
    icon(512).save(os.path.join(out, "icon-512.png"))
    icon(512, True).save(os.path.join(out, "icon-maskable.png"))
    manifest = {
        "name": "필름 레시피 변환기", "short_name": "필름 레시피", "lang": "ko",
        "start_url": "./", "scope": "./", "display": "standalone",
        "background_color": "#12110f", "theme_color": "#12110f",
        "icons": [{"src": "icon-192.png", "sizes": "192x192", "type": "image/png"},
                  {"src": "icon-512.png", "sizes": "512x512", "type": "image/png"},
                  {"src": "icon-maskable.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable"}],
    }
    json.dump(manifest, open(os.path.join(out, "manifest.webmanifest"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    open(os.path.join(out, "sw.js"), "w").write(read("sw.js").replace("__VERSION__", VERSION))


def build_android():
    out = os.path.join(ROOT, "android", "app", "src", "main", "assets", "www")
    os.makedirs(out, exist_ok=True)
    open(os.path.join(out, "index.html"), "w", encoding="utf-8").write(doc(page("jszip.min.js")))
    shutil.copy(os.path.join(HERE, "jszip.min.js"), out)
    res = os.path.join(ROOT, "android", "app", "src", "main", "res")
    for dpi, px in (("mdpi", 48), ("hdpi", 72), ("xhdpi", 96), ("xxhdpi", 144), ("xxxhdpi", 192)):
        os.makedirs(os.path.join(res, "mipmap-" + dpi), exist_ok=True)
        icon(512).resize((px, px), Image.LANCZOS).save(os.path.join(res, "mipmap-" + dpi, "ic_launcher.png"))


def build_artifact():
    out = os.path.join(ROOT, "build")
    os.makedirs(out, exist_ok=True)
    open(os.path.join(out, "artifact.html"), "w", encoding="utf-8").write(
        page("https://cdnjs.cloudflare.com/ajax/libs/jszip/3.10.1/jszip.min.js"))


if __name__ == "__main__":
    build_web(); build_android(); build_artifact()
    print("built web/, android assets, build/artifact.html")
