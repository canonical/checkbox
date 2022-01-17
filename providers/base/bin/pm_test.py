#!/usr/bin/env python3
"""
If you're debugging this program, set PM_TEST_DRY_RUN in your environment.
It will make the script not run actual S3, S4, reboot and poweroff commands.
"""
import gi
import json
import logging
import logging.handlers
import os
import pwd
import re
import shutil
import signal
import subprocess
import sys
from argparse import ArgumentParser, SUPPRESS
from calendar import timegm
from configparser import ConfigParser
from datetime import datetime, timedelta
from time import localtime, time
gi.require_version("Gtk", "3.0")
from gi.repository import GObject, Gtk  # noqa: E402


def main():
    """
    Run power management operation as many times as needed
    """
    args, extra_args = MyArgumentParser().parse()

    # Verify that script is run as root
    if os.getuid():
        sys.stderr.write('This script needs superuser '
                         'permissions to run correctly\n')
        sys.exit(1)

    # Obtain name of the invoking user.
    username = os.getenv('NORMAL_USER')
    if not username:
        uid = os.getenv('SUDO_UID') or os.getenv('PKEXEC_UID')
        if not uid:
            sys.stderr.write('Unable to determine invoking user\n')
            sys.exit(1)
        username = pwd.getpwuid(int(uid)).pw_name

    LoggingConfiguration.set(args.log_level, args.log_filename, args.append)
    logging.debug('Invoking username: %s', username)
    logging.debug('Arguments: {0!r}'.format(args))
    logging.debug('Extra Arguments: {0!r}'.format(extra_args))

    dry_run = os.environ.get('PM_TEST_DRY_RUN', False)
    if dry_run:
        logging.info("Running in dry-run mode")

    try:
        operation = PowerManagementOperation(
            args, extra_args, user=username, dry_run=dry_run)
        operation.setup()
        operation.run()
    except (TestCancelled, TestFailed) as exception:
        if isinstance(exception, TestFailed):
            logging.error(exception.args[0])
        message = exception.MESSAGE.format(args.pm_operation.capitalize())
        if args.silent:
            logging.info(message)
        else:
            title = '{0} test'.format(args.pm_operation.capitalize())
            MessageDialog(title, message, Gtk.MessageType.ERROR).run()
        operation.teardown()
        result = {
            'outcome': 'fail',
            'comments': message,
        }
        with open(os.path.join(args.log_dir, '__result'), 'wt') as f:
            json.dump(result, f)
        env = os.environ.copy()
        # remove following envvars
        for key in ['LD_LIBRARY_PATH', 'PYTHONPATH', 'PYTHONHOME']:
            if key in env.keys():
                del env[key]
        env['DISPLAY'] = ':0'
        sudo_cmd = 'sudo -u {} bash -c "source {}; exec bash"'.format(
            operation.user, args.checkbox_respawn_cmd)
        args = ['x-terminal-emulator', '-e', sudo_cmd]
        print("\nCheckbox will resume in another window.")
        print("It's safe to close this one.", flush=True)
        os.execvpe('x-terminal-emulator', args, env)

    return 0


class PowerManagementOperation():
    SLEEP_TIME = 5

    def __init__(self, args, extra_args, user=None, dry_run=False):
        self.args = args
        self.extra_args = extra_args
        self.user = user
        self.dry_run = dry_run
        self.hw_list_start = os.path.join(
            self.args.log_dir, 'hardware.at_start')

    def setup(self):
        """
        Enable configuration file
        """
        if self.args.check_hardware_list:
            if not os.path.exists(self.hw_list_start):
                # create baseline list once per session
                with open(self.hw_list_start, 'wt') as f:
                    f.write(self.get_hw_list())

        # Enable autologin and sudo on first cycle
        if self.args.total == self.args.repetitions:
            AutoLoginConfigurator(user=self.user).enable()
            SudoersConfigurator(user=self.user).enable()

        # Schedule this script to be automatically executed
        # on startup to continue testing
        autostart_file = AutoStartFile(self.args, user=self.user)
        autostart_file.write()

    def run(self):
        """
        Run a power management iteration
        """
        logging.info('{0} operations remaining: {1}'
                     .format(self.args.pm_operation, self.args.repetitions))
        if self.args.pm_timestamp:
            pm_timestamp = datetime.fromtimestamp(self.args.pm_timestamp)
            now = datetime.now()
            pm_time = now - pm_timestamp
            logging.info('{0} time: {1}'
                         .format(self.args.pm_operation.capitalize(), pm_time))
        if self.args.repetitions > 0:
            self.run_suspend_cycles(self.args.suspends_before_reboot,
                                    self.args.fwts)
            self.run_pm_command()
            if self.args.check_hardware_list:
                self.check_hw_list()
        else:
            self.summary()

    def run_pm_command(self):
        """
        Run power managment command and check result if needed
        """
        # Display information to user
        # and make it possible to cancel the test
        CountdownDialog(self.args.pm_operation,
                        self.args.pm_delay,
                        self.args.hardware_delay,
                        self.args.total - self.args.repetitions,
                        self.args.total).run()

        # A small sleep time is added to reboot and poweroff
        # so that script has time to return a value
        # (useful when running it as an automated test)
        command_str = ('sleep {0}; {1}'
                       .format(self.SLEEP_TIME, self.args.pm_operation))
        if self.extra_args:
            command_str += ' {0}'.format(' '.join(self.extra_args))

        if self.args.pm_operation != 'reboot':
            WakeUpAlarm.set(seconds=self.args.wakeup)

        logging.info('Executing new {0!r} operation...'
                     .format(self.args.pm_operation))
        logging.debug('Executing: {0!r}...'.format(command_str))
        if self.dry_run:
            print("\n\nRUNNING IN DRY-RUN MODE")
            print("Normally the program would run: {}".format(command_str))
            print("Waiting for Enter instead")
            input()
        else:
            # The PM operation is performed asynchronously so let's just wait
            # indefinitely until it happens and someone comes along to kill us.
            # This addresses LP: #1413134
            subprocess.check_call(command_str, shell=True)
            signal.pause()

    def run_suspend_cycles(self, cycles_count, fwts):
        """Run suspend and resume cycles."""
        if cycles_count < 1:
            return
        script_path = ''
        if fwts:
            script_path = 'checkbox-support-fwts_test'
            command_tpl = '-s s3 --s3-device-check ' \
                          '--s3-sleep-delay=30 --s3-multiple={}'
            if self.args.log_dir:
                command_tpl = '--log={}/fwts.log '.format(
                    self.args.log_dir) + command_tpl
            command_tpl = '{} ' + command_tpl
        else:
            script_name = 'sleep_test.py'
            command_tpl = '{} -s mem -p -i {} -w 10'
            script_path = os.path.join(
                os.path.dirname(os.path.realpath(__file__)), script_name)
        command_str = command_tpl.format(script_path, cycles_count)
        logging.info('Running suspend/resume cycles')
        logging.debug('Executing: {0!r}...'.format(command_str))
        if self.dry_run:
            print("\n\nRUNNING IN DRY-RUN MODE")
            print("Normally the program would run: {}".format(command_str))
            print("Waiting for Enter instead")
            input()
        else:
            try:
                # We call sleep_test.py or fwts_test script and log its output
                # as it contains average times we need to compute global
                # average times later.
                logging.info(subprocess.check_output(
                    command_str, universal_newlines=True, shell=True))
            except subprocess.CalledProcessError as e:
                logging.error('Error while running {0}:'.format(e.cmd))
                logging.error(e.output)

    def summary(self):
        """
        Gather hardware information for the last time,
        log execution time and exit
        """
        # Just gather hardware information one more time and exit
        CountdownDialog(self.args.pm_operation,
                        self.args.pm_delay,
                        self.args.hardware_delay,
                        self.args.total - self.args.repetitions,
                        self.args.total).run()

        self.teardown()

        # Log some time information
        start = datetime.fromtimestamp(self.args.start)
        end = datetime.now()
        if self.args.pm_operation == 'reboot':
            sleep_time = timedelta(seconds=self.SLEEP_TIME)
        else:
            sleep_time = timedelta(seconds=self.args.wakeup)

        wait_time = timedelta(seconds=(self.args.pm_delay +
                                       self.args.hardware_delay *
                                       self.args.total))
        average = (end - start - wait_time) / self.args.total - sleep_time
        time_message = ('Total elapsed time: {total}\n'
                        'Average recovery time: {average}'
                        .format(total=end - start,
                                average=average))
        logging.info(time_message)

        message = ('{0} test complete'
                   .format(self.args.pm_operation.capitalize()))
        if self.args.suspends_before_reboot:
            total_suspends_expected = (
                self.args.suspends_before_reboot * self.args.total)
            problems = ''
            fwts_log_path = os.path.join(self.args.log_dir, 'fwts.log')
            try:
                with open(fwts_log_path, 'rt') as f:
                    magic_line_s3 = 'Completed S3 cycle(s) \n'
                    magic_line_s2idle = 'Completed s2idle cycle(s) \n'
                    lines = f.readlines()
                    count_s3 = lines.count(magic_line_s3)
                    count_s2idle = lines.count(magic_line_s2idle)
                    count = count_s3 + count_s2idle
                    if count != total_suspends_expected:
                        problems = (
                            "Found {} occurrences of S3/S2idle."
                            " Expected {}".format(
                                count, total_suspends_expected))
            except FileNotFoundError:
                problems = "Error opening {}".format(fwts_log_path)
            if problems:
                result = {
                    'outcome': 'fail' if problems else 'pass',
                    'comments': problems,
                }
                result_filename = os.path.join(self.args.log_dir, '__result')
                with open(result_filename, 'wt') as f:
                    json.dump(result, f)

        if self.args.silent:
            logging.info(message)
        else:
            title = '{0} test'.format(self.args.pm_operation.capitalize())
            MessageDialog(title, message).run()
        if self.args.checkbox_respawn_cmd:
            subprocess.run(
                r'unset LD_LIBRARY_PATH;'
                r'unset PYTHONPATH; unset PYTHONHOME;'
                r'DISPLAY=:0 x-terminal-emulator -e "sudo -u '
                r'{} bash -c \"source {}; exec bash\""'.format(
                    self.user, self.args.checkbox_respawn_cmd), shell=True)

    def teardown(self):
        """
        Restore configuration
        """
        # Don't execute this script again on next reboot
        autostart_file = AutoStartFile(self.args, user=self.user)
        autostart_file.remove()

        # Restore previous configuration
        SudoersConfigurator().disable()
        AutoLoginConfigurator().disable()

    def get_hw_list(self):
        try:
            content = subprocess.check_output(
                'lspci', encoding=sys.stdout.encoding)
            content += subprocess.check_output(
                'lsusb', encoding=sys.stdout.encoding)
            return content
        except subprocess.CalledProcessError as exc:
            logging.warning("Problem running lspci or lsusb: %s", exc)
            return ''

    def check_hw_list(self):
        with open(self.hw_list_start, 'rt') as f:
            before = set(f.read().split('\n'))
        after = set(self.get_hw_list().split('\n'))
        if after != before:
            message = "Hardware changed!"
            only_before = before - after
            if only_before:
                message += "\nHardware lost after pm operation:"
                for item in sorted(list(only_before)):
                    message += '\n\t{}'.format(item)
            only_after = after - before
            if only_after:
                message += "\nNew hardware found after pm operation:"
                for item in sorted(list(only_after)):
                    message += '\n\t{}'.format(item)
            raise TestFailed(message)


class TestCancelled(Exception):
    RETURN_CODE = 1
    MESSAGE = '{0} test cancelled by user'


class TestFailed(Exception):
    RETURN_CODE = 2
    MESSAGE = '{0} test failed'


class WakeUpAlarm():
    ALARM_FILENAME = '/sys/class/rtc/rtc0/wakealarm'
    RTC_FILENAME = '/proc/driver/rtc'

    @classmethod
    def set(cls, minutes=0, seconds=0):
        """
        Calculate wakeup time and write it to BIOS
        """
        now = int(time())
        timeout = minutes * 60 + seconds
        wakeup_time_utc = now + timeout
        wakeup_time_local = timegm(localtime()) + timeout

        subprocess.check_call('echo 0 > %s' % cls.ALARM_FILENAME, shell=True)
        subprocess.check_call('echo %d > %s'
                              % (wakeup_time_utc, cls.ALARM_FILENAME),
                              shell=True)

        with open(cls.ALARM_FILENAME) as alarm_file:
            wakeup_time_stored_str = alarm_file.read()

            if not re.match(r'\d+', wakeup_time_stored_str):
                subprocess.check_call('echo "+%d" > %s'
                                      % (timeout, cls.ALARM_FILENAME),
                                      shell=True)
                with open(cls.ALARM_FILENAME) as alarm_file2:
                    wakeup_time_stored_str = alarm_file2.read()
                if not re.match(r'\d+', wakeup_time_stored_str):
                    logging.error('Invalid wakeup time format: {0!r}'
                                  .format(wakeup_time_stored_str))
                    sys.exit(1)

            wakeup_time_stored = int(wakeup_time_stored_str)
            try:
                logging.debug('Wakeup timestamp: {0} ({1})'
                              .format(wakeup_time_stored,
                                      datetime.fromtimestamp(
                                          wakeup_time_stored).strftime('%c')))
            except ValueError as e:
                logging.error(e)
                sys.exit(1)

            if (
                (abs(wakeup_time_utc - wakeup_time_stored) > 1) and
                (abs(wakeup_time_local - wakeup_time_stored) > 1)
            ):
                logging.error('Wakeup time not stored correctly')
                sys.exit(1)

        with open(cls.RTC_FILENAME) as rtc_file:
            separator_regex = re.compile(r'\s+:\s+')
            rtc_data = dict([separator_regex.split(line.rstrip())
                             for line in rtc_file])
            logging.debug('RTC data:\n{0}'
                          .format('\n'.join(['- {0}: {1}'.format(*pair)
                                             for pair in rtc_data.items()])))

            # Verify wakeup time has been set properly
            # by looking into the alarm_IRQ and alrm_date field
            if rtc_data['alarm_IRQ'] != 'yes':
                logging.error('alarm_IRQ not set properly: {0}'
                              .format(rtc_data['alarm_IRQ']))
                sys.exit(1)

            if '*' in rtc_data['alrm_date']:
                logging.error('alrm_date not set properly: {0}'
                              .format(rtc_data['alrm_date']))
                sys.exit(1)


class Command():
    """
    Simple subprocess.Popen wrapper to run shell commands
    and log their output
    """
    def __init__(self, command_str, verbose=True):
        self.command_str = command_str
        self.verbose = verbose

        self.process = None
        self.stdout = None
        self.stderr = None
        self.time = None

    def run(self):
        """
        Execute shell command and return output and status
        """
        logging.debug('Executing: {0!r}...'.format(self.command_str))

        self.process = subprocess.Popen(self.command_str,
                                        shell=True,
                                        stdout=subprocess.PIPE,
                                        stderr=subprocess.PIPE)
        start = datetime.now()
        result = self.process.communicate()
        end = datetime.now()
        self.time = end - start

        if self.verbose:
            stdout, stderr = result
            message = ['Output:\n'
                       '- returncode:\n{0}'.format(self.process.returncode)]
            if stdout:
                if type(stdout) is bytes:
                    stdout = stdout.decode('utf-8', 'ignore')
                message.append('- stdout:\n{0}'.format(stdout))
            if stderr:
                if type(stderr) is bytes:
                    stderr = stderr.decode('utf-8', 'ignore')
                message.append('- stderr:\n{0}'.format(stderr))
            logging.debug('\n'.join(message))

            self.stdout = stdout
            self.stderr = stderr

        return self


class CountdownDialog(Gtk.Dialog):
    """
    Dialog that shows the amount of progress in the reboot test
    and lets the user cancel it if needed
    """
    def __init__(self, pm_operation, pm_delay, hardware_delay,
                 iterations, iterations_count):
        self.pm_operation = pm_operation
        title = '{0} test'.format(pm_operation.capitalize())

        buttons = (Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,)
        super(CountdownDialog, self).__init__(title=title,
                                              buttons=buttons)
        self.set_default_response(Gtk.ResponseType.CANCEL)
        self.set_resizable(False)
        self.set_position(Gtk.WindowPosition.CENTER)

        progress_bar = Gtk.ProgressBar()
        progress_bar.set_fraction(iterations / float(iterations_count))
        progress_bar.set_text('{0}/{1}'
                              .format(iterations, iterations_count))
        progress_bar.set_show_text(True)
        self.vbox.pack_start(progress_bar, True, True, 0)

        operation_event = {'template': ('Next {0} in {{time}} seconds...'
                                        .format(self.pm_operation)),
                           'timeout': pm_delay}
        hardware_info_event = \
            {'template': 'Gathering hardware information in {time} seconds...',
             'timeout': hardware_delay,
             'callback': self.on_hardware_info_timeout_cb}
        system_info_event = \
            {'template': 'Gathering system information in {time} seconds...',
             'timeout': 2,
             'callback': self.on_system_info_timeout_cb}

        if iterations == 0:
            # In first iteration, gather hardware and system  information
            # directly and perform pm-operation
            self.on_hardware_info_timeout_cb()
            self.on_system_info_timeout_cb()
            self.events = [operation_event]
        elif iterations < iterations_count:
            # In last iteration, wait before gathering hardware information
            # and perform pm-operation
            self.events = [operation_event,
                           hardware_info_event,
                           system_info_event]
        else:
            # In last iteration, wait before gathering hardware information
            # and finish the test
            self.events = [hardware_info_event, system_info_event]

        self.label = Gtk.Label()
        self.vbox.pack_start(self.label, True, True, 0)
        self.show_all()

    def run(self):
        """
        Set label text and run dialog
        """
        self.schedule_next_event()
        response = super(CountdownDialog, self).run()
        self.destroy()

        if response != Gtk.ResponseType.ACCEPT:
            raise TestCancelled()

    def schedule_next_event(self):
        """
        Schedule next timed event
        """
        if self.events:
            self.event = self.events.pop()
            self.timeout_counter = self.event.get('timeout', 0)
            self.label.set_text(self.event['template']
                                .format(time=self.timeout_counter))
            GObject.timeout_add_seconds(1, self.on_timeout_cb)
        else:
            # Return Accept response
            # if there are no other events scheduled
            self.response(Gtk.ResponseType.ACCEPT)

    def on_timeout_cb(self):
        """
        Set label properly and use callback method if needed
        """
        if self.timeout_counter > 0:
            self.label.set_text(self.event['template']
                                .format(time=self.timeout_counter))
            self.timeout_counter -= 1
            return True

        # Call calback if defined
        callback = self.event.get('callback')
        if callback:
            callback()

        # Schedule next event if needed
        self.schedule_next_event()

        return False

    def on_hardware_info_timeout_cb(self):
        """
        Gather hardware information and print it to logs
        """
        logging.info('Gathering hardware information...')
        logging.debug('Networking:\n'
                      '{network}\n'
                      '{ethernet}\n'
                      '{ifconfig}\n'
                      '{iwconfig}'
                      .format(network=(Command('lspci | grep Network')
                                       .run().stdout),
                              ethernet=(Command('lspci | grep Ethernet')
                                        .run().stdout),
                              ifconfig=(Command(
                                        r"ifconfig -a | grep -A1 '^\w'")
                                        .run().stdout),
                              iwconfig=(Command(r"iwconfig | grep -A1 '^\w'")
                                        .run().stdout)))
        logging.debug('Bluetooth Device:\n'
                      '{hciconfig}'
                      .format(hciconfig=(Command(r"hciconfig -a "
                                                 r"| grep -A2 '^\w'")
                                         .run().stdout)))
        logging.debug('Video Card:\n'
                      '{lspci}'
                      .format(lspci=Command('lspci | grep VGA').run().stdout))
        logging.debug('Touchpad and Keyboard:\n'
                      '{xinput}'
                      .format(xinput=Command(
                          'xinput list --name-only | sort').run().stdout))
        logging.debug('Pulse Audio Sink:\n'
                      '{pactl_sink}'
                      .format(pactl_sink=(Command('pactl list | grep Sink')
                                          .run().stdout)))
        logging.debug('Pulse Audio Source:\n'
                      '{pactl_source}'
                      .format(pactl_source=(Command('pactl list | grep Source')
                                            .run().stdout)))

        # Check kernel logs using firmware test suite
        command = Command('fwts -r stdout klog oops').run()
        if command.process.returncode != 0:
            # Don't abort the test loop,
            # errors can be retrieved by pm_log_check.py
            logging.error('Problem found in logs by fwts')

    def on_system_info_timeout_cb(self):
        """
        Gather system information and print it to logs
        """
        logging.info('Gathering system information...')
        # FIXME: Commented out as it created huge log files
        # during stress tests.
        # logging.debug('--- beginning of dmesg ---')
        # logging.debug(Command('dmesg').run().stdout)
        # logging.debug('--- end of dmesg ---')
        # logging.debug('--- beginning of syslog ---')
        # logging.debug(Command('cat /var/log/syslog').run().stdout)
        # logging.debug('--- end of syslog ---')


class MessageDialog():
    """
    Simple wrapper aroung Gtk.MessageDialog
    """
    def __init__(self, title, message, type=Gtk.MessageType.INFO):
        self.title = title
        self.message = message
        self.type = type

    def run(self):
        dialog = Gtk.MessageDialog(buttons=Gtk.ButtonsType.OK,
                                   message_format=self.message,
                                   type=self.type)
        logging.info(self.message)
        dialog.set_title(self.title)
        dialog.run()
        dialog.destroy()


class AutoLoginConfigurator():
    """
    Enable/disable autologin configuration
    to make sure that reboot test will work properly
    """
    def __init__(self, user=None):
        self.user = user
        self.config_filename = '/etc/lightdm/lightdm.conf'
        self.template = """
[SeatDefaults]
greeter-session=unity-greeter
user-session=ubuntu
autologin-user={username}
autologin-user-timeout=0
"""
        if os.path.exists('/etc/gdm3/custom.conf'):
            self.config_filename = '/etc/gdm3/custom.conf'
            self.parser = ConfigParser()
            self.parser.optionxform = str
            self.parser.read(self.config_filename)
            self.parser.set('daemon', 'AutomaticLoginEnable', 'True')
            if self.user:
                self.parser.set('daemon', 'AutomaticLogin', self.user)

    def enable(self):
        """
        Make sure user will autologin in next reboot
        """
        logging.debug('Enabling autologin for this user...')
        if os.path.exists(self.config_filename):
            for backup_filename in self.generate_backup_filename():
                if not os.path.exists(backup_filename):
                    shutil.copyfile(self.config_filename, backup_filename)
                    shutil.copystat(self.config_filename, backup_filename)
                    break

        with open(self.config_filename, 'w') as f:
            if self.config_filename == '/etc/lightdm/lightdm.conf':
                f.write(self.template.format(username=self.user))
            elif self.config_filename == '/etc/gdm3/custom.conf':
                self.parser.write(f)

    def disable(self):
        """
        Remove latest configuration file
        and use the same configuration that was in place
        before running the test
        """
        logging.debug('Restoring autologin configuration...')
        backup_filename = None
        for filename in self.generate_backup_filename():
            if not os.path.exists(filename):
                break
            backup_filename = filename

        if backup_filename:
            shutil.copy(backup_filename, self.config_filename)
            os.remove(backup_filename)
        else:
            os.remove(self.config_filename)

    def generate_backup_filename(self):
        backup_filename = self.config_filename + '.bak'
        yield backup_filename

        index = 0
        while True:
            index += 1
            backup_filename = (self.config_filename +
                               '.bak.{0}'.format(index))
            yield backup_filename


class SudoersConfigurator():
    """
    Enable/disable reboot test to be executed as root
    to make sure that reboot test works properly
    """
    MARK = '# Automatically added by pm.py'
    SUDOERS = '/etc/sudoers'

    def __init__(self, user=None):
        self.user = user

    def enable(self):
        """
        Make sure that user will be allowed to execute reboot test as root
        """
        logging.debug('Enabling user to execute test as root...')
        command = ("sed -i -e '$a{mark}\\n"
                   "{user} ALL=NOPASSWD: /usr/bin/python3' "
                   "{filename}".format(mark=self.MARK,
                                       user=self.user,
                                       script=os.path.realpath(__file__),
                                       filename=self.SUDOERS))

        Command(command, verbose=False).run()

    def disable(self):
        """
        Revert sudoers configuration changes
        """
        logging.debug('Restoring sudoers configuration...')
        command = (("sed -i -e '/{mark}/,+1d' "
                    "{filename}")
                   .format(mark=self.MARK,
                           filename=self.SUDOERS))
        Command(command, verbose=False).run()


class AutoStartFile():
    """
    Generate autostart file contents and write it to proper location
    """
    TEMPLATE = """
[Desktop Entry]
Name={pm_operation} test
Comment=Verify {pm_operation} works properly
Exec=sudo {script} -r {repetitions} -w {wakeup} --hardware-delay {hardware_delay} --pm-delay {pm_delay} --min-pm-time {min_pm_time} --max-pm-time {max_pm_time} --append --total {total} --start {start} --pm-timestamp {pm_timestamp} {silent} --log-level={log_level} --log-dir={log_dir} --suspends-before-reboot={suspend_cycles} --checkbox-respawn-cmd={checkbox_respawn} {check_hardware} {fwts} {pm_operation}
Type=Application
X-GNOME-Autostart-enabled=true
Hidden=false
"""  # noqa: E501

    def __init__(self, args, user=None):
        self.args = args
        self.user = user

        # Generate desktop filename
        # based on environment variables
        username = self.user
        default_config_directory = os.path.expanduser('~{0}/.config'
                                                      .format(username))
        config_directory = os.getenv('XDG_CONFIG_HOME',
                                     default_config_directory)
        autostart_directory = os.path.join(config_directory, 'autostart')
        if not os.path.exists(autostart_directory):
            os.makedirs(autostart_directory)
            user_id = os.getenv('PKEXEC_UID') or os.getenv('SUDO_UID')
            group_id = os.getenv('PKEXEC_UID') or os.getenv('SUDO_GID')
            if user_id:
                os.chown(config_directory, int(user_id), int(group_id))
                os.chown(autostart_directory, int(user_id), int(group_id))

        basename = '{0}.desktop'.format(os.path.basename(__file__))
        self.desktop_filename = os.path.join(autostart_directory,
                                             basename)

    def write(self):
        """
        Write autostart file to execute the script on startup
        """
        logging.debug('Writing desktop file ({0!r})...'
                      .format(self.desktop_filename))
        snap_name = os.getenv('SNAP_NAME')
        if snap_name:
            script = '/snap/bin/{}.pm-test'.format(snap_name)
        else:
            script = '/usr/bin/python3 {}'.format(os.path.realpath(__file__))
        contents = (self.TEMPLATE
                    .format(script=script,
                            repetitions=self.args.repetitions - 1,
                            wakeup=self.args.wakeup,
                            hardware_delay=self.args.hardware_delay,
                            pm_delay=self.args.pm_delay,
                            min_pm_time=self.args.min_pm_time,
                            max_pm_time=self.args.max_pm_time,
                            total=self.args.total,
                            start=self.args.start,
                            pm_timestamp=int(time()),
                            silent='--silent' if self.args.silent else '',
                            log_level=self.args.log_level_str,
                            log_dir=self.args.log_dir,
                            fwts='--fwts' if self.args.fwts else '',
                            suspend_cycles=self.args.suspends_before_reboot,
                            pm_operation=self.args.pm_operation,
                            checkbox_respawn=self.args.checkbox_respawn_cmd,
                            check_hardware='--check-hardware-list' if
                            self.args.check_hardware_list else '',
                            )
                    )
        logging.debug(contents)

        with open(self.desktop_filename, 'w') as f:
            f.write(contents)

    def remove(self):
        """
        Remove autostart file to avoid executing the script on startup
        """
        if os.path.exists(self.desktop_filename):
            logging.debug('Removing desktop file ({0!r})...'
                          .format(self.desktop_filename))
            os.remove(self.desktop_filename)


class LoggingConfiguration():
    @classmethod
    def set(cls, log_level, log_filename, append):
        """
        Configure a rotating file logger
        """
        logger = logging.getLogger()
        logger.setLevel(logging.DEBUG)

        # Log to sys.stdout using log level passed through command line
        if log_level != logging.NOTSET:
            log_handler = logging.StreamHandler(sys.stdout)
            formatter = logging.Formatter('%(levelname)-8s %(message)s')
            log_handler.setFormatter(formatter)
            log_handler.setLevel(log_level)
            logger.addHandler(log_handler)

        # Log to rotating file using DEBUG log level
        log_handler = logging.handlers.RotatingFileHandler(log_filename,
                                                           mode='a+',
                                                           backupCount=3)
        formatter = logging.Formatter('%(asctime)s %(levelname)-8s '
                                      '%(message)s')
        log_handler.setFormatter(formatter)
        log_handler.setLevel(logging.DEBUG)
        logger.addHandler(log_handler)

        if not append:
            # Create a new log file on every new
            # (i.e. not scheduled) invocation
            log_handler.doRollover()


class MyArgumentParser():
    """
    Command-line argument parser
    """
    def __init__(self):
        """
        Create parser object
        """
        pm_operations = ('poweroff', 'reboot')
        description = 'Run power management operation as many times as needed'
        epilog = ('Unknown arguments will be passed '
                  'to the underlying command: poweroff or reboot.')
        parser = ArgumentParser(description=description, epilog=epilog)
        parser.add_argument('-r', '--repetitions', type=int, default=1,
                            help=('Number of times that the power management '
                                  'operation has to be repeated '
                                  '(%(default)s by default)'))
        parser.add_argument('-w', '--wakeup', type=int, default=60,
                            help=('Timeout in seconds for the wakeup alarm '
                                  '(%(default)s by default). '
                                  "Note: wakeup alarm won't be scheduled "
                                  'for reboot.'))
        parser.add_argument('--min-pm-time', dest='min_pm_time',
                            type=int, default=0,
                            help=('Minimum time in seconds that '
                                  'it should take the power management '
                                  'operation each cycle (0 for reboot and '
                                  'wakeup time minus two seconds '
                                  'for the other power management operations '
                                  'by default)'))
        parser.add_argument('--max-pm-time', dest='max_pm_time',
                            type=int, default=300,
                            help=('Maximum time in seconds '
                                  'that it should take '
                                  'the power management operation each cycle '
                                  '(%(default)s by default)'))
        parser.add_argument('--pm-delay', dest='pm_delay',
                            type=int, default=5,
                            help=('Delay in seconds '
                                  'after hardware information '
                                  'has been gathered and before executing '
                                  'the power management operation '
                                  '(%(default)s by default)'))
        parser.add_argument('--hardware-delay', dest='hardware_delay',
                            type=int, default=30,
                            help=('Delay in seconds before gathering hardware '
                                  'information (%(default)s by default)'))
        parser.add_argument('--silent', action='store_true',
                            help=("Don't display any dialog "
                                  'when test is complete '
                                  'to let the script be used '
                                  'in automated tests'))
        log_levels = ['notset', 'debug', 'info',
                      'warning', 'error', 'critical']
        parser.add_argument('--log-level', dest='log_level_str',
                            default='info', choices=log_levels,
                            help=('Log level. '
                                  'One of {0} or {1} (%(default)s by default)'
                                  .format(', '.join(log_levels[:-1]),
                                          log_levels[-1])))
        parser.add_argument('--log-dir', dest='log_dir', default='/var/log',
                            help=('Path to the directory to store log files'))
        parser.add_argument('pm_operation', choices=pm_operations,
                            help=('Power management operation to be performed '
                                  '(one of {0} or {1!r})'
                                  .format(', '.join(map(repr,
                                                        pm_operations[:-1])),
                                          pm_operations[-1])))

        # Test timestamps
        parser.add_argument('--start', type=int, default=0, help=SUPPRESS)
        parser.add_argument('--pm-timestamp', dest='pm_timestamp',
                            type=int, default=0, help=SUPPRESS)

        # Append to log on subsequent startups
        parser.add_argument('--append', action='store_true',
                            default=False, help=SUPPRESS)

        # Total number of iterations initially passed through the command line
        parser.add_argument('--total', type=int, default=0, help=SUPPRESS)

        # suspend cycles before reboot
        parser.add_argument('--suspends-before-reboot', type=int, default=0,
                            help=('How many cycles of suspend/resume to run'
                                  'before each reboot or poweroff'))

        # use fwts for suspend tests
        parser.add_argument('--fwts', action='store_true', help=('Use fwts '
                            'when doing the suspend tests'))
        parser.add_argument('--checkbox-respawn-cmd', type=str, help=(
            'path to a file telling how to return to checkbox after the'
            ' test is done'), default='')
        parser.add_argument('--check-hardware-list', action='store_true',
                            help=('Look for changes in the list of devices '
                                  'after each PM action'), default=False)
        self.parser = parser

    def parse(self):
        """
        Parse command-line arguments
        """
        args, extra_args = self.parser.parse_known_args()
        args.log_level = getattr(logging, args.log_level_str.upper())

        # Total number of repetitions
        # is the number of repetitions passed through the command line
        # the first time the script is executed
        if not args.total:
            args.total = args.repetitions

        # Test start time automatically set on first iteration
        if not args.start:
            args.start = int(time())

        # Wakeup time set to 0 for 'reboot'
        # since wakeup alarm won't be scheduled
        if args.pm_operation == 'reboot':
            args.wakeup = 0
            args.min_pm_time = 0

        # Minimum time for each power management operation
        # is set to the wakeup time
        if not args.min_pm_time:
            min_pm_time = args.wakeup - 2
            if min_pm_time < 0:
                min_pm_time = 0
            args.min_pm_time = min_pm_time

        # Log filename shows clearly the type of test (pm_operation)
        # and the times it was repeated (repetitions)
        args.log_filename = os.path.join(
            args.log_dir,
            '{0}.{1}.{2}.log'.format(
                os.path.splitext(os.path.basename(__file__))[0],
                args.pm_operation,
                args.total))
        return args, extra_args


if __name__ == '__main__':
    sys.exit(main())
