# Pick-A-Toon Screen Changes Summary

## Overview
Modified the pick-a-toon screen to display all 6 original avatar slots, with only position 1 (green) enabled for creating/selecting toons. The other 5 slots now display as grey with "DISABLED" text in Minnie font.

## Assets Used

### Models (located in `resources/phase_3/models/gui/`)
- **`tt_m_gui_pat_mainGui.bam`** - Main GUI model containing:
  - `tt_t_gui_pat_squareRed` - Red button (position 0)
  - `tt_t_gui_pat_squareGreen` - Green button (position 1) ✅ **ENABLED SLOT**
  - `tt_t_gui_pat_squarePurple` - Purple button (position 2)
  - `tt_t_gui_pat_squareBlue` - Blue button (position 3)
  - `tt_t_gui_pat_squarePink` - Pink button (position 4)
  - `tt_t_gui_pat_squareYellow` - Yellow button (position 5)
  - `tt_t_gui_pat_background` - Background image
- **`quit_button.bam`** - Quit and logout buttons
- **`trashcan_gui.bam`** - Delete button for avatars

### Fonts (located in `resources/phase_3/models/fonts/`)
- **`MinnieFont.bam`** - Used for "DISABLED" text on inactive slots

### Audio (located in `resources/phase_3/audio/`)
- `bgm/create_a_toon.ogg` - Background music
- `sfx/GUI_*.ogg` - Various UI sound effects

## Code Changes

### `toontown/login/AvatarChooser.py`

#### Added Constants:
```python
# All 6 positions from original design
POSITIONS = (Vec3(-0.840167, 0, 0.359333),      # Position 0 (Red)
 Vec3(0.00933349, 0, 0.306533),                 # Position 1 (Green) ✅
 Vec3(0.862, 0, 0.3293),                        # Position 2 (Purple)
 Vec3(-0.863554, 0, -0.445659),                 # Position 3 (Blue)
 Vec3(0.00999999, 0, -0.5181),                  # Position 4 (Pink)
 Vec3(0.864907, 0, -0.445659))                  # Position 5 (Yellow)

COLORS = (Vec4(0.917, 0.164, 0.164, 1),         # Red
 Vec4(0.152, 0.75, 0.258, 1),                   # Green ✅
 Vec4(0.598, 0.402, 0.875, 1),                  # Purple
 Vec4(0.133, 0.59, 0.977, 1),                   # Blue
 Vec4(0.895, 0.348, 0.602, 1),                  # Pink
 Vec4(0.977, 0.816, 0.133, 1))                  # Yellow

# Position 1 (green) is the only enabled slot
ENABLED_POSITIONS = [1]
```

#### Modified Panel Creation Logic:
- Now creates all 6 panels (instead of just 1)
- Maps avatars saved in position 0 to position 1 for database compatibility
- Only allows avatar creation/selection in position 1
- Passes `enabled` parameter to AvatarChoice for disabled slots

### `toontown/login/AvatarChoice.py`

#### Added Position Arrays:
```python
NAME_ROTATIONS = (7, -11, 1, -5, 3.5, -5)
NAME_POSITIONS = ((0, 0, 0.26), (-0.03, 0, 0.25), (0, 0, 0.27), 
                  (-0.03, 0, 0.25), (0.03, 0, 0.26), (0, 0, 0.26))
DELETE_POSITIONS = ((0.187, 0, -0.26), (0.31, 0, -0.167), (0.231, 0, -0.241),
                    (0.314, 0, -0.186), (0.243, 0, -0.233), (0.28, 0, -0.207))
```

#### Added New Mode:
```python
MODE_DISABLED = 3  # New mode for inactive slots
```

#### Disabled Slot Configuration:
- Grey button color: `Vec4(0.5, 0.5, 0.5, 1)`
- Text: "DISABLED" in MinnieFont
- Text colors: Dark grey with reduced opacity
- Click handler: Does nothing (no-op)

## Database Compatibility

✅ **No database schema changes required!**

The code includes mapping logic to handle avatars saved in the old position system:
- Avatars saved in position 0 are automatically mapped to position 1 (green slot)
- This ensures existing toons load correctly without database migration

## Visual Layout

```
     [RED]        [GREEN ✅]      [PURPLE]
   DISABLED      Your Toon       DISABLED

     [BLUE]       [PINK]         [YELLOW]
   DISABLED      DISABLED        DISABLED
```

## Position Mapping

| Old System | New System | Color  | Status    |
|------------|-----------|--------|-----------|
| Position 0 | Position 1| Green  | ✅ ENABLED |
| N/A        | Position 0| Red    | DISABLED  |
| N/A        | Position 2| Purple | DISABLED  |
| N/A        | Position 3| Blue   | DISABLED  |
| N/A        | Position 4| Pink   | DISABLED  |
| N/A        | Position 5| Yellow | DISABLED  |

## Key Features

1. **All 6 slots visible** - Maintains the classic Toontown layout
2. **Only green slot functional** - Users can only create/select toons in position 1
3. **Clear visual indication** - Grey buttons with "DISABLED" text
4. **Proper text positioning** - Uses correct NAME_POSITIONS[1] for the enabled slot
5. **Database safe** - Existing toons automatically mapped to correct position
6. **No-op on click** - Clicking disabled slots does nothing

## Testing Checklist

- [ ] All 6 slots display on pick-a-toon screen
- [ ] Green slot (position 1) allows toon creation
- [ ] Green slot displays existing toon correctly
- [ ] Text on green slot is properly positioned
- [ ] All other slots show grey with "DISABLED" text
- [ ] Clicking disabled slots does nothing
- [ ] Existing toons load correctly (database compatibility)
- [ ] Delete button appears in correct position on green slot
- [ ] Name-your-toon button appears correctly
