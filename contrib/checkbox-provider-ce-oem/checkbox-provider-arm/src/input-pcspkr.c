#include<stdint.h>
#include<string.h>
#include<fcntl.h>
#include<unistd.h>
#include<stdio.h>
#include<linux/input.h>
#include<unistd.h>

int main(int argc, char *argv[])
{

        int fd, version, ret, freq=200;
        struct input_event event;
        event.type = EV_SND;
        event.code = SND_TONE;
        while ( freq != 3300 ) {
                if ((fd = open(argv[1], O_RDWR)) < 0) {
                        perror("beep test");
                        return 1;
                }
                event.value = freq;
                ret = write(fd, &event, sizeof(struct input_event));
                sleep(0.2);
                freq+=50;
                close(fd);
        }
        fd = open(argv[1], O_RDWR);
        event.type = EV_SND;
        event.code = SND_TONE;
        event.value = 0;
        ret = write(fd, &event, sizeof(struct input_event));
        close(fd);
        return 0;
}
