# Typotrix 2.0

A typographic display app for Raspberry Pi + HyperPixel 4 Square (720×720 touch).
Cycles through Google Fonts, displaying 4-letter words in a 2×2 grid.
Variable fonts animate between thin and bold weights in a sine-wave breathing cycle.

---

## Hardware

| Component | Spec |
|---|---|
| Board | Raspberry Pi 3B |
| Display | Pimoroni HyperPixel 4 Square (720×720, touch) |
| OS | Raspberry Pi OS Lite 64-bit (Trixie / Debian 13) |
| Power | 5V / 2.5A micro-USB minimum (throttling occurs below this) |

---

## Features

- 2×2 grid of large glyphs spelling 4-letter words (TYPE, KERN, FLUX, etc.)
- Pulls font list from Google Fonts API sorted by popularity
- Variable fonts fetched as full TTFs from the `google/fonts` GitHub repo
- Weight animation: pre-renders 5 instances (thin → bold), animates via sine wave over 6s
- Static fonts (non-variable) display with staggered letter reveal
- Colour circles: long-press to anchor, drag to size, release to commit
- Colormind API for palette-aware circle colours
- Invert mode: long-press centre of screen

## Touch Controls

| Gesture | Action |
|---|---|
| Tap right half | Next font |
| Tap left half | Previous font |
| Long press (350ms) off-centre | Draw colour circle — drag to set size |
| Long press (350ms) centre | Toggle invert |

## Keyboard (dev/SSH)

| Key | Action |
|---|---|
| → | Next font |
| ← | Previous font |
| Esc | Quit |

---

## Project Structure

```
typotrix.py     — main app
install.sh      — Pi 3B + HyperPixel 4 Square setup script
requirements.txt
.gitignore
fonts/          — downloaded font cache (gitignored)
font_instances/ — pre-rendered weight instances (gitignored)
```

---

## Pi Setup (fresh install)

```bash
# 1. Clone repo
git clone https://github.com/miloze/Typotrix_2.0.git ~/typotrix

# 2. Run install script (handles drivers, X stack, autostart)
cd ~/typotrix
chmod +x install.sh
./install.sh

# 3. Reboot
sudo reboot
```

The app autostarts on boot via `.xinitrc` → `startx` → `matchbox-window-manager`.

### HyperPixel 4 Square config.txt entry (already applied by install.sh)

```
dtoverlay=vc4-kms-dpi-hyperpixel4sq
display_auto_detect=0
```

Touch optional params (add to the overlay line if needed):

```
touchscreen-swapped-x-y   # swap axes
touchscreen-inverted-x    # flip x
touchscreen-inverted-y    # flip y
```

---

## Dependencies

```
pygame >= 2.1.0
requests >= 2.28.0
fonttools >= 4.28.0
brotli >= 1.0.0       # WOFF2 support
```

Install on Pi:
```bash
sudo apt-get install -y python3-pygame python3-requests
pip3 install --break-system-packages fonttools brotli
```

---

## SSH Access

Pi is on the local network as `typotrix2` (mDNS may not resolve — use IP).

```bash
# Find Pi MAC (b8:27:eb prefix = RPi Foundation)
arp -a | grep b8:27:eb

ssh milo@192.168.1.227
# password: see local notes
```

---

## Known Issues / Next Steps

- **Variable font instancing is slow on first load** — `instantiateVariableFont` +
  `copy.deepcopy` on large fonts (Roboto Flex ~3MB) takes 30–60s per font.
  Fix: pre-generate instances at install time via a separate script, not at runtime.

- **Power** — Pi 3B + HyperPixel draws ~1.5A under load. Use a quality 5V/2.5A
  supply with a short cable. Undervoltage causes CPU throttling and slow font loading.

- **mDNS** — `typotrix.local` doesn't resolve reliably. Use IP address for SSH.

- **Killing the app over SSH** — `pkill typotrix.py` kills the X session (app is
  `exec`'d from `.xinitrc`). Use `sudo reboot` to restart cleanly.

---

## API Keys

- **Google Fonts API** — key hardcoded in `typotrix.py`. Replace with your own from
  [Google Cloud Console](https://console.cloud.google.com/) if the key is revoked.
- **Colormind** — no key required, public API.

---

## Variable Font Pipeline

1. `fetch_variable_font_items()` — queries GitHub API (`google/fonts` repo) for TTF
   filenames containing `[` (axis tags), confirming they are variable fonts.
2. `download_font()` — downloads the full TTF (not a web subset) direct from GitHub raw CDN.
3. `get_wght_from_file()` — reads `fvar` table to confirm wght axis and get min/max range.
4. `build_weight_instances()` — loads TTFont once, pins all axes to defaults except wght,
   generates 5 static TTF instances spaced across the wght range. Disk-cached in `~/font_instances/`.
5. `VariableScene` — pre-renders each glyph at each weight step into cell-sized canvases,
   animates by alpha-blending adjacent frames driven by a sine oscillator.
