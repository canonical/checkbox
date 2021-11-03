#
# This file is part of Checkbox.
#
# Copyright 2013-2020 Canonical Ltd.
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
from checkbox_support.snap_utils.system import in_classic_snap

TYPES = ("source", "sink")
DIRECTIONS = {"source": "input", "sink": "output"}

# use %s string format to compatible with other python version
default_pattern = "(?<=Default %s: ).*"
index_regex = re.compile("(?<=Sink Input #)[0-9]*")
muted_regex = re.compile("(?<=Mute: ).*")
name_regex = re.compile("(?<=Name:).*")
channel_map_regex = re.compile("(?<=Channel Map: ).*")

# use %s string format to compatible with other python version
entry_pattern = "Name: %s.*?(?=Properties)"
volume_pattern = r"Volume: .*(?:%s):[\w\/0-9 ]* ([0-9]*)%%"


def unlocalized_env(reset={"LANG": "POSIX.UTF-8"}):
    """
    Create un-localized environment.

    Produce an environment that is suitable for subprocess.Popen() and
    associated subprocess functions. The returned environment is equal to a
    copy the current environment, updated with the value of the reset argument.
    """
    env = dict(os.environ)
    env.update(reset)
    if in_classic_snap():
        prp = '/run/user/{}/snap.{}/../pulse'.format(
            os.geteuid(), os.getenv('SNAP_NAME'))
        env['PULSE_RUNTIME_PATH'] = prp
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
            if ('HDMI' in p.label) and (('DisplayPort' in p.label) or ('DP' in p.label))]
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
        profile = min([p for p in port.profile_list if ('stereo' in p) or ('Hdmi' in p)], key=len)
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
        logging.error("Failed setting audio output to:{}: {}".format(
                        profile, error))


def get_current_profiles_settings(profiles_file):
    """Captures and Writes current audio profiles settings"""
    pactl_list = check_output(
        ['pactl', 'list'], universal_newlines=True, env=unlocalized_env())

    config = configparser.ConfigParser()

    for match in re.finditer(
        r"(?P<card_id>Card #\d+)\n\tName:\s+(?P<card_name>.*?)\n.*?"
        r"Active\sProfile:\s+(?P<profile>.*?)\n", pactl_list, re.M | re.S
    ):
        config[match.group('card_id')] = {
            'name': match.group('card_name'),
            'profile': match.group('profile')
        }

    try:
        with open(profiles_file, 'w') as active_profiles:
            config.write(active_profiles)
    except IOError:
        logging.error("Failed to save active profiles information: {}".format(
                        sys.exc_info()[1]))


def restore_profiles_settings(profiles_file):
    config = configparser.ConfigParser()
    try:
        config.read(profiles_file)
    except IOError:
        logging.error("Failed to retrieve previous profiles information")

    for card in config.sections():
        try:
            check_call(["pactl", "set-card-profile", config[card]['name'],
                       config[card]['profile']])
        except CalledProcessError as error:
            logging.error(
                "Failed setting card <{}> profile to <{}>: {}".format(
                    config[card]['name'], config[card]['profile'], error))


def move_sinks(name):
    sink_inputs = check_output(["pactl", "list", "sink-inputs"],
                               universal_newlines=True,
                               env=unlocalized_env())
    input_indexes = index_regex.findall(sink_inputs)

    for input_index in input_indexes:
        try:
            with open(os.devnull, 'wb') as DEVNULL:
                check_call(["pactl", "move-sink-input", input_index, name],
                           stdout=DEVNULL)
        except CalledProcessError:
            logging.error("Failed to move input {} to sink {}".format(
                            input_index, name))
            sys.exit(1)


def get_audio_settings(type, name="default"):
    if name == "default":
        pactl_status = check_output(["pactl", "info"],
                                universal_newlines=True,
                                env=unlocalized_env())
        default_regex = re.compile(default_pattern % type.title())
        name = default_regex.search(pactl_status).group()

    pactl_list = check_output(["pactl", "list", "{}s".format(type)],
                              universal_newlines=True,
                              env=unlocalized_env())
    entry_regex = re.compile(entry_pattern % name, re.DOTALL)
    entry = entry_regex.search(pactl_list).group()

    muted = muted_regex.search(entry).group()

    volumes = {}
    max_volume = 0
    channels = channel_map_regex.search(entry).group()
    for channel in channels.split(","):
        volume_regex = re.compile(volume_pattern % channel, re.DOTALL)
        _volume = int(volume_regex.search(entry).group(1).strip())
        volumes.update({channel: _volume})
        max_volume = max(_volume, max_volume)

    return {
        "name": name,
        "muted": muted,
        "volumes": volumes,
        "max_volume": max_volume
    }


def store_audio_settings(file):
    logging.info("[ Saving audio settings ]".center(80, '='))
    try:
        settings_file = open(file, 'w')
    except IOError:
        logging.error("Failed to save settings: {}".format(sys.exc_info()[1]))
        sys.exit(1)

    for type in TYPES:
        audio_settings = get_audio_settings(type)
        print("default_{}: {}".format(type, audio_settings["name"]),
              file=settings_file)
        print("{}_muted: {}".format(type, audio_settings["muted"].strip()),
              file=settings_file)
        print("{}_volume: {}%".format(
                type, str(audio_settings["max_volume"])),
              file=settings_file)

    settings_file.close()


def set_audio_settings(device, mute, volume):
    for type in TYPES:
        pactl_entries = check_output(["pactl", "list", "{}s".format(type)],
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
                        check_call(["pactl",
                                    "set-default-{}".format(type),
                                    name],
                                   stdout=DEVNULL)
                except CalledProcessError:
                    logging.error("Failed to set default {}".format(type))
                    sys.exit(1)

                if type == "sink":
                    move_sinks(name)

                try:
                    check_call(["pactl",
                                "set-{}-mute".format(type),
                                name,
                                str(int(mute))])
                except:
                    logging.error("Failed to set mute for {}".format(name))
                    sys.exit(1)

                try:
                    check_call(["pactl", "set-{}-volume".format(type),
                               name, "{}%".format(str(volume))])
                except:
                    logging.error("Failed to set volume for {}".format(name))
                    sys.exit(1)


def restore_audio_settings(file):
    logging.info("[ Restoring audio settings ]".center(80, '='))
    try:
        with open(file) as f:
            settings_file = f.read().split()
    except IOError:
        logging.error("Unable to open existing settings file: {}".format(
                            sys.exc_info()[1]))
        return 1

    for type in TYPES:
        # First try to get the three elements we need.
        # If we fail to get any of them, it means the file's format
        # is incorrect, so we just abort.
        try:
            name = settings_file[
                settings_file.index("default_{}:".format(type)) + 1]
            muted = settings_file[
                settings_file.index("{}_muted:".format(type)) + 1]
            volume = settings_file[
                settings_file.index("{}_volume:".format(type)) + 1]
        except ValueError:
            logging.error("Unable to restore settings because settings "
                          "file is invalid")
            return 1

        try:
            with open(os.devnull, 'wb') as DEVNULL:
                check_call(["pactl", "set-default-{}".format(type), name],
                           stdout=DEVNULL)
        except CalledProcessError:
            logging.error("Failed to restore default {}".format(name))
            return 1

        if type == "sink":
            move_sinks(name)

        try:
            check_call(["pactl", "set-{}-mute".format(type), name, muted])
        except:
            logging.error("Failed to restore mute for {}".format(name))
            return 1

        try:
            check_call(["pactl", "set-{}-volume".format(type), name, volume])
        except:
            logging.error("Failed to restore volume for {}".format(name))
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

    # Settings and profiles need to be stored separately
    if args.action in ['store', 'restore']:
        if not args.file:
            logging.error("No file specified to store audio settings!")
            return 1
        settings_file = args.file
        profiles_file = "{}.profiles".format(args.file)

    if args.verbose:
        logging.basicConfig(format='%(levelname)s:%(message)s',
                            level=logging.INFO, stream=sys.stdout)
    if args.action == "store":
        store_audio_settings(settings_file)
        get_current_profiles_settings(profiles_file)
    elif args.action == "restore":
        if (restore_profiles_settings(profiles_file) or
                restore_audio_settings(settings_file)):
            return 1
    elif args.action == "set":
        if not args.device:
            logging.error("No device specified to change settings of!")
            return 1
        if args.volume is None:
            logging.error("No volume level specified!")
            return 1

        if args.device == "hdmi":
            set_profile_hdmi()
        set_audio_settings(args.device, args.mute, args.volume)
    else:
        logging.error("{} is not a valid action".format(args.action))
        return 1

    return 0
