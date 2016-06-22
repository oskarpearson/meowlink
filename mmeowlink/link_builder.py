from mmeowlink.exceptions import UnknownLinkType

from mmeowlink.vendors.mmcommander_link import MMCommanderLink
from mmeowlink.vendors.spi_link import SPILink
from mmeowlink.vendors.subg_rfspy_link import SubgRfspyLink
import glob

class LinkBuilder():
  def scan (self):
    candidate = '/dev/serial/by-id/usb-*subg_rfspy*'
    results = glob.glob(candidate)
    return (results[0:1] or ['']).pop( )
  def build(self, radio_type, port):
    if radio_type == 'mmcommander':
      return MMCommanderLink(port)
    elif radio_type == 'spi':
      return SPILink()
    elif radio_type == 'subg_rfspy':
      return SubgRfspyLink(port)
    else:
      raise UnknownLinkType("Unknown radio type '%s' - check parameters" % radio_type)
