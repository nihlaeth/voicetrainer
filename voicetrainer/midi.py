# -*- coding: utf-8 -*-
# pylint: disable=too-many-lines,too-complex,too-many-branches
# pylint: disable=too-many-statements,arguments-differ
# needs refactoring, but I don't have the energy for anything
# more than a superficial cleanup.
#-------------------------------------------------------------------------------
# Name:         midi/__init__.py
# Purpose:      Access to MIDI library / music21 classes for dealing with midi data
#
# Authors:      Christopher Ariza
#               Michael Scott Cuthbert
#               (Will Ware -- see docs)
#
# Copyright:    Copyright © 2011-2013 Michael Scott Cuthbert and the music21 Project
#               Some parts of this module are in the Public Domain, see details.
# License:      LGPL or BSD, see license.txt
#-------------------------------------------------------------------------------
'''
Objects and tools for processing MIDI data.  Converts from MIDI files to
:class:`~MidiEvent`, :class:`~MidiTrack`, and
:class:`~MidiFile` objects, and vice-versa.
This module uses routines from Will Ware's public domain midi.py library from 2001
see http://groups.google.com/group/alt.sources/msg/0c5fc523e050c35e
'''
import struct
import sys
import unicodedata # @UnresolvedImport

# good midi reference:
# http://www.sonicspot.com/guide/midifiles.html

def is_num(usr_data):
    '''
    check if usr_data is a number (float, int, long, Decimal),
    return boolean

    unlike `isinstance(usr_data, Number)` does not return True for `True, False`.

    Does not use `isinstance(usr_data, Number)` which is 6 times slower
    than calling this function (except in the case of Fraction, when
    it's 6 times faster, but that's rarer)

    Runs by adding 0 to the "number" -- so anything that implements
    add to a scalar works

    >>> is_num(3.0)
    True
    >>> is_num(3)
    True
    >>> is_num('three')
    False
    >>> is_num([2, 3, 4])
    False

    True and False are NOT numbers:

    >>> is_num(True)
    False
    >>> is_num(False)
    False
    >>> is_num(None)
    False

    :rtype: bool
    '''
    try:
        dummy = usr_data + 0
        # pylint: disable=simplifiable-if-statement
        if usr_data is not True and usr_data is not False:
            return True
        else:
            return False
    except Exception: # pylint: disable=broad-except
        return False

# pylint: disable=missing-docstring
#-------------------------------------------------------------------------------
class EnumerationException(Exception):
    pass

class MidiException(Exception):
    pass

#-------------------------------------------------------------------------------

def char_to_binary(char):
    '''
    Convert a char into its binary representation. Useful for debugging.

    >>> char_to_binary('a')
    '01100001'
    '''
    ascii_value = ord(char)
    binary_digits = []
    while ascii_value > 0:
        if (ascii_value & 1) == 1:
            binary_digits.append("1")
        else:
            binary_digits.append("0")
        ascii_value = ascii_value >> 1

    binary_digits.reverse()
    binary = ''.join(binary_digits)
    zerofix = (8 - len(binary)) * '0'
    return zerofix + binary


def ints_to_hex_string(int_list):
    '''
    Convert a list of integers into a hex string, suitable for testing MIDI encoding.


    >>> # note on, middle c, 120 velocity
    >>> ints_to_hex_string([144, 60, 120])
    b'\\x90<x'
    '''
    # note off are 128 to 143
    # note on messages are decimal 144 to 159
    post = b''
    for i in int_list:
        # B is an unsigned char
        # this forces values between 0 and 255
        # the same as chr(int)
        post += struct.pack(">B", i)
    return post

def get_number(midi_str, length):
    '''
    Return the value of a string byte or bytes if length > 1
    from an 8-bit string or (PY3) bytes object

    Then, return the remaining string or bytes object
    The `length` is the number of chars to read.
    This will sum a length greater than 1 if desired.
    Note that MIDI uses big-endian for everything.
    This is the inverse of Python's chr() function.

    >>> get_number('test', 0)
    (0, 'test')
    >>> get_number('test', 2)
    (29797, 'st')
    >>> get_number('test', 4)
    (1952805748, '')
    '''
    summation = 0
    if not is_num(midi_str):
        for i in range(length):
            midi_str_or_num = midi_str[i]
            if is_num(midi_str_or_num):
                summation = (summation << 8) + midi_str_or_num
            else:
                summation = (summation << 8) + ord(midi_str_or_num)
        return summation, midi_str[length:]
    else:
        mid_num = midi_str
        summation = mid_num - ((mid_num >> (8*length)) << (8*length))
        big_bytes = mid_num - summation
        return summation, big_bytes

def get_variable_length_number(midi_str):
    r'''
    Given a string of data, strip off a the first character, or all high-byte characters
    terminating with one whose ord() function is < 0x80.  Thus a variable number of bytes
    might be read.

    After finding the appropriate termination,
    return the remaining string.
    This is necessary as DeltaTime times are given with variable size,
    and thus may be if different numbers of characters are used.
    (The ellipses below are just to make the doctests work on both Python 2 and
    Python 3 (where the output is in bytes).)

    >>> get_variable_length_number('A-u')
    (65, ...'-u')
    >>> get_variable_length_number('-u')
    (45, ...'u')
    >>> get_variable_length_number('u')
    (117, ...'')
    >>> get_variable_length_number('test')
    (116, ...'est')
    >>> get_variable_length_number('E@-E')
    (69, ...'@-E')
    >>> get_variable_length_number('@-E')
    (64, ...'-E')
    >>> get_variable_length_number('-E')
    (45, ...'E')
    >>> get_variable_length_number('E')
    (69, ...'')

    Test that variable length characters work:
    >>> get_variable_length_number(b'\xff\x7f')
    (16383, ...'')
    >>> get_variable_length_number('中xy')
    (210638584, ...'y')

    If no low-byte character is encoded, raises an IndexError
    >>> get_variable_length_number('中国')
    Traceback (most recent call last):
    MidiException: did not find the end of the number!
    '''
    # from http://faydoc.tripod.com/formats/mid.htm
    # This allows the number to be read one byte at a time, and when you see
    # a msb of 0, you know that it was the last (least significant) byte of the number.
    summation = 0
    if isinstance(midi_str, str):
        midi_str = midi_str.encode('utf-8')

    for i, byte in enumerate(midi_str):
        if not is_num(byte):
            byte = ord(byte)
        summation = (summation << 7) + (byte & 0x7F)
        if not byte & 0x80:
            try:
                return summation, midi_str[i+1:]
            except IndexError:
                break
    raise MidiException('did not find the end of the number!')

def get_numbers_as_list(midi_str):
    '''
    Translate each char into a number, return in a list.
    Used for reading data messages where each byte encodes
    a different discrete value.

    >>> get_numbers_as_list('\\x00\\x00\\x00\\x03')
    [0, 0, 0, 3]
    '''
    post = []
    for item in midi_str:
        if is_num(item):
            post.append(item)
        else:
            post.append(ord(item))
    return post

def put_number(num, length):
    '''
    Put a single number as a hex number at the end of a string `length` bytes long.

    >>> put_number(3, 4)
    b'\\x00\\x00\\x00\\x03'
    >>> put_number(0, 1)
    b'\\x00'
    '''
    lst = bytearray()

    for i in range(length):
        shift_bits = 8 * (length - 1 - i)
        this_num = (num >> shift_bits) & 0xFF
        lst.append(this_num)
    return bytes(lst)

def put_variable_length_number(num):
    '''
    >>> put_variable_length_number(4)
    b'\\x04'
    >>> put_variable_length_number(127)
    b'\\x7f'
    >>> put_variable_length_number(0)
    b'\\x00'
    >>> put_variable_length_number(1024)
    b'\\x88\\x00'
    >>> put_variable_length_number(8192)
    b'\\xc0\\x00'
    >>> put_variable_length_number(16383)
    b'\\xff\\x7f'
    >>> put_variable_length_number(-1)
    Traceback (most recent call last):
    MidiException: cannot put_variable_length_number() when number is negative: -1
    '''
    if num < 0:
        raise MidiException(
            'cannot put_variable_length_number() when number is negative: %s' % num)
    lst = bytearray()
    while True:
        result, num = num & 0x7F, num >> 7
        lst.append(result + 0x80)
        if num == 0:
            break
    lst.reverse()
    lst[-1] = lst[-1] & 0x7f
    return bytes(lst)

def put_numbers_as_list(num_list):
    '''
    Translate a list of numbers (0-255) into a bytestring.
    Used for encoding data messages where each byte encodes a different discrete value.

    >>> put_numbers_as_list([0, 0, 0, 3])
    b'\\x00\\x00\\x00\\x03'

    If a number is < 0 then it wraps around from the top.
    >>> put_numbers_as_list([0, 0, 0, -3])
    b'\\x00\\x00\\x00\\xfd'
    >>> put_numbers_as_list([0, 0, 0, -1])
    b'\\x00\\x00\\x00\\xff'

    A number > 255 is an exception:
    >>> put_numbers_as_list([256])
    Traceback (most recent call last):
    MidiException: Cannot place a number > 255 in a list: 256
    '''
    post = bytearray()
    for num in num_list:
        if num < 0:
            num = num % 256 # -1 will be 255
        if num >= 256:
            raise MidiException("Cannot place a number > 255 in a list: %d" % num)
        post.append(num)
    return bytes(post)

#-------------------------------------------------------------------------------
class Enumeration(object):
    '''
    Utility object for defining binary MIDI message constants.
    '''
    def __init__(self, enum_list=None):
        if enum_list is None:
            enum_list = []
        lookup = {}
        reverse_lookup = {}
        num = 0
        unique_names = []
        unique_values = []
        for enum in enum_list:
            if isinstance(enum, tuple):
                enum, num = enum
            if not isinstance(enum, str):
                raise EnumerationException("enum name is not a string: " + enum)
            if not isinstance(num, int):
                raise EnumerationException("enum value is not an integer: " + num)
            if enum in unique_names:
                raise EnumerationException("enum name is not unique: " + enum)
            if num in unique_values:
                raise EnumerationException("enum value is not unique for " + enum)
            unique_names.append(enum)
            unique_values.append(num)
            lookup[enum] = num
            reverse_lookup[num] = enum
            num = num + 1
        self.lookup = lookup
        self.reverse_lookup = reverse_lookup

    def __add__(self, other):
        lst = []
        for k in self.lookup:
            lst.append((k, self.lookup[k]))
        for k in other.lookup:
            lst.append((k, other.lookup[k]))
        return Enumeration(lst)

    def hasattr(self, attr):
        if attr in self.lookup:
            return True
        return False

    def has_value(self, attr):
        if attr in self.reverse_lookup:
            return True
        return False

    def __getattr__(self, attr):
        if attr not in self.lookup:
            raise AttributeError
        return self.lookup[attr]

    def whatis(self, value):
        post = self.reverse_lookup[value]
        return post

CHANNEL_VOICE_MESSAGES = Enumeration([
    ("NOTE_OFF", 0x80),
    ("NOTE_ON", 0x90),
    ("POLYPHONIC_KEY_PRESSURE", 0xA0),
    ("CONTROLLER_CHANGE", 0xB0),
    ("PROGRAM_CHANGE", 0xC0),
    ("CHANNEL_KEY_PRESSURE", 0xD0),
    ("PITCH_BEND", 0xE0)])

CHANNEL_MODE_MESSAGES = Enumeration([
    ("ALL_SOUND_OFF", 0x78),
    ("RESET_ALL_CONTROLLERS", 0x79),
    ("LOCAL_CONTROL", 0x7A),
    ("ALL_NOTES_OFF", 0x7B),
    ("OMNI_MODE_OFF", 0x7C),
    ("OMNI_MODE_ON", 0x7D),
    ("MONO_MODE_ON", 0x7E),
    ("POLY_MODE_ON", 0x7F)])

META_EVENTS = Enumeration([
    ("SEQUENCE_NUMBER", 0x00),
    ("TEXT_EVENT", 0x01),
    ("COPYRIGHT_NOTICE", 0x02),
    ("SEQUENCE_TRACK_NAME", 0x03),
    ("INSTRUMENT_NAME", 0x04),
    ("LYRIC", 0x05),
    ("MARKER", 0x06),
    ("CUE_POINT", 0x07),
    ("PROGRAM_NAME", 0x08),
    # optional event is used to embed the
    # patch/program name that is called up by the immediately
    # subsequent Bank Select and Program Change messages.
    # It serves to aid the end user in making an intelligent
    #  program choice when using different hardware.
    ("SOUND_SET_UNSUPPORTED", 0x09),
    ("MIDI_CHANNEL_PREFIX", 0x20),
    ("MIDI_PORT", 0x21),
    ("END_OF_TRACK", 0x2F),
    ("SET_TEMPO", 0x51),
    ("SMTPE_OFFSET", 0x54),
    ("TIME_SIGNATURE", 0x58),
    ("KEY_SIGNATURE", 0x59),
    ("SEQUENCER_SPECIFIC_META_EVENT", 0x7F)])

#-------------------------------------------------------------------------------
class MidiEvent(object):
    '''
    A model of a MIDI event, including note-on, note-off, program change,
    controller change, any many others.
    MidiEvent objects are paired (preceded) by :class:`~base.DeltaTime`
    objects in the list of events in a MidiTrack object.
    The `track` argument must be a :class:`~base.MidiTrack` object.
    The `type_` attribute is a string representation of a Midi event from the CHANNEL_VOICE_MESSAGES
    or META_EVENTS definitions.
    The `channel` attribute is an integer channel id, from 1 to 16.
    The `time` attribute is an integer duration of the event in ticks. This value
    can be zero. This value is not essential, as ultimate time positioning is
    determined by :class:`~base.DeltaTime` objects.
    The `pitch` attribute is only defined for note-on and note-off messages.
    The attribute stores an integer representation (0-127, with 60 = middle C).
    The `velocity` attribute is only defined for note-on and note-off messages.
    The attribute stores an integer representation (0-127).  A note-on message with
    velocity 0 is generally assumed to be the same as a note-off message.
    The `data` attribute is used for storing other messages,
    such as SEQUENCE_TRACK_NAME string values.

    >>> mt = MidiTrack(1)
    >>> me1 = MidiEvent(mt)
    >>> me1.type_ = "NOTE_ON"
    >>> me1.channel = 3
    >>> me1.time = 200
    >>> me1.pitch = 60
    >>> me1.velocity = 120
    >>> me1
    <MidiEvent NOTE_ON, t=200, track=1, channel=3, pitch=60, velocity=120>
    >>> me2 = MidiEvent(mt)
    >>> me2.type_ = "SEQUENCE_TRACK_NAME"
    >>> me2.time = 0
    >>> me2.data = 'guitar'
    >>> me2
    <MidiEvent SEQUENCE_TRACK_NAME, t=0, track=1, channel=None, data=b'guitar'>
    '''
    def __init__(self, track, type_=None, time=None, channel=None):
        self.track = track
        self.type_ = type_
        self.time = time
        self.channel = channel

        self._parameter1 = None # pitch or first data value
        self._parameter2 = None # velocity or second data value

        # data is a property...

        # if this is a Note on/off, need to store original
        # pitch space value in order to determine if this is has a microtone
        self.cent_shift = None

        # store a reference to a corresponding event
        # if a noteOn, store the note off, and vice versa
        # NTODO: We should make sure that we garbage collect this -- otherwise it's a memory
        # leak from a circular reference.
        # note: that's what weak references are for
        # unimplemented
        self.corresponding_event = None

        # store and pass on a running status if found
        self.last_status_byte = None

        self.sort_order = 0
        self.update_sort_order()

    def update_sort_order(self):
        if self.type_ == 'PITCH_BEND':
            self.sort_order = -10
        if self.type_ == 'NOTE_OFF':
            self.sort_order = -20

    def __repr__(self):
        if self.track is None:
            track_index = None
        else:
            track_index = self.track.index

        return_str = ("<MidiEvent %s, t=%s, track=%s, channel=%s" %
             (self.type_, repr(self.time), track_index,
              repr(self.channel)))
        if self.type_ in ['NOTE_ON', 'NOTE_OFF']:
            attr_list = ["pitch", "velocity"]
        else:
            if self._parameter2 is None:
                attr_list = ['data']
            else:
                attr_list = ['_parameter1', '_parameter2']

        for attrib in attr_list:
            if getattr(self, attrib) is not None:
                return_str = return_str + ", " + attrib + "=" + repr(getattr(self, attrib))
        return return_str + ">"

    def _set_pitch(self, value):
        self._parameter1 = value

    def _get_pitch(self):
        if self.type_ in ['NOTE_ON', 'NOTE_OFF']:
            return self._parameter1
        else:
            return None

    pitch = property(_get_pitch, _set_pitch)

    def _set_velocity(self, value):
        self._parameter2 = value

    def _get_velocity(self):
        return self._parameter2

    velocity = property(_get_velocity, _set_velocity)

    def _set_data(self, value):
        if value is not None and not isinstance(value, bytes):
            if isinstance(value, str):
                value = value.encode('utf-8')
        self._parameter1 = value

    def _get_data(self):
        return self._parameter1

    data = property(_get_data, _set_data)

    def set_pitch_bend(self, cents, bend_range=2):
        '''
        Treat this event as a pitch bend value, and set the ._parameter1 and
         ._parameter2 fields appropriately given a specified bend value in cents.

        The `bend_range` parameter gives the number of half steps in the bend range.

        >>> mt = MidiTrack(1)
        >>> me1 = MidiEvent(mt)
        >>> me1.set_pitch_bend(50)
        >>> me1._parameter1, me1._parameter2
        (0, 80)
        >>> me1.set_pitch_bend(100)
        >>> me1._parameter1, me1._parameter2
        (0, 96)
        >>> me1.set_pitch_bend(200)
        >>> me1._parameter1, me1._parameter2
        (127, 127)
        >>> me1.set_pitch_bend(-50)
        >>> me1._parameter1, me1._parameter2
        (0, 48)
        >>> me1.set_pitch_bend(-100)
        >>> me1._parameter1, me1._parameter2
        (0, 32)
        '''
        # value range is 0, 16383
        # center should be 8192
        cent_range = bend_range * 100
        center = 8192
        top_span = 16383 - center
        bottom_span = center

        if cents > 0:
            shift_scalar = cents / float(cent_range)
            shift = int(round(shift_scalar * top_span))
        elif cents < 0:
            shift_scalar = cents / float(cent_range) # will be negative
            shift = int(round(shift_scalar * bottom_span)) # will be negative
        else:
            shift = 0
        target = center + shift

        # produce a two-char value
        char_value = put_variable_length_number(target)
        data1, _ = get_number(char_value[0], 1)
        # need to convert from 8 bit to 7, so using & 0x7F
        data1 = data1 & 0x7F
        if len(char_value) > 1:
            data2, _ = get_number(char_value[1], 1)
            data2 = data2 & 0x7F
        else:
            data2 = 0

        self._parameter1 = data2
        self._parameter2 = data1 # data1 is msb here

    def _parse_channel_voice_message(self, midi_str):
        '''

        >>> mt = MidiTrack(1)
        >>> me1 = MidiEvent(mt)
        >>> remainder = me1._parse_channel_voice_message(ints_to_hex_string([144, 60, 120]))
        >>> me1.channel
        1
        >>> remainder = me1._parse_channel_voice_message(ints_to_hex_string([145, 60, 120]))
        >>> me1.channel
        2
        >>> me1.type_
        'NOTE_ON'
        >>> me1.pitch
        60
        >>> me1.velocity
        120
        '''
        # first_byte, channel_number, and second_byte define
        # characteristics of the first two chars
        # for first_byte: The left nybble (4 bits) contains the actual command, and the right nibble
        # contains the midi channel number on which the command will be executed.
        if is_num(midi_str[0]):
            first_byte = midi_str[0]
        else:
            first_byte = ord(midi_str[0])
        channel_number = first_byte & 0xF0
        if is_num(midi_str[1]):
            second_byte = midi_str[1]
        else:
            second_byte = ord(midi_str[1])
        if is_num(midi_str[2]):
            third_byte = midi_str[2]
        else:
            third_byte = ord(midi_str[2])

        self.channel = (first_byte & 0x0F) + 1
        self.type_ = CHANNEL_VOICE_MESSAGES.whatis(channel_number)
        if (self.type_ == "PROGRAM_CHANGE" or
                self.type_ == "CHANNEL_KEY_PRESSURE"):
            self.data = second_byte
            return midi_str[2:]
        elif self.type_ == "CONTROLLER_CHANGE":
            # for now, do nothing with this data
            # for a note, str[2] is velocity; here, it is the control value
            self.pitch = second_byte # this is the controller id
            self.velocity = third_byte # this is the controller value
            return midi_str[3:]
        else:
            self.pitch = second_byte
            self.velocity = third_byte
            return midi_str[3:]

    def read(self, time, midi_str):
        '''
        Parse the string that is given and take the beginning
        section and convert it into data for this event and return the
        now truncated string.
        The `time` value is the number of ticks into the Track
        at which this event happens. This is derived from reading
        data the level of the track.
        TODO: These instructions are inadequate.
        >>> # all note-on messages (144-159) can be found
        >>> 145 & 0xF0 # testing message type_ extraction
        144
        >>> 146 & 0xF0 # testing message type_ extraction
        144
        >>> (144 & 0x0F) + 1 # getting the channel
        1
        >>> (159 & 0x0F) + 1 # getting the channel
        16
        '''
        if len(midi_str) < 2:
            # often what we have here are null events:
            # the string is simply: 0x00
            print(
                'MidiEvent.read(): got bad data string',
                'time',
                time,
                'str',
                repr(midi_str))
            return ''

        # first_byte, message_type, and second_byte define
        # characteristics of the first two chars
        # for first_byte: The left nybble (4 bits) contains the
        # actual command, and the right nibble
        # contains the midi channel number on which the command will
        # be executed.
        if is_num(midi_str[0]):
            first_byte = midi_str[0]
        else:
            first_byte = ord(midi_str[0])

        # detect running status: if the status byte is less than 128, its
        # not a status byte, but a data byte
        if first_byte < 128:
            if self.last_status_byte is not None:
                rsb = self.last_status_byte
                if is_num(rsb):
                    rsb = bytes([rsb])
            else:
                rsb = bytes([0x90])
            # add the running status byte to the front of the string
            # and process as before
            midi_str = rsb + midi_str
            if is_num(midi_str[0]):
                first_byte = midi_str[0]
            else:
                first_byte = ord(midi_str[0])
        else:
            self.last_status_byte = midi_str[0]

        message_type = first_byte & 0xF0

        if is_num(midi_str[1]):
            second_byte = midi_str[1]
        else:
            second_byte = ord(midi_str[1])

        if CHANNEL_VOICE_MESSAGES.has_value(message_type):
            return self._parse_channel_voice_message(midi_str)

        elif message_type == 0xB0 and CHANNEL_MODE_MESSAGES.has_value(second_byte):
            self.channel = (first_byte & 0x0F) + 1
            self.type_ = CHANNEL_MODE_MESSAGES.whatis(second_byte)
            if self.type_ == "LOCAL_CONTROL":
                self.data = (ord(midi_str[2]) == 0x7F)
            elif self.type_ == "MONO_MODE_ON":
                self.data = ord(midi_str[2])
            else:
                print('unhandled message:', midi_str[2])
            return midi_str[3:]

        elif first_byte == 0xF0 or first_byte == 0xF7:
            self.type_ = {0xF0: "F0_SYSEX_EVENT",
                         0xF7: "F7_SYSEX_EVENT"}[first_byte]
            length, midi_str = get_variable_length_number(midi_str[1:])
            self.data = midi_str[:length]
            return midi_str[length:]

        # SEQUENCE_TRACK_NAME and other MetaEvents are here
        elif first_byte == 0xFF:
            if not META_EVENTS.has_value(second_byte):
                print("unknown meta event: FF %02X" % second_byte)
                sys.stdout.flush()
                raise MidiException("Unknown midi event type_: %r, %r" % (first_byte, second_byte))
            self.type_ = META_EVENTS.whatis(second_byte)
            length, midi_str = get_variable_length_number(midi_str[2:])
            self.data = midi_str[:length]
            return midi_str[length:]
        else:
            # an uncaught message
            print(
                'got unknown midi event type_',
                repr(first_byte),
                'char_to_binary(midi_str[0])',
                char_to_binary(midi_str[0]),
                'char_to_binary(midi_str[1])',
                char_to_binary(midi_str[1]))
            raise MidiException("Unknown midi event type_")


    def get_bytes(self):
        '''
        Return a set of bytes for this MIDI event.
        '''
        sysex_event_dict = {"F0_SYSEX_EVENT": 0xF0,
                            "F7_SYSEX_EVENT": 0xF7}
        if CHANNEL_VOICE_MESSAGES.hasattr(self.type_):
            return_bytes = chr((self.channel - 1) +
                    getattr(CHANNEL_VOICE_MESSAGES, self.type_))
            # for writing note-on/note-off
            if self.type_ not in [
                    'PROGRAM_CHANGE', 'CHANNEL_KEY_PRESSURE']:
                # this results in a two-part string, like '\x00\x00'
                try:
                    data = chr(self._parameter1) + chr(self._parameter2)
                except ValueError:
                    raise MidiException(
                        "Problem with representing either %d or %d" % (
                            self._parameter1, self._parameter2))
            elif self.type_ in ['PROGRAM_CHANGE']:
                try:
                    data = chr(self.data)
                except TypeError:
                    raise MidiException(
                        "Got incorrect data for %return_bytes in .data: %return_bytes," %
                            (self, self.data) + "cannot parse Program Change")
            else:
                try:
                    data = chr(self.data)
                except TypeError:
                    raise MidiException(
                        ("Got incorrect data for %return_bytes in "
                         ".data: %return_bytes, ") % (self, self.data) +
                        "cannot parse Miscellaneous Message")
            return return_bytes + data

        elif CHANNEL_MODE_MESSAGES.hasattr(self.type_):
            return_bytes = getattr(CHANNEL_MODE_MESSAGES, self.type_)
            return_bytes = (chr(0xB0 + (self.channel - 1)) +
                 chr(return_bytes) +
                 chr(self.data))
            return return_bytes

        elif self.type_ in sysex_event_dict:
            return_bytes = bytes([sysex_event_dict[self.type_]])
            return_bytes = return_bytes + put_variable_length_number(len(self.data))
            return return_bytes + self.data

        elif META_EVENTS.hasattr(self.type_):
            return_bytes = bytes([0xFF]) + bytes([getattr(META_EVENTS, self.type_)])
            return_bytes = return_bytes + put_variable_length_number(len(self.data))

            try:
                return return_bytes + self.data
            except (UnicodeDecodeError, TypeError):
                return return_bytes + unicodedata.normalize(
                    'NFKD', self.data).encode('ascii', 'ignore')
        else:
            raise MidiException("unknown midi event type_: %return_bytes" % self.type_)

    #---------------------------------------------------------------------------
    def is_note_on(self):
        '''
        return a boolean if this is a NOTE_ON message and velocity is not zero_

        >>> mt = MidiTrack(1)
        >>> me1 = MidiEvent(mt)
        >>> me1.type_ = "NOTE_ON"
        >>> me1.velocity = 120
        >>> me1.is_note_on()
        True
        >>> me1.is_note_off()
        False
        '''
        return self.type_ == "NOTE_ON" and self.velocity != 0

    def is_note_off(self):
        '''
        Return a boolean if this is should be interpreted as a note-off message,
        either as a real note-off or as a note-on with zero velocity.

        >>> mt = MidiTrack(1)
        >>> me1 = MidiEvent(mt)
        >>> me1.type_ = "NOTE_OFF"
        >>> me1.is_note_on()
        False
        >>> me1.is_note_off()
        True
        >>> me2 = MidiEvent(mt)
        >>> me2.type_ = "NOTE_ON"
        >>> me2.velocity = 0
        >>> me2.is_note_on()
        False
        >>> me2.is_note_off()
        True
        '''
        if self.type_ == "NOTE_OFF":
            return True
        elif self.type_ == "NOTE_ON" and self.velocity == 0:
            return True
        return False

    def is_delta_time(self):
        '''
        Return a boolean if this is a DeltaTime subclass.

        >>> mt = MidiTrack(1)
        >>> dt = DeltaTime(mt)
        >>> dt.is_delta_time()
        True
        '''
        if self.type_ == "DeltaTime":
            return True
        return False

    def matched_note_off(self, other):
        '''
        Returns True if `other` is a MIDI event that specifies
        a note-off message for this message.  That is, this event
        is a NOTE_ON message, and the other is a NOTE_OFF message
        for this pitch on this channel.  Otherwise returns False

        >>> mt = MidiTrack(1)
        >>> me1 = MidiEvent(mt)
        >>> me1.type_ = "NOTE_ON"
        >>> me1.velocity = 120
        >>> me1.pitch = 60
        >>> me2 = MidiEvent(mt)
        >>> me2.type_ = "NOTE_ON"
        >>> me2.velocity = 0
        >>> me2.pitch = 60
        >>> me1.matched_note_off(me2)
        True
        >>> me2.pitch = 61
        >>> me1.matched_note_off(me2)
        False
        >>> me2.type_ = "NOTE_OFF"
        >>> me1.matched_note_off(me2)
        False
        >>> me2.pitch = 60
        >>> me1.matched_note_off(me2)
        True
        >>> me2.channel = 12
        >>> me1.matched_note_off(me2)
        False
        '''
        if other.is_note_off:
            # might check velocity here too?
            if self.pitch == other.pitch and self.channel == other.channel:
                return True
        return False

class DeltaTime(MidiEvent):
    '''
    A :class:`~base.MidiEvent` subclass that stores the
    time change (in ticks) since the start or since the last MidiEvent.
    Pairs of DeltaTime and MidiEvent objects are the basic presentation of temporal data.
    The `track` argument must be a :class:`~base.MidiTrack` object.
    Time values are in integers, representing ticks.
    The `channel` attribute, inherited from MidiEvent is not used and set to None
    unless overridden (don't!).

    >>> mt = MidiTrack(1)
    >>> dt = DeltaTime(mt)
    >>> dt.time = 380
    >>> dt
    <MidiEvent DeltaTime, t=380, track=1, channel=None>
    '''
    def __init__(self, track, time=None, channel=None):
        MidiEvent.__init__(self, track, time=time, channel=channel)
        self.type_ = "DeltaTime"

    def read(self, oldstr):
        self.time, newstr = get_variable_length_number(oldstr)
        return self.time, newstr

    def get_bytes(self):
        midi_str = put_variable_length_number(self.time)
        return midi_str

class MidiTrack(object):
    '''
    A MIDI Track. Each track contains a list of
    :class:`~base.MidiChannel` objects, one for each channel.
    All events are stored in the `events` list, in order.
    An `index` is an integer identifier for this object.
    TODO: Better Docs

    >>> mt = MidiTrack(0)

    '''
    def __init__(self, index):
        self.index = index
        self.events = []
        self.length = 0 #the data length; only used on read()

    def read(self, midi_str):
        '''
        Read as much of the string (representing midi data) as necessary;
        return the remaining string for reassignment and further processing.
        The string should begin with `MTrk`, specifying a Midi Track
        Creates and stores :class:`~base.DeltaTime`
        and :class:`~base.MidiEvent` objects.
        '''
        time = 0 # a running counter of ticks

        if not midi_str[:4] == b"MTrk":
            raise MidiException('badly formed midi string: missing leading MTrk')
        # get the 4 chars after the MTrk encoding
        length, midi_str = get_number(midi_str[4:], 4)
        self.length = length

        # all event data is in the track str
        track_str = midi_str[:length]
        remainder = midi_str[length:]

        e_previous = None
        while track_str:
            # shave off the time stamp from the event
            delta_t = DeltaTime(self)
            # return extracted time, as well as remaining string
            d_time, track_str_candidate = delta_t.read(track_str)
            # this is the offset that this event happens at, in ticks
            time_candidate = time + d_time

            # pass self to event, set this MidiTrack as the track for this event
            event = MidiEvent(self)
            if e_previous is not None: # set the last status byte
                event.last_status_byte = e_previous.last_status_byte
            # some midi events may raise errors; simply skip for now
            try:
                track_str_candidate = event.read(time_candidate, track_str_candidate)
            except MidiException:
                # assume that track_str, after delta extraction, is still correct
                # set to result after taking delta time
                track_str = track_str_candidate
                continue
            # only set after trying to read, which may raise exception
            time = time_candidate
            track_str = track_str_candidate # remainder string
            # only append if we get this far
            self.events.append(delta_t)
            self.events.append(event)
            e_previous = event

        return remainder # remainder string after extracting track data

    def get_bytes(self):
        '''
        returns a string of midi-data from the `.events` in the object.
        '''
        # build str using MidiEvents
        midi_str = b""
        for event in self.events:
            # this writes both delta time and message events
            try:
                event_bytes = event.get_bytes()
                int_array = []
                for byte in event_bytes:
                    if is_num(byte):
                        int_array.append(byte)
                    else:
                        int_array.append(ord(byte))
                event_bytes = bytes(bytearray(int_array))
                midi_str = midi_str + event_bytes
            except MidiException as err:
                print("Conversion error for %s: %s; ignored." % (event, err))
        return b"MTrk" + put_number(len(midi_str), 4) + midi_str

    def __repr__(self):
        return_str = "<MidiTrack %d -- %d events\n" % (self.index, len(self.events))
        for event in self.events:
            return_str = return_str + "    " + event.__repr__() + "\n"
        return return_str + "  >"

    #---------------------------------------------------------------------------
    def update_events(self):
        '''
        We may attach events to this track before setting their `track` parameter.
        This method will move through all events and set their track to this track.
        '''
        for event in self.events:
            event.track = self

    def has_notes(self):
        '''Return True/False if this track has any note-on/note-off pairs defined.
        '''
        for event in self.events:
            if event.is_note_on():
                return True
        return False

    def set_channel(self, value):
        '''Set the channel of all events in this Track.
        '''
        if value not in range(1, 17):
            raise MidiException('bad channel value: %s' % value)
        for event in self.events:
            event.channel = value

    def get_channels(self):
        '''Get all channels used in this Track.
        '''
        post = []
        for event in self.events:
            if event.channel not in post:
                post.append(event.channel)
        return post

    def get_program_changes(self):
        '''Get all unique program changes used in this Track, sorted.
        '''
        post = []
        for event in self.events:
            if event.type_ == 'PROGRAM_CHANGE':
                if event.data not in post:
                    post.append(event.data)
        return post

class MidiFile(object):
    '''
    Low-level MIDI file writing, emulating methods from normal Python files.
    The `ticks_per_quarter_note` attribute must be set before writing. 1024 is a common value.
    This object is returned by some properties for directly writing files of midi representations.
    '''

    def __init__(self):
        self.file = None
        self.format = 1
        self.tracks = []
        self.ticks_per_quarter_note = 1024
        self.ticks_per_second = None

    def open(self, filename, attrib="rb"):
        '''
        Open a MIDI file path for reading or writing.

        For writing to a MIDI file, `attrib` should be "wb".
        '''
        if attrib not in ['rb', 'wb']:
            raise MidiException('cannot read or write unless in binary mode, not:', attrib)
        self.file = open(filename, attrib)

    def open_file_like(self, file_like):
        '''Assign a file-like object, such as those provided by StringIO, as an open file object.
        >>> from io import StringIO
        >>> fileLikeOpen = StringIO()
        >>> mf = MidiFile()
        >>> mf.open_file_like(fileLikeOpen)
        >>> mf.close()
        '''
        self.file = file_like

    def __repr__(self):
        return_str = "<MidiFile %d tracks\n" % len(self.tracks)
        for track in self.tracks:
            return_str = return_str + "  " + track.__repr__() + "\n"
        return return_str + ">"

    def close(self):
        '''
        Close the file.
        '''
        self.file.close()

    def read(self):
        '''
        Read and parse MIDI data stored in a file.
        '''
        self.readstr(self.file.read())

    def readstr(self, midi_str):
        '''
        Read and parse MIDI data as a string, putting the
        data in `.ticks_per_quarter_note` and a list of
        `MidiTrack` objects in the attribute `.tracks`.
        '''
        if not midi_str[:4] == b"MThd":
            raise MidiException('badly formated midi string, got: %s' % midi_str[:20])

        # we step through the str src, chopping off characters as we go
        # and reassigning to str
        length, midi_str = get_number(midi_str[4:], 4)
        if length != 6:
            raise MidiException('badly formated midi string')

        midi_format_type, midi_str = get_number(midi_str, 2)
        self.format = midi_format_type
        if midi_format_type not in (0, 1):
            raise MidiException('cannot handle midi file format: %s' % format)

        num_tracks, midi_str = get_number(midi_str, 2)
        division, midi_str = get_number(midi_str, 2)

        # very few midi files seem to define ticks_per_second
        if division & 0x8000:
            frames_per_second = -((division >> 8) | -128)
            ticks_per_frame = division & 0xFF
            if ticks_per_frame not in [24, 25, 29, 30]:
                raise MidiException('cannot handle ticks per frame: %s' % ticks_per_frame)
            if ticks_per_frame == 29:
                ticks_per_frame = 30  # drop frame
            self.ticks_per_second = ticks_per_frame * frames_per_second
        else:
            self.ticks_per_quarter_note = division & 0x7FFF

        for i in range(num_tracks):
            trk = MidiTrack(i) # sets the MidiTrack index parameters
            midi_str = trk.read(midi_str) # pass all the remaining string, reassing
            self.tracks.append(trk)

    def write(self):
        '''
        Write MIDI data as a file to the file opened with `.open()`.
        '''
        self.file.write(self.writestr())

    def writestr(self):
        '''
        generate the midi data header and convert the list of
        midi_track objects in self_tracks into midi data and return it as a string_
        '''
        midi_str = self.write_m_thd_str()
        for trk in self.tracks:
            midi_str = midi_str + trk.get_bytes()
        return midi_str

    def write_m_thd_str(self):
        '''
        convert the information in self_ticks_per_quarter_note
        into midi data header and return it as a string_'''
        division = self.ticks_per_quarter_note
        # Don't handle ticks_per_second yet, too confusing
        if (division & 0x8000) != 0:
            raise MidiException(
                'Cannot write midi string unless self.ticks_per_quarter_note is a multiple of 1024')
        midi_str = b"MThd" + put_number(6, 4) + put_number(self.format, 2)
        midi_str = midi_str + put_number(len(self.tracks), 2)
        midi_str = midi_str + put_number(division, 2)
        return midi_str

if __name__ == "__main__":
    import doctest
    doctest.testmod(optionflags=doctest.ELLIPSIS)
