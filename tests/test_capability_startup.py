"""One-shot recovery after readiness, with real reader/initial-sync paths."""
from threading import Event,Lock,Thread
import unittest
from unittest.mock import Mock,patch
import test_artwork_v2 as legacy

TOKEN='0123456789ABCDEF'
NEXT='FEDCBA9876543210'
VALUES={'HEAP':154356,'HEAP_TOTAL':261112,'MIN_HEAP':153444,'UPTIME':19}
STATUS=b'ESP32_STATUS:HEAP:154356,HEAP_TOTAL:261112,MIN_HEAP:153444,UPTIME:19\n'


class ObservedLock:
    def __init__(self):self.lock=Lock();self.entered=Event()
    def __enter__(self):self.entered.set();self.lock.acquire();return self
    def __exit__(self,*args):self.lock.release()
    def acquire(self,*args,**kwargs):return self.lock.acquire(*args,**kwargs)
    def release(self):self.lock.release()


class CapabilityStartupTests(unittest.TestCase):
    def engine(self):
        e=legacy.ArtworkV2Tests().make_engine();e.baudrate=921600;e._data_lock=Lock()
        e._artwork_v2_challenge=TOKEN;e._artwork_v2_fast_challenge='';e._artwork_v2_compact_challenge=''
        e._capability_fallback=(e.serial_conn,e._artwork_v2_epoch,TOKEN)
        e.media_bridge=Mock();return e

    def query(self,e,conn=None,context=None,values=None):
        e._retry_capability_after_status(conn or e.serial_conn,
            context if context is not None else e._capability_fallback,VALUES if values is None else values)

    def test_one_same_challenge_query_preserves_media_epoch_cache_and_old_peer_gating(self):
        e=self.engine();context=e._capability_fallback;cached=bytes(37632)
        e._cached_artwork=cached;e._artwork_v2_pending_id=42;e._artwork_retry=('cached-retry',)
        for _ in range(3):self.query(e,context=context)
        e.serial_conn.write.assert_called_once_with(f'CAPS?:{TOKEN}\n'.encode())
        self.assertIsNone(e._capability_fallback);self.assertEqual(e._artwork_v2_epoch,0)
        self.assertIs(e._cached_artwork,cached);self.assertEqual(e._artwork_v2_pending_id,42)
        self.assertEqual(e._artwork_retry,('cached-retry',));self.assertFalse(e._artwork_v2_supported)
        self.assertEqual(e._artwork_v2_compact_challenge,'');e.media_bridge.control.assert_not_called()

    def test_invalid_status_does_not_consume_the_one_shot(self):
        e=self.engine();context=e._capability_fallback
        cases=[{},dict(VALUES,HEAP=-1),dict(VALUES,HEAP_TOTAL=0),dict(VALUES,MIN_HEAP=200000),
               dict(VALUES,UPTIME=-1),dict(VALUES,UPTIME=0x100000000),dict(VALUES,HEAP=True)]
        for values in cases:self.query(e,context=context,values=values)
        e.serial_conn.write.assert_not_called();self.assertIs(e._capability_fallback,context)
        self.query(e,context=context);self.assertEqual(e.serial_conn.write.call_count,1)

    def test_whole_compact_capability_is_required_to_skip_resend(self):
        for base,compact,refine in [(b,c,r) for b in (False,True) for c in (False,True) for r in (False,True)]:
            e=self.engine();e._artwork_v2_supported=base
            e._artwork_v2_compact_challenge=TOKEN if compact else ''
            e._artwork_v2_refine_challenge=TOKEN if refine else ''
            self.query(e)
            self.assertEqual(e.serial_conn.write.call_count,0 if base and compact and refine else 1)
            self.assertIsNone(e._capability_fallback)

    def test_old_connection_epoch_challenge_and_context_cannot_target_a_new_handle(self):
        e=self.engine();old=e.serial_conn;previous=e._capability_fallback
        current=Mock(is_open=True);current.write.side_effect=lambda p:len(p)
        e.serial_conn=current;e._artwork_v2_epoch=1;e._artwork_v2_challenge=NEXT
        fresh=(current,1,NEXT);e._capability_fallback=fresh
        for context,conn in [(previous,old),((current,0,NEXT),current),((current,1,TOKEN),current),((current,1,NEXT),current)]:
            self.query(e,conn,context)
        old.write.assert_not_called();current.write.assert_not_called()
        self.assertIs(e._capability_fallback,fresh)
        self.query(e,current,fresh);current.write.assert_called_once_with(f'CAPS?:{NEXT}\n'.encode())

    def test_reader_captures_context_before_blocking_read_and_writes_outside_data_lock(self):
        e=self.engine();conn=e.serial_conn;count=0
        def read():
            nonlocal count
            count+=1
            if count==1:
                e._artwork_v2_epoch=1;e._artwork_v2_challenge=NEXT
                e._capability_fallback=(conn,1,NEXT)
            else:self.assertEqual(conn.write.call_count,0)
            return STATUS
        def write(p):
            self.assertTrue(e._data_lock.acquire(blocking=False));e._data_lock.release()
            self.assertEqual(count,2);e.running=False;return len(p)
        conn.readline.side_effect=read;conn.write.side_effect=write
        with patch('engine.diagnostics.event'):e._serial_reader_loop()
        conn.write.assert_called_once_with(f'CAPS?:{NEXT}\n'.encode())

    def test_resync_and_reconnect_rearm_only_the_new_generation(self):
        e=self.engine();e.get_system_stats=Mock(return_value=(1,2));e._last_media_snapshot=None
        with patch('engine.secrets.token_hex',side_effect=['0123456789abcdef','fedcba9876543210','abcd1234abcd1234']),\
             patch('engine.time.sleep'),patch('engine.diagnostics.event'),patch('builtins.print'):
            e.send_initial_sync();first=e._capability_fallback;self.query(e,context=first)
            e._resync_device();second=e._capability_fallback
            self.assertNotEqual(first[1:],second[1:]);self.query(e,context=first)
            self.assertIs(e._capability_fallback,second);self.query(e,context=second)
            old=e.serial_conn;e.serial_conn=None;e.port='FAKE_PORT';e._auto_port=False;e._next_reconnect_at=0
            e._reconnect_attempts=0;e._last_device_reply_at=0
            reopened=Mock(is_open=True);reopened.write.side_effect=lambda p:len(p)
            with patch('engine.serial.Serial',return_value=reopened):e._attempt_reconnect()
            third=e._capability_fallback;self.assertIs(third[0],reopened)
            self.query(e,old,second);self.assertIs(e._capability_fallback,third)
            self.query(e,reopened,third)
        self.assertEqual(sum(p.args[0].startswith(b'CAPS?:') for p in reopened.write.call_args_list),2)

    def test_shutdown_while_waiting_for_serial_lock_prevents_write(self):
        e=self.engine();gate=ObservedLock();gate.lock.acquire();e._serial_lock=gate
        worker=Thread(target=self.query,args=(e,),daemon=True);worker.start()
        self.assertTrue(gate.entered.wait(1));e._stop_requested.set();gate.lock.release();worker.join(1)
        self.assertFalse(worker.is_alive());e.serial_conn.write.assert_not_called()
        self.assertIsNone(e._capability_fallback)

    def test_partial_query_retires_handle_after_releasing_lock(self):
        e=self.engine();conn=e.serial_conn;conn.write.side_effect=lambda p:len(p)-1
        with patch('engine.diagnostics.event'),patch('builtins.print'):
            self.query(e)
        self.assertIsNone(e.serial_conn);conn.close.assert_called_once_with()
        self.assertIsNone(e._capability_fallback)

    def test_reader_recovers_missing_base_cap_and_never_repeats_for_old_peer(self):
        for compact_peer in (False,True):
            e=self.engine();e.baudrate=921600 if compact_peer else 230400
            replies=[STATUS];queries=[]
            def write(p):
                queries.append(p);replies.append(f'CAPS:MEDIA_ART2:{TOKEN}\n'.encode())
                if compact_peer:replies.append(f'CAPS:MEDIA_ART2_RGB56580:{TOKEN}:921600\n'.encode())
                replies.append(STATUS);return len(p)
            def read():
                result=replies.pop(0)
                if not replies and len(queries):e.running=False
                return result
            e.serial_conn.write.side_effect=write;e.serial_conn.readline.side_effect=read
            original=e._retry_capability_after_status
            def status(conn,context,values):
                original(conn,context,values)
                if len(queries) and context is None:e.running=False
            e._retry_capability_after_status=status
            with patch('engine.diagnostics.event'):e._serial_reader_loop()
            self.assertEqual(queries,[f'CAPS?:{TOKEN}\n'.encode()]);self.assertTrue(e._artwork_v2_supported)
            self.assertEqual(e._artwork_v2_compact_challenge,TOKEN if compact_peer else '')


if __name__=='__main__':unittest.main()
