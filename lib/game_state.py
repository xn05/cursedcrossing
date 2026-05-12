import pygame

from lib.settings import FADE_IN_DURATION, LOGICAL_HEIGHT, LOGICAL_WIDTH


class GameStateController:
    def __init__(self):
        self.state = "menu"
        self.hovered_button = None
        self.fade_in_duration = max(0.0, float(FADE_IN_DURATION))
        self.fade_out_duration = self.fade_in_duration
        self.transition_active = False
        self.transition_phase = None
        self.transition_time = 0.0
        self.transition_midpoint_done = False
        self.transition_on_midpoint = None

    def start_transition(self, on_midpoint):
        self.transition_active = True
        self.transition_phase = "out"
        self.transition_time = 0.0
        self.transition_midpoint_done = False
        self.transition_on_midpoint = on_midpoint

    def update_transition(self, dt):
        if not self.transition_active:
            return
        duration = self.fade_out_duration if self.transition_phase == "out" else self.fade_in_duration
        duration = max(0.0, float(duration))
        if duration == 0.0:
            self._advance_transition_phase()
            return
        self.transition_time += dt
        if self.transition_time >= duration:
            self._advance_transition_phase()

    def draw_transition_overlay(self, surface):
        alpha = self.get_transition_alpha()
        if alpha <= 0:
            return
        overlay = pygame.Surface((LOGICAL_WIDTH, LOGICAL_HEIGHT))
        overlay.fill((0, 0, 0))
        overlay.set_alpha(alpha)
        surface.blit(overlay, (0, 0))

    def get_transition_alpha(self):
        if not self.transition_active or not self.transition_phase:
            return 0
        duration = self.fade_out_duration if self.transition_phase == "out" else self.fade_in_duration
        duration = max(0.0, float(duration))
        if duration == 0.0:
            return 0 if self.transition_phase == "in" else 255
        t = min(1.0, self.transition_time / duration)
        if self.transition_phase == "out":
            return int(255 * t)
        return int(255 * (1.0 - t))

    def _advance_transition_phase(self):
        if self.transition_phase == "out":
            if not self.transition_midpoint_done and self.transition_on_midpoint:
                self.transition_on_midpoint()
            self.transition_midpoint_done = True
            self.transition_phase = "in"
            self.transition_time = 0.0
            return

        self.transition_active = False
        self.transition_phase = None
        self.transition_time = 0.0
        self.transition_on_midpoint = None
