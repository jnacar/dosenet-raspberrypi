# -*- coding: utf-8 -*-
from __future__ import print_function

try:
    import RPi.GPIO as GPIO
    RPI = True
except ImportError:
    print('Not on a Raspberry Pi, proceeding anyway')
    RPI = False

import datetime
import multiprocessing
import csv
from time import sleep
import os

import cust_crypt


def datetime_from_epoch(timestamp):
    """
    Return a datetime object equivalent to the number of seconds since
    Unix epoch (Jan 1, 1970).

    The datetime object is in UTC.
    """

    datetime_value = (datetime.datetime(year=1970, month=1, day=1) +
                      datetime.timedelta(seconds=timestamp))
    return datetime_value


def set_verbosity(class_instance, verbosity=None):
    """
    Define the verbosity level for any class instance,
    by generating a custom print method, 'vprint', for the instance.

    The vprint method can take arguments exactly like the print function,
    except that first there is a required argument, v, which is the minimum
    verbosity for the printing to happen.

    If verbosity is not given, get it from class_instance.v.

    Usage example:
      def __init__(self, verbosity=1):
          set_verbosity(self, verbosity=verbosity)
      ...
      self.vprint(2, 'This only prints if verbosity >= 2')
    """

    if verbosity is None:
        verbosity = class_instance.v

    def vprint(level, *args, **kwargs):
        """
        The conditional print function, to be returned.
        """

        if verbosity >= level:
            print(*args, **kwargs)

    class_instance.vprint = vprint


class LED(object):
    """
    Represents one LED, available for blinking or steady operation.

    Methods/usage:

    myLED = LED(broadcom_pin_number)
    myLED.on()
    myLED.off()
    myLED.flash()   # single flash, like for a count
    myLED.start_blink(interval=1)   # set the LED blinking in a subprocess
                                    # interval is the period of blink
    myLED.stop_blink()
    """

    def __init__(self, pin):
        """
        Initialize a pin for operating an LED. pin is the Broadcom GPIO #
        """

        if RPI:
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(pin, GPIO.OUT)
            self.pin = pin
            self.blinker = None
        else:
            raise EnvironmentError('Must be a Raspberry Pi to have an LED')

    def on(self):
        """Turn on the LED"""
        GPIO.output(self.pin, True)

    def off(self):
        """Turn off the LED"""
        try:
            GPIO.output(self.pin, False)
        except RuntimeError:
            # if GPIO is cleaned up too early
            pass

    def flash(self):
        """Flash the LED once"""
        self.on()
        sleep(0.005)
        self.off()

    def start_blink(self, interval=1):
        """
        Set the LED in a blinking state using a subprocess.

        interval is the period of the blink, in seconds.
        """

        if self.blinker:
            self.blinker.terminate()
            # this is maybe not necessary, but seems safer
        self.blinker = multiprocessing.Process(
            target=self._do_blink, kwargs={'interval': interval})
        self.blinker.start()

    def stop_blink(self):
        """Switch off the blinking state of the LED"""
        if self.blinker:
            self.blinker.terminate()
        self.off()

    def _do_blink(self, interval=1):
        """
        Run this method as a subprocess only!

        It blinks forever (until terminated).
        """

        while True:
            self.on()
            sleep(interval / 2.0)
            self.off()
            sleep(interval / 2.0)


class NetworkStatus(object):
    """
    Keep track of network status.

    Inputs:
      hostname='dosenet.dhcp.lbl.gov'
        hostname to ping
      up_interval_s=300
        this is the interval between pings, if the network was up
      down_interval_s=5
        this is the interval between pings, if the network was down
      network_led=None
        an instance of LED class
      verbosity=1
        verbosity 0: nothing printed
        verbosity 1: only network down printed
        verbosity 2: always printed

    Output:
      use the __bool__() function
      e.g.:
      ns = NetworkStatus()
      if ns:
          # network is up
    """

    def __init__(self,
                 hostname='dosenet.dhcp.lbl.gov',
                 up_interval_s=300,
                 down_interval_s=5,
                 network_led=None,
                 verbosity=1):
        self.hostname = hostname
        self.up_interval_s = up_interval_s
        self.down_interval_s = down_interval_s
        self.led = network_led
        self.blink_period_s = 1.5

        self.v = verbosity
        set_verbosity(self)

        self.is_up = False

        self._p = multiprocessing.Process(target=self._do_pings)
        self._p.start()

    def update(self):
        """Update network status"""

        response = self._ping()
        if response == 0:
            self.is_up = True
            if self.led:
                if self.led.blinker:
                    self.led.stop_blink()
                self.led.on()
            self.vprint(2, '  {} is UP'.format(self.hostname))
        else:
            self.is_up = False
            if self.led:
                self.led.start_blink(interval=self.blink_period_s)
            self.vprint(1, '  {} is DOWN!'.format(self.hostname))

    def _do_pings(self):
        """Runs forever - only call as a subprocess"""
        while True:
            self.update()
            if self:
                sleep(self.up_interval_s)
            else:
                sleep(self.down_interval_s)

    def _ping(self):
        """one ping"""
        return os.system('ping -c 1 {} > /dev/null'.format(self.hostname))

    def __bool__(self):
        return self.is_up

    # python2 uses __nonzero__ for __bool__
    __nonzero__ = __bool__

    def cleanup(self):
        GPIO.cleanup()


class Config(object):
    """
    Represents the CSV configuration file.
    """

    def __init__(self, filename, verbosity=1):
        set_verbosity(self, verbosity=verbosity)
        try:
            with open(filename, 'rb') as config_file:
                config_reader = csv.DictReader(config_file)
                content = config_reader.next()
        except IOError:
            self.vprint(1, 'IOError loading config file.',
                        'Check filename, path, permissions?')
            return None

        self.ID = content['stationID']
        self.hash = content['message_hash']
        self.lat = content['lat']
        self.long = content['long']


class PublicKey(object):
    """
    Represents the public key file.
    """

    def __init__(self, filename, verbosity=1):
        set_verbosity(self, verbosity=verbosity)
        try:
            self.encrypter = cust_crypt.PublicDEncrypt(
                key_file_lst=[filename])
        except IOError:
            self.vprint(1, 'IOError loading public key file.',
                        'Check filename, path, permissions?')
            return None
