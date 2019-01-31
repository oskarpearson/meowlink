from __future__ import print_function
import json

from mmeowlink.mmtune import MMTune
from base_mmeowlink_app import BaseMMeowlinkApp

class MMTuneApp(BaseMMeowlinkApp):
  """
  Tune radio automatically
  """
  def customize_parser(self, parser):
    parser = super(self.__class__, self).configure_radio_params(parser)

    parser.add_argument('--radio_locale', choices=['US', 'WW'], default='US', help="US=916mhz, WW=868mhz. Only supported on subg_rfspy radios")

    return parser

  def prelude(self, args):
    # When running mmtune, we don't want the code to try and send
    # prelude packets or auto-init the pump, since they duplicate what
    # we are about to do
    args.no_rf_prelude = True

    super(MMTuneApp, self).prelude(args)

  def main(self, args):
    tuner = MMTune(self.link, args.serial, args.radio_locale)
    output = tuner.run()
    print(json.dumps(output, sort_keys=True,indent=4, separators=(',', ': ')))
