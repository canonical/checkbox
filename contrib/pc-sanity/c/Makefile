#!/usr/bin/make -f
# vim: sw=8 ts=8 noet

PREFIX = /usr/local

CC = gcc
SOURCES = $(wildcard *.c)
TARGETS = $(SOURCES:.c=)

all: $(TARGETS)

%: %.c
	$(CC) -o $@ $^

clean:
	rm -f $(TARGETS)

install: %: $(TARGETS)
	install -d $(PREFIX)/bin
	install -m 755 $^ $(PREFIX)/bin

uninstall:
	cd $(PREFIX)/bin && rm -f $(TARGETS)

.PHONY: all clean install uninstall
