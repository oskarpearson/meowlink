
import decocare
from decocare import session, lib, commands
from .. packets.rf import Packet
from .. exceptions import InvalidPacketReceived, CommsException

import logging
import time

from decocare import lib

io  = logging.getLogger(decocare.__name__).getChild(__name__)
log = io.getChild(__name__)

class Sender (object):
  STANDARD_RETRY_COUNT = 3
  RETRY_BACKOFF = 1

  sent_params = False
  def __init__ (self, link):
    self.link = link
    self.frames = [ ]
    self.ack_for_more_data = False
    self.received_ack = False

  def send_params (self):
    command = self.command
    params = self.command.params
    payload = bytearray([len(params)]) + bytearray(params)
    missing = [ ]
    missing = bytearray([0x00]) * (64 - len(params))
    payload = payload + missing
    pkt = Packet.fromCommand(command, payload=payload, serial=command.serial)
    pkt = pkt.update(payload)
    buf = pkt.assemble( )
    self.sent_params = True
    try:
      buf = self.link.write_and_read(buf)
      resp = Packet.fromBuffer(buf)
      self.respond(resp)
    except AttributeError:
      self.link.write(buf)

  def ack (self, listen=False):
    null = bytearray([0x00])
    pkt = Packet.fromCommand(self.command, payload=null, serial=self.command.serial)
    pkt = pkt._replace(payload=null, op=0x06)
    buf = pkt.assemble( )
    if listen:
      buf = self.link.write_and_read(buf, timeout=0.1)
      return Packet.fromBuffer(buf)
    else:
      self.link.write(buf)

  def unframe (self, resp):
    if self.command.bytesPerRecord * self.command.maxRecords > 64:
      self.ack_for_more_data = True
      num, payload = resp.payload[0], resp.payload[1:]
      self.frames.append((num, resp.payload))
    else:
      self.ack_for_more_data = False
      payload = resp.payload[1:]

    self.command.respond(payload)


  def done (self):
    needs_params = self.command.params and len(self.command.params) > 0 or False
    if needs_params and not self.sent_params:
      return False
    return self.command.done( )

  def respond (self, resp):
    if resp.valid and resp.serial == self.command.serial:
      if resp.op == 0x06 and self.sent_params:
        self.command.respond(bytearray(64))
      elif resp.op == self.command.code:
        self.unframe(resp)

  def wait_for_ack (self, timeout=.500):
    link = self.link

    while not self.done( ):
      buf = link.read( timeout=timeout )
      resp = Packet.fromBuffer(buf)
      if self.responds_to(resp):
        if resp.op == 0x06:
          return

  def responds_to (self, resp):
    return resp.valid and resp.serial == self.command.serial

  def wait_response (self):
    link = self.link
    buf = link.read( )
    resp = Packet.fromBuffer(buf)
    if self.responds_to(resp):
      return resp

  def prelude (self):
    link = self.link
    command = self.command
    log.debug("*** Sending prelude for command %d" % command.code)

    payload = bytearray([0])
    self.pkt = Packet.fromCommand(command, payload=payload, serial=command.serial)
    self.pkt = self.pkt.update(payload)
    buf = self.pkt.assemble( )
    try:
      buf = self.link.write_and_read(buf)
      resp = Packet.fromBuffer(buf)
      if self.responds_to(resp):
        if resp.op == 0x06:
          self.received_ack = True
        else:
          self.respond(resp)
    except AttributeError:
      self.link.write(buf)

  def upload (self):
    params = self.command.params
    log.debug("len(params)  == %d" % len(params))

    should_send = len(params) > 0
    if should_send:
      if not self.received_ack:
        self.wait_for_ack( )
      self.send_params( )

  def restart_command( self ):
    # This is a bit of a hack; would be nice if decocare explicitly supported a command reset
    self.command.data = bytearray()
    self.command.responded = False

  def __call__ (self, command):
    self.command = command

    for retry_count in range(self.STANDARD_RETRY_COUNT):
      try:
        self.prelude()
        self.upload()

        while not self.done( ):
          if self.ack_for_more_data:
            try:
              resp = self.ack(listen=True)
            except AttributeError:
              self.ack(listen=False)
              resp = self.wait_response( )
          else:
            resp = self.wait_response( )
          if resp:
            self.respond(resp)

        return command
      except InvalidPacketReceived as e:
        log.error("Invalid Packet Received - '%s' - retrying: %s of %s" % (e, retry_count+1, self.STANDARD_RETRY_COUNT))
        self.restart_command()
      except CommsException as e:
        log.error("Timed out or other comms error - %s - retrying: %s of %s" % (e, retry_count+1, self.STANDARD_RETRY_COUNT))
        self.restart_command()
      time.sleep(self.RETRY_BACKOFF * retry_count)

class Repeater (Sender):

  def __call__ (self, command, repetitions=None, ack_wait_seconds=None, retry_count=None):
    self.command = command

    pkt = Packet.fromCommand(self.command, serial=self.command.serial)
    buf = pkt.assemble( )
    log.debug('Sending repeated message %s' % (str(buf).encode('hex')))

    self.link.write(buf, repetitions=repetitions)

    # Sometimes the first packet received will be mangled by the simultaneous
    # transmission of a CGMS and the pump. We thus retry on invalid packets
    # being received. Note how ever that we do *not* retry on timeouts, since
    # our wait period is typically very long here, which would lead to long
    # waits with no activity. It's better to fail and retry externally
    for retry_count in range(retry_count):
      try:
        self.wait_for_ack(timeout=ack_wait_seconds)
        return True
      except InvalidPacketReceived:
        log.error("Invalid Packet Received - retrying: %s of %s" % (retry_count, self.STANDARD_RETRY_COUNT))

class Pump (session.Pump):
  STANDARD_RETRY_COUNT = 3
  STANDARD_RETRY_BACKOFF = 1

  def __init__ (self, link, serial):
    self.link = link
    self.serial = serial

  def power_control (self, minutes=None):
    """ Control Pumping """
    log.info('BEGIN POWER CONTROL %s' % self.serial)
    self.command = commands.PowerControl(**dict(minutes=minutes, serial=self.serial))
    repeater = Repeater(self.link)

    repeater(self.command, repetitions=500, ack_wait_seconds=15, retry_count=2)

  def execute (self, command):
    command.serial = self.serial

    for retry_count in range(self.STANDARD_RETRY_COUNT):
      try:
          sender = Sender(self.link)
          return sender(command)
      except (CommsException, AssertionError) as e:
          log.error("Timed out or other comms exception - %s - retrying: %s of %s" % (e, retry_count, self.STANDARD_RETRY_COUNT))
          time.sleep(self.RETRY_BACKOFF * retry_count)
