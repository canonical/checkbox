#                                               -*- Autoconf -*-
# Process this file with autoconf to produce a configure script.

AC_PREREQ([2.68])
AC_INIT([plainbox-provider-resource], [0.3], [https://bugs.launchpad.net/plainbox-provider-resource/+filebug])
AM_INIT_AUTOMAKE
AC_CONFIG_SRCDIR([80211_resource.c])
AC_CONFIG_HEADERS([config.h])

# Checks for programs.
AC_PROG_CC
# TODO: remove AM_PROG_CC_C_O when Ubuntu 12.04 is no longer supported
AM_PROG_CC_C_O
PKG_PROG_PKG_CONFIG([0.26])

# Checks for libraries.
PKG_CHECK_MODULES([LIBNL], [libnl-3.0 >= 0.26 libnl-genl-3.0 >= 0.26])
AC_SUBST(LIBNL_CFLAGS)
AC_SUBST(LIBNL_LIBS)

# Checks for header files.
AC_CHECK_HEADER([linux/nl80211.h], [], [AC_ERROR([Install linux-libc-dev])])
AC_DEFINE([HAVE_NL80211_BAND_ATTR_VHT_CAPA], [0],
          [Define to 1 if <linux/nl80211.h> defines NL80211_BAND_ATTR_VHT_CAPA])
AC_EGREP_HEADER([NL80211_BAND_ATTR_VHT_CAPA], [linux/nl80211.h],
                [AC_DEFINE([HAVE_NL80211_BAND_ATTR_VHT_CAPA], 1)])
AC_DEFINE([HAVE_NL80211_BAND_ATTR_HT_CAPA], [0],
          [Define to 1 if <linux/nl80211.h> defines NL80211_BAND_ATTR_HT_CAPA])
AC_EGREP_HEADER([NL80211_BAND_ATTR_HT_CAPA], [linux/nl80211.h],
                [AC_DEFINE([HAVE_NL80211_BAND_ATTR_HT_CAPA], 1)])
AC_DEFINE([HAVE_NL80211_BAND_ATTR_VHT_MCS_SET], [0],
          [Define to 1 if <linux/nl80211.h> defines NL80211_BAND_ATTR_VHT_MCS_SET])
AC_EGREP_HEADER([NL80211_BAND_ATTR_VHT_MCS_SET], [linux/nl80211.h],
                [AC_DEFINE([HAVE_NL80211_BAND_ATTR_VHT_MCS_SET], 1)])

# Checks for typedefs, structures, and compiler characteristics.
# TODO: re-enable AC_CHECK_HEADER_STDBOOL when Ubuntu 12.04 is no longer supported
# AC_CHECK_HEADER_STDBOOL
AC_TYPE_UINT32_T

# Checks for library functions.
AC_CHECK_FUNCS([strerror])

AC_CONFIG_FILES([Makefile])
AC_OUTPUT
