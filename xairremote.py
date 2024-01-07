#cleaned +power off latest version 1pm
# control a Behringer XAIR mixer with a nanoKONTROL connected to a Raspberry Pi
import os
import sys
sys.path.append('python-x32/src')
sys.path.append('python-x32/src/pythonx32')
from re import match
import threading
import time
import socket
from alsa_midi import SequencerClient, WRITE_PORT, MidiBytesEvent
from pythonx32 import x32
bus_changed = 0
found_addr   = -1
is_raspberry = os.uname()[4][:3] == 'arm'
# fader1 = 16  #actual XR ch number
# fader2 = 6
# fader3 = 8
# fader4 = 9
fader = [16,6,8,9]
def main():
  #global found_addr, found_port, fader_init_val, bus_init_val, is_raspberry, bus_changed, fader1, fader2, fader3, fader4, fader
  global found_addr, found_port, fader_init_val, bus_init_val, is_raspberry, bus_changed, fader

  # setup the MIDI sequencer client for xairremote
  client = SequencerClient("xairremote")
  port   = client.create_port("output", caps = WRITE_PORT)
  queue  = client.create_queue()
  queue.start()

  # get the nanoKONTROL ALSA midi port
  dest_ports    = client.list_ports(output = True)
  filtered_port = list(filter(lambda cur_port: match('\W*(nanoKONTROL)\W*', cur_port.name), dest_ports))
  if len(filtered_port) == 0:
    raise Exception('No nanoKONTROL MIDI device found. Is the nanoKONTROL connected?')
  nanoKONTROL_port = filtered_port[0];
  port.connect_from(nanoKONTROL_port)

  try:
    # search for a mixer and initialize the connection to the mixer
    local_port  = 10300
    addr_subnet = '.'.join(get_ip().split('.')[0:3]) # only use first three numbers of local IP address
    while found_addr < 0:
      for j in range(10024, 10022, -1): # X32:10023, XAIR:10024 -> check both
        if found_addr < 0:
          for i in range(2, 255):
            threading.Thread(target = try_to_ping_mixer, args = (addr_subnet, local_port + 1, i, j, )).start()
            if found_addr >= 0:
              break
        if found_addr < 0:
          time.sleep(2) # time-out is 1 second -> wait two-times the time-out

    mixer = x32.BehringerX32(f"{addr_subnet}.{found_addr}", local_port, False, 10, found_port)

    # parse MIDI inevents
    bus_ch          = 7; # define here the bus channel you want to control
    MIDI_table      = nanoKONTROL_MIDI_lookup() # create MIDI table for nanoKONTROL
    AUX_table       = auxBus_lookup()  #Aux bus select lookup
    faderShift_table = faderShift_lookup()  # allows use of solo button to select second fader selection 
    MIDI_statusbyte = 0
    cur_SCENE       = -1
    
    while True:
      try:
        event = client.event_input(prefer_bytes = True)
      except KeyboardInterrupt:
          raise KeyboardInterrupt
      except:
        client.drop_input() # fix "ALSAError: No space left on device"
        continue # avoid "UnboundLocalError: local variable 'event' referenced before assignment"

      if event is not None and isinstance(event, MidiBytesEvent):
        if len(event.midi_bytes) == 3:
          # status byte has changed
          MIDI_statusbyte = event.midi_bytes[0]
          MIDI_databyte1  = event.midi_bytes[1]
          MIDI_databyte2  = event.midi_bytes[2]
        elif len(event.midi_bytes) == 2:
          MIDI_databyte1  = event.midi_bytes[0]
          MIDI_databyte2  = event.midi_bytes[1]

        if len(event.midi_bytes) == 2 or len(event.midi_bytes) == 3:
          # send corresponding OSC commands to the mixer

          d = (MIDI_statusbyte, MIDI_databyte1, MIDI_databyte2)
          if d in AUX_table:
            bus_ch = AUX_table[d]
            query_all_faders(mixer, bus_ch)         

          f = (MIDI_statusbyte, MIDI_databyte1, MIDI_databyte2) # S button push
          if f in faderShift_table:
            x = faderShift_table[f][0] -1
            fader[x] = faderShift_table[f][1]

          c = (MIDI_statusbyte, MIDI_databyte1)
          if c in MIDI_table:
            #channel = MIDI_table[c][2] + 1
            channel = MIDI_table[c][2] 
            value   = MIDI_databyte2 / 127
            if channel ==16:
                channel = fader[0]
            if channel ==7:
                channel = fader[1]
            if channel ==8:
                channel = fader[2]
            if channel ==9:
                channel = fader[3]
            # reset fader init values if SCENE has changed
            if cur_SCENE is not MIDI_table[c][0]:
              query_all_faders(mixer, bus_ch)
              cur_SCENE = MIDI_table[c][0]
            #if MIDI_table[c][0] == 0 and MIDI_table[c][1] == "f": # fader in first SCENE
            if bus_ch == 7:
              ini_value = fader_init_val[channel - 1]
              # only apply value if current fader value is not too far off
              if ini_value < 0 or (ini_value >= 0 and abs(ini_value - value) < 0.01):
                fader_init_val[channel - 1] = -1 # invalidate initial value
                mixer.set_value(f'/ch/{channel:#02}/mix/fader', [value], False)
                threading.Thread(target = switch_pi_board_led, args = (False, )).start() # takes time to process
              else:
                threading.Thread(target = switch_pi_board_led, args = (True, )).start() # takes time to process

           # if MIDI_table[c][0] == 1 and MIDI_table[c][1] == "f": # bus fader in second SCENE
            if (bus_ch <7):
              ini_value = bus_init_val[channel - 1]
              # only apply value if current fader value is not too far off
              if ini_value < 0 or (ini_value >= 0 and abs(ini_value - value) < 0.01):
                bus_init_val[channel - 1] = -1 # invalidate initial value
                mixer.set_value(f'/ch/{channel:#02}/mix/{bus_ch:#02}/level', [value], False)
                threading.Thread(target = switch_pi_board_led, args = (False, )).start() # takes time to process
              else:
                threading.Thread(target = switch_pi_board_led, args = (True, )).start() # takes time to process

            if MIDI_table[c][0] == 3 and MIDI_table[c][1] == "d": # dial in last SCENE
              mixer.set_value(f'/ch/{channel:#02}/mix/pan', [value], False)

           # if is_raspberry and MIDI_table[c][0] == 3 and MIDI_table[c][1] == "b2": # button 2 of last fader in last SCENE
            if MIDI_table[c][0] == 3 and MIDI_table[c][1] == "b2": # button 2 of last fader in last SCENE
              if MIDI_databyte2 == 0: # on turing LED off
                os.system('sudo shutdown -h now')

        #event_s = " ".join(f"{b}" for b in event.midi_bytes)
        #print(f"{event_s}")
  except KeyboardInterrupt:
    pass

def query_all_faders(mixer, bus_ch): # query all current fader values
    global fader_init_val, bus_init_val
    fader_init_val = [0] * 16 # nanoKONTROL has 9 faders
    bus_init_val   = [0] * 16
    for i in range(16): # was(80)
      fader_init_val[i] = mixer.get_value(f'/ch/{i + 1:#02}/mix/fader')[0]
      bus_init_val[i]   = mixer.get_value(f'/ch/{i + 1:#02}/mix/{bus_ch:#02}/level')[0]

def try_to_ping_mixer(addr_subnet, start_port, i, j):
    global found_addr, found_port
    #print(f"{addr_subnet}.{i}:{start_port + i + j}")
    search_mixer = x32.BehringerX32(f"{addr_subnet}.{i}", start_port + i + j, False, 1, j) # just one second time-out
    try:
      search_mixer.ping()
      search_mixer.__del__() # important to delete object before changing found_addr
      found_addr = i
      found_port = j
    except:
      search_mixer.__del__()

mutex = threading.Lock()
def switch_pi_board_led(new_state): # call this function in a separate thread since it might take long to execute
    global is_raspberry, mutex
    # check outside mutex: we rely on fact that flag is set immediately in mutex region
    if new_state is not switch_pi_board_led.state:
      mutex.acquire()
      if is_raspberry and switch_pi_board_led.state and not new_state:
        switch_pi_board_led.state = False
        os.system('echo none | sudo tee /sys/class/leds/led0/trigger')
      if is_raspberry and not switch_pi_board_led.state and new_state:
        switch_pi_board_led.state = True
        os.system('echo default-on | sudo tee /sys/class/leds/led0/trigger')
      mutex.release()
switch_pi_board_led.state = True # function name as static variable

# taken from stack overflow "Finding local IP addresses using Python's stdlib"
def get_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(0)
    try:
      # doesn't even have to be reachable
      s.connect(('10.255.255.255', 1))
      IP = s.getsockname()[0]
    except Exception:
      IP = '127.0.0.1'
    finally:
      s.close()
    return IP


def nanoKONTROL_MIDI_lookup():
    # (scene, type, value), types: "f" is fader, "d" is dial, "b1" is button 1, "b2" is button 2
    # these need to match the faderShift "off " selections below 
    # Orig was XR channel is -1 here so 0 = ch 1 below
    return {(0XB0,  0): (0, "f",  16), (0XB0,  1): (0, "f",  7), (0XB0,  2): (0, "f",  8), (0XB0,  3): (0, "f",  9), (0XB0,  4): (0, "f",  11),
            (0XB0,  5): (0, "f", 13), (0XB0,  6): (0, "f", 14), (0XB0,  7): (0, "f", 15)} #, (0XB0,  8): (0, "f",  8), (0XB0, 71): (3, "b2", 7)}


def auxBus_lookup():
    # (status, cc, value): (auxbus#)
    # number matches actual bus # (vs faders above off by 1)
    return {(0XB0, 43, 127): (1), (0XB0, 44, 127): (2), (0XB0, 42, 127): (3), (0XB0, 41, 127): (4), (0XB0, 45, 127): (5), (0XB0, 46, 127): (6), (0XB0, 46, 0): (7)}
def faderShift_lookup():
    # (status, cc, value): (scene, XRchannelassignment)
    # eg (0XB0, 32, 0): (15) sets the nano fader #1 to channel 16 when the solo button (CC32) is off (0XB0, 32, 127): (0) sets it to 1 when on
    # practice uses electronic drums on ch 16 vs gig acoustic with 4 mices so can use second selection on nano to have 4 mic drum faders
    # number beleow is -1 from actual channel on XR
    return {(0XB0, 32, 0): (1, 16), (0XB0, 32, 127): (1, 1), (0XB0, 33, 0): (2, 7), (0XB0, 33, 127): (2, 2), (0XB0, 34, 0): (3, 8), (0XB0, 34, 127): (3, 3), 
            (0XB0, 35, 0): (4, 9), (0XB0, 35, 127): (4, 4)}

if __name__ == '__main__':
  main()





