/* Recipe Lab 레시피 변환 엔진 (recipefilter.py 의 JavaScript 이식판).
 * 원본 레시피: voxivoid/recipe-lab-sony-pmca v1.6.2 (MIT). 브라우저 메인 스레드, Web Worker, Node 어디서든 돈다. */
var RecipeEngine = (function () {
  var STYLES = {
    standard: {},
    vivid: { sat: 1.32, con: 0.12 },
    neutral: { sat: 0.80, con: -0.10, sharp: -0.5 },
    portrait: { sat: 0.92, con: -0.06, gamma: 0.98, tint: [1.01, 1.0, 0.99], hues: [[25, 30, -0.08]], sharp: -0.5 },
    landscape: { sat: 1.18, con: 0.10, hues: [[110, 50, 0.15], [215, 45, 0.15]], sharp: 0.5 },
    clear: { sat: 1.06, con: 0.06, gamma: 0.97, tint: [0.99, 1.0, 1.01] },
    deep: { sat: 1.15, con: 0.10, gamma: 1.08 },
    light: { sat: 0.88, con: -0.14, gamma: 0.90 },
    sunset: { sat: 1.12, con: 0.05, tint: [1.04, 1.0, 0.92], hues: [[20, 40, 0.20]] },
    night: { sat: 0.85, con: 0.06, gamma: 1.12 },
    autumn: { sat: 1.10, con: 0.04, tint: [1.02, 1.0, 0.97], hues: [[15, 35, 0.30], [45, 30, 0.20]] },
    mono: { mono: true },
    sepia: { mono: true, sepia: true }
  };
  var SAT_STEP = 0.10, CON_STEP = 0.10, SHARP_STEP = 0.35, AB_MIRED_STEP = 5.0, GM_STEP = 0.025, SCENE_KELVIN = 5500;
  var DRO_LIFT = { off: -0.06, 1: -0.03, 2: -0.015, auto: 0, 3: 0.03, 4: 0.06, 5: 0.09 };
  var LR = 0.299, LG = 0.587, LB = 0.114;

  function clamp01(x) { return x < 0 ? 0 : x > 1 ? 1 : x; }
  function toLin(c) { return c <= 0.04045 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4); }
  function toSrgb(c) { if (c < 0) c = 0; return c <= 0.0031308 ? c * 12.92 : 1.055 * Math.pow(c, 1 / 2.4) - 0.055; }

  function kelvinToLin(t) {
    t = Math.min(25000, Math.max(1667, t));
    var x, y;
    if (t <= 4000) x = -0.2661239e9 / (t * t * t) - 0.2343589e6 / (t * t) + 0.8776956e3 / t + 0.179910;
    else x = -3.0258469e9 / (t * t * t) + 2.1070379e6 / (t * t) + 0.2226347e3 / t + 0.240390;
    if (t <= 2222) y = -1.1063814 * x * x * x - 1.34811020 * x * x + 2.18555832 * x - 0.20219683;
    else if (t <= 4000) y = -0.9549476 * x * x * x - 1.37418593 * x * x + 2.09137015 * x - 0.16748867;
    else y = 3.0817580 * x * x * x - 5.87338670 * x * x + 3.75112997 * x - 0.37001483;
    var X = x / y, Y = 1, Z = (1 - x - y) / y;
    return [3.2406 * X - 1.5372 * Y - 0.4986 * Z, -0.9689 * X + 1.8758 * Y + 0.0415 * Z, 0.0557 * X - 0.2040 * Y + 1.0570 * Z];
  }

  function wbGains(r) {
    var scene = kelvinToLin(SCENE_KELVIN);
    var target = r.wb === "kelvin" && r.kelvin ? r.kelvin : SCENE_KELVIN;
    var mired = 1e6 / target - AB_MIRED_STEP * (r.wb_amber_blue || 0);
    var w = kelvinToLin(1e6 / mired);
    var g = [scene[0] / w[0], scene[1] / w[1], scene[2] / w[2]];
    g = [g[0] / g[1], 1, g[2] / g[1]];
    g[1] *= 1 + GM_STEP * (r.wb_green_magenta || 0);
    return g;
  }

  function hueDeg(r, g, b) {
    var h = Math.atan2(Math.sqrt(3) * (g - b), 2 * r - g - b) * 180 / Math.PI;
    return (h + 360) % 360;
  }

  function contrast(x, k) {
    if (Math.abs(k) < 1e-6) return x;
    x = clamp01(x);
    var s = k > 0 ? x * x * (3 - 2 * x) : 0.5 - Math.sin(Math.asin(Math.max(-1, Math.min(1, 1 - 2 * x))) / 3);
    return x + Math.min(Math.abs(k), 1) * (s - x);
  }

  function droCurve(y, dro) {
    var s = DRO_LIFT[dro] || 0;
    var out = y + s * y * (1 - y) * (1 - y) * 6.75;
    if (typeof dro === "number" && dro > 3) out -= 0.02 * (dro - 3) * y * y * (1 - y) * 6.75;
    return out;
  }

  function sepiaOf(y, out) { out[0] = y * 1.07 + 0.02; out[1] = y * 0.97 + 0.01; out[2] = y * 0.80; }

  function effect(c, pe, sub) {
    var y = c[0] * LR + c[1] * LG + c[2] * LB, i, s = [0, 0, 0], t;
    if (pe === "rough-mono") { var m = contrast(contrast(y, 0.8), 0.4); c[0] = c[1] = c[2] = m; return; }
    if (pe === "retro-photo") {
      sepiaOf(y, s);
      for (i = 0; i < 3; i++) c[i] = contrast((y + (c[i] - y) * 0.45) * 0.65 + s[i] * 0.35, -0.25) * 0.92 + 0.06;
      return;
    }
    if (pe === "soft-high-key") {
      t = [[0.94, 1.0, 1.08], [1.07, 0.96, 1.02], [0.96, 1.06, 0.97]][sub >= 0 && sub < 3 ? sub : 0];
      for (i = 0; i < 3; i++) c[i] = (contrast(Math.pow(clamp01(y + (c[i] - y) * 0.7), 0.75), -0.35) * 0.9 + 0.1) * t[i];
      return;
    }
    if (pe === "pop-color") { for (i = 0; i < 3; i++) c[i] = contrast(clamp01(y + (c[i] - y) * 1.7), 0.2); return; }
    if (pe === "toy-camera") {
      t = [[1, 1, 1], [0.92, 1.0, 1.1], [1.1, 1.0, 0.88], [0.95, 1.08, 0.95], [1.08, 0.92, 1.06]][sub >= 0 && sub < 5 ? sub : 0];
      for (i = 0; i < 3; i++) c[i] = contrast(clamp01(y + (c[i] - y) * 1.3), 0.3) * t[i];
      return;
    }
    if (pe === "posterization") {
      for (i = 0; i < 3; i++) c[i] = Math.round((sub === 1 ? y : c[i]) * 3) / 3;
      return;
    }
    if (pe === "part-color") {
      var center = [0, 120, 225, 55][sub >= 0 && sub < 4 ? sub : 0];
      var d = Math.abs(((hueDeg(c[0], c[1], c[2]) - center + 180) % 360 + 360) % 360 - 180);
      var keep = clamp01(1 - (d - 20) / 20);
      for (i = 0; i < 3; i++) c[i] = y + (c[i] - y) * keep;
    }
  }

  /** 레시피를 미리 계산해 픽셀 하나에 빠르게 적용할 수 있게 만든다. */
  function prepare(r) {
    var g = wbGains(r), ev = Math.pow(2, r.ev || 0);
    return {
      r: r, gains: [g[0] * ev, g[1] * ev, g[2] * ev],
      bright: Math.max(g[0] * ev, g[1] * ev, g[2] * ev) > 1.001,
      dro: r.dro == null ? "auto" : r.dro,
      pe: r.picture_effect || "off", sub: r.effect_sub || 0,
      st: STYLES[r.style || "standard"] || {},
      sat: (STYLES[r.style || "standard"].sat || 1) * Math.max(0, 1 + SAT_STEP * (r.saturation || 0)),
      con: (STYLES[r.style || "standard"].con || 0) + CON_STEP * (r.contrast || 0)
    };
  }

  /** c: [r,g,b] sRGB 0..1, 제자리에서 바꾼다. */
  function colorPixel(p, c) {
    var i, v, knee = 0.85;
    for (i = 0; i < 3; i++) {
      v = toLin(c[i]) * p.gains[i];
      if (p.bright && v > knee) v = knee + (1 - knee) * Math.tanh((v - knee) / (1 - knee));
      c[i] = clamp01(toSrgb(v));
    }
    if (p.dro !== "auto") {
      var y0 = c[0] * LR + c[1] * LG + c[2] * LB;
      var y2 = clamp01(droCurve(y0, p.dro)), f = y2 / Math.max(y0, 1e-4);
      for (i = 0; i < 3; i++) c[i] = clamp01(c[i] * f);
    }
    if (p.pe !== "off") { effect(c, p.pe, p.sub); for (i = 0; i < 3; i++) c[i] = clamp01(c[i]); return c; }
    var st = p.st;
    if (st.tint) for (i = 0; i < 3; i++) c[i] *= st.tint[i];
    if (st.gamma && st.gamma !== 1) for (i = 0; i < 3; i++) c[i] = Math.pow(clamp01(c[i]), st.gamma);
    var y = c[0] * LR + c[1] * LG + c[2] * LB;
    if (st.mono) { c[0] = c[1] = c[2] = y; }
    else {
      var s = p.sat;
      if (st.hues) {
        var h = hueDeg(c[0], c[1], c[2]);
        for (var k = 0; k < st.hues.length; k++) {
          var d = Math.abs(((h - st.hues[k][0] + 180) % 360 + 360) % 360 - 180);
          s += p.sat * st.hues[k][2] * clamp01(1 - d / st.hues[k][1]);
        }
      }
      for (i = 0; i < 3; i++) c[i] = y + (c[i] - y) * s;
    }
    for (i = 0; i < 3; i++) c[i] = contrast(clamp01(c[i]), p.con);
    if (st.sepia) sepiaOf(c[0], c);
    for (i = 0; i < 3; i++) c[i] = clamp01(c[i]);
    return c;
  }

  /** [b][g][r] 순서 3D LUT (Float32Array, size^3*3). */
  function buildLut(r, size) {
    size = size || 33;
    var p = prepare(r), lut = new Float32Array(size * size * size * 3), c = [0, 0, 0], n = 0;
    for (var b = 0; b < size; b++) for (var g = 0; g < size; g++) for (var rr = 0; rr < size; rr++) {
      c[0] = rr / (size - 1); c[1] = g / (size - 1); c[2] = b / (size - 1);
      colorPixel(p, c);
      lut[n++] = c[0]; lut[n++] = c[1]; lut[n++] = c[2];
    }
    return { size: size, data: lut };
  }

  /** RGBA 바이트 배열에 LUT를 삼선형 보간으로 적용 (제자리). 0..255 정수 결과. */
  function applyLut(px, lut) {
    var N = lut.size, D = lut.data, s1 = N - 1, sg = N * 3, sb = N * N * 3;
    for (var i = 0; i < px.length; i += 4) {
      var fr = px[i] / 255 * s1, fg = px[i + 1] / 255 * s1, fb = px[i + 2] / 255 * s1;
      var r0 = fr | 0, g0 = fg | 0, b0 = fb | 0;
      if (r0 > N - 2) r0 = N - 2; if (g0 > N - 2) g0 = N - 2; if (b0 > N - 2) b0 = N - 2;
      var dr = fr - r0, dg = fg - g0, db = fb - b0;
      var o = b0 * sb + g0 * sg + r0 * 3;
      for (var ch = 0; ch < 3; ch++) {
        var c000 = D[o + ch], c001 = D[o + 3 + ch], c010 = D[o + sg + ch], c011 = D[o + sg + 3 + ch];
        var c100 = D[o + sb + ch], c101 = D[o + sb + 3 + ch], c110 = D[o + sb + sg + ch], c111 = D[o + sb + sg + 3 + ch];
        var c00 = c000 + (c001 - c000) * dr, c01 = c010 + (c011 - c010) * dr;
        var c10 = c100 + (c101 - c100) * dr, c11 = c110 + (c111 - c110) * dr;
        var c0 = c00 + (c01 - c00) * dg, c1 = c10 + (c11 - c10) * dg;
        px[i + ch] = (c0 + (c1 - c0) * db) * 255 + 0.5;
      }
    }
  }

  function sharpAmount(r) {
    if ((r.picture_effect || "off") !== "off") return 0;
    return SHARP_STEP * (r.sharpness || 0) + 0.35 * ((STYLES[r.style || "standard"] || {}).sharp || 0);
  }

  function boxBlurH(src, dst, w, h, rad) {
    var win = rad * 2 + 1;
    for (var y = 0; y < h; y++) for (var ch = 0; ch < 3; ch++) {
      var row = y * w * 4 + ch, acc = 0, x;
      for (x = -rad; x <= rad; x++) acc += src[row + Math.min(w - 1, Math.max(0, x)) * 4];
      for (x = 0; x < w; x++) {
        dst[row + x * 4] = acc / win;
        acc += src[row + Math.min(w - 1, x + rad + 1) * 4] - src[row + Math.max(0, x - rad) * 4];
      }
    }
  }
  function boxBlurV(src, dst, w, h, rad) {
    var win = rad * 2 + 1, st = w * 4;
    for (var x = 0; x < w; x++) for (var ch = 0; ch < 3; ch++) {
      var col = x * 4 + ch, acc = 0, y;
      for (y = -rad; y <= rad; y++) acc += src[col + Math.min(h - 1, Math.max(0, y)) * st];
      for (y = 0; y < h; y++) {
        dst[col + y * st] = acc / win;
        acc += src[col + Math.min(h - 1, y + rad + 1) * st] - src[col + Math.max(0, y - rad) * st];
      }
    }
  }

  /** 가우시안 근사(박스 블러 3회)로 선명하게(+) 또는 부드럽게(-). px: RGBA Uint8ClampedArray, 제자리. */
  function sharpen(px, w, h, amount, radius) {
    if (Math.abs(amount) < 0.01) return;
    var rad = Math.max(1, Math.round(radius * 0.8));
    var a = new Float32Array(px.length), b = new Float32Array(px.length);
    for (var i = 0; i < px.length; i++) a[i] = px[i];
    boxBlurH(a, b, w, h, rad); boxBlurV(b, a, w, h, rad);
    boxBlurH(a, b, w, h, rad); boxBlurV(b, a, w, h, rad);
    for (i = 0; i < px.length; i += 4) for (var ch = 0; ch < 3; ch++) {
      var o = px[i + ch], bl = a[i + ch];
      if (amount > 0) { var d = o - bl; if (Math.abs(d) >= 2) px[i + ch] = o + amount * d; }
      else px[i + ch] = o + Math.min(1, -amount) * (bl - o);
    }
  }

  function hash(x, y, seed) {
    var n = (x * 374761393 + y * 668265263 + seed * 2147483647) | 0;
    n = Math.imul(n ^ (n >>> 13), 1274126177);
    return ((n ^ (n >>> 16)) >>> 0) / 4294967296;
  }

  /** 입자(rough-mono)와 비네팅(toy-camera). y0: 전체 이미지에서 이 띠의 시작 행. */
  function spatial(px, w, rows, y0, fullW, fullH, r) {
    var pe = r.picture_effect || "off";
    if (pe === "toy-camera") {
      for (var y = 0; y < rows; y++) {
        var yy = (y0 + y - fullH / 2) / (fullH / 2);
        for (var x = 0; x < w; x++) {
          var xx = (x - fullW / 2) / (fullW / 2), d2 = yy * yy + xx * xx;
          var f = Math.max(0, 1 - 0.35 * Math.pow(d2, 1.2)), o = (y * w + x) * 4;
          px[o] *= f; px[o + 1] *= f; px[o + 2] *= f;
        }
      }
    } else if (pe === "rough-mono") {
      var cell = Math.max(1, 1.4 * Math.max(fullW, fullH) / 3000);
      for (y = 0; y < rows; y++) {
        var gy = (y0 + y) / cell, iy = Math.floor(gy), ty = gy - iy;
        for (x = 0; x < w; x++) {
          var gx = x / cell, ix = Math.floor(gx), tx = gx - ix;
          var n = (hash(ix, iy, 7) * (1 - tx) + hash(ix + 1, iy, 7) * tx) * (1 - ty) +
                  (hash(ix, iy + 1, 7) * (1 - tx) + hash(ix + 1, iy + 1, 7) * tx) * ty;
          var add = (n - 0.5) * 2 * 31; // 표준편차 약 18
          o = (y * w + x) * 4;
          px[o] += add; px[o + 1] += add; px[o + 2] += add;
        }
      }
    }
  }

  function summary(r) {
    var b = [];
    if (r.picture_effect && r.picture_effect !== "off") b.push("효과 " + r.picture_effect);
    else b.push(r.style + " " + sg(r.saturation) + "/" + sg(r.contrast) + "/" + sg(r.sharpness));
    if (r.wb === "kelvin") b.push(r.kelvin + "K");
    if (r.wb_amber_blue) b.push((r.wb_amber_blue > 0 ? "A" : "B") + Math.abs(r.wb_amber_blue));
    if (r.wb_green_magenta) b.push((r.wb_green_magenta > 0 ? "G" : "M") + Math.abs(r.wb_green_magenta));
    if (r.ev) b.push("EV " + (r.ev > 0 ? "+" : "") + r.ev.toFixed(1));
    if (r.dro !== "auto" && r.dro != null) b.push("DRO " + r.dro);
    return b.join(" · ");
    function sg(v) { v = v || 0; return (v > 0 ? "+" : "") + v; }
  }

  return { STYLES: STYLES, prepare: prepare, colorPixel: colorPixel, buildLut: buildLut, applyLut: applyLut,
           sharpAmount: sharpAmount, sharpen: sharpen, spatial: spatial, summary: summary, wbGains: wbGains };
})();
if (typeof module !== "undefined") module.exports = RecipeEngine;
