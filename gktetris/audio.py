"""Original procedural chiptune and effects; no downloaded audio assets."""

from array import array
import pygame

RATE = 22050


def frequency(note: int) -> float:
    return 440.0 * 2 ** ((note - 69) / 12)


def tone(note: int, duration: float, volume: float = 0.2, triangle: bool = False) -> array:
    count = int(RATE * duration)
    hz = frequency(note)
    samples = array("h")
    for i in range(count):
        phase = (i * hz / RATE) % 1.0
        wave = (1 - 4 * abs(phase - 0.5)) if triangle else (1 if phase < 0.25 else -0.33)
        envelope = min(1.0, i / (RATE * 0.006), (count - i) / (RATE * 0.025))
        samples.append(int(32767 * volume * envelope * wave))
    return samples


def effect(notes: tuple[int, ...], duration: float = 0.05) -> pygame.mixer.Sound:
    samples = array("h")
    for note in notes:
        samples.extend(tone(note, duration))
    return pygame.mixer.Sound(buffer=samples)


def soundtrack() -> pygame.mixer.Sound:
    # An original eight-bar melody, with triangle bass and a soft arpeggio.
    melody = (
        76, 0, 79, 83, 81, 79, 76, 74,
        72, 76, 79, 0, 76, 74, 72, 71,
        69, 0, 72, 76, 79, 76, 72, 74,
        71, 74, 78, 0, 81, 78, 74, 71,
        76, 79, 83, 86, 83, 81, 79, 76,
        72, 0, 76, 79, 84, 83, 79, 76,
        74, 77, 81, 84, 81, 77, 74, 72,
        71, 74, 78, 81, 78, 74, 75, 0,
    )
    roots = (40, 36, 33, 35, 40, 36, 38, 35)
    duration = 0.18
    count = int(RATE * duration)
    song = array("h")
    for beat, note in enumerate(melody):
        lead = tone(note, duration, 0.11) if note else array("h", [0]) * count
        root = roots[beat // 8]
        bass = tone(root + (12 if beat % 2 else 0), duration, 0.12, triangle=True)
        arp = tone(root + (24, 31, 36, 31)[beat % 4], duration, 0.045, triangle=True)
        song.extend(a + b + c for a, b, c in zip(lead, bass, arp))
    return pygame.mixer.Sound(buffer=song)


class Audio:
    def __init__(self):
        self.available = False
        self.muted = False
        self.sounds: dict[str, pygame.mixer.Sound] = {}
        try:
            pygame.mixer.init(frequency=RATE, size=-16, channels=1, buffer=512, allowedchanges=0)
            pygame.mixer.set_num_channels(12)
            pygame.mixer.set_reserved(1)
            self.channel = pygame.mixer.Channel(0)
            self.song = soundtrack()
            self.sounds = {
                "move": effect((60,), 0.018),
                "rotate": effect((72, 79), 0.026),
                "hold": effect((79, 72), 0.045),
                "drop": effect((48, 36, 24), 0.035),
                "lock": effect((43,), 0.035),
                "clear": effect((72, 76, 79, 84), 0.065),
                "tetris": effect((72, 76, 79, 84, 88, 91), 0.07),
                "game_over": effect((64, 62, 59, 55, 52, 40), 0.13),
                "start": effect((60, 67, 72, 79), 0.06),
            }
            self.available = True
        except pygame.error:
            pass

    def sync(self, muted: bool, music: bool, playing: bool) -> None:
        self.muted = muted
        if not self.available:
            return
        if muted:
            for i in range(1, pygame.mixer.get_num_channels()):
                pygame.mixer.Channel(i).stop()
        if playing and music and not muted:
            if not self.channel.get_busy():
                self.channel.play(self.song, loops=-1)
            self.channel.unpause()
        else:
            self.channel.pause()

    def play(self, name: str) -> None:
        if self.available and not self.muted and name in self.sounds:
            channel = pygame.mixer.find_channel()
            if channel is not None:
                channel.play(self.sounds[name])

    def close(self) -> None:
        if self.available:
            pygame.mixer.quit()
