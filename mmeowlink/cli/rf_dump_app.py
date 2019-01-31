from __future__ import print_function
from datetime import datetime

from .. hex_handling import hexify
from .. exceptions import CommsException
from mmeowlink.exceptions import CommsException,InvalidPacketReceived

from mmeowlink.vendors.mmcommander_link import MMCommanderLink
from mmeowlink.vendors.subg_rfspy_link import SubgRfspyLink

from base_mmeowlink_app import BaseMMeowlinkApp

class RfDumpApp(BaseMMeowlinkApp):
  """
  Dump Radio Transmissions
  """

  # Override the parser since we don't want the standard commands
  def customize_parser(self, parser):
    parser = super(self.__class__, self).configure_radio_params(parser)

    return parser

  def prelude(self, args):
    # When running mmtune, we don't want the code to try and send
    # prelude packets or auto-init the pump, since they duplicate what
    # we are about to do
    args.no_rf_prelude = True

    super(RfDumpApp, self).prelude(args)

  def main(self, args):
    while True:
      try:
        if isinstance(self.link, SubgRfspyLink):
          resp = self.link.get_packet(timeout=1)
          ts = datetime.now()
          print("%s (%d db) - %s" % (ts, resp['rssi'], hexify(resp['data']).upper()))
        elif isinstance(self.link, MMCommanderLink):
          resp = self.link.read(timeout=1)
          ts = datetime.now()
          print("%s (N/A db) - %s" % (ts, hexify(resp).upper()))
      except CommsException as e:
        pass
      except InvalidPacketReceived:
        ts = datetime.now()
        print("%s (N/A db) - Corrupt packet" % ts)
