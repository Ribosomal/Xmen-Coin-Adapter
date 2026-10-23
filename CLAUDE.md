# Xmen Coin Adapter

MicroPython program for a Raspberry Pi Pico 2 (RP2350) in an arcade cabinet. It converts coin pulses from 4 coin comparators into game start pulses, with the number of coins per credit set by 4 dip switches.

## Development

- VS Code + MicroPico extension (`paulober.pico-w-go`). Disable other MicroPython extensions; they fight over the serial port.
- "Run current file" to test; "Upload project to Pico" so `main.py` runs at boot.
- Debug output prints to the MicroPico vREPL (`Px coin`, `Px credit`, coins per credit at startup).

## How main.py works

- Pins are GPIO numbers (GPxx), not physical pin numbers:
  - Dips: GP2-GP5 (bit 0-3)
  - Coin inputs: GP6-GP9 (P1-P4)
  - Start outputs: GP10-GP13, paired with coin inputs by index
  - `PLAYER_NUMBERS = (3, 1, 2, 4)` gives the cabinet player for each channel. It only changes the printed `Px` labels (here and in `coin_probe.py`); the wiring and logic stay by channel index. Channel 1 (GP6/GP10) is cabinet P3, channel 2 is P1, channel 3 is P2 and channel 4 is P4.
- Dips are read **once at boot**. Coins per credit = dip value + 1, so all off = 1 and all on = 16 (`MIN_COINS`-`MAX_COINS`). This is deliberate, so changing them mid-game can't award credits. Power-cycle to apply a new setting.
- Main loop polls every 1 ms and never blocks. Coin inputs are debounced (`COIN_DEBOUNCE_MS`) on both edges, and a coin counts only on the debounced leading edge.
- Onboard LED (`Pin("LED")`, GP25): a 50 ms heartbeat blip every `HEARTBEAT_MS` (5 s) and a longer `COIN_FLASH_MS` flash on each counted coin. Non-blocking, driven from the main loop.
- Test button: pressing the BOOTSEL button (`rp2.bootsel_button()`, polled every `TEST_BUTTON_POLL_MS`) adds one coin to `TEST_BUTTON_CHANNEL` (P1). Set it to `None` to disable it.
- Each channel queues credits. The main loop sends them as non-blocking pulses (`PULSE_ON_MS` on, `PULSE_GAP_MS` gap), **one pulse at a time across all channels**, round-robin between channels with queued credits. The game missed a credit when two channels pulsed at once (found in the cabinet), so keep the gap global. Tuned in the cabinet with `pulse_test.py`: the game needs ~1.2 s between starts, so `PULSE_GAP_MS = 1250` with `PULSE_ON_MS = 100`.
- Signal polarity is set by `DIP_ON_LEVEL`, `COIN_ACTIVE_LEVEL` and `START_ACTIVE_LEVEL`. Change these rather than the logic.

## Hardware decisions

- Bench tested with a button and an LED on channel 4: working. **Not yet tested in the cabinet.**
- Power: cabinet 5 V into VSYS (physical pin 39) and a shared GND with the cabinet. The Pico boots with the cabinet, well before the game board.
- Pico 1 (RP2040) compatibility: `main.py` runs unchanged (flash the RP2040 MicroPython firmware). But RP2040 GPIO are **not** 5 V tolerant; nothing above 3.3 V may reach a pin. The current wiring meets this (JAMMA start lines measured 3.33 V). Re-measure the start lines if the game board changes.
- RP2350 GPIO inputs are 5 V tolerant only while the Pico is powered. Outputs are 3.3 V only. ADC pins GP26-GP28 are not 5 V tolerant. 12 V is never OK.
- Start outputs: wired directly from the GPIO to the JAMMA start line, no transistor. Measured on the game: the start line idles at 3.333 V and drops to ~1.5 V with a 10k load to GND. That means a ~10-12 kΩ pull-up to 3.3 V, so pulling it low sinks only ~0.3 mA. The pin runs open-drain (`START_OPEN_DRAIN = True`, `START_ACTIVE_LEVEL = 0`): released when idle, pulled to GND during a pulse, the same as the button. It is high-impedance at boot. To go back to a 2N7000, set `START_OPEN_DRAIN = False` and `START_ACTIVE_LEVEL = 1`.
- P3/P4 start buttons are not on JAMMA. They go through USB encoder boards (joystick emulation) whose ground is separate from JAMMA ground (~17 mV difference measured). The P3 start pin read ~400 mV idle, about 0 V with 10k to GND, and then 1.6-2 V for a few seconds. Shorting start to the encoder's GND (which is continuous with USB GND) registers a press, so P3/P4 use the same direct open-drain wiring as P1/P2. **The Pico GND must also be wired to the encoder GND.** If P3/P4 get a stray start when the cabinet powers on, it is probably the RP2350's default pull-down acting before `main.py` runs; fix it with a 10k pull-up on the encoder start line. If the direct wiring ever misbehaves, the fallback is a PC817-type optocoupler across the encoder's start and GND (push-pull active-high, which needs per-channel output config in `main.py`).
- Coin inputs: wired directly, no transistor. The 12 V seen on the coin wire earlier came from a pull-up on the JAMMA side, not from the comparator. The comparator's N/O output has no voltage of its own; it floats when idle and pulls to GND during a coin. The comparator connects only to the Pico (disconnected from the JAMMA coin wiring, so 12 V can't reach a GPIO), with N/O to the GPIO (internal pull-up) and `COIN_ACTIVE_LEVEL = 0`. The Pico GND must be tied to cabinet GND. Without it the inputs were very noisy. The measured coin pulse is ~20 ms, so `COIN_DEBOUNCE_MS = 10` is half the pulse width. Keep it there.
- `coin_probe.py`: a standalone diagnostic ("Run current file"). It prints debounced coin pin changes with pulse widths in ms and counts the noise flips it filters out.
- `pulse_test.py`: a standalone diagnostic ("Run current file"). Every `ROUND_MS` it sends one start pulse to each player in `TEST_PLAYERS` (cabinet numbers), in sequence with its own `PULSE_ON_MS` and `PULSE_GAP_MS`, or all at once with `SIMULTANEOUS = True`. Use it to tune the gap without coining, then copy the values into `main.py`.
- Dips: wired directly from the GPIO to GND, using the internal pull-ups.
- Noise: try raising `COIN_DEBOUNCE_MS` (keep it below the comparator pulse width) before adding external 4.7-10 kΩ pull-ups to 3V3(OUT). The user prefers a minimal parts count.
- Still to check in the cabinet: whether the game accepts `PULSE_ON_MS`, and that coins aren't double-counted.
