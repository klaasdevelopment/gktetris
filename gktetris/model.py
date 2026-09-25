"""Deterministic falling-block rules. No rendering, audio, or wall-clock access."""

from collections import deque
from dataclasses import dataclass, replace
import random

WIDTH, HEIGHT, HIDDEN = 10, 20, 2
LOCK_DELAY = 0.5
MAX_RESETS = 15

SPAWNS = {
    "I": ((0, 1), (1, 1), (2, 1), (3, 1)),
    "O": ((1, 0), (2, 0), (1, 1), (2, 1)),
    "T": ((1, 0), (0, 1), (1, 1), (2, 1)),
    "J": ((0, 0), (0, 1), (1, 1), (2, 1)),
    "L": ((2, 0), (0, 1), (1, 1), (2, 1)),
    "S": ((1, 0), (2, 0), (0, 1), (1, 1)),
    "Z": ((0, 0), (1, 0), (1, 1), (2, 1)),
}

# SRS clockwise kick offsets in board coordinates (positive y points down).
JLSTZ_KICKS = (
    ((0, 0), (-1, 0), (-1, -1), (0, 2), (-1, 2)),
    ((0, 0), (1, 0), (1, 1), (0, -2), (1, -2)),
    ((0, 0), (1, 0), (1, -1), (0, 2), (1, 2)),
    ((0, 0), (-1, 0), (-1, 1), (0, -2), (-1, -2)),
)
I_KICKS = (
    ((0, 0), (-2, 0), (1, 0), (-2, 1), (1, -2)),
    ((0, 0), (-1, 0), (2, 0), (-1, -2), (2, 1)),
    ((0, 0), (2, 0), (-1, 0), (2, -1), (-1, 2)),
    ((0, 0), (1, 0), (-2, 0), (1, 2), (-2, -1)),
)


def shape(kind: str, rotation: int = 0) -> tuple[tuple[int, int], ...]:
    cells = SPAWNS[kind]
    if kind == "O":
        return cells
    size = 4 if kind == "I" else 3
    for _ in range(rotation % 4):
        cells = tuple((size - 1 - y, x) for x, y in cells)
    return cells


@dataclass(frozen=True)
class Piece:
    kind: str
    x: int = 3
    y: int = -1
    rotation: int = 0

    def cells(self) -> tuple[tuple[int, int], ...]:
        return tuple((self.x + x, self.y + y) for x, y in shape(self.kind, self.rotation))


@dataclass(frozen=True)
class GameEvent:
    name: str
    rows: tuple[int, ...] = ()
    cells: tuple[tuple[int, int], ...] = ()
    distance: int = 0


class Game:
    def __init__(self, seed: int | None = None):
        self.rng = random.Random(seed)
        self.board: list[list[str | None]] = [[None] * WIDTH for _ in range(HEIGHT + HIDDEN)]
        self.queue: deque[str] = deque()
        self.events: list[GameEvent] = []
        self.score = self.lines = 0
        self.held: str | None = None
        self.hold_used = False
        self.over = False
        self.active = Piece("T")
        self.fall_time = self.lock_time = 0.0
        self.lock_resets = 0
        self._spawn()

    @property
    def level(self) -> int:
        return 1 + self.lines // 10

    @property
    def gravity(self) -> float:
        return max(0.08, 0.8 ** (self.level - 1))

    @property
    def grounded(self) -> bool:
        return not self.fits(replace(self.active, y=self.active.y + 1))

    def fits(self, piece: Piece) -> bool:
        return all(
            0 <= x < WIDTH and -HIDDEN <= y < HEIGHT and self.board[y + HIDDEN][x] is None
            for x, y in piece.cells()
        )

    def _spawn(self, kind: str | None = None) -> None:
        if len(self.queue) < 7:
            bag = list(SPAWNS)
            self.rng.shuffle(bag)
            self.queue.extend(bag)
        self.active = Piece(kind if kind is not None else self.queue.popleft())
        self.fall_time = self.lock_time = 0.0
        self.lock_resets = 0
        if not self.fits(self.active):
            self._game_over()

    def _game_over(self) -> None:
        self.over = True
        self.events.append(GameEvent("game_over"))

    def _adjust(self, candidate: Piece) -> bool:
        if self.over or not self.fits(candidate):
            return False
        was_grounded = self.grounded
        self.active = candidate
        if was_grounded and self.lock_resets < MAX_RESETS:
            self.lock_time = 0.0
            self.lock_resets += 1
        return True

    def move(self, dx: int) -> bool:
        if self._adjust(replace(self.active, x=self.active.x + dx)):
            self.events.append(GameEvent("move"))
            return True
        return False

    def rotate(self) -> bool:
        if self.over or self.active.kind == "O":
            return False
        kicks = I_KICKS if self.active.kind == "I" else JLSTZ_KICKS
        for dx, dy in kicks[self.active.rotation]:
            candidate = replace(self.active, x=self.active.x + dx, y=self.active.y + dy,
                                rotation=(self.active.rotation + 1) % 4)
            if self._adjust(candidate):
                self.events.append(GameEvent("rotate"))
                return True
        return False

    def landing(self) -> Piece:
        piece = self.active
        while self.fits(replace(piece, y=piece.y + 1)):
            piece = replace(piece, y=piece.y + 1)
        return piece

    def hard_drop(self) -> None:
        if self.over:
            return
        landing = self.landing()
        distance = landing.y - self.active.y
        self.events.append(GameEvent("drop", cells=self.active.cells(), distance=distance))
        self.score += distance * 2
        self.active = landing
        self._lock()

    def hold(self) -> bool:
        if self.over or self.hold_used:
            return False
        previous = self.held
        self.held = self.active.kind
        self.hold_used = True
        self._spawn(previous)
        self.events.append(GameEvent("hold"))
        return True

    def _lock(self) -> None:
        cells = self.active.cells()
        for x, y in cells:
            self.board[y + HIDDEN][x] = self.active.kind
        self.events.append(GameEvent("lock", cells=cells))
        if any(y < 0 for _, y in cells):
            self._game_over()
            return
        rows = tuple(i - HIDDEN for i, row in enumerate(self.board) if all(row))
        if rows:
            self.score += (0, 100, 300, 500, 800)[len(rows)] * self.level
            self.lines += len(rows)
            remaining = [row for row in self.board if not all(row)]
            self.board = [[None] * WIDTH for _ in rows] + remaining
            self.events.append(GameEvent("clear", rows=rows))
        self.hold_used = False
        self._spawn()

    def update(self, dt: float) -> None:
        """Advance chronologically so landing time isn't counted as grounded time."""
        if self.over:
            return
        remaining = max(0.0, dt)
        while remaining > 1e-9:
            if self.grounded:
                self.lock_time += remaining
                self.fall_time = 0.0
                if self.lock_time + 1e-9 >= LOCK_DELAY:
                    self._lock()
                return
            step = min(remaining, max(0.0, self.gravity - self.fall_time))
            self.fall_time += step
            remaining -= step
            if self.fall_time + 1e-9 >= self.gravity:
                self.active = replace(self.active, y=self.active.y + 1)
                self.fall_time = 0.0

    def drain_events(self) -> list[GameEvent]:
        events, self.events = self.events, []
        return events
