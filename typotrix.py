#!/usr/bin/env python3
"""
Typotrix 2.0 — Variable Font Edition
Raspberry Pi 3B + HyperPixel 4 Square (720×720 touch)

Touch:  tap left  → next font
        tap right → prev font
        long-press center       → invert colours
        long-press off-centre   → grow colour circle
"""

import pygame
import requests
import re
import os
import random
import json
import math
import urllib.request

os.environ['SDL_AUDIODRIVER'] = 'dummy'
os.environ['DISPLAY'] = ':0'

# ── Variable font support ─────────────────────────────────────────────────────
try:
    from fontTools.ttLib import TTFont
    from fontTools.varLib.instancer import instantiateVariableFont
    HAS_FONTTOOLS = True
except ImportError:
    try:
        from fontTools.ttLib import TTFont
        from fontTools.varLib.mutator import instantiateVariableFont
        HAS_FONTTOOLS = True
    except ImportError:
        HAS_FONTTOOLS = False

# ── Config ────────────────────────────────────────────────────────────────────
API_KEY      = "AIzaSyCltIMLz8FERwlYfYPOPlj0tzM4GneDbhg"
SCREEN_SIZE  = (720, 720)
FONT_CACHE   = os.path.expanduser("~/fonts")
INST_CACHE   = os.path.expanduser("~/font_instances")
WEIGHT_STEPS = 5      # pre-rendered frames thin → bold
ANIM_PERIOD  = 6.0    # seconds for one full thin → bold → thin cycle

os.makedirs(FONT_CACHE, exist_ok=True)
os.makedirs(INST_CACHE, exist_ok=True)

WEIGHT_PRIORITY = [
    "900italic", "900", "800italic", "800", "700italic", "700",
    "600italic", "600", "500italic", "500", "italic", "regular",
    "400italic", "400", "300italic", "300", "200italic", "200",
    "100italic", "100",
]

# Browser UA required to receive WOFF2 variable fonts from Google Fonts CSS2 API
CHROME_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

# Curated variable fonts: (display name, google/fonts repo dir, license subdir)
# GitHub repo has full TTFs with variation data intact
VARIABLE_FAMILIES = [
    ("Roboto Flex",       "robotoflex",        "ofl"),
    ("Recursive",         "recursive",         "ofl"),
    ("Fraunces",          "fraunces",          "ofl"),
    ("Raleway",           "raleway",           "ofl"),
    ("Figtree",           "figtree",           "ofl"),
    ("Crimson Pro",       "crimsonpro",        "ofl"),
    ("Syne",              "syne",              "ofl"),
    ("Anybody",           "anybody",           "ofl"),
    ("Encode Sans",       "encodesans",        "ofl"),
    ("Manrope",           "manrope",           "ofl"),
    ("Nunito",            "nunito",            "ofl"),
    ("Jost",              "jost",              "ofl"),
    ("Outfit",            "outfit",            "ofl"),
    ("Urbanist",          "urbanist",          "ofl"),
    ("Cabin",             "cabin",             "apache"),
    ("Inter",             "inter",             "ofl"),
    ("DM Sans",           "dmsans",            "ofl"),
    ("Plus Jakarta Sans", "plusjakartasans",   "ofl"),
]

EXCLUDE_FONTS = {
    "material symbols outlined", "material symbols rounded",
    "material symbols sharp", "material icons", "material icons outlined",
    "material icons round", "material icons sharp", "material icons two tone",
    "noto emoji", "noto color emoji",
}

WORDS = [
    "TYPE", "KERN", "GRID", "FLUX", "BOLD", "GLYPH", "INK", "LEAD",
    "FONT", "FORM", "MARK", "AXIS", "BEAM", "CROP", "DASH", "EDGE",
    "FACE", "GRIT", "HEFT", "JOIN", "KNOT", "LIFT", "MESH", "NODE",
    "OPEN", "PATH", "QUAD", "RULE", "SLAB", "THIN", "UNIT", "VOID",
    "WAVE", "XRAY", "YARD", "ZERO", "APEX", "BARE", "COAT", "DIRE",
    "EMIT", "FINE", "GRIP", "HARD", "IRON", "JUST", "KEEN", "LOOP",
    "MAST", "NEON", "OVAL", "PINE", "QUAT", "RIFT", "SCAN", "TILT",
    "URGE", "VANE", "WARP", "XACT", "YOKE", "ZONE", "ARCH", "BLOC",
    "CORD", "DUCT", "EXPO", "FOLD", "GLOW", "HALO", "IDEA", "JOLT",
    "KNOB", "LACE", "MINT", "NULL", "ORBS", "PEAK", "QUIT", "RING",
    "SLOT", "TRIM", "UPON", "VENT", "WIRE", "ZOOM", "ALTO", "BASS",
    "CLEF", "DEEP", "ECHO", "FLAT", "GLUE", "HOOK", "OPUS", "PULSE",
]

# ── Colour ────────────────────────────────────────────────────────────────────
def get_colormind_color():
    try:
        req = urllib.request.Request(
            "http://colormind.io/api/",
            data=json.dumps({"model": "default"}).encode(),
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=3) as r:
            data = json.loads(r.read())
            return tuple(random.choice(data["result"]))
    except Exception:
        return (random.randint(30, 255), random.randint(30, 255), random.randint(30, 255))

# ── Easing ────────────────────────────────────────────────────────────────────
def ease_in_out(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)

# ── Google Fonts API ──────────────────────────────────────────────────────────
def get_github_vf_url(dir_name, license_dir="ofl"):
    """
    Fetch the download URL for a variable font TTF from the google/fonts GitHub repo.
    Variable font filenames contain '[' (axis tags), e.g. Roboto[wght].ttf.
    """
    api_url = f"https://api.github.com/repos/google/fonts/contents/{license_dir}/{dir_name}"
    try:
        r = requests.get(api_url, timeout=8)
        if r.status_code != 200:
            return None
        files = r.json()
        # Prefer TTFs with axis tags in the filename (variable fonts)
        for f in files:
            if f["name"].endswith(".ttf") and "[" in f["name"]:
                return f["download_url"]
        # Fallback: any TTF
        for f in files:
            if f["name"].endswith(".ttf"):
                return f["download_url"]
    except Exception as e:
        print(f"GitHub API error ({dir_name}): {e}")
    return None

def fetch_variable_font_items():
    """Resolve variable font download URLs via the Google Fonts GitHub repo."""
    items = []
    for family, dir_name, license_dir in VARIABLE_FAMILIES:
        safe = os.path.join(FONT_CACHE, f"{family.replace(' ', '_')}_variable.ttf")
        if os.path.exists(safe):
            # Already downloaded — infer wght range from fvar
            wght = get_wght_from_file(safe)
            if wght:
                items.append({
                    "family": family, "_use": "variable",
                    "_is_variable": True,
                    "_wght_min": wght[0], "_wght_max": wght[1],
                    "_vf_url": None, "_vf_path": safe,
                })
                print(f"  VF cached: {family} wght {wght[0]}–{wght[1]}")
            continue

        url = get_github_vf_url(dir_name, license_dir)
        if url:
            items.append({
                "family": family, "_use": "variable",
                "_is_variable": True,
                "_wght_min": 100, "_wght_max": 900,  # will be refined after download
                "_vf_url": url,
            })
            print(f"  VF: {family} → {url.split('/')[-1]}")
        else:
            print(f"  VF not found: {family}")
    return items

def get_fonts():
    url = (
        f"https://www.googleapis.com/webfonts/v1/webfonts"
        f"?key={API_KEY}&sort=popularity"
    )
    r = requests.get(url)
    data = r.json()
    static = []
    for f in data["items"]:
        if f["family"].lower() in EXCLUDE_FONTS:
            continue
        for w in WEIGHT_PRIORITY:
            if w in f["files"]:
                f["_use"] = w
                f["_is_variable"] = False
                static.append(f)
                break

    variable = fetch_variable_font_items()
    print(f"{len(variable)} variable fonts, {len(static)} static fonts")

    # Interleave: 1 variable font per 3 static
    result = []
    vi = si = 0
    while vi < len(variable) or si < len(static):
        if vi < len(variable):
            result.append(variable[vi]); vi += 1
        for _ in range(3):
            if si < len(static):
                result.append(static[si]); si += 1
    return result

def get_wght_from_file(path):
    """Check a font file for an fvar wght axis. Returns (min, max) or None."""
    if not HAS_FONTTOOLS:
        return None
    try:
        tt = TTFont(path)
        if "fvar" not in tt:
            return None
        for axis in tt["fvar"].axes:
            if axis.axisTag == "wght":
                return int(axis.minValue), int(axis.maxValue)
    except Exception:
        pass
    return None

# ── Font download ─────────────────────────────────────────────────────────────
def download_font(font_item):
    family = font_item["family"]
    safe   = family.replace(" ", "_")

    # Variable font — use cached path or download from GitHub
    if font_item.get("_is_variable"):
        if "_vf_path" in font_item:
            return font_item["_vf_path"]
        path = os.path.join(FONT_CACHE, f"{safe}_variable.ttf")
        if not os.path.exists(path) and font_item.get("_vf_url"):
            try:
                r = requests.get(font_item["_vf_url"], timeout=20)
                r.raise_for_status()
                with open(path, "wb") as fh:
                    fh.write(r.content)
                # Refine wght range now we have the actual file
                wght = get_wght_from_file(path)
                if wght:
                    font_item["_wght_min"], font_item["_wght_max"] = wght
            except Exception as e:
                print(f"Variable download failed {family}: {e}")
                return None
        return path if os.path.exists(path) else None

    # Static font — download TTF via v1 API files dict
    weight = font_item.get("_use", "regular")
    path   = os.path.join(FONT_CACHE, f"{safe}_{weight}.ttf")
    if not os.path.exists(path):
        try:
            url = font_item["files"][weight]
            r = requests.get(url, timeout=8)
            r.raise_for_status()
            with open(path, "wb") as fh:
                fh.write(r.content)
        except Exception as e:
            print(f"Download failed {family}: {e}")
            if os.path.exists(path):
                os.remove(path)
            return None
    try:
        pygame.font.Font(path, 100)
        return path
    except Exception:
        print(f"Font unreadable, skipping: {path}")
        os.remove(path)
        return None

# ── Variable font instancing ──────────────────────────────────────────────────
def build_weight_instances(vf_path, wght_min, wght_max, family):
    """
    Return WEIGHT_STEPS static TTF paths spanning wght_min → wght_max.
    Loads the source font once and pins ALL axes for fastest instancing.
    Results are disk-cached so subsequent scene loads are instant.
    """
    import copy
    safe   = family.replace(" ", "_")
    wghts  = [
        round(wght_min + i / (WEIGHT_STEPS - 1) * (wght_max - wght_min))
        for i in range(WEIGHT_STEPS)
    ]
    paths  = [os.path.join(INST_CACHE, f"{safe}_{w}.ttf") for w in wghts]

    # Return immediately if all already cached
    if all(os.path.exists(p) for p in paths):
        return paths

    # Load source font once
    try:
        tt_base   = TTFont(vf_path)
        # Collect default values for every axis so we fully instantiate
        axis_defaults = {a.axisTag: a.defaultValue for a in tt_base["fvar"].axes}
    except Exception as e:
        print(f"Font load failed: {e}")
        return None

    for wght, out in zip(wghts, paths):
        if os.path.exists(out):
            continue
        try:
            tt = copy.deepcopy(tt_base)
            axes = dict(axis_defaults)
            axes["wght"] = wght          # vary only weight
            instantiateVariableFont(tt, axes)
            tt.save(out)
            print(f"  instanced wght={wght}")
        except Exception as e:
            print(f"  instance failed wght={wght}: {e}")
            return None

    return paths

# ── Font sizing ───────────────────────────────────────────────────────────────
def find_font_size(font_path, ch, max_w, max_h, scale=1.4):
    lo, hi = 10, 900
    best = lo
    while lo <= hi:
        mid = (lo + hi) // 2
        try:
            f = pygame.font.Font(font_path, mid)
        except Exception:
            f = pygame.font.SysFont("monospace", mid)
        w, h = f.size(ch)
        if w <= max_w and h <= max_h:
            best = mid
            lo = mid + 1
        else:
            hi = mid - 1
    sized = int(best * scale)
    try:
        return pygame.font.Font(font_path, sized)
    except Exception:
        return pygame.font.SysFont("monospace", sized)

def find_font_size_px(font_path, ch, max_w, max_h, scale=1.4):
    """Same as find_font_size but returns the integer pixel size."""
    lo, hi = 10, 900
    best = lo
    while lo <= hi:
        mid = (lo + hi) // 2
        try:
            f = pygame.font.Font(font_path, mid)
        except Exception:
            f = pygame.font.SysFont("monospace", mid)
        w, h = f.size(ch)
        if w <= max_w and h <= max_h:
            best = mid
            lo = mid + 1
        else:
            hi = mid - 1
    return int(best * scale)

# ── Loading screen ────────────────────────────────────────────────────────────
def draw_loading(screen, font, font_name, inverted, detail=""):
    bg = (255, 255, 255) if inverted else (0, 0, 0)
    fg = (80, 80, 80) if inverted else (160, 160, 160)
    screen.fill(bg)
    msg = font.render(f"loading  {font_name}...", True, fg)
    screen.blit(
        msg,
        (SCREEN_SIZE[0] // 2 - msg.get_width() // 2,
         SCREEN_SIZE[1] // 2 - msg.get_height() // 2 - (10 if detail else 0)),
    )
    if detail:
        d = font.render(detail, True, fg)
        screen.blit(d, (SCREEN_SIZE[0] // 2 - d.get_width() // 2,
                        SCREEN_SIZE[1] // 2 + 10))
    pygame.display.flip()

# ── Scenes ────────────────────────────────────────────────────────────────────
class Scene:
    """Static scene for non-variable fonts — identical behaviour to 1.x."""

    def __init__(self, letters, label, circle):
        self.letters = letters    # [(Surface, x, y), ...]
        self.label = label
        self.circle = circle
        self.order = list(range(len(letters)))
        random.shuffle(self.order)
        self.shown = 0
        self.show_timer = 0.0
        self.show_interval = 0.08

    def update(self, dt):
        self.show_timer += dt
        while self.show_timer >= self.show_interval and self.shown < len(self.order):
            self.show_timer -= self.show_interval
            self.shown += 1

    def draw(self, screen, inverted, growing_circle=None):
        bg = (255, 255, 255) if inverted else (0, 0, 0)
        screen.fill(bg)

        if self.circle:
            cx, cy, cr, colour = self.circle
            pygame.draw.circle(screen, colour, (cx, cy), max(1, cr))
        if growing_circle:
            cx, cy, cr, colour = growing_circle
            if cr > 1:
                pygame.draw.circle(screen, colour, (cx, cy), int(cr))

        for i in self.order[:self.shown]:
            surf, x, y = self.letters[i]
            screen.blit(surf, (x, y))

        if self.label:
            lsurf, lx, ly, lalpha = self.label
            lsurf.set_alpha(lalpha)
            screen.blit(lsurf, (lx, ly))


class VariableScene:
    """
    Weight-morphing scene for variable fonts.

    Pre-renders every glyph at WEIGHT_STEPS instances into fixed cell-sized
    SRCALPHA canvases, then alpha-blends adjacent frames each tick — zero
    font work at runtime.
    """

    def __init__(self, frames, positions, label, circle):
        # frames[step_idx][letter_idx] = pygame.Surface (cell_w × cell_h, SRCALPHA)
        self.frames = frames
        self.positions = positions    # [(cell_x, cell_y), ...] top-left of each cell
        self.label = label
        self.circle = circle
        self.anim_time = random.uniform(0, ANIM_PERIOD)  # randomise phase per scene
        self.order = list(range(len(positions)))
        random.shuffle(self.order)
        self.shown = 0
        self.show_timer = 0.0
        self.show_interval = 0.08

    def update(self, dt):
        self.anim_time += dt
        self.show_timer += dt
        while self.show_timer >= self.show_interval and self.shown < len(self.order):
            self.show_timer -= self.show_interval
            self.shown += 1

    def draw(self, screen, inverted, growing_circle=None):
        bg = (255, 255, 255) if inverted else (0, 0, 0)
        screen.fill(bg)

        if self.circle:
            cx, cy, cr, colour = self.circle
            pygame.draw.circle(screen, colour, (cx, cy), max(1, cr))
        if growing_circle:
            cx, cy, cr, colour = growing_circle
            if cr > 1:
                pygame.draw.circle(screen, colour, (cx, cy), int(cr))

        # Sine oscillation: 0 (thin) → 1 (bold) → 0 (thin)
        phase = (math.sin(self.anim_time * 2 * math.pi / ANIM_PERIOD) + 1) / 2
        frame_pos = phase * (len(self.frames) - 1)
        f0 = int(frame_pos)
        f1 = min(f0 + 1, len(self.frames) - 1)
        blend = frame_pos - f0

        for i in self.order[:self.shown]:
            x, y = self.positions[i]
            s0 = self.frames[f0][i]

            if blend > 0.01 and f1 != f0:
                # Cross-fade between weight frames
                composite = s0.copy()
                s1_tmp = self.frames[f1][i].copy()
                s1_tmp.set_alpha(int(blend * 255))
                composite.blit(s1_tmp, (0, 0))
                screen.blit(composite, (x, y))
            else:
                screen.blit(s0, (x, y))

        if self.label:
            lsurf, lx, ly, lalpha = self.label
            lsurf.set_alpha(lalpha)
            screen.blit(lsurf, (lx, ly))

# ── Scene builder ─────────────────────────────────────────────────────────────
def build_scene(fonts, fi, ui_font, inverted, screen, case_cache, circle=None):
    fg        = (0, 0, 0)       if inverted else (255, 255, 255)
    label_fg  = (80, 80, 80)    if inverted else (160, 160, 160)

    # Download font, skipping broken ones
    attempts = 0
    path = None
    font_item = None
    while path is None and attempts < 10:
        font_item = fonts[fi % len(fonts)]
        draw_loading(screen, ui_font, font_item["family"], inverted)
        path = download_font(font_item)
        if path is None:
            fi += 1
        attempts += 1

    if path is None:
        return None, fi

    family      = font_item["family"]
    is_variable = font_item.get("_is_variable", False)
    wght_min    = font_item.get("_wght_min", 400)
    wght_max    = font_item.get("_wght_max", 400)

    print(f"Font: {family} ({'variable' if is_variable else font_item.get('_use','regular')}) idx={fi}")

    cols, rows = 2, 2
    label_h = 27
    cell_w = SCREEN_SIZE[0] // cols
    cell_h = (SCREEN_SIZE[1] - label_h) // rows

    # Stable word + digit for this font slot
    if fi not in case_cache:
        word  = random.choice(WORDS)
        upper = random.random() < 0.5
        case_cache[fi] = [ch.upper() if upper else ch.lower() for ch in word[:4]]
    chars = list(case_cache[fi])

    char_grid = [chars[:2], chars[2:]]    # [[row0_ch0, row0_ch1], [row1_ch0, row1_ch1]]

    # ── Variable font ─────────────────────────────────────────────────────────
    if is_variable and HAS_FONTTOOLS:
        draw_loading(screen, ui_font, family, inverted, "generating weights…")
        pygame.event.pump()

        instances = build_weight_instances(path, wght_min, wght_max, family)
        if instances is not None:
            # Use the boldest instance to determine font size (most space-constrained)
            bold_path = instances[-1]
            char_px = {
                ch: find_font_size_px(bold_path, ch, cell_w, cell_h, scale=1.4)
                for ch in chars
            }

            # Pre-render all weight steps
            frames = []
            for step_i, inst_path in enumerate(instances):
                draw_loading(
                    screen, ui_font, family, inverted,
                    f"weight {step_i + 1}/{len(instances)}…",
                )
                pygame.event.pump()

                step_surfs = []
                for ri, row in enumerate(char_grid):
                    for ci, ch in enumerate(row):
                        px = char_px[ch]
                        try:
                            font = pygame.font.Font(inst_path, px)
                        except Exception:
                            font = pygame.font.SysFont("monospace", px)
                        glyph  = font.render(ch, True, fg)
                        canvas = pygame.Surface((cell_w, cell_h), pygame.SRCALPHA)
                        canvas.fill((0, 0, 0, 0))
                        gx = (cell_w - glyph.get_width())  // 2
                        gy = (cell_h - glyph.get_height()) // 2
                        canvas.blit(glyph, (gx, gy))
                        step_surfs.append(canvas)
                frames.append(step_surfs)

            positions = [
                (ci * cell_w, ri * cell_h)
                for ri in range(rows)
                for ci in range(cols)
            ]

            label_text = f"{family} / wght {wght_min}–{wght_max}"
            lsurf = ui_font.render(label_text, True, label_fg)
            lx = SCREEN_SIZE[0] // 2 - lsurf.get_width() // 2
            ly = SCREEN_SIZE[1] - label_h + 4
            label = (lsurf, lx, ly, 180)

            return VariableScene(frames, positions, label, circle), fi

        # Instance generation failed — fall through to static render
        print(f"  instancing failed, rendering static")

    # ── Static font ───────────────────────────────────────────────────────────
    letters = []
    for ri, row in enumerate(char_grid):
        for ci, ch in enumerate(row):
            font = find_font_size(path, ch, cell_w, cell_h, scale=1.4)
            surf = font.render(ch, True, fg)
            w, h = surf.get_size()
            x = ci * cell_w + (cell_w - w) // 2
            y = ri * cell_h + (cell_h - h) // 2
            letters.append((surf, x, y))

    weight_label = font_item.get("_use", "regular")
    label_text   = f"{family} / {weight_label}"
    lsurf = ui_font.render(label_text, True, label_fg)
    lx = SCREEN_SIZE[0] // 2 - lsurf.get_width() // 2
    ly = SCREEN_SIZE[1] - label_h + 4
    label = (lsurf, lx, ly, 180)

    return Scene(letters, label, circle), fi

# ── Main loop ─────────────────────────────────────────────────────────────────
def main():
    pygame.init()
    screen = pygame.display.set_mode(SCREEN_SIZE)
    pygame.display.set_caption("typotrix")
    clock = pygame.time.Clock()

    if not HAS_FONTTOOLS:
        print("WARNING: fonttools not installed — variable font animation disabled.")
        print("  pip3 install fonttools")

    print("Fetching fonts…")
    fonts = get_fonts()
    print(f"{len(fonts)} fonts loaded")

    ui_font    = pygame.font.SysFont("monospace", 14)
    font_index = 0
    inverted   = False
    case_cache = {}
    circle     = None

    scene, font_index = build_scene(
        fonts, font_index, ui_font, inverted, screen, case_cache, circle
    )

    touches          = {}
    long_press_fired = set()
    LONG_PRESS_MS = 350
    CENTER_ZONE   = 0.1
    CIRCLE_MAX_R  = int(math.sqrt(SCREEN_SIZE[0] ** 2 + SCREEN_SIZE[1] ** 2))  # screen diagonal

    running = True
    while running:
        dt  = clock.tick(30) / 1000.0
        dt  = min(dt, 0.05)
        now = pygame.time.get_ticks()

        growing_circle = None

        for fid, t in list(touches.items()):
            held_ms   = now - t["start_time"]
            cur_x     = 1.0 - t.get("cur_x", t["start_x"])   # invert x to match screen
            cur_y     = t.get("cur_y", t["start_y"])
            is_center = (abs(cur_x - 0.5) < CENTER_ZONE
                         and abs(cur_y - 0.5) < CENTER_ZONE)

            if held_ms >= LONG_PRESS_MS:
                if fid not in long_press_fired:
                    long_press_fired.add(fid)
                    if is_center:
                        inverted = not inverted
                        scene, font_index = build_scene(
                            fonts, font_index, ui_font, inverted,
                            screen, case_cache, circle,
                        )
                    else:
                        # Anchor circle at the press point (raw coords = screen coords)
                        ax = int(t["start_x"] * SCREEN_SIZE[0])
                        ay = int(t["start_y"] * SCREEN_SIZE[1])
                        t["circle_colour"]  = get_colormind_color()
                        t["circle_anchor"]  = (ax, ay)

                if not is_center and "circle_anchor" in t:
                    ax, ay = t["circle_anchor"]
                    fx = int(t.get("cur_x", t["start_x"]) * SCREEN_SIZE[0])
                    fy = int(t.get("cur_y", t["start_y"]) * SCREEN_SIZE[1])
                    r  = min(math.sqrt((fx - ax) ** 2 + (fy - ay) ** 2), CIRCLE_MAX_R)
                    growing_circle = (ax, ay, r, t["circle_colour"])

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_RIGHT:
                    font_index += 1
                    circle = None
                    scene, font_index = build_scene(
                        fonts, font_index, ui_font, inverted, screen, case_cache, circle
                    )
                elif event.key == pygame.K_LEFT:
                    font_index = max(0, font_index - 1)
                    circle = None
                    scene, font_index = build_scene(
                        fonts, font_index, ui_font, inverted, screen, case_cache, circle
                    )

            elif event.type == pygame.FINGERDOWN:
                touches[event.finger_id] = {
                    "start_x":    event.x,
                    "start_y":    event.y,
                    "cur_x":      event.x,
                    "cur_y":      event.y,
                    "start_time": now,
                }

            elif event.type == pygame.FINGERMOTION:
                if event.finger_id in touches:
                    touches[event.finger_id]["cur_x"] = event.x
                    touches[event.finger_id]["cur_y"] = event.y

            elif event.type == pygame.FINGERUP:
                if event.finger_id not in touches:
                    continue
                t        = touches.pop(event.finger_id)
                was_long = event.finger_id in long_press_fired
                long_press_fired.discard(event.finger_id)

                if was_long:
                    if growing_circle:
                        cx, cy, cr, colour = growing_circle
                        circle = (cx, cy, max(1, int(cr)), colour)
                        if scene:
                            scene.circle = circle
                        print(f"CIRCLE COMMITTED r={int(cr)}")
                else:
                    circle = None
                    if t["start_x"] < 0.5:
                        font_index = max(0, font_index - 1)
                    else:
                        font_index += 1
                    scene, font_index = build_scene(
                        fonts, font_index, ui_font, inverted, screen, case_cache, circle
                    )

        if scene:
            scene.update(dt)
            scene.draw(screen, inverted, growing_circle)

        pygame.display.flip()

    pygame.quit()


if __name__ == "__main__":
    main()
