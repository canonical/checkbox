#
# This file is part of Checkbox.
#
# Copyright 2013 Canonical Ltd.
#
# Checkbox is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3,
# as published by the Free Software Foundation.

#
# Checkbox is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Checkbox.  If not, see <http://www.gnu.org/licenses/>.

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

from argparse import ArgumentParser
from subprocess import check_output, check_call, CalledProcessError
from io import open
import configparser
import logging
import os
import re
import sys

from checkbox_support.parsers.pactl import parse_pactl_output

TYPES = ("source", "sink")
DIRECTIONS = {"source": "input", "sink": "output"}

default_pattern = "(?<=Default %s: ).*"
index_regex = re.compile("(?<=index: )[0-9]*")
muted_regex = re.compile("(?<=Mute: ).*")
volume_regex = re.compile("(?<=Volume: 0:)\s*[0-9]*")
name_regex = re.compile("(?<=Name:).*")

entry_pattern = "Name: %s.*?(?=Properties)"


def unlocalized_env(reset={"LANG": "POSIX.UTF-8"}):
    """
    Create un-localized environment.

    Produce an environment that is suitable for subprocess.Popen() and
    associated subprocess functions. The returned environment is equal to a
    copy the current environment, updated with the value of the reset argument.
    """
    env = dict(os.environ)
    env.update(reset)
    return env


def _guess_hdmi_profile(pactl_list):
    """
    Use the pactl parser to get the stereo profile of the available HDMI port

    :returns: (card, profile)
    """
    hdmi_ports = {}
    available_port = {}
    port_status_location = 'Sink'

    # First parse all cards for HDMI / DisplayPort ports
    for record in parse_pactl_output(pactl_list).record_list:
        if not 'Card' in record.name:
            continue
        card = re.sub('.*#', '', record.name)  # save the card id
        ports = [
            p for p in record.attribute_map['Ports'].value
            if 'HDMI / DisplayPort' in p.label]
        if not ports:
            continue
        if [p for p in ports if p.availability]:
            port_status_location = 'Card'
        hdmi_ports[card] = ports

    if not hdmi_ports:
        return (None, None)

    logging.info("[ HDMI / DisplayPort ports ]".center(80, '='))
    for card, ports in hdmi_ports.items():
        for card_port in ports:
            logging.info("Card #{} Port: {}".format(card, card_port))

    # Check the ports availability in the list of pulseaudio sinks
    # if the status is not already available in the cards section.
    def check_available_port():
        match_found = False
        for record in parse_pactl_output(pactl_list).record_list:
            if not port_status_location in record.name:
                continue
            for sink_port in record.attribute_map['Ports'].value:
                for card, ports in hdmi_ports.items():
                    for card_port in ports:
                        if sink_port.label == card_port.label:
                            match_found = True
                            if sink_port.availability != 'not available':
                                return {card: card_port}
        # If the availability cannot be determined then we keep the first
        # candidate
        if not match_found and hdmi_ports:
            card, ports = hdmi_ports.popitem()
            return {card: ports.pop()}

    available_port = check_available_port()

    if available_port:
        card, port = available_port.popitem()
        # Keep the shortest string in the profile_list including 'stereo'
        # it will avoid testing 'surround' profiles
        profile = min([p for p in port.profile_list if 'stereo' in p], key=len)
        logging.info("[ Selected profile ]".center(80, '='))
        logging.info("Card #{} Profile: {}".format(card, profile))
        return (card, profile)
    else:
        return (None, None)


def set_profile_hdmi():
    """Sets desired device as active profile. This is typically
    used as a fallback for setting HDMI / DisplayPort as the output device.
    """
    pactl_list = check_output(
        ['pactl', 'list'], universal_newlines=True, env=unlocalized_env())

    card, profile = _guess_hdmi_profile(pactl_list)
    if not profile:
        logging.error('No available port found')
        return 1

    # Try and set device as default audio output
    try:
        check_call(["pactl", "set-card-profile", card, profile])
    except CalledProcessError as error:
        logging.error("Failed setting audio output to:%s: %s" %
                      (profile, error))


def get_current_profiles_settings():
    """Captures and Writes current audio profiles settings"""
    pactl_list = check_output(
        ['pactl', 'list'], universal_newlines=True, env=unlocalized_env())

    config = configparser.ConfigParser()

    for match in re.finditer(
        "(?P<card_id>Card #\d+)\n\tName:\s+(?P<card_name>.*?)\n.*?"
        "Active\sProfile:\s+(?P<profile>.*?)\n", pactl_list, re.M | re.S
    ):
        config[match.group('card_id')] = {
            'name': match.group('card_name'),
            'profile': match.group('profile')
        }

    try:
        with open('active_profiles', 'w') as active_profiles:
            config.write(active_profiles)
    except IOError:
        logging.error("Failed to save active profiles information: %s" %
                      sys.exc_info()[1])


def restore_profiles_settings():
    config = configparser.ConfigParser()
    try:
        config.read('active_profiles')
    except IOError:
        logging.error("Failed to retrieve previous profiles information")

    for card in config.sections():
        try:
            check_call(["pactl", "set-card-profile", config[card]['name'],
                       config[card]['profile']])
        except CalledProcessError as error:
            logging.error("Failed setting card <%s> profile to <%s>: %s" %
                          (config[card]['name'],
                           config[card]['profile'], error))


def move_sinks(name):
    sink_inputs = check_output(["pacmd", "list-sink-inputs"],
                               universal_newlines=True,
                               env=unlocalized_env())
    input_indexes = index_regex.findall(sink_inputs)

    for input_index in input_indexes:
        try:
            with open(os.devnull, 'wb') as DEVNULL:
                check_call(["pacmd", "move-sink-input", input_index, name],
                           stdout=DEVNULL)
        except CalledProcessError:
            logging.error("Failed to move input %d to sink %d" %
                          (input_index, name))
            sys.exit(1)


def store_audio_settings(file):
    logging.info("[ Saving audio settings ]".center(80, '='))
    try:
        settings_file = open(file, 'w')
    except IOError:
        logging.error("Failed to save settings: %s" % sys.exc_info()[1])
        sys.exit(1)

    for type in TYPES:
        pactl_status = check_output(["pactl", "stat"],
                                    universal_newlines=True,
                                    env=unlocalized_env())
        default_regex = re.compile(default_pattern % type.title())
        default = default_regex.search(pactl_status).group()

        print("default_%s: %s" % (type, default), file=settings_file)

        pactl_list = check_output(["pactl", "list", type + 's'],
                                  universal_newlines=True,
                                  env=unlocalized_env())

        entry_regex = re.compile(entry_pattern % default, re.DOTALL)
        entry = entry_regex.search(pactl_list).group()

        muted = muted_regex.search(entry)
        print("%s_muted: %s" % (type, muted.group().strip()),
              file=settings_file)

        volume = int(volume_regex.search(entry).group().strip())

        print("%s_volume: %s%%" % (type, str(volume)),
              file=settings_file)
    settings_file.close()


def set_audio_settings(device, mute, volume):
    for type in TYPES:
        pactl_entries = check_output(["pactl", "list", type + 's'],
                                     universal_newlines=True,
                                     env=unlocalized_env())

        # Find the name of the sink/source we want to set
        names = name_regex.findall(pactl_entries)

        for name in names:
            name = name.strip()
            if device in name and DIRECTIONS[type] in name:
                try:
                    logging.info("[ Fallback sink ]".center(80, '='))
                    logging.info("Name: {}".format(name))
                    with open(os.devnull, 'wb') as DEVNULL:
                        check_call(["pacmd", "set-default-%s" % type, name],
                                   stdout=DEVNULL)
                except CalledProcessError:
                    logging.error("Failed to set default %s" % type)
                    sys.exit(1)

                if type == "sink":
                    move_sinks(name)

                try:
                    check_call(["pactl",
                                "set-%s-mute" % type, name, str(int(mute))])
                except:
                    logging.error("Failed to set mute for %s" % name)
                    sys.exit(1)

                try:
                    check_call(["pactl", "set-%s-volume" % type,
                               name, str(volume) + '%'])
                except:
                    logging.error("Failed to set volume for %s" % name)
                    sys.exit(1)


def restore_audio_settings(file):
    logging.info("[ Restoring audio settings ]".center(80, '='))
    try:
        with open(file) as f:
            settings_file = f.read().split()
    except IOError:
        logging.error("Unable to open existing settings file: %s" %
                      sys.exc_info()[1])
        return 1

    for type in TYPES:
        # First try to get the three elements we need.
        # If we fail to get any of them, it means the file's format
        # is incorrect, so we just abort.
        try:
            name = settings_file[
                settings_file.index("default_%s:" % type) + 1]
            muted = settings_file[settings_file.index("%s_muted:" % type) + 1]
            volume = settings_file[
                settings_file.index("%s_volume:" % type) + 1]
        except ValueError:
            logging.error("Unable to restore settings because settings "
                          "file is invalid")
            return 1

        try:
            with open(os.devnull, 'wb') as DEVNULL:
                check_call(["pacmd", "set-default-%s" % type, name],
                           stdout=DEVNULL)
        except CalledProcessError:
            logging.error("Failed to restore default %s" % name)
            return 1

        if type == "sink":
            move_sinks(name)

        try:
            check_call(["pactl", "set-%s-mute" % type, name, muted])
        except:
            logging.error("Failed to restore mute for %s" % name)
            return 1

        try:
            check_call(["pactl", "set-%s-volume" % type, name, volume])
        except:
            logging.error("Failed to restore volume for %s" % name)
            return 1


def main():
    parser = ArgumentParser("Manipulate PulseAudio settings")
    parser.add_argument("action",
                        choices=['store', 'set', 'restore'],
                        help="Action to perform with the audio settings")
    parser.add_argument("-d", "--device",
                        help="The device to apply the new settings to.")
    parser.add_argument("-m", "--mute",
                        action="store_true",
                        help="""The new value for the mute setting
                                of the specified device.""")
    parser.add_argument("-v", "--volume",
                        type=int,
                        help="""The new value for the volume setting
                                of the specified device.""")
    parser.add_argument("-f", "--file",
                        help="""The file to store settings in or restore
                                settings from.""")
    parser.add_argument("--verbose",
                        action='store_true',
                        help="Turn on verbosity")
    args = parser.parse_args()

    if args.verbose:
        logging.basicConfig(format='%(levelname)s:%(message)s',
                            level=logging.INFO, stream=sys.stdout)
    if args.action == "store":
        if not args.file:
            logging.error("No file specified to store audio settings!")
            return 1

        store_audio_settings(args.file)
        get_current_profiles_settings()
    elif args.action == "set":
        if not args.device:
            logging.error("No device specified to change settings of!")
            return 1
        if not args.volume:
            logging.error("No volume level specified!")
            return 1

        if args.device == "hdmi":
            set_profile_hdmi()
        set_audio_settings(args.device, args.mute, args.volume)
    elif args.action == "restore":
        if restore_profiles_settings() or restore_audio_settings(args.file):
            return 1
    else:
        logging.error(args.action + "is not a valid action")
        return 1

    return 0
