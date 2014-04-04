.PHONY: all
all: 80211_resource

.PHONY: clean
clean:
	rm -f 80211_resource 80211_resource.o

80211_resource: CFLAGS += $(shell pkg-config --cflags libnl-3.0 libnl-genl-3.0)
80211_resource: LDLIBS += $(shell pkg-config --libs libnl-3.0 libnl-genl-3.0)

CFLAGS += -Wall -Wundef -Wstrict-prototypes -Wno-trigraphs -fno-strict-aliasing -fno-common -Werror-implicit-function-declaration
