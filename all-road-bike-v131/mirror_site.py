#!/usr/bin/env python3
from __future__ import annotations
import json, os, re, sys
from pathlib import Path
from urllib.parse import urljoin, urlparse, unquote
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

BASE = (sys.argv[1] if len(sys.argv) > 1 else os.environ.get('ARB_SITE', '')).rstrip('/') + '/'
if not BASE.startswith('https://'):
    raise SystemExit('ARB_SITE HTTPS requis')
BASE_HOST = urlparse(BASE).netloc
OUT = Path('app/src/main/assets')
OUT.mkdir(parents=True, exist_ok=True)

TEXT_EXT = {'.html','.htm','.css','.js','.json','.webmanifest','.svg','.xml','.txt','.md','.geojson'}
RUNTIME_EXT = TEXT_EXT | {'.png','.jpg','.jpeg','.webp','.gif','.ico','.woff','.woff2','.ttf','.otf','.mp3','.wav','.m4a','.gpx'}
SEEDS = ['/', '/manifest.webmanifest', '/sw.js', '/pwa-v120.js']
seen=set(); queue=list(SEEDS); errors=[]

def request_bytes(url:str):
    req=Request(url, headers={'User-Agent':'ALL-ROAD-BIKE-Android-Packager/131','Accept':'*/*'})
    with urlopen(req, timeout=25) as r:
        return r.read(), r.headers.get_content_type(), r.geturl()

def norm_path(raw:str, current_url:str):
    raw=raw.strip().strip("\"'")
    if not raw or raw.startswith(('#','data:','blob:','javascript:','mailto:','tel:')):
        return None
    full=urljoin(current_url, raw)
    p=urlparse(full)
    if p.scheme not in ('http','https') or p.netloc != BASE_HOST:
        return None
    path=unquote(p.path or '/')
    if path.startswith('/.netlify/functions/'):
        return None
    if path.endswith('/'):
        path += 'index.html'
    ext=Path(path).suffix.lower()
    if path != '/index.html' and ext and ext not in RUNTIME_EXT:
        return None
    return path

def discover(text:str, current_url:str):
    found=set()
    patterns=[
        r'''(?:src|href|poster)\s*=\s*["']([^"']+)["']''',
        r'''url\(\s*["']?([^\)"']+)["']?\s*\)''',
        r'''["']((?:\.?\.?/|/)[^"'\s?#]+(?:\?[^"']*)?)["']''',
        r'''["']([^"']+\.(?:css|js|json|webmanifest|png|jpg|jpeg|webp|svg|ico|woff2?|ttf|otf|gpx|geojson|html)(?:\?[^"']*)?)["']'''
    ]
    for pat in patterns:
        for m in re.findall(pat, text, flags=re.I):
            path=norm_path(m, current_url)
            if path: found.add(path)
    return found

while queue:
    path=queue.pop(0)
    if path == '/': path='/index.html'
    if path in seen: continue
    seen.add(path)
    if len(seen) > 900:
        raise SystemExit('Trop de ressources découvertes, arrêt de sécurité')
    url=urljoin(BASE, path.lstrip('/'))
    try:
        data, ctype, final_url=request_bytes(url)
    except (HTTPError, URLError, TimeoutError) as e:
        print(f'WARN {path}: {e}')
        if path == '/index.html':
            raise
        errors.append((path,str(e)))
        continue
    dest=OUT/path.lstrip('/')
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    ext=dest.suffix.lower()
    if ctype.startswith('text/') or ext in TEXT_EXT:
        text=data.decode('utf-8','ignore')
        for found in sorted(discover(text, final_url)):
            if found not in seen and found not in queue:
                queue.append(found)

index=OUT/'index.html'
if not index.exists(): raise SystemExit('index.html absent')
html=index.read_text('utf-8','ignore')
required_tokens=['ALL ROAD BIKE','saved-routes-v129.css','veloplan.js','ride-dashboard.js','profile-v126.js']
for token in required_tokens:
    if token not in html and not any(token in p.name for p in OUT.rglob('*')):
        raise SystemExit(f'V129 non détectée ou ressource absente: {token}')

if 'android-native.js?v=131' not in html:
    if re.search(r'<head[^>]*>', html, flags=re.I):
        html=re.sub(r'(<head[^>]*>)', r'\1\n<script src="/android-native.js?v=131"></script>', html, count=1, flags=re.I)
    else:
        html='<script src="/android-native.js?v=131"></script>\n'+html
index.write_text(html,'utf-8')

bridge=r'''(() => {
  'use strict';
  const REMOTE = 'https://artfelt-griffin-1f8222.netlify.app';
  window.__ALL_ROAD_BIKE_ANDROID__ = true;
  const rewrite = value => {
    try {
      const s = value instanceof URL ? value.href : String(value);
      if (s.startsWith('/.netlify/functions/')) return REMOTE + s;
      if (s.startsWith(location.origin + '/.netlify/functions/')) return REMOTE + s.slice(location.origin.length);
      return value;
    } catch (_) { return value; }
  };

  const nativeFetch = window.fetch.bind(window);
  window.fetch = function(input, init) {
    if (typeof input === 'string' || input instanceof URL) return nativeFetch(rewrite(input), init);
    try {
      if (input instanceof Request) {
        const u = rewrite(input.url);
        if (u !== input.url) return nativeFetch(new Request(u, input), init);
      }
    } catch (_) {}
    return nativeFetch(input, init);
  };

  try {
    const nativeOpen = XMLHttpRequest.prototype.open;
    XMLHttpRequest.prototype.open = function(method, url, ...rest) {
      return nativeOpen.call(this, method, rewrite(url), ...rest);
    };
  } catch (_) {}

  try {
    const nativeBeacon = navigator.sendBeacon && navigator.sendBeacon.bind(navigator);
    if (nativeBeacon) navigator.sendBeacon = (url, data) => nativeBeacon(rewrite(url), data);
  } catch (_) {}

  try {
    if (navigator.serviceWorker) {
      navigator.serviceWorker.register = async () => ({
        scope: location.origin + '/', active: null, installing: null, waiting: null,
        update: async () => {}, unregister: async () => true
      });
      navigator.serviceWorker.getRegistrations = async () => [];
      navigator.serviceWorker.getRegistration = async () => undefined;
    }
  } catch (_) {}

  class NativeNotification {
    constructor(title, options={}) {
      try { AndroidNative.notify(String(title || 'ALL ROAD BIKE'), String(options.body || '')); } catch (_) {}
    }
    static get permission() { return 'granted'; }
    static requestPermission() {
      try { AndroidNative.requestNotificationPermission(); } catch (_) {}
      return Promise.resolve('granted');
    }
  }
  try { Object.defineProperty(window, 'Notification', { configurable: true, value: NativeNotification }); } catch (_) {}

  async function saveBlobAnchor(anchor) {
    try {
      const response = await nativeFetch(anchor.href);
      const blob = await response.blob();
      const reader = new FileReader();
      reader.onloadend = () => {
        const data = String(reader.result || '');
        const base64 = data.includes(',') ? data.split(',')[1] : '';
        if (base64) AndroidNative.saveBase64(anchor.download || 'all-road-bike-export', base64, blob.type || 'application/octet-stream');
      };
      reader.readAsDataURL(blob);
    } catch (_) {}
  }

  document.addEventListener('click', event => {
    const anchor = event.target && event.target.closest ? event.target.closest('a[download]') : null;
    if (anchor && anchor.href && anchor.href.startsWith('blob:')) {
      event.preventDefault();
      event.stopPropagation();
      saveBlobAnchor(anchor);
    }
  }, true);

  const markNative = () => {
    document.documentElement.dataset.androidApp = 'true';
    const install = document.getElementById('installBtn');
    if (install) install.hidden = true;
    const help = document.getElementById('installHelp');
    if (help) help.hidden = true;
  };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', markNative, {once:true});
  else markNative();
  setTimeout(markNative, 400);
  setTimeout(markNative, 1600);
})();
'''
(OUT/'android-native.js').write_text(bridge,'utf-8')

manifest_path=OUT/'manifest.webmanifest'
icon_url=None
if manifest_path.exists():
    try:
        manifest=json.loads(manifest_path.read_text('utf-8'))
        icons=manifest.get('icons') or []
        def score(item):
            sizes=str(item.get('sizes',''))
            nums=[int(x.split('x')[0]) for x in sizes.split() if 'x' in x and x.split('x')[0].isdigit()]
            return (512 in nums, max(nums) if nums else 0)
        for item in sorted(icons, key=score, reverse=True):
            src=item.get('src')
            if src:
                icon_url=urljoin(BASE, src)
                break
    except Exception as e:
        print('Manifest icon parse warning:',e)
for candidate in [icon_url, urljoin(BASE,'icons/all-road-bike-logo.png'), urljoin(BASE,'icons/icon-512.png')]:
    if not candidate: continue
    try:
        data, _, _ = request_bytes(candidate)
        if data.startswith(b'\x89PNG') and len(data) > 2000:
            icon_dest=Path('app/src/main/res/drawable-nodpi/app_icon.png')
            icon_dest.parent.mkdir(parents=True, exist_ok=True)
            icon_dest.write_bytes(data)
            break
    except Exception:
        pass
else:
    raise SystemExit('Icône PNG ALL ROAD BIKE introuvable')

print(f'Miroir V129 Android: {len([p for p in OUT.rglob("*") if p.is_file()])} fichiers')
print(f'Erreurs non bloquantes: {len(errors)}')
