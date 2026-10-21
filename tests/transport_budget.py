"""Dependency injection for existing transport/backoff component regressions.

Preventive admission is exercised with the REAL policy in test_api_budget*
and long simulations. This fixture keeps transport clocks/HTTP isolated from
profile budgets so old 0.5s start-time and protocol assertions stay meaningful.
"""
from api_budget import OperationGrant
from spotify_api import SpotifyApiBridge as RealSpotifyApiBridge


class TransportBudget:
    def __init__(self):self.number=0
    def configure(self,values):pass
    def notify_activity(self):pass
    def import_legacy_limits(self,*args):pass
    def note_retry(self,*args):pass
    def admit(self,**kwargs):pass
    def http_attempt(self,function,**kwargs):
        check=kwargs.get('start_check')
        if check is not None:check()
        return function()
    def finish_operation(self,operation):pass
    def begin_operation(self,kind):
        self.number+=1
        return OperationGrant(self.number,self)
    def view(self,idle=False):
        return dict(profile='day',interval_seconds=0,wait_seconds=0,wait_reason='none',
            history_complete=True,quota_recovery=False,pressure=0,retry_remaining_seconds=0,
            clock_guard_remaining_seconds=0,activity_wake_allowed=False)


class TransportSpotifyApiBridge(RealSpotifyApiBridge):
    def __init__(self,*args,**kwargs):
        kwargs['budget']=TransportBudget()
        super().__init__(*args,**kwargs)
