import os
import glob
import time
import itertools
import signal
import sys


def pick_wayland_socket() -> tuple[str | None, str | None]:
    # 1) Prefer current env if it already points to a runtime dir with a socket
    xdg = os.environ.get("XDG_RUNTIME_DIR")
    if xdg:
        socks = sorted(glob.glob(os.path.join(xdg, "wayland-*")))
        if socks:
            sock = socks[0]
            return os.path.dirname(sock), os.path.basename(sock)

    # 2) Scan common system locations
    candidates = sorted(glob.glob("/run/user/*/wayland-*"))
    if not candidates:
        return None, None

    # Prefer root's socket if present (typical for ubuntu-frame daemon)
    for c in candidates:
        if c.startswith("/run/user/0/"):
            return os.path.dirname(c), os.path.basename(c)

    # Otherwise pick the first found (lowest uid typically)
    c = candidates[0]
    return os.path.dirname(c), os.path.basename(c)


def die(msg: str, code: int = 1) -> None:
    print(f"[ERROR] {msg}", file=sys.stderr)
    sys.exit(code)


def main() -> int:
    xdg_dir, wayland_display = pick_wayland_socket()
    if not xdg_dir or not wayland_display:
        die(
            "No Wayland socket found.\n"
            "Make sure Ubuntu Frame (or another Wayland compositor) is running.\n"
            "Hint: ls -l /run/user/*/wayland-*"
        )

    # Must be set BEFORE importing pygame (SDL decides backend at import/init time)
    os.environ["XDG_RUNTIME_DIR"] = xdg_dir
    os.environ["WAYLAND_DISPLAY"] = wayland_display
    os.environ.setdefault("SDL_VIDEODRIVER", "wayland")

    print(f"[INFO] Using XDG_RUNTIME_DIR={xdg_dir}")
    print(f"[INFO] Using WAYLAND_DISPLAY={wayland_display}")
    print(f"[INFO] SDL_VIDEODRIVER={os.environ.get('SDL_VIDEODRIVER')}")

    # Import after env is set
    try:
        import pygame
    except Exception as e:
        die(
            f"Failed to import pygame: {e}\nInstall: sudo apt install python3-pygame"
        )

    pygame.init()

    # Graceful exit on Ctrl+C
    running = True

    def handle_sigint(_sig, _frame):
        nonlocal running
        running = False

    signal.signal(signal.SIGINT, handle_sigint)

    # Query current display size; fallback if unavailable
    try:
        info = pygame.display.Info()
        w, h = info.current_w, info.current_h
        if not w or not h:
            raise RuntimeError("pygame.display.Info returned 0 size")
    except Exception:
        # Safe fallback; you can adjust if needed
        w, h = 1920, 1080

    # Some SDL/Wayland setups behave better with explicit size + SCALED
    flags = pygame.SCALED  # try SCALED first
    # If you really want "exclusive" fullscreen, you can switch to:
    # flags = pygame.FULLSCREEN

    screen = pygame.display.set_mode((w, h), flags)
    pygame.display.set_caption("Wayland Color Test (ESC/Q to quit)")

    colors = [
        ((255, 0, 0), "RED"),
        ((0, 255, 0), "GREEN"),
        ((0, 0, 255), "BLUE"),
        ((255, 255, 255), "WHITE"),
        ((0, 0, 0), "BLACK"),
    ]

    delay_s = 1.0  # seconds per color
    clock = pygame.time.Clock()

    for rgb, name in itertools.cycle(colors):
        if not running:
            break

        # Pump events so the window stays responsive
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_ESCAPE, pygame.K_q):
                    running = False

        if not running:
            break

        screen.fill(rgb)
        pygame.display.flip()
        print(f"[INFO] Color: {name}")

        # Sleep while still pumping events a bit (avoid "not responding")
        end = time.time() + delay_s
        while running and time.time() < end:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN and event.key in (
                    pygame.K_ESCAPE,
                    pygame.K_q,
                ):
                    running = False
            clock.tick(60)

    pygame.quit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
