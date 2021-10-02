# aeronear

Raspberry Pi-based ambient device showing the nearest aircraft in real-time.

Forked for local dump1090 of FR24 feeder integration and other free APIs for extra data and images.

# planes_config.py

Set your lon and lat location and set the address of your dump1090 aircraft.json or Flightradar24 feeder flights.json. You can select the source with the SOURCE option.


# Required packages

Here is a list of commands to install the required packages.

sudo apt install fbi<br>
sudo apt install python3<br>
sudo apt install libopenjp3d7<br>
sudo apt install python3-pip<br>
sudo pip3 install Pillow<br>
sudo pip3 install neopixel<br>
sudo pip3 install adafruit-circuitpython-neopixel<br>
sudo apt-get install python3-rpi.gpio<br>