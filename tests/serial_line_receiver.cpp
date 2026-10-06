#include "../src/serial_line_receiver.h"

#include <assert.h>
#include <string>
#include <vector>

struct FakeSerial {
    std::string bytes;
    size_t offset = 0;
    int scalar_reads = 0;
    int bulk_reads = 0;

    int available() const { return static_cast<int>(bytes.size() - offset); }
    int read() {
        ++scalar_reads;
        return available() ? static_cast<unsigned char>(bytes[offset++]) : -1;
    }
    size_t read(uint8_t *output, size_t amount) {
        ++bulk_reads;
        size_t copied = 0;
        while (copied < amount && available()) {
            output[copied++] = static_cast<uint8_t>(bytes[offset++]);
        }
        return copied;
    }
    void add(const std::string &more) { bytes += more; }
};

int main() {
    SerialLineReceiver<256> receiver;
    FakeSerial serial;
    BufferedSerialSource<FakeSerial, 64> input(serial);
    std::vector<std::string> lines;
    int overflow = 0;
    uint32_t clock = 10;
    auto now = [&]() { return clock; };
    auto line = [&](const char *text) {
        lines.push_back(text);
        return true;
    };
    auto too_long = [&]() { ++overflow; };
    auto drain = [&]() {
        drainSerialLines(input, receiver, now, line, too_long, 5, 2048, 10);
    };

    // A serial read may stop in the middle of a base64 line. Only its real
    // newline makes the command visible to the parser.
    serial.add("MEDIA_ART2_CHUNK:7:0:AAAA");
    drain();
    assert(lines.empty() && receiver.hasPartial());
    serial.add("BBBB\nMEDIA_ART2_CHUNK:7:128:CCCC\n");
    drain();
    assert(lines.size() == 2);
    assert(lines[0] == "MEDIA_ART2_CHUNK:7:0:AAAABBBB");
    assert(lines[1] == "MEDIA_ART2_CHUNK:7:128:CCCC");

    // A burst is drained within a line count budget, then the next loop can
    // service GUI and touch before taking the remaining lines.
    lines.clear();
    for (int i = 0; i < 13; ++i) serial.add("PING\n");
    drain();
    assert(lines.size() == 10 && input.available() > 0);
    drain();
    assert(lines.size() == 13 && input.available() == 0);
    assert(serial.bulk_reads > 0 && serial.scalar_reads == 0);

    serial.add(std::string(260, 'X') + "\nPING\n");
    drain();
    assert(overflow == 1 && lines.back() == "PING");

    serial.add("MEDIA_ART2_CHUNK:8:0:partial");
    drain();
    assert(receiver.hasPartial());
    clock += 249;
    assert(!receiver.expire(clock, 250));
    clock += 1;
    assert(receiver.expire(clock, 250) && !receiver.hasPartial());
    serial.add("PING\n");
    drain();
    assert(lines.back() == "PING");

    // A raw legacy frame begins immediately after its header. The callback
    // must stop draining at that boundary, leaving RGB bytes to its receiver.
    FakeSerial legacy;
    BufferedSerialSource<FakeSerial, 64> legacy_input(legacy);
    SerialLineReceiver<256> legacy_receiver;
    legacy.add("MEDIA_ART_RGB:112:112:37632\n\x01\x02\x03");
    std::vector<std::string> legacy_lines;
    drainSerialLines(legacy_input, legacy_receiver, now,
                     [&](const char *text) {
                         legacy_lines.push_back(text);
                         return false;
                     }, too_long, 5, 2048, 10);
    assert(legacy_lines.size() == 1);
    assert(legacy_lines[0] == "MEDIA_ART_RGB:112:112:37632");
    assert(legacy_input.available() == 3);
    uint8_t raw[3] = {};
    assert(legacy_input.read(raw, sizeof(raw)) == 3);
    assert(raw[0] == 1 && raw[1] == 2 && raw[2] == 3);
    assert(legacy.bulk_reads > 0 && legacy.scalar_reads == 0);

    // Raw artwork can start in the prefetched block and continue in the
    // UART. Binary newline/NUL bytes stay raw; the next command stays intact.
    FakeSerial crossing;
    BufferedSerialSource<FakeSerial, 8> crossing_input(crossing);
    SerialLineReceiver<256> crossing_receiver;
    std::string crossing_bytes = "MEDIA_ART_RGB:112:112:37632\n";
    const uint8_t expected_raw[] = {0, '\n', 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11};
    crossing_bytes.append(reinterpret_cast<const char *>(expected_raw), sizeof(expected_raw));
    crossing_bytes += "PING\n";
    crossing.add(crossing_bytes);
    drainSerialLines(crossing_input, crossing_receiver, now,
                     [](const char *) { return false; }, too_long,
                     5, 2048, 10);
    uint8_t crossing_raw[sizeof(expected_raw)] = {};
    int reads_before_raw = crossing.bulk_reads;
    assert(crossing_input.read(crossing_raw, sizeof(crossing_raw)) == sizeof(crossing_raw));
    assert(crossing.bulk_reads > reads_before_raw);
    for (size_t i = 0; i < sizeof(crossing_raw); ++i) {
        assert(crossing_raw[i] == expected_raw[i]);
    }
    std::vector<std::string> after_raw;
    drainSerialLines(crossing_input, crossing_receiver, now,
                     [&](const char *text) {
                         after_raw.push_back(text);
                         return true;
                     }, too_long, 5, 2048, 10);
    assert(after_raw.size() == 1 && after_raw[0] == "PING");
    assert(crossing.scalar_reads == 0);

    // The core-0 framer must preserve a complete binary legacy frame and
    // deliver the next text command after exactly the advertised byte count.
    SerialInputFramer<256, 192> framer;
    std::vector<std::string> framed_lines;
    std::string framed_raw;
    int framed_overflow = 0;
    std::string framed = " \tMEDIA_ART_RGB:112:112:37632 \r\n";
    std::string binary(SerialInputFramer<256, 192>::LegacyRawBytes, 'R');
    binary[0] = '\0';
    binary[1] = '\n';
    binary[191] = '\n';
    framed += binary + "PING\n";
    for (unsigned char byte : framed) {
        framer.push(byte, clock,
                    [&](const char *text) { framed_lines.push_back(text); },
                    [&](const uint8_t *raw_bytes, size_t count) {
                        framed_raw.append(reinterpret_cast<const char *>(raw_bytes), count);
                    },
                    [&]() { ++framed_overflow; });
    }
    assert(framed_lines.size() == 2);
    assert(framed_lines[0] == " \tMEDIA_ART_RGB:112:112:37632 \r");
    assert(framed_lines[1] == "PING");
    assert(framed_raw == binary && framed_overflow == 0);
    assert(!framer.hasPartial());

    SerialInputFramer<256, 192> invalid_legacy;
    std::vector<std::string> invalid_lines;
    for (unsigned char byte : std::string("MEDIA_ART_RGB:111:112:37632\nPING\n")) {
        invalid_legacy.push(byte, clock,
                            [&](const char *text) { invalid_lines.push_back(text); },
                            [](const uint8_t *, size_t) {}, too_long);
    }
    assert(invalid_lines.size() == 2 && invalid_lines[1] == "PING");
    assert(invalid_legacy.rawRemaining() == 0);

    SerialInputFramer<256, 192> stalled_framer;
    stalled_framer.push('P', clock, line,
                        [](const uint8_t *, size_t) {}, too_long);
    assert(stalled_framer.hasPartial());
    assert(!stalled_framer.expireLine(clock + 249, 250));
    assert(stalled_framer.expireLine(clock + 250, 250));
    assert(!stalled_framer.hasPartial());
    SerialInputFramer<256, 192> raw_stall;
    for (unsigned char byte : std::string("MEDIA_ART_RGB:112:112:37632\n\0", 29)) {
        raw_stall.push(byte, clock, line,
                       [](const uint8_t *, size_t) {}, too_long);
    }
    assert((raw_stall.rawRemaining() == SerialInputFramer<256, 192>::LegacyRawBytes - 1));
    assert(!raw_stall.expireRaw(clock + 14999, 15000));
    assert(raw_stall.expireRaw(clock + 15000, 15000));
    assert(!raw_stall.hasPartial());

    // A time budget can stop mid-line without dispatching a truncated frame.
    FakeSerial timed;
    BufferedSerialSource<FakeSerial, 64> timed_input(timed);
    SerialLineReceiver<256> timed_receiver;
    std::vector<std::string> timed_lines;
    timed.add("MEDIA_ART2_CHUNK:9:0:AAAA\n");
    uint32_t ticks = 0;
    auto advancing_clock = [&]() { return ticks++; };
    drainSerialLines(timed_input, timed_receiver, advancing_clock,
                     [&](const char *text) {
                         timed_lines.push_back(text);
                         return true;
                     }, too_long, 5, 2048, 10);
    assert(timed_lines.empty() && timed_receiver.hasPartial());
    while (timed_input.available()) {
        drainSerialLines(timed_input, timed_receiver, advancing_clock,
                         [&](const char *text) {
                             timed_lines.push_back(text);
                             return true;
                         }, too_long, 5, 2048, 10);
    }
    assert(timed_lines.size() == 1);
    assert(timed_lines[0] == "MEDIA_ART2_CHUNK:9:0:AAAA");
    return 0;
}
