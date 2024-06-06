/**
 * uwake.c - a simple uinput program to wake up the computer
 *
 * vim: ts=8 sw=8 noet
**/

#include <linux/uinput.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <fcntl.h>
#include <unistd.h>

#define NONSENSE KEY_F17

void emit(int fd, int type, int code, int val);

int main(void) {
	int fd;
	struct uinput_setup usetup;

	fd = open("/dev/uinput", O_WRONLY | O_NONBLOCK);
	if (fd < 0) {
		perror("error: open /dev/uinput");
		exit(1);
	}

	ioctl(fd, UI_SET_EVBIT, EV_KEY);
	ioctl(fd, UI_SET_KEYBIT, NONSENSE);

	memset(&usetup, 0, sizeof(usetup));
	usetup.id.bustype = BUS_USB;
	usetup.id.vendor = 0xdead;
	usetup.id.product = 0xbee0;
	strcpy(usetup.name, "uinput-nonsense");

	ioctl(fd, UI_DEV_SETUP, &usetup);
	ioctl(fd, UI_DEV_CREATE);

	// wait for the device to be created
	sleep(1);

	emit(fd, EV_KEY, NONSENSE, 1);
	emit(fd, EV_SYN, SYN_REPORT, 0);
	emit(fd, EV_KEY, NONSENSE, 0);
	emit(fd, EV_SYN, SYN_REPORT, 0);

	// wait for the events to be read
	sleep(1);

	ioctl(fd, UI_DEV_DESTROY);
	close(fd);

	return 0;
}

void emit(int fd, int type, int code, int val) {
	struct input_event ie;

	ie.type = type;
	ie.code = code;
	ie.value = val;
	/* timestamp values below are ignored */
	ie.time.tv_sec = 0;
	ie.time.tv_usec = 0;

	write(fd, &ie, sizeof(ie));
}
