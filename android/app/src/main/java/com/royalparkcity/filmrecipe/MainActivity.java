package com.royalparkcity.filmrecipe;

import android.app.Activity;
import android.content.ClipData;
import android.content.ContentResolver;
import android.content.ContentValues;
import android.content.Intent;
import android.database.Cursor;
import android.graphics.Color;
import android.net.Uri;
import android.os.Bundle;
import android.provider.MediaStore;
import android.provider.OpenableColumns;
import android.util.Base64;
import android.webkit.JavascriptInterface;
import android.webkit.ValueCallback;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceRequest;
import android.webkit.WebResourceResponse;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;

import androidx.annotation.NonNull;
import androidx.webkit.WebViewAssetLoader;

import java.io.InputStream;
import java.io.OutputStream;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * 웹앱(assets/www/index.html)을 그대로 띄우는 껍데기.
 * 웹에서 할 수 없는 두 가지만 맡는다: 사진 고르기(파일 선택 창)와 결과를 갤러리에 저장하기.
 */
public class MainActivity extends Activity {
    private static final String HOST = "appassets.androidplatform.net";
    private static final String START = "https://" + HOST + "/assets/www/index.html";
    private static final int PICK = 1;

    private WebView web;
    private ValueCallback<Uri[]> pending;
    private final List<Uri> shared = new ArrayList<>();
    private final Map<String, Sink> sinks = new HashMap<>();
    private int nextToken = 1;

    private static class Sink {
        Uri uri;
        OutputStream out;
    }

    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);
        getWindow().setStatusBarColor(Color.rgb(18, 17, 15));
        getWindow().setNavigationBarColor(Color.rgb(18, 17, 15));

        final ContentResolver cr = getContentResolver();
        final WebViewAssetLoader loader = new WebViewAssetLoader.Builder()
                .setDomain(HOST)
                .addPathHandler("/assets/", new WebViewAssetLoader.AssetsPathHandler(this))
                // 다른 앱에서 공유받은 사진: /shared/0, /shared/1 ...
                .addPathHandler("/shared/", path -> {
                    try {
                        int i = Integer.parseInt(path);
                        Uri u;
                        synchronized (shared) { u = i < shared.size() ? shared.get(i) : null; }
                        if (u == null) return null;
                        String type = cr.getType(u);
                        InputStream in = cr.openInputStream(u);
                        return new WebResourceResponse(type != null ? type : "image/jpeg", null, in);
                    } catch (Exception e) {
                        return null;
                    }
                })
                .build();

        web = new WebView(this);
        web.setBackgroundColor(Color.rgb(18, 17, 15));
        WebSettings s = web.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        s.setAllowFileAccess(false);
        s.setAllowContentAccess(true);

        web.setWebViewClient(new WebViewClient() {
            @Override
            public WebResourceResponse shouldInterceptRequest(WebView v, WebResourceRequest req) {
                return loader.shouldInterceptRequest(req.getUrl());
            }

            @Override
            public boolean shouldOverrideUrlLoading(WebView v, WebResourceRequest req) {
                Uri u = req.getUrl();
                if (HOST.equals(u.getHost())) return false;
                try { startActivity(new Intent(Intent.ACTION_VIEW, u)); } catch (Exception ignored) { }
                return true;
            }
        });

        web.setWebChromeClient(new WebChromeClient() {
            @Override
            public boolean onShowFileChooser(WebView v, ValueCallback<Uri[]> cb, FileChooserParams p) {
                if (pending != null) pending.onReceiveValue(null);
                pending = cb;
                Intent i = new Intent(Intent.ACTION_GET_CONTENT);
                i.setType("image/*");
                i.addCategory(Intent.CATEGORY_OPENABLE);
                i.putExtra(Intent.EXTRA_ALLOW_MULTIPLE, true);
                try {
                    startActivityForResult(Intent.createChooser(i, "사진 고르기"), PICK);
                } catch (Exception e) {
                    pending = null;
                    return false;
                }
                return true;
            }
        });

        web.addJavascriptInterface(new Bridge(), "AndroidBridge");
        takeShared(getIntent());
        setContentView(web);
        if (state != null) web.restoreState(state);
        else web.loadUrl(START);
    }

    @Override
    protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent);
        if (takeShared(intent)) web.evaluateJavascript("window.onAndroidShare && window.onAndroidShare()", null);
    }

    /** 공유로 들어온 사진 목록을 새로 받는다. */
    private boolean takeShared(Intent intent) {
        if (intent == null) return false;
        List<Uri> got = new ArrayList<>();
        String a = intent.getAction();
        if (Intent.ACTION_SEND.equals(a)) {
            Uri u = intent.getParcelableExtra(Intent.EXTRA_STREAM);
            if (u != null) got.add(u);
        } else if (Intent.ACTION_SEND_MULTIPLE.equals(a)) {
            ArrayList<Uri> us = intent.getParcelableArrayListExtra(Intent.EXTRA_STREAM);
            if (us != null) got.addAll(us);
        }
        if (got.isEmpty()) return false;
        synchronized (shared) { shared.clear(); shared.addAll(got); }
        return true;
    }

    private String displayName(Uri u) {
        try (Cursor c = getContentResolver().query(u, new String[]{OpenableColumns.DISPLAY_NAME}, null, null, null)) {
            if (c != null && c.moveToFirst()) return c.getString(0);
        } catch (Exception ignored) { }
        String last = u.getLastPathSegment();
        return last != null ? last : "photo.jpg";
    }

    @Override
    protected void onActivityResult(int req, int res, Intent data) {
        super.onActivityResult(req, res, data);
        if (req != PICK || pending == null) return;
        Uri[] result = null;
        if (res == RESULT_OK && data != null) {
            ClipData clip = data.getClipData();
            if (clip != null) {
                result = new Uri[clip.getItemCount()];
                for (int i = 0; i < result.length; i++) result[i] = clip.getItemAt(i).getUri();
            } else if (data.getData() != null) {
                result = new Uri[]{data.getData()};
            }
        }
        pending.onReceiveValue(result);
        pending = null;
    }

    @Override
    protected void onSaveInstanceState(@NonNull Bundle out) {
        super.onSaveInstanceState(out);
        web.saveState(out);
    }

    @Override
    public void onBackPressed() {
        if (web.canGoBack()) web.goBack();
        else super.onBackPressed();
    }

    /** 웹 화면에서 window.AndroidBridge 로 부르는 함수들. */
    private class Bridge {
        @JavascriptInterface
        public int sharedCount() {
            synchronized (shared) { return shared.size(); }
        }

        @JavascriptInterface
        public String sharedName(int i) {
            Uri u;
            synchronized (shared) { u = i < shared.size() ? shared.get(i) : null; }
            return u == null ? "" : displayName(u);
        }

        @JavascriptInterface
        public void clearShared() {
            synchronized (shared) { shared.clear(); }
        }

        /** 저장을 시작하고 토큰을 돌려준다. JPG는 사진/FilmRecipe, ZIP은 다운로드/FilmRecipe. */
        @JavascriptInterface
        public String begin(String name, String mime) {
            try {
                boolean zip = mime != null && mime.contains("zip");
                ContentValues v = new ContentValues();
                v.put(MediaStore.MediaColumns.DISPLAY_NAME, name);
                v.put(MediaStore.MediaColumns.MIME_TYPE, zip ? "application/zip" : "image/jpeg");
                v.put(MediaStore.MediaColumns.RELATIVE_PATH, zip ? "Download/FilmRecipe" : "Pictures/FilmRecipe");
                v.put(MediaStore.MediaColumns.IS_PENDING, 1);
                Uri base = zip ? MediaStore.Downloads.EXTERNAL_CONTENT_URI : MediaStore.Images.Media.EXTERNAL_CONTENT_URI;
                Sink sk = new Sink();
                sk.uri = getContentResolver().insert(base, v);
                if (sk.uri == null) return "";
                sk.out = getContentResolver().openOutputStream(sk.uri);
                if (sk.out == null) return "";
                synchronized (sinks) {
                    String t = String.valueOf(nextToken++);
                    sinks.put(t, sk);
                    return t;
                }
            } catch (Exception e) {
                return "";
            }
        }

        @JavascriptInterface
        public boolean append(String token, String b64) {
            Sink sk;
            synchronized (sinks) { sk = sinks.get(token); }
            if (sk == null) return false;
            try {
                sk.out.write(Base64.decode(b64, Base64.DEFAULT));
                return true;
            } catch (Exception e) {
                return false;
            }
        }

        @JavascriptInterface
        public String finish(String token) {
            Sink sk;
            synchronized (sinks) { sk = sinks.remove(token); }
            if (sk == null) return "저장할 파일을 찾지 못했어요";
            try {
                sk.out.close();
                ContentValues v = new ContentValues();
                v.put(MediaStore.MediaColumns.IS_PENDING, 0);
                getContentResolver().update(sk.uri, v, null, null);
                return "ok";
            } catch (Exception e) {
                getContentResolver().delete(sk.uri, null, null);
                return "저장하지 못했어요: " + e.getMessage();
            }
        }
    }
}
