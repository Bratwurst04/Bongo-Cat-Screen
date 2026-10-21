#pragma once
#include <stdint.h>

// Diagnostic profile only. Durations are unsigned differences, so micros()/
// millis() wrap is safe within one sample/report interval. No text is retained.
struct RenderTimingHistogram {
    uint32_t count = 0;
    uint32_t maximum_us = 0;
    uint32_t bins[6] = {};

    void add(uint32_t elapsed_us) {
        static const uint32_t bounds[5] = {1000, 4000, 16000, 33000, 66000};
        ++count;
        if (elapsed_us > maximum_us) maximum_us = elapsed_us;
        unsigned int bucket = 0;
        while (bucket < 5 && elapsed_us > bounds[bucket]) ++bucket;
        ++bins[bucket];
    }
};

struct RenderTimingGroup {
    RenderTimingHistogram gap;
    RenderTimingHistogram handler;
    RenderTimingHistogram flush;
};

class RenderDiagnostics {
public:
    RenderTimingGroup groups[4] = {};

    static unsigned int groupFor(bool playing, bool transfer) {
        return (playing ? 1U : 0U) | (transfer ? 2U : 0U);
    }

    bool beginHandler(uint32_t now_us, bool playing, bool transfer) {
        if (handler_active) return false;
        handler_active = true;
        current_group = groupFor(playing, transfer);
        if (have_entry) groups[current_group].gap.add(uint32_t(now_us - last_entry_us));
        last_entry_us = handler_entry_us = now_us;
        have_entry = true;
        return true;
    }

    void endHandler(uint32_t now_us) {
        if (!handler_active) return;
        groups[current_group].handler.add(uint32_t(now_us - handler_entry_us));
        handler_active = false;
    }

    void recordFlush(uint32_t start_us, uint32_t end_us, bool playing, bool transfer) {
        groups[groupFor(playing, transfer)].flush.add(uint32_t(end_us - start_us));
    }

    bool reportDue(uint32_t now_ms) {
        if (uint32_t(now_ms - last_report_ms) < 15000U) return false;
        last_report_ms = now_ms;
        return true;
    }

    void clearWindow() {
        for (unsigned int i = 0; i < 4; ++i) groups[i] = RenderTimingGroup{};
        // Keep last_entry_us: the next real handler gap crosses the window edge.
    }

private:
    uint32_t last_entry_us = 0;
    uint32_t handler_entry_us = 0;
    uint32_t last_report_ms = 0;
    unsigned int current_group = 0;
    bool have_entry = false;
    bool handler_active = false;
};
