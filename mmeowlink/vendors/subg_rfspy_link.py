
# Based on decoding-carelink/decocare/link.py

import array
import binascii
import logging
import time

from decocare.lib import hexdump, CRC8

from .. fourbysix import FourBySix
from .. exceptions import InvalidPacketReceived, CommsException, SubgRfspyVersionNotSupported

from serial_interface import SerialInterface
from serial_rf_spy import SerialRfSpy

io  = logging.getLogger( )
log = io.getChild(__name__)

class SubgRfspyLink(SerialInterface):
  REPETITION_DELAY = 0
  MAX_REPETITION_BATCHSIZE = 250
  FREQ_XTAL = 24000000

  REG_FREQ2 = 0x09
  REG_FREQ1 = 0x0A
  REG_FREQ0 = 0x0B
  REG_MDMCFG4 = 0x0C
  REG_MDMCFG3 = 0x0D
  REG_MDMCFG2 = 0x0E
  REG_MDMCFG1 = 0x0F
  REG_MDMCFG0 = 0x10
  REG_AGCCTRL2 = 0x17
  REG_AGCCTRL1 = 0x18
  REG_AGCCTRL0 = 0x19
  REG_FREND1 = 0x1A
  REG_FREND0 = 0x1B

  # Which version of subg_rfspy do we support?
  UINT16_TIMEOUT_VERSIONS = ["0.6"]
  SUPPORTED_VERSIONS = ["0.6", "0.7", "0.8", "0.9", "1.0"]

  RFSPY_ERRORS = {
    0xaa: "Timeout",
    0xbb: "Command Interrupted",
    0xcc: "Zero Data"
  }

  def __init__(self, device):
    self.timeout = 1
    self.device = device
    self.speed = 19200
    self.channel = 0

    self.open()

  def update_register(self, reg, value, timeout=1):
    args = chr(reg) + chr(value)
    self.serial_rf_spy.do_command(self.serial_rf_spy.CMD_UPDATE_REGISTER, args, timeout=timeout)

  def set_base_freq(self, freq_mhz):
    val = ((freq_mhz * 1000000)/(self.FREQ_XTAL/float(2**16)))
    val = long(val)
    self.update_register(self.REG_FREQ0, val & 0xff)
    self.update_register(self.REG_FREQ1, (val >> 8) & 0xff)
    self.update_register(self.REG_FREQ2, (val >> 16) & 0xff)

  def check_setup(self):
    self.serial_rf_spy = SerialRfSpy(self.serial)
#    if self.device.find('spi') >= 0:
#        self.serial_rf_spy.do_command(SerialRfSpy.CMD_RESET, param="", timeout=1)
    self.serial_rf_spy.sync()

    # Check it's a SerialRfSpy device by retrieving the firmware version
    self.serial_rf_spy.send_command(self.serial_rf_spy.CMD_GET_VERSION, timeout=1)
    version = self.serial_rf_spy.get_response(timeout=1).split(' ')[1]

    log.debug( 'serial_rf_spy Firmware version: %s' % version)

    self.uint16_timeout_width = version in self.UINT16_TIMEOUT_VERSIONS

    if version not in self.SUPPORTED_VERSIONS:
      raise SubgRfspyVersionNotSupported("Your subg_rfspy version (%s) is not in the supported version list: %s" % (version, "".join(self.SUPPORTED_VERSIONS)))

  def write_and_read( self, string, repetitions=1, repetition_delay=0, timeout=None ):
    rf_spy = self.serial_rf_spy

    if timeout == None:
      timeout = 0.5

    timeout_ms = int(timeout * 1000)


    log.debug("write_and_read: %s" % str(string).encode('hex'))

    if repetitions > self.MAX_REPETITION_BATCHSIZE:
      raise CommsException("repetition count of %d is greater than max repitition count of %d" % (repetitions, self.MAX_REPETITION_BATCHSIZE))

    crc = CRC8.compute(string)

    listen_channel = self.channel

    cmd_body = chr(self.channel) + chr(repetitions - 1) + chr(repetition_delay) + chr(listen_channel)

    if self.uint16_timeout_width:
      timeout_ms_high = int(timeout_ms / 256)
      timeout_ms_low = int(timeout_ms - (timeout_ms_high * 256))
      cmd_body += chr(timeout_ms_high) + chr(timeout_ms_low)
    else:
      cmd_body += chr(timeout_ms >> 24) + chr((timeout_ms >> 16) & 0xff) + \
        chr((timeout_ms >> 8) & 0xff) + chr(timeout_ms & 0xff)

    retry_count = 0
    cmd_body += chr(retry_count)

    cmd_body += FourBySix.encode(string)

    resp = rf_spy.do_command(rf_spy.CMD_SEND_AND_LISTEN, cmd_body, timeout=(timeout_ms/1000.0 + 1))
    return self.handle_response(resp)['data']

  def write( self, string, repetitions=1, repetition_delay=0, timeout=None ):
    rf_spy = self.serial_rf_spy

    if timeout is None:
      timeout = self.timeout

    remaining_messages = repetitions
    while remaining_messages > 0:
      if remaining_messages < self.MAX_REPETITION_BATCHSIZE:
        transmissions = remaining_messages
      else:
        transmissions = self.MAX_REPETITION_BATCHSIZE
      remaining_messages = remaining_messages - transmissions

      crc = CRC8.compute(string)

      message = chr(self.channel) + chr(transmissions - 1) + chr(repetition_delay) + FourBySix.encode(string)

      rf_spy.do_command(rf_spy.CMD_SEND_PACKET, message, timeout=timeout)

  def handle_response( self, resp ):
    if not resp:
      raise CommsException("Did not get a response, or response is too short: %s" % len(resp))

    # In some cases the radio will respond with 'OK', which is an ack that the radio is responding,
    # we treat this as a retryable Comms error so that the caller can deal with it
    if len(resp) == 2 and resp == "OK":
      raise CommsException("Received null/OK response")

    # If the length is less than or equal to 2, then it means we've received an error
    if len(resp) <= 2:
      raise CommsException("Received an error response %s" % self.RFSPY_ERRORS[ resp[0] ])

    decoded = FourBySix.decode(resp[2:])

    rssi_dec = resp[0]
    rssi_offset = 73
    if rssi_dec >= 128:
      rssi = (( rssi_dec - 256) / 2) - rssi_offset
    else:
      rssi = (rssi_dec / 2) - rssi_offset

    sequence = resp[1]

    return {'rssi':rssi, 'sequence':sequence, 'data':decoded}

  def get_packet( self, timeout=None ):
    rf_spy = self.serial_rf_spy

    if timeout is None:
      timeout = self.timeout

    timeout_ms = int(timeout * 1000)

    cmd_body = chr(self.channel)
    if self.uint16_timeout_width:
      timeout_ms_high = int(timeout_ms / 256)
      timeout_ms_low = int(timeout_ms - (timeout_ms_high * 256))
      cmd_body += chr(timeout_ms_high) + chr(timeout_ms_low)
    else:
      cmd_body += chr(timeout_ms >> 24) + chr((timeout_ms >> 16) & 0xff) + \
        chr((timeout_ms >> 8) & 0xff) + chr(timeout_ms & 0xff)

    resp = rf_spy.do_command(SerialRfSpy.CMD_GET_PACKET, cmd_body, timeout=timeout + 1)
    return self.handle_response(resp)

  def read( self, timeout=None ):
    if timeout is None:
      timeout = self.timeout

    return self.get_packet(timeout)['data']
