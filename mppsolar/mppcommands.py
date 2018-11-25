"""
MPP Solar Inverter Command Library
reference library of serial commands (and responses) for PIP-4048MS inverters
mppcommands.py
"""

import serial
import time
import re
import logging
import json
import glob
# from pprint import pprint
from os import path
from argparse import ArgumentParser

from .mppcommand import mppCommand

logger = logging.getLogger()


class MppSolarError(Exception):
    pass


class NoDeviceError(MppSolarError):
    pass


class NoTestResponseDefined(MppSolarError):
    pass


# Read in all the json files in the commands subdirectory
# this builds a list of all valid commands
COMMANDS = []
here = path.abspath(path.dirname(__file__))
files = glob.glob(here + '/commands/*.json')
for file in sorted(files):
    with open(file) as f:
        try:
            data = json.load(f)
        except Exception as e:
            print("Error processing JSON in {}".format(file))
            print(e)
        # print("Command: {} ({}) - expects {} response(s) [regex: {}]".format(data['name'], data['description'], len(data['response']), data['regex']))
        if data['regex']:
            regex = re.compile(data['regex'])
        else:
            regex = None
        COMMANDS.append(mppCommand(data['name'], data['description'], data['type'], data['response'], data['test_responses'], regex))


def trunc(text):
    """
    Truncates / right pads supplied text
    """
    if len(text) >= 30:
        text = text[:30]
        return '{:<30}...'.format(text)
    return '{:<30}   '.format(text)


def getKnownCommands():
    """
    Provides a human readable list of all defined commands
    """
    msgs = []
    msgs.append('-------- List of known commands --------')
    for cmd in COMMANDS:
        msgs.append('{}: {}'.format(cmd.name, cmd.description))
    return msgs


def getCommand(cmd):
    """
    Returns the mppcommand object of the supplied cmd string
    """
    logging.debug("Searching for cmd '{}'".format(cmd))
    for command in COMMANDS:
        if not command.regex:
            if cmd == command.name:
                return command
        else:
            match = command.regex.match(cmd)
            if match:
                logging.debug(command.name, command.regex)
                logging.debug("Matched: {} Value: {}".format(command.name, match.group(1)))
                command.set_value(match.group(1))
                return command
    return None


class mppCommands:
    """
    MPP Solar Inverter Command Library
    """

    def __init__(self, serial_device=None, baud_rate=2400):
        if (serial_device is None):
            raise NoDeviceError("A device to communicate by must be supplied, e.g. /dev/ttyUSB0")
        self._baud_rate = baud_rate
        self._serial_device = serial_device

    def getKnownCommands(self):
        """
        Return list of defined commands
        """
        return getKnownCommands()

    def doSerialCommand(self, command):
        """
        Opens serial connection, sends command (multiple times if needed)
        and returns the response
        """
        response_line = None
        logging.debug('port %s, baudrate %s', self._serial_device, self._baud_rate)
        if (self._serial_device == 'TEST'):
            # Return a valid response if _serial_device is TEST
            # - for those commands that have test responses defined
            # print "TEST"
            # print command.get_test_response()
            command.set_response(command.get_test_response())
            return command
        with serial.serial_for_url(self._serial_device, self._baud_rate) as s:
            # Execute command multiple times, increase timeouts each time
            for x in (1, 2, 3, 4):
                logging.debug('Command execution attempt %d...', x)
                s.timeout = 1 + x
                s.write_timeout = 1 + x
                s.flushInput()
                s.flushOutput()
                encoded_command = bytearray(ord(x) for x in command.full_command)
                s.write(encoded_command)
                time.sleep(0.5 * x)  # give serial port time to receive the data
                response_line = s.readline()
                logging.debug('serial response was: %s', response_line)
                decoded_response = ''.join(chr(x) for x in bytearray(response_line))
                if command.is_response_valid(decoded_response):
                    command.set_response(decoded_response)
                    # return response without the start byte and the crc
                    return command
            logging.critical('Command execution failed')
            return None

    def execute(self, cmd):
        """
        Sends a command (as supplied) to inverter and returns the raw response
        """
        command = getCommand(cmd)
        if command is None:
            logging.critical("Command not found")
            return None
        else:
            logging.debug("Command valid {}".format(command.name))
            logging.debug('called: execute with query %s', command)
            return self.doSerialCommand(command)


if __name__ == '__main__':
    parser = ArgumentParser(description='MPP Solar Command Utility')
    parser.add_argument('-c', '--command', help='Command to run', default='QID')
    args = parser.parse_args()

    logging.basicConfig(level='DEBUG')

    mp = mppCommands("TEST")
    cmd = mp.execute(args.command)
    print("response: ", cmd.response)
    # print len(cmd.response_definition)
    print("valid? ", cmd.valid_response)
    print("response_dict: ", cmd.response_dict)
    # for line in getKnownCommands():
    #    print line
