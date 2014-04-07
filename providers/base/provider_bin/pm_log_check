#!/usr/bin/env python3
import os
import sys
import re
import difflib
import logging
from argparse import ArgumentParser

# Script return codes
SUCCESS = 0
NOT_MATCH = 1
NOT_FINISHED = 2
NOT_FOUND = 3


def main():
    args = parse_args()

    if not os.path.isfile(args.input_log_filename):
        sys.stderr.write('Log file {0!r} not found\n'
                         .format(args.input_log_filename))
        sys.exit(NOT_FOUND)

    LoggingConfiguration.set(args.log_level,
                             args.output_log_filename)
    parser = Parser(args.input_log_filename)
    results = parser.parse()

    if not compare_results(results):
        sys.exit(NOT_MATCH)

    sys.exit(SUCCESS)


class Parser(object):
    """
    Reboot test log file parser
    """
    is_logging_line = (re.compile('^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3}')
                       .search)
    is_getting_info_line = (re.compile('Gathering hardware information...$')
                            .search)
    is_executing_line = (re.compile("Executing: '(?P<command>.*)'...$")
                         .search)
    is_output_line = re.compile('Output:$').search
    is_field_line = (re.compile('^- (?P<field>returncode|stdout|stderr):$')
                     .match)
    is_test_complete_line = re.compile('test complete$').search

    def __init__(self, filename):
        self.filename = filename

    def parse(self):
        """
        Parse log file and return results
        """
        with open(self.filename) as f:
            results = self._parse_file(LineIterator(f))
        return results

    def _parse_file(self, iterator):
        """
        Parse all lines in iterator and return results
        """
        results = []
        result = {}

        for line in iterator:
            if self.is_getting_info_line(line):
                if result:
                    # Add last result to list of results
                    results.append(result)

                # Initialize for a new iteration results
                result = {}

            match = self.is_executing_line(line)
            if match:
                command = match.group('command')
                command_output = self._parse_command_output(iterator)

                if command_output is not None:
                    result[command] = command_output
        else:
            if result:
                # Add last result to list of results
                results.append(result)

        if not self.is_test_complete_line(line):
            sys.stderr.write("Test didn't finish properly according to logs\n")
            sys.exit(NOT_FINISHED)

        return results

    def _parse_command_output(self, iterator):
        """
        Parse one command output
        """
        command_output = None

        # Skip all lines until command output is found
        for line in iterator:
            if self.is_output_line(line):
                command_output = {}
                break
            if (self.is_executing_line(line)
                or self.is_getting_info_line(line)):
                # Skip commands with no output
                iterator.unnext(line)
                return None

        # Parse command output message
        for line in iterator:
            match = self.is_field_line(line)
            if match:
                field = match.group('field')
                value = self._parse_command_output_field(iterator)
                command_output[field] = value
            # Exit when all command output fields
            # have been gathered
            else:
                iterator.unnext(line)
                break

        return command_output

    def _parse_command_output_field(self, iterator):
        """
        Parse one command output field
        """
        # Accummulate as many lines as needed
        # for the field value
        value = []
        for line in iterator:
            if (self.is_logging_line(line)
                or self.is_field_line(line)):
                iterator.unnext(line)
                break

            value.append(line)

        value = ''.join(value)
        return value


class LineIterator:
    """
    Iterator wrapper to make it possible
    to push back lines that shouldn't have been consumed
    """

    def __init__(self, iterator):
        self.iterator = iterator
        self.buffer = []

    def __iter__(self):
        return self

    def __next__(self):
        if self.buffer:
            return self.buffer.pop()

        return next(self.iterator)

    def unnext(self, line):
        self.buffer.append(line)


class LoggingConfiguration(object):
    @classmethod
    def set(cls, log_level, log_filename):
        """
        Configure a rotating file logger
        """
        logger = logging.getLogger()
        logger.setLevel(logging.DEBUG)

        # Log to sys.stderr using log level passed through command line
        if log_level != logging.NOTSET:
            log_handler = logging.StreamHandler()
            formatter = logging.Formatter('%(levelname)-8s %(message)s')
            log_handler.setFormatter(formatter)
            log_handler.setLevel(log_level)
            logger.addHandler(log_handler)

        # Log to rotating file using DEBUG log level
        log_handler = logging.FileHandler(log_filename, mode='w')
        formatter = logging.Formatter('%(asctime)s %(levelname)-8s '
                                      '%(message)s')
        log_handler.setFormatter(formatter)
        log_handler.setLevel(logging.DEBUG)
        logger.addHandler(log_handler)


def compare_results(results):
    """
    Compare results using first one as a baseline
    """
    baseline = results[0]

    success = True
    for index, result in enumerate(results[1:]):
        for command in baseline.keys():
            baseline_output = baseline[command]
            result_output = result[command]

            error_messages = []
            fields = (set(baseline_output.keys())
                      | set(result_output.keys()))
            for field in fields:
                baseline_field = baseline_output.get(field, '')
                result_field = result_output.get(field, '')

                if baseline_field != result_field:
                    differ = difflib.Differ()

                    message = ["** {field!r} field doesn't match:"
                               .format(field=field)]
                    comparison = differ.compare(baseline_field.splitlines(),
                                                result_field.splitlines())
                    message.extend(list(comparison))
                    error_messages.append('\n'.join(message))

            if not error_messages:
                logging.debug('[Iteration {0}] {1}...\t[OK]'
                              .format(index + 1, command))
            else:
                success = False
                if command.startswith('fwts'):
                    logging.error('[Iteration {0}] {1}...\t[FAIL]'
                                  .format(index + 1, command))
                else:
                    logging.error('[Iteration {0}] {1}...\t[FAIL]\n'
                                  .format(index + 1, command))
                    for message in error_messages:
                        logging.error(message)

    return success


def parse_args():
    """
    Parse command-line arguments
    """
    parser = ArgumentParser(description=('Check power management '
                                         'test case results'))
    parser.add_argument('input_log_filename', metavar='log_filename',
                        help=('Path to the input log file '
                              'on which to perform the check'))
    parser.add_argument('output_log_filename', metavar='log_filename',
                        help=('Path to the output log file '
                              'for the results of the check'))
    log_levels = ['notset', 'debug', 'info', 'warning', 'error', 'critical']
    parser.add_argument('--log-level', dest='log_level', default='info',
                        choices=log_levels,
                        help=('Log level. '
                              'One of {0} or {1} (%(default)s by default)'
                              .format(', '.join(log_levels[:-1]),
                                      log_levels[-1])))
    args = parser.parse_args()
    args.log_level = getattr(logging, args.log_level.upper())

    return args


if __name__ == '__main__':
    main()
