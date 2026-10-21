from machine import Pin
import time

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# GPIO numbers (GPxx, not physical pin numbers)
DIP_PINS = (2, 3, 4, 5)          # bit 0 .. bit 3 of the coins-per-credit value
COIN_PINS = (6, 7, 8, 9)         # coin mech pulse inputs, one per player
START_PINS = (10, 11, 12, 13)    # game start pulse outputs, paired with COIN_PINS

DIP_ON_LEVEL = 0        # dip switch to GND with pull-up -> ON reads 0
COIN_ACTIVE_LEVEL = 1   # 2N7000 inverts: comparator idles at 12 V (GPIO 0), coin drops it to 0 V (GPIO 1)
START_ACTIVE_LEVEL = 0  # level on the output during a start pulse
START_OPEN_DRAIN = True # True: wired direct, line released when idle (needs START_ACTIVE_LEVEL = 0)
                        # False: push-pull, e.g. driving a 2N7000 gate (START_ACTIVE_LEVEL = 1)

MIN_COINS = 1
MAX_COINS = 16

COIN_DEBOUNCE_MS = 10   # coin input must be stable this long to count
PULSE_ON_MS = 500       # start pulse width
PULSE_GAP_MS = 100      # minimum gap between consecutive start pulses
LOOP_MS = 1


# ---------------------------------------------------------------------------
# Dip switches
# ---------------------------------------------------------------------------

def read_coins_per_credit(pins):
    # Read once at boot; changes take effect on the next power cycle
    pins = [Pin(p, Pin.IN, Pin.PULL_UP) for p in pins]
    time.sleep_ms(10)  # let the pull-ups settle before reading

    v = 0
    for bit, pin in enumerate(pins):
        if pin.value() == DIP_ON_LEVEL:
            v |= 1 << bit

    # 4 bits give 0-15; offset so all-off = MIN_COINS, giving 1-16 coins
    return min(v + MIN_COINS, MAX_COINS)


# ---------------------------------------------------------------------------
# Coin input -> start output channel
# ---------------------------------------------------------------------------

IDLE, PULSE_ON, PULSE_GAP = 0, 1, 2


class Channel:
    def __init__(self, index, coin_pin, start_pin):
        self.index = index
        self.coin = Pin(coin_pin, Pin.IN, Pin.PULL_UP)
        mode = Pin.OPEN_DRAIN if START_OPEN_DRAIN else Pin.OUT
        self.start = Pin(start_pin, mode, value=1 - START_ACTIVE_LEVEL)

        now = time.ticks_ms()
        self.raw = self._coin_active()
        self.stable = self.raw
        self.changed_at = now

        self.coins = 0          # coins inserted toward the next credit
        self.pending = 0        # credits waiting to be pulsed out
        self.state = IDLE
        self.state_at = now

    def _coin_active(self):
        return self.coin.value() == COIN_ACTIVE_LEVEL

    def _poll_coin(self, now):
        raw = self._coin_active()
        if raw != self.raw:
            self.raw = raw
            self.changed_at = now
        elif raw != self.stable and time.ticks_diff(now, self.changed_at) >= COIN_DEBOUNCE_MS:
            self.stable = raw
            if raw:  # count on the leading edge of a debounced pulse
                self.coins += 1
                print("P{} coin ({} toward credit)".format(self.index + 1, self.coins))

    def _drive_output(self, now):
        elapsed = time.ticks_diff(now, self.state_at)
        if self.state == IDLE:
            if self.pending:
                self.pending -= 1
                self.start.value(START_ACTIVE_LEVEL)
                self.state = PULSE_ON
                self.state_at = now
        elif self.state == PULSE_ON:
            if elapsed >= PULSE_ON_MS:
                self.start.value(1 - START_ACTIVE_LEVEL)
                self.state = PULSE_GAP
                self.state_at = now
        elif self.state == PULSE_GAP:
            if elapsed >= PULSE_GAP_MS:
                self.state = IDLE

    def update(self, now, coins_per_credit):
        self._poll_coin(now)
        if self.coins >= coins_per_credit:
            self.coins -= coins_per_credit
            self.pending += 1
            print("P{} credit".format(self.index + 1))
        self._drive_output(now)


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def main():
    coins_per_credit = read_coins_per_credit(DIP_PINS)
    channels = [Channel(i, c, s) for i, (c, s) in enumerate(zip(COIN_PINS, START_PINS))]
    print("Coin adapter running. Coins per credit:", coins_per_credit)

    while True:
        now = time.ticks_ms()
        for ch in channels:
            ch.update(now, coins_per_credit)
        time.sleep_ms(LOOP_MS)


main()