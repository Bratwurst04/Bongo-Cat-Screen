#pragma once

#include <stddef.h>
#include <stdint.h>

// Keep an incomplete serial command across loop iterations. Stream's
// readStringUntil() can return a partial art2 frame after its short timeout.
template <size_t Capacity>
class SerialLineReceiver {
public:
    static_assert(Capacity >= 2, "Serial line buffer is too small");

    enum class Result { None, Complete, Overflow };

    Result push(uint8_t byte, uint32_t now) {
        last_byte_ms_ = now;
        if (byte == '\n') {
            if (overflow_) {
                reset();
                return Result::Overflow;
            }
            buffer_[length_] = '\0';
            length_ = 0;
            return Result::Complete;
        }
        if (overflow_) return Result::None;
        if (length_ >= Capacity - 1) {
            overflow_ = true;
            length_ = 0;
            return Result::None;
        }
        buffer_[length_++] = static_cast<char>(byte);
        return Result::None;
    }

    bool expire(uint32_t now, uint32_t timeout_ms) {
        if (!hasPartial() || now - last_byte_ms_ < timeout_ms) return false;
        reset();
        return true;
    }

    bool hasPartial() const { return length_ != 0 || overflow_; }
    const char *line() const { return buffer_; }

    void reset() {
        length_ = 0;
        overflow_ = false;
    }

private:
    char buffer_[Capacity] = {};
    size_t length_ = 0;
    uint32_t last_byte_ms_ = 0;
    bool overflow_ = false;
};

// HardwareSerial::read() takes the UART mutex for every byte. Read a bounded
// block once, then preserve any bytes past a legacy RGB header for the raw
// receiver instead of treating them as another line.
template <class Source, size_t Capacity>
class BufferedSerialSource {
public:
    explicit BufferedSerialSource(Source &source) : source_(source) {}

    int available() {
        if (offset_ < used_) return static_cast<int>(used_ - offset_);
        return source_.available();
    }

    size_t totalAvailable() {
        return used_ - offset_ + source_.available();
    }

    int read() {
        if (offset_ == used_) {
            int ready = source_.available();
            if (ready <= 0) return -1;
            size_t amount = static_cast<size_t>(ready);
            if (amount > Capacity) amount = Capacity;
            used_ = source_.read(bytes_, amount);
            offset_ = 0;
            if (!used_) return -1;
        }
        return bytes_[offset_++];
    }

    size_t read(uint8_t *output, size_t amount) {
        size_t copied = 0;
        while (copied < amount && offset_ < used_) {
            output[copied++] = bytes_[offset_++];
        }
        if (copied < amount) {
            int ready = source_.available();
            if (ready > 0) {
                size_t wanted = amount - copied;
                if (wanted > static_cast<size_t>(ready)) wanted = ready;
                copied += source_.read(output + copied, wanted);
            }
        }
        return copied;
    }

private:
    Source &source_;
    uint8_t bytes_[Capacity] = {};
    size_t offset_ = 0;
    size_t used_ = 0;
};

// The other core may frame UART bytes, but never interprets commands or
// changes artwork/UI state. Preserve the exact legacy binary span in the
// same ordered event stream as text lines.
template <size_t LineCapacity, size_t RawBlockCapacity>
class SerialInputFramer {
public:
    static_assert(RawBlockCapacity > 0, "Raw block buffer is too small");
    static constexpr size_t LegacyRawBytes = 112u * 112u * 3u;

    template <class OnLine, class OnRaw, class OnOverflow>
    void push(uint8_t byte, uint32_t now, OnLine onLine, OnRaw onRaw,
              OnOverflow onOverflow) {
        if (raw_remaining_) {
            raw_[raw_used_++] = byte;
            --raw_remaining_;
            last_raw_byte_ms_ = now;
            if (raw_used_ == RawBlockCapacity || !raw_remaining_) {
                onRaw(raw_, raw_used_);
                raw_used_ = 0;
            }
            return;
        }
        auto result = line_.push(byte, now);
        if (result == SerialLineReceiver<LineCapacity>::Result::Overflow) {
            onOverflow();
        } else if (result == SerialLineReceiver<LineCapacity>::Result::Complete) {
            const char *text = line_.line();
            onLine(text);
            if (isLegacyHeader(text)) {
                raw_remaining_ = LegacyRawBytes;
                last_raw_byte_ms_ = now;
            }
        }
    }

    bool expireLine(uint32_t now, uint32_t timeout_ms) {
        return line_.expire(now, timeout_ms);
    }

    bool expireRaw(uint32_t now, uint32_t timeout_ms) {
        if (!raw_remaining_ || now - last_raw_byte_ms_ < timeout_ms) return false;
        raw_remaining_ = 0;
        raw_used_ = 0;
        return true;
    }

    bool hasPartial() const { return line_.hasPartial() || raw_remaining_ != 0; }
    size_t rawRemaining() const { return raw_remaining_; }

private:
    static bool isLegacyHeader(const char *text) {
        const char expected[] = "MEDIA_ART_RGB:112:112:37632";
        // Match the main-loop String.trim() rule, including CRLF transport.
        while (*text == ' ' || *text == '\t' || *text == '\r') ++text;
        for (size_t i = 0; i < sizeof(expected) - 1; ++i) {
            if (text[i] != expected[i]) return false;
        }
        text += sizeof(expected) - 1;
        while (*text == ' ' || *text == '\t' || *text == '\r') ++text;
        return *text == '\0';
    }

    SerialLineReceiver<LineCapacity> line_;
    uint8_t raw_[RawBlockCapacity] = {};
    size_t raw_remaining_ = 0;
    size_t raw_used_ = 0;
    uint32_t last_raw_byte_ms_ = 0;
};

class SerialDrainBudget {
public:
    SerialDrainBudget(uint32_t started_ms, uint32_t max_ms,
                      size_t max_bytes, size_t max_lines)
        : started_ms_(started_ms), max_ms_(max_ms),
          max_bytes_(max_bytes), max_lines_(max_lines) {}

    bool canRead(uint32_t now) const {
        return bytes_ < max_bytes_ && lines_ < max_lines_ &&
               now - started_ms_ < max_ms_;
    }

    void byteRead(size_t count = 1) { bytes_ += count; }
    void lineRead() { ++lines_; }

private:
    uint32_t started_ms_;
    uint32_t max_ms_;
    size_t max_bytes_;
    size_t max_lines_;
    size_t bytes_ = 0;
    size_t lines_ = 0;
};

template <size_t Capacity, class Source, class Clock, class OnLine,
          class OnOverflow>
void drainSerialLines(Source &source, SerialLineReceiver<Capacity> &receiver,
                      Clock now, OnLine onLine, OnOverflow onOverflow,
                      uint32_t max_ms, size_t max_bytes, size_t max_lines) {
    SerialDrainBudget budget(now(), max_ms, max_bytes, max_lines);
    while (source.available() > 0 && budget.canRead(now())) {
        int incoming = source.read();
        if (incoming < 0) break;
        auto result = receiver.push(static_cast<uint8_t>(incoming), now());
        budget.byteRead();
        if (result == SerialLineReceiver<Capacity>::Result::None) continue;
        budget.lineRead();
        if (result == SerialLineReceiver<Capacity>::Result::Overflow) {
            onOverflow();
            continue;
        }
        if (!onLine(receiver.line())) break;
    }
}
