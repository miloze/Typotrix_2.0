#!/bin/bash
# Typotrix 2.0 — Pi 3B + HyperPixel 4 Square setup
# Run as regular user (sudo will be invoked where needed)
set -e

echo "=== Typotrix 2.0 install ==="
echo ""

# ── System packages ───────────────────────────────────────────────────────────
echo "[1/5] Updating packages..."
sudo apt-get update -q
sudo apt-get install -y \
    python3-pip \
    python3-pygame \
    python3-requests \
    git \
    xserver-xorg \
    xinit \
    matchbox-window-manager \
    unclutter

# ── Python dependencies ───────────────────────────────────────────────────────
echo "[2/5] Installing Python dependencies..."
pip3 install --break-system-packages fonttools requests

# ── HyperPixel 4 Square drivers ───────────────────────────────────────────────
echo "[3/5] Installing HyperPixel 4 Square drivers..."
if [ ! -d "$HOME/hyperpixel4" ]; then
    git clone https://github.com/pimoroni/hyperpixel4 "$HOME/hyperpixel4"
fi
cd "$HOME/hyperpixel4"
sudo ./install.sh --variant=square-non-touch
# NOTE: HyperPixel 4 Square touch uses a separate overlay.
# If your unit is touch-enabled, edit /boot/firmware/config.txt after reboot and
# change: dtoverlay=hyperpixel4-square
# to:     dtoverlay=hyperpixel4-square,touchscreen-swapped-x-y
cd -

# ── X session autostart ───────────────────────────────────────────────────────
echo "[4/5] Setting up autostart..."

cat > "$HOME/.xinitrc" << 'XINITRC'
#!/bin/sh
xset s off
xset -dpms
xset s noblank
unclutter -idle 0 &
matchbox-window-manager -use_titlebar no &
exec python3 /home/$USER/typotrix/typotrix.py
XINITRC

# Auto-login and startx on boot
PROFILE="$HOME/.bash_profile"
if ! grep -q "startx" "$PROFILE" 2>/dev/null; then
    cat >> "$PROFILE" << 'PROFILE_EOF'

# Auto-start X on tty1
if [ -z "$DISPLAY" ] && [ "$(tty)" = "/dev/tty1" ]; then
    startx
fi
PROFILE_EOF
fi

sudo raspi-config nonint do_boot_behaviour B2   # auto login to CLI

# ── Font caches ───────────────────────────────────────────────────────────────
echo "[5/5] Creating font cache directories..."
mkdir -p "$HOME/fonts" "$HOME/font_instances"

echo ""
echo "=== Done ==="
echo ""
echo "Copy typotrix.py to ~/typotrix/typotrix.py then:"
echo "  sudo reboot"
echo ""
echo "The display will require a reboot to activate the HyperPixel overlay."
echo "If touch axes are swapped after reboot, edit /boot/firmware/config.txt:"
echo "  dtoverlay=hyperpixel4-square,touchscreen-swapped-x-y"
