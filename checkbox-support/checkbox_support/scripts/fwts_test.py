#! /usr/bin/python3

import sys
import re
from argparse import ArgumentParser, RawTextHelpFormatter, REMAINDER
from subprocess import Popen, PIPE, DEVNULL
from shutil import which
import os

# These tests require user interaction and need either special handling
# or skipping altogether (right now, we skip them but they're kept here
# in case we figure out a way to present the interaction to the user).
INTERACTIVE_TESTS = ['ac_adapter',
                     'battery',
                     'hotkey',
                     'power_button',
                     'brightness',
                     'lid']
# Tests recommended by the Hardware Enablement Team (HWE)
# These are performed on QA certification runs
QA_TESTS = ['acpitests',
            'apicedge',
            'aspm',
            'cpufreq',
            'dmicheck',
            'esrt',
            'klog',
            'maxfreq',
            'msr',
            'mtrr',
            'nx',
            'oops',
            'securebootcert',
            'uefibootpath',
            'uefirtmisc',
            'uefirttime',
            'uefirtvariable',
            'version',
            'virt']
# The following tests will record logs in a separate file for the HWE team
HWE_TESTS = ['version',
             'mtrr',
             'virt',
             'apicedge',
             'klog',
             'oops']
# THe following tests are re-introduced to the server suite at the request of
# the hyperscale team
# These are called when running the --uefitests shortcut
UEFI_TESTS = ['esrt',
              'uefirtauthvar',
              'uefibootpath',
              'securebootcert',
              'uefirtmisc',
              'uefirtvariable',
              'uefirttime',
              'csm']
# These are called when running the --sbbr shortcut
SBBR_TESTS = ['dmicheck',
              'xsdt',
              'spcr',
              'rsdp_sbbr',
              'method',
              'madt',
              'gtdt',
              'fadt_sbbr',
              'dbg2',
              'acpi_sbbr',
              'acpitables']
# These are called when running the --acpitests shortcut
ACPI_TESTS = ['acpiinfo', 'xenv', 'xsdt', 'wsmt', 'wpbt', 'wmi', 'wdat',
              'waet', 'uefi', 'tpm2', 'tcpa', 'stao', 'srat', 'spmi', 'spcr',
              'slit', 'slic', 'sdev', 'sdei', 'sbst', 'rsdt', 'rsdp', 'rasf',
              'pptt', 'pmtt', 'pdtt', 'pcct', 'pcc', 'nfit', 'method', 'msdm',
              'msct', 'mpst', 'mchi', 'mcfg', 'madt', 'lpit', 'iort', 'hmat',
              'hpet', 'hest', 'gtdt', 'fpdt', 'fadt', 'facs', 'erst', 'einj',
              'ecdt', 'drtm', 'dppt', 'dmar', 'acpi_wpc', 'acpi_time',
              'acpi_als', 'acpi_lid', 'acpi_slpb', 'acpi_pwrb', 'acpi_ec',
              'smart_battery', 'acpi_battery', 'acpi_ac', 'dbg2', 'dbgp',
              'cstates', 'csrt', 'cpep', 'checksum', 'boot', 'bgrt', 'bert',
              'aspt', 'asf', 'apicinstance', 'acpitables']
# There are some overlaps there, this creates one master list removing
# duplicates and then we add some that seem to only apply to Power hardware
SERVER_TESTS = list(dict.fromkeys(ACPI_TESTS + SBBR_TESTS + UEFI_TESTS))
SERVER_TESTS.extend(['cpu_info', 'dt_base', 'dt_sysinfo', 'maxreadreq',
                     'mem_info', 'mtd_info', 'power_mgmt', 'prd_info',
                     'reserv_mem version'])
# By default, we launch all the tests
TESTS = sorted(list(set(QA_TESTS + HWE_TESTS)))
SLEEP_TIME_RE = re.compile('(Suspend|Resume):\s+([\d\.]+)\s+seconds.')


def get_sleep_times(log, start_marker):
    suspend_time = ''
    resume_time = ''
    with open(log, 'r', encoding='UTF-8', errors='ignore') as f:
        line = ''
        while start_marker not in line:
            line = f.readline()
            if start_marker in line:
                loglist = f.readlines()
        for i, l in enumerate(loglist):
            if 'Suspend/Resume Timings:' in l:
                suspend_line = loglist[i+1]
                resume_line = loglist[i+2]
                match = SLEEP_TIME_RE.search(suspend_line)
                if match:
                    suspend_time = float(match.group(2))
                match = SLEEP_TIME_RE.search(resume_line)
                if match:
                    resume_time = float(match.group(2))
    return (suspend_time, resume_time)


def average_times(runs):
    sleep_total = 0.0
    resume_total = 0.0
    run_count = 0
    try:
        for run in runs.keys():
            run_count += 1
            sleep_total += runs[run][0]
            resume_total += runs[run][1]
        sleep_avg = sleep_total / run_count
        resume_avg = resume_total / run_count
        print('Average time to sleep: %0.5f' % sleep_avg)
        print('Average time to resume: %0.5f' % resume_avg)
    except TypeError:
        print('Average time to sleep: N/A')
        print('Average time to resume: N/A')


def fix_sleep_args(args):
    new_args = []
    for arg in args:
        if "=" in arg:
            new_args.extend(arg.split('='))
        else:
            new_args.append(arg)
    return new_args


def detect_progress_indicator():
    # Return a command suitable for piping progress information to its
    # stdin (invoked via Popen), in list format.
    # Return zenity if installed and DISPLAY (--auto-close)
    # return dialog if installed and no DISPLAY (width height)
    display = os.environ.get('DISPLAY')
    if display and which('zenity'):
        return ["zenity", "--progress", "--text", "Progress", "--auto-close"]
    if not display and which('dialog'):
        return ["dialog", "--gauge", "Progress", "20", "70"]
    # Return empty list if no progress indicator is to be used
    return []


def main():
    description_text = 'Tests the system BIOS using the Firmware Test Suite'
    epilog_text = ('To perform sleep testing, you will need at least some of '
                   'the following options: \n'
                   's3 or s4: tells fwts which type of sleep to perform.\n'
                   '--s3-delay-delta\n'
                   '--s3-device-check\n'
                   '--s3-device-check-delay\n'
                   '--s3-hybrid-sleep\n'
                   '--s3-max-delay\n'
                   '--s3-min-delay\n'
                   '--s3-multiple\n'
                   '--s3-quirks\n'
                   '--s3-sleep-delay\n'
                   '--s3power-sleep-delay\n\n'
                   'Example: fwts_test --sleep s3 --s3-min-delay 30 '
                   '--s3-multiple 10 --s3-device-check\n\n'
                   'For further help with sleep options:\n'
                   'fwts_test --fwts-help')
    parser = ArgumentParser(description=description_text,
                            epilog=epilog_text,
                            formatter_class=RawTextHelpFormatter)
    parser.add_argument('-l', '--log',
                        default='/tmp/fwts_results.log',
                        help=('Specify the location and name '
                              'of the log file.\n'
                              '[Default: %(default)s]'))
    # "supercritical" default is used to avoid displaying critical results by
    # default
    parser.add_argument('-f', '--fail-level',
                        default='supercritical',
                        choices=['critical', 'high', 'medium',
                                 'low', 'none', 'aborted'],
                        help=('Specify the FWTS failure level that will '
                              'trigger this script to return a failing exit '
                              'code. For example, if you chose "critical" as '
                              'the fail-level, this wrapper will NOT return '
                              'a failing exit code unless FWTS reports a '
                              'test as FAILED_CRITICAL. You will still be '
                              'notified of all FWTS test failures. '
                              '[Default level: %(default)s]'))
    parser.add_argument('-q', '--quiet',
                        action='store_true',
                        help='Suppress script output except for failures '
                             'matching the fail-level set by -f')
    group = parser.add_mutually_exclusive_group()
    group.add_argument('-t', '--test',
                       action='append',
                       help='Name of the test to run.')
    group.add_argument('-a', '--all',
                       action='store_true',
                       help='Run ALL FWTS automated tests (assumes -w and -c)')
    group.add_argument('-s', '--sleep',
                       nargs=REMAINDER,
                       action='store',
                       help=('Perform sleep test(s) using the additional\n'
                             'arguments provided after --sleep. Remaining\n'
                             'items on the command line will be passed \n'
                             'through to fwts for performing sleep tests. \n'
                             'For info on these extra fwts options, please \n'
                             'see the epilog below and \n'
                             'the --fwts-help option.'))
    group.add_argument('--hwe',
                       action='store_true',
                       help='Run HWE concerned tests in fwts')
    group.add_argument('--qa',
                       action='store_true',
                       help='Run QA concerned tests in fwts')
    group.add_argument('--server',
                       action='store_true',
                       help='Run Server Certification concerned tests in fwts')
    group.add_argument('--fwts-help',
                       dest='fwts_help',
                       action='store_true',
                       help='Display the help info for fwts itself (lengthy)')
    group.add_argument('--list',
                       action='store_true',
                       help='List all tests in fwts.')
    group.add_argument('--list-hwe',
                       action='store_true',
                       help='List all HWE concerned tests in fwts')
    group.add_argument('--list-qa',
                       action='store_true',
                       help='List all QA concerned tests in fwts')
    group.add_argument('--list-server',
                       action='store_true',
                       help=('List all Server Certification concerned tests '
                             'in fwts'))
    args = parser.parse_args()

    tests = []
    requested_tests = []
    results = {}
    critical_fails = []
    high_fails = []
    medium_fails = []
    low_fails = []
    passed = []
    aborted = []
    skipped = []
    unavailable = []
    warnings = []

    # Set correct fail level
    if args.fail_level != 'none':
        args.fail_level = 'FAILED_%s' % args.fail_level.upper()

        # Get our failure priority and create the priority values
        fail_levels = {'FAILED_SUPERCRITICAL': 5,
                       'FAILED_CRITICAL': 4,
                       'FAILED_HIGH': 3,
                       'FAILED_MEDIUM': 2,
                       'FAILED_LOW': 1,
                       'FAILED_NONE': 0,
                       'FAILED_ABORTED': -1}
        fail_priority = fail_levels[args.fail_level]

    if args.fwts_help:
        Popen('fwts -h', shell=True).communicate()[0]
        return 0
    elif args.list:
        print('\n'.join(TESTS))
        return 0
    elif args.list_hwe:
        print('\n'.join(HWE_TESTS))
        return 0
    elif args.list_qa:
        print('\n'.join(QA_TESTS))
        return 0
    elif args.list_server:
        print('Server Certification Tests:')
        print('  * ', '\n  * '.join(SERVER_TESTS))
    elif args.test:
        requested_tests.extend(args.test)
    elif args.hwe:
        requested_tests.extend(HWE_TESTS)
    elif args.qa:
        requested_tests.extend(QA_TESTS)
    elif args.server:
        requested_tests.extend(SERVER_TESTS)
    elif args.sleep:
        args.sleep = fix_sleep_args(args.sleep)
        iterations = 1
        # if multiple iterations are requested, we need to intercept
        # that argument and keep it from being presented to fwts since
        # we're handling the iterations directly.
        s3 = '--s3-multiple'
        s4 = '--s4-multiple'
        if s3 in args.sleep:
            iterations = int(args.sleep.pop(args.sleep.index(s3) + 1))
            args.sleep.remove(s3)
        if s4 in args.sleep:
            iterations = int(args.sleep.pop(args.sleep.index(s4) + 1))
            args.sleep.remove(s4)
        requested_tests.extend(args.sleep)
    else:
        requested_tests.extend(TESTS)

        # run the tests we want
    if args.sleep:
        tests = requested_tests
        iteration_results = {}
        print('=' * 20 + ' Test Results ' + '=' * 20)
        progress_indicator = None
        if detect_progress_indicator():
            progress_indicator = Popen(detect_progress_indicator(),
                                       stdin=PIPE, stderr=DEVNULL)
        for iteration in range(1, iterations+1):
            marker = '{:=^80}\n'.format(' Iteration {} '.format(iteration))
            with open(args.log, 'a') as f:
                f.write(marker)
            command = ('fwts -q --stdout-summary -r %s %s'
                       % (args.log, ' '.join(tests)))
            results['sleep'] = (Popen(command, stdout=PIPE, shell=True)
                                .communicate()[0].strip()).decode()
            if 's4' not in args.sleep:
                suspend_time, resume_time = get_sleep_times(args.log, marker)
                iteration_results[iteration] = (suspend_time, resume_time)
                if not suspend_time or not resume_time:
                    progress_string = (
                        'Cycle %s/%s - Suspend: N/A s - Resume: N/A s'
                        % (iteration, iterations))
                else:
                    progress_string = (
                        'Cycle %s/%s - Suspend: %0.2f s - Resume: %0.2f s'
                        % (iteration, iterations, suspend_time, resume_time))
                progress_pct = "{}".format(int(100 * iteration / iterations))
                if "zenity" in detect_progress_indicator():
                    progress_indicator.stdin.write("# {}\n".format(
                        progress_string).encode('utf-8'))
                    progress_indicator.stdin.write("{}\n".format(
                        progress_pct).encode('utf-8'))
                    if progress_indicator.poll() is None:
                        # LP: #1741217 process may have already terminated
                        # flushing its stdin would yield broken pipe
                        progress_indicator.stdin.flush()
                elif "dialog" in detect_progress_indicator():
                    progress_indicator.stdin.write("XXX\n".encode('utf-8'))
                    progress_indicator.stdin.write(
                        progress_pct.encode('utf-8'))
                    progress_indicator.stdin.write(
                        "\nTest progress\n".encode('utf-8'))
                    progress_indicator.stdin.write(
                        progress_string.encode('utf-8'))
                    progress_indicator.stdin.write(
                        "\nXXX\n".encode('utf-8'))
                    if progress_indicator.poll() is None:
                        progress_indicator.stdin.flush()
                else:
                    print(progress_string, flush=True)
        if detect_progress_indicator():
            progress_indicator.terminate()
        if 's4' not in args.sleep:
            average_times(iteration_results)
    else:
        # Because the list of available tests varies from arch to arch, we
        # need to validate our test selections and remove any unsupported
        # tests.
        cmd = ('fwts --show-tests')
        fwts_test_list = (Popen(cmd, stdout=PIPE, shell=True)
                          .communicate()[0].strip().decode().split('\n'))
        AVAILABLE_TESTS = list(dict.fromkeys(
                               [item.lstrip().split()[0] for item in
                                fwts_test_list if not item.endswith(':')
                                and item != '']))
        # Compare requested tests to AVAILABLE_TESTS, and if we've requested a
        # test that isn't available, go ahead and mark it as skipped, otherwise
        # add it to tests for execution
        for test in requested_tests:
            if test not in AVAILABLE_TESTS:
                unavailable.append(test)
            else:
                tests.append(test)

        if tests:
            for test in tests:
                # ACPI tests can now be run with --acpitests (fwts >= 15.07.00)
                log = args.log
                # Split the log file for HWE (only if -t is not used)
                if test == 'acpitests':
                    test = '--acpitests'
                command = ('fwts -q --stdout-summary -r %s %s'
                           % (log, test))
                results[test] = (Popen(command, stdout=PIPE, shell=True)
                                 .communicate()[0].strip()).decode()
    # parse the summaries
    if results:
        for test in results.keys():
            if 'FAILED_CRITICAL' in results[test]:
                critical_fails.append(test)
            elif 'FAILED_HIGH' in results[test]:
                high_fails.append(test)
            elif 'FAILED_MEDIUM' in results[test]:
                medium_fails.append(test)
            elif 'FAILED_LOW' in results[test]:
                low_fails.append(test)
            elif 'PASSED' in results[test]:
                passed.append(test)
            elif 'ABORTED' in results[test]:
                aborted.append(test)
            elif 'WARNING' in results[test]:
                warnings.append(test)
            elif 'SKIPPED' in results[test]:
                skipped.append(test)
            else:
                return 1

    if critical_fails:
        print("Critical Failures: %d" % len(critical_fails))
        if ((args.quiet and fail_priority <= fail_levels['FAILED_CRITICAL'])
            or not args.quiet):
            print(" WARNING: The following test cases were reported as"
                  " critical\n"
                  " level failures by fwts:")
            for test in critical_fails:
                print("  - " + test)
    if high_fails:
        print("High Failures: %d" % len(high_fails))
        if ((args.quiet and fail_priority <= fail_levels['FAILED_HIGH'])
            or not args.quiet):
            print(" WARNING: The following test cases were reported as high\n"
                  " level failures by fwts:")
            for test in high_fails:
                print("  - " + test)
    if medium_fails:
        print("Medium Failures: %d" % len(medium_fails))
        if ((args.quiet and fail_priority <= fail_levels['FAILED_MEDIUM'])
            or not args.quiet):
            print(" WARNING: The following test cases were reported as"
                  " medium\n"
                  " level failures by fwts:")
            for test in medium_fails:
                print("  - " + test)
    if low_fails:
        print("Low Failures: %d" % len(low_fails))
        if ((args.quiet and fail_priority <= fail_levels['FAILED_LOW'])
            or not args.quiet):
            print(" WARNING: The following test cases were reported as low\n"
                  " level failures by fwts:")
            for test in low_fails:
                print("  - " + test)
    if passed:
        print("Passed: %d" % len(passed))
        if ((args.quiet and fail_priority <= fail_levels['FAILED_NONE'])
            or not args.quiet):
            for test in passed:
                print(" - " + test)
    if skipped:
        print("Skipped Tests: %d" % len(skipped))
        if not args.quiet:
            print(" WARNING: The following test cases were skipped by fwts:")
            for test in skipped:
                print("  - " + test)
    if unavailable:
        print("Unavailable Tests: %d" % len(unavailable))
        if not args.quiet:
            print(" WARNING: The following test cases are not available\n"
                  " on this architecture. Running fwts --show-tests on\n"
                  " this system will list available tests.")
            for test in unavailable:
                print("  - " + test)
    if warnings:
        print("WARNINGS: %d" % len(warnings))
        if not args.quiet:
            for test in warnings:
                print("  - " + test)
    if aborted:
        print("Aborted Tests: %d" % len(aborted))
        if ((args.quiet and fail_priority <= fail_levels['FAILED_ABORTED'])
            or not args.quiet):
            print(" WARNING: The following test cases were aborted by fwts:")
            for test in aborted:
                print("  - " + test)
    # Append content of the log file to stdout for easier review
    print()
    print(" Please review the following log for more information:")
    print()
    with open(args.log) as f:
	    print(f.read())

    if args.fail_level != 'none':
        if fail_priority == fail_levels['FAILED_CRITICAL']:
            if critical_fails:
                return 1
        if fail_priority == fail_levels['FAILED_HIGH']:
            if critical_fails or high_fails:
                return 1
        if fail_priority == fail_levels['FAILED_MEDIUM']:
            if critical_fails or high_fails or medium_fails:
                return 1
        if fail_priority == fail_levels['FAILED_LOW']:
            if critical_fails or high_fails or medium_fails or low_fails:
                return 1
        if fail_priority == fail_levels['FAILED_ABORTED']:
            if aborted or critical_fails or high_fails:
                return 1

    return 0


if __name__ == '__main__':
    sys.exit(main())
