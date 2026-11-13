# Desktop pet

A small orange pixel creature that lives on your desktop (Windows). A fan-made pet inspired by
Clawd, the Claude Code mascot; the sprite is the one from my usage-window app.

## What he does

- Walks along the bottom of every screen (on top of the taskbar), stops now and then, and blinks.
- Now and then he leaps onto the top edge of another window and walks along it, or stands on the
  bottom edge of a window that floats above the taskbar.
- At the end of a window top he usually turns around, but sometimes climbs down the side or walks off and falls.
- **Hangs** from the top edge of maximised and full-screen windows and from the bottom edge of
  floating windows, climbs along it hand over hand, and lets go after a while.
- **Walls:** he clings to the edges of the screens and the sides of windows, holds on, slides down
  or climbs up. Sometimes he walks to the side of a window and climbs it instead of leaping, then
  pulls himself onto the top.
- If you move the window he is on, he rides along. If the window is closed, minimised or covered
  by another window, he falls down.
- **Several screens:** he walks off the edge of a screen onto a lower one next to it and leaps
  between screens. He keeps the same physical size on every screen (the sprite is scaled by each
  screen's pixels per millimetre), and he never stands half over empty space between screens.
- **Favourite window:** while the usage window (any untitled Tk window of another program) is
  open, he heads there after most rests (60% of the time) and stays on or around it. When it is
  closed he behaves normally again.
- **Colours:** a random colour every time he starts.

## Run

```
pythonw desktop_pet.pyw
```

Needs only Python 3 on Windows (tkinter and ctypes come with it). Starting it a second time does
nothing while he is already running. To start him at login, put a shortcut to
`pythonw.exe "...\desktop_pet.pyw"` in your Startup folder (`Win+R`, then `shell:startup`);
`pet.ico` is a matching icon.

## Controls

- **Drag with the left mouse button:** pick him up. Let go to drop him; move the mouse quickly
  while letting go to throw him. Let go just below a top edge, or next to a wall, and he holds on.
- **Right-click:** he disappears and drops in again from the top after 15 seconds.
- **Shift + right-click:** choose his colour from a menu.
- **Ctrl + right-click** (or middle-click): close the program for good.

## Network

None. The pet makes no network requests.

## Planned

- A tray icon to spawn and quit him.
- Perch on prominent things inside windows (a search bar, a menu).
- Remind you to take a break after a long time at the computer (timers).
