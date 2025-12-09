import os
from abc import ABC, abstractmethod
from typing import List, Optional, Tuple, Union

import pygame
from screeninfo import Monitor, get_monitors

from src.backend.clients.vision_tracking_client import VisionTrackingClient
from src.backend.clients.windows_webcam_client import WindowsWebcamClient


class _RootAdapter:
    """
    Minimal adapter to provide `winfo_screenwidth()` and `winfo_screenheight()`
    compatibility for existing subclasses. Also exposes `destroy()` for symmetry.
    """

    def __init__(self, monitor: Monitor, quit_callback):
        self._monitor = monitor
        self._quit_callback = quit_callback

    def winfo_screenwidth(self) -> int:
        return int(self._monitor.width)

    def winfo_screenheight(self) -> int:
        return int(self._monitor.height)

    def destroy(self):
        self._quit_callback()


class _CanvasAdapter:
    """
    Pygame-backed adapter that mimics the limited subset of tkinter.Canvas API
    used by our GUIs: delete("all"), create_oval, and create_text.
    """

    def __init__(self, screen: "pygame.Surface", background_color=(0, 0, 0)):
        self._screen = screen
        self._background_color = background_color

    def delete(self, tag: str):
        # Only "all" is used in the codebase; clear the screen.
        if tag == "all":
            self._screen.fill(self._background_color)

    def create_oval(
        self,
        x1: int,
        y1: int,
        x2: int,
        y2: int,
        fill: str = "white",
        outline: str = "",
    ):
        # Convert simple color names to RGB; default to white on unknown.
        color = _parse_color(fill, default=(255, 255, 255))
        center_x = (x1 + x2) // 2
        center_y = (y1 + y2) // 2
        radius_x = abs(x2 - x1) // 2
        radius_y = abs(y2 - y1) // 2
        # Draw ellipse inside the bounding rect
        rect = pygame.Rect(
            center_x - radius_x, center_y - radius_y, radius_x * 2, radius_y * 2
        )
        pygame.draw.ellipse(self._screen, color, rect)

    def create_text(
        self,
        x: int,
        y: int,
        text: str,
        fill: str = "white",
        font: Optional[Tuple[str, int, Union[str, int]]] = None,
        justify: str = "left",
    ):
        color = _parse_color(fill, default=(255, 255, 255))
        pg_font = _parse_font(font)

        # Support multiline text separated by "\n"
        lines = text.split("\n")
        line_surfaces = [pg_font.render(line, True, color) for line in lines]
        line_height = pg_font.get_linesize()
        total_height = line_height * len(line_surfaces)

        # Top-left starting point for vertical centering around y
        start_y = int(y - total_height / 2)
        for idx, surface in enumerate(line_surfaces):
            surface_rect = surface.get_rect()
            # Horizontal alignment: center around x if justify == "center"
            if justify == "center":
                surface_rect.centerx = x
            else:
                surface_rect.x = x
            surface_rect.y = start_y + idx * line_height
            self._screen.blit(surface, surface_rect)


def _parse_color(
    spec: Union[str, Tuple[int, int, int]], default=(255, 255, 255)
) -> Tuple[int, int, int]:
    if isinstance(spec, tuple) and len(spec) == 3:
        return tuple(int(max(0, min(255, c))) for c in spec)  # clamp
    if isinstance(spec, str):
        name = spec.lower()
        named = {
            "white": (255, 255, 255),
            "black": (0, 0, 0),
            "red": (255, 0, 0),
            "green": (0, 255, 0),
            "blue": (0, 0, 255),
        }
        return named.get(name, default)
    return default


def _parse_font(
    font_spec: Optional[Tuple[str, int, Union[str, int]]]
) -> "pygame.font.Font":
    # Default: Arial 24 regular
    family = "Arial"
    size = 24
    bold = False
    italic = False

    if isinstance(font_spec, tuple) and len(font_spec) >= 2:
        family = font_spec[0] or family
        size = int(font_spec[1] or size)
        # Third element may be style like "bold" or numeric weight
        if len(font_spec) >= 3:
            style = font_spec[2]
            if isinstance(style, str):
                if "bold" in style.lower():
                    bold = True
                if "italic" in style.lower():
                    italic = True
            else:
                # Non-string styles are ignored
                pass

    try:
        return pygame.font.SysFont(family, size, bold=bold, italic=italic)
    except Exception:
        return pygame.font.Font(None, size)


class BaseGUITest(ABC):
    def __init__(
        self,
        monitor: Optional[Monitor],
        windows_webcam_client: WindowsWebcamClient,
        vision_tracking_client: VisionTrackingClient,
    ):
        self.monitor = monitor
        self.windows_webcam_client = windows_webcam_client
        self.vision_tracking_client = vision_tracking_client
        self.started_calibration = False
        self.index = 0

        self._running = False
        self._screen: Optional[pygame.Surface] = None
        self.root: Optional[_RootAdapter] = None
        self.canvas: Optional[_CanvasAdapter] = None

    def run(self):
        # Determine target area: single monitor or all monitors (union)
        if self.monitor is None:
            monitors = get_monitors()
            min_x = min(m.x for m in monitors)
            min_y = min(m.y for m in monitors)
            max_x = max(m.x + m.width for m in monitors)
            max_y = max(m.y + m.height for m in monitors)
            win_x, win_y = int(min_x), int(min_y)
            win_w, win_h = int(max_x - min_x), int(max_y - min_y)

            # Create a simple virtual monitor-like object for adapters
            class _VirtualMonitor:
                def __init__(self, x, y, width, height):
                    self.x = x
                    self.y = y
                    self.width = width
                    self.height = height

            target_monitor = _VirtualMonitor(win_x, win_y, win_w, win_h)
        else:
            target_monitor = self.monitor
            win_x, win_y = int(self.monitor.x), int(self.monitor.y)
            win_w, win_h = int(self.monitor.width), int(self.monitor.height)

        # Position window and create a borderless window covering target area
        os.environ["SDL_VIDEO_WINDOW_POS"] = f"{win_x},{win_y}"

        pygame.init()
        pygame.font.init()
        self._screen = pygame.display.set_mode(
            (win_w, win_h),
            flags=pygame.NOFRAME,
        )
        pygame.display.set_caption("Gaze Calibration")
        self._screen.fill((0, 0, 0))

        self.root = _RootAdapter(target_monitor, quit_callback=self._request_quit)
        self.canvas = _CanvasAdapter(self._screen, background_color=(0, 0, 0))

        # Initial start message
        self.show_start_message()
        pygame.display.flip()

        clock = pygame.time.Clock()
        self._running = True
        while self._running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self._request_quit()
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        self.exit_app()
                    elif event.key == pygame.K_RETURN:
                        self.next_position()
                    elif event.key == pygame.K_BACKSPACE:
                        self.prev_position()

            # Limit CPU usage; drawing is on-demand by subclass calls
            clock.tick(60)
            pygame.display.update()

        pygame.quit()

    @abstractmethod
    def show_start_message(self):
        pass

    @abstractmethod
    def next_position(self, event=None):
        pass

    @abstractmethod
    def prev_position(self, event=None):
        pass

    def draw_element(self):
        if not self.canvas or not self._screen:
            return
        self.canvas.delete("all")
        x, y = self.positions[self.index]
        self.canvas.create_oval(x - 5, y - 5, x + 5, y + 5, fill="white", outline="")
        pygame.display.flip()

    def exit_app(self, event=None):
        self._request_quit()

    def _request_quit(self):
        self._running = False
