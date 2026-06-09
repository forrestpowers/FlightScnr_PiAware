"""Round 1080×1080 touch display — FlightScnr UI on plane-tracker backend."""

import logging
import os
import time

import pygame

from utilities.overhead import Overhead
from display.round_touch import draw, input_handler, scale, settings, theme, video
from display.round_touch.screens import clock, details, flight_detail, info, radar

logger = logging.getLogger("plane-tracker.display")

SCREEN_RADAR = "radar"
SCREEN_FLIGHT = "flight_detail"
SCREEN_SETTINGS = "settings"
SCREEN_DETAILS = "details"
SCREEN_CLOCK = "clock"

SECONDARY_TIMEOUT_S = 45
BOOT_SPLASH_S = 3


class RoundTouchDisplay:
    def __init__(self):
        try:
            from config import DISPLAY_FULLSCREEN
            fullscreen = DISPLAY_FULLSCREEN
        except ImportError:
            fullscreen = os.environ.get("DISPLAY_FULLSCREEN", "true").lower() in ("1", "true", "yes")

        self.surface = video.init_display(theme.DISPLAY_WIDTH, theme.DISPLAY_HEIGHT, fullscreen)
        pygame.mouse.set_visible(False)
        pygame.event.set_allowed(
            None
        )  # allow all; we filter QUIT manually

        try:
            from config import SEARCH_RADIUS_NM
            scale.select_for_radius_nm(SEARCH_RADIUS_NM)
        except ImportError:
            scale.select(settings.scale_index())
        try:
            from config import DISTANCE_UNITS
            if DISTANCE_UNITS == "imperial" and not settings.distance_in_miles():
                settings.toggle_distance_units()
            elif DISTANCE_UNITS == "metric" and settings.distance_in_miles():
                settings.toggle_distance_units()
        except ImportError:
            pass

        self.overhead = Overhead()
        self.overhead.grab_data()

        self.input = input_handler.TouchInput()
        self.screen = SCREEN_RADAR
        self.settings_page = info.PAGE_MAIN
        self.flights = []
        self.flight_index = 0
        self._secondary_activity = time.time()
        self._boot_until = time.time() + BOOT_SPLASH_S
        self._last_clock_minute = -1
        self._last_radar_draw = 0
        self._last_static_draw = 0
        self._display_focus = 0
        self._fatal_error = None

        radar._init_sweep()
        self._safe_draw()

    def _refresh_flights(self):
        try:
            if self.overhead.processing:
                return
            self.flights = self.overhead.peek_data()
        except Exception:
            logger.exception("Failed to refresh flight data")

    def _ordered_flights(self):
        return radar.flights_by_distance(self.flights)

    def _draw(self):
        if self._fatal_error:
            draw.draw_error(self.surface, self._fatal_error)
            pygame.display.flip()
            return

        if time.time() < self._boot_until:
            details.draw_details(self.surface, boot_splash=True)
            pygame.display.flip()
            return

        if self.screen == SCREEN_RADAR:
            radar.draw_radar(self.surface, self.flights)
        elif self.screen == SCREEN_FLIGHT:
            flight_detail.draw_flight_detail(self.surface, self._ordered_flights(), self.flight_index)
        elif self.screen == SCREEN_SETTINGS:
            info.draw_info(self.surface, self.settings_page)
        elif self.screen == SCREEN_DETAILS:
            details.draw_details(self.surface)
        elif self.screen == SCREEN_CLOCK:
            clock.draw_clock(self.surface)
        pygame.display.flip()

    def _safe_draw(self):
        try:
            self._draw()
        except Exception as exc:
            self._fatal_error = str(exc)
            logger.exception("Display draw failed")
            try:
                draw.draw_error(self.surface, self._fatal_error)
                pygame.display.flip()
            except Exception:
                logger.exception("Could not render error screen")

    def _note_activity(self):
        self._secondary_activity = time.time()

    def _return_to_radar(self):
        self.screen = SCREEN_RADAR
        self.settings_page = info.PAGE_MAIN

    def _handle_settings_knob(self, delta: int):
        if self.settings_page != info.PAGE_DISPLAY:
            return
        if self._display_focus == 0:
            settings.set_brightness_percent(settings.brightness_percent() + delta * 5)
        elif self._display_focus == 1 and delta != 0:
            settings.toggle_distance_units()
        elif self._display_focus == 2 and delta != 0:
            settings.toggle_compass_rose()

    def _handle_settings_tap(self):
        if self.settings_page == info.PAGE_DISPLAY:
            self._display_focus = (self._display_focus + 1) % 3

    def _handle_navigation(self):
        swipe = self.input.consume_swipe()
        if time.time() < self._boot_until:
            return

        if swipe != input_handler.SWIPE_NONE and self.screen not in (SCREEN_RADAR, SCREEN_CLOCK):
            self._note_activity()

        if swipe == input_handler.SWIPE_DOWN and self.screen == SCREEN_RADAR:
            self.screen = SCREEN_CLOCK
            self._safe_draw()
        elif swipe == input_handler.SWIPE_UP and self.screen == SCREEN_RADAR:
            self.screen = SCREEN_DETAILS
            self._note_activity()
            self._safe_draw()
        elif swipe == input_handler.SWIPE_DOWN and self.screen == SCREEN_DETAILS:
            self._return_to_radar()
            self._safe_draw()
        elif swipe == input_handler.SWIPE_UP and self.screen == SCREEN_CLOCK:
            self._return_to_radar()
            self._safe_draw()
        elif swipe == input_handler.SWIPE_LEFT and self.screen == SCREEN_RADAR:
            self.screen = SCREEN_SETTINGS
            self.settings_page = info.PAGE_MAIN
            self._note_activity()
            self._safe_draw()
        elif swipe == input_handler.SWIPE_LEFT and self.screen == SCREEN_SETTINGS and self.settings_page == info.PAGE_MAIN:
            self.settings_page = info.PAGE_DISPLAY
            self._safe_draw()
        elif swipe == input_handler.SWIPE_LEFT and self.screen == SCREEN_SETTINGS and self.settings_page == info.PAGE_DISPLAY:
            self.settings_page = info.PAGE_COLORS
            self._safe_draw()
        elif swipe == input_handler.SWIPE_RIGHT and self.screen == SCREEN_FLIGHT:
            self._return_to_radar()
            self._safe_draw()
        elif swipe == input_handler.SWIPE_RIGHT and self.screen == SCREEN_SETTINGS and self.settings_page == info.PAGE_COLORS:
            self.settings_page = info.PAGE_DISPLAY
            self._safe_draw()
        elif swipe == input_handler.SWIPE_RIGHT and self.screen == SCREEN_SETTINGS and self.settings_page == info.PAGE_DISPLAY:
            self.settings_page = info.PAGE_MAIN
            self._safe_draw()
        elif swipe == input_handler.SWIPE_RIGHT and self.screen == SCREEN_SETTINGS:
            self._return_to_radar()
            self._safe_draw()

        tap = self.input.consume_tap()
        if tap and self.screen == SCREEN_RADAR:
            picked = radar.pick_flight_at(self.flights, tap[0], tap[1])
            ordered = self._ordered_flights()
            if picked and ordered:
                try:
                    self.flight_index = ordered.index(picked)
                except ValueError:
                    self.flight_index = 0
                self.screen = SCREEN_FLIGHT
                self._note_activity()
                self._safe_draw()
            elif ordered:
                self.flight_index = 0
                self.screen = SCREEN_FLIGHT
                self._note_activity()
                self._safe_draw()
        elif tap and self.screen == SCREEN_SETTINGS:
            self._handle_settings_tap()
            self._note_activity()
            self._safe_draw()

        scroll = self.input.consume_scroll()
        if scroll and self.screen == SCREEN_RADAR:
            if scroll > 0:
                scale.decrease()
            else:
                scale.increase()
            settings.set_scale_index(scale.active_index())
            self._safe_draw()
        elif scroll and self.screen == SCREEN_FLIGHT:
            ordered = self._ordered_flights()
            if ordered:
                self.flight_index = (self.flight_index - scroll) % len(ordered)
                self._note_activity()
                self._safe_draw()
        elif scroll and self.screen == SCREEN_SETTINGS:
            self._handle_settings_knob(scroll)
            self._note_activity()
            self._safe_draw()

    def _tick_timeout(self):
        if time.time() < self._boot_until:
            return
        if self.screen in (SCREEN_RADAR, SCREEN_CLOCK):
            return
        if time.time() - self._secondary_activity >= SECONDARY_TIMEOUT_S:
            self._return_to_radar()
            self._safe_draw()

    def _tick_clock(self):
        if self.screen != SCREEN_CLOCK:
            return
        minute = time.localtime().tm_min + time.localtime().tm_hour * 60
        if minute != self._last_clock_minute:
            self._last_clock_minute = minute
            self._safe_draw()

    def _tick_data(self):
        try:
            self._refresh_flights()
            if not self.overhead.processing:
                self.overhead.grab_data()
        except Exception:
            logger.exception("Flight data poll failed")

    def run(self):
        logger.info("Round touch display starting (%dx%d)", theme.DISPLAY_WIDTH, theme.DISPLAY_HEIGHT)
        running = True
        last_data_poll = 0
        try:
            from config import DATA_REFRESH_SECONDS
        except ImportError:
            DATA_REFRESH_SECONDS = 2.0

        try:
            while running:
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        # Touch drivers / compositors sometimes emit spurious QUIT.
                        logger.warning("Ignoring pygame QUIT event")
                        continue
                    if event.type == pygame.ACTIVEEVENT and not event.gain:
                        logger.debug("Display lost focus (continuing)")
                        continue
                    if event.type in (
                        pygame.FINGERDOWN, pygame.FINGERUP,
                        pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP,
                        pygame.MOUSEWHEEL,
                    ):
                        self.input.handle_event(event)
                        self._handle_navigation()

                self._refresh_flights()

                now = time.time()
                if now - last_data_poll >= DATA_REFRESH_SECONDS:
                    self._tick_data()
                    last_data_poll = now

                if self._fatal_error:
                    time.sleep(1.0)
                    continue

                if now < self._boot_until:
                    self._safe_draw()
                    time.sleep(0.05)
                elif self.screen == SCREEN_RADAR:
                    radar.tick_sweep()
                    if (now - self._last_radar_draw) * 1000 >= theme.SWEEP_FRAME_MS:
                        self._safe_draw()
                        self._last_radar_draw = now
                elif self.screen == SCREEN_CLOCK:
                    self._tick_clock()
                elif self.screen in (SCREEN_FLIGHT, SCREEN_SETTINGS, SCREEN_DETAILS):
                    if (now - self._last_static_draw) >= 1.0:
                        self._safe_draw()
                        self._last_static_draw = now

                self._tick_timeout()
                time.sleep(0.01)

        except KeyboardInterrupt:
            logger.info("Display stopped by user")
        except Exception:
            logger.exception("Display loop crashed")
            raise
        finally:
            pygame.quit()
