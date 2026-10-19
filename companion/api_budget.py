"""Local, persistent Web API admission. No HTTP, credentials or media data."""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import copy
import datetime as dt
import json
import math
import os
from pathlib import Path
import tempfile
import threading
import time
import weakref
from zoneinfo import ZoneInfo

DAY = 86400.0
MAX_FILE_BYTES = 256 * 1024
DEFAULTS = {
    "api_budget_short_total": 24, "api_budget_short_auto": 18,
    "api_budget_long_total": 8000, "api_budget_long_auto": 7200,
    "api_budget_day_playing_seconds": 5.0, "api_budget_night_playing_seconds": 30.0,
    "api_budget_day_idle_seconds": 15.0, "api_budget_night_idle_seconds": 60.0,
    "api_budget_night_start_hour": 0, "api_budget_night_end_hour": 8,
    "api_budget_timezone": "Europe/Stockholm",
}


class BudgetWait(RuntimeError):
    def __init__(self, seconds: float, reason: str):
        self.wait_seconds = max(0.05, float(seconds))
        self.reason = reason
        super().__init__("Local API guard: " + reason)


def settings(values: dict) -> dict:
    result = {key: values.get(key, default) for key, default in DEFAULTS.items()}
    for key in DEFAULTS:
        value = result[key]
        if key == "api_budget_timezone":
            if not isinstance(value, str) or len(value) > 64:
                raise ValueError("Invalid API budget timezone")
            ZoneInfo(value)
            continue
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError("Invalid API budget number")
    for key in ("api_budget_short_total", "api_budget_short_auto", "api_budget_long_total",
                "api_budget_long_auto", "api_budget_night_start_hour", "api_budget_night_end_hour"):
        if int(result[key]) != result[key]:
            raise ValueError("API budget counts/hours must be integers")
        result[key] = int(result[key])
    if not 6 <= result["api_budget_short_total"] <= 120:
        raise ValueError("Invalid API short budget")
    if not 1 <= result["api_budget_short_auto"] < result["api_budget_short_total"]:
        raise ValueError("Invalid API automatic short budget")
    if not 100 <= result["api_budget_long_total"] <= 100000:
        raise ValueError("Invalid API long budget")
    if not 1 <= result["api_budget_long_auto"] < result["api_budget_long_total"]:
        raise ValueError("Invalid API automatic long budget")
    for key in ("api_budget_day_playing_seconds", "api_budget_night_playing_seconds"):
        if not 0.5 <= result[key] <= 300:
            raise ValueError("Invalid API playing profile")
    for key in ("api_budget_day_idle_seconds", "api_budget_night_idle_seconds"):
        if not 15 <= result[key] <= 600:
            raise ValueError("Invalid API idle profile")
    if not all(0 <= result[key] <= 23 for key in ("api_budget_night_start_hour", "api_budget_night_end_hour")):
        raise ValueError("Invalid API night hours")
    if result["api_budget_night_start_hour"] == result["api_budget_night_end_hour"]:
        raise ValueError("Night start and end must differ")
    return result


def _new_state(wall: float, mono: float) -> dict:
    return dict(version=1, wall=wall, mono=mono, logical=wall, warm_until=wall + DAY,
                retry_until=0.0, retry_reason=0, quota_strong=0.0, quota_soft=0.0, clock_guard=0.0,
                last_auto=-1.0e12, last_start=-1.0e12, last_burst=-1.0e12, burst_end=0.0,
                burst_polls=0, next_grant=1, short=[], minutes=[], fast=[], grants=[], pending=[])


def _validate(state: dict) -> None:
    expected = _new_state(0, 0)
    if not isinstance(state, dict) or set(state) != set(expected) or state.get("version") != 1:
        raise BudgetWait(60, "history_corrupt")
    for key, value in state.items():
        if key in ("short", "minutes", "fast", "grants", "pending"):
            continue
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or abs(value) > 1e13:
            raise BudgetWait(60, "history_corrupt")
    sizes = {"short": (128, 2), "minutes": (1441, 3), "fast": (120, 1), "grants": (16, 4), "pending": (1, 2)}
    for key, (maximum, width) in sizes.items():
        rows = state[key]
        if not isinstance(rows, list) or len(rows) > maximum:
            raise BudgetWait(60, "history_corrupt")
        for row in rows:
            values = [row] if width == 1 else row
            if not isinstance(values, list) or len(values) != width or any(
                isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or abs(v) > 1e13
                for v in values
            ):
                raise BudgetWait(60, "history_corrupt")
    if any(row[1] not in (0, 1) or row[0] > state["logical"] + 0.01 for row in state["short"]):
        raise BudgetWait(60, "history_corrupt")
    if any(any(v not in (0,1) for v in row) for row in state['pending']):
        raise BudgetWait(60, 'history_corrupt')
    if any(row[0] % 60 or row[0] > state["logical"] or
           any(v < 0 or int(v) != v or v > 100000 for v in row[1:]) for row in state["minutes"]):
        raise BudgetWait(60, "history_corrupt")
    if any(b[0] <= a[0] for a, b in zip(state["minutes"], state["minutes"][1:])):
        raise BudgetWait(60, "history_corrupt")
    if any(row[0] < 1 or row[2] < 1 or row[2] > 6 or row[3] not in (1, 2) for row in state["grants"]):
        raise BudgetWait(60, "history_corrupt")
    if (state["retry_reason"] not in (0, 1, 2) or state["next_grant"] < 1 or
            int(state["next_grant"]) != state["next_grant"] or
            len({r[0] for r in state["grants"]}) != len(state["grants"]) or
            any(r[0] >= state["next_grant"] for r in state["grants"])):
        raise BudgetWait(60, "history_corrupt")


_LOCKS = weakref.WeakValueDictionary()
_LOCKS_GUARD = threading.Lock()


class _ProfileState:
    def __init__(self):
        self.lock = threading.RLock()
        self.unsaved = None
        self.lock_failed = False


class FileBudgetStore:
    """Atomic per-profile transactions, including other API client instances."""
    def __init__(self, path: Path):
        self.path = Path(path)
        with _LOCKS_GUARD:
            key = str(self.path.resolve()).casefold()
            self._profile = _LOCKS.setdefault(key, _ProfileState())
            self.lock = self._profile.lock

    def read(self, factory):
        with self.lock:
            if self._profile.unsaved is not None:
                return copy.deepcopy(self._profile.unsaved)
            try:
                if not self.path.exists():
                    return factory()
                if self.path.stat().st_size > MAX_FILE_BYTES:
                    raise BudgetWait(60, "history_corrupt")
                value = json.loads(self.path.read_text(encoding="utf-8"))
                _validate(value)
                return value
            except BudgetWait:
                raise
            except (ValueError, TypeError):
                raise BudgetWait(60, "history_corrupt") from None
            except OSError:
                raise BudgetWait(60, "history_io") from None

    @contextmanager
    def _file_lock(self):
        # No serial/input thread enters this path. Never wait indefinitely for
        # another process, and never delete the shared lock file.
        if self._profile.lock_failed:
            raise BudgetWait(60, "history_io")
        handle = None
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            handle = open(str(self.path) + ".lock", "a+b")
            if handle.tell() == 0:
                handle.write(b"\0"); handle.flush()
            handle.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            if handle is not None:
                try: handle.close()
                except OSError: pass
            raise BudgetWait(1, "history_io") from None
        body_failed = False
        try:
            yield
        except BaseException:
            body_failed = True
            raise
        finally:
            # HTTPError/URLError are OSError subclasses: body errors must keep
            # their classification. An unlock failure guards future work.
            unlock_failed = False
            try:
                if os.name == "nt":
                    handle.seek(0); msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            except OSError:
                unlock_failed = True
            try: handle.close()
            except OSError: unlock_failed = True
            if unlock_failed:
                self._profile.lock_failed = True
                if not body_failed:
                    raise BudgetWait(60, "history_io") from None

    def update(self, factory, function):
        with self.lock, self._file_lock():
            state = self.read(factory)
            if self._profile.unsaved is not None:
                self.save(state)
                self._profile.unsaved = None
            failure = None
            try:
                result = function(state)
            except BaseException as exc:
                result, failure = None, exc
            try:
                self.save(state)
            except BudgetWait:
                # Keep known server protection shared between profile clients,
                # even when the final commit fails. Flush before any next work.
                self._profile.unsaved = copy.deepcopy(state)
                if failure is None:
                    raise
            if failure:
                raise failure
            return result

    def save(self,state):
        _validate(state)
        data=json.dumps(state,separators=(',',':')).encode('ascii')
        if len(data)>MAX_FILE_BYTES:raise BudgetWait(60,'history_corrupt')
        temporary=None
        try:
            fd,temporary=tempfile.mkstemp(prefix=self.path.name+'.',suffix='.tmp',dir=self.path.parent)
            with os.fdopen(fd,'wb') as handle:
                handle.write(data);handle.flush();os.fsync(handle.fileno())
            os.replace(temporary,self.path);temporary=None
        except OSError:
            raise BudgetWait(60,'history_io') from None
        finally:
            if temporary is not None:
                try:os.unlink(temporary)
                except OSError:pass


class MemoryBudgetStore:
    """Same transaction semantics for long virtual traces; real I/O tested separately."""
    def __init__(self, state=None):
        self.state = copy.deepcopy(state)
        self.lock = threading.RLock()

    def read(self, factory):
        with self.lock:
            if self.state is None:
                return factory()
            state = dict(self.state)
            for key in ("minutes", "short", "grants", "pending"):
                state[key] = [list(row) for row in self.state[key]]
            state["fast"] = list(self.state["fast"])
            return state

    def update(self, factory, function):
        with self.lock:
            state = self.state if self.state is not None else factory()
            self.state = state
            return function(state)

    def save(self,state):
        self.state=state


@dataclass(frozen=True)
class OperationGrant:
    number: int
    owner: object


class ApiBudget:
    def __init__(self, path: Path, values=None, *, store=None, wall=None, monotonic=None):
        self.values = settings(values or {})
        self.zone = ZoneInfo(self.values["api_budget_timezone"])
        self.store = store if store is not None else FileBudgetStore(path)
        self.wall = wall or time.time
        self.monotonic = monotonic or time.monotonic
        self._anchor = None
        self._clock_guard_pending = 0.0
        self._anchor_lock = threading.RLock()
        self._activity_lock = threading.Lock()
        self._activity_sequence = 0
        self._activity_at = -1.0e12
        self._consumed_activity = 0
        self._owned = set()

    def configure(self, values):
        new = settings(values)
        self.zone = ZoneInfo(new["api_budget_timezone"])
        self.values = new  # Never delete the existing ledger/deadlines.

    def notify_activity(self):
        # A numeric signal only: no input data, disk, API or HTTP lock here.
        with self._activity_lock:
            self._activity_sequence += 1
            self._activity_at = self.monotonic()

    def _factory(self):
        return _new_state(self.wall(), self.monotonic())

    def _advance(self, state):
        wall, mono = self.wall(), self.monotonic()
        with self._anchor_lock:
            uncertain = False
            if self._anchor is None:
                elapsed = mono - state["mono"]
                uncertain = elapsed < 0 or abs((wall - state["wall"]) - elapsed) > 5
                logical = state["logical"] + (0 if uncertain else elapsed)
                self._anchor = (logical, mono, wall)
            else:
                logical_at_anchor, mono_at_anchor, wall_at_anchor = self._anchor
                elapsed = mono - mono_at_anchor
                uncertain = elapsed < 0 or abs((wall - wall_at_anchor) - elapsed) > 5
                logical = max(state["logical"], logical_at_anchor + max(0, elapsed))
                if uncertain:
                    self._anchor = (logical, mono, wall)
            if uncertain:
                self._clock_guard_pending = max(self._clock_guard_pending, logical + 600)
            state["clock_guard"] = max(state["clock_guard"], self._clock_guard_pending)
            state.update(wall=wall, mono=mono, logical=logical)
        state["short"] = [r for r in state["short"] if r[0] > logical - 30]
        # Keep the entire partial minute until its END is older than 24 h.
        state["minutes"] = [r for r in state["minutes"] if r[0] + 60 > logical - DAY]
        state["fast"] = [t for t in state["fast"] if t > logical - 3600]
        state["grants"] = [r for r in state["grants"] if r[1] > logical and r[2] > 0]
        self._owned.intersection_update(r[0] for r in state["grants"])
        return logical

    def _limits(self, state):
        now = state["logical"]
        factor = 0.5 if now < max(state["warm_until"], state["quota_strong"]) else 0.75 if now < state["quota_soft"] else 1.0
        return self.values["api_budget_short_total"], self.values["api_budget_short_auto"], \
            max(1, int(self.values["api_budget_long_total"] * factor)), \
            max(1, int(self.values["api_budget_long_auto"] * factor))

    @staticmethod
    def _spent(state):
        pending=len(state['pending']);auto_pending=sum(r[0]==0 for r in state['pending'])
        return len(state["short"])+pending, sum(r[1] == 0 for r in state["short"])+auto_pending, \
            sum(r[1]+r[2] for r in state["minutes"])+pending, sum(r[1] for r in state["minutes"])+auto_pending

    def _profile(self, state, idle):
        now = state["logical"]
        local = dt.datetime.fromtimestamp(self.wall(), self.zone)
        start, end = self.values["api_budget_night_start_hour"], self.values["api_budget_night_end_hour"]
        night = start <= local.hour < end if start < end else local.hour >= start or local.hour < end
        prefix = "night" if night else "day"
        interval = float(self.values["api_budget_" + prefix + ("_idle_seconds" if idle else "_playing_seconds")])
        _, _, total, auto = self._spent(state)
        limits = self._limits(state)
        used = max(total / limits[2], auto / limits[3])
        multiplier = 3 if used >= 0.8 else 1.5 if used >= 0.5 else 1
        interval *= multiplier
        if used >= 0.8 and state["minutes"]:
            # Spread remaining automatic headroom to the next whole-minute
            # expiry. Keep a small buffer for variation/fallback reads instead
            # of consuming the last request and then waiting for hours.
            reserved = sum(r[2] for r in state["grants"])
            remaining = min(limits[3]-auto, limits[2]-total-reserved)
            headroom = max(4, int(limits[3]*0.01))
            expiry = state["minutes"][0][0]+60+DAY
            interval = max(interval, max(0,expiry-now)/max(1,remaining-headroom))
        # Known playing music may follow the chosen day cadence; reduced
        # budgets/pressure still decide what remains affordable. Night/idle
        # keep their conservative recovery floors.
        if (night or idle) and now < state["warm_until"]:
            interval = max(interval, 30)
        if (night or idle) and now < state["quota_strong"]:
            interval = max(interval, 60)
        elif (night or idle) and now < state["quota_soft"]:
            interval = max(interval, 30)
        burst = (now < state["burst_end"] and state["burst_polls"] < 10 and len(state["fast"]) < 120 and used < 0.5 and
                 now >= max(state["warm_until"], state["quota_soft"], state["clock_guard"]))
        return prefix, used, 0.5 if burst and not idle else interval, burst and not idle

    def _arm_activity(self, state, idle):
        with self._activity_lock:
            sequence = self._activity_sequence
            fresh = 0 <= self.monotonic() - self._activity_at <= 5
        if sequence == self._consumed_activity:
            return
        self._consumed_activity = sequence
        now = state["logical"]
        _, used, _, _ = self._profile(state, idle)
        if (fresh and not idle and used < 0.5 and now - state["last_burst"] >= 300 and len(state["fast"]) < 120 and
                now >= max(state["warm_until"], state["quota_soft"], state["clock_guard"], state["retry_until"])):
            state.update(last_burst=now, burst_end=now+5, burst_polls=0)

    def _wait(self, state, idle, explicit=False, own=0):
        now = state["logical"]
        if now < state["retry_until"]:
            return state["retry_until"]-now, "server_retry"
        if now < state["clock_guard"]:
            return state["clock_guard"]-now, "clock_guard"
        short, auto_short, total, auto = self._spent(state)
        limit_short, limit_auto_short, limit_total, limit_auto = self._limits(state)
        reserved = sum(r[2] for r in state["grants"] if r[0] != own)
        waits = [(max(0, state["last_start"]+0.5-now), "start_spacing")]
        if short + reserved >= limit_short or not explicit and auto_short >= limit_auto_short:
            waits.append((max(0.05, state["short"][0][0]+30-now) if state["short"] else 0.5, "short_budget"))
        if total + reserved >= limit_total or not explicit and auto >= limit_auto:
            waits.append((max(0.05, state["minutes"][0][0]+60+DAY-now) if state["minutes"] else 1, "long_budget"))
        if not explicit:
            _, _, interval, _ = self._profile(state, idle)
            if state["last_auto"]:
                waits.append((max(0, state["last_auto"]+interval-now), "profile"))
        return max(waits, key=lambda item:item[0])

    def begin_operation(self, kind):
        if kind != "control":
            raise ValueError("Unknown explicit operation")
        cost = 3  # Include one real 401 retry.
        def reserve(state):
            now = self._advance(state)
            wait, reason = self._wait(state, False, True)
            if reason in ("server_retry", "clock_guard", "long_budget") and wait > 0:
                raise BudgetWait(wait, reason)
            short, _, total, _ = self._spent(state)
            limits = self._limits(state)
            reserved = sum(r[2] for r in state["grants"])
            if len(state["grants"]) >= 8 or short+reserved+cost > limits[0] or total+reserved+cost > limits[2]:
                raise BudgetWait(max(0.05, wait), "operation_capacity")
            number = int(state["next_grant"]); state["next_grant"] += 1
            state["grants"].append([number, now+10, cost, 1])
            return number
        number = self.store.update(self._factory, reserve)
        self._owned.add(number)
        return OperationGrant(number, self)

    def finish_operation(self, grant):
        if not isinstance(grant, OperationGrant) or grant.owner is not self or grant.number not in self._owned:
            return
        self._owned.discard(grant.number)
        def release(state):
            self._advance(state)
            state["grants"] = [r for r in state["grants"] if r[0] != grant.number]
        self.store.update(self._factory, release)

    def admit(self, idle=False, operation=None):
        def charge(state):
            now = self._advance(state)
            record = None
            if operation is not None:
                if not isinstance(operation, OperationGrant) or operation.owner is not self or operation.number not in self._owned:
                    raise BudgetWait(0.05, "operation_expired")
                record = next((r for r in state["grants"] if r[0] == operation.number), None)
                if record is None:
                    raise BudgetWait(0.05, "operation_expired")
            else:
                self._arm_activity(state, idle)
            wait, reason = self._wait(state, idle, record is not None, record[0] if record else 0)
            if wait > 1e-6:
                raise BudgetWait(wait, reason)
            if record:
                record[2] -= 1
                if record[2] == 0:
                    state["grants"] = [r for r in state["grants"] if r[0] != record[0]]
                    self._owned.discard(record[0])
            else:
                _, _, _, fast = self._profile(state, idle)
                state["last_auto"] = now
                if fast:
                    state["fast"].append(now); state["burst_polls"] += 1
            explicit = int(record is not None)
            state["short"].append([now, explicit])
            minute = int(now//60)*60
            if not state["minutes"] or state["minutes"][-1][0] != minute:
                state["minutes"].append([minute, 0, 0])
            state["minutes"][-1][1+explicit] += 1
            state["last_start"] = now
        self.store.update(self._factory, charge)

    @staticmethod
    def _record_completed_cost(state,explicit,fast):
        now=state['logical']
        state['short'].append([now,explicit])
        minute=int(now//60)*60
        if not state['minutes'] or state['minutes'][-1][0]!=minute:
            state['minutes'].append([minute,0,0])
        state['minutes'][-1][1+explicit]+=1
        # Completion time is never earlier than the true /v1 start, even if
        # OAuth, fsync or thread scheduling took arbitrarily long. It keeps
        # window costs conservatively longer and spaces the next start safely.
        state['last_start']=now
        if not explicit:
            state['last_auto']=now
            if fast:state['fast'].append(now);state['burst_polls']+=1

    def http_attempt(self,function,*,idle=False,operation=None,start_check=None):
        """Shared profile transaction through network return; no input locks.

        Pending cost is fsynced before the callback. Actual costs become
        conservative completion-time rows; a crash leaves a non-expiring
        pending debit that the next attempt recovers instead of losing it.
        """
        def execute(state):
            now=self._advance(state)
            if state['pending']:
                # A process died after the durable claim; its server outcome is
                # unknown. Keep the cost and quarantine all /v1 work for 24 h.
                state['clock_guard']=max(state['clock_guard'],now+DAY)
                state['warm_until']=max(state['warm_until'],now+DAY)
            for explicit,fast in state['pending']:
                self._record_completed_cost(state,explicit,fast)
            state['pending']=[]
            record=None;deadline=None
            if operation is not None:
                if not isinstance(operation,OperationGrant) or operation.owner is not self or operation.number not in self._owned:
                    raise BudgetWait(0.05,'operation_expired')
                record=next((r for r in state['grants'] if r[0]==operation.number),None)
                if record is None:raise BudgetWait(0.05,'operation_expired')
                deadline=record[1]
            else:self._arm_activity(state,idle)
            wait,reason=self._wait(state,idle,record is not None,record[0] if record else 0)
            if wait>1e-6:raise BudgetWait(wait,reason)
            explicit=int(record is not None)
            fast=self._profile(state,idle)[3] if not explicit else False
            if record:
                record[2]-=1
                if record[2]==0:state['grants']=[r for r in state['grants'] if r[0]!=record[0]]
            state['pending']=[[explicit,int(fast)]]
            self.store.save(state) # Durable claim BEFORE /v1, still under the shared lock.
            called=False;failure=None
            try:
                now=self._advance(state)
                pending=state['pending'];state['pending']=[]
                wait,reason=self._wait(state,idle,bool(explicit),record[0] if record else 0)
                state['pending']=pending
                if deadline is not None and now>=deadline:raise BudgetWait(0.05,'operation_expired')
                if wait>1e-6:raise BudgetWait(wait,reason)
                if start_check is not None:start_check()
                called=True
                return function()
            except BaseException as exc:
                failure=exc
                raise
            finally:
                self._advance(state);state['pending']=[]
                if called:self._record_completed_cost(state,explicit,fast)
                elif record and record in state['grants']:record[2]+=1
                if failure is not None and hasattr(failure,'_budget_retry_after'):
                    self._note_retry_state(state,failure._budget_retry_after,failure._budget_quota)
        return self.store.update(self._factory,execute)

    def _note_retry_state(self,state,seconds,quota):
        now=state['logical']
        state['retry_until']=max(state['retry_until'],now+seconds)
        state['retry_reason']=2 if quota else 1
        if quota:
            state['quota_strong']=max(state['quota_strong'],now+seconds+DAY)
            state['quota_soft']=max(state['quota_soft'],now+seconds+3*DAY)
        state['grants']=[];self._owned.clear()

    def note_retry(self, seconds, quota=False):
        def record(state):
            self._advance(state)
            self._note_retry_state(state,seconds,quota)
        self.store.update(self._factory, record)
        self._owned.clear()

    def import_legacy_limits(self, retry_wall=0.0, quota_retry_wall=0.0, quota_retry=False):
        """Import absolute saved protection without extending it each restart."""
        if not (retry_wall > self.wall() or quota_retry_wall and quota_retry_wall + 3*DAY > self.wall()):
            return
        def record(state):
            now = self._advance(state)
            wall = self.wall()
            until = now+max(0,retry_wall-wall)
            if until > state["retry_until"]:
                state["retry_until"] = until
                state["retry_reason"] = 2 if quota_retry else 1
            if quota_retry_wall:
                state["quota_strong"] = max(state["quota_strong"], now+max(0,quota_retry_wall+DAY-wall))
                state["quota_soft"] = max(state["quota_soft"], now+max(0,quota_retry_wall+3*DAY-wall))
        self.store.update(self._factory, record)

    def view(self, idle=False):
        try:
            state = self.store.read(self._factory)
            now = self._advance(state)
            profile, used, interval, fast = self._profile(state, idle)
            wait, reason = self._wait(state, idle)
            short, auto_short, total, auto = self._spent(state)
            limits = self._limits(state)
            return dict(profile=profile, interval_seconds=interval, fast_active=fast,
                short_used=short, short_auto_used=auto_short, short_total_limit=limits[0], short_auto_limit=limits[1],
                long_used=total, long_auto_used=auto, long_total_limit=limits[2], long_auto_limit=limits[3],
                reserved=sum(r[2] for r in state["grants"]), pressure=used,
                wait_seconds=wait, wait_reason=reason if wait > 0 else "none",
                history_complete=now >= state["warm_until"], quota_recovery=now < state["quota_soft"],
                activity_wake_allowed=not idle and used < 0.5 and len(state["fast"]) < 120 and
                    now >= max(state["warm_until"], state["quota_soft"], state["clock_guard"], state["retry_until"]) and
                    (fast or now-state["last_burst"] >= 300),
                retry_remaining_seconds=max(0,state["retry_until"]-now),
                retry_reason=state["retry_reason"],
                clock_guard_remaining_seconds=max(0,state["clock_guard"]-now))
        except BudgetWait as exc:
            return dict(profile="guarded", wait_seconds=exc.wait_seconds, wait_reason=exc.reason,
                        interval_seconds=60.0, fast_active=False, history_complete=False,
                        retry_remaining_seconds=0.0, clock_guard_remaining_seconds=0.0)
