"""Desktop pet: the orange pixel creature lives on your desktop.

It walks along the bottom of every screen (on top of the taskbar), leaps onto the
top edges of other windows, hangs from the top edge of maximised windows, rides
along when you move a window, and falls off when the window goes away.
Drag it with the left mouse button and let go to drop (or throw) it.
Right-click the creature: it goes away and comes back after 15 seconds.
Shift + right-click: choose his colour. Ctrl + right-click (or middle-click): close the program for good.
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
# Colours to choose from (Shift + right-click): name, body colour, eye colour. The first is the original.
# Every start picks one at random.
PALETTE = [
    ("Orange", "#FF7A1A", "#1C1E25"),
    ("Blue", "#3B8BFF", "#12182B"),
    ("Sky", "#6FD3FF", "#12202B"),
    ("Teal", "#19C3B1", "#0F2623"),
    ("Green", "#3DDC84", "#10261A"),
    ("Lime", "#B6E83A", "#202A0C"),
    ("Yellow", "#FFD23F", "#2B2410"),
    ("Pink", "#FF6FB5", "#2B1220"),
    ("Red", "#F0454A", "#2B1011"),
    ("Purple", "#9B59FF", "#1A1030"),
    ("White", "#F2F2F2", "#1C1E25"),
    ("Black", "#26262E", "#F2F2F2"),
]
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
WALL_SLIDE = 1.0                    # sliding down a wall, pixels per tick
WALL_CLIMB = 1.2                    # climbing up a wall, pixels per tick
WALL_REACH = GRAB_REACH             # dropped this close to a wall: it grabs it
WALL_GRAB_CHANCE = 0.4              # chance to catch a wall it passes (walking into it or falling past it)
CLIMB_SHARE = 0.4                   # when it would leap: this share of the time it climbs a window side instead
MIN_WALL = 40                       # ignore bits of wall shorter than this
FAV_CLASS = "TkTopLevel"            # untitled Tk windows of other programs (the usage window): its favourite place
FAV_STAY = 0.60                    # when it is not on the favourite window: chance to head there after a rest
FAV_HOP = 0.5                       # when it is on it: chance to hop to another spot on it after a rest
FAV_TURN_CHANCE = 0.97              # at the end of its favourite window: turn around (rather than walk off)
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

user32.ShowWindow.argtypes = [wt.HWND, ctypes.c_int]
user32.GetForegroundWindow.restype = wt.HWND
user32.GetParent.argtypes = [wt.HWND]
user32.GetParent.restype = wt.HWND
user32.SetWindowLongW.argtypes = [wt.HWND, ctypes.c_int, ctypes.c_long]
user32.SetWindowPos.argtypes = [wt.HWND, wt.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wt.UINT]

GWL_EXSTYLE = -20
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_TOPMOST = 0x00000008
WS_EX_NOACTIVATE = 0x08000000       # clicking it never makes it the active window
SW_HIDE, SW_SHOWNOACTIVATE = 0, 4   # show/hide without taking the focus
SWP_NOSIZE, SWP_NOMOVE, SWP_NOZORDER, SWP_NOACTIVATE, SWP_FRAMECHANGED = 0x1, 0x2, 0x4, 0x10, 0x20
HWND_TOPMOST = -1
MONITORINFOF_PRIMARY = 1
DWMWA_EXTENDED_FRAME_BOUNDS = 9     # the window's real visible edges (without the invisible resize border)
DWMWA_CLOAKED = 14                  # "cloaked" = hidden by Windows (other virtual desktop, background apps)
SKIP_CLASSES = {"Progman", "WorkerW", "Shell_TrayWnd", "Shell_SecondaryTrayWnd"}  # desktop and taskbar
OWN_PID = os.getpid()


def blend(colour, other, amount):
    """Mix two '#rrggbb' colours: amount 0 gives colour, 1 gives other."""
    a = [int(colour[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(other[i:i + 2], 16) for i in (1, 3, 5)]
    return "#%02x%02x%02x" % tuple(round(x + (y - x) * amount) for x, y in zip(a, b))


def is_light(colour):
    r, g, b = (int(colour[i:i + 2], 16) for i in (1, 3, 5))
    return 0.299 * r + 0.587 * g + 0.114 * b > 150


def rounded(canvas, x1, y1, x2, y2, r, **kw):
    """A rectangle with rounded corners on a canvas (radius r). Returns the item id."""
    pts = [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2, x2 - r, y2,
           x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]
    return canvas.create_polygon(pts, smooth=True, **kw)


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
    name = ctypes.create_unicode_buffer(64)
    user32.GetClassNameW(hwnd, name, 64)
    # no title: usually not a real app window (but small Tk tools such as the usage window have none)
    if user32.GetWindowTextLengthW(hwnd) == 0 and name.value != "TkTopLevel":
        return False
    if user32.GetWindowLongW(hwnd, GWL_EXSTYLE) & WS_EX_TOOLWINDOW:
        return False
    pid = wt.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    if pid.value == OWN_PID:                              # our own window
        return False
    if name.value in SKIP_CLASSES:
        return False
    cloaked = wt.DWORD()
    dwmapi.DwmGetWindowAttribute(hwnd, DWMWA_CLOAKED, ctypes.byref(cloaked), ctypes.sizeof(cloaked))
    return cloaked.value == 0


FAVOURITES = set()                  # handles of the favourite windows seen by the last windows_front_to_back()


def taskbar_on_top(screen):
    """True if a taskbar is showing above other windows on this screen (it is the creature's floor)."""
    found = []

    def visit(hwnd, _):
        name = ctypes.create_unicode_buffer(64)
        user32.GetClassNameW(hwnd, name, 64)
        if name.value in ("Shell_TrayWnd", "Shell_SecondaryTrayWnd") and user32.IsWindowVisible(hwnd):
            r = wt.RECT()
            user32.GetWindowRect(hwnd, ctypes.byref(r))
            cx, cy = (r.left + r.right) // 2, (r.top + r.bottom) // 2
            if screen[0] <= cx < screen[2] and screen[1] <= cy < screen[3]                     and user32.GetWindowLongW(hwnd, GWL_EXSTYLE) & WS_EX_TOPMOST:
                found.append(hwnd)
        return True

    user32.EnumWindows(ENUM_PROC(visit), 0)
    return bool(found)


def foreground_is_fullscreen(mons):
    """True if the window in front really is full screen (video, game, F11 browser) and hides the taskbar.

    Windows sometimes leaves the taskbar showing over a full-screen window; then the creature stays."""
    hwnd = user32.GetForegroundWindow()
    if not hwnd or not user32.IsWindowVisible(hwnd):
        return False
    pid = wt.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    if pid.value == OWN_PID:
        return False
    name = ctypes.create_unicode_buffer(64)
    user32.GetClassNameW(hwnd, name, 64)
    if name.value in SKIP_CLASSES:                        # the desktop itself fills the screen
        return False
    if name.value == "Chrome_WidgetWin_1":                # Chrome / Claude app: full screen still counts as a window
        return False
    left, top, right, bottom = window_rect(hwnd)
    for m in mons:
        sl, st, sr, sb = m["screen"]
        if left <= sl + 1 and top <= st + 1 and right >= sr - 1 and bottom >= sb - 1:
            return not taskbar_on_top(m["screen"])
    return False


def windows_front_to_back():
    """All real windows as (hwnd, left, top, right, bottom). EnumWindows lists the front window first."""
    found = []
    FAVOURITES.clear()

    def visit(hwnd, _):
        if is_real_window(hwnd):
            found.append((hwnd,) + window_rect(hwnd))
            name = ctypes.create_unicode_buffer(64)
            user32.GetClassNameW(hwnd, name, 64)
            if name.value == FAV_CLASS:
                FAVOURITES.add(hwnd)
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
    ceilings: top edges of windows with no room above (maximised or full screen) and bottom edges of
              windows with room below them (key (hwnd, "B")): it hangs below them.
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
        # the bottom edge of a window that floats above the taskbar: stand on it (inside the window)
        floats = [(m["work"][0], m["work"][2]) for m in mons
                  if m["work"][1] + pet_height <= bottom < m["work"][3] - 3]
        segments = [(left, right)]
        for _, fl, ft, fr, fb in wins[:i]:
            if ft <= bottom < fb:
                segments = subtract(segments, fl, fr)
        parts = [s for s in intersect(segments, floats) if s[1] - s[0] >= MIN_LEDGE]
        if parts:
            ledges.append(((hwnd, "B"), bottom, parts))
        # ... or hang from it, below the window, if there is room under it
        under = [(m["work"][0], m["work"][2]) for m in mons
                 if m["work"][1] <= bottom and bottom + pet_height <= m["work"][3]]
        parts = [s for s in intersect(segments, under) if s[1] - s[0] >= MIN_LEDGE]
        if parts:
            ceilings.append(((hwnd, "B"), bottom, parts))
    return ledges, ceilings


def find_walls(wins, mons):
    """Vertical edges it can hang on and slide down: a list of (key, x, [(top, bottom), ...], sides).

    sides says on which side of the edge the creature's body may hang: +1 = to the right of the edge,
    -1 = to the left. Outer screen edges only count from the inside; window sides from both sides.
    A window side only counts where no window in front covers it. Key: ("screen", i, "L"/"R") or (hwnd, "L"/"R").
    """
    walls = []
    for i, m in enumerate(mons):
        left, _, right, _ = m["screen"]
        for x, side, tag in ((left, 1, "L"), (right, -1, "R")):
            segs = [(m["work"][1], m["work"][3])]
            for o in mons:                                # another screen next to this edge hides it
                if o is not m and (o["screen"][2] == x if side > 0 else o["screen"][0] == x):
                    segs = subtract(segs, o["screen"][1], o["screen"][3])
            segs = [g for g in segs if g[1] - g[0] >= MIN_WALL]
            if segs:
                walls.append((("screen", i, tag), x, segs, (side,)))
    edges = [m["screen"][0] for m in mons] + [m["screen"][2] for m in mons]
    for i, (hwnd, left, top, right, bottom) in enumerate(wins):
        for x, tag in ((left, "L"), (right, "R")):
            if any(abs(x - e) <= 8 for e in edges):       # maximised and snapped windows: the screen edge does it
                continue
            segs = []
            for m in mons:
                if m["screen"][0] <= x < m["screen"][2]:
                    lo, hi = max(top, m["work"][1]), min(bottom, m["work"][3])
                    if hi > lo:
                        segs.append((lo, hi))
            for _, fl, ft, fr, fb in wins[:i]:
                if fl <= x < fr:
                    segs = subtract(segs, ft, fb)
            segs = [g for g in segs if g[1] - g[0] >= MIN_WALL]
            if segs:
                walls.append(((hwnd, tag), x, segs, (-1, 1)))
    return walls


def launch_speed(height):
    """Upward speed needed to rise exactly `height` pixels.

    Each tick adds GRAVITY to the speed and then moves, so the rise is v*v/(2g) - v/2
    (a bit less than the smooth-motion formula). Solving that for v gives this.
    """
    return -(GRAVITY + math.sqrt(GRAVITY * GRAVITY + 8 * GRAVITY * height)) / 2


def window_of(key):
    """The window handle a spot key belongs to: hwnd, (hwnd, "B"/"L"/"R"), or None for floors and screens."""
    if isinstance(key, tuple):
        return key[0] if len(key) == 2 and not isinstance(key[0], str) else None
    return key


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
        self.fs_hidden = False                      # hidden because a full-screen window is in front
        self.menu = None                            # the colour menu while it is open
        self.colour = random.choice(PALETTE)
        self.redraw = False                         # draw at once (after the size changed)
        self.canvas = tk.Canvas(root, width=self.w, height=self.h, bg=SEE_THROUGH,
                                highlightthickness=0, bd=0)
        self.canvas.pack()
        root.update_idletasks()
        self.make_unobtrusive()
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
        self.walls = []
        self.wall = 0                               # clinging to a wall: side of the body (+1 right of it, -1 left)
        self.wall_key = None
        self.wall_mode = "hold"                     # hold / slide / climb
        self.wall_left = 0                          # ticks left before letting go
        self.wall_mode_left = 0
        self.wall_cool = 0                          # ticks before it may catch another wall while walking
        self.goal_wall = None                       # a wall it is walking to on purpose, to climb it
        self.climb_to_top = False                   # climbing on purpose: keeps going up to the top
        self.can_grab = True                        # may catch a wall while flying
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
        if self.hanging or self.wall:
            self.feet += self.h - old_h                   # keep the hands where they are
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
    def start_falling(self, vx=0.0, vy=0.0, grab=WALL_GRAB_CHANCE):
        self.airborne, self.hanging, self.wall = True, False, 0
        self.can_grab = random.random() < grab
        self.on_key = None
        self.vx, self.vy = vx, vy

    def attach(self, key):
        """Remember where the window it is now on sits, so it can ride along when it moves."""
        self.on_key = key
        self.on_left = next((w[1] for w in self.wins if w[0] == window_of(key)), None)
        self.vx = self.vy = 0.0
        self.walk_left = 0

    def land(self, y, key):
        self.airborne, self.hanging, self.wall = False, False, 0
        self.feet = float(y)
        self.attach(key)
        self.rest_left = random.randint(20, 60)        # catch its breath after landing

    def grab(self, y, key):
        self.airborne, self.hanging, self.wall = False, True, 0
        self.feet = float(y + self.h)                   # hands at the edge, body below it
        self.attach(key)
        self.rest_left = random.randint(10, 40)
        self.hang_left = random.randint(*HANG_TICKS)

    # --- Favourite window ---------------------------------------------------------
    def favourite(self):
        """The handle of the favourite window if one is open, else None."""
        return next((w[0] for w in self.wins if w[0] in FAVOURITES), None)

    def stay_near(self, fav):
        """After a rest: stay on or around the favourite window. Returns True if it did something."""
        on_it = window_of(self.on_key) == fav
        if on_it:
            if random.random() < FAV_HOP:
                if random.random() < CLIMB_SHARE and self.plan_climb(fav):
                    return True
                return self.leap(fav)
            return False
        if random.random() >= FAV_STAY:
            return False
        if self.leap(fav):                                    # in reach: jump straight to it
            return True
        win = next(w for w in self.wins if w[0] == fav)       # too far: walk towards it
        self.facing = 1 if (win[1] + win[3]) / 2 > self.centre() else -1
        self.walk_left = 400
        return True

    # --- Walls ------------------------------------------------------------------
    def hand_x(self, side, x=None):
        """x of the hand that holds a wall, for a body on `side` of it (+1 right of the wall, -1 left)."""
        x = self.x if x is None else x
        return x + 1.5 * self.px if side > 0 else x + self.w - 1.5 * self.px

    def wall_x(self, side, wall_x):
        """Left edge of the sprite so that its hand is on the wall."""
        return wall_x - 1.5 * self.px if side > 0 else wall_x - self.w + 1.5 * self.px

    def wall_crossed(self, old_x, new_x, covering):
        """A wall the hand passes when the sprite moves from old_x to new_x: (key, x, side) or None.

        covering: the wall must reach from the head down to the feet (walking up to it);
        otherwise the hands just have to be next to some part of it (flying past it).
        """
        if old_x == new_x:
            return None
        for key, wx, segs, sides in self.walls:
            for s in sides:
                if (self.hand_x(s, old_x) - wx) * s >= 0 >= (self.hand_x(s, new_x) - wx) * s:
                    if covering:
                        ok = any(a <= self.feet - self.h + 6 and b >= self.feet - 6 for a, b in segs)
                    else:
                        y = self.feet - self.h + self.px
                        ok = any(a - 4 <= y <= b for a, b in segs)
                    if ok:
                        return key, wx, s
        return None

    def near_wall(self):
        """The wall closest to the hands when dropped: (key, x, side) or None."""
        y = self.feet - self.h
        best = None
        for key, wx, segs, sides in self.walls:
            if not any(a - 6 <= y <= b for a, b in segs):
                continue
            s = 1 if self.centre() > wx else -1
            if s not in sides:
                continue
            d = abs(self.hand_x(s) - wx)
            if d <= WALL_REACH and (best is None or d < best[0]):
                best = (d, key, wx, s)
        return best and best[1:]

    def set_wall_mode(self, mode=None):
        if self.climb_to_top:
            mode = "climb"
        self.wall_mode = mode or random.choices(("hold", "slide", "climb"), (25, 40, 35))[0]
        self.wall_mode_left = random.randint(60, 200)

    def grab_wall(self, key, wx, side, mode=None):
        self.airborne, self.hanging = False, False
        self.wall, self.wall_key = side, key
        self.x = self.wall_x(side, wx)
        self.attach(key)
        self.wall_left = random.randint(*HANG_TICKS)
        self.climb_to_top = key == self.goal_wall         # it came here to climb: no giving up half way
        self.set_wall_mode(mode)
        self.goal_wall = None

    def let_go_wall(self):
        self.climb_to_top = False
        self.start_falling(self.wall * 1.5, 0.0, grab=0)  # pushes away from the wall; no catching it again

    def cling(self):
        """One tick on a wall: hold on, slide down or climb up. Returns True while it moves."""
        entry = next((w for w in self.walls if w[0] == self.wall_key), None)
        if entry is None or self.wall not in entry[3]:        # the window moved away or closed
            self.let_go_wall()
            return False
        _, wx, segs, _ = entry
        y = self.feet - self.h
        seg = next(((a, b) for a, b in segs if a - 6 <= y <= b), None)
        if seg is None:
            self.let_go_wall()
            return False
        self.x = self.wall_x(self.wall, wx)                   # follows the window when it moves
        if not self.climb_to_top:
            self.wall_left -= 1
        if self.wall_left <= 0:
            self.let_go_wall()
            return False
        self.wall_mode_left -= 1
        if self.wall_mode_left <= 0:
            self.set_wall_mode()
        if self.wall_mode == "slide":
            new_feet = self.feet + WALL_SLIDE
            hit = self.landing_between(self.feet, new_feet)   # reached something to stand on
            if hit:
                self.land(*hit)
                return False
            self.feet = new_feet
            if self.feet - self.h > seg[1]:                   # slid off the bottom of the wall
                self.let_go_wall()
            return True
        if self.wall_mode == "climb":
            self.feet -= WALL_CLIMB
            if self.feet - self.h <= seg[0]:
                self.top_of_wall(wx, seg)
            return True
        return False

    def top_of_wall(self, wx, seg):
        """Climbed to the top of a wall: pull up onto the window's top edge if it has one, else turn around."""
        key = self.wall_key
        self.climb_to_top = False
        if not isinstance(key[0], str):                       # a window side (not a screen edge)
            ledge = next((l for l in self.ledges if l[0] == key[0]), None)
            if ledge and abs(ledge[1] - seg[0]) <= 3:
                cx = wx + (14 if key[1] == "L" else -14)      # a little way in from the corner
                if any(l <= cx <= r for l, r in ledge[2]):
                    self.x = cx - self.w / 2
                    self.land(ledge[1], key[0])
                    return
        self.set_wall_mode("slide")

    def plan_climb(self, only_window=None):
        """Walk to the side of a window on this level, to climb it instead of jumping. False if none."""
        spot = find_at(self.ledges, self.on_key, self.centre())
        if spot is None:
            return False
        _, (seg_l, seg_r) = spot
        cx = self.centre()
        options = []
        for key, wx, segs, sides in self.walls:
            if isinstance(key[0], str) or not any(l[0] == key[0] for l in self.ledges):
                continue                                      # only windows that have a top to climb to
            if only_window is not None and key[0] != only_window:
                continue
            if not seg_l <= wx <= seg_r or abs(wx - cx) > LEAP_REACH:
                continue
            if not any(a <= self.feet - self.h + 6 and b >= self.feet - 6 for a, b in segs):
                continue                                      # the side must reach down to where it stands
            options.append((key, -1 if wx > cx else 1))
        if not options:
            return False
        self.goal_wall, side = random.choice(options)
        self.facing = -side
        self.walk_left = 400
        return True

    # --- Movement -------------------------------------------------------------
    def fly(self):
        """One tick of flying or falling: gravity, then check for something to grab or land on."""
        left = min(m["screen"][0] for m in self.mons)
        right = max(m["screen"][2] for m in self.mons)
        self.vy = min(self.vy + GRAVITY, MAX_FALL)
        old_x = self.x
        self.x += self.vx
        if self.can_grab and self.vx:                     # flying past a wall: it may catch hold
            hit = self.wall_crossed(old_x, self.x, covering=False)
            if hit:
                self.grab_wall(*hit)
                return
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

    def leap(self, only_window=None):
        """Jump in an arc to a random window top or ceiling. Returns False if there is nothing in reach.

        only_window: jump only to spots that belong to this window."""
        cx = self.centre()
        spots = []
        for kind, spots_list in (("stand", self.ledges), ("hang", self.ceilings)):
            for key, y, segments in spots_list:
                if key == self.on_key or (kind == "hang" and y >= self.feet - self.h):
                    continue
                if only_window is not None and window_of(key) != only_window:
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
            if self.wall_cool > 0:
                self.wall_cool -= 1
            else:                                         # walking up to a wall: maybe climb it
                hit = self.wall_crossed(self.x, self.x + step + self.facing * 1.5 * self.px, covering=True)   # looks one hand ahead
                if hit and hit[2] == -self.facing:
                    if hit[0] == self.goal_wall or random.random() < WALL_GRAB_CHANCE:
                        self.grab_wall(*hit, mode="climb")
                        return True
                    self.wall_cool = 60
            if not self.fits(new_cx + self.facing * (self.w / 2 - 1), self.feet):
                self.facing = -self.facing                # the body would go over the edge of the screens: turn
                return True
            if not seg_l <= new_cx <= seg_r:              # reached the end
                wkey = (self.on_key, "R" if self.facing > 0 else "L")
                entry = next((w for w in self.walls if w[0] == wkey), None)
                if entry and isinstance(self.on_key, int) and random.random() < WALL_GRAB_CHANCE:
                    top = min(g[0] for g in entry[2])     # climb down: hang from the corner and slide
                    if abs(top - y) <= 3:
                        self.grab_wall(wkey, entry[1], self.facing, mode="slide")
                        self.feet = top + self.h + 4
                        return True
                beyond = self.screen_at(new_cx, self.feet - 1)
                on_floor = isinstance(self.on_key, tuple) and self.on_key[0] in ("floor", "screen")
                on_fav = window_of(self.on_key) == self.favourite() and self.favourite() is not None
                chance = FAV_TURN_CHANCE if on_fav else EDGE_TURN_CHANCE
                if beyond is None or (not on_floor and random.random() < chance):
                    self.facing = -self.facing            # screen edge, or it decided to turn around
                    return True
                self.x += step                            # walk off and fall (onto the next screen, too)
                self.start_falling(WALK_SPEED * self.facing * 2, -2)
                return True
            self.x += step
            if self.walk_left == 0:
                self.rest_left = random.randint(30, 150)
                self.goal_wall = None
            return True
        self.rest_left -= 1
        if self.rest_left <= 0:
            fav = self.favourite()
            if fav is not None and self.stay_near(fav):
                return False
            if fav is None and random.random() < LEAP_CHANCE:
                if random.random() < CLIMB_SHARE and self.plan_climb():
                    return False
                if self.leap():
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
            if hwnd == window_of(self.on_key):
                if self.on_left is not None:
                    self.x += left - self.on_left
                self.on_left = left
                return

    # --- Staying out of the way -------------------------------------------------
    def native_window(self):
        inner = self.root.winfo_id()
        return user32.GetParent(inner) or inner

    def make_unobtrusive(self):
        """The creature's window never takes the focus, and is not a normal app window."""
        hwnd = self.native_window()
        style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style | WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW)
        user32.SetWindowPos(hwnd, None, 0, 0, 0, 0,
                            SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE | SWP_FRAMECHANGED)

    def raise_to_top(self):
        """Other topmost windows (the usage window) jump above us when clicked: step back in front, no focus."""
        user32.SetWindowPos(self.native_window(), HWND_TOPMOST, 0, 0, 0, 0,
                            SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE)

    def set_visible(self, visible):
        user32.ShowWindow(self.native_window(), SW_SHOWNOACTIVATE if visible else SW_HIDE)

    # --- Vanishing and respawning ---------------------------------------------
    def vanish(self, event=None):
        if event is not None and event.state & 0x0004:    # Ctrl held: quit for good
            self.root.destroy()
            return
        if event is not None and event.state & 0x0001:    # Shift held: colour menu
            self.open_menu(event)
            return
        self.gone = True
        self.held = False
        self.set_visible(False)
        self.root.after(RESPAWN_MS, self.respawn)

    # --- Colour menu ----------------------------------------------------------
    def open_menu(self, event):
        self.close_menu()
        row_w, row_h, gap, pad = 104, 18, 2, 6
        n = len(PALETTE)
        w = row_w + 2 * pad
        h = n * row_h + (n - 1) * gap + 2 * pad
        menu = tk.Toplevel(self.root)
        menu.overrideredirect(True)
        menu.attributes("-topmost", True)
        menu.attributes("-transparentcolor", SEE_THROUGH)     # the corners outside the rounded panel
        menu.config(bg=SEE_THROUGH)
        c = tk.Canvas(menu, width=w, height=h, bg=SEE_THROUGH, highlightthickness=0, bd=0)
        c.pack()
        rounded(c, 0, 0, w - 1, h - 1, 11, fill="#15171D", outline="#3A3D48")
        for i, (name, body, eye) in enumerate(PALETTE):
            y = pad + i * (row_h + gap)
            tag = f"row{i}"
            box = rounded(c, pad, y, pad + row_w, y + row_h, 6, fill=body, outline="", tags=(tag,))
            mark = "✓  " if name == self.colour[0] else "     "
            c.create_text(pad + 9, y + row_h / 2, text=mark + name, anchor="w", tags=(tag,),
                          fill="#14161C" if is_light(body) else "#FFFFFF", font=("Segoe UI", 8, "bold"))
            c.tag_bind(tag, "<Enter>", lambda e, b=box, col=body: c.itemconfig(b, fill=blend(col, "#FFFFFF", 0.18)))
            c.tag_bind(tag, "<Leave>", lambda e, b=box, col=body: c.itemconfig(b, fill=col))
            c.tag_bind(tag, "<Button-1>", lambda e, ch=(name, body, eye): self.choose_colour(ch))
        c.config(cursor="arrow")
        menu.bind("<Escape>", lambda e: self.close_menu())
        menu.bind("<Button-1>", lambda e: self.close_menu() if not self.inside_menu(e) else None)
        scr = self.screen_at(event.x_root, event.y_root) or self.mons[0]
        sl, st, sr, sb = scr["screen"]
        x = max(sl, min(event.x_root, sr - w))
        y = max(st, min(event.y_root, sb - h))
        menu.geometry(f"{w}x{h}+{x}+{y}")
        self.menu = menu
        menu.after(20, self.grab_menu)

    def grab_menu(self):
        if self.menu is not None:
            try:
                self.menu.focus_force()
                self.menu.grab_set()                      # clicks outside the menu come to it, to close it
            except tk.TclError:
                pass

    def inside_menu(self, e):
        m = self.menu
        return (m.winfo_rootx() <= e.x_root < m.winfo_rootx() + m.winfo_width()
                and m.winfo_rooty() <= e.y_root < m.winfo_rooty() + m.winfo_height())

    def close_menu(self):
        if self.menu is not None:
            try:
                self.menu.grab_release()
                self.menu.destroy()
            except tk.TclError:
                pass
            self.menu = None

    def choose_colour(self, colour):
        self.colour = colour
        self.redraw = True
        self.close_menu()

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
        self.fs_hidden = foreground_is_fullscreen(self.mons)
        self.set_visible(not self.fs_hidden)

    # --- Mouse ------------------------------------------------------------
    def on_grab(self, e):
        self.held = True
        self.hanging = False
        self.wall = 0
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
        near = self.near_wall()                           # let go next to a wall: hold on to it
        if near:
            self.grab_wall(*near)
            return
        vx, vy = (max(-25, min(25, v)) for v in self.throw)
        self.start_falling(vx, vy, grab=1.0)

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
        if self.wall:                                    # on a wall: one hand up on it, legs dangling
            if self.wall_mode == "climb" and moving and (f // 2) % 2 == 1:
                top = EMPTY_ROW                          # reaching up: the top hand lets go for a moment
            else:
                top = HANDS_LEFT
            legs = LEGS_DANGLE if f % 8 < 4 else LEGS_A
            rows = [top, HANDS_LEFT, ARMS_UP, eyes[0], eyes[1], BODY_ROW, BODY_ROW, BODY_ROW,
                    LEGS_DANGLE, legs]
        elif self.hanging:
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
        if (self.wall < 0) if self.wall else (self.facing < 0):
            rows = [r[::-1] for r in rows]
        return rows

    def draw(self, rows):
        c = self.canvas
        c.delete("all")
        colors = {"O": self.colour[1], "E": self.colour[2]}
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
        fullscreen = foreground_is_fullscreen(self.mons)  # a full-screen app is in front: get out of its way
        if fullscreen != self.fs_hidden:
            self.fs_hidden = fullscreen
            self.set_visible(not fullscreen)
        if fullscreen:
            self.root.after(TICK_MS * 5, self.tick)
            return
        self.mons = monitors()                            # screens and taskbars can change
        self.wins = windows_front_to_back()
        self.update_scale()
        self.ledges, self.ceilings = find_spots(self.wins, self.mons, self.h)
        self.walls = find_walls(self.wins, self.mons)
        moving = False
        if not self.held and self.menu is None:
            if self.airborne:
                self.fly()
            else:
                self.ride()
                if self.wall:
                    moving = self.cling()
                elif self.hanging:
                    moving = self.hang()
                else:
                    moving = self.walk()
        if self.ticks % TICKS_PER_FRAME == 0 or self.redraw:
            self.redraw = False
            self.frame += 1
            self.draw(self.sprite_rows(moving))
        self.root.geometry(f"{self.w}x{self.h}+{round(self.x)}+{round(self.feet) - self.h}")
        if self.ticks % 10 == 0:
            self.raise_to_top()
        self.ticks += 1
        self.root.after(TICK_MS, self.tick)


def already_running():
    """True if another desktop pet is running. Holds a named mutex for as long as this program lives."""
    global _mutex
    kernel32 = ctypes.windll.kernel32
    kernel32.CreateMutexW.restype = wt.HANDLE
    kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, wt.BOOL, wt.LPCWSTR]
    _mutex = kernel32.CreateMutexW(None, False, r"Local\DesktopPetSingleInstance")
    return kernel32.GetLastError() == 183                  # ERROR_ALREADY_EXISTS


_mutex = None

if __name__ == "__main__":
    if already_running():                                  # starting it twice does nothing
        raise SystemExit
    enable_real_pixels()
    root = tk.Tk()
    Pet(root)
    root.mainloop()
