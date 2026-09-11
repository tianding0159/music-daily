"""Regression for exhausted catalog recycling, identity changes and build idempotency."""
import contextlib
import copy
import datetime as dt
import hashlib
import io
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import picker
import build_daily as daily
import check_daily_freshness as guard


def track(i, **changes):
    value = {'id': str(i), 'artist': 'Artist '+str(i), 'title': 'Song '+str(i),
             'album': 'Album '+str(i), 'has_melody': True, 'genres': ['indie pop'],
             'fit_score': 80, 'mood_tags': ['warm']}
    value.update(changes)
    return value


class FreshSelectionTests(unittest.TestCase):
    def test_never_recycles_exhausted_high_scoring_tracks(self):
        pool = [track(1, fit_score=100), track(2, fit_score=40)]
        history = {'2020-01-01': ['1']}
        history.update({f'2026-07-{n:02}': [] for n in range(1, 30)})
        self.assertEqual([t['id'] for t in picker.select_daily(pool, history, '2026-09-12', 30, recency_days=1)], ['2'])
        self.assertEqual(picker.select_daily(pool, {'2020-01-01':['1','2']}, '2026-09-12'), [])

    def test_new_id_old_alias_or_same_work_cannot_bypass_history(self):
        old = track('old', artist='Björk', title='Jóga')
        variants = [track('new', artist='Bjork', title='Joga - 2025 Remaster'),
                    track('alias', legacy_ids=['old'])]
        self.assertEqual(picker.select_daily(variants, {'2020-01-01':['old']}, '2026-09-12', history_tracks=[old]), [])

    def test_work_dedup_does_not_confuse_different_artists(self):
        old = track('old', title='Home', artist='A')
        new = track('new', title='Home', artist='B')
        self.assertEqual([t['id'] for t in picker.select_daily([old,new], {'2020':['old']}, '2026-09-12')], ['new'])

    def test_duplicate_works_only_appear_once_even_with_new_ids(self):
        a = track('a'); b = dict(a, id='b', title=a['title']+' - Remastered')
        self.assertEqual(len(picker.select_daily([a,b], {}, '2026-09-12')), 1)

    def test_pending_requires_explicit_status_and_never_fabricates_listening(self):
        pending = track('p', selection_status='discovery_not_curated')
        for field in ['has_melody','fit_score','mood_tags']: pending.pop(field)
        bad = dict(pending, id='bad', genres=['metal'])
        unverified = dict(pending, id='unknown'); unverified.pop('selection_status')
        result = picker.select_daily([], {}, '2026-09-12', discoveries=[pending,bad,unverified])
        self.assertEqual(result, [pending])
        self.assertNotIn('has_melody', result[0])
        self.assertFalse(picker.is_eligible(pending)[0])

    def test_real_inventory_over_a_month_has_no_repeated_work(self):
        pool = json.loads((ROOT/'data/pool.json').read_text(encoding='utf-8'))
        history = json.loads((ROOT/'data/history.json').read_text(encoding='utf-8'))
        discoveries = daily._random_catalog_items([])
        previous = daily._historical_tracks()
        seen = {picker.work_key(t) for t in previous}
        counts = []
        for day in range(34):
            date = str(dt.date(2026,9,12)+dt.timedelta(days=day))
            picks = picker.select_daily(pool,history,date,discoveries=discoveries,history_tracks=previous)
            works = {picker.work_key(t) for t in picks}
            self.assertEqual(len(works),len(picks))
            self.assertFalse(works & seen, date)
            history[date] = [t['id'] for t in picks]
            previous.extend(picks); seen.update(works); counts.append(len(picks))
        self.assertGreaterEqual(sum(counts), 900)
        self.assertTrue(all(n == 30 for n in counts[:30]), counts)


class DailyBuildTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.data = self.root/'data'; shutil.copytree(ROOT/'data', self.data)
        self.site = self.root/'site'; self.site.mkdir()
        for name,value in [('DATA',self.data),('SITE',self.site),('ISSUES',self.data/'issues'),('MEDIA',self.data/'pool_media.json')]:
            obj=patch.object(daily,name,value); obj.start(); self.addCleanup(obj.stop)

    def run_daily(self, *args):
        with patch.object(sys,'argv',['build_daily.py',*args]), contextlib.redirect_stdout(io.StringIO()), \
                patch.object(daily.itunes,'lookup',side_effect=AssertionError('offline')), \
                patch.object(daily.push_wechat,'push',side_effect=AssertionError('no messages')):
            daily.main()

    def test_new_day_never_repeats_and_retries_preserve_snapshot_and_notified(self):
        history = json.loads((self.data/'history.json').read_text(encoding='utf-8'))
        self.run_daily('--date','2026-09-12','--no-itunes')
        snap_path=self.data/'issues/2026-09-12.json'
        saved=snap_path.read_bytes(); snap=json.loads(saved)
        self.assertEqual(len(snap['tracks']),30)
        self.assertFalse({t['id'] for t in snap['tracks']} & {i for ids in history.values() for i in ids})
        self.assertTrue(all(t.get('_preview') for t in snap['tracks']))
        self.assertTrue(all('has_melody' not in t for t in snap['tracks']))
        latest=json.loads((self.data/'latest.json').read_text(encoding='utf-8')); latest['notified']='2026-09-12'
        (self.data/'latest.json').write_text(json.dumps(latest),encoding='utf-8')
        self.run_daily('--date','2026-09-12','--no-itunes')
        self.assertEqual(saved,snap_path.read_bytes())
        self.assertEqual(json.loads((self.data/'latest.json').read_text(encoding='utf-8'))['notified'],'2026-09-12')
        current=(self.site/'daily.html').read_text(encoding='utf-8')
        classic=(self.site/'legacy/daily.html').read_text(encoding='utf-8')
        self.assertIn('legacy/daily.html',current)
        self.assertIn('返回新版',classic)
        for t in snap['tracks']:
            import html
            self.assertIn(html.escape(t['title']), current)
            self.assertIn(html.escape(t['title']), classic)
        self.assertEqual((self.site/'pool.min.json').read_bytes(),(self.site/'legacy/pool.min.json').read_bytes())

    def test_missing_history_uses_saved_snapshots_as_repeat_evidence(self):
        combined=daily._complete_history({})
        self.assertTrue(combined)
        records=daily._historical_tracks()
        self.assertFalse(picker.unsent_tracks(records,combined,records))

    def test_force_rebuild_remembers_every_superseded_recommendation(self):
        self.run_daily('--date','2026-09-12','--no-itunes')
        path = self.data/'issues/2026-09-12.json'
        original = json.loads(path.read_text(encoding='utf-8'))['tracks']
        self.run_daily('--date','2026-09-12','--force-rebuild','--no-itunes')
        replacement = json.loads(path.read_text(encoding='utf-8'))
        self.assertEqual(replacement['superseded_tracks'], original)
        self.assertFalse({t['id'] for t in original} & {t['id'] for t in replacement['tracks']})
        self.assertFalse(picker.unsent_tracks(original,daily._complete_history({}),daily._historical_tracks()))
        self.assertEqual(guard.validate(self.data), [])
        self.run_daily('--date','2026-09-13','--no-itunes')
        self.assertEqual(guard.validate(self.data), [])

    def test_publish_guard_rejects_renamed_id_repeating_an_old_work(self):
        previous = json.loads((self.data/'issues/2026-09-10.json').read_text(encoding='utf-8'))['tracks'][0]
        variant = dict(previous,id='new-store-id',title=previous['title']+' - Remastered')
        snap = {'date':'2026-09-12','tracks':[variant], 'selection_policy':'never_repeat_v1'}
        (self.data/'issues/2026-09-12.json').write_text(json.dumps(snap),encoding='utf-8')
        history = json.loads((self.data/'history.json').read_text(encoding='utf-8'))
        history['2026-09-12'] = ['new-store-id']
        (self.data/'history.json').write_text(json.dumps(history),encoding='utf-8')
        self.assertTrue(any('already recommended' in e for e in guard.validate(self.data)))

    def test_publish_guard_rejects_duplicates_inside_an_issue(self):
        a = track('test-a'); b = dict(a,id='test-b')
        snap = {'date':'2026-09-12','tracks':[a,b], 'selection_policy':'never_repeat_v1'}
        (self.data/'issues/2026-09-12.json').write_text(json.dumps(snap),encoding='utf-8')
        self.assertTrue(any('duplicate works' in e for e in guard.validate(self.data)))

    def test_exhaustion_does_not_write_a_fake_or_repeat_issue(self):
        (self.data/'discovery.json').unlink()
        before={str(p.relative_to(self.data)):hashlib.sha256(p.read_bytes()).hexdigest() for p in self.data.rglob('*') if p.is_file()}
        with self.assertRaisesRegex(SystemExit,'耗尽'):
            self.run_daily('--date','2026-09-12','--no-itunes')
        after={str(p.relative_to(self.data)):hashlib.sha256(p.read_bytes()).hexdigest() for p in self.data.rglob('*') if p.is_file()}
        self.assertEqual(before,after)
        self.assertEqual(list(self.site.iterdir()),[])


if __name__ == '__main__': unittest.main(verbosity=2)
