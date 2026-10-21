#pragma once

// Bounded notification metadata only; pixels remain in the existing two slots.
class MediaArtRefinementNotice {
public:
    bool generation(const char *challenge) {
        bool same = true;
        for (unsigned i = 0; i < 16; ++i) if (challenge_[i] != challenge[i]) same = false;
        if (!same) cancel();
        for (unsigned i = 0; i < 16; ++i) challenge_[i] = challenge[i];
        challenge_[16] = 0;
        return !same;
    }
    void cancel() { id_ = 0; }
    void stage(unsigned short id, unsigned char slot, unsigned int context) {
        if (!challenge_[0]) return;
        id_ = id; slot_ = slot; context_ = context;
    }
    unsigned short take(unsigned char slot, unsigned int context, bool artwork) {
        if (!id_ || slot_ != slot || context_ != context || !artwork) return 0;
        const unsigned short id = id_;
        id_ = 0;
        return id;
    }
    const char *challenge() const { return challenge_; }
private:
    char challenge_[17] = {};
    unsigned int context_ = 0;
    unsigned short id_ = 0;
    unsigned char slot_ = 0;
};
