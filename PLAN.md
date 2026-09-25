# GK Tetris implementation and publishing plan

## Desktop game

Build a Linux desktop game with Python and Pygame. Use a dark arcade style,
colorful beveled blocks, original looping chiptune music, and synthesized effects.

- A 10×20 visible board, seven tetrominoes, seven-bag randomization, clockwise
  SRS rotation with wall kicks, a landing ghost, hold, and three next previews.
- Left/Right moves with held-key repeat. Up rotates. Down instantly drops and
  locks, once per physical keypress. C holds once per placement.
- Start at one gravity row per second; every ten lines advance a level, using
  `max(0.08, 1.0 * 0.8 ** (level - 1))` seconds per row. Contact allows 500 ms
  before locking, with at most 15 successful movement/rotation resets.
- Score 100/300/500/800 times the current level for one/two/three/four lines,
  plus two points per hard-drop row. End on blocked spawn or a lock above the
  visible board. No T-spin or combo bonuses.
- Resizable, 60 FPS presentation with score, best, level, lines, hold, previews,
  controls, brief clear flashes, and drop trails.
- Enter starts/restarts; P pauses; Escape pauses play and exits menus. Losing
  focus pauses and clears held keys. M mutes all audio; N toggles music.
- Start music on play. Continue silently without audio hardware. Persist best
  score and audio preferences in the XDG configuration directory and tolerate
  missing, corrupt, or unwritable settings.
- Separate deterministic rules, rendering/input, audio, and persistence. Provide
  dependency declarations, a launcher, and installation/play instructions.

## Verification

Test collisions, wall kicks, randomization, hold restrictions, hard drops, row
clears, scoring, level progression, lock delay, and game-over conditions. Use
SDL dummy drivers for automated integration tests and startup smoke tests.
Inspect rendered screenshots and check input repeat, focus pause, resize, audio,
mute, and restart. Document any validation that cannot be performed here.

## Git and GitHub

- Initialize `main` in this directory. Ignore virtual environments, bytecode,
  caches, coverage, build artifacts, editor metadata, credentials, and local
  agent metadata. Track the implementation, tests, docs, and this plan.
- Inspect staged content before creating the initial commit.
- Verify GitHub authentication, then create the public repository
  `klaasdevelopment/gktetris`, set `origin`, and push `main`. If it already
  exists, inspect it first and never overwrite history.
- Confirm clean status, branch tracking, public visibility, and matching commits.
- Default to source distribution without an installer. Do not add a license
  without a license choice. No multiplayer, online services, or borrowed assets.

## Environment findings

The starting project was empty and had no initialized Git repository. Python
3.14 and the GitHub CLI were installed. The configured GitHub account is
`klaasdevelopment`; its initial authentication check failed inside the network
sandbox, but a subsequent authenticated API call with network access succeeded.

## Implementation verification

The game, launcher, documentation, and test suite are implemented. All 33 tests
pass on Python 3.14.7 with pygame-ce 2.5.8. The headless startup smoke test passes.
A native X11 run confirmed available audio, rendered gameplay and menu screens,
and exercised focus pause and resume. Screenshots were visually inspected; the
gameplay screenshot is included in the README. Sound playback was exercised
programmatically, without a subjective listening review.
