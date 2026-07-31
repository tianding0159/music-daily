"""一次性/增量预热 data/pool_media.json：给全池补 iTunes 封面/试听（走缓存，逐个查）。
用法：python3 tools/warm_media.py [每次最多查多少首，默认全部]
"""
import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'scripts'))
import itunes, picker

DATA = ROOT / 'data'; MEDIA = DATA / 'pool_media.json'
limit = int(sys.argv[1]) if len(sys.argv) > 1 else 10**9
pool = json.loads((DATA / 'pool.json').read_text(encoding='utf-8'))
media = json.loads(MEDIA.read_text(encoding='utf-8')) if MEDIA.exists() else {}
items = [t for t in pool if picker.is_eligible(t)[0]]
todo = [t for t in items if t['id'] not in media][:limit]
print(f"池 {len(items)} · 已有 {len(media)} · 本次待补 {len(todo)}", flush=True)
cache = itunes.load_cache(); hit = 0
for i, t in enumerate(todo, 1):
    info = itunes.lookup(t['artist'], t['title'], cache)
    ok = info.get('found')
    media[t['id']] = ({"c": info['artwork'], "p": info['preview'], "a": info['apple_url']}
                      if ok else {"c": "", "p": "", "a": ""})
    hit += 1 if ok else 0
    if i % 40 == 0:
        MEDIA.write_text(json.dumps(media, ensure_ascii=False), encoding='utf-8')
        itunes.save_cache(cache)
        print(f"  {i}/{len(todo)} · 命中 {hit}", flush=True)
MEDIA.write_text(json.dumps(media, ensure_ascii=False), encoding='utf-8')
itunes.save_cache(cache)
print(f"完成：本次 {len(todo)} 首、命中 {hit}；媒体表共 {len(media)} 条", flush=True)
