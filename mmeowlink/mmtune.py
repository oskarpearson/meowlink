#!/usr/bin/env python
import os
import sys
import json
from decocare.lib import CRC8
from mmeowlink.exceptions import CommsException,InvalidPacketReceived
from mmeowlink.vendors.subg_rfspy_link import SubgRfspyLink

try:
  xrange
except NameError:
  xrange = range

class MMTune:
  FREQ_RANGES = {
    'US': { 'start': 916.300, 'end': 916.900, 'default': 916.630 },
    'WW': { 'start': 868.150, 'end': 868.750, 'default': 868.328 }
  }

  def __init__(self, link, pumpserial, radio_locale='US'):
    self.link = link

    # MMTune can only be used with the SubgRfspy firmware, as MMCommander
    # cannot change frequencies
    assert isinstance(link, SubgRfspyLink)

    self.pumpserial = pumpserial
    self.radio_locale = radio_locale

    self.scan_range = self.FREQ_RANGES[self.radio_locale]

  def run(self):
    #print "waking..."
    self.wakeup()

    use_old_settings = False
    filepath = 'mmtune_old.json'
    if os.path.isfile(filepath) and os.path.getsize(filepath) > 0:
      use_old_settings = True

    if use_old_settings:
      try:
        old_run = open('mmtune_old.json', 'r')
        data = json.load(old_run)
        old_run.close()
        if data["usedDefault"] == False:
          testFreq = data["setFreq"]
          self.link.set_base_freq(testFreq)
          results = []
          results.append(self.run_trial("%0.3f" % testFreq))
          if results[0][1] == 5 and results[0][2] > -80:
            output = {'scanDetails': results, 'setFreq': testFreq, 'usedDefault': False}
            return output
      except (ValueError, KeyError):
        pass 

    #print "scanning..."
    results = self.scan_over_freq(self.scan_range['start'], self.scan_range['end'], 25)
    results_sorted = list(reversed(sorted(results, key=lambda x: x[1:])))

    top_results = [result for result in results if result[2] == results_sorted[0][2]]
    results_sorted = list(sorted(top_results, key=lambda x: x[0:]))
    chosen_result = len(results_sorted) // 2

    set_freq = self.scan_range['default']
    used_default = True
    if results_sorted[chosen_result][1] > 0:
      used_default = False
      set_freq = float(results_sorted[chosen_result][0])
    self.link.set_base_freq(set_freq)
    output = {'scanDetails': results, 'setFreq': set_freq, 'usedDefault': used_default}
    return output

  def run_trial(self, var):
    sample_size = 5
    success_count = 0
    error_count = 0
    rssi_readings = []
    for i in xrange(sample_size):
      self.send_packet("a7" + self.pumpserial + "8000") # DO not use 8d00 (get model), as it fails on 512/712. Use 8000 (get history). 
      try:
        packet = self.get_packet(0.080)
        success_count += 1
        rssi_readings.append(packet["rssi"])
      except (CommsException,InvalidPacketReceived):
        error_count += 1
        rssi_readings.append(-99)

    avg_rssi = sum(rssi_readings)/len(rssi_readings)

    #print "%s, %d, rssi:%0.1f" % (var, error_count, avg_rssi)
    return [var, success_count, avg_rssi]


  def scan_over_freq(self, start_freq, end_freq, steps):
    step_size = (end_freq - start_freq) / steps
    cur_freq = start_freq
    results = []
    while cur_freq < end_freq:
      self.link.set_base_freq(cur_freq)
      results.append(self.run_trial("%0.3f" % cur_freq))
      cur_freq += step_size
    return results

  def send_packet(self, data, repetitions=1, repetition_delay=0, timeout=1):
    buf = bytearray()
    buf.extend(data.decode('hex'))
    buf.extend([CRC8.compute(buf)])
    self.link.write(buf, repetitions=repetitions, repetition_delay=repetition_delay, timeout=timeout)

  def get_packet(self, timeout):
    return self.link.get_packet(timeout)

  def wakeup(self):
    awake = False
    for i in xrange(3):
      self.send_packet("a7" + self.pumpserial + "8d00")
      try:
        packet = self.get_packet(0.08)
        #print "packet = " + str(packet)
      except (CommsException, InvalidPacketReceived):
        packet = None
        #print "No response..."
        pass
      if packet:
        #print "Woke up pump: " + str(packet)
        awake = True
        break

    if awake != True:
      # Pump in free space
      self.link.set_base_freq(self.scan_range['default'])

      # Send 200 wake-up packets
      self.send_packet("a7" + self.pumpserial + "5d00", repetitions=200, timeout=4.5)
      try:
        wake_ack = self.get_packet(9) # wait 9 s for response
      except (CommsException, InvalidPacketReceived):
        wake_ack = None
        #print "No response..."
        pass
