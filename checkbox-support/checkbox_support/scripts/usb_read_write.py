#!/usr/bin/env python3
# Copyright 2015 - 2016 Canonical Ltd.
# All rights reserved.
#
# Written by:
#   Taihsiang Ho <taihsiang.ho@canonical.com>

"""
Script to test the performance of USB read/write.

This script is intended be used as part of a plainbox provider.
It is expected to find the partition of the usb storage
inserted in the previous insertion test
and use the info to mount, read and write the USB.

The test is performed by the following steps:
    1. create a random file, say a "source file"
    2. mount the USB storage with the folder FOLDER_TO_MOUNT
    3. copy the source file into FOLDER_TO_MOUNT by dd REPETITION_NUM times.
    4. access the md5sum numbers of the files copied into FOLDER_TO_MOUNT
    5. compare the md5sum numbers with the md5sum of the source file.
    6. report the result and return associated values back to plainbox.
"""

import sys
import subprocess
import os
import collections
import tempfile
import logging
import errno
import contextlib


PLAINBOX_SESSION_SHARE = os.environ.get('PLAINBOX_SESSION_SHARE', '')
FOLDER_TO_MOUNT = tempfile.mkdtemp()
REPETITION_NUM = 5  # number to repeat the read/write test units.
# Prepare a random file which size is RANDOM_FILE_SIZE.
# Default 1048576 = 1MB  to perform writing test
RANDOM_FILE_SIZE = 104857600
USB_INSERT_INFO = "usb_insert_info"

log_path = os.path.join(PLAINBOX_SESSION_SHARE, 'usb-rw.log')
logging.basicConfig(level=logging.DEBUG, filename=log_path)


class RandomData():
    """
    Class to create data files.

    This class is ported from the original checkbox script.
    """

    def __init__(self, size):
        """
        init method of class RandomData.

        :param size:
            an integer to decide the size of the generated random file in byte.
        """
        self.tfile = tempfile.NamedTemporaryFile(delete=False)
        self.path = ''
        self.name = ''
        self.path, self.name = os.path.split(self.tfile.name)
        self._write_test_data_file(size)

    def _generate_test_data(self):
        seed = "104872948765827105728492766217823438120"
        phrase = '''
        Lorem ipsum dolor sit amet, consectetuer adipiscing elit, sed diam
        nonummy nibh euismod tincidunt ut laoreet dolore magna aliquam erat
        volutpat. Ut wisi enim ad minim veniam, quis nostrud exerci tation
        ullamcorper suscipit lobortis nisl ut aliquip ex ea commodo consequat.
        Duis autem vel eum iriure dolor in hendrerit in vulputate velit esse
        molestie consequat, vel illum dolore eu feugiat nulla facilisis at vero
        eros et accumsan et iusto odio dignissim qui blandit praesent luptatum
        zzril delenit augue duis dolore te feugait nulla facilisi.
        '''
        words = phrase.replace('\n', '').split()
        word_deque = collections.deque(words)
        seed_deque = collections.deque(seed)
        while True:
            yield ' '.join(list(word_deque))
            word_deque.rotate(int(seed_deque[0]))
            seed_deque.rotate(1)

    def _write_test_data_file(self, size):
        data = self._generate_test_data()
        while os.path.getsize(self.tfile.name) < size:
            self.tfile.write(next(data).encode('UTF-8'))
        return self


def get_partition_info():
    """
    get partition info.

    use a cache file provided by usb insertion test
    to get the partition to mount later

    return: a string which is a partition name. e.g. sdb1
    """
    if not PLAINBOX_SESSION_SHARE:
        logging.error("no PLAINBOX_SESSION_SHARE is defined.")
        sys.exit(1)
    file_lines = ""
    info_path = os.path.join(PLAINBOX_SESSION_SHARE, USB_INSERT_INFO)
    try:
        with open(info_path, "r") as file_usb_insert_info:
            file_lines = file_usb_insert_info.readlines()
    except OSError as e:
        if e.errno == errno.ENOENT:
            logging.error("%s info file was not found. \
                           Did the insertion test was run successfully?"
                          % USB_INSERT_INFO)
        sys.exit(1)
    # TODO: need to be smarter
    if len(file_lines) == 1:
        partition = file_lines[0].strip()
    else:
        logging.error("has no idea which partition to mount or not found")
        sys.exit(1)

    return partition


def run_read_write_test():
    """try to mount the partition candidates."""
    # random file as a benchmark, a "source" file
    with gen_random_file() as random_file:
        # initialize the necessary tasks before performing read/write test
        partitions = os.environ.get('USB_RWTEST_PARTITIONS', '').split()
        if not partitions:
            partitions = [get_partition_info()]
        for partition in partitions:
            with mount_usb_storage(partition):
                # write test
                write_test(random_file)
                # already write some data into the target
                # so let's read it to perform the read test
                # and validate the writing correctness
                read_test(random_file)


@contextlib.contextmanager
def mount_usb_storage(partition):
    """
    initialize the configuration so we could get ready to test jobs.

    get everything ready to have the read/write test, including
    1. create a temporary folder used for mounting devices
    2. un-mount the target device at the very beginning if it was mounted

    TODO: this function should be smarter and not completed enough
    """
    logging.debug("try to mount usb storage for testing")

    try:
        device_to_mount = os.path.join("/dev", partition)
        # use pipe so I could hide message like
        # "umount: /tmp/tmpjzwb6lys: not mounted"
        subprocess.call(['umount', FOLDER_TO_MOUNT], stderr=subprocess.PIPE)

        # mount the target device/partition
        # if the return code of the shell command is non-zero,
        # means something wrong.
        # quit this script and return a non-zero value to plainbox
        if subprocess.call(['mount', device_to_mount, FOLDER_TO_MOUNT]):
            logging.error("mount %s on %s failed."
                          % (device_to_mount, FOLDER_TO_MOUNT))
            sys.exit(1)
        else:
            logging.debug("mount %s on %s successfully."
                          % (device_to_mount, FOLDER_TO_MOUNT))
        yield

    finally:
        logging.info("context manager exit: unmount USB storage")
        if subprocess.call(['umount', FOLDER_TO_MOUNT]):
            logging.warning("umount %s failed." % FOLDER_TO_MOUNT)
        else:
            logging.info("umount %s successfully." % FOLDER_TO_MOUNT)


def read_test(random_file):
    """perform the read test."""
    logging.debug("===================")
    logging.debug("reading test begins")
    logging.debug("===================")

    read_test_list = []
    for idx in range(REPETITION_NUM):
        read_test_list.append(read_test_unit(random_file, str(idx)))
    print('PASS: all reading tests passed.')


def read_test_unit(random_source_file, idx=""):
    """
    perform the read test.

    :param random_source_file: a RandomData object
    :param idx: a idx to label the files to be compared with the source file.
          It is an int string, "1", "2", "3", ......etc.
    """
    # access the temporary file
    path_random_file = os.path.join(
        FOLDER_TO_MOUNT, os.path.basename(random_source_file.tfile.name)) + idx
    # get the md5sum of the temp random files to compare
    process = subprocess.Popen(['md5sum', path_random_file],
                               stdout=subprocess.PIPE)
    tfile_md5sum = process.communicate()[0].decode().split(" ")[0]
    # get the md5sum of the source random file
    process = subprocess.Popen(['md5sum', random_source_file.tfile.name],
                               stdout=subprocess.PIPE)
    source_md5sum = process.communicate()[0].decode().split(" ")[0]

    logging.debug("%s %s (verified)" % (tfile_md5sum, path_random_file))
    logging.debug("%s %s (source)"
                  % (source_md5sum, random_source_file.tfile.name))

    # Clean the target file
    os.remove(path_random_file)

    # verify the md5sum
    if tfile_md5sum == source_md5sum:
        print("PASS: READING TEST: %s passes md5sum comparison."
              % path_random_file)
    else:
        # failed in the reading test
        # tell plainbox the failure code
        logging.warning("FAIL: READING TEST: %s failed in md5sum comparison."
                        % path_random_file)
        sys.exit(1)


def write_test(random_file):
    """perform a writing test."""
    logging.debug("===================")
    logging.debug("writing test begins")
    logging.debug("===================")

    write_speed_list = []
    for idx in range(REPETITION_NUM):
        write_speed_list.append(write_test_unit(random_file, str(idx)))
    average_speed = sum(write_speed_list)/REPETITION_NUM
    file_size_in_mb = RANDOM_FILE_SIZE / (1024*1024)
    print("Average writing speed is: {:.3f} MB/s "
          "({}x{} MB files were written)".format(
              average_speed, REPETITION_NUM, file_size_in_mb))


def write_test_unit(random_file, idx=""):
    """
    perform the writing test.

    :param random_file: a RndomData object created to be written
    :return: a float in MB/s to denote writing speed
    """
    target_file = os.path.join(
        FOLDER_TO_MOUNT, os.path.basename(random_file.tfile.name)) + idx
    process = subprocess.Popen([
        'dd', 'if=' + random_file.tfile.name, 'of=' + target_file],
        stderr=subprocess.STDOUT, stdout=subprocess.PIPE)
    logging.debug("Apply command: %s" % process.args)
    # will get something like
    # ['2048+1 records in', '2048+1 records out',
    # '1049076 bytes (1.0 MB) copied, 0.00473357 s, 222 MB/s', '']
    list_dd_message = process.communicate()[0].decode().split("\n")
    logging.debug(list_dd_message)
    logging.debug(get_md5sum(target_file))

    try:
        dd_speed = float(list_dd_message[2].split(" ")[-2])
        print("PASS: WRITING TEST: %s" % target_file)
    except:
        # Example:
        # ['dd: writing to ‘/tmp/tmp08osy45j/tmpnek46on30’: Input/output error'
        # , '38913+0 records in', '38912+0 records out', '19922944 bytes
        # (20 MB) copied, 99.647 s, 200 kB/s', '']
        print("ERROR: {}".format(list_dd_message))
        sys.exit(1)

    return dd_speed


@contextlib.contextmanager
def gen_random_file():
    """
    generate a random file which size is RANDOM_FILE_SIZE.

    :return: a RandomData object
    """
    logging.debug("generating a random file")

    try:
        # 1048576 = 1024 * 1024
        # we are going to generate a 1M file
        random_file = RandomData(RANDOM_FILE_SIZE)
        # flush the remaining data in the memory buffer
        # otherwise the md5sum will be different if you
        # check it manually from your shell command md5sum
        random_file.tfile.file.flush()

        yield random_file

    finally:
        logging.info("Remove temporary folders and files.")
        # delete the mount folder
        try:
            os.rmdir(FOLDER_TO_MOUNT)
        except OSError:
            logging.warning("Failed to remove %s (mount folder not empty)."
                            % FOLDER_TO_MOUNT)
        # delete the random file (source file of a writing test)
        os.unlink(random_file.tfile.name)


def get_md5sum(file_to_check):
    """
    get md5sum of file_to_check.

    :param file_to_check: the absolute path of a file to access its md5sum
    :return: md5sum as a string
    """
    try:
        # return the md5sum of the temp file
        process = subprocess.Popen(['md5sum', file_to_check],
                                   stdout=subprocess.PIPE)
        # something like
        # (b'07bc8f96b7c7dba2c1f3eb2f7dd50541  /tmp/tmp9jnuv329\n', None)
        # will be returned by communicate() in this case
        md5sum = process.communicate()[0].decode().split(" ")[0]

        if md5sum:
            logging.debug("MD5SUM: of %s \t\t\t\t\t%s"
                          % (file_to_check, md5sum))
            return md5sum
        else:
            logging.error("Could not found file to check its MD5SUM. \
                           Check the folder permission?")
            sys.exit(1)

    except OSError as e:
        if e.errno == errno.ENOENT:
            logging.error("%s info file was not found. \
                           Did the insertion test was run successfully?"
                          % USB_INSERT_INFO)
            sys.exit(1)


if __name__ == "__main__":
    run_read_write_test()
