"""Execute render_grid.JS with controlled DOM/media events and promise ordering."""
from pathlib import Path
import json
import shutil
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import render_grid

NODE = shutil.which("node")
HARNESS = Path(__file__).with_name("daily_interactions_harness.cjs")


@unittest.skipUnless(NODE, "Node.js is required for the executable UI regressions")
class DailyInteractionsTests(unittest.TestCase):
    def run_scenario(self, name):
        result = subprocess.run([NODE, str(HARNESS)], input=json.dumps({"script": render_grid.JS, "scenario": name}, ensure_ascii=True),
                                capture_output=True, text=True, encoding="utf-8", timeout=20, cwd=ROOT)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(json.loads(result.stdout)["status"], "PASS")


SCENARIOS = (
    "old_source_failure_and_events_cannot_touch_b",
    "old_source_success_cannot_clear_b_pending_state",
    "an_old_attempt_on_the_same_source_cannot_settle_a_new_attempt",
    "pause_pending_ignores_late_success_playing_waiting_and_error",
    "pause_also_cancels_a_queued_ended_event",
    "a_natural_end_still_advances_to_the_next_visible_track",
    "resume_policy_rejection_is_handled_and_retry_works",
    "resume_network_rejection_automatically_moves_to_b",
    "broken_sources_have_a_six_attempt_cap_and_manual_retry",
    "duplicate_media_error_and_rejection_only_skip_once",
    "automatic_skip_obeys_current_search_and_favorites",
    "search_favorites_empty_state_and_exports_stay_in_sync",
    "bad_storage_types_do_not_crash_or_pollute_export",
    "unavailable_storage_keeps_current_page_favorites_and_copy_fallback",
    "keyboard_on_native_controls_never_triggers_global_playback",
    "copy_exports_exact_current_text_and_restores_button_label",
)

for scenario in SCENARIOS:
    def test(self, name=scenario):
        self.run_scenario(name)
    setattr(DailyInteractionsTests, "test_" + scenario, test)


if __name__ == "__main__":
    unittest.main(verbosity=2)
