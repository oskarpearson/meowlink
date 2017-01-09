from bluepy.btle import UUID, Peripheral, ADDR_TYPE_PUBLIC, DefaultDelegate
import time
import struct
from serial_rf_spy import SerialRfSpy
from subg_rfspy_link import SubgRfspyLink
from decocare.lib import hexdump, CRC8
from .. fourbysix import FourBySix
from .. exceptions import InvalidPacketReceived, CommsException, SubgRfspyVersionNotSupported
import logging

io  = logging.getLogger( )
log = io.getChild(__name__)

class RileyLink(DefaultDelegate, object):
    SERVICE_UUID        = "0235733b-99c5-4197-b856-69219c2a3845"
    DATA_UUID           = "c842e849-5028-42e2-867c-016adada9155"
    RESPONSE_COUNT_UUID = "6e6c7910-b89e-43a5-a0fe-50c5e2b81f4a"
    CUSTOM_NAME_UUID    = "d93b2af0-1e28-11e4-8c21-0800200c9a66"
    TIMER_TICK_UUID     = "6e6c7910-b89e-43a5-78af-50c5e2b86f7e"

    def __init__(self, port):
        DefaultDelegate.__init__(self)
        self.port = port
        self.timeout = 1
        self.channel = 0
        self.ready_to_read = False
        self.p = None
        self.open()

    def handleNotification(self, cHandle, data):
        if cHandle == self.response_count_handle:
            self.ready_to_read = True
        else:
            print "unexpected notification on: %s" % cHandle
    
    def open(self):
        if self.p != None:
            return

        name_uuid = UUID(0x2a00)
 
        self.p = Peripheral(self.port, ADDR_TYPE_PUBLIC)
        self.p.setDelegate(self)
  
        svc = self.p.getServiceByUUID(RileyLink.SERVICE_UUID)

        characteristics = svc.getCharacteristics()

        for ch in characteristics:
            if ch.uuid == UUID(RileyLink.DATA_UUID):
                self.data_ch = ch
            elif ch.uuid == UUID(RileyLink.RESPONSE_COUNT_UUID):
                self.response_count_characteristic = ch
                self.response_count_handle = ch.getHandle()
                # Enable notification.  This seems really poor.  We should be able to 
                # enumerate descriptors on characteristics to get the CCCD.  Instead
                # We just assume that the next handle is the right one.
                self.p.writeCharacteristic(ch.getHandle()+1, str(bytearray([1,0])), True)
            elif ch.uuid == UUID(RileyLink.CUSTOM_NAME_UUID):
                self.custom_name_characteristic = ch
            elif ch.uuid == UUID(RileyLink.TIMER_TICK_UUID):
                self.timer_tick_characteristic = ch

        #ch = self.p.getCharacteristics(uuid=name_uuid)[0]
        #if (ch.supportsRead()):
        #    print "RileyLink name = \"%s\"" % ch.read()
        version = self.sync().split(' ')[1]
        log.debug( 'RileyLink Firmware version: %s' % version)

        self.uint16_timeout_width = version in SubgRfspyLink.UINT16_TIMEOUT_VERSIONS

        if version not in SubgRfspyLink.SUPPORTED_VERSIONS:
            raise SubgRfspyVersionNotSupported("Your subg_rfspy version (%s) is not in the supported version list: %s" % (str(version).encode('hex'), ", ".join(SubgRfspyLink.SUPPORTED_VERSIONS)))

    def close(self):
        self.p.disconnect()


    def update_register(self, reg, value, timeout=1):
        args = chr(reg) + chr(value)
        self.do_command(SerialRfSpy.CMD_UPDATE_REGISTER, args, timeout=timeout)

    def set_base_freq(self, freq_mhz):
        val = ((freq_mhz * 1000000)/(SubgRfspyLink.FREQ_XTAL/float(2**16)))
        val = long(val)
        self.update_register(SubgRfspyLink.REG_FREQ0, val & 0xff)
        self.update_register(SubgRfspyLink.REG_FREQ1, (val >> 8) & 0xff)
        self.update_register(SubgRfspyLink.REG_FREQ2, (val >> 16) & 0xff)

    def write(self, string, repetitions=1, repetition_delay=0, timeout=None ):
        if timeout is None:
            timeout = self.timeout

        remaining_messages = repetitions
        while remaining_messages > 0:
            if remaining_messages < SubgRfspyLink.MAX_REPETITION_BATCHSIZE:
                transmissions = remaining_messages
            else:
                transmissions = SubgRfspyLink.MAX_REPETITION_BATCHSIZE
            remaining_messages = remaining_messages - transmissions

            crc = CRC8.compute(string)

            message = chr(self.channel) + chr(transmissions - 1) + chr(repetition_delay) + FourBySix.encode(string)

            min_wait = transmissions * (0.05 + (repetition_delay/1000.0)) + 1
            if timeout < min_wait:
                timeout = min_wait

            self.do_command(SerialRfSpy.CMD_SEND_PACKET, message, timeout=timeout)


    def write_and_read( self, string, repetitions=1, repetition_delay=0, timeout=None ):

        if timeout == None:
            timeout = 0.5

        timeout_ms = int(timeout * 1000)

        log.debug("write_and_read: %s" % str(string).encode('hex'))

        if repetitions > SubgRfspyLink.MAX_REPETITION_BATCHSIZE:
            repetitions = SubgRfspyLink.MAX_REPETITION_BATCHSIZE
            #raise CommsException("repetition count of %d is greater than max repitition count of %d" % (repetitions, self.MAX_REPETITION_BATCHSIZE))

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

        resp = self.do_command(SerialRfSpy.CMD_SEND_AND_LISTEN, cmd_body, timeout=(timeout_ms/1000.0 + 1))
        return self.handle_response(resp)['data']

    def do_command(self, command, param="", timeout=0):
        self.send_command(command, param, timeout=timeout)
        return self.get_response(timeout=timeout)

    def read( self, timeout=None ):
        if timeout is None:
            timeout = self.timeout

        return self.get_packet(timeout)['data']

    def get_response(self, timeout=2.0):
        log.debug("get_response: timeout = %s" % str(timeout))

        if timeout is None or timeout <= 0:
            # We don't want infinite hangs for things, as it'll lock up processing
            raise CommsException("Timeout cannot be None, zero, or negative - coding error")

        start_time = time.time()

        resp = bytearray()

        while 1:
            elapsed = time.time() - start_time
            if elapsed < timeout:
                self.p.waitForNotifications(timeout - elapsed)
            else:
                log.debug("gave up waiting for response from subg_rfspy")
                return bytearray()

            new_data = self.data_ch.read()
            if new_data is not None and len(new_data) > 0:
                resp.extend(new_data)
                if resp[-1] == 0:
                    return resp[0:-1]

    def handle_response( self, resp ):
       if not resp:
           raise CommsException("Did not get a response, or response is too short: %s" % len(resp))

       # In some cases the radio will respond with 'OK', which is an ack that the radio is responding,
       # we treat this as a retryable Comms error so that the caller can deal with it
       if len(resp) == 2 and resp == "OK":
           raise CommsException("Received null/OK response")

       # If the length is less than or equal to 2, then it means we've received an error
       if len(resp) <= 2:
           raise CommsException("Received an error response %s" % SubgRfspyLink.RFSPY_ERRORS[ resp[0] ])

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

        resp = self.do_command(SerialRfSpy.CMD_GET_PACKET, cmd_body, timeout=timeout + 1)
        return self.handle_response(resp)

    def send_command(self, command, param="", timeout=1):
        full = chr(command)
        log.debug("command %d" % command)
        if len(param) > 0:
           log.debug("params: %s" % str(param).encode('hex'))
           full += param

        self.data_ch.write(chr(len(full)) + full, True) 


    def sync(self):
        self.send_command(SerialRfSpy.CMD_GET_STATE)
        status = self.get_response(timeout=1)
        if status == "OK":
            print "subg_rfspy status: " + status

        self.send_command(SerialRfSpy.CMD_GET_VERSION)
        version = self.get_response(timeout=1)
        if len(version) >= 3:
            print "Version: " + version

        if not status or not version:
           raise CommsException("Could not get subg_rfspy state or version. Have you got the right port/device and radio_type?")

        return version


