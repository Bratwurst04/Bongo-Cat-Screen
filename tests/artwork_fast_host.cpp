// Actual production framing, drain budget and CRC state; freestanding host only.
typedef unsigned __int64 size_t;
typedef unsigned char uint8_t;
typedef unsigned short uint16_t;
typedef unsigned int uint32_t;
extern "C" void *memset(void *,int,size_t);
extern "C" void *memcpy(void *,const void *,size_t);
#pragma function(memset)
#pragma function(memcpy)
extern "C" void *memset(void *p,int value,size_t bytes) {
    volatile unsigned char *out=static_cast<volatile unsigned char *>(p);
    for(size_t i=0;i<bytes;++i)out[i]=static_cast<unsigned char>(value);
    return p;
}
extern "C" void *memcpy(void *p,const void *source,size_t bytes) {
    volatile unsigned char *out=static_cast<volatile unsigned char *>(p);
    const unsigned char *in=static_cast<const unsigned char *>(source);
    for(size_t i=0;i<bytes;++i)out[i]=in[i];
    return p;
}
inline void *operator new(size_t,void *p){return p;}
#include "artwork_fast_fixture.inc"

static SerialInputFramer<SERIAL_LINE_BYTES,SERIAL_RX_RAW_BLOCK_BYTES> framer;
static MediaArtV2Transfer transfer(112u*112u*3u);
static SerialDrainBudget budget(0,1,1,1);
static char lines[SERIAL_RX_QUEUE_DEPTH][SERIAL_LINE_BYTES];
static unsigned lengths[SERIAL_RX_QUEUE_DEPTH],head=0,count=0,overflows=0;

static void enqueue(const char *text) {
    unsigned slot=(head+count)%SERIAL_RX_QUEUE_DEPTH,n=0;
    while(text[n]){lines[slot][n]=text[n];++n;}
    lines[slot][n]=0;lengths[slot]=n;++count;
}
extern "C" __declspec(dllexport) void af_reset(){
    framer=SerialInputFramer<SERIAL_LINE_BYTES,SERIAL_RX_RAW_BLOCK_BYTES>{};
    new (&transfer) MediaArtV2Transfer(112u*112u*3u);
    head=count=overflows=0;
}
extern "C" __declspec(dllexport) unsigned af_pump(const uint8_t *data,unsigned bytes,unsigned now){
    unsigned used=0;
    while(used<bytes && count<SERIAL_RX_QUEUE_DEPTH){
        framer.push(data[used++],now,[](const char *text){enqueue(text);},
            [](const uint8_t *,size_t){},[](){++overflows;enqueue("");});
    }
    return used;
}
extern "C" __declspec(dllexport) unsigned af_queue(){return count;}
extern "C" __declspec(dllexport) unsigned af_overflows(){return overflows;}
extern "C" __declspec(dllexport) void af_budget(unsigned now){
    new (&budget) SerialDrainBudget(now,SERIAL_DRAIN_MAX_MS,SERIAL_DRAIN_MAX_BYTES,SERIAL_DRAIN_MAX_LINES);
}
extern "C" __declspec(dllexport) int af_can_read(unsigned now){return budget.canRead(now);}
extern "C" __declspec(dllexport) unsigned af_pop(uint8_t *out){
    if(!count)return 0;
    unsigned n=lengths[head];for(unsigned i=0;i<=n;++i)out[i]=lines[head][i];
    head=(head+1)%SERIAL_RX_QUEUE_DEPTH;--count;budget.byteRead(n+1);budget.lineRead();return n;
}
extern "C" __declspec(dllexport) int af_begin(unsigned id,unsigned length,unsigned crc){return transfer.begin(static_cast<uint16_t>(id),length,crc);}
extern "C" __declspec(dllexport) int af_accept(unsigned id,unsigned offset,const uint8_t *data,unsigned length){return transfer.accept(static_cast<uint16_t>(id),offset,data,length);}
extern "C" __declspec(dllexport) int af_complete(unsigned id){return transfer.complete(static_cast<uint16_t>(id));}
extern "C" __declspec(dllexport) void af_abort(){transfer.abort();}
