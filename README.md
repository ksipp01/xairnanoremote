# Python script to control a Behringer XAIR mixer with a Korg nanoKONTROL connected to a Raspberry Pi
TEST----THIS IS A FORKED README----TEST
Credit:  https://github.com/corrados/xairnanoremote 

This is a modified version for the nanoKontrol2 and designed specifically for use with IEM (Aux 1-5) and Subwoofer on Aux 6.
The 5 lower left buttons select the Aux bus
The “cycle” button selects main LR mix or subwoofer on Aux 6
Channels are set up for our most frequently needed channels to adjust which are not necessarily 1-8. 
We practice with electronic drums on Ch 16 but use acoustic drums at live gigs so 1-4 are mics.  You can see me hit the solo button on 1-4 which allows an alternate channel assignment for 1-4.


The Python script [xairremote.py](xairremote.py) implements the connection between the Korg nanoKONTROL MIDI mixer with
a Behringer X-AIR or X32 digital mixer. The nanoKONTROL is connected to a Raspberry Pi (e.g. a Raspberry Pi Zero W)
using USB and the connection from the Raspberry Pi to the Behringer mixer is either via wireless LAN (WiFi) or
an Ethernet cable. The protocol used to talk to the Behringer mixer is OSC (using the library [python-x32](https://github.com/tjoracoder/python-x32)).

You can see the script in action in this ([https://youtu.be/CBD8GMQ4UX4](https://youtu.be/Pw0nQCNP3Sk?si=7Ub4uTrc2NJqnx6E)).


## Setup Raspberry Pi

Use the following commands to setup the Raspberry Pi and start the script:

```
sudo apt-get update
sudo apt-get dist-upgrade
sudo apt-get install git python3-pip
python3 -m pip install alsa-midi
git clone https://github.com/ksipp01/xairnanoremote.git
cd xairnanoremote
git submodule update --init
python3 xairremote.py
```

Optionally, insert the following line in rc.local to auto start the script on boot up of the
Raspberry Pi:

```
su pi -c 'cd /home/pi/xairnanoremote;sleep 15;python3 xairremote.py' &
```


## Debugging with X32 emulator by pmaillot

I have used an X32 emulator software by pmaillot to create the Python script. To compile and run
the emulator, you can use the following commands:

```
cd X32-Behringer
make
make X32
cd build
./X32 -i127.0.0.1
```

