#!/usr/bin/env python3
#
# Copyright 2019 Canonical Ltd.
# Written by:
#   Maciej Kisielewski <maciej.kisielewski@canonical.com>
#
# This is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3,
# as published by the Free Software Foundation.
#
# This file is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this file.  If not, see <http://www.gnu.org/licenses/>.
"""
This program tests whether the system properly reacts to hotkey presses.

To inject the keypresses /dev/input/ devices are used.

For particular scenarios see "check_*" methods of the HotKeyTesting class.

TODO: Create one virtual input device using uinput.
      Heuristic for picking the device to write to is not optimal, and on some
      systems the fake keypresses are not registered. Having "own" input
      device could improve reliability/portability.
"""

import contextlib
import datetime
import enum
import os
import re
import struct
import subprocess
import sys
import time


class KeyCodes(enum.Enum):
    KEY_RESERVED = 0
    KEY_ESC = 1
    KEY_1 = 2
    KEY_2 = 3
    KEY_3 = 4
    KEY_4 = 5
    KEY_5 = 6
    KEY_6 = 7
    KEY_7 = 8
    KEY_8 = 9
    KEY_9 = 10
    KEY_0 = 11
    KEY_MINUS = 12
    KEY_EQUAL = 13
    KEY_BACKSPACE = 14
    KEY_TAB = 15
    KEY_Q = 16
    KEY_W = 17
    KEY_E = 18
    KEY_R = 19
    KEY_T = 20
    KEY_Y = 21
    KEY_U = 22
    KEY_I = 23
    KEY_O = 24
    KEY_P = 25
    KEY_LEFTBRACE = 26
    KEY_RIGHTBRACE = 27
    KEY_ENTER = 28
    KEY_LEFTCTRL = 29
    KEY_A = 30
    KEY_S = 31
    KEY_D = 32
    KEY_F = 33
    KEY_G = 34
    KEY_H = 35
    KEY_J = 36
    KEY_K = 37
    KEY_L = 38
    KEY_SEMICOLON = 39
    KEY_APOSTROPHE = 40
    KEY_GRAVE = 41
    KEY_LEFTSHIFT = 42
    KEY_BACKSLASH = 43
    KEY_Z = 44
    KEY_X = 45
    KEY_C = 46
    KEY_V = 47
    KEY_B = 48
    KEY_N = 49
    KEY_M = 50
    KEY_COMMA = 51
    KEY_DOT = 52
    KEY_SLASH = 53
    KEY_RIGHTSHIFT = 54
    KEY_KPASTERISK = 55
    KEY_LEFTALT = 56
    KEY_SPACE = 57
    KEY_CAPSLOCK = 58
    KEY_F1 = 59
    KEY_F2 = 60
    KEY_F3 = 61
    KEY_F4 = 62
    KEY_F5 = 63
    KEY_F6 = 64
    KEY_F7 = 65
    KEY_F8 = 66
    KEY_F9 = 67
    KEY_F10 = 68
    KEY_NUMLOCK = 69
    KEY_SCROLLLOCK = 70
    KEY_KP7 = 71
    KEY_KP8 = 72
    KEY_KP9 = 73
    KEY_KPMINUS = 74
    KEY_KP4 = 75
    KEY_KP5 = 76
    KEY_KP6 = 77
    KEY_KPPLUS = 78
    KEY_KP1 = 79
    KEY_KP2 = 80
    KEY_KP3 = 81
    KEY_KP0 = 82
    KEY_KPDOT = 83
    KEY_ZENKAKUHANKAKU = 85
    KEY_102ND = 86
    KEY_F11 = 87
    KEY_F12 = 88
    KEY_RO = 89
    KEY_KATAKANA = 90
    KEY_HIRAGANA = 91
    KEY_HENKAN = 92
    KEY_KATAKANAHIRAGANA = 93
    KEY_MUHENKAN = 94
    KEY_KPJPCOMMA = 95
    KEY_KPENTER = 96
    KEY_RIGHTCTRL = 97
    KEY_KPSLASH = 98
    KEY_SYSRQ = 99
    KEY_RIGHTALT = 100
    KEY_LINEFEED = 101
    KEY_HOME = 102
    KEY_UP = 103
    KEY_PAGEUP = 104
    KEY_LEFT = 105
    KEY_RIGHT = 106
    KEY_END = 107
    KEY_DOWN = 108
    KEY_PAGEDOWN = 109
    KEY_INSERT = 110
    KEY_DELETE = 111
    KEY_MACRO = 112
    KEY_MUTE = 113
    KEY_VOLUMEDOWN = 114
    KEY_VOLUMEUP = 115
    KEY_POWER = 116  # SC System Power Down
    KEY_KPEQUAL = 117
    KEY_KPPLUSMINUS = 118
    KEY_PAUSE = 119
    KEY_SCALE = 120  # AL Compiz Scale (Expose)

    KEY_KPCOMMA = 121
    KEY_HANGEUL = 122
    KEY_HANGUEL = KEY_HANGEUL
    KEY_HANJA = 123
    KEY_YEN = 124
    KEY_LEFTMETA = 125
    KEY_RIGHTMETA = 126
    KEY_COMPOSE = 127

    KEY_STOP = 128  # AC Stop
    KEY_AGAIN = 129
    KEY_PROPS = 130  # AC Properties
    KEY_UNDO = 131  # AC Undo
    KEY_FRONT = 132
    KEY_COPY = 133  # AC Copy
    KEY_OPEN = 134  # AC Open
    KEY_PASTE = 135  # AC Paste
    KEY_FIND = 136  # AC Search
    KEY_CUT = 137  # AC Cut
    KEY_HELP = 138  # AL Integrated Help Center
    KEY_MENU = 139  # Menu (show menu)
    KEY_CALC = 140  # AL Calculator
    KEY_SETUP = 141
    KEY_SLEEP = 142  # SC System Sleep
    KEY_WAKEUP = 143  # System Wake Up
    KEY_FILE = 144  # AL Local Machine Browser
    KEY_SENDFILE = 145
    KEY_DELETEFILE = 146
    KEY_XFER = 147
    KEY_PROG1 = 148
    KEY_PROG2 = 149
    KEY_WWW = 150  # AL Internet Browser
    KEY_MSDOS = 151
    KEY_COFFEE = 152  # AL Terminal Lock/Screensaver
    KEY_SCREENLOCK = KEY_COFFEE
    KEY_ROTATE_DISPLAY = 153  # Display orientation for e.g. tablets
    KEY_DIRECTION = KEY_ROTATE_DISPLAY
    KEY_CYCLEWINDOWS = 154
    KEY_MAIL = 155
    KEY_BOOKMARKS = 156  # AC Bookmarks
    KEY_COMPUTER = 157
    KEY_BACK = 158  # AC Back
    KEY_FORWARD = 159  # AC Forward
    KEY_CLOSECD = 160
    KEY_EJECTCD = 161
    KEY_EJECTCLOSECD = 162
    KEY_NEXTSONG = 163
    KEY_PLAYPAUSE = 164
    KEY_PREVIOUSSONG = 165
    KEY_STOPCD = 166
    KEY_RECORD = 167
    KEY_REWIND = 168
    KEY_PHONE = 169  # Media Select Telephone
    KEY_ISO = 170
    KEY_CONFIG = 171  # AL Consumer Control Configuration
    KEY_HOMEPAGE = 172  # AC Home
    KEY_REFRESH = 173  # AC Refresh
    KEY_EXIT = 174  # AC Exit
    KEY_MOVE = 175
    KEY_EDIT = 176
    KEY_SCROLLUP = 177
    KEY_SCROLLDOWN = 178
    KEY_KPLEFTPAREN = 179
    KEY_KPRIGHTPAREN = 180
    KEY_NEW = 181  # AC New
    KEY_REDO = 182  # AC Redo/Repeat

    KEY_F13 = 183
    KEY_F14 = 184
    KEY_F15 = 185
    KEY_F16 = 186
    KEY_F17 = 187
    KEY_F18 = 188
    KEY_F19 = 189
    KEY_F20 = 190
    KEY_F21 = 191
    KEY_F22 = 192
    KEY_F23 = 193
    KEY_F24 = 194

    KEY_PLAYCD = 200
    KEY_PAUSECD = 201
    KEY_PROG3 = 202
    KEY_PROG4 = 203
    KEY_DASHBOARD = 204  # AL Dashboard
    KEY_SUSPEND = 205
    KEY_CLOSE = 206  # AC Close
    KEY_PLAY = 207
    KEY_FASTFORWARD = 208
    KEY_BASSBOOST = 209
    KEY_PRINT = 210  # AC Print
    KEY_HP = 211
    KEY_CAMERA = 212
    KEY_SOUND = 213
    KEY_QUESTION = 214
    KEY_EMAIL = 215
    KEY_CHAT = 216
    KEY_SEARCH = 217
    KEY_CONNECT = 218
    KEY_FINANCE = 219  # AL Checkbook/Finance
    KEY_SPORT = 220
    KEY_SHOP = 221
    KEY_ALTERASE = 222
    KEY_CANCEL = 223  # AC Cancel
    KEY_BRIGHTNESSDOWN = 224
    KEY_BRIGHTNESSUP = 225
    KEY_MEDIA = 226
    # Cycle between available video outputs (Monitor/LCD/TV-out/etc)
    KEY_SWITCHVIDEOMODE = 227
    KEY_KBDILLUMTOGGLE = 228
    KEY_KBDILLUMDOWN = 229
    KEY_KBDILLUMUP = 230
    KEY_SEND = 231  # AC Send
    KEY_REPLY = 232  # AC Reply
    KEY_FORWARDMAIL = 233  # AC Forward Msg
    KEY_SAVE = 234  # AC Save
    KEY_DOCUMENTS = 235
    KEY_BATTERY = 236
    KEY_BLUETOOTH = 237
    KEY_WLAN = 238
    KEY_UWB = 239
    KEY_UNKNOWN = 240
    KEY_VIDEO_NEXT = 241  # drive next video source
    KEY_VIDEO_PREV = 242  # drive previous video source
    KEY_BRIGHTNESS_CYCLE = 243  # brightness up, after max is min
    # Set Auto Brightness = manual brightness control is off, rely on ambient
    KEY_BRIGHTNESS_AUTO = 244
    KEY_BRIGHTNESS_ZERO = KEY_BRIGHTNESS_AUTO
    KEY_DISPLAY_OFF = 245  # display device to off state
    KEY_WWAN = 246  # Wireless WAN (LTE, UMTS, GSM, etc.)
    KEY_WIMAX = KEY_WWAN
    KEY_RFKILL = 247  # Key that controls all radios
    KEY_MICMUTE = 248  # Mute / unmute the microphone

    def from_char(c):
        obvious_keys = {
            '/': KeyCodes.KEY_SLASH,
            ' ': KeyCodes.KEY_SPACE,
            '-': KeyCodes.KEY_MINUS,
            '.': KeyCodes.KEY_DOT,
        }
        if c in obvious_keys.keys():
            return obvious_keys[c]
        keycode_name = 'KEY_{}'.format(c.upper())
        try:
            return KeyCodes[keycode_name]
        except KeyError:
            raise SystemExit(
                'One does not simply convert {} to a keycode'.format(c))


class VolumeChange:
    def __init__(self):
        self.before = 0
        self.after = 0
        self.mute_before = None
        self.mute_after = None


class FauxKeyboard():
    def __init__(self):
        base = '/dev/input/by-path'
        all_devs = [
            os.path.join(base, dev) for dev in sorted(os.listdir(base))]
        kbd_devs = [dev for dev in all_devs if dev.endswith('kbd')]
        event_devs = [dev for dev in all_devs if dev.endswith('event-mouse')]
        self.kb_dev_file = None
        self.event_dev_file = None
        if not kbd_devs:
            raise SystemExit(
                "Could not connect to existing keyboard connection. "
                "Is keyboard plugged in?")
        if not event_devs:
            raise SystemExit(
                "Could not connect to existing mouse connection. "
                "Is mouse plugged in?")
        self.kb_dev_file = open(kbd_devs[0], 'wb')
        self.event_dev_file = open(event_devs[0], 'wb')
        self.event_struct = struct.Struct('llHHi')

    def __del__(self):
        if self.kb_dev_file:
            self.kb_dev_file.close()
        if self.event_dev_file:
            self.event_dev_file.close()

    def type_text(self, text):
        for c in text:
            if c == '>':
                self.press_key(KeyCodes.KEY_DOT, {'shift'})
                continue
            modifiers = {'shift'} if c.isupper() else set()
            self.press_key(KeyCodes.from_char(c), modifiers)

    def press_key(self, key_code, modifiers=set(), repetitions=1, delay=0.05):
        # simple key press actions contains four events:
        # EV_MSC, MSC_SCAN, {KEY_CODE}
        # EV_KEY, {KEY_CODE}, 1
        # EV_SYN, 0, 0
        # EV_KEY, {KEY_CODE}, 0
        # XXX: ATM there's no distinction between left and right modifiers
        assert(repetitions >= 0)
        # sending "special" codes (like media control ones) to a general kbd
        # device doesn't work, so we have to send them to the event-mouse one
        SPECIAL_CODES = [
            KeyCodes.KEY_PLAYPAUSE,
        ]
        use_special = key_code in SPECIAL_CODES
        while repetitions:
            if not modifiers.issubset({'alt', 'ctrl', 'shift', 'meta'}):
                raise SystemExit('Unknown modifier')
            if type(key_code) == KeyCodes:
                key_code = key_code.value
            data = bytes()
            data += self.event_struct.pack(0, 0, 4, 4, key_code)
            for mod in modifiers:
                mod_code = KeyCodes['KEY_LEFT{}'.format(mod.upper())].value
                data += self.event_struct.pack(0, 0, 1, mod_code, 1)
            data += self.event_struct.pack(0, 0, 1, key_code, 1)
            data += self.event_struct.pack(0, 0, 0, 0, 0)
            data += self.event_struct.pack(0, 10, 1, key_code, 0)
            for mod in modifiers:
                mod_code = KeyCodes['KEY_LEFT{}'.format(mod.upper())].value
                data += self.event_struct.pack(0, 10, 1, mod_code, 0)
            data += self.event_struct.pack(0, 10, 0, 0, 0)
            if use_special:
                self.event_dev_file.write(data)
                self.event_dev_file.flush()
            else:
                self.kb_dev_file.write(data)
                self.kb_dev_file.flush()
            time.sleep(delay)
            repetitions -= 1


class HotKeyTesting:

    def __init__(self):
        self.kb = FauxKeyboard()

    def check_volume_up(self):
        """
        Check if the volume up key has an effect on ALSA
        """
        # if the volume is already on max, then raising it won't make any
        # difference, so first, let's lower it before establishing the baseline
        self.kb.press_key(KeyCodes.KEY_VOLUMEDOWN, repetitions=4, delay=0.2)
        self.kb.press_key(KeyCodes.KEY_VOLUMEUP)
        # let's grab output of alsa mixer to establish what is the baseline
        # before we start raising the volume
        vc = VolumeChange()
        with self._monitored_volume_change(vc):
            self.kb.press_key(KeyCodes.KEY_VOLUMEUP, repetitions=3, delay=0.2)
        time.sleep(1)
        return vc.before < vc.after

    def check_volume_down(self):
        """
        Check if the volume down key has an effect on ALSA
        """
        # if the volume is already on min, then lowering it won't make any
        # difference, so first, let's raise it before establishing the baseline
        self.kb.press_key(KeyCodes.KEY_VOLUMEUP, repetitions=4, delay=0.2)
        self.kb.press_key(KeyCodes.KEY_VOLUMEDOWN)
        # let's grab output of alsa mixer to establish what is the baseline
        # before we start raising the volume
        vc = VolumeChange()
        with self._monitored_volume_change(vc):
            self.kb.press_key(
                KeyCodes.KEY_VOLUMEDOWN, repetitions=3, delay=0.2)
        return vc.before > vc.after

    def check_mute(self):
        """
        Check if the mute key has an effect on ALSA
        """
        # first, let's raise volume (if it was already muted, then it will
        # unmute it)
        self.kb.press_key(KeyCodes.KEY_VOLUMEUP)
        vc = VolumeChange()
        with self._monitored_volume_change(vc):
            self.kb.press_key(KeyCodes.KEY_MUTE)
        time.sleep(1)
        return vc.mute_after

    @contextlib.contextmanager
    def _monitored_volume_change(self, vc):
        before = subprocess.check_output('amixer').decode(
            sys.stdout.encoding).splitlines()
        yield
        after = subprocess.check_output('amixer').decode(
            sys.stdout.encoding).splitlines()
        temp = before.copy()
        for line in temp:
            if line in after:
                before.remove(line)
                after.remove(line)
        if not before:
            # all lines removed from before, so there's no state change
            # of the stuff reported bevore hitting volume up, so let's fail
            # the test
            print('No change in amixer registered! ', end='')
            return
        # we expect that the lines that changed are status information about
        # the output devices. Percentage volume is in square brackets so let's
        # search for those and see if they got higher
        regex = re.compile(r'\[(\d*)%\].*\[(on|off)\]')
        if len(before) != len(after):
            # more of an assertion - the lines diff should match
            return
        for b, a in zip(before, after):
            match_b = regex.search(b)
            match_a = regex.search(a)
            if match_b and match_a:
                vc.before = int(match_b.groups()[0])
                vc.after = int(match_a.groups()[0])
                vc.mute_before = match_b.groups()[1] == 'off'
                vc.mute_after = match_a.groups()[1] == 'off'
            return

    def check_terminal_hotkey(self):
        # spawn a terminal window using ctrl+alt+t
        # touch a unique temporary file, and check if it got created
        timestamp = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
        filename = os.path.join('/tmp/hotkey-testing-{}'.format(timestamp))
        self.kb.press_key(KeyCodes.KEY_T, {'ctrl', 'alt'})
        # wait for the terminal window to appear
        assert(not os.path.exists(filename))
        time.sleep(2)
        self.kb.type_text('touch {}'.format(filename))
        self.kb.press_key(KeyCodes.KEY_ENTER)
        for attempt_no in range(10):
            # let's wait some time to let X/terminal process the command
            time.sleep(0.5)
            if os.path.exists(filename):
                self.kb.press_key(KeyCodes.KEY_D, {'ctrl'})
                os.unlink(filename)
                return True
        else:
            self.kb.press_key(KeyCodes.KEY_D, {'ctrl'})
            return False

    def check_command_hotkey(self):
        timestamp = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
        filename = os.path.join('/tmp/hotkey-testing-cmd-{}'.format(timestamp))
        self.kb.press_key(KeyCodes.KEY_F2, {'alt'})
        assert(not os.path.exists(filename))
        time.sleep(2)
        self.kb.type_text('touch {}'.format(filename))
        self.kb.press_key(KeyCodes.KEY_ENTER)
        for attempt_no in range(10):
            # let's wait some time to let X/terminal process the command
            time.sleep(0.5)
            if os.path.exists(filename):
                os.unlink(filename)
                return True
        else:
            return False

    def check_media_play(self):
        cmd = "timeout 30 rhythmbox --debug 2> /tmp/media-key-test"
        self.kb.press_key(KeyCodes.KEY_T, {'ctrl', 'alt'})
        time.sleep(2)
        self.kb.type_text(cmd)
        self.kb.press_key(KeyCodes.KEY_ENTER)
        time.sleep(3)
        self.kb.press_key(KeyCodes.KEY_PLAYPAUSE)
        self.kb.press_key(KeyCodes.KEY_F4, {'alt'})
        time.sleep(1)
        self.kb.press_key(KeyCodes.KEY_D, {'ctrl'})
        with open('/tmp/media-key-test', 'rt') as f:
            output = f.read()
            return "got media key 'Play'" in output


def main():
    if not (os.geteuid() == 0):
        raise SystemExit('Must be run as root.')
    hkt = HotKeyTesting()
    failed = False
    for member in dir(hkt):
        attr = getattr(hkt, member)
        if not member.startswith('check_') or not callable(attr):
            continue
        print('{}... '.format(member), end='', flush=True)
        if not attr():
            print("FAIL")
            failed = True
        else:
            print("PASS")
    if failed:
        raise SystemExit('Some test failed!')


if __name__ == '__main__':
    main()
