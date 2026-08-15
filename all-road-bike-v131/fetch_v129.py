from pathlib import Path
from urllib.request import Request, urlopen
from urllib.parse import urljoin, urlparse
import re, json

base='https://artfelt-griffin-1f8222.netlify.app/'
host=urlparse(base).netloc
root=Path('app/src/main/assets/www')
root.mkdir(parents=True, exist_ok=True)

def fetch(url):
    req=Request(url, headers={'User-Agent':'ALL-ROAD-BIKE-V131-BUILDER/1.0'})
    with urlopen(req, timeout=30) as r:
        return r.read(), r.headers.get('Content-Type','')

index_bytes,_=fetch(base+'index.html')
index_text=index_bytes.decode('utf-8','replace')
if 'saved-routes-v129.css?v=129' not in index_text:
    raise SystemExit('FAIL: deployed site is not V129; refusing to build wrong APK')

queue=['index.html','manifest.webmanifest','sw.js']
seen=set()
text_ext={'.html','.htm','.css','.js','.json','.webmanifest','.txt','.xml','.svg'}
asset_ext={'.html','.htm','.css','.js','.json','.webmanifest','.png','.jpg','.jpeg','.webp','.gif','.svg','.ico','.woff','.woff2','.ttf','.otf','.gpx','.geojson','.kml','.xml','.txt','.mp3','.wav','.m4a','.webm','.mp4'}
attr_re=re.compile(r'''(?:src|href)\s*=\s*["']([^"']+)["']''',re.I)
css_re=re.compile(r'''url\(\s*["']?([^\)"']+)''',re.I)
quote_re=re.compile(r'''["']((?:\.?\.?/|/)[^"'\s?#]+(?:\?[^"'\s#]*)?)["']''')

while queue:
    rel=queue.pop(0).split('#',1)[0]
    if rel.startswith('/'): rel=rel[1:]
    if not rel or rel in seen or rel.startswith('.netlify/functions/'): continue
    seen.add(rel)
    url=urljoin(base,rel)
    try: data,ctype=fetch(url)
    except Exception as e:
        print('SKIP',rel,e); continue
    out=root/rel
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_bytes(data)
    ext=Path(urlparse(rel).path).suffix.lower()
    if ext in text_ext or 'text/' in ctype or 'javascript' in ctype or 'json' in ctype or 'xml' in ctype:
        text=data.decode('utf-8','replace')
        candidates=attr_re.findall(text)+css_re.findall(text)+quote_re.findall(text)
        for ref in candidates:
            ref=ref.strip()
            if not ref or ref.startswith(('data:','blob:','mailto:','tel:','javascript:','#')): continue
            absolute=urljoin(url,ref); p=urlparse(absolute)
            if p.netloc!=host: continue
            path=p.path.lstrip('/')
            if not path or path.startswith('.netlify/functions/'): continue
            ext2=Path(path).suffix.lower()
            if ext2 in asset_ext or path in ('index.html','sw.js','manifest.webmanifest'):
                if path not in seen: queue.append(path)

critical=['index.html','styles.css','veloplan.js','sw.js','manifest.webmanifest','osaka-arcade-90-validated.css','v119-finitions.css','mobile-v121.css','mobile-v121.js','mobile-v122.css','profile-v126.js','saved-routes-v124.css','saved-routes-v125.css','saved-routes-v127.css','saved-routes-v128.css','saved-routes-v129.css','ride-dashboard.css','ride-dashboard.js']
missing=[p for p in critical if not (root/p).is_file()]
if missing: raise SystemExit('FAIL missing V129 runtime files: '+', '.join(missing))

for p in root.rglob('*'):
    if p.is_file() and p.suffix.lower() in {'.js','.html'}:
        try: s=p.read_text(encoding='utf-8')
        except Exception: continue
        s2=s.replace('navigator.serviceWorker.register(', 'false && navigator.serviceWorker.register(')
        if s2!=s: p.write_text(s2,encoding='utf-8')

manifest=json.loads((root/'manifest.webmanifest').read_text(encoding='utf-8'))
pngs=[x for x in manifest.get('icons',[]) if str(x.get('src','')).lower().split('?')[0].endswith('.png')]
if not pngs: raise SystemExit('FAIL: no PNG launcher icon in V129 manifest')
def score(x):
    try: return int(str(x.get('sizes','0x0')).split()[0].split('x')[0])
    except: return 0
icon=max(pngs,key=score)
icon_bytes,_=fetch(urljoin(base,icon['src']))
if not icon_bytes.startswith(b'\x89PNG\r\n\x1a\n'): raise SystemExit('FAIL: launcher icon is not PNG')
icon_out=Path('app/src/main/res/drawable/app_logo.png')
icon_out.parent.mkdir(parents=True,exist_ok=True)
icon_out.write_bytes(icon_bytes)
count=sum(1 for p in root.rglob('*') if p.is_file())
total=sum(p.stat().st_size for p in root.rglob('*') if p.is_file())
print(f'V129 runtime frozen: {count} files, {total/1024/1024:.2f} MiB')
print('Launcher icon:',icon['src'])
