# Start pulse test: every ROUND_MS, sends one start pulse to each player in
# TEST_PLAYERS, one after another, so PULSE_ON_MS / PULSE_GAP_MS can be tuned
# without coining. Run with "Run current file" (it replaces main.py until reset).
from machine import Pin
import time

START_PINS = (10, 11, 12, 13)    # same as main.py
PLAYER_NUMBERS = (3, 1, 2, 4)    # cabinet player for each start pin, same as main.py
START_ACTIVE_LEVEL = 0           # same as main.py
START_OPEN_DRAIN = True          # same as main.py

TEST_PLAYERS = (1, 3)   # cabinet players to credit each round, pulsed in this order
PULSE_ON_MS = 100       # start pulse width
PULSE_GAP_MS = 1250      # gap after each pulse before the next one
ROUND_MS = 10000        # time from the start of one round to the next
SIMULTANEOUS = False    # True pulses all TEST_PLAYERS at once, to reproduce the missed credit

mode = Pin.OPEN_DRAIN if START_OPEN_DRAIN else Pin.OUT
starts = [Pin(p, mode, value=1 - START_ACTIVE_LEVEL) for p in START_PINS]
pins = [starts[PLAYER_NUMBERS.index(p)] for p in TEST_PLAYERS]
names = ", ".join("P{}".format(p) for p in TEST_PLAYERS)

print("Pulse test: {} every {} ms, on {} ms, gap {} ms, {}".format(
    names, ROUND_MS, PULSE_ON_MS, PULSE_GAP_MS,
    "simultaneous" if SIMULTANEOUS else "in sequence"))
print("Ctrl+C to stop")

rounds = 0
while True:
    round_at = time.ticks_ms()
    rounds += 1
    print("Round {}: {}".format(rounds, names))

    # Timings are measured, not the configured values; times are from the round start
    if SIMULTANEOUS:
        on_at = time.ticks_ms()
        for pin in pins:
            pin.value(START_ACTIVE_LEVEL)
        time.sleep_ms(PULSE_ON_MS)
        for pin in pins:
            pin.value(1 - START_ACTIVE_LEVEL)
        off_at = time.ticks_ms()
        print("  {} pressed at +{} ms, held {} ms".format(
            names, time.ticks_diff(on_at, round_at), time.ticks_diff(off_at, on_at)))
    else:
        last_off = None
        for player, pin in zip(TEST_PLAYERS, pins):
            on_at = time.ticks_ms()
            pin.value(START_ACTIVE_LEVEL)
            time.sleep_ms(PULSE_ON_MS)
            pin.value(1 - START_ACTIVE_LEVEL)
            off_at = time.ticks_ms()

            gap = "" if last_off is None else ", gap before {} ms".format(time.ticks_diff(on_at, last_off))
            print("  P{} pressed at +{} ms, held {} ms{}".format(
                player, time.ticks_diff(on_at, round_at), time.ticks_diff(off_at, on_at), gap))
            last_off = off_at

            # Sleep the rest of the gap, so the print above doesn't lengthen it
            rest = PULSE_GAP_MS - time.ticks_diff(time.ticks_ms(), off_at)
            if rest > 0:
                time.sleep_ms(rest)

    # Wait out the rest of the round, measured from its start
    wait = ROUND_MS - time.ticks_diff(time.ticks_ms(), round_at)
    if wait > 0:
        time.sleep_ms(wait)
