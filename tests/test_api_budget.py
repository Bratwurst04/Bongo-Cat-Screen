"""Persistent/local budget checks. No HTTP or personal profiles."""
import concurrent.futures
import datetime as dt
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "companion"))
from api_budget import ApiBudget, BudgetWait, FileBudgetStore, MemoryBudgetStore, _new_state, settings


class Clock:
    def __init__(self, wall=None, mono=1000):
        self.wall_value = wall if wall is not None else dt.datetime(2026,10,14,10,tzinfo=dt.timezone.utc).timestamp()
        self.mono_value = mono
    def wall(self): return self.wall_value
    def mono(self): return self.mono_value
    def advance(self, seconds): self.wall_value += seconds; self.mono_value += seconds


class BudgetTests(unittest.TestCase):
    def memory(self, values=None, complete=True, clock=None):
        clock = clock or Clock()
        state = _new_state(clock.wall(), clock.mono())
        if complete: state["warm_until"] = 0
        store = MemoryBudgetStore(state)
        budget = ApiBudget(Path("unused"), values, store=store, wall=clock.wall, monotonic=clock.mono)
        return budget, clock, store

    def file(self, clock=None):
        folder = tempfile.TemporaryDirectory(dir=ROOT); self.addCleanup(folder.cleanup)
        clock = clock or Clock()
        path = Path(folder.name)/"budget.json"
        state = _new_state(clock.wall(),clock.mono()); state["warm_until"] = 0
        path.write_text(json.dumps(state))
        return ApiBudget(path, wall=clock.wall,monotonic=clock.mono), clock, path

    def test_day_night_idle_and_wrapping_night_profile(self):
        budget, clock, _ = self.memory()
        self.assertEqual(budget.view()["interval_seconds"],5)
        self.assertEqual(budget.view(True)["interval_seconds"],15)
        clock.advance(12*3600) # 00:00 Stockholm
        self.assertEqual(budget.view()["profile"],"night")
        self.assertEqual(budget.view()["interval_seconds"],30)
        self.assertEqual(budget.view(True)["interval_seconds"],60)
        budget.configure({"api_budget_night_start_hour":23,"api_budget_night_end_hour":7})
        self.assertEqual(budget.view()["profile"],"night")

    def test_first_unknown_day_is_half_budget_without_fast(self):
        budget,clock,_=self.memory(complete=False)
        budget.notify_activity();budget.admit()
        view=budget.view()
        self.assertEqual(view["long_total_limit"],4000)
        self.assertEqual(view["interval_seconds"],5)
        self.assertFalse(view["fast_active"])
        clock.advance(86400)
        self.assertTrue(budget.view()["history_complete"])

    def test_single_fast_period_is_not_extended_by_continuous_activity(self):
        budget,clock,store=self.memory()
        budget.notify_activity()
        for _ in range(10):
            budget.admit(); clock.advance(0.5);budget.notify_activity()
        with self.assertRaises(BudgetWait):budget.admit()
        self.assertEqual(len(store.state["fast"]),10)
        self.assertFalse(budget.view()["fast_active"])
        clock.advance(295);budget.notify_activity();budget.admit()
        self.assertEqual(len(store.state["fast"]),11)

    def test_activity_from_old_windows_session_does_not_arm_later(self):
        budget,clock,_=self.memory()
        budget.notify_activity();clock.advance(60);budget.admit()
        self.assertFalse(budget.view()["fast_active"])

    def test_no_activity_and_27_automatic_changes_cannot_arm_fast(self):
        budget,clock,store=self.memory()
        for _ in range(27):budget.admit();clock.advance(180)
        self.assertFalse(store.state["fast"])

    def test_explicit_uses_free_total_not_a_fixed_six(self):
        budget,clock,store=self.memory()
        for _ in range(8):
            grant=budget.begin_operation("control")
            budget.admit(operation=grant);clock.advance(0.5)
            budget.admit(operation=grant);clock.advance(0.5)
            budget.finish_operation(grant)
        self.assertEqual(len(store.state["short"]),16)
        self.assertEqual(budget.view()["short_auto_used"],0)

    def test_grants_reserve_future_cost_and_release_or_expire(self):
        budget,clock,_=self.memory()
        grants=[budget.begin_operation("control") for _ in range(8)]
        with self.assertRaises(BudgetWait):budget.admit()
        self.assertEqual(budget.view()["reserved"],24)
        budget.finish_operation(grants[0]);budget.admit()
        self.assertEqual(budget.view()["reserved"],21)
        clock.advance(11)
        self.assertEqual(budget.view()["reserved"],0)
        with self.assertRaises(BudgetWait):budget.admit(operation=grants[1])

    def test_auto_short_and_total_limits_hold_at_boundary(self):
        budget,clock,store=self.memory({"api_budget_day_playing_seconds":0.5})
        for _ in range(18):budget.admit();clock.advance(0.5)
        with self.assertRaises(BudgetWait):budget.admit()
        grant=budget.begin_operation("control")
        for _ in range(3):budget.admit(operation=grant);clock.advance(0.5)
        budget.finish_operation(grant)
        self.assertEqual(len(store.state["short"]),21)
        clock.advance(19.5)
        budget.admit()
        self.assertLessEqual(budget.view()["short_auto_used"],18)

    def test_whole_minute_expiry_does_not_free_a_partial_24h_window(self):
        budget,clock,store=self.memory({"api_budget_long_total":100,"api_budget_long_auto":90})
        now=clock.wall()
        bucket=int(now//60)*60
        store.state["minutes"]=[[bucket,90,0]]
        with self.assertRaises(BudgetWait):budget.admit()
        clock.advance(86400-1)
        with self.assertRaises(BudgetWait):budget.admit()
        clock.advance(61)
        budget.admit()

    def test_tail_spreads_remaining_capacity_before_hard_exhaustion(self):
        budget,clock,store=self.memory()
        old=int((clock.wall()-16*3600)//60)*60
        store.state['minutes']=[[old,5760,0]]
        self.assertGreater(budget.view()['interval_seconds'],15)
        budget.admit()
        self.assertLess(budget.view()['long_auto_used'],7200)
        # Genuine exhaustion still defers to conservative expiry; it is not
        # replaced by a fake maximum poll interval for nicer latency figures.
        store.state['minutes']=[[old,7200,0]]
        with self.assertRaises(BudgetWait):budget.admit()

    def test_lower_settings_and_reset_do_not_delete_spent_or_retry(self):
        budget,clock,store=self.memory()
        budget.admit();budget.note_retry(100,True)
        budget.configure({"api_budget_long_total":100,"api_budget_long_auto":90})
        self.assertEqual(budget.view()["long_used"],1)
        with self.assertRaises(BudgetWait):budget.begin_operation("control")
        clock.advance(101)
        self.assertTrue(budget.view()["quota_recovery"])
        self.assertEqual(budget.view()["interval_seconds"],5)
        self.assertEqual(budget.view()["long_total_limit"],50)

    def test_forward_and_backward_clock_keep_retry_in_monotonic_time(self):
        for direction in (-1,1):
            budget,clock,_=self.memory()
            budget.note_retry(100)
            clock.wall_value += direction*3600;clock.mono_value +=1
            self.assertGreaterEqual(budget.view()["retry_remaining_seconds"],99)
            with self.assertRaises(BudgetWait):budget.admit()
            self.assertGreater(budget.view()["clock_guard_remaining_seconds"],0)

    def test_restart_uncertain_clock_never_erases_spent_or_future_retry(self):
        budget,clock,path=self.file()
        budget.admit();budget.note_retry(100)
        clock.wall_value +=86400;clock.mono_value=2 # reboot or bad UTC continuity
        other=ApiBudget(path,wall=clock.wall,monotonic=clock.mono)
        self.assertEqual(other.view()["long_used"],1)
        self.assertGreaterEqual(other.view()["retry_remaining_seconds"],100)
        with self.assertRaises(BudgetWait):other.admit()
        self.assertGreater(other.view()["clock_guard_remaining_seconds"],0)

    def test_normal_restart_sleep_and_dst_do_not_reset_counts(self):
        wall=dt.datetime(2026,10,25,0,20,tzinfo=dt.timezone.utc).timestamp()
        budget,clock,path=self.file(Clock(wall))
        budget.admit();clock.advance(3600)
        other=ApiBudget(path,wall=clock.wall,monotonic=clock.mono)
        self.assertEqual(other.view()["profile"],"night") # same local 02:20 after fall-back
        self.assertEqual(other.view()["long_used"],1)
        other.admit()
        self.assertEqual(other.view()["long_used"],2)

    def test_corrupt_file_and_failed_atomic_write_are_fail_closed(self):
        budget,_,path=self.file()
        path.write_text('{"version":1,"secret":"bad"}')
        before=path.read_bytes()
        with self.assertRaises(BudgetWait):budget.admit()
        self.assertEqual(path.read_bytes(),before)
        budget,_,path=self.file()
        with patch("api_budget.os.replace",side_effect=OSError("fixture")):
            with self.assertRaises(BudgetWait):budget.admit()
        self.assertEqual(json.loads(path.read_text())["minutes"],[])

    def test_parallel_instances_cannot_overbook_shared_reservations(self):
        budget,clock,path=self.file()
        others=[ApiBudget(path,wall=clock.wall,monotonic=clock.mono) for _ in range(10)]
        def reserve(client):
            try:return client.begin_operation("control")
            except BudgetWait:return None
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as pool:
            grants=list(pool.map(reserve,others))
        self.assertEqual(sum(g is not None for g in grants),8)
        self.assertEqual(budget.view()["reserved"],24)
        self.assertEqual(budget.view()["long_used"],0)

    def test_numeric_file_has_no_media_or_credentials(self):
        budget,_,path=self.file();budget.admit()
        def numbers(value):
            if isinstance(value,dict):return all(numbers(v) for v in value.values())
            if isinstance(value,list):return all(numbers(v) for v in value)
            return type(value) in (int,float)
        self.assertTrue(numbers(json.loads(path.read_text())))
        self.assertLess(path.stat().st_size,256*1024)

    def test_field_validation_is_strict_and_old_fields_are_ignored(self):
        self.assertEqual(settings({"api_min_interval_seconds":1.5})["api_budget_day_playing_seconds"],5)
        for values in ({"api_budget_short_total":True},{"api_budget_day_playing_seconds":float("nan")},
                       {"api_budget_short_auto":24},{"api_budget_night_start_hour":8},
                       {"api_budget_timezone":"invalid/fixture"},{"api_budget_long_auto":8000}):
            with self.assertRaises((ValueError,KeyError)):settings(values)


if __name__=="__main__":unittest.main()
