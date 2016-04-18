#!/usr/bin/env python

import sys
from decocare.lib import CRC8
from mmeowlink.exceptions import CommsException,InvalidPacketReceived
from mmeowlink.vendors.subg_rfspy_link import SubgRfspyLink

class MMTune:
  FREQ_RANGES = {
    'US': { 'start': 916.5, 'end': 916.9, 'default': 916.63 },
    'WW': { 'start': 868.3, 'end': 868.9, 'default': 868.36 }
  }

  def __init__(self, link, pumpserial, radio_locale='US'):
    self.link = link

    # MMTune can only be used with the SubgRfspy firmware, as MMCommander
    # cannot change frequencies
    assert type(link) == SubgRfspyLink

    self.pumpserial = pumpserial
    self.radio_locale = radio_locale

    self.scan_range = self.FREQ_RANGES[self.radio_locale]

  def run(self):

    ############################################################################
    # Commented these out as they may be causing issues with certain pumps:
    ############################################################################
    # self.link.update_register(SubgRfspyLink.REG_MDMCFG4, 0xa9)
    #
    # # Sometimes getting lower ber with 0x07 here (default is 0x03)
    # self.link.update_register(SubgRfspyLink.REG_AGCCTRL2, 0x07)
    #
    # self.link.update_register(SubgRfspyLink.REG_AGCCTRL1, 0x40)
    #
    # # With rx bw > 101kzHZ, this should be 0xB6, otherwise 0x56
    # self.link.update_register(SubgRfspyLink.REG_FREND1, 0x56)
    #
    # # default (0x91) seems to work best
    # #self.link.update_register(SubgRfspyLink.REG_AGCCTRL0, 0x91)

    #print "waking..."
    self.wakeup()

    #print "scanning..."
    results = self.scan_over_freq(self.scan_range['start'], self.scan_range['end'], 20)
    results_sorted = list(reversed(sorted(results, key=lambda x: x[1:])))

    set_freq = self.scan_range['default']
    used_default = True
    if results_sorted[0][1] > 0:
      used_default = False
      set_freq = float(results_sorted[0][0])
    self.link.set_base_freq(set_freq)
    output = {'scanDetails': results, 'setFreq': set_freq, 'usedDefault': used_default}
    return output

  def run_trial(self, var):
    sample_size = 5
    success_count = 0
    error_count = 0
    rssi_readings = []
    for i in xrange(sample_size):
      self.send_packet("a7" + self.pumpserial + "8d00") # Get Model
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
