.PHONY:
all: clocktest threaded_memtest

.PHONY: clean
clean:
	rm -f clocktest threaded_memtest

threaded_memtest: CFLAGS += -pthread
threaded_memtest: CFLAGS += -Wno-unused-but-set-variable

CFLAGS += -Wall
