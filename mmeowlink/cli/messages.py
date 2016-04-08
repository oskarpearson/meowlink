"""
module to send arbitrary pump messages.
"""

# PYTHON_ARGCOMPLETE_OK
from decocare.helpers import messages
from mmeowlink.handlers.stick import Pump
from mmeowlink.link_builder import LinkBuilder
import argcomplete


class SendMsgApp(messages.SendMsgApp):
    """
    mmeowlink adapter to decocare's SendMsgApp
    """

    def customize_parser(self, parser):
        parser.add_argument('--radio_type', dest='radio_type', default='subg_rfspy',
                            choices=['mmcommander', 'subg_rfspy'])
        parser.add_argument('--mmcommander', dest='radio_type', action='store_const', const='mmcommander')
        parser.add_argument('--subg_rfspy', dest='radio_type', action='store_const', const='subg_rfspy')
        parser = super(SendMsgApp, self).customize_parser(parser)
        return parser

    def prelude(self, args):
        port = args.port
        builder = LinkBuilder()
        if port == 'scan':
            port = builder.scan()
        self.link = link = LinkBuilder().build(args.radio_type, port)
        link.open()
        # get link
        # drain rx buffer
        self.pump = Pump(self.link, args.serial)
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
