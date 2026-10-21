from machine import Pin
import rp2
import time

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# GPIO numbers (GPxx, not physical pin numbers)
DIP_PINS = (2, 3, 4, 5)          # bit 0 .. bit 3 of the coins-per-credit value
COIN_PINS = (6, 7, 8, 9)         # coin mech pulse inputs, one per player
START_PINS = (10, 11, 12, 13)    # game start pulse outputs, paired with COIN_PINS
PLAYER_NUMBERS = (3, 1, 2, 4)    # cabinet player for each channel, used only in printed output

DIP_ON_LEVEL = 0        # dip switch to GND with pull-up -> ON reads 0
COIN_ACTIVE_LEVEL = 0   # comparator output wired direct: floats when idle (pull-up reads 1), pulls to GND on a coin
START_ACTIVE_LEVEL = 0  # level on the output during a start pulse
START_OPEN_DRAIN = True # True: wired direct, line released when idle (needs START_ACTIVE_LEVEL = 0)
                        # False: push-pull, e.g. driving a 2N7000 gate (START_ACTIVE_LEVEL = 1)

MIN_COINS = 1
MAX_COINS = 16

COIN_DEBOUNCE_MS = 10   # coin input must be stable this long to count
PULSE_ON_MS = 100       # start pulse width
PULSE_GAP_MS = 100      # minimum gap between consecutive start pulses
LOOP_MS = 1

HEARTBEAT_MS = 5000     # onboard LED blips this often to show the program is running
HEARTBEAT_ON_MS = 50    # heartbeat blip length
COIN_FLASH_MS = 250     # onboard LED flash per counted coin (longer than the heartbeat)

TEST_BUTTON_CHANNEL = 1 # BOOTSEL press adds a coin to this channel index (0 = first channel, cabinet P3); None disables
TEST_BUTTON_POLL_MS = 20  # BOOTSEL read interval; reading it briefly pauses flash access


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
# Onboard LED: heartbeat + coin flash
# ---------------------------------------------------------------------------

class StatusLed:
    def __init__(self):
        self.pin = Pin("LED", Pin.OUT, value=0)
        now = time.ticks_ms()
        self.lit = False
        self.off_at = now
        self.next_beat = now

    def flash(self, now, ms):
        # Never cut short a flash that is already running
        off_at = time.ticks_add(now, ms)
        if not self.lit or time.ticks_diff(off_at, self.off_at) > 0:
            self.off_at = off_at
        self.pin.value(1)
        self.lit = True

    def update(self, now):
        if time.ticks_diff(now, self.next_beat) >= 0:
            self.next_beat = time.ticks_add(now, HEARTBEAT_MS)
            self.flash(now, HEARTBEAT_ON_MS)
        elif self.lit and time.ticks_diff(now, self.off_at) >= 0:
            self.pin.value(0)
            self.lit = False


# ---------------------------------------------------------------------------
# Coin input -> start output channel
# ---------------------------------------------------------------------------

IDLE, PULSE_ON, PULSE_GAP = 0, 1, 2


class Channel:
    def __init__(self, index, coin_pin, start_pin, led):
        self.index = index
        self.name = "P{}".format(PLAYER_NUMBERS[index])
        self.led = led
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
                self.add_coin(now)

    def add_coin(self, now, source="coin"):
        self.coins += 1
        self.led.flash(now, COIN_FLASH_MS)
        print("{} {} ({} toward credit)".format(self.name, source, self.coins))

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
            print("{} credit".format(self.name))
        self._drive_output(now)


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def main():
    coins_per_credit = read_coins_per_credit(DIP_PINS)
    led = StatusLed()
    channels = [Channel(i, c, s, led) for i, (c, s) in enumerate(zip(COIN_PINS, START_PINS))]
    print("Coin adapter running. Coins per credit:", coins_per_credit)

    button_down = False
    button_at = time.ticks_ms()

    while True:
        now = time.ticks_ms()

        # BOOTSEL test button: one coin per press. The poll interval also debounces it.
        if TEST_BUTTON_CHANNEL is not None and time.ticks_diff(now, button_at) >= TEST_BUTTON_POLL_MS:
            button_at = now
            pressed = bool(rp2.bootsel_button())
            if pressed and not button_down:
                channels[TEST_BUTTON_CHANNEL].add_coin(now, "test coin")
            button_down = pressed

        for ch in channels:
            ch.update(now, coins_per_credit)
        led.update(now)
        time.sleep_ms(LOOP_MS)


main()