.PHONY:
all: alsa_test clocktest threaded_memtest ptrace_test

.PHONY: clean
clean:
	rm -f alsa_test clocktest threaded_memtest ptrace_test

threaded_memtest: CFLAGS += -pthread
threaded_memtest: CFLAGS += -Wno-unused-but-set-variable
clocktest: CFLAGS += -D_POSIX_C_SOURCE=199309L -D_DEFAULT_SOURCE
clocktest: LDLIBS += -lrt
alsa_test: CXXFLAGS += -std=c++11
alsa_test: LDLIBS += -lasound -pthread

CFLAGS += -Wall
