"""Touch swipe and tap detection (FlightScnr navigation)."""

import pygame

SWIPE_NONE = 0
SWIPE_UP = 1
SWIPE_DOWN = 2
SWIPE_LEFT = 3
SWIPE_RIGHT = 4

_MIN_SWIPE_PX = 80


class TouchInput:
    def __init__(self):
        self._start = None
        self._pending_swipe = SWIPE_NONE
        self._pending_tap = None
        self._scroll_delta = 0

    def handle_event(self, event: pygame.event.Event):
        if event.type == pygame.MOUSEWHEEL:
            self._scroll_delta += event.y
            return
        if event.type == pygame.FINGERDOWN:
            self._start = (event.x, event.y)
            return
        if event.type == pygame.FINGERUP and self._start is not None:
            dx = event.x - self._start[0]
            dy = event.y - self._start[1]
            self._start = None
            if abs(dx) < 0.02 and abs(dy) < 0.02:
                self._pending_tap = (int(event.x * pygame.display.get_surface().get_width()),
                                     int(event.y * pygame.display.get_surface().get_height()))
                return
            if abs(dx) > abs(dy):
                if dx * pygame.display.get_surface().get_width() > _MIN_SWIPE_PX:
                    self._pending_swipe = SWIPE_RIGHT
                elif dx * pygame.display.get_surface().get_width() < -_MIN_SWIPE_PX:
                    self._pending_swipe = SWIPE_LEFT
            else:
                if dy * pygame.display.get_surface().get_height() > _MIN_SWIPE_PX:
                    self._pending_swipe = SWIPE_DOWN
                elif dy * pygame.display.get_surface().get_height() < -_MIN_SWIPE_PX:
                    self._pending_swipe = SWIPE_UP
            return
        if event.type == pygame.MOUSEBUTTONDOWN:
            self._start = event.pos
            return
        if event.type == pygame.MOUSEBUTTONUP and self._start is not None:
            sx, sy = self._start
            ex, ey = event.pos
            self._start = None
            dx, dy = ex - sx, ey - sy
            if abs(dx) < 12 and abs(dy) < 12:
                self._pending_tap = (ex, ey)
                return
            if abs(dx) > abs(dy):
                if dx > _MIN_SWIPE_PX:
                    self._pending_swipe = SWIPE_RIGHT
                elif dx < -_MIN_SWIPE_PX:
                    self._pending_swipe = SWIPE_LEFT
            else:
                if dy > _MIN_SWIPE_PX:
                    self._pending_swipe = SWIPE_DOWN
                elif dy < -_MIN_SWIPE_PX:
                    self._pending_swipe = SWIPE_UP

    def consume_swipe(self) -> int:
        swipe = self._pending_swipe
        self._pending_swipe = SWIPE_NONE
        return swipe

    def consume_tap(self):
        tap = self._pending_tap
        self._pending_tap = None
        return tap

    def consume_scroll(self) -> int:
        delta = self._scroll_delta
        self._scroll_delta = 0
        return delta
