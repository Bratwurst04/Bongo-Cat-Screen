# 🎭 Bongo Cat Animations

This folder contains all the sprite data and animation definitions for the Bongo Cat display.

## 📁 Animation Categories

### 🎯 **body/** - Body Movements
- `standardbody1.c` - Default body pose
- `bodyeartwitch.c` - Ear twitching animation

### 😸 **faces/** - Facial Expressions  
- `stock_face.c` - Default neutral expression
- `happy_face.c` - Happy/excited expression
- `sleepy_face.c` - Tired/sleepy expression
- `blink_face.c` - Blinking animation

### 🐾 **paws/** - Paw Movements
- `leftpawdown.c` - Left paw pressing down (typing)
- `rightpawdown.c` - Right paw pressing down (typing)
- `twopawsup.c` - Both paws raised (idle)

### ✨ **effects/** - Special Effects
- `left_click_effect.c` - Visual effect for left mouse clicks
- `right_click_effect.c` - Visual effect for right mouse clicks
- `sleepy1.c`, `sleepy2.c`, `sleepy3.c` - Sleep mode animations

### 🏓 **table/** - Background Elements
- `table1.c` - Table/desk surface sprite

## 🎨 Sprite Format

All sprites are stored as C arrays containing:
- **Width** and **Height** dimensions
- **Color Data** in RGB565 format (16-bit)
- **Transparency** support for overlaying

Example sprite structure:
```cpp
const uint16_t sprite_width = 64;
const uint16_t sprite_height = 64;
const uint16_t sprite_data[] = {
    // RGB565 pixel data...
};
```

## 🔄 Animation States

The animation system supports multiple states:

| State | Description | Speed |
|-------|-------------|--------|
| **IDLE** | Cat sitting peacefully | Slow |
| **TYPING** | Paws moving with typing | Variable |
| **SLEEPING** | Peaceful sleep animation | Very Slow |
| **EXCITED** | Fast typing/happy state | Fast |

## 🛠️ Adding New Animations

1. **Create Sprite Data**
   - Use image conversion tools to generate C arrays
   - Follow the existing naming convention
   - Ensure proper dimensions (typically 64x64 or smaller)

2. **Update animations_sprites.h**
   - Add your new sprite declarations
   - Include the new `.c` file

3. **Modify Animation Logic**
   - Update `bongo_cat.ino` to use new animations
   - Add state transitions and timing

## 🎨 Animation Guidelines

See `Animation guidelines.md` for detailed information on:
- Sprite creation best practices  
- Color palette recommendations
- Animation timing and transitions
- Performance considerations

## 🤝 Contributing Animations

Want to add new animations? Here's how:

1. **Design** your animation frames
2. **Convert** to C sprite format
3. **Test** on hardware
4. **Submit** via pull request

Popular animation ideas:
- Different typing speeds
- Mouse click responses  
- Time-based expressions
- Custom cat personalities

---

*Let your creativity run wild and make Bongo Cat even more expressive!* 🐱 