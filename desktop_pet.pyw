"""Desktop pet: the orange pixel creature walks along the top of the Windows taskbar.

Step 1: a see-through, always-on-top window that walks left and right,
stops now and then, and blinks. Right-click the creature to close it.
Uses only the Python standard library (tkinter + ctypes).
"""
import ctypes
import ctypes.wintypes
import random
import tkinter as tk

# --- Look (same sprite as the usage-window creature) ---------------------
PX = 4                              # on-screen size of one sprite pixel
GRID_W, GRID_H = 15, 10             # sprite size in sprite pixels (60 x 40 on screen)
BODY_COLOR = "#FF7A1A"
EYE_COLOR = "#1C1E25"
SEE_THROUGH = "#FF00FE"             # this colour is drawn as "nothing" (see-through)

BODY_ROW = "..OOOOOOOOOOO.."
ARMS_ROW = "OOOOOOOOOOOOOOO"
EMPTY_ROW = "..............."
EYES_OPEN = ("..OOEOOOOOEOO..", "..OOEOOOOOEOO..")
EYES_SHUT = ("..OOOOOOOOOOO..", "..OEEOOOOOEEO..")
LEGS_A = "...O..O.O..O..."
LEGS_B = "..O..O...O..O.."

# --- Behaviour ------------------------------------------------------------
ANIM_MS = 125                       # about 8 frames per second
WALK_PX = 3                         # pixels moved per frame while walking


def enable_real_pixels():
    """Tell Windows we handle display scaling ourselves, so our pixels are real screen pixels."""
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except (AttributeError, OSError):
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except (AttributeError, OSError):
            pass


def work_area():
    """The screen without the taskbar, as (left, top, right, bottom). Bottom = top edge of the taskbar."""
    rect = ctypes.wintypes.RECT()
    SPI_GETWORKAREA = 0x0030
    ctypes.windll.user32.SystemParametersInfoW(SPI_GETWORKAREA, 0, ctypes.byref(rect), 0)
    return rect.left, rect.top, rect.right, rect.bottom


class Pet:
    def __init__(self, root):
        self.root = root
        self.w, self.h = GRID_W * PX, GRID_H * PX
        root.overrideredirect(True)                 # no title bar, no taskbar button
        root.attributes("-topmost", True)           # stay above other windows
        root.attributes("-transparentcolor", SEE_THROUGH)
        root.config(bg=SEE_THROUGH)
        self.canvas = tk.Canvas(root, width=self.w, height=self.h, bg=SEE_THROUGH,
                                highlightthickness=0, bd=0)
        self.canvas.pack()
        self.canvas.bind("<Button-3>", lambda e: root.destroy())   # right-click closes

        left, _, right, bottom = work_area()
        self.x = random.randint(left, max(left, right - self.w))
        self.facing = random.choice((-1, 1))
        self.frame = 0
        self.walk_left = 0      # frames left to walk
        self.rest_left = 16     # frames left to stand still

        self.tick()

    def sprite_rows(self, walking):
        """The 10 rows of the sprite for this frame."""
        f = self.frame
        eyes = EYES_SHUT if f % 32 in (30, 31) else EYES_OPEN   # blink about every 4 s
        if walking:
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
                    c.create_rectangle(x * PX, y * PX, (x + 1) * PX, (y + 1) * PX,
                                       fill=colors[ch], outline="")

    def step(self):
        """Decide what to do this frame: walk, or stand and rest."""
        left, _, right, _ = work_area()
        if self.walk_left > 0:
            self.walk_left -= 1
            self.x += WALK_PX * self.facing
            if self.x <= left or self.x + self.w >= right:     # screen edge: turn around
                self.x = max(left, min(self.x, right - self.w))
                self.facing = -self.facing
            if self.walk_left == 0:
                self.rest_left = random.randint(8, 40)
            return True
        self.rest_left -= 1
        if self.rest_left <= 0:
            self.walk_left = random.randint(20, 80)
            if random.random() < 0.4:
                self.facing = -self.facing
        return False

    def tick(self):
        walking = self.step()
        self.draw(self.sprite_rows(walking))
        _, _, _, bottom = work_area()          # re-read: the taskbar can move or auto-hide
        self.root.geometry(f"{self.w}x{self.h}+{self.x}+{bottom - self.h}")
        self.frame += 1
        self.root.after(ANIM_MS, self.tick)


if __name__ == "__main__":
    enable_real_pixels()
    root = tk.Tk()
    Pet(root)
    root.mainloop()
