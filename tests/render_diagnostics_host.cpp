typedef unsigned int uint32_t;
typedef unsigned __int64 size_t;
extern "C" void *memcpy(void *, const void *, size_t);
extern "C" void *memset(void *, int, size_t);
#pragma function(memcpy, memset)
extern "C" void *memcpy(void *out, const void *in, size_t count) {
    volatile unsigned char *dst = static_cast<volatile unsigned char *>(out);
    const unsigned char *src = static_cast<const unsigned char *>(in);
    for (size_t i = 0; i < count; ++i) dst[i] = src[i];
    return out;
}
extern "C" void *memset(void *out, int value, size_t count) {
    volatile unsigned char *dst = static_cast<volatile unsigned char *>(out);
    for (size_t i = 0; i < count; ++i) dst[i] = static_cast<unsigned char>(value);
    return out;
}
#include "render_diagnostics_fixture.inc"
static RenderDiagnostics diagnostics;
extern "C" __declspec(dllexport) void rd_reset() { diagnostics = RenderDiagnostics{}; }
extern "C" __declspec(dllexport) int rd_begin(unsigned int now, int playing, int transfer) {
    return diagnostics.beginHandler(now, playing != 0, transfer != 0);
}
extern "C" __declspec(dllexport) void rd_end(unsigned int now) { diagnostics.endHandler(now); }
extern "C" __declspec(dllexport) void rd_flush(unsigned int start, unsigned int end, int playing, int transfer) {
    diagnostics.recordFlush(start, end, playing != 0, transfer != 0);
}
extern "C" __declspec(dllexport) unsigned int rd_value(int group, int metric, int field) {
    const RenderTimingGroup &g = diagnostics.groups[group];
    const RenderTimingHistogram &h = metric == 0 ? g.gap : metric == 1 ? g.handler : g.flush;
    return field == 0 ? h.count : field == 1 ? h.maximum_us : h.bins[field - 2];
}
extern "C" __declspec(dllexport) int rd_due(unsigned int now) { return diagnostics.reportDue(now); }
extern "C" __declspec(dllexport) void rd_clear() { diagnostics.clearWindow(); }
