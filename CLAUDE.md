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
- Dips are read **once at boot** and clamped to `MIN_COINS`-`MAX_COINS` (1-8). This is deliberate, so changing them mid-game can't award credits. Power-cycle to apply a new setting.
- Main loop polls every 1 ms and never blocks. Coin inputs are debounced (`COIN_DEBOUNCE_MS`) on both edges, and a coin counts only on the debounced leading edge.
- Each channel queues credits and sends them as non-blocking pulses (`PULSE_ON_MS` on, `PULSE_GAP_MS` gap).
- Signal polarity is set by `DIP_ON_LEVEL`, `COIN_ACTIVE_LEVEL` and `START_ACTIVE_LEVEL`. Change these rather than the logic.

## Hardware decisions

- Bench tested with a button and an LED on channel 4: working. **Not yet tested in the cabinet.**
- Power: cabinet 5 V into VSYS (physical pin 39) and a shared GND with the cabinet. The Pico boots with the cabinet, well before the game board.
- RP2350 GPIO inputs are 5 V tolerant only while the Pico is powered. Outputs are 3.3 V only. ADC pins GP26-GP28 are not 5 V tolerant. 12 V is never OK.
- Start outputs: 2N7000 low-side switch. Drain to the start line (assumed active-low with a game-side pull-up), source to GND, gate to the GPIO. The gate-to-source pull-down was skipped because the Pico boots before the game. `START_ACTIVE_LEVEL = 1`.
- Coin inputs: the comparators' output type is still unknown. Measure the COIN wire at rest with the comparator powered:
  - ~0 V or floating: open-collector, so wire it directly and use the internal pull-up.
  - ~12 V: it needs a 2N7000 or optocoupler.
  - A 2N7000 on an input inverts the signal, so set `COIN_ACTIVE_LEVEL = 1`.
- Dips: wired directly from the GPIO to GND, using the internal pull-ups.
- Noise: try raising `COIN_DEBOUNCE_MS` (keep it below the comparator pulse width) before adding external 4.7-10 kΩ pull-ups to 3V3(OUT). The user prefers a minimal parts count.
- Still to check in the cabinet: start line voltage (expect ~5 V idle, ~0 V when pressed), comparator output type, whether the game accepts `PULSE_ON_MS`, and that coins aren't double-counted.
