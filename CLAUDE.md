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
- Dips are read **once at boot**. Coins per credit = dip value + 1, so all off = 1 and all on = 16 (`MIN_COINS`-`MAX_COINS`). This is deliberate, so changing them mid-game can't award credits. Power-cycle to apply a new setting.
- Main loop polls every 1 ms and never blocks. Coin inputs are debounced (`COIN_DEBOUNCE_MS`) on both edges, and a coin counts only on the debounced leading edge.
- Each channel queues credits and sends them as non-blocking pulses (`PULSE_ON_MS` on, `PULSE_GAP_MS` gap).
- Signal polarity is set by `DIP_ON_LEVEL`, `COIN_ACTIVE_LEVEL` and `START_ACTIVE_LEVEL`. Change these rather than the logic.

## Hardware decisions

- Bench tested with a button and an LED on channel 4: working. **Not yet tested in the cabinet.**
- Power: cabinet 5 V into VSYS (physical pin 39) and a shared GND with the cabinet. The Pico boots with the cabinet, well before the game board.
- RP2350 GPIO inputs are 5 V tolerant only while the Pico is powered. Outputs are 3.3 V only. ADC pins GP26-GP28 are not 5 V tolerant. 12 V is never OK.
- Start outputs: wired directly from the GPIO to the JAMMA start line, no transistor. Measured on the game: the start line idles at 3.333 V and drops to ~1.5 V with a 10k load to GND. That means a ~10-12 kΩ pull-up to 3.3 V, so pulling it low sinks only ~0.3 mA. The pin runs open-drain (`START_OPEN_DRAIN = True`, `START_ACTIVE_LEVEL = 0`): released when idle, pulled to GND during a pulse, the same as the button. It is high-impedance at boot. To go back to a 2N7000, set `START_OPEN_DRAIN = False` and `START_ACTIVE_LEVEL = 1`.
- P3/P4 start buttons are not on JAMMA. They go through USB encoder boards (joystick emulation) whose ground is separate from JAMMA ground (~17 mV difference measured). The P3 start pin read ~400 mV idle, about 0 V with 10k to GND, and then 1.6-2 V for a few seconds. Shorting start to the encoder's GND (which is continuous with USB GND) registers a press, so P3/P4 use the same direct open-drain wiring as P1/P2. **The Pico GND must also be wired to the encoder GND.** If P3/P4 get a stray start when the cabinet powers on, it is probably the RP2350's default pull-down acting before `main.py` runs; fix it with a 10k pull-up on the encoder start line. If the direct wiring ever misbehaves, the fallback is a PC817-type optocoupler across the encoder's start and GND (push-pull active-high, which needs per-channel output config in `main.py`).
- Coin inputs: the comparators' COIN wire idles at 12 V and drops to 0 V during a coin. Each one goes through a 2N7000 (reusing the ones removed from the start outputs): gate to the COIN wire, drain to the GPIO (internal pull-up on), source to GND. The transistor inverts the signal, so `COIN_ACTIVE_LEVEL = 1`. A 100k gate-to-GND resistor is optional; it stops phantom coins if a comparator is unplugged. The comparator ground must be common with the Pico GND.
- Dips: wired directly from the GPIO to GND, using the internal pull-ups.
- Noise: try raising `COIN_DEBOUNCE_MS` (keep it below the comparator pulse width) before adding external 4.7-10 kΩ pull-ups to 3V3(OUT). The user prefers a minimal parts count.
- Still to check in the cabinet: whether the game accepts `PULSE_ON_MS`, and that coins aren't double-counted.
