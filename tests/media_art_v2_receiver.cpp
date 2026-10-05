#include "../src/media_art_v2.h"

#include <assert.h>
#include <stdint.h>

int main() {
    // CRC-32 of "123456789" is the standard check vector CB F4 39 26.
    const uint8_t first[] = {'1', '2', '3', '4'};
    const uint8_t rest[] = {'5', '6', '7', '8', '9'};
    const uint8_t bad[] = {'5', '6', '7', '8', '0'};
    MediaArtV2Transfer frame(9);

    assert(!frame.begin(0, 9, 0xCBF43926u));
    assert(!frame.begin(1, 8, 0xCBF43926u));
    assert(frame.begin(1, 9, 0xCBF43926u));
    assert(frame.accept(1, 0, first, sizeof(first)));
    assert(!frame.complete(1));
    assert(!frame.accept(1, 3, rest, sizeof(rest)));  // missing/duplicate offset
    assert(!frame.accept(2, 4, rest, sizeof(rest)));  // wrong transfer id
    assert(frame.received == sizeof(first));
    assert(frame.accept(1, 4, rest, sizeof(rest)));
    assert(!frame.complete(2));
    assert(frame.complete(1));

    frame.abort();
    assert(!frame.complete(1));
    assert(!frame.accept(1, 0, first, sizeof(first)));

    assert(frame.begin(3, 9, 0xCBF43926u));
    assert(frame.accept(3, 0, first, sizeof(first)));
    assert(frame.accept(3, 4, bad, sizeof(bad)));
    assert(!frame.complete(3));  // a full but corrupted image stays hidden

    assert(frame.begin(4, 9, 0xCBF43926u));
    assert(frame.accept(4, 0, first, sizeof(first)));
    assert(!frame.accept(4, 4, rest, 6));  // exceeds declared frame size
    assert(!frame.complete(4));
    return 0;
}
