
# Based on decoding-carelink/decocare/link.py

import array
import logging
import time

import decocare
from decocare.lib import hexdump
from .. exceptions import InvalidPacketReceived, CommsException, MMCommanderNotWriteable

from serial_interface import SerialInterface

io  = logging.getLogger(decocare.__name__).getChild(__name__)
log = io.getChild(__name__)

class MMCommanderLink(SerialInterface):
  # How many repetitions can be sent by the underlying code in one go.
  # It seems that the mmcommander firmware can crash if this is too high
  MAX_REPETITION_BATCHSIZE = 100
  VERSION_FETCH_COMMAND = 0x00
  TIMEOUT = 1

  def __init__(self, device, radio_locale=None):
    self.timeout = 1
    self.device = device
    self.speed = 57600
    # radio_locale is not supported here

    SerialInterface.__init__(self)
    self.open()

  def check_setup(self):
    # Check it's a mmcommander device:
    # We should get a response from the firmware immediately, otherwise
    # it's possible the device we're trying to query is not a MMCommander
    # device
    self.serial.timeout = self.serial.write_timeout = 1

    self.serial.write(chr(self.VERSION_FETCH_COMMAND))
    version = self.serial.read(1)
    if len(version) == 0:
      raise CommsException("Could not get version from mmcommander device. Have you got the right port/device and radio_type?")

  def write( self, string, repetitions=1, timeout=None ):
    if timeout is None:
      timeout = self.TIMEOUT
    self.serial.write_timeout = timeout

    message = bytearray( string )
    message_length = len(message)

    # Format of transmission is as follows. Note that the content is
    # automatically converted to radio (FourBySix) format
    #
    # Command | Length of Message | Repetititons | Message ...
    #
    # Command is:
    #  0x1  Send - CRC already included
    #  0x81 Send - Add CRC-8 at the end
    #  0xC1 Send - Add CRC-16 at the end
    #
    # Repetitions must be <= 255 as it's a byte. So we loop according to the
    # maximum batch size
    remaining_messages = repetitions
    while remaining_messages > 0:
      if remaining_messages < self.MAX_REPETITION_BATCHSIZE:
        transmissions = remaining_messages
      else:
        transmissions = self.MAX_REPETITION_BATCHSIZE
      remaining_messages = remaining_messages - transmissions

      arr = array.array('B', bytearray([0x1, message_length, transmissions]) + message)

      r = self.serial.write( arr.tostring() )
      if r != len(arr):
        raise CommsException("Could not write to serial port - Tried to write %s bytes but only wrote %s" % (len(arr), r))

      io.info( 'usb.write.len: %s\n%s' % ( len( string ),
                                           hexdump( bytearray( string ) ) ) )

      # If the batch is large, the hardware can take a while to respond to us.
      # Based on testing, this seems about right:
      self.serial.timeout = timeout + (0.03 * transmissions)
      confirmation = self.serial.read(3)

      # If the MMCommander stick is not write-enabled, the firmware returns 0 as the message length
      # and transmission count
      if bytearray( confirmation ) == bytearray([ 0x01, 0x0, 0x0]):
        raise MMCommanderNotWriteable("Error sending radio comms. Your MMCommander stick may not have write-enabled firmware?")

      if repetitions > 1:
        if bytearray( confirmation ) != bytearray([ 0x01, message_length, transmissions]):
          io.warn("usb.write.confirmation: Could not get confirmation of transmission from mmcommander. Response was %d %d %d, not %d %d %d" % (
            ord(confirmation[0]), ord(confirmation[1]), ord(confirmation[2]),
            0x01, message_length, transmissions
          ))
          self.clear_receive_buffer('Unclear message confirmation')

    # This is a hack - which seems to occur because we occasionally don't get
    # the right number of packets above.

    return r

  def read( self, timeout=None ):
    if timeout is None:
      timeout = self.TIMEOUT
    self.serial.timeout = timeout

    # Result format:
    # State | Length | Message
    #
    # State is:
    #   - 2:  CRC ok
    #   - 4:  Repeated Message (we have this disabled)
    #   - 82: CRC not ok
    # Anything else is unknown, or part of a previous receive that we
    # didn't expect. We ignore those.
    #
    # We also ignore messages where the CRC doesn't match our expectation
    #
    while True:
      state = self.serial.read(1)
      if (state is None) or len(state) == 0:
        raise CommsException("No response from pump after timeout %s seconds" % timeout)

      if ord(state) == 2:
        body_len = self.serial.read(1)

        if (body_len is None) or (len(body_len) == 0):
          raise CommsException("Timeout reading length of response")

        # This is raised as a concern in the mmcommander code, so I
        # currently treat this as an error case
        if ord(body_len) > 74:
          raise InvalidPacketReceived("Warning - received message > 74 chars")

        message = self.serial.read(ord(body_len))
        if (message is None) or (len(message) == 0):
          raise CommsException("Timeout reading message body")

        return bytearray( message )
      else:
        io.info( 'usb.read error: state message received. Ignoring value %i' % ord(state) )
