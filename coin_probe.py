# Coin input probe: prints debounced level changes on the coin pins with timing,
# plus how many raw noise flips were filtered out. Run with "Run current file".
from machine import Pin
import time

COIN_PINS = (6, 7, 8, 9)   # same as main.py
PLAYER_NUMBERS = (3, 1, 2, 4)  # cabinet player for each coin pin, same as main.py
DEBOUNCE_MS = 10           # level must hold this long to count (match COIN_DEBOUNCE_MS)
NOISE_REPORT_MS = 2000     # how often to report noise on lines that haven't changed

pins = [Pin(p, Pin.IN, Pin.PULL_UP) for p in COIN_PINS]
n = len(pins)
now = time.ticks_ms()
raw = [p.value() for p in pins]
raw_at = [now] * n
stable = list(raw)
stable_at = [now] * n
flips = [0] * n            # raw changes since the last debounced change
noise_at = now

print("Idle levels:", ", ".join("P{}={}".format(PLAYER_NUMBERS[i], v) for i, v in enumerate(stable)))
print("Debounce {} ms. Watching (Ctrl+C to stop)...".format(DEBOUNCE_MS))

while True:
    now = time.ticks_ms()
    for i, p in enumerate(pins):
        v = p.value()
        if v != raw[i]:
            raw[i] = v
            raw_at[i] = now
            flips[i] += 1
        elif v != stable[i] and time.ticks_diff(now, raw_at[i]) >= DEBOUNCE_MS:
            # Width runs from the previous settled edge to the start of this one
            held = time.ticks_diff(raw_at[i], stable_at[i])
            print("P{} {} -> {}  (was {} for {} ms, {} raw flips)".format(
                PLAYER_NUMBERS[i], stable[i], v, stable[i], held, flips[i]))
            stable[i] = v
            stable_at[i] = raw_at[i]
            flips[i] = 0

    if time.ticks_diff(now, noise_at) >= NOISE_REPORT_MS:
        noise_at = now
        for i in range(n):
            # A clean line has 0 flips; a pending real edge has 1
            if flips[i] > 1:
                print("P{} noise: {} raw flips, level held at {}".format(PLAYER_NUMBERS[i], flips[i], stable[i]))
                flips[i] = 0
