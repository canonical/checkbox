/**
 * keyboard-mouse_test.c - A simple uinput program to randomly generate input events
 * including key presses, mouse movements.
 *
 * SPDX-License-Identifier: GPL-2.0 (inherited from linux/uinput.h)
 *
 * vim: ts=8 sw=8 noet
 **/

#include <linux/uinput.h>
#include <stdlib.h>
#include <time.h>
#include <stdio.h>
#include <string.h>
#include <fcntl.h>
#include <unistd.h>

/**
 * Helper macros
**/
#define ARRAY_SIZE(arr) (sizeof(arr) / sizeof(arr[0]))
#define MAX(l, r) ((l) > (r) ? (l) : (r))

#define KEYBOARD_KEYS \
	KEY_A, KEY_B, KEY_C, KEY_D, KEY_E, KEY_F, KEY_G, KEY_H, KEY_I, KEY_J, \
	KEY_K, KEY_L, KEY_M, KEY_N, KEY_O, KEY_P, KEY_Q, KEY_R, KEY_S, KEY_T, \
	KEY_U, KEY_V, KEY_W, KEY_X, KEY_Y, KEY_Z, \
	KEY_1, KEY_2, KEY_3, KEY_4, KEY_5, KEY_6, KEY_7, KEY_8, KEY_9, KEY_0
#define MOUSE_BUTTONS BTN_LEFT, BTN_RIGHT

#define IOCTL_SET_BITS(fd, ev, bits...) do { \
	const unsigned int __bits[] = { bits }; \
	if (ioctl(fd, UI_SET_EVBIT, EV_##ev) < 0) { \
		perror("error: ioctl(UI_SET_EVBIT, EV_" #ev ")"); \
		return 1; \
	} \
	for (int i = 0; i < ARRAY_SIZE(__bits); i++) { \
		if (ioctl(fd, UI_SET_##ev##BIT, __bits[i]) < 0) { \
			perror("error: ioctl(UI_SET_" #ev "BIT)"); \
			return 1; \
		} \
	} \
} while (0)

int dev_init(int fd, const char *name) {
	IOCTL_SET_BITS(fd, KEY, KEYBOARD_KEYS, MOUSE_BUTTONS);
	IOCTL_SET_BITS(fd, REL, REL_X, REL_Y);

	struct uinput_setup usetup;
	memset(&usetup, 0, sizeof(usetup));
	strcpy(usetup.name, name);
	usetup.id.bustype = BUS_USB;
	usetup.id.vendor = 0xbad;
	usetup.id.product = 0xa55;
	usetup.id.version = 777;

	if (ioctl(fd, UI_DEV_SETUP, &usetup) < 0) {
		perror("error: ioctl(UI_DEV_SETUP)");
		return 1;
	}
	if (ioctl(fd, UI_DEV_CREATE) < 0) {
		perror("error: ioctl(UI_DEV_CREATE)");
		return 1;
	}

	sleep(1);		/* give userspace time to detect the new device */
	return 0;
}

void dev_deinit(int fd) {
	sleep(1);		/* give userspace time to read the events */
	ioctl(fd, UI_DEV_DESTROY);
}

void key_press(int fd, unsigned int key) {
	struct input_event ev, ev_sync;
	memset(&ev_sync, 0, sizeof(ev_sync));
	ev_sync.type = EV_SYN;
	ev_sync.code = SYN_REPORT;

	memset(&ev, 0, sizeof(ev));
	ev.type = EV_KEY;
	ev.code = key;

	ev.value = 1;
	write(fd, &ev, sizeof(ev));
	write(fd, &ev_sync, sizeof(ev_sync));

	ev.value = 0;
	write(fd, &ev, sizeof(ev));
	write(fd, &ev_sync, sizeof(ev_sync));
}

void mouse_move(int fd, int x, int y) {
	struct input_event ev, ev_sync;
	memset(&ev_sync, 0, sizeof(ev_sync));
	ev_sync.type = EV_SYN;
	ev_sync.code = SYN_REPORT;

	memset(&ev, 0, sizeof(ev));
	ev.type = EV_REL;
	ev.code = REL_X;
	ev.value = x;
	write(fd, &ev, sizeof(ev));
	ev.code = REL_Y;
	ev.value = y;
	write(fd, &ev, sizeof(ev));
	write(fd, &ev_sync, sizeof(ev_sync));
}

/**
 * Helper functions
**/

/* Randomly press a key among `KEYBOARD_KEYS` */
void rand_key_press(int fd);
/* Randomly move the mouse smoothly */
void rand_mouse_moves(int fd);

/**
 * The following constants can be overridden at compile time:
 * - FREQUENCY_USEC:	frequency of input events in microseconds
 * - N_EPISODES:	number of input events to generate
 * - WEIGHT_MOUSEMOVE:	weight of mouse movements
 * - WEIGHT_KEYPRESS:	weight of key presses
**/

#ifndef FREQUENCY_USEC
#define FREQUENCY_USEC 100000
#endif

#ifndef N_EPISODES
#define N_EPISODES 81
#endif

#ifndef WEIGHT_MOUSEMOVE
#define WEIGHT_MOUSEMOVE 10
#endif

#ifndef WEIGHT_KEYPRESS
#define WEIGHT_KEYPRESS 1
#endif

#define WEIGHT_SUM (WEIGHT_MOUSEMOVE + WEIGHT_KEYPRESS)
int main(void) {
	int fd, rc = 0;

	fd = open("/dev/uinput", O_WRONLY | O_NONBLOCK);
	if (fd < 0) {
		perror("error: open /dev/uinput");
		return 1;
	}

	if ((rc = dev_init(fd, "key-mouse-random")))
		goto close_fd;

	srand(time(NULL));
	for (int i = 0; i < N_EPISODES; i++) {
		switch (rand() % WEIGHT_SUM) {
			case 0 ... WEIGHT_MOUSEMOVE - 1:
				rand_mouse_moves(fd);
				break;
			default:
				rand_key_press(fd);
				break;
		}
	}

	dev_deinit(fd);
close_fd:
	close(fd);
	return rc;
}

#define __MOVE_MAX 100
#define MOVE_DELTA 5
#define MOVE_MAX (__MOVE_MAX & 1 ? __MOVE_MAX : __MOVE_MAX + 1)
#define MOVE_RAND (rand() % MOVE_MAX - MOVE_MAX / 2)

void rand_key_press(int fd) {
	const unsigned int keys[] = { KEYBOARD_KEYS };
	key_press(fd, keys[rand() % ARRAY_SIZE(keys)]);
	usleep(FREQUENCY_USEC);
}

void rand_mouse_moves(int fd) {
	int x, y, steps;
	x = MOVE_RAND;
	y = MOVE_RAND;
	steps = MAX(abs(x), abs(y)) / MOVE_DELTA;

	for (int i = 0; i < steps; i++) {
		mouse_move(fd, x / steps, y / steps);
		usleep(FREQUENCY_USEC / MOVE_DELTA);
	}

	steps = steps ? steps : 0x7fffffff;
	int rest_x = x % steps, rest_y = y % steps;
	if (rest_x || rest_y) {
		mouse_move(fd, rest_x, rest_y);
		usleep(FREQUENCY_USEC / MOVE_DELTA);
	}
}
