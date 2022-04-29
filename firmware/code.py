# SPDX-FileCopyrightText: 2019 Dan Cogliano for Adafruit Industries
#
# SPDX-License-Identifier: MIT

import time
import json
import array
import math
import gc
import board
import busio
import audioio
import audiocore
import displayio
import digitalio
from adafruit_bitmap_font import bitmap_font
from adafruit_display_text import bitmap_label as label
from adafruit_display_shapes.circle import Circle
from adafruit_button import Button
from adafruit_mcp9600 import MCP9600
import adafruit_ili9341
import adafruit_focaltouch
import adafruit_vs1053
from adafruit_display_shapes.roundrect import RoundRect

TITLE = "EZ Make Oven Controller!"
VERSION = "1.3.2"

print(TITLE, "version ", VERSION)
time.sleep(2)

displayio.release_displays()

spi = board.SPI()

tft_cs = board.D10
tft_dc = board.D9

AUDIO_MP3CS = board.D7  # Pin connected to VS1053 CS line.
AUDIO_DREQ = board.D3  # Pin connected to VS1053 DREQ line.
AUDIO_XDCS = board.D6  # Pin connected to VS1053 D/C line.
vs1053 = adafruit_vs1053.VS1053(spi, AUDIO_MP3CS, AUDIO_XDCS, AUDIO_DREQ)
vs1053.set_volume(0, 0)

REFLOW_CONTROL_PIN = board.D13
POWER_SWITCH_STATUS_PIN = board.D4 # Has pull up from display pcb

power_switch_status = digitalio.DigitalInOut(POWER_SWITCH_STATUS_PIN)
power_switch_status.direction = digitalio.Direction.INPUT

i2c = busio.I2C(board.SCL, board.SDA, frequency=100000)
ft = adafruit_focaltouch.Adafruit_FocalTouch(i2c, debug=False)

WIDTH = 240
HEIGHT = 320

display_bus = displayio.FourWire(spi, command=tft_dc, chip_select=tft_cs)
display = adafruit_ili9341.ILI9341(display_bus, width=WIDTH, height=HEIGHT, rotation=90)


# Make the display context
display_group = displayio.Group()
display.show(display_group)

PROFILE_SIZE = 2  # plot thickness
GRID_SIZE = 2
GRID_STYLE = 3
TEMP_SIZE = 2
AXIS_SIZE = 2

BLACK = 0x0
BLUE = 0x2020FF
GREEN = 0x00FF55
RED = 0xFF0000
YELLOW = 0xFFFF00


palette = displayio.Palette(5)
palette[0] = BLACK
palette[1] = GREEN
palette[2] = BLUE
palette[3] = RED
palette[4] = YELLOW

palette.make_transparent(0)

BACKGROUND_COLOR = 0
PROFILE_COLOR = 1
GRID_COLOR = 2
TEMP_COLOR = 3
AXIS_COLOR = 2

GXSTART = 0
GYSTART = 160
GWIDTH = WIDTH - GXSTART
GHEIGHT = HEIGHT - GYSTART
plot = displayio.Bitmap(GWIDTH, GHEIGHT, 4)

display_group.append(
    displayio.TileGrid(plot, pixel_shader=palette, x=GXSTART, y=GYSTART)
)



class Beep(object):
    def __init__(self):
        pass

    # pylint: disable=protected-access
    def play(self, duration=0.1):
        vs1053.sine_test(0x66, duration)

    def stop(self):
        pass
        #if self._speaker_enable.value:
        #    self.duration = 0
        #    self.audio.stop()
        #    self._speaker_enable.value = False

    def refresh(self):
        pass
        #if time.monotonic() - self.start >= self.duration:
        #    self.stop()


class ReflowOvenControl(object):
    states = ("wait", "ready", "start", "preheat", "soak", "reflow", "cool")

    def __init__(self, pin):
        global i2c
        self.oven = digitalio.DigitalInOut(pin)
        self.oven.direction = digitalio.Direction.OUTPUT
        with open("/config.json", mode="r") as fpr:
            self.config = json.load(fpr)
            fpr.close()
        self.sensor_status = False
        with open("/profiles/" + self.config["profile"] + ".json", mode="r") as fpr:
            self.sprofile = json.load(fpr)
            fpr.close()
        try:
            self.sensor = MCP9600(i2c, 0x60, "K")
            self.ontemp = self.sensor.temperature
            self.offtemp = self.ontemp
            self.sensor_status = True
        except ValueError:
            print("temperature sensor not available")
        self.control = False
        self.reset()
        self.beep = Beep()
        self.set_state("ready")
        if self.sensor_status:
            if self.sensor.temperature >= 50:
                self.last_state = "wait"
                self.set_state("wait")

    def reset(self):
        self.ontime = 0
        self.offtime = 0
        self.enable(False)
        self.reflow_start = 0

    def get_profile_temp(self, seconds):
        x1 = self.sprofile["profile"][0][0]
        y1 = self.sprofile["profile"][0][1]
        for point in self.sprofile["profile"]:
            x2 = point[0]
            y2 = point[1]
            if x1 <= seconds < x2:
                temp = y1 + (y2 - y1) * (seconds - x1) // (x2 - x1)
                return temp
            x1 = x2
            y1 = y2
        return 0

    def set_state(self, state):
        self.state = state
        self.check_state()
        self.last_state = state

    # pylint: disable=too-many-branches, too-many-statements
    def check_state(self):
        try:
            temp = self.sensor.temperature
        except AttributeError:
            temp = 32  # sensor not available, use 32 for testing
            self.sensor_status = False
            # set_message("Temperature sensor missing")
        self.beep.refresh()
        if self.state == "wait":
            self.enable(False)
            if self.state != self.last_state:
                # change in status, time for a beep!
                self.beep.play(0.1)
            if temp < 35:
                self.set_state("ready")
                oven.reset()
                draw_profile(sgraph, oven.sprofile)
                timer_data.text = format_time(0)

        if self.state == "ready":
            self.enable(False)
        if self.state == "start" and temp >= 50:
            self.set_state("preheat")
        if self.state == "start":
            set_message("Starting")
            self.enable(True)
        if self.state == "preheat" and temp >= self.sprofile["stages"]["soak"][1]:
            self.set_state("soak")
        if self.state == "preheat":
            set_message("Preheat")
        if self.state == "soak" and temp >= self.sprofile["stages"]["reflow"][1]:
            self.set_state("reflow")
        if self.state == "soak":
            set_message("Soak")
        if (
            self.state == "reflow"
            and temp >= self.sprofile["stages"]["cool"][1]
            and self.reflow_start > 0
            and (
                time.monotonic() - self.reflow_start
                >= self.sprofile["stages"]["cool"][0]
                - self.sprofile["stages"]["reflow"][0]
            )
        ):
            self.set_state("cool")
            self.beep.play(5)
        if self.state == "reflow":
            set_message("Reflow")
            if self.last_state != "reflow":
                self.reflow_start = time.monotonic()
        if self.state == "cool":
            self.enable(False)
            set_message("Cool Down", "Open Door")

        if self.state in ("start", "preheat", "soak", "reflow"):
            if self.state != self.last_state:
                # change in status, time for a beep!
                self.beep.play(0.1)
            # oven temp control here
            # check range of calibration to catch any humps in the graph
            checktime = 0
            checktimemax = self.config["calibrate_seconds"]
            checkoven = False
            if not self.control:
                checktimemax = max(
                    0,
                    self.config["calibrate_seconds"]
                    - (time.monotonic() - self.offtime),
                )
            while checktime <= checktimemax:
                check_temp = self.get_profile_temp(int(timediff + checktime))
                if (
                    temp + self.config["calibrate_temp"] * checktime / checktimemax
                    < check_temp
                ):
                    checkoven = True
                    break
                checktime += 5
            if not checkoven:
                # hold oven temperature
                if (
                    self.state in ("start", "preheat", "soak")
                    and self.offtemp > self.sensor.temperature
                ):
                    checkoven = True
            self.enable(checkoven)

    # turn oven on or off
    def enable(self, enable):
        try:
            self.oven.value = enable
            self.control = enable
            if enable:
                self.offtime = 0
                self.ontime = time.monotonic()
                self.ontemp = self.sensor.temperature
                print("oven on")
            else:
                self.offtime = time.monotonic()
                self.ontime = 0
                self.offtemp = self.sensor.temperature
                print("oven off")
        except AttributeError:
            # bad sensor
            pass


class Graph(object):
    def __init__(self):
        self.xmin = 0
        self.xmax = 720  # graph up to 12 minutes
        self.ymin = 0
        self.ymax = 240
        self.xstart = 0
        self.ystart = 0
        self.width = GWIDTH
        self.height = GHEIGHT

    # pylint: disable=too-many-branches
    def draw_line(self, x1, y1, x2, y2, size=PROFILE_SIZE, color=1, style=1):
        # print("draw_line:", x1, y1, x2, y2)
        # convert graph coords to screen coords
        x1p = self.xstart + self.width * (x1 - self.xmin) // (self.xmax - self.xmin)
        y1p = self.ystart + int(
            self.height * (y1 - self.ymin) / (self.ymax - self.ymin)
        )
        x2p = self.xstart + self.width * (x2 - self.xmin) // (self.xmax - self.xmin)
        y2p = self.ystart + int(
            self.height * (y2 - self.ymin) / (self.ymax - self.ymin)
        )
        # print("screen coords:", x1p, y1p, x2p, y2p)

        if (max(x1p, x2p) - min(x1p, x2p)) > (max(y1p, y2p) - min(y1p, y2p)):
            for xx in range(min(x1p, x2p), max(x1p, x2p)):
                if x2p != x1p:
                    yy = y1p + (y2p - y1p) * (xx - x1p) // (x2p - x1p)
                    if style == 2:
                        if xx % 2 == 0:
                            self.draw_point(xx, yy, size, color)
                    elif style == 3:
                        if xx % 8 == 0:
                            self.draw_point(xx, yy, size, color)
                    elif style == 4:
                        if xx % 12 == 0:
                            self.draw_point(xx, yy, size, color)
                    else:
                        self.draw_point(xx, yy, size, color)
        else:
            for yy in range(min(y1p, y2p), max(y1p, y2p)):
                if y2p != y1p:
                    xx = x1p + (x2p - x1p) * (yy - y1p) // (y2p - y1p)
                    if style == 2:
                        if yy % 2 == 0:
                            self.draw_point(xx, yy, size, color)
                    elif style == 3:
                        if yy % 8 == 0:
                            self.draw_point(xx, yy, size, color)
                    elif style == 4:
                        if yy % 12 == 0:
                            self.draw_point(xx, yy, size, color)
                    else:
                        self.draw_point(xx, yy, size, color)

    def draw_graph_point(self, x, y, size=PROFILE_SIZE, color=1):
        """ draw point using graph coordinates """

        # wrap around graph point when x goes out of bounds
        x = (x - self.xmin) % (self.xmax - self.xmin) + self.xmin
        xx = self.xstart + self.width * (x - self.xmin) // (self.xmax - self.xmin)
        yy = self.ystart + int(self.height * (y - self.ymin) / (self.ymax - self.ymin))
        print("graph point:", x, y, xx, yy)
        self.draw_point(xx, max(0 + size, yy), size, color)

    def draw_point(self, x, y, size=PROFILE_SIZE, color=1):
        """Draw data point on to the plot bitmap at (x,y)."""
        if y is None:
            return
        offset = size // 2
        for xx in range(x - offset, x + offset + 1):
            if xx in range(self.xstart, self.xstart + self.width):
                for yy in range(y - offset, y + offset + 1):
                    if yy in range(self.ystart, self.ystart + self.height):
                        try:
                            yy = GHEIGHT - yy
                            plot[xx, yy] = color
                        except IndexError:
                            pass


def draw_profile(graph, profile):
    """Update the display with current info."""
    for i in range(GWIDTH * GHEIGHT):
        plot[i] = 0

    # draw stage lines
    # preheat
    graph.draw_line(
        profile["stages"]["preheat"][0],
        profile["temp_range"][0],
        profile["stages"]["preheat"][0],
        profile["temp_range"][1] * 1.1,
        GRID_SIZE,
        GRID_COLOR,
        GRID_STYLE,
    )
    graph.draw_line(
        profile["time_range"][0],
        profile["stages"]["preheat"][1],
        profile["time_range"][1],
        profile["stages"]["preheat"][1],
        GRID_SIZE,
        GRID_COLOR,
        GRID_STYLE,
    )
    # soak
    graph.draw_line(
        profile["stages"]["soak"][0],
        profile["temp_range"][0],
        profile["stages"]["soak"][0],
        profile["temp_range"][1] * 1.1,
        GRID_SIZE,
        GRID_COLOR,
        GRID_STYLE,
    )
    graph.draw_line(
        profile["time_range"][0],
        profile["stages"]["soak"][1],
        profile["time_range"][1],
        profile["stages"]["soak"][1],
        GRID_SIZE,
        GRID_COLOR,
        GRID_STYLE,
    )
    # reflow
    graph.draw_line(
        profile["stages"]["reflow"][0],
        profile["temp_range"][0],
        profile["stages"]["reflow"][0],
        profile["temp_range"][1] * 1.1,
        GRID_SIZE,
        GRID_COLOR,
        GRID_STYLE,
    )
    graph.draw_line(
        profile["time_range"][0],
        profile["stages"]["reflow"][1],
        profile["time_range"][1],
        profile["stages"]["reflow"][1],
        GRID_SIZE,
        GRID_COLOR,
        GRID_STYLE,
    )
    # cool
    graph.draw_line(
        profile["stages"]["cool"][0],
        profile["temp_range"][0],
        profile["stages"]["cool"][0],
        profile["temp_range"][1] * 1.1,
        GRID_SIZE,
        GRID_COLOR,
        GRID_STYLE,
    )
    graph.draw_line(
        profile["time_range"][0],
        profile["stages"]["cool"][1],
        profile["time_range"][1],
        profile["stages"]["cool"][1],
        GRID_SIZE,
        GRID_COLOR,
        GRID_STYLE,
    )

    # draw labels
    x = profile["time_range"][0]
    y = profile["stages"]["reflow"][1]
    xp = int(GXSTART + graph.width * (x - graph.xmin) // (graph.xmax - graph.xmin))
    yp = int(GHEIGHT * (y - graph.ymin) // (graph.ymax - graph.ymin))

    label_reflow.x = xp + 10
    label_reflow.y = HEIGHT - yp
    label_reflow.text = str(profile["stages"]["reflow"][1])
    print("reflow temp:", str(profile["stages"]["reflow"][1]))
    print("graph point: ", x, y, "->", xp, yp)

    x = profile["stages"]["reflow"][0]
    y = profile["stages"]["reflow"][1]

    # draw time line (horizontal)
    graph.draw_line(
        graph.xmin, graph.ymin + 1, graph.xmax, graph.ymin + 1, AXIS_SIZE, AXIS_COLOR, 1
    )
    graph.draw_line(
        graph.xmin, graph.ymax, graph.xmax, graph.ymax, AXIS_SIZE, AXIS_COLOR, 1
    )
    # draw time ticks
    tick = graph.xmin
    while tick < (graph.xmax - graph.xmin):
        graph.draw_line(
            tick, graph.ymin, tick, graph.ymin + 10, AXIS_SIZE, AXIS_COLOR, 1
        )
        graph.draw_line(
            tick,
            graph.ymax,
            tick,
            graph.ymax - 10 - AXIS_SIZE,
            AXIS_SIZE,
            AXIS_COLOR,
            1,
        )
        tick += 60

    # draw temperature line (vertical)
    graph.draw_line(
        graph.xmin, graph.ymin, graph.xmin, graph.ymax, AXIS_SIZE, AXIS_COLOR, 1
    )
    graph.draw_line(
        graph.xmax - AXIS_SIZE + 1,
        graph.ymin,
        graph.xmax - AXIS_SIZE + 1,
        graph.ymax,
        AXIS_SIZE,
        AXIS_COLOR,
        1,
    )
    # draw temperature ticks
    tick = graph.ymin
    while tick < (graph.ymax - graph.ymin) * 1.1:
        graph.draw_line(
            graph.xmin, tick, graph.xmin + 10, tick, AXIS_SIZE, AXIS_COLOR, 1
        )
        graph.draw_line(
            graph.xmax,
            tick,
            graph.xmax - 10 - AXIS_SIZE,
            tick,
            AXIS_SIZE,
            AXIS_COLOR,
            1,
        )
        tick += 50

    # draw profile
    x1 = profile["profile"][0][0]
    y1 = profile["profile"][0][1]
    for point in profile["profile"]:
        x2 = point[0]
        y2 = point[1]
        graph.draw_line(x1, y1, x2, y2, PROFILE_SIZE, PROFILE_COLOR, 1)
        # print(point)
        x1 = x2
        y1 = y2


def format_time(seconds):
    minutes = seconds // 60
    seconds = int(seconds) % 60
    return "{:02d}:{:02d}".format(minutes, seconds, width=2)

timediff = 0
oven = ReflowOvenControl(REFLOW_CONTROL_PIN)
print("melting point: ", oven.sprofile["melting_point"])
font1 = bitmap_font.load_font("/fonts/OpenSans-9.bdf")

font2 = bitmap_font.load_font("/fonts/OpenSans-12.bdf")

font3 = bitmap_font.load_font("/fonts/OpenSans-16.bdf")

label_reflow = label.Label(font1, text="", color=0xFFFFFF, line_spacing=0)
label_reflow.x = 0
label_reflow.y = -20
display_group.append(label_reflow)
#title_label = label.Label(font3, text=TITLE)
#title_label.x = 5
#title_label.y = 14
#display_group.append(title_label)
profile_label = label.Label(font1, text="Profile:", color=0xAAAAAA)
profile_label.x = 5
profile_label.y = 10
display_group.append(profile_label)
profile_data = label.Label(font1, text=oven.sprofile["title"])
profile_data.x = 10
profile_data.y = 30-4
display_group.append(profile_data)
alloy_label = label.Label(font1, text="Alloy:", color=0xAAAAAA)
alloy_label.x = 5
alloy_label.y = 80-30-4
display_group.append(alloy_label)
alloy_data = label.Label(font1, text=str(oven.sprofile["alloy"]))
alloy_data.x = 10
alloy_data.y = 100-30-8
display_group.append(alloy_data)
timer_label = label.Label(font1, text="Time:", color=0xAAAAAA)
timer_label.x = 5
timer_label.y = 120-30-8
display_group.append(timer_label)
timer_data = label.Label(font3, text=format_time(timediff))
timer_data.x = 10
timer_data.y = 140-30-12
display_group.append(timer_data)
temp_label = label.Label(font1, text="Temp(C):", color=0xAAAAAA)
temp_label.x = 5
temp_label.y = 160-30-12
display_group.append(temp_label)
temp_data = label.Label(font3, text="--")
temp_data.x = 10
temp_data.y = 180-30-16
display_group.append(temp_data)
circle = Circle(308, 12, 8, fill=0)
display_group.append(circle)
message1 = label.Label(font2, text="Wait")
message1.x = 90
message1.y = 10
display_group.append(message1)
message2 = label.Label(font2, text="")
message2.x = 90
message2.y = 30
display_group.append(message2)

sgraph = Graph()

# sgraph.xstart = 100
# sgraph.ystart = 4
sgraph.xstart = 0
sgraph.ystart = 0
# sgraph.width = WIDTH - sgraph.xstart - 4  # 216 for standard PyPortal
# sgraph.height = HEIGHT - 80  # 160 for standard PyPortal
sgraph.width = GWIDTH  # 216 for standard PyPortal
sgraph.height = GHEIGHT  # 160 for standard PyPortal
sgraph.xmin = oven.sprofile["time_range"][0]
sgraph.xmax = oven.sprofile["time_range"][1]
sgraph.ymin = oven.sprofile["temp_range"][0]
sgraph.ymax = oven.sprofile["temp_range"][1] * 1.1
print("x range:", sgraph.xmin, sgraph.xmax)
print("y range:", sgraph.ymin, sgraph.ymax)
draw_profile(sgraph, oven.sprofile)

#if oven.sensor_status:
button = Button(
    x=WIDTH-80, y=GYSTART-50, width=80, height=40, label="Disabled", label_font=font2, style=Button.ROUNDRECT
)
button._label.y -= 4;
display_group.append(button)

def set_message(line1, line2=""):
    global message1, message2
    message1.text = line1
    message2.text = line2

try:
    display.refresh(target_frames_per_second=60)
except AttributeError:
    display.refresh_soon()
print("display complete")
last_temp = 0
last_state = "ready"
last_control = False
second_timer = time.monotonic()
timer = time.monotonic()
while True:
    gc.collect()
    try:
        display.refresh(target_frames_per_second=60)
    except AttributeError:
        display.refresh_soon()
    oven.beep.refresh()  # this allows beeps less than one second in length

    if power_switch_status.value and oven.state != "cool":
        set_message("Power Disabled")
        if button.label != "Disabled":
            button.label = "Disabled"
            button._label.y -= 4
        continue

    try:
        oven_temp = int(oven.sensor.temperature)
    except AttributeError:
        oven_temp = 32  # testing
        oven.sensor_status = False
        set_message("Bad/missing temp","sensor")
        if button.label != "Disabled":
            button.label = "Disabled"
            button._label.y -= 4
        continue

    if oven.control != last_control:
        last_control = oven.control
        if oven.control:
            circle.fill = 0xFF0000
        else:
            circle.fill = 0x0

    status = ""
    last_status = ""

    touches = ft.touches
    if len(touches) > 0:
        p = touches[0]
        p[0] = p["x"]
        p[1] = p["y"]
        print("touch? %d, %d" %(p["x"], p["y"]))
        if button.contains(p):
            print("touch!")
            if oven.state == "ready":
                button.label = "Stop"
                button._label.y -= 4;
                oven.set_state("start")

            else:
                # cancel operation
                set_message("Wait")
                button.label = "Wait"
                button._label.y -= 4;
                oven.set_state("wait")
            time.sleep(1)  # for debounce
    if oven.sensor_status:
        if oven.state == "ready":
            status = "Ready"
            if last_state != "ready":
                oven.beep.refresh()
                oven.reset()
                draw_profile(sgraph, oven.sprofile)
                timer_data.text = format_time(0)
            if button.label != "Start":
                button.label = "Start"
                button._label.y -= 4;
        if oven.state == "start":
            status = "Starting"
            if last_state != "start":
                timer = time.monotonic()
        if oven.state == "preheat":
            if last_state != "preheat":
                timer = time.monotonic()  # reset timer when preheat starts
            status = "Preheat"
        if oven.state == "soak":
            status = "Soak"
        if oven.state == "reflow":
            status = "Reflow"
        if oven.state == "cool" or oven.state == "wait":
            status = "Cool Down, Open Door"
        if last_status != status:
            set_message(status)
            last_status = status

        if oven_temp != last_temp and oven.sensor_status:
            last_temp = oven_temp
            temp_data.text = str(oven_temp)
        # update once per second when oven is active
        if oven.state != "ready" and time.monotonic() - second_timer >= 1.0:
            second_timer = time.monotonic()
            oven.check_state()
            if oven.state == "preheat" and last_state != "preheat":
                timer = time.monotonic()  # reset timer at start of preheat
            timediff = int(time.monotonic() - timer)
            timer_data.text = format_time(timediff)
            print(oven.state)
            if oven_temp >= 50:
                sgraph.draw_graph_point(
                    int(timediff), oven_temp, size=TEMP_SIZE, color=TEMP_COLOR
                )

        last_state = oven.state
