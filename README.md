# Desktop pet

The orange pixel creature from the usage window, living on the desktop.

- Walks along the bottom of every screen (on top of the taskbar), stops now and then, and blinks.
- Now and then it leaps onto the top edge of another window and walks along it.
- At the end of a window top it usually turns around, but sometimes walks off and falls.
- Maximised and full-screen windows have no room above them, so it leaps up and
  **hangs** from their top edge instead, climbs along it hand over hand, and lets go after a while.
- If you move the window it is on, it rides along. If the window is closed,
  minimised or covered by another window, it falls down.
- **Several screens:** it can walk off the edge of a screen onto a lower one next to it,
  and leap between screens. A higher screen next to it is a wall it turns around at.

## Run

```
pythonw desktop_pet.pyw
```

Needs only Python 3 on Windows (tkinter and ctypes come with it).

## Controls

- **Drag with the left mouse button:** pick it up. Let go to drop it; move the
  mouse quickly while letting go to throw it. Let go just below the top edge of
  a maximised window and it holds on to it.
- **Right-click the creature:** close it.

## Network

None. The pet makes no network requests.

## Planned

- Remind you to take a break after a long time at the computer (timers).
