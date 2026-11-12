"""Desktop pet: the orange pixel creature lives on your desktop.

It walks along the bottom of every screen (on top of the taskbar), leaps onto the
top edges of other windows, hangs from the top edge of maximised windows, rides
along when you move a window, and falls off when the window goes away.
Drag it with the left mouse button and let go to drop (or throw) it.
Right-click the creature: it goes away and comes back after 15 seconds.
Middle-click the creature to close the program for good.
Uses only the Python standard library (tkinter + ctypes).
"""
import ctypes
import ctypes.wintypes as wt
import math
import os
import random
import tkinter as tk

# --- Look (same sprite as the usage-window creature) ---------------------
PX = 4                              # size of one sprite pixel on the main screen (other screens: scaled
                                    # so the creature is the same physical size, see monitors())
GRID_W, GRID_H = 15, 10             # sprite size in sprite pixels (60 x 40 on screen)
BODY_COLOR = "#FF7A1A"
EYE_COLOR = "#1C1E25"
SEE_THROUGH = "#FF00FE"             # this colour is drawn as "nothing" (see-through)

BODY_ROW = "..OOOOOOOOOOO.."
ARMS_ROW = "OOOOOOOOOOOOOOO"
EMPTY_ROW = "..............."
EYES_OPEN = ("..OOEOOOOOEOO..", "..OOEOOOOOEOO..")
EYES_WIDE = ("..OEEOOOOOEEO..", "..OEEOOOOOEEO..")
EYES_SHUT = ("..OOOOOOOOOOO..", "..OEEOOOOOEEO..")
LEGS_A = "...O..O.O..O..."
LEGS_B = "..O..O...O..O.."
LEGS_SPREAD = ".O..O....O..O.."   # in the air: legs stretched out
LEGS_DANGLE = "....O.O.O.O...."   # hanging: legs close together, pointing down
HANDS_BOTH = ".O...........O."    # hanging: both arms up, holding the edge
HANDS_LEFT = ".O............."
HANDS_RIGHT = ".............O."
ARMS_UP = ".OOOOOOOOOOOOO."   # shoulders of the hanging pose

# --- Timing and movement --------------------------------------------------
TICK_MS = 30                        # movement updates about 33 times a second (smooth falling)
TICKS_PER_FRAME = 4                 # the sprite itself animates every 4 ticks (about 8 fps)
WALK_SPEED = 0.75                   # pixels per tick (about 25 px per second)
CLIMB_SPEED = 0.5                   # hand over hand along a top edge, pixels per tick
GRAVITY = 0.6                       # added to the falling speed every tick
MAX_FALL = 28                       # fastest falling speed, pixels per tick
LEAP_CHANCE = 0.3                   # after a rest: chance to leap somewhere instead of walking
LEAP_REACH = 900                    # leap only to spots at most this far away sideways
LEAP_APEX = 70                      # the leap arc goes this many pixels above the higher end
HANG_TICKS = (150, 600)             # how long it hangs before letting go (about 4 to 18 s)
GRAB_REACH = 25                     # dropped this close below a top edge: it grabs it
EDGE_TURN_CHANCE = 0.7              # at the end of a window top: turn around (otherwise walk off)
RESPAWN_MS = 15000                  # right-click: gone for this long, then it drops in from the top again
MIN_LEDGE = 30                      # ignore visible bits of window tops narrower than this

# --- Windows API -----------------------------------------------------------
user32 = ctypes.windll.user32
dwmapi = ctypes.windll.dwmapi
ENUM_PROC = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
MONITOR_PROC = ctypes.WINFUNCTYPE(wt.BOOL, wt.HMONITOR, wt.HDC, ctypes.POINTER(wt.RECT), wt.LPARAM)


class MONITORINFO(ctypes.Structure):
    _fields_ = [("cbSize", wt.DWORD), ("rcMonitor", wt.RECT), ("rcWork", wt.RECT), ("dwFlags", wt.DWORD),
                ("szDevice", ctypes.c_wchar * 32)]     # (this is MONITORINFOEXW)


gdi32 = ctypes.windll.gdi32
gdi32.CreateDCW.restype = wt.HDC
gdi32.CreateDCW.argtypes = [wt.LPCWSTR, wt.LPCWSTR, wt.LPCWSTR, ctypes.c_void_p]
gdi32.GetDeviceCaps.argtypes = [wt.HDC, ctypes.c_int]
gdi32.DeleteDC.argtypes = [wt.HDC]
HORZSIZE = 4                        # GetDeviceCaps: width of the screen in millimetres

user32.EnumWindows.argtypes = [ENUM_PROC, wt.LPARAM]
user32.EnumDisplayMonitors.argtypes = [wt.HDC, ctypes.POINTER(wt.RECT), MONITOR_PROC, wt.LPARAM]
user32.GetMonitorInfoW.argtypes = [wt.HMONITOR, ctypes.POINTER(MONITORINFO)]
user32.IsWindowVisible.argtypes = [wt.HWND]
user32.IsIconic.argtypes = [wt.HWND]
user32.GetWindowTextLengthW.argtypes = [wt.HWND]
user32.GetClassNameW.argtypes = [wt.HWND, wt.LPWSTR, ctypes.c_int]
user32.GetWindowThreadProcessId.argtypes = [wt.HWND, ctypes.POINTER(wt.DWORD)]
user32.GetWindowLongW.argtypes = [wt.HWND, ctypes.c_int]
user32.GetWindowRect.argtypes = [wt.HWND, ctypes.POINTER(wt.RECT)]
dwmapi.DwmGetWindowAttribute.argtypes = [wt.HWND, wt.DWORD, ctypes.c_void_p, wt.DWORD]

GWL_EXSTYLE = -20
WS_EX_TOOLWINDOW = 0x00000080
MONITORINFOF_PRIMARY = 1
DWMWA_EXTENDED_FRAME_BOUNDS = 9     # the window's real visible edges (without the invisible resize border)
DWMWA_CLOAKED = 14                  # "cloaked" = hidden by Windows (other virtual desktop, background apps)
SKIP_CLASSES = {"Progman", "WorkerW", "Shell_TrayWnd", "Shell_SecondaryTrayWnd"}  # desktop and taskbar
OWN_PID = os.getpid()


def enable_real_pixels():
    """Tell Windows we handle display scaling ourselves, so our pixels are real screen pixels."""
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except (AttributeError, OSError):
        try:
            user32.SetProcessDPIAware()
        except (AttributeError, OSError):
            pass


def monitors():
    """Every screen as a dict: 'screen' and 'work' are (left, top, right, bottom).

    'work' is the screen without its taskbar, so work[3] is where the creature stands.
    'ppmm' is pixels per millimetre (0 if Windows does not know the physical size).
    The main screen comes first.
    """
    found = []

    def visit(hmon, _hdc, _rect, _):
        info = MONITORINFO()
        info.cbSize = ctypes.sizeof(MONITORINFO)
        user32.GetMonitorInfoW(hmon, ctypes.byref(info))
        s, w = info.rcMonitor, info.rcWork
        ppmm = 0.0
        dc = gdi32.CreateDCW(info.szDevice, None, None, None)
        if dc:
            mm = gdi32.GetDeviceCaps(dc, HORZSIZE)
            gdi32.DeleteDC(dc)
            ppmm = (s.right - s.left) / mm if mm > 0 else 0.0
        found.append({"screen": (s.left, s.top, s.right, s.bottom),
                      "work": (w.left, w.top, w.right, w.bottom),
                      "primary": bool(info.dwFlags & MONITORINFOF_PRIMARY),
                      "ppmm": ppmm})
        return True

    user32.EnumDisplayMonitors(None, None, MONITOR_PROC(visit), 0)
    found.sort(key=lambda m: not m["primary"])
    main = found[0]["ppmm"] if found else 0.0
    for m in found:                                       # sprite pixel size that keeps the physical size
        m["px"] = max(1, round(PX * m["ppmm"] / main)) if main and m["ppmm"] else PX
    return found


def window_rect(hwnd):
    """The visible edges of a window. Falls back to GetWindowRect if DWM does not answer."""
    rect = wt.RECT()
    if dwmapi.DwmGetWindowAttribute(hwnd, DWMWA_EXTENDED_FRAME_BOUNDS,
                                    ctypes.byref(rect), ctypes.sizeof(rect)) != 0:
        user32.GetWindowRect(hwnd, ctypes.byref(rect))
    return rect.left, rect.top, rect.right, rect.bottom


def is_real_window(hwnd):
    """True for normal app windows you can see; False for hidden, minimised, tool and system windows."""
    if not user32.IsWindowVisible(hwnd) or user32.IsIconic(hwnd):
        return False
    if user32.GetWindowTextLengthW(hwnd) == 0:            # no title: usually not a real app window
        return False
    if user32.GetWindowLongW(hwnd, GWL_EXSTYLE) & WS_EX_TOOLWINDOW:
        return False
    pid = wt.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    if pid.value == OWN_PID:                              # our own window
        return False
    name = ctypes.create_unicode_buffer(64)
    user32.GetClassNameW(hwnd, name, 64)
    if name.value in SKIP_CLASSES:
        return False
    cloaked = wt.DWORD()
    dwmapi.DwmGetWindowAttribute(hwnd, DWMWA_CLOAKED, ctypes.byref(cloaked), ctypes.sizeof(cloaked))
    return cloaked.value == 0


def windows_front_to_back():
    """All real windows as (hwnd, left, top, right, bottom). EnumWindows lists the front window first."""
    found = []

    def visit(hwnd, _):
        if is_real_window(hwnd):
            found.append((hwnd,) + window_rect(hwnd))
        return True

    user32.EnumWindows(ENUM_PROC(visit), 0)
    return found


def subtract(segments, cut_left, cut_right):
    """Remove the range cut_left..cut_right from a list of (left, right) ranges."""
    out = []
    for left, right in segments:
        if cut_right <= left or cut_left >= right:        # no overlap
            out.append((left, right))
            continue
        if left < cut_left:
            out.append((left, cut_left))
        if cut_right < right:
            out.append((cut_right, right))
    return out


def intersect(segments, ranges):
    """Keep only the parts of segments that lie inside one of ranges."""
    out = []
    for left, right in segments:
        for rl, rr in ranges:
            l, r = max(left, rl), min(right, rr)
            if r > l:
                out.append((l, r))
    return out


def find_spots(wins, mons, pet_height):
    """Where the creature can be. Returns (ledges, ceilings), each a list of (key, y, [(left, right), ...]).

    ledges:   things to stand on: the bottom of every screen (key ("floor", i)) and window
              top edges with room above them (key = window handle).
    ceilings: top edges of windows with no room above (maximised or full screen): it hangs below them.
    A window's top edge only counts where no window in front of it covers that edge.
    """
    ledges = [(("floor", i), m["work"][3], [(m["work"][0], m["work"][2])]) for i, m in enumerate(mons)]
    ceilings = []
    for i, (hwnd, left, top, right, bottom) in enumerate(wins):
        if right - left < MIN_LEDGE:
            continue
        stand = [(m["work"][0], m["work"][2]) for m in mons            # screens with room above this edge
                 if m["work"][1] + pet_height <= top < m["work"][3]]
        hang = [(m["work"][0], m["work"][2]) for m in mons             # screens where this edge is at the very top
                if m["screen"][1] - 2 <= top < m["work"][1] + pet_height]
        segments = [(left, right)]
        for _, fl, ft, fr, fb in wins[:i]:                # windows in front of this one
            if ft <= top < fb:                            # it covers this window's top edge
                segments = subtract(segments, fl, fr)
        for ranges, target in ((stand, ledges), (hang, ceilings)):
            parts = [s for s in intersect(segments, ranges) if s[1] - s[0] >= MIN_LEDGE]
            if parts:
                target.append((hwnd, top, parts))
    return ledges, ceilings


def launch_speed(height):
    """Upward speed needed to rise exactly `height` pixels.

    Each tick adds GRAVITY to the speed and then moves, so the rise is v*v/(2g) - v/2
    (a bit less than the smooth-motion formula). Solving that for v gives this.
    """
    return -(GRAVITY + math.sqrt(GRAVITY * GRAVITY + 8 * GRAVITY * height)) / 2


def find_at(spots, key, x):
    """The spot with this key whose part contains x, as (y, (left, right)), or None."""
    for k, y, segments in spots:
        if k == key:
            for seg in segments:
                if seg[0] <= x <= seg[1]:
                    return y, seg
    return None


class Pet:
    def __init__(self, root):
        self.root = root
        self.px = PX
        self.w, self.h = GRID_W * self.px, GRID_H * self.px
        root.overrideredirect(True)                 # no title bar, no taskbar button
        root.attributes("-topmost", True)           # stay above other windows
        root.attributes("-transparentcolor", SEE_THROUGH)
        root.config(bg=SEE_THROUGH)
        self.gone = False                           # hidden, waiting to respawn
        self.redraw = False                         # draw at once (after the size changed)
        self.canvas = tk.Canvas(root, width=self.w, height=self.h, bg=SEE_THROUGH,
                                highlightthickness=0, bd=0)
        self.canvas.pack()
        self.canvas.bind("<Button-3>", self.vanish)                # right-click: gone for a while
        self.canvas.bind("<Button-2>", lambda e: root.destroy())   # middle-click: quit for good
        self.canvas.bind("<ButtonPress-1>", self.on_grab)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_drop)

        self.mons = monitors()
        self.wins = []
        self.ledges, self.ceilings = [], []
        left, _, right, bottom = self.mons[0]["work"]   # start on the main screen
        self.x = float(random.randint(left, max(left, right - self.w)))   # left edge of the sprite
        self.feet = float(bottom)                   # y of the bottom of the sprite
        self.vx = self.vy = 0.0
        self.airborne = False
        self.hanging = False                        # holding on below a top edge
        self.held = False                           # being dragged with the mouse
        self.on_key = ("floor", 0)                  # what it stands on or hangs from
        self.on_left = None                         # that window's left edge last tick (to ride along)
        self.facing = random.choice((-1, 1))
        self.ticks = 0
        self.frame = 0
        self.walk_left = 0                          # ticks left to walk (or climb)
        self.rest_left = 60                         # ticks left to stand still
        self.hang_left = 0                          # ticks left before letting go
        self.tick()

    # --- Where is it? -------------------------------------------------------
    def centre(self):
        return self.x + self.w / 2

    def screen_at(self, x, y):
        """The screen that contains the point, or None if the point is off every screen."""
        for m in self.mons:
            l, t, r, b = m["screen"]
            if l <= x < r and t <= y < b:
                return m
        return None

    def fits(self, x, feet):
        """True if the sprite's side at x, standing with its feet at `feet`, is over a screen (not empty space)."""
        return (self.screen_at(x, feet - 1) is not None
                and self.screen_at(x, feet - self.h + 1) is not None)

    def update_scale(self):
        """Keep the creature the same physical size on every screen (screens differ in pixels per mm)."""
        m = self.screen_at(self.centre(), self.feet - self.h / 2)
        if m is None or m["px"] == self.px:
            return
        cx, old_h = self.centre(), self.h
        self.px = m["px"]
        self.w, self.h = GRID_W * self.px, GRID_H * self.px
        self.canvas.config(width=self.w, height=self.h)
        self.x = cx - self.w / 2
        if self.hanging:
            self.feet += self.h - old_h                   # keep the hands at the edge
        self.redraw = True

    def lowest_floor_at(self, x):
        """The bottom of the screen(s) below x, or of the closest screen if x is between screens."""
        floors = [(i, m["work"][3]) for i, m in enumerate(self.mons) if m["work"][0] <= x < m["work"][2]]
        if not floors:
            i = min(range(len(self.mons)), key=lambda i: min(abs(x - self.mons[i]["work"][0]),
                                                           abs(x - self.mons[i]["work"][2])))
            floors = [(i, self.mons[i]["work"][3])]
        return max(floors, key=lambda f: f[1])

    def landing_between(self, y_from, y_to):
        """The first ledge crossed when falling from y_from to y_to: (y, key) or None."""
        cx = self.centre()
        best = None
        for key, y, segments in self.ledges:
            if y_from <= y <= y_to and any(l <= cx <= r for l, r in segments):
                if best is None or y < best[0]:
                    best = (y, key)
        return best

    def ceiling_near(self, top_from, top_to):
        """A ceiling the top of the sprite passes between top_from and top_to: (y, key) or None."""
        cx = self.centre()
        lo, hi = min(top_from, top_to), max(top_from, top_to)
        for key, y, segments in self.ceilings:
            if lo <= y <= hi and any(l <= cx <= r for l, r in segments):
                return y, key
        return None

    # --- Changing state -------------------------------------------------------
    def start_falling(self, vx=0.0, vy=0.0):
        self.airborne, self.hanging = True, False
        self.on_key = None
        self.vx, self.vy = vx, vy

    def attach(self, key):
        """Remember where the window it is now on sits, so it can ride along when it moves."""
        self.on_key = key
        self.on_left = next((w[1] for w in self.wins if w[0] == key), None)
        self.vx = self.vy = 0.0
        self.walk_left = 0

    def land(self, y, key):
        self.airborne, self.hanging = False, False
        self.feet = float(y)
        self.attach(key)
        self.rest_left = random.randint(20, 60)        # catch its breath after landing

    def grab(self, y, key):
        self.airborne, self.hanging = False, True
        self.feet = float(y + self.h)                   # hands at the edge, body below it
        self.attach(key)
        self.rest_left = random.randint(10, 40)
        self.hang_left = random.randint(*HANG_TICKS)

    # --- Movement -------------------------------------------------------------
    def fly(self):
        """One tick of flying or falling: gravity, then check for something to grab or land on."""
        left = min(m["screen"][0] for m in self.mons)
        right = max(m["screen"][2] for m in self.mons)
        self.vy = min(self.vy + GRAVITY, MAX_FALL)
        self.x += self.vx
        if self.x < left or self.x + self.w > right:      # bounce off the outer screen edges
            self.x = max(left, min(self.x, right - self.w))
            self.vx = -self.vx * 0.5
        new_feet = self.feet + self.vy
        if self.vy < 0:                                   # going up: grab a top edge it reaches
            hit = self.ceiling_near(self.feet - self.h, new_feet - self.h)
            if hit:
                self.grab(*hit)
                return
        else:                                             # only land on the way down (jump up through edges)
            hit = self.landing_between(self.feet, new_feet)
            if hit:
                self.land(*hit)
                return
        self.feet = new_feet
        index, floor = self.lowest_floor_at(self.centre())
        if self.feet > floor:                             # fell below the screens (e.g. between two of them)
            self.land(floor, ("floor", index))
            return
        if self.vx:
            self.facing = 1 if self.vx > 0 else -1

    def leap(self):
        """Jump in an arc to a random window top or ceiling. Returns False if there is nothing in reach."""
        cx = self.centre()
        spots = []
        for kind, spots_list in (("stand", self.ledges), ("hang", self.ceilings)):
            for key, y, segments in spots_list:
                if key == self.on_key or (kind == "hang" and y >= self.feet - self.h):
                    continue
                for l, r in segments:
                    tx = random.uniform(l + 10, r - 10)
                    if abs(tx - cx) <= LEAP_REACH:
                        spots.append((kind, tx, y))
        if not spots:
            return False
        kind, tx, ty = random.choice(spots)
        if kind == "hang":
            # Peak just above the edge, so the hands reach it on the way up
            vy = launch_speed(self.feet - (ty + self.h - 12))
            flight = -vy / GRAVITY
        else:
            apex = min(self.feet, ty) - LEAP_APEX            # highest point of the arc
            vy = launch_speed(self.feet - apex)
            flight = -vy / GRAVITY + math.sqrt(2 * (ty - apex) / GRAVITY)
        self.start_falling((tx - cx) / flight, vy)
        return True

    def walk(self):
        """One tick on the ground: walk or rest, and handle the end of what it stands on."""
        spot = find_at(self.ledges, self.on_key, self.centre())
        if spot is None:                                  # window closed, minimised or covered: fall
            self.start_falling()
            return False
        y, (seg_l, seg_r) = spot
        self.feet = float(y)                              # follows the window or taskbar up and down
        if not self.fits(self.x, self.feet):              # half of it hangs over empty space: slide back on
            self.x += 2
            self.facing = 1
            return True
        if not self.fits(self.x + self.w - 1, self.feet):
            self.x -= 2
            self.facing = -1
            return True
        if self.walk_left > 0:
            self.walk_left -= 1
            step = WALK_SPEED * self.facing
            new_cx = self.centre() + step
            if not self.fits(new_cx + self.facing * (self.w / 2 - 1), self.feet):
                self.facing = -self.facing                # the body would go over the edge of the screens: turn
                return True
            if not seg_l <= new_cx <= seg_r:              # reached the end
                beyond = self.screen_at(new_cx, self.feet - 1)
                on_floor = isinstance(self.on_key, tuple)
                if beyond is None or (not on_floor and random.random() < EDGE_TURN_CHANCE):
                    self.facing = -self.facing            # screen edge, or it decided to turn around
                    return True
                self.x += step                            # walk off and fall (onto the next screen, too)
                self.start_falling(WALK_SPEED * self.facing * 2, -2)
                return True
            self.x += step
            if self.walk_left == 0:
                self.rest_left = random.randint(30, 150)
            return True
        self.rest_left -= 1
        if self.rest_left <= 0:
            if random.random() < LEAP_CHANCE and self.leap():
                return False
            self.walk_left = random.randint(80, 300)
            if random.random() < 0.4:
                self.facing = -self.facing
        return False

    def hang(self):
        """One tick hanging below a top edge: climb hand over hand, rest, and let go after a while."""
        spot = find_at(self.ceilings, self.on_key, self.centre())
        if spot is None:                                  # the window is gone or moved down: drop
            self.start_falling()
            return False
        y, (seg_l, seg_r) = spot
        self.feet = float(y + self.h)
        if self.walk_left > 0 and not self.fits(self.centre() + self.facing * (CLIMB_SPEED + self.w / 2 - 1), self.feet):
            self.facing = -self.facing                    # the body would go over the edge of the screens
        self.hang_left -= 1
        if self.hang_left <= 0:
            self.start_falling()                          # let go
            return False
        if self.walk_left > 0:
            self.walk_left -= 1
            step = CLIMB_SPEED * self.facing
            if not seg_l <= self.centre() + step <= seg_r:
                self.facing = -self.facing
                return True
            self.x += step
            if self.walk_left == 0:
                self.rest_left = random.randint(30, 120)
            return True
        self.rest_left -= 1
        if self.rest_left <= 0:
            self.walk_left = random.randint(60, 200)
            if random.random() < 0.4:
                self.facing = -self.facing
        return False

    def ride(self):
        """If the window it is on moved sideways, move with it."""
        for hwnd, left, top, right, bottom in self.wins:
            if hwnd == self.on_key:
                if self.on_left is not None:
                    self.x += left - self.on_left
                self.on_left = left
                return

    # --- Vanishing and respawning ---------------------------------------------
    def vanish(self, _event=None):
        self.gone = True
        self.held = False
        self.root.withdraw()
        self.root.after(RESPAWN_MS, self.respawn)

    def respawn(self):
        """Drop in from the top of the main screen at a random spot."""
        left, top, right, _ = self.mons[0]["work"]
        self.px = PX
        self.w, self.h = GRID_W * self.px, GRID_H * self.px
        self.canvas.config(width=self.w, height=self.h)
        self.x = float(random.randint(left, right - self.w))
        self.feet = float(top + self.h)
        self.start_falling()
        self.facing = random.choice((-1, 1))
        self.rest_left = 30
        self.redraw = True
        self.gone = False
        self.root.deiconify()
        self.root.attributes("-topmost", True)

    # --- Mouse ------------------------------------------------------------
    def on_grab(self, e):
        self.held = True
        self.hanging = False
        self.grab_dx, self.grab_dy = e.x_root - self.x, e.y_root - self.feet
        self.last_mouse = (e.x_root, e.y_root)
        self.throw = (0.0, 0.0)

    def on_drag(self, e):
        lx, ly = self.last_mouse
        self.throw = (e.x_root - lx, e.y_root - ly)      # how fast the mouse moved: used for a throw
        self.last_mouse = (e.x_root, e.y_root)
        self.x = e.x_root - self.grab_dx
        self.feet = e.y_root - self.grab_dy

    def on_drop(self, e):
        self.held = False
        top = self.feet - self.h
        # let go just below a top edge, or with his head above it (dragged to the very top): hold on
        hit = self.ceiling_near(top - GRAB_REACH, top + GRAB_REACH)
        if hit:
            self.grab(*hit)
            return
        vx, vy = (max(-25, min(25, v)) for v in self.throw)
        self.start_falling(vx, vy)

    # --- Drawing ------------------------------------------------------------
    def sprite_rows(self, moving):
        """The 10 rows of the sprite for this frame."""
        f = self.frame
        in_air = self.airborne or self.held
        if in_air:
            eyes = EYES_WIDE
        elif f % 32 in (30, 31):                         # blink about every 4 s
            eyes = EYES_SHUT
        else:
            eyes = EYES_OPEN
        if self.hanging:
            if moving:                                   # hand over hand: one hand reaches forward at a time
                hands = HANDS_LEFT if (f // 2) % 2 == 0 else HANDS_RIGHT
            else:
                hands = HANDS_BOTH
            rows = [hands, HANDS_BOTH, ARMS_UP, eyes[0], eyes[1], BODY_ROW, BODY_ROW, BODY_ROW,
                    LEGS_DANGLE, LEGS_DANGLE if f % 8 < 4 else LEGS_A]   # legs sway a little
        else:
            if in_air:
                bob, legs = 0, (LEGS_SPREAD, LEGS_SPREAD)
            elif moving:
                bob = f % 2
                legs = (LEGS_A, LEGS_B) if (f // 2) % 2 == 0 else (LEGS_B, LEGS_A)
            else:
                bob = (f // 4) % 2
                legs = (LEGS_A, LEGS_A)
            body = [BODY_ROW, eyes[0], eyes[1], ARMS_ROW, ARMS_ROW, BODY_ROW, BODY_ROW]
            rows = [EMPTY_ROW] * GRID_H
            top = 1 - bob
            for i, row in enumerate(body):
                rows[top + i] = row
            rows[8], rows[9] = legs
        if self.facing < 0:
            rows = [r[::-1] for r in rows]
        return rows

    def draw(self, rows):
        c = self.canvas
        c.delete("all")
        colors = {"O": BODY_COLOR, "E": EYE_COLOR}
        for y, row in enumerate(rows):
            for x, ch in enumerate(row):
                if ch in colors:
                    c.create_rectangle(x * self.px, y * self.px, (x + 1) * self.px, (y + 1) * self.px,
                                       fill=colors[ch], outline="")

    # --- Main loop ----------------------------------------------------------
    def tick(self):
        if self.gone:                                     # hidden: just wait
            self.root.after(TICK_MS, self.tick)
            return
        self.mons = monitors()                            # screens and taskbars can change
        self.wins = windows_front_to_back()
        self.update_scale()
        self.ledges, self.ceilings = find_spots(self.wins, self.mons, self.h)
        moving = False
        if not self.held:
            if self.airborne:
                self.fly()
            else:
                self.ride()
                moving = self.hang() if self.hanging else self.walk()
        if self.ticks % TICKS_PER_FRAME == 0 or self.redraw:
            self.redraw = False
            self.frame += 1
            self.draw(self.sprite_rows(moving))
        self.root.geometry(f"{self.w}x{self.h}+{round(self.x)}+{round(self.feet) - self.h}")
        self.ticks += 1
        self.root.after(TICK_MS, self.tick)


if __name__ == "__main__":
    enable_real_pixels()
    root = tk.Tk()
    Pet(root)
    root.mainloop()
