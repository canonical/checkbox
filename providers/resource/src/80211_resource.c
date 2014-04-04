/*
 * Lite version of iw (the nl80211 userspace tool)
 *
 * Copyright (c) 2014  Sylvain Pineau <sylvain.pineau@canonical.com>
 *
 * This file incorporates work covered by the following copyright and
 * permission notice:
 *
 * Copyright (c) 2007, 2008	Johannes Berg <johannes@sipsolutions.net>
 * Copyright (c) 2007		Andy Lutomirski
 * Copyright (c) 2007		Mike Kershaw
 * Copyright (c) 2008-2009	Luis R. Rodriguez
 *
 * Permission to use, copy, modify, and/or distribute this software for any
 * purpose with or without fee is hereby granted, provided that the above
 * copyright notice and this permission notice appear in all copies.
 *
 * THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES
 * WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF
 * MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR
 * ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES
 * WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN
 * ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF
 * OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.
 */

#include <errno.h>
#include <stdbool.h>

#include <netlink/genl/genl.h>
#include <netlink/genl/ctrl.h>

#include <linux/nl80211.h>

struct nl80211_state {
	struct nl_sock *nl_sock;
	int nl80211_id;
};

static const char *ifmodes[NL80211_IFTYPE_MAX + 1] = {
	"unspecified",
	"IBSS",
	"managed",
	"AP",
	"AP_VLAN",
	"WDS",
	"monitor",
	"mesh_point",
	"P2P_client",
	"P2P_GO",
	"P2P_device",
};

#define BIT(x) (1ULL<<(x))

static int nl80211_init(struct nl80211_state *state)
{
	int err;

	state->nl_sock = nl_socket_alloc();
	if (!state->nl_sock) {
		fprintf(stderr, "Failed to allocate netlink socket.\n");
		return -ENOMEM;
	}

	nl_socket_set_buffer_size(state->nl_sock, 8192, 8192);

	if (genl_connect(state->nl_sock)) {
		fprintf(stderr, "Failed to connect to generic netlink.\n");
		err = -ENOLINK;
		goto out_handle_destroy;
	}

	state->nl80211_id = genl_ctrl_resolve(state->nl_sock, "nl80211");
	if (state->nl80211_id < 0) {
		fprintf(stderr, "nl80211 not found.\n");
		err = -ENOENT;
		goto out_handle_destroy;
	}

	return 0;

 out_handle_destroy:
	nl_socket_free(state->nl_sock);
	return err;
}

static void nl80211_cleanup(struct nl80211_state *state)
{
	nl_socket_free(state->nl_sock);
}

static int error_handler(struct sockaddr_nl *nla, struct nlmsgerr *err,
			 void *arg)
{
	int *ret = arg;
	*ret = err->error;
	return NL_STOP;
}

static int finish_handler(struct nl_msg *msg, void *arg)
{
	int *ret = arg;
	*ret = 0;
	return NL_SKIP;
}

static int print_phy_handler(struct nl_msg *msg, void *arg)
{
	struct nlattr *tb_msg[NL80211_ATTR_MAX + 1];
	struct genlmsghdr *gnlh = nlmsg_data(nlmsg_hdr(msg));
	struct nlattr *tb_band[NL80211_BAND_ATTR_MAX + 1];
	struct nlattr *tb_freq[NL80211_FREQUENCY_ATTR_MAX + 1];
	struct nlattr *nl_band;
	struct nlattr *nl_freq;
	struct nlattr *nl_mode;
	int rem_band, rem_freq, rem_mode;
    bool ac_support = false;
    bool n_support = false;
    bool bg_support = false;
    bool band_5GHz_support = false;

	nla_parse(tb_msg, NL80211_ATTR_MAX, genlmsg_attrdata(gnlh, 0),
		  genlmsg_attrlen(gnlh, 0), NULL);

	if (tb_msg[NL80211_ATTR_WIPHY_BANDS]) {
		nla_for_each_nested(nl_band, tb_msg[NL80211_ATTR_WIPHY_BANDS], rem_band) {
			nla_parse(tb_band, NL80211_BAND_ATTR_MAX, nla_data(nl_band),
				  nla_len(nl_band), NULL);
            /* 802.11ac is also known as Very High Throughput (VHT) */
            if (tb_band[NL80211_BAND_ATTR_VHT_CAPA] &&
			    tb_band[NL80211_BAND_ATTR_VHT_MCS_SET])
				ac_support = true;
            /* 802.11n can use a new set of rates designed specifically for high throughput (HT) */
            if (tb_band[NL80211_BAND_ATTR_HT_CAPA])
				n_support = true;
            /* Always assume 802.11b/g support */
            bg_support = true;

			if (tb_band[NL80211_BAND_ATTR_FREQS]) {
				nla_for_each_nested(nl_freq, tb_band[NL80211_BAND_ATTR_FREQS], rem_freq) {
					uint32_t freq;
					nla_parse(tb_freq, NL80211_FREQUENCY_ATTR_MAX, nla_data(nl_freq),
						  nla_len(nl_freq), NULL);
					if (!tb_freq[NL80211_FREQUENCY_ATTR_FREQ])
						continue;
                    if (tb_freq[NL80211_FREQUENCY_ATTR_DISABLED]) {
                        continue;
                    }
					freq = nla_get_u32(tb_freq[NL80211_FREQUENCY_ATTR_FREQ]);
                    /* http://en.wikipedia.org/wiki/List_of_WLAN_channels */
                    if (freq >= 4915 && freq <= 5825) 
                        band_5GHz_support = true;
				}
			}
		}
	}

	if (tb_msg[NL80211_ATTR_SUPPORTED_IFTYPES]) {
		nla_for_each_nested(nl_mode, tb_msg[NL80211_ATTR_SUPPORTED_IFTYPES], rem_mode) {
            enum nl80211_iftype iftype = nla_type(nl_mode);
            if (iftype <= NL80211_IFTYPE_MAX && ifmodes[iftype])
                printf("%s: supported\n", ifmodes[iftype]);
        }
	}

    if (ac_support)
        printf("ac: supported\n");
    if (n_support)
        printf("n: supported\n");
    if (bg_support)
        printf("bg: supported\n");
    if (band_5GHz_support) 
        printf("band_5GHz: supported\n");

    return 0;
}

int main(int argc, char **argv)
{
	struct nl80211_state nlstate;
	int err;

	err = nl80211_init(&nlstate);
	if (err)
		return 1;

	struct nl_cb *cb;
	struct nl_cb *s_cb;
	struct nl_msg *msg;

	msg = nlmsg_alloc();
	if (!msg) {
		fprintf(stderr, "failed to allocate netlink message\n");
		return 2;
	}

	cb = nl_cb_alloc(NL_CB_DEFAULT);
	s_cb = nl_cb_alloc(NL_CB_DEFAULT);
	if (!cb || !s_cb) {
		fprintf(stderr, "failed to allocate netlink callbacks\n");
		err = 2;
		goto out_free_msg;
	}

	genlmsg_put(msg, 0, 0, nlstate.nl80211_id, 0,
		    NLM_F_DUMP, NL80211_CMD_GET_WIPHY, 0);

	nl_socket_set_cb(nlstate.nl_sock, s_cb);

	err = nl_send_auto_complete(nlstate.nl_sock, msg);
	if (err < 0)
		goto out;

	err = 1;

	nl_cb_err(cb, NL_CB_CUSTOM, error_handler, &err);
	nl_cb_set(cb, NL_CB_FINISH, NL_CB_CUSTOM, finish_handler, &err);
    nl_cb_set(cb, NL_CB_VALID, NL_CB_CUSTOM, print_phy_handler, &err);

	while (err > 0)
		nl_recvmsgs(nlstate.nl_sock, cb);
 out:
	nl_cb_put(cb);
 out_free_msg:
	nlmsg_free(msg);

	if (err < 0)
		fprintf(stderr, "command failed: %s (%d)\n", strerror(-err), err);

	nl80211_cleanup(&nlstate);

	return err;
}
