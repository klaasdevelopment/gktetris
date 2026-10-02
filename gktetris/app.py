"""Desktop presentation, keyboard input, and app lifecycle."""

import argparse
import os
from pathlib import Path

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
import pygame

from .audio import Audio
from .model import Game, HEIGHT, HIDDEN, WIDTH, shape
from .storage import Settings, load, save

SIZE = (1100, 850)
BOARD = pygame.Rect(400, 160, 300, 600)
CELL = 30
BG = (12, 17, 26)
PANEL = (19, 26, 38)
EDGE = (42, 54, 72)
TEXT = (233, 239, 246)
MUTED = (143, 158, 181)
ACCENT = (102, 235, 205)
COLORS = {
    "I": (66, 204, 230), "O": (246, 201, 78), "T": (175, 119, 235),
    "J": (91, 134, 238), "L": (244, 151, 75), "S": (96, 211, 148),
    "Z": (236, 105, 124),
}


def tint(color: tuple[int, ...], amount: int) -> tuple[int, ...]:
    return tuple(max(0, min(255, c + amount)) for c in color)


class App:
    def __init__(self, *, persistent: bool = True, seed: int | None = None):
        pygame.display.init()
        pygame.font.init()
        self.screen = pygame.display.set_mode(SIZE, pygame.RESIZABLE)
        pygame.display.set_caption("GK Tetris · Arcade")
        self.canvas = pygame.Surface(SIZE)
        self.clock = pygame.time.Clock()
        self.fonts: dict[tuple[int, bool, bool], pygame.font.Font] = {}
        self.persistent = persistent
        self.settings = load() if persistent else Settings()
        self.audio = Audio()
        self.game = Game(seed)
        self.state = "ready"
        self.running = True
        self.held_keys: list[int] = []
        self.pressed: set[int] = set()
        self.repeat_time = 0.0
        self.repeat_started = False
        self.flash_rows: tuple[int, ...] = ()
        self.flash_time = 0.0
        self.drop_cells: tuple[tuple[int, int], ...] = ()
        self.drop_distance = 0
        self.drop_time = 0.0
        self.notice = ""
        self.notice_time = 0.0
        self.elapsed = 0.0
        self.audio.sync(self.settings.muted, self.settings.music, False)
        icon = pygame.Surface((32, 32), pygame.SRCALPHA)
        for x, y in shape("T"):
            pygame.draw.rect(icon, ACCENT, (x * 10 + 1, y * 10 + 6, 9, 9), border_radius=2)
        pygame.display.set_icon(icon)

    def font(self, size: int, bold: bool = False, mono: bool = False) -> pygame.font.Font:
        key = (size, bold, mono)
        if key not in self.fonts:
            self.fonts[key] = pygame.font.SysFont("DejaVu Sans Mono" if mono else "DejaVu Sans", size, bold)
        return self.fonts[key]

    def text(self, value: str, pos: tuple[int, int], size: int = 16,
             color: tuple[int, ...] = TEXT, bold: bool = False, mono: bool = False,
             center: bool = False) -> None:
        surface = self.font(size, bold, mono).render(value, True, color)
        rect = surface.get_rect(midtop=pos) if center else surface.get_rect(topleft=pos)
        self.canvas.blit(surface, rect)

    def clear_keys(self) -> None:
        self.held_keys.clear()
        self.pressed.clear()
        self.repeat_time = 0.0
        self.repeat_started = False

    def persist(self) -> None:
        self.settings.best = max(self.settings.best, self.game.score)
        if self.persistent:
            save(self.settings)

    def start(self) -> None:
        self.persist()
        self.game = Game()
        self.state = "playing"
        self.clear_keys()
        self.flash_time = self.drop_time = self.notice_time = 0.0
        self.audio.sync(self.settings.muted, self.settings.music, True)
        self.audio.play("start")

    def pause(self) -> None:
        self.state = "paused"
        self.clear_keys()
        self.audio.sync(self.settings.muted, self.settings.music, False)
        self.persist()

    def resume(self) -> None:
        self.state = "playing"
        self.clear_keys()
        self.audio.sync(self.settings.muted, self.settings.music, True)

    def handle(self, event: pygame.event.Event) -> None:
        if event.type == pygame.QUIT:
            self.running = False
        elif event.type == pygame.WINDOWFOCUSLOST:
            if self.state == "playing":
                self.pause()
            else:
                self.clear_keys()
        elif event.type == pygame.KEYUP:
            self.pressed.discard(event.key)
            if event.key in self.held_keys:
                self.held_keys.remove(event.key)
                self.repeat_time = 0.0
                self.repeat_started = False
        elif event.type == pygame.KEYDOWN:
            if getattr(event, "repeat", False) or event.key in self.pressed:
                return
            self.pressed.add(event.key)
            key = event.key
            if key in (pygame.K_m, pygame.K_n):
                if key == pygame.K_m:
                    self.settings.muted = not self.settings.muted
                else:
                    self.settings.music = not self.settings.music
                self.audio.sync(self.settings.muted, self.settings.music, self.state == "playing")
                self.persist()
            elif key == pygame.K_ESCAPE:
                if self.state == "playing":
                    self.pause()
                else:
                    self.running = False
            elif key == pygame.K_RETURN:
                if self.state in ("ready", "over"):
                    self.start()
                elif self.state == "paused":
                    self.resume()
            elif key == pygame.K_p and self.state in ("playing", "paused"):
                self.pause() if self.state == "playing" else self.resume()
            elif self.state == "playing":
                if key in (pygame.K_LEFT, pygame.K_RIGHT):
                    self.held_keys.append(key)
                    self.repeat_time = 0.0
                    self.repeat_started = False
                    self.game.move(-1 if key == pygame.K_LEFT else 1)
                elif key == pygame.K_UP:
                    self.game.rotate()
                elif key == pygame.K_DOWN:
                    self.game.hard_drop()
                elif key == pygame.K_c:
                    self.game.hold()
                self.process_game_events()

    def process_game_events(self) -> None:
        events = self.game.drain_events()
        names = {event.name for event in events}
        for event in events:
            sound = event.name
            if event.name == "drop":
                self.drop_cells, self.drop_distance = event.cells, event.distance
                self.drop_time = 0.16
            elif event.name == "clear":
                self.flash_rows = event.rows
                self.flash_time = 0.22
                self.notice = ("", "SINGLE", "DOUBLE", "TRIPLE", "TETRIS!")[len(event.rows)]
                self.notice_time = 1.3
                if len(event.rows) == 4:
                    sound = "tetris"
            elif event.name == "game_over":
                self.state = "over"
                self.clear_keys()
                self.audio.sync(self.settings.muted, self.settings.music, False)
                self.persist()
            if event.name != "lock" or not names.intersection({"drop", "clear", "game_over"}):
                self.audio.play(sound)

    def update(self, dt: float) -> None:
        self.elapsed += dt
        if self.state != "playing":
            return
        self.flash_time = max(0.0, self.flash_time - dt)
        self.drop_time = max(0.0, self.drop_time - dt)
        self.notice_time = max(0.0, self.notice_time - dt)
        if self.held_keys:
            self.repeat_time += dt
            interval = 0.055 if self.repeat_started else 0.16
            while self.repeat_time >= interval:
                self.repeat_time -= interval
                self.repeat_started = True
                self.game.move(-1 if self.held_keys[-1] == pygame.K_LEFT else 1)
                interval = 0.055
        self.game.update(dt)
        self.process_game_events()

    def card(self, rect: tuple[int, int, int, int], label: str, tag: str = "") -> None:
        x, y, w, h = rect
        pygame.draw.rect(self.canvas, PANEL, rect, border_radius=12)
        pygame.draw.rect(self.canvas, EDGE, rect, width=1, border_radius=12)
        self.text(label, (x + 22, y + 18), 12, MUTED, bold=True)
        if tag:
            self.text(tag, (x + w - 44, y + 17), 12, ACCENT, mono=True)

    def block(self, rect: pygame.Rect, kind: str, ghost: bool = False) -> None:
        color = COLORS[kind]
        r = rect.inflate(-3, -3)
        if ghost:
            pygame.draw.rect(self.canvas, tint(color, -95), r, width=1, border_radius=3)
            pygame.draw.rect(self.canvas, tint(color, -155), r.inflate(-6, -6), width=1, border_radius=1)
            return
        pygame.draw.rect(self.canvas, tint(color, -45), r, border_radius=3)
        pygame.draw.rect(self.canvas, color, (r.x + 2, r.y + 2, r.w - 4, r.h - 6), border_radius=2)
        pygame.draw.line(self.canvas, tint(color, 50), (r.x + 3, r.y + 2), (r.right - 4, r.y + 2))
        pygame.draw.line(self.canvas, tint(color, 20), (r.x + 2, r.y + 3), (r.x + 2, r.bottom - 5))

    def preview(self, kind: str, center: tuple[int, int], size: int = 26) -> None:
        cells = shape(kind)
        minx, maxx = min(x for x, _ in cells), max(x for x, _ in cells)
        miny, maxy = min(y for _, y in cells), max(y for _, y in cells)
        left = center[0] - (maxx - minx + 1) * size // 2
        top = center[1] - (maxy - miny + 1) * size // 2
        for x, y in cells:
            self.block(pygame.Rect(left + (x - minx) * size, top + (y - miny) * size, size, size), kind)

    def draw_board(self) -> None:
        pygame.draw.rect(self.canvas, (27, 38, 53), BOARD.inflate(16, 16), border_radius=8)
        pygame.draw.rect(self.canvas, EDGE, BOARD.inflate(16, 16), width=1, border_radius=8)
        pygame.draw.rect(self.canvas, (9, 14, 23), BOARD)
        for x in range(1, WIDTH):
            pygame.draw.line(self.canvas, (20, 28, 40), (BOARD.x + x * CELL, BOARD.y), (BOARD.x + x * CELL, BOARD.bottom))
        for y in range(1, HEIGHT):
            pygame.draw.line(self.canvas, (20, 28, 40), (BOARD.x, BOARD.y + y * CELL), (BOARD.right, BOARD.y + y * CELL))
        self.canvas.set_clip(BOARD)
        for row, cells in enumerate(self.game.board[HIDDEN:]):
            for x, kind in enumerate(cells):
                if kind:
                    self.block(pygame.Rect(BOARD.x + x * CELL, BOARD.y + row * CELL, CELL, CELL), kind)
        if self.state != "over":
            for x, y in self.game.landing().cells():
                self.block(pygame.Rect(BOARD.x + x * CELL, BOARD.y + y * CELL, CELL, CELL), self.game.active.kind, ghost=True)
            for x, y in self.game.active.cells():
                self.block(pygame.Rect(BOARD.x + x * CELL, BOARD.y + y * CELL, CELL, CELL), self.game.active.kind)
        if self.drop_time:
            trails = pygame.Surface(BOARD.size, pygame.SRCALPHA)
            for x, y in self.drop_cells:
                pygame.draw.rect(trails, (*ACCENT, int(65 * self.drop_time / 0.16)),
                                 (x * CELL + 7, y * CELL, CELL - 14, self.drop_distance * CELL))
            self.canvas.blit(trails, BOARD)
        if self.flash_time:
            flash = pygame.Surface((BOARD.w, CELL), pygame.SRCALPHA)
            flash.fill((*ACCENT, int(210 * self.flash_time / 0.22)))
            for y in self.flash_rows:
                self.canvas.blit(flash, (BOARD.x, BOARD.y + y * CELL))
        self.canvas.set_clip(None)

    def draw_overlay(self) -> None:
        veil = pygame.Surface(BOARD.size, pygame.SRCALPHA)
        veil.fill((7, 12, 20, 190))
        self.canvas.blit(veil, BOARD)
        rect = pygame.Rect(414, 340, 272, 224)
        pygame.draw.rect(self.canvas, PANEL, rect, border_radius=12)
        pygame.draw.rect(self.canvas, EDGE, rect, width=1, border_radius=12)
        headings = {"ready": "READY TO STACK?", "paused": "TAKE A BREATHER", "over": "ONE MORE ROUND?"}
        titles = {"ready": "Let's play.", "paused": "Paused.", "over": "Game over."}
        self.text(headings[self.state], (550, 365), 11, ACCENT, bold=True, center=True)
        self.text(titles[self.state], (550, 391), 30, bold=True, center=True)
        subtitle = f"Final score  {self.game.score:,}" if self.state == "over" else (
            "Your stack can wait." if self.state == "paused" else "Find your flow. Clear a line.")
        self.text(subtitle, (550, 436), 13, MUTED, center=True)
        button = pygame.Rect(442, 479, 216, 40)
        pygame.draw.rect(self.canvas, ACCENT, button, border_radius=6)
        action = "RESUME" if self.state == "paused" else "PLAY AGAIN" if self.state == "over" else "START GAME"
        self.text(f"ENTER  /  {action}", (550, 491), 12, BG, bold=True, center=True)
        self.text("P also resumes" if self.state == "paused" else "A little focus. A lot of blocks.", (550, 533), 10, MUTED, center=True)

    def render(self) -> None:
        self.canvas.fill(BG)
        # Subtle arcade scanlines stay behind the interface and playfield.
        for y in range(0, SIZE[1], 4):
            pygame.draw.line(self.canvas, (14, 20, 30), (0, y), (SIZE[0], y))
        for x, y in shape("T"):
            pygame.draw.rect(self.canvas, ACCENT, (64 + x * 13, 47 + y * 13, 11, 11), border_radius=2)
        self.text("GK TETRIS", (118, 38), 30, bold=True)
        self.text("THE CLASSIC. YOUR RHYTHM.", (120, 79), 10, MUTED, bold=True)
        pygame.draw.circle(self.canvas, ACCENT if self.state == "playing" else MUTED, (883, 59), 4)
        self.text("ARCADE / 01", (900, 48), 16, MUTED, mono=True)
        pygame.draw.line(self.canvas, EDGE, (64, 115), (1036, 115))
        self.text("THE WELL", (400, 129), 10, MUTED, bold=True)
        self.text("10 × 20", (646, 129), 10, MUTED, mono=True)
        self.draw_board()

        self.card((64, 160, 280, 148), "SCORE")
        score_size = 36 if self.game.score < 1000000 else 26
        self.text(f"{self.game.score:07,}", (85, 202), score_size, bold=True, mono=True)
        self.text("BEST", (87, 270), 10, MUTED, bold=True)
        self.text(f"{max(self.settings.best, self.game.score):,}", (139, 264), 17, ACCENT, mono=True)

        self.card((64, 324, 280, 119), "LEVEL")
        self.text(f"{self.game.level:02}", (85, 362), 30, bold=True, mono=True)
        self.text("LINES", (224, 343), 12, MUTED, bold=True)
        self.text(f"{self.game.lines:02}", (224, 362), 30, bold=True, mono=True)
        pygame.draw.rect(self.canvas, EDGE, (86, 415, 236, 4), border_radius=2)
        progress = self.game.lines % 10 / 10
        if progress:
            pygame.draw.rect(self.canvas, ACCENT, (86, 415, int(236 * progress), 4), border_radius=2)

        self.card((64, 459, 280, 169), "HOLD", "C")
        if self.game.held:
            self.preview(self.game.held, (204, 543), 29)
        else:
            self.text("—", (204, 520), 32, EDGE, center=True)
        self.text("NEXT PIECE TO UNLOCK" if self.game.hold_used else "SAVE A PIECE FOR LATER", (204, 599), 10, MUTED, center=True)

        self.text("MAKE ROOM", (86, 668), 11, ACCENT, bold=True)
        self.text("Every line is a fresh start.", (86, 693), 14, MUTED)
        self.text("Keep the stack low. Keep going.", (86, 716), 12, MUTED)

        self.card((756, 160, 280, 280), "UP NEXT", "03")
        for index, kind in enumerate(list(self.game.queue)[:3]):
            self.text(f"0{index + 1}", (779, 226 + index * 74), 11, MUTED, mono=True)
            self.preview(kind, (909, 237 + index * 74), 25 if index == 0 else 22)
            if index < 2:
                pygame.draw.line(self.canvas, EDGE, (778, 277 + index * 74), (1013, 277 + index * 74))

        self.card((756, 456, 280, 304), "HOW TO PLAY")
        controls = (("← →", "Move"), ("↑", "Rotate"), ("↓", "Instant drop"), ("C", "Hold piece"), ("P", "Pause"))
        for i, (key, action) in enumerate(controls):
            y = 502 + i * 36
            pygame.draw.rect(self.canvas, (31, 41, 57), (778, y, 59, 27), border_radius=4)
            self.text(key, (807, y + 3), 15, TEXT, mono=True, center=True)
            self.text(action, (855, y + 4), 14, MUTED)
        pygame.draw.line(self.canvas, EDGE, (778, 693), (1013, 693))
        self.text("M  Sound", (778, 713), 11, MUTED, mono=True)
        self.text("N  Music", (918, 713), 11, MUTED, mono=True)

        if self.notice_time and self.state == "playing":
            self.text(self.notice, (550, 776), 14, ACCENT, bold=True, center=True)
        else:
            self.text("BUILD. CLEAR. REPEAT.", (550, 778), 10, MUTED, center=True)
        pygame.draw.line(self.canvas, EDGE, (64, 811), (1036, 811))
        self.text("ORIGINAL ARCADE SOUND", (64, 825), 9, MUTED, bold=True)
        status = "AUDIO UNAVAILABLE" if not self.audio.available else "SOUND OFF" if self.settings.muted else (
            "MUSIC + SFX" if self.settings.music else "SFX ONLY")
        self.text(status, (880, 825), 9, ACCENT, bold=True)
        if self.state != "playing":
            self.draw_overlay()
        w, h = self.screen.get_size()
        scale = min(w / SIZE[0], h / SIZE[1])
        scaled = (max(1, int(SIZE[0] * scale)), max(1, int(SIZE[1] * scale)))
        self.screen.fill((6, 9, 15))
        surface = self.canvas if scaled == SIZE else pygame.transform.smoothscale(self.canvas, scaled)
        self.screen.blit(surface, ((w - scaled[0]) // 2, (h - scaled[1]) // 2))
        pygame.display.flip()

    def close(self) -> None:
        self.persist()
        self.audio.close()
        pygame.quit()

    def run(self, smoke: bool = False, screenshot: Path | None = None) -> None:
        frames = 0
        try:
            while self.running:
                dt = min(self.clock.tick(60) / 1000.0, 0.1)
                for event in pygame.event.get():
                    self.handle(event)
                self.update(dt)
                self.render()
                frames += 1
                if smoke and frames >= 5:
                    break
            if screenshot:
                screenshot.parent.mkdir(parents=True, exist_ok=True)
                pygame.image.save(self.screen, str(screenshot))
        finally:
            self.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="GK Tetris desktop arcade game")
    parser.add_argument("--smoke-test", action="store_true", help="Render five frames and exit without saving preferences")
    parser.add_argument("--screenshot", type=Path, help="Save the final window as a PNG")
    args = parser.parse_args()
    if args.smoke_test:
        os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
        os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    App(persistent=not args.smoke_test).run(args.smoke_test, args.screenshot)


if __name__ == "__main__":
    main()
