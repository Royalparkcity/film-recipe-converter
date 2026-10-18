# 필름 레시피 변환기

Sony 카메라용 [Recipe Lab](https://github.com/voxivoid/recipe-lab-sony-pmca)의 레시피 77개
(라이카, 후지, 리코, 코닥, 일포드 …)를 이미 찍은 사진에 입히는 변환기. 사진 여러 장을 한꺼번에 바꾸고,
사진은 기기 밖으로 나가지 않는다.

- **웹**: https://royalparkcity.github.io/film-recipe-converter/ (폰 크롬에서 "홈 화면에 추가"하면 앱처럼 설치, 한 번 열면 오프라인 동작)
- **안드로이드 앱**: [Releases → FilmRecipe.apk](../../releases/latest). 결과는 갤러리의 `Pictures/FilmRecipe`에 저장되고, 갤러리에서 사진을 "공유 → 필름 레시피"로 보내도 열린다.
- **LUT 77개 (.cube)**: [Releases → FilmRecipe_LUTs.zip](../../releases/tag/luts-latest). 프리미어 프로 Lumetri, 다빈치 리졸브 등에서 사용. 만들기: `node app/export_luts.js`
- **명령줄(파이썬)**: `python/recipefilter.py` — 폴더 일괄 변환, 비교 시트, .cube LUT 내보내기

## 레시피는 어떻게 옮겼나
Recipe Lab 레시피는 LUT가 아니라 a6000에 저장되는 설정값(Creative Style, 채도/대비/선명도, WB 켈빈과 미세조정,
노출 보정, DRO, Picture Effect)이다. 각 설정값을 근사적인 이미지 연산으로 옮겼다(`app/engine.js`, 파이썬판과 결과 동일).
입력 사진을 "Sony Standard + 자동 WB"로 가정하므로 폰 사진은 강도를 70–80%로 두는 편이 자연스럽다.
원작자도 밝히듯 다른 회사 색을 그대로 복제한 것이 아니라 비슷하게 흉내 낸 근사치다.

## 구조
| 경로 | 내용 |
|---|---|
| `app/` | 화면(`app.template.html`), 변환 엔진(`engine.js`), 레시피(`recipes.json`), 빌드 스크립트 |
| `web/` | 빌드된 웹앱 (Pages로 배포) |
| `android/` | 웹앱을 띄우는 WebView 앱. 사진 선택과 갤러리 저장만 네이티브로 처리 |
| `python/` | 명령줄 변환기와 레시피 추출기 |

화면이나 엔진을 고친 뒤 `python3 app/build.py`를 실행하면 `web/`와 안드로이드 assets가 다시 만들어진다.
main에 푸시하면 웹은 Pages로 배포되고 APK는 자동 빌드되어 Releases에 올라간다.

`android/app/signing.keystore`는 개인용 직접 설치 앱이라 업데이트가 끊기지 않도록 일부러 저장소에 둔 서명 키다.
Play 스토어에 올릴 때는 새 키를 만들어 비밀로 보관해야 한다.

레시피 데이터: Recipe Lab © 2026 André Domingues, MIT.
