===========================
plainbox-session-export (1)
===========================

.. argparse::
    :ref: plainbox.impl.box.get_parser_for_sphinx
    :prog: plainbox
    :manpage:
    :path: session export

    The `plainbox session export` command allows to export any existing session
    (that can be still resumed) with any set of exporter / exporter option
    combinations.

    The exported session representation can be printed to stdout (default) or
    saved to a specified file. You can pass a question mark (?) to both
    ``--output-format`` and ``--output-options`` for a list of available
    values.

Limitations
===========

Sessions that cannot be resumed cannot be exported. Two common causes for that
are known.

First of all, a session can fail to resume because of missing or changed job
definitions. For that you need to re-install the exact same provider version as
was available on the machine that generated the session you are trying to work
with.

The second case is when a session was copied from another machine and some of
the log files are pointing to a different users' account. This can be worked
around by providing appropriate symbolic links from /home/some-user/ to
/home/your-user/
