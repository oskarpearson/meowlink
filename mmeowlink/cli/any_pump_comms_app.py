import sys
import time

from mmeowlink.detect_radio_comms import DetectRadioComms

from base_mmeowlink_app import BaseMMeowlinkApp

class AnyPumpCommsApp(BaseMMeowlinkApp):
  """
  Waits for any pump communications, up to the timeout specified by wait_for
  """

  # Override the parser since we don't want the standard commands
  def customize_parser(self, parser):
    parser = super(self.__class__, self).configure_radio_params(parser)

    parser.add_argument('--wait-for', default=5, type=int, help="How long to wait for other comms")
    parser.add_argument('--ignore-wake', action='store_true', help="Ignore 'wake' commands")

    return parser

  def prelude(self, args):
    # When running mmtune, we don't want the code to try and send
    # prelude packets or auto-init the pump, since they duplicate what
    # we are about to do
    args.no_rf_prelude = True

    super(AnyPumpCommsApp, self).prelude(args)

  def main(self, args):
    self.detector = DetectRadioComms(link=self.link, wait_for=int(args.wait_for), ignore_wake=args.ignore_wake)
    self.app_result = self.detector.detect()
