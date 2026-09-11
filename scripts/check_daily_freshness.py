"""Publish guard: new-policy daily issues must not repeat any earlier recommendation."""
import json
from pathlib import Path
import picker


def validate(data: Path) -> list[str]:
    snapshots = sorted((json.loads(p.read_text(encoding='utf-8')) for p in (data/'issues').glob('*.json')), key=lambda s:s['date'])
    history = json.loads((data/'history.json').read_text(encoding='utf-8'))
    known = json.loads((data/'pool.json').read_text(encoding='utf-8'))
    previous = list(known)
    published = {}
    errors = []
    for snap in snapshots:
        tracks = snap['tracks']; date = snap['date']
        if snap.get('selection_policy') == 'never_repeat_v1':
            earlier = {d: list(set(ids) | set(published.get(d, []))) for d,ids in history.items() if d < date}
            for d, ids in published.items():
                earlier[d] = list(set(earlier.get(d, [])) | set(ids))
            replaced = snap.get('superseded_tracks', [])
            earlier[date] = [t['id'] for t in replaced]
            fresh = picker.unsent_tracks(tracks,earlier,previous + replaced)
            if len(fresh) != len(tracks): errors.append(f'{date}: contains an already recommended work')
            if len({picker.work_key(t) for t in tracks}) != len(tracks): errors.append(f'{date}: duplicate works within issue')
            recorded = history.get(date, [])
            current_ids = [t['id'] for t in tracks]
            allowed = set(current_ids) | {t['id'] for t in replaced}
            if recorded[:len(current_ids)] != current_ids or set(recorded) - allowed:
                errors.append(f'{date}: history and issue disagree')
            if not tracks: errors.append(f'{date}: empty issue')
        records = tracks + snap.get('superseded_tracks', [])
        previous.extend(records)
        published[date] = [t['id'] for t in records]
    return errors


if __name__ == '__main__':
    errors = validate(Path(__file__).resolve().parents[1]/'data')
    for error in errors: print('ERROR:',error)
    print('Daily freshness:', 'FAIL' if errors else 'PASS')
    raise SystemExit(bool(errors))
