#include <Arduino.h>
#include "../animations_sprites.h"

// Arduino IDE normally generates these declarations for .ino sketches.
void resetSettings();
void createBongoCat();
const char* get_state_name(animation_state_t state);
void createFeatureOverlay();
void createMediaScreen();
void createFocusScreen();
void createFocusSettingsScreen();
void createLocalSettingsScreen();
void refreshAccentTheme();
void showMediaScreen();
void showBongoScreen();
void showFocusScreen();
void showFocusScreen(bool acknowledge_cue);
void refreshMediaUi();
void handleTouchFeature(uint32_t current_time);
void triggerTouchBonk(uint32_t current_time);
void cancelTouchBonk();
void toggleFeatureOverlay(uint32_t current_time);

#include "bongo_cat_featured.inc"
