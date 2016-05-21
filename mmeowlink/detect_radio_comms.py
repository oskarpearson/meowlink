import time

from exceptions import CommsException
from hex_handling import hexify

from vendors.mmcommander_link import MMCommanderLink
from vendors.subg_rfspy_link import SubgRfspyLink

class DetectRadioComms(object):
  def __init__(self, link=None, wait_for=5, ignore_wake=False):
    self.link = link
    self.wait_for = wait_for
    self.ignore_wake = ignore_wake

  def detect(self):
    start = time.time()
    assert self.wait_for >= 1

    # We wait for packets 1 second at a time so that we don't exceed the
    # firmware timeout value with 0.6 firmware:
    while time.time() <= start + self.wait_for:
      hex_string = None

      try:
        if type(self.link) == SubgRfspyLink:
          resp = self.link.get_packet(timeout=1)
          hex_string = hexify(resp['data']).upper()
        elif type(self.link) == MMCommanderLink:
          resp = self.link.read(timeout=1)
          hex_string = hexify(resp).upper()
      except CommsException as e:
        pass

      # EG:   A7 12 31 23 22 5D .. ..
      # POS:  01234567890123456789
      #   'A7' indicates comms with the pump
      if hex_string:
        if (hex_string[0:2] == 'A7'):
          if hex_string[15:16] == '5D' and self.ignore_wake:
            pass
          else:
            return(1)
        else:
          print('Picked up something other than pump comms - ignoring: %s' % hex_string)

    # No comms picked up
    return(0)
