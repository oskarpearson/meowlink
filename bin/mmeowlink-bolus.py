#!/usr/bin/env python
# PYTHON_ARGCOMPLETE_OK

from decocare import commands
from decocare import lib
from decocare.helpers.cli import CommandApp

from mmeowlink.link_builder import LinkBuilder
from mmeowlink.handlers.stick import Pump


class BolusApp (CommandApp):
  """ %(prog)s - Send bolus command to a pump.

  XXX: Be careful please!

  Units might be wrong.  Keep disconnected from pump until you trust it by
  observing the right amount first.
  """
  def customize_parser (self, parser):
    parser.add_argument('units',
                         type=float,
                         help="Amount of insulin to bolus."
                       )

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--515',
                        dest='strokes_per_unit',
                        action='store_const',
                        const=10
                      )
    group.add_argument('--554',
                        dest='strokes_per_unit',
                        action='store_const',
                        const=40
                      )
    group.add_argument('--strokes',
                        dest='strokes_per_unit',
                        type=int
                      )

    parser.add_argument('--radio_type', dest='radio_type', default='subg_rfspy', choices=['mmcommander', 'subg_rfspy'])
    parser.add_argument('--mmcommander', dest='radio_type', action='store_const', const='mmcommander')
    parser.add_argument('--subg_rfspy', dest='radio_type', action='store_const', const='subg_rfspy')
    # parser = super(BolusApp, self).customize_parser(parser)

    return parser

  def prelude(self, args):
      port = args.port
      builder = LinkBuilder()
      if port == 'scan':
          port = builder.scan()
      self.link = link = LinkBuilder().build(args.radio_type, port)
      link.open()
      self.pump = Pump(self.link, args.serial)
      self.model = None
      if args.no_rf_prelude:
          return
      if not args.autoinit:
          if args.init:
              self.pump.power_control(minutes=args.session_life)
      else:
          self.autoinit(args)
      self.sniff_model()

  def postlude(self, args):
      # self.link.close( )
      return

  def main (self, args):
    print args
    self.bolus(args);

  def bolus (self, args):
    query = commands.Bolus
    kwds = dict(params=fmt_params(args))

    resp = self.exec_request(self.pump, query, args=kwds,
                 dryrun=args.dryrun, render_hexdump=False)
    return resp

def fmt_params (args):
  strokes = int(float(args.units) * args.strokes_per_unit)
  if (args.strokes_per_unit > 10):
    return [lib.HighByte(strokes), lib.LowByte(strokes)]
  return [strokes]

if __name__ == '__main__':
  app = BolusApp( )
  app.run(None)
