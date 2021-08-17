# -*- coding: utf-8 -*-

# Small device that shows the nearest plane using Dump1090



from PIL import Image, ImageDraw, ImageFont
import os
import csv
import requests
import math
import haversine

import RPi.GPIO as GPIO
import time
import neopixel
import board

import subprocess

# make sure we are in the same working directory
abspath = os.path.abspath(__file__)
dname = os.path.dirname(abspath)
os.chdir(dname)

# Contains API_KEY, MY_LAT, MY_LONG and RADIUS

from planes_config import MY_LAT, MY_LONG

# Contains the north and position variables and is used to avoid
# calibration position is the current position of the stepper motor in
# the range 0 to revolution-1. north is the LED that points to north.

from planes_position import north, position

# FUNCTIONS TO READ THE BLUE PUSH BUTTON

GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)

BUTTON_PIN = 23
GPIO.setup(BUTTON_PIN, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

def button_wait():
    while GPIO.input(BUTTON_PIN) == GPIO.LOW:
        pass


# FUNCTIONS FOR THE CIRCULAR STRIP OF LEDS THAT INDICATE DIRECTION TO
# THE AIRCRAFT

LED_COUNT = 16
STRIP_PIN = board.D18
strip = neopixel.NeoPixel(STRIP_PIN, LED_COUNT, brightness=0.3)


# strip_clear turns off every LED on the strip, call strip.show()
# to update the strip after calling this
def strip_clear():
    for i in range(0, LED_COUNT):
        strip[i] = (0, 0, 0)


# strip_spin lights up each LED on the strip in turn and finishes with
# them all off
def strip_spin():
    strip_clear()
    strip.show()

    for i in range(0, LED_COUNT):
        if i > 0:
            strip[i - 1] = (0, 0, 0)
        strip[i] = (0, 0, 128)
        strip.show()
        time.sleep(0.1)

    strip_clear()
    strip.show()


# FUNCTIONS TO CONTROL THE MODEL AIRCRAFT USED TO INDICATE THE TRACK
# OF THE AIRCRAFT

# These are the GPIO pins to which the four coils are connected

coilApin = 4
coilBpin = 17
coilCpin = 27
coilDpin = 22

# There are revolution steps of the motor in a complete revolution and
# degree degrees per step

revolution = 2038
degree = 2038 / 360

# This defines the sequence of coil activations for the stepper motor
# and current_step contains the step that was laste used to move the
# model aircraft

steps = 4
seq = list(range(steps))
seq[0] = [True, True, False, False]
seq[1] = [False, True, True, False]
seq[2] = [False, False, True, True]
seq[3] = [True, False, False, True]

current_step = 0

GPIO.setup(coilApin, GPIO.OUT)
GPIO.setup(coilBpin, GPIO.OUT)
GPIO.setup(coilCpin, GPIO.OUT)
GPIO.setup(coilDpin, GPIO.OUT)


# motor_set_coils sets the coils on the stepper motor and is typically
# used with seq[] above
def motor_set_coils(a, b, c, d):
    GPIO.output(coilApin, a)
    GPIO.output(coilBpin, b)
    GPIO.output(coilCpin, c)
    GPIO.output(coilDpin, d)


# motor_step moves the motor one step. The direction is determined by
# the clockwise parameter (True for clockwise) and this function
# updates position and current_step to keep track of the current motor
# position and which step in seq[] to use next
def motor_step(clockwise):
    global position
    global current_step

    if clockwise:
        current_step += 1
        position += 1
    else:
        current_step -= 1
        position -= 1

    current_step %= steps
    position %= revolution

    motor_set_coils(seq[current_step][0], seq[current_step][1],
                    seq[current_step][2], seq[current_step][3])


# motor_off turns off all the coils on the stepper motor. Since there
# is no torque on the motor needed between movements we can switch it
# off
def motor_off():
    motor_set_coils(False, False, False, False)


# plane_rotate moves the plane count steps in a clockwise or
# anti-clockwise direction with a delay of delay seconds between steps
def plane_rotate(delay, count, clockwise=True):
    for i in range(count):
        motor_step(clockwise)
        time.sleep(delay)
    motor_off()


# Since the stepper motor moves in units of 360/2038 degrees there will
# be errors in the position which accumulate over time. We keep track
# here and then fix the position when the error grows larger than a
# single step.

accumulated_error = 0.0


# plane_trak moves the plane to point to the angle trak degrees from
# north. It uses the position variable to determine the number of
# steps needed and goes by the shortest route (clockwise or
# anti-clockwise)
def plane_track(track):
    d = track * degree - position
    delta = int(d)

    global accumulated_error
    accumulated_error += (d - delta)
    if abs(accumulated_error) >= 1:
        fix = int(accumulated_error)
        delta += fix
        accumulated_error -= fix

    clockwise = delta > 0
    delta = abs(delta)

    if delta > revolution / 2:
        delta = revolution - delta
        clockwise = not clockwise

    plane_rotate(0.002, delta, clockwise)


# findcsv reads a CSV file from filename and tries to find match in
# column col. If it finds it returns the row, if it doesn't it returns
# a fake row containing match. Yeah, this really should just read the
# CSV once on startup and make a dictionary but this allowed me to
# fiddle with the CSV files while the program was running
def findcsv(filename, col, match):
    with open(filename, 'r') as f:
        r = csv.reader(f)
        for row in r:
            if row[col] == match.strip():
                return row

    return [match, match, match, match, match]


# getplanes calls the Dump1090 API to get the JSON containing
# planes. It returns the result of requests.get()
def getplanes():
    try:
        url = "http://192.168.1.61/dump1090/data/aircraft.json"
        return requests.get(url)
    except requests.exceptions.ConnectionError:
        return ""


def getplaneExtraData(hexcode):
    try:
        url = "https://api.joshdouch.me/api/aircraft/%s" % (hexcode)
        return requests.get(url)
    except requests.exceptions.ConnectionError:
        return ""


def getplaneReg(hexcode):
    try:
        url = "https://api.joshdouch.me/hex-reg.php?hex=%s" % (hexcode)
        return requests.get(url)
    except requests.exceptions.ConnectionError:
        return ""


def getplaneRoutetoData(callsign):
    try:
        url = "https://api.joshdouch.me/callsign-des_ICAO.php?callsign=%s" % (callsign)
        return requests.get(url)
    except requests.exceptions.ConnectionError:
        return ""


def getplaneRoutefromData(callsign):
    try:
        url = "https://api.joshdouch.me/callsign-origin_ICAO.php?callsign=%s" % (callsign)
        return requests.get(url)
    except requests.exceptions.ConnectionError:
        return ""


def getplaneImg(hexcode):
    try:
        url = "https://api.joshdouch.me/hex-image-v2-thumb.php?hex=%s" % (hexcode)
        imgurl = requests.get(url).text
        if len(imgurl) > 1:
            return requests.get(imgurl, stream=True)
        else:
            return False
    except:
        return False


# FUNCTIONS FOR DRAWING TEXT AND IMAGES ON THE SCREEN

# flag tries to find the flag of the country named in country
# by looking for a file called images/country.gif (any spaces
# in the country name are turned into -). If found it inserts
# the flag into img and then returns the new x position where
# its safe to write to the image and not overwrite the flag.
# All flags are resized to 38x25 for consistency
def flag(img, country, x, y):
    country_gif = 'images/' + country.lower() + '.gif'
    country_gif = country_gif.replace(' ', '-')

    if os.path.isfile(country_gif):
        country_img = Image.open(country_gif, 'r')
        img.paste(country_img.resize((38, 25)), (x, y + 3))
        country_img.close()
        return x + 45

    return x


# The number of pixels to leave between lines of text on the screen

spacing = 4

last_text = ''


# text writes a line of text to d automatically adjusting the font
# size to fit the text on screen. It returns the new y position where
# text can be written based on the size of the text and the spacing
# value. Note that it uses last_text to automatically prevent the same
# string being written twice sequentially (this is done to eliminate
# airports that have the same name as the town they are in)
#
# The up parameter determines whether the text is being written top to
# bottom on the screen (up = False) or up from the bottom (up = True)
#
# The default (preferred) font size is s (in pt) and will
# automatically be reduced until the text fits across the screen
def text(d, x, y, t, s, up=False, position='l', colour=(240, 240, 240)):
    global last_text
    if last_text == t:
        return y
    last_text = t

    while s >= 10:
        lx = x
        f = ImageFont.truetype('DejaVuSansMono.ttf', s)
        (w, h) = f.getsize(t)
        if position == 'r':
            lx = x - w
            if lx < 200:
                lx = 200
        if position == 'c':
            lx = x - (w/2)
        if w <= 320 - lx:
            if up:
                y -= h
            d.text((lx, y), t, colour, font=f)

            if up:
                return y - spacing
            else:
                return y + h + spacing

        s -= 2
    return y


plane_picture = '/tmp/planepic.jpg'
screen_tmp = '/tmp/planes.tmp.png'
screen_file = '/tmp/planes.png'
screen_links = ['/tmp/planes%d.png' % i for i in range(1, 4)]


# screen_show takes an image in img and writes it to a file and then
# uses fbi to draw it to the screen
def screen_show(img):
    # This is done to prevent fbi from getting an error if it tries to
    # read one of the images it is displaying while we write it. It's
    # written to a temporary file and then mv'ed into place.

    img.save(screen_tmp)
    subprocess.run('mv %s %s' % (screen_tmp, screen_file), shell=True)

    # Determine if there are any instance of fbi running. Start one if
    # there is not
    running = []
    try:
        running = subprocess.check_output(['pgrep', 'fbi']).decode("utf-8").strip().split('\n')
    except:
        pass

    if len(running) == 0:
        subprocess.run('fbi -t 1 -T 2 -a -cachemem 0 -noverbose -d /dev/fb1 %s' % ' '.join(screen_links),
                       shell=True)


# screen_start sets up the screen for use. The most important thing it
# does is create three symbolic links that are fed to fbi in
# screen_show. This is a trick to get fbi to cycle through images and
# allow a single fbi instance to updated smoothly
def screen_start():
    subprocess.run(['pkill', 'fbcp'])

    for l in screen_links:
        subprocess.run(['ln -s %s %s' % (screen_file, l)], shell=True)


# get a colour for the strip LEDs depending on the altitude.
def altitude_colour(alt):
    # Input a value 0 to 255 to get a color value.
    # The colours are a transition r - g - b - back to r.

    pos = int(alt / 100)
    if pos > 340:
        pos = 340
    elif pos < 0:
        pos = 0
    if pos < 85:
        r = 255
        g = int(pos * 3)
        b = 0
    elif pos < 170:
        pos -= 85
        r = int(255 - pos * 3)
        g = 255
        b = 0
    elif pos < 255:
        pos -= 170
        r = 0
        g = 255
        b = int(pos * 3)
    else:
        pos -= 255
        r = 0
        g = int(255 - pos * 3)
        b = 255
    return r, g, b


# spotted is called when an aircraft has been found and it updates the
# screen, moves the model aircraft to track the actual aircraft and
# sets the LED strip to show where to look for it
def spotted(flight, airline, from_airport, from_country,
            to_airport, to_country, aircraftmodel, type, altitude,
            bearing, track, reg, photo, dist):
    strip_clear()
    strip[(north - int(LED_COUNT * bearing / 360)) % LED_COUNT] = altitude_colour(altitude)
    strip.show()

    img = Image.new('RGB', (320, 480), color=(0, 0, 0))
    d = ImageDraw.Draw(img)

    y = 0
    y = text(d, 160, y, airline, 32, position='c')
    text(d, 310, y, reg, 24, position='r')
    y = text(d, 10, y, flight, 24)
    text(d, 310, y, str(aircraftmodel), 24, position='r')
    y = text(d, 10, y, str(round(dist,1)) + ' miles', 24)
    text(d, 310, y, str(type), 24, position='r')
    y = text(d, 10, y, str(altitude) + ' ft', 24)
    y += 3
    d.line([(0, y), (320, y)])
    y += 3
    # TODO: do this on loading the CSV
    from_airport = from_airport.replace(' Airport', '')
    to_airport = to_airport.replace(' Airport', '')
    from_airport = from_airport.replace(' International', '')
    to_airport = to_airport.replace(' International', '')

    y = text(d, 160, y, from_airport, 24, position='c')
    flag(img, from_country, 10, y)
    y = text(d, 160, y, from_country, 24, position='c')
    y += spacing

    icon = Image.open('images/down.png', 'r')
    (w, h) = icon.size
    img.paste(icon, (int(160-(w/2)), y), icon)
    icon.close()
    y += h + spacing

    y = text(d, 160, y, to_airport, 24, position='c')
    flag(img, to_country, 10, y)
    y = text(d, 160, y, to_country, 24, position='c')
    y += spacing * 2
    if photo is not False:
        pic = Image.open(plane_picture, 'r')
        basewidth = 220
        wpercent = (basewidth / float(pic.size[0]))
        hsize = int((float(pic.size[1]) * float(wpercent)))
        pic = pic.resize((basewidth, hsize), Image.ANTIALIAS)
        (w, h) = pic.size
        img.paste(pic, box=(40, 470-h))
    screen_show(img)
    plane_track(track)
    save_position()


# save_position saves the current plane position and calibrated north
# in planes_position.py so that when the program reloads it can avoid
# calibration
def save_position():
    f = open('planes_position.py', 'w')
    f.writelines(['north = %d\n' % north, 'position = %d\n' % position])
    f.close()


# distance returns the distance to an aircraft
def distance(a):
    return haversine.haversine((MY_LAT, MY_LONG), (float(a['lat']), float(a['lon'])), unit=haversine.Unit.NAUTICAL_MILES)


# bearing works out the bearing of one lat/long from another
def bearing(la1, lo1, la2, lo2):
    lat1 = math.radians(la1)
    lat2 = math.radians(la2)

    diff = math.radians(lo2 - lo1)

    x = math.sin(diff) * math.cos(lat2)
    y = math.cos(lat1) * math.sin(lat2) - (math.sin(lat1)
                                           * math.cos(lat2) * math.cos(diff))

    b = math.degrees(math.atan2(x, y))
    return (b + 360) % 360


# blank is used to ensure that the screen and LEDs are off when
# there's no activity. It shuts off the screen after drawing black
# image on it and shuts off the LEDs.
def blank(screenText = "No aircraft"):
    strip_clear()
    strip.show()
    img = Image.new('RGB', (320, 480), color=(0, 0, 0))
    d = ImageDraw.Draw(img)
    text(d, 160, 180, screenText, 32, position='c')
    screen_show(img)


# select aircraft to lock onto
def select_aircraft_screen(nearac, index):
    strip_clear()
    strip.show()
    img = Image.new('RGB', (320, 480), color=(0, 0, 0))
    d = ImageDraw.Draw(img)
    y = 0
    y += 3
    d.line([(0, y), (320, y)])
    y += 3
    for step in range(len(nearac)):
        if step == index:
            y = text(d, 160, y, nearac[step]['flight'], 32, position='c', colour=(255, 255, 255))
        else:
            y = text(d, 160, y, nearac[step]['flight'], 32, position='c', colour=(150, 150, 150))
        y += 3
        d.line([(0, y), (320, y)])
        y += 3
    if len(nearac) == index:
        y = text(d, 160, y, "Auto select", 32, position='c', colour=(255, 255, 255))
    else:
        y = text(d, 160, y, "Auto select", 32, position='c', colour=(150, 150, 150))
    y += 3
    d.line([(0, y), (320, y)])
    y += 3
    screen_show(img)


# calibrate_plane is used to point the model aircraft to north on
# startup. The user rotates the the plane by holding down the blue
# button until it points in the right direction and then releases
# it. After five seconds with no pressure on the button the plane's
# position is set
def calibrate_plane():
    button_wait()

    c = time.time()

    while (time.time() - c) < 5:
        if GPIO.input(BUTTON_PIN) == GPIO.HIGH:
            plane_rotate(0.01, 4, True)
            c = time.time()


# calibrate_strip is used on start up to find the position of north
# where the device is installed. The user needs to hold the blue
# button down until the LED closest to north is illuminated. After 5
# seconds without touching the blue button the north position is fixed
# and returned by the function. This function leaves the LED pointing
# to north illuminated but in a different colour to show that the
# user's choice is confirmed
def calibrate_strip():
    strip_clear()
    strip.show()
    button_wait()

    i = LED_COUNT-1
    strip[i] = (0, 0, 128)
    strip.show()
    c = time.time()

    while (time.time() - c) < 5:
        if GPIO.input(BUTTON_PIN) == GPIO.HIGH:
            strip[i] = (0, 0, 0)
            i = (i - 1) % LED_COUNT
            strip[i] = (0, 0, 128)
            strip.show()
            time.sleep(0.2)
            c = time.time()

    strip[i] = (128, 0, 0)
    strip.show()
    return i


def calibration():
    global north
    global position
    blank("Set LED to north")
    north = calibrate_strip()
    blank("Set plane to north")
    calibrate_plane()
    position = 0
    save_position()

# required contains a list of fields that must be present and
# non-empty in the returned JSON

required = ['hex', 'lat', 'lon', 'track', 'altitude', 'flight']

strip_spin()

strip_clear()
strip.show()

screen_start()

if north == -1:
    calibration()

blank("Starting up")

# The default update_delay is 5000 milliseconds. Until an aircraft is seen
# the code checks once every 30 seconds for new aircraft; once
# tracking a plane it updates every ten seconds. Once there are no
# more planes it goes back to checking every 30 seconds

no_planes_delay = 500
tracking_plane_delay = 500
calibration_delay = 500
update_delay = 0
currentPlane = ""
button_state = False
select_aircraft = False
select_aircraft_hex = ""

planemake = ""
planetype = ""
airline = ""
flight = ''
from_airport = ''
from_city = ''
from_country = ''
to_airport = ''
to_city = ''
to_country = ''
reg = ''
photo = False
blanked = True


while True:

    planes = getplanes()
    if planes is not "":
        j = planes.json()

        if j is None or j['aircraft'] is None:
            print("No planes received")
            blank()
            blanked = True
            continue

        # Build near so that it contains aircraft that have all the fields
        # in required and are not on the ground

        near = []
        for ac in j['aircraft']:
            ok = True
            for r in required:
                if r not in ac:
                    ok = False
                    break

            if ok and ac['altitude'] != "ground":
                near.append(ac)

        # If there are aircraft then sort them by distance from the device
        # and display the nearest

        if len(near) > 0:
            blanked = False
            #print(len(near).__str__() + " planes nearby")
            if select_aircraft:
                ac = None
                for single in near:
                    if single["hex"] == select_aircraft_hex:
                        ac = single
                if ac is None:
                    #print("Plane lock lost")
                    select_aircraft = False
                    near.sort(key=distance)
                    ac = near[0]
            else:
                near.sort(key=distance)
                ac = near[0]
            if ac['hex'] != currentPlane:
                #print("New plane received")
                currentPlane = ac['hex']
                extra = getplaneExtraData(ac['hex']).json()
                reg = getplaneReg(ac['hex']).text
                photo = getplaneImg(ac['hex'])
                if photo != False:
                    with open(plane_picture, 'wb') as f:
                        f.write(photo.content)
                try:
                    extra['ModeS']
                except:
                    planemake = ""
                    planetype = ""
                    airline = ""
                else:
                    planemake = extra['Manufacturer']
                    planetype = extra['Type']
                    airline = extra['RegisteredOwners']
                try:
                    flight = ac['flight'].strip()
                except:
                    flight = ''
                    from_airport = ''
                    from_city = ''
                    from_country = ''
                    to_airport = ''
                    to_city = ''
                    to_country = ''
                else:
                    from_ = findcsv('airports.dat', 5, getplaneRoutefromData(flight).text[:4])
                    from_airport = from_[1]
                    from_city = from_[2]
                    from_country = from_[3]
                    to_ = findcsv('airports.dat', 5, getplaneRoutetoData(flight).text[:4])
                    to_airport = to_[1]
                    to_city = to_[2]
                    to_country = to_[3]
            altitude = ac['altitude']
            b = bearing(MY_LAT, MY_LONG, float(ac['lat']), float(ac['lon']))
            track = float(ac['track'])
            spotted(flight, airline, from_airport, from_country,
                    to_airport, to_country, planemake, planetype, altitude, b, track, reg, photo, distance(ac))
            update_delay = tracking_plane_delay
        else:
            update_delay = no_planes_delay
            if not blanked:
                blank()
                blanked = True
            #print("No planes nearby")

        count = 0
        button_count = 0
        select_index = 0
        while count <= update_delay:
            time.sleep(0.01)
            if GPIO.input(BUTTON_PIN) == GPIO.HIGH and not button_state:
                #print("button pressed")
                button_state = True
                button_count = 0
                count = 0
            elif GPIO.input(BUTTON_PIN) == GPIO.LOW and button_state:
                #print("button released")
                button_state = False
                if select_aircraft:
                    select_index += 1
                    if len(near) == select_index:
                        select_aircraft = False
                    else:
                        select_aircraft_hex = near[select_index]['hex']
                    select_aircraft_screen(near, select_index)
                elif not blanked:
                    select_aircraft = True
                    select_index = 0
                    select_aircraft_screen(near, select_index)
                    select_aircraft_hex = near[select_index]['hex']

            if button_state:
                button_count += 1
                if button_count >= calibration_delay:
                    button_state = False
                    calibration()
            else:
                count += 1
