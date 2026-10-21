"""Actual native RX helpers and an explicitly assumed virtual UART/TFT schedule."""
import base64
from collections import deque
import ctypes
from functools import lru_cache
import math
import os
from pathlib import Path
import re
import subprocess

ROOT=Path(__file__).resolve().parents[1]
BUILD=ROOT/'build/artwork-fast921600-2026-10-18'


def firmware_limits():
    source=(ROOT/'src/bongo_cat_featured.inc').read_text(encoding='utf-8')
    keys=('SERIAL_LINE_BYTES','SERIAL_RX_RAW_BLOCK_BYTES','SERIAL_RX_QUEUE_DEPTH',
          'SERIAL_DRAIN_MAX_MS','SERIAL_DRAIN_MAX_BYTES','SERIAL_DRAIN_MAX_LINES')
    values={key:int(re.search(r'^#define '+key+r' (\d+)',source,re.M)[1]) for key in keys}
    values['uart_bytes']=int(re.search(r'Serial.setRxBufferSize\((\d+)\)',source)[1])
    values['loop_delay_ms']=int(re.search(r'delay\((\d+)\);[^\n]*Reduced from 5ms',source)[1])
    return values


@lru_cache(maxsize=1)
def load_host():
    folder=BUILD/'rx-host';folder.mkdir(parents=True,exist_ok=True)
    limits=firmware_limits()
    text='\n'.join('#define '+k+' '+str(v) for k,v in limits.items() if k.startswith('SERIAL_'))+'\n'
    # Only standard type includes are supplied above by the freestanding host.
    # Production class bodies remain byte-for-byte identical after preprocessing.
    for name in ('serial_line_receiver.h','media_art_v2.h'):
        text+=re.sub(r'^#(?:include[^\n]*|pragma once)\n','',
                     (ROOT/'src'/name).read_text(encoding='utf-8'),flags=re.M)+'\n'
    (folder/'artwork_fast_fixture.inc').write_text(text,encoding='utf-8')
    compiler=sorted(Path('C:/Program Files/Microsoft Visual Studio').glob('*/*/VC/Tools/MSVC/*/bin/Hostx64/x64/cl.exe'))[-1]
    dll=folder/'artwork_fast.dll'
    command=[str(compiler),'/nologo','/std:c++14','/O2','/GS-','/GR-','/Zl','/LD','/I'+str(folder),
        str(ROOT/'tests/artwork_fast_host.cpp'),'/Fo'+str(folder/'artwork_fast.obj'),
        '/link','/NODEFAULTLIB','/NOENTRY','/OUT:'+str(dll)]
    env=dict(os.environ,PATH=str(compiler.parent)+os.pathsep+os.environ.get('PATH',''))
    result=subprocess.run(command,cwd=folder,env=env,capture_output=True,text=True)
    (folder/'compile.log').write_text(result.stdout+result.stderr,encoding='utf-8')
    if result.returncode:raise RuntimeError(result.stdout+result.stderr)
    host=ctypes.CDLL(str(dll));word=ctypes.c_uint
    host.af_pump.argtypes=[ctypes.c_char_p,word,word];host.af_pop.argtypes=[ctypes.c_void_p]
    host.af_budget.argtypes=[word];host.af_can_read.argtypes=[word]
    host.af_begin.argtypes=[word,word,word];host.af_accept.argtypes=[word,word,ctypes.c_char_p,word]
    host.af_complete.argtypes=[word]
    return host


class WireModel:
    """Not a measured ESP32. CPU line cost, paint stalls and flush cost are inputs."""
    def __init__(self,engine,baud=921600,render_ms=0,blackout_ms=0,flush_poll_ms=0):
        self.h=load_host();self.h.af_reset();self.limits=firmware_limits();self.engine=engine
        self.baud=baud;self.render_us=render_ms*1000;self.blackout_us=blackout_ms*1000
        self.flush_poll_us=flush_poll_ms*1000;self.now=0.;self.wire_end=0.;self.wire=deque();self.uart=deque()
        self.next_work=0.;self.draining=False;self.dropped=0;self.peak_queue=0;self.peak_uart=0
        self.data=bytearray();self.committed=None;self.acks=[];self.touch_times=[];self.metadata=[];self.writes=[]
        self.parse_us=80 # explicit illustrative assumption, NOT an ESP32 benchmark

    def write(self,payload):
        self.writes.append(payload)
        for byte in payload:
            self.wire_end=max(self.wire_end,self.now)+1e7/self.baud
            self.wire.append((self.wire_end,byte))
        return len(payload)

    def flush(self):
        end=self.wire_end
        if self.flush_poll_us:end=self.now+math.ceil((end-self.now)/self.flush_poll_us)*self.flush_poll_us
        self.advance(end)

    def sleep(self,seconds):self.advance(self.now+seconds*1e6)

    def wait(self,timeout):
        end=self.now+timeout*1e6
        while self.now<end and not self.engine._artwork_ack.is_set():self.advance(min(end,self.now+1000))
        return self.engine._artwork_ack.is_set()

    def reply(self,ok):
        self.acks.append((self.now,ok));self.engine._artwork_v2_ack_result=ok;self.engine._artwork_ack.set()

    def handle(self,line):
        try:self.handle_line(line)
        except (ValueError,IndexError):self.h.af_abort();self.reply(False)

    def handle_line(self,line):
        if line.startswith(b'MEDIA_ART2_BEGIN:'):
            _,ident,w,h,length,crc=line.split(b':');self.data.clear()
            self.h.af_begin(int(ident),int(length),int(crc,16))
        elif line.startswith(b'MEDIA_ART2_CHUNK:'):
            _,ident,offset,encoded=line.split(b':',3)
            try:data=base64.b64decode(encoded,validate=True)
            except ValueError:self.h.af_abort();self.reply(False);return
            if not self.h.af_accept(int(ident),int(offset),data,len(data)):
                self.h.af_abort();self.reply(False)
            else:self.data.extend(data)
        elif line.startswith(b'MEDIA_ART2_END:'):
            ok=bool(self.h.af_complete(int(line.split(b':')[1])))
            if ok:self.committed=bytes(self.data)
            self.h.af_abort();self.reply(ok)
        elif line.startswith(b'MEDIA_ART2_ABORT:'):self.h.af_abort()
        else:self.metadata.append((self.now,line))

    def advance(self,end):
        while self.now<end:
            self.now=min(end,self.now+100)
            while self.wire and self.wire[0][0]<=self.now+0.001:
                _,byte=self.wire.popleft()
                if len(self.uart)<self.limits['uart_bytes']:self.uart.append(byte)
                else:self.dropped+=1
            self.peak_uart=max(self.peak_uart,len(self.uart))
            if self.uart:
                incoming=bytes(self.uart);used=self.h.af_pump(incoming,len(incoming),int(self.now/1000))
                for _ in range(used):self.uart.popleft()
            self.peak_queue=max(self.peak_queue,self.h.af_queue())
            if self.now<self.blackout_us or self.now<self.next_work:continue
            if not self.draining:self.h.af_budget(int(self.now/1000));self.draining=True
            if self.h.af_queue() and self.h.af_can_read(int(self.now/1000)):
                buf=ctypes.create_string_buffer(self.limits['SERIAL_LINE_BYTES']);n=self.h.af_pop(buf)
                self.handle(buf.raw[:n]);self.next_work=self.now+self.parse_us
            else:
                self.touch_times.append(self.now);self.draining=False
                self.next_work=self.now+self.render_us+self.limits['loop_delay_ms']*1000
