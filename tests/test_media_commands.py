"""Normal media commands, neutral track identity and retired-input rejection."""
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'companion'))
from media_bridge import MediaSnapshot, WindowsMediaBridge
from media_commands import MEDIA_ACTIONS, media_track_context_id, parse_media_command

class MediaCommandTests(unittest.TestCase):
    def test_only_normal_commands_parse_and_legacy_frames_never_reach_control(self):
        import test_artwork_v2
        self.assertEqual(MEDIA_ACTIONS, {'PLAY_PAUSE', 'NEXT', 'PREVIOUS'})
        retired = ['MEDIA_CMD:SEEK:+15:123', 'MEDIA_CMD:SEEK:-15:123',
                   'MEDIA_CMD:SEEK:+15', 'MEDIA_CMD:seek:-15',
                   'MEDIA_CMD:NEXT:123', 'MEDIA_CMD:PLAY_PAUSE\nNEXT']
        for line in retired:
            self.assertIsNone(parse_media_command(line))
        engine = test_artwork_v2.ArtworkV2Tests().make_engine()
        engine.media_bridge = Mock()
        lines = iter([(line + '\n').encode() for line in retired[:4]] +
                     [b'MEDIA_CMD:PLAY_PAUSE\n', b'MEDIA_CMD:PREVIOUS\n', b'MEDIA_CMD:NEXT\n'])
        def read():
            line = next(lines)
            if line == b'MEDIA_CMD:NEXT\n':engine.running = False
            return line
        engine.serial_conn.readline.side_effect = read
        with patch('engine.diagnostics.event'), patch('builtins.print'):
            engine._serial_reader_loop()
        self.assertEqual([call.args for call in engine.media_bridge.control.call_args_list],
                         [('PLAY_PAUSE',), ('PREVIOUS',), ('NEXT',)])

    def test_retired_direct_controls_cannot_queue_reserve_or_call_spotify_or_windows(self):
        import test_api_budget_integration as integration
        fixture = integration.IntegrationTests()
        self.addCleanup(fixture.doCleanups)
        fixture.setUp()
        bridge = fixture.bridge()
        before = fixture.budget.view()
        for source in ('spotify_api', 'windows_spotify'):
            bridge._current_source = source
            for action in ('SEEK:+15', 'SEEK:-15', 'SEEK:+15:123', 'SEEK:-15:123'):
                self.assertFalse(bridge.control(action))
            self.assertTrue(bridge._commands.empty())
            self.assertFalse(bridge._control_requests)
        self.assertEqual(len(fixture.calls), 1)  # Initial authoritative snapshot only.
        after = fixture.budget.view()
        for key in ('long_used', 'long_auto_used', 'reserved'):
            self.assertEqual(before[key], after[key])
        self.assertFalse(hasattr(fixture.api, 'seek_relative'))
        self.assertFalse(hasattr(fixture.api, 'get_seek_context'))
        self.assertFalse(hasattr(bridge, '_seek_windows'))

    def test_legacy_budget_grants_remain_readable_but_cannot_be_created(self):
        import test_api_budget as budget_tests
        from api_budget import _validate
        fixture = budget_tests.BudgetTests()
        budget, clock, store = fixture.memory()
        state = store.state
        state['grants'] = [[1, state['logical'] + 10, 4, 2]]
        state['next_grant'] = 2
        _validate(state)  # Existing ledger schema, including retired grant tag.
        self.assertEqual(budget.view()['reserved'], 4)
        with self.assertRaises(ValueError):budget.begin_operation('seek')
        self.assertEqual(budget.view()['reserved'], 4)

    def test_neutral_context_parser_preserves_flip_and_aborts_old_transfer_only_on_change(self):
        from record_flip_host import load_host
        host = load_host()
        host.rf_fw_reset()
        self.assertTrue(host.rf_fw_track_context(b'101', 3, 10))
        self.assertEqual(host.rf_fw_context_aborts(), 0)
        self.assertTrue(host.rf_fw_receiving())
        for value in (b'', b'0123', b'-1', b'4294967296', b'1:2'):
            self.assertFalse(host.rf_fw_track_context(value, len(value), 20))
        self.assertEqual(host.rf_fw_context_aborts(), 0)
        self.assertTrue(host.rf_fw_track_context(b'102', 3, 30))
        self.assertEqual(host.rf_fw_context_aborts(), 1)
        self.assertFalse(host.rf_fw_receiving())
        self.assertTrue(host.rf_fw_track_context(b'102', 3, 40))
        self.assertEqual(host.rf_fw_context_aborts(), 1)
        self.assertTrue(host.rf_fw_track_context(b'4294967295', 10, 50))
        self.assertTrue(host.rf_fw_track_context(b'0', 1, 60))

    def test_actual_firmware_media_route_and_tap_grouping_use_normal_controls(self):
        from record_flip_host import load_host
        host = load_host()
        self.assertEqual(host.rf_touch(0, 0, 0), 3)  # Tap.
        self.assertEqual(host.rf_touch(0, 420, 0), 1)  # NEXT.
        self.assertEqual(host.rf_touch(0, -420, 0), 2)  # PREVIOUS.
        self.assertEqual(host.rf_touch(420, 0, 0), 4)  # DJ toggle.
        self.assertEqual(host.rf_touch(0, 0, 1), 5)  # Visible local focus timer.
        self.assertEqual(host.rf_touch(0, 419, 0), 3)
        self.assertEqual([host.rf_taps(count, 0, 0) for count in (1, 2, 3)], [3, 1, 2])
        self.assertEqual(host.rf_taps(1, 1, 0), 0)  # Held touch may become long press.
        self.assertEqual(host.rf_taps(1, 0, 1), 0)  # Menu owns touch.

    def test_fresh_position_updates_existing_media_time(self):
        import test_artwork_v2
        engine = test_artwork_v2.ArtworkV2Tests().make_engine()
        first = MediaSnapshot(available=True, source="SPOTIFY", title="Song", artist="Artist",
                              track_key="same", playing=False, position_seconds=30, duration_seconds=180)
        engine._on_media_update(first, None)
        engine.serial_conn.write.reset_mock()
        confirmed = MediaSnapshot(**{**first.__dict__, "position_seconds": 45})
        engine._on_media_update(confirmed, None)
        self.assertIn(b"MEDIA_TIME:45:180\n", engine.serial_conn.write.call_args.args[0])
        self.assertEqual(engine._last_media_time, (45, 180))
        self.assertTrue(engine._artwork_queue.empty())

    def test_context_is_sent_only_on_track_source_change_or_resync(self):
        import test_artwork_v2
        engine = test_artwork_v2.ArtworkV2Tests().make_engine()
        snap = MediaSnapshot(available=True, source="SPOTIFY API", track_key="song", duration_seconds=180)
        engine._on_media_update(snap, None)
        context = media_track_context_id(snap.source, snap.track_key)
        self.assertIn(f"MEDIA_TRACK_CONTEXT:{context}\n".encode(), engine.serial_conn.write.call_args.args[0])
        engine.serial_conn.write.reset_mock()
        engine._last_media_full_sync = -100 # force existing regular metadata refresh
        engine._on_media_update(snap, None)
        self.assertNotIn(b"MEDIA_TRACK_CONTEXT:", engine.serial_conn.write.call_args.args[0])
        changed = MediaSnapshot(**{**snap.__dict__, "source":"SPOTIFY"})
        engine._on_media_update(changed, None)
        self.assertIn(f"MEDIA_TRACK_CONTEXT:{media_track_context_id(changed.source, changed.track_key)}\n".encode(), engine.serial_conn.write.call_args.args[0])
        engine.send_initial_sync = Mock()
        engine.serial_conn.write.reset_mock()
        engine._resync_device()
        self.assertEqual(engine._last_media_track_context_id, media_track_context_id(changed.source, changed.track_key))
        self.assertIn(b"MEDIA_TRACK_CONTEXT:", engine.serial_conn.write.call_args.args[0])

    def test_deferred_metadata_keeps_old_id_and_context_is_final_bundle_marker(self):
        import test_artwork_v2
        engine = test_artwork_v2.ArtworkV2Tests().make_engine()
        old = MediaSnapshot(available=True, source="SPOTIFY", title="Old", artist="Artist",
                            track_key="old", duration_seconds=180)
        new = MediaSnapshot(available=True, source="SPOTIFY API", title="New", artist="New Artist",
                            track_key="new", duration_seconds=200, position_seconds=10)
        engine._on_media_update(old, None)
        old_id = engine._last_media_track_context_id
        engine._write_media_payload = Mock(return_value=False)
        engine._on_media_update(new, None)
        self.assertEqual(engine._last_media_track_context_id, old_id)
        self.assertEqual(engine._last_media_snapshot, new)
        payload = engine._write_media_payload.call_args.args[0].decode().splitlines()
        marker = f"MEDIA_TRACK_CONTEXT:{media_track_context_id(new.source, new.track_key)}"
        self.assertEqual(payload[-1], marker)
        for field in ("MEDIA_TITLE:New", "MEDIA_ARTIST:New Artist", "MEDIA_TIME:10:200", "MEDIA_ART_DEFAULT"):
            self.assertLess(payload.index(field), payload.index(marker))
        engine._write_media_payload.return_value = True
        engine._on_media_update(new, None)
        self.assertEqual(engine._last_media_track_context_id, media_track_context_id(new.source, new.track_key))
        self.assertEqual(engine._write_media_payload.call_args.args[0].decode().splitlines()[-1], marker)

