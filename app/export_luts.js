// 레시피 77개를 .cube 3D LUT로 내보낸다 (프리미어 프로 Lumetri, 다빈치 리졸브, 파이널 컷, 포토샵 등).
// 사용: node app/export_luts.js [출력 폴더=luts] [크기=33]
// 앱과 똑같은 엔진(engine.js)의 색 변환만 담긴다. 선명도·입자·비네팅은 LUT로 표현할 수 없어 빠진다.
const fs = require("fs"), path = require("path");
const E = require("./engine.js");
const recipes = require("./recipes.json").recipes;
const out = process.argv[2] || "luts", size = +(process.argv[3] || 33);
const BRAND = { "Sony": "01 Sony", "Fuji Sim": "02 Fuji Simulation", "Fuji Film": "03 Fuji Film", "Kodak": "04 Kodak", "Cine": "05 Cine",
  "Ricoh GR": "06 Ricoh GR", "Leica": "07 Leica", "Hasselblad": "08 Hasselblad", "Canon / Nikon": "09 Canon Nikon",
  "Pana / Olympus": "10 Panasonic Olympus", "Other Stocks": "11 Other Stocks", "Ilford": "12 Ilford" };
const safe = s => s.replace(/[\/\\:*?"<>|]+/g, " ").replace(/\s+/g, " ").trim();
let n = 0;
for (const r of recipes) {
  const dir = path.join(out, BRAND[r.group] || r.group);
  fs.mkdirSync(dir, { recursive: true });
  const lut = E.buildLut(r, size).data;
  // 프로그램마다 해석이 갈리는 주석·DOMAIN 줄은 넣지 않는다 (기본값 0..1). 가장 단순한 Adobe .cube 형식.
  const lines = [`TITLE "${safe(r.name)}"`, `LUT_3D_SIZE ${size}`];
  for (let i = 0; i < lut.length; i += 3) lines.push(`${lut[i].toFixed(6)} ${lut[i + 1].toFixed(6)} ${lut[i + 2].toFixed(6)}`);
  fs.writeFileSync(path.join(dir, safe(r.name) + ".cube"), lines.join("\r\n") + "\r\n");
  n++;
}
console.log(`${n} LUTs (${size}^3) -> ${out}/`);
