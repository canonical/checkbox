import subprocess as sp


def main():
    """
    (manually verified on ubuntu16 ~ 24 including ubuntu core)
    The output of "wpa_supplicant -v" always looks like the following

    wpa_supplicant v2.10
    Copyright (c) 2003-2022, Jouni Malinen <j@w1.fi> and contributors
    """

    wpa_supplicant_version_output = sp.check_output(
        ["wpa_supplicant", "-v"], universal_newlines=True
    )

    # take the 1st line, 2nd word, remove the 'v'
    clean_version_str = wpa_supplicant_version_output.splitlines()[0].split()[
        1
    ][1:]

    print("wpa_supplicant_version: {}".format(clean_version_str))


if __name__ == "__main__":
    main()
