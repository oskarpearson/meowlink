import logging
import serial

from .. import fuser

io  = logging.getLogger( )
log = io.getChild(__name__)

class NotImplementedException (Exception):
  pass

class AlreadyInUseException (Exception):
  pass

class SerialInterface (object):
  serial = None
  def open( self ):
    if not self.serial:
      log.info( '{agent} opening serial port'
        .format(agent=self.__class__.__name__ ))

      if fuser.in_use(self.device):
        raise AlreadyInUseException("%s already in use" % self.device)

      if self.device.find('spi') >= 0:
        import spi_serial
        self.serial = spi_serial.SpiSerial()
        self.check_setup()
      else:
        self.serial = serial.Serial( self.device, self.speed )
        self.clear_receive_buffer('New port open')
        self.check_setup()

    return True

  def close( self ):
    log.info( '{agent} stopped using serial port'
      .format(agent=self.__class__.__name__ ))

    self.clear_receive_buffer('Closing port')
    self.serial.close( )
    self.serial = None
    return True

  # Tries to clear out the receive buffer, reading any outstanding bytes
  def clear_receive_buffer(self, message):
    orig_timeout = self.serial.timeout
    self.serial.timeout = 0
    loops = 0
    log.debug("clear_receive_buffer - %s - waiting for input" % message)
    while True:
      resp = self.serial.read()
      if len(resp) == 0:
        self.serial.timeout = orig_timeout
        log.debug("clear_receive_buffer - %s - looped %s times" % (message, loops))
        return
      loops = loops + 1

  def check_link_ok(self):
    # Override this method with your own check, using a 'pass' clause if necessary
    raise NotImplementedException("check_link_ok should be implemented by child class")

  def readline( self ):
    raise NotImplementedException("readline currently not implemented")

  def readlines( self ):
    raise NotImplementedException("readlines currently not implemented")
