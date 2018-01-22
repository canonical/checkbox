=========================
plainbox-session-list (1)
=========================

.. argparse::
    :ref: plainbox.impl.box.get_parser_for_sphinx
    :prog: plainbox
    :manpage:
    :path: session list

    The `plainbox session list` command simply prints a list of available
    sessions. Each session has the following attributes displayed:

    storage identifier:
        A randomly-looking identifier string starting with 'pbox-' that
        identifies the session in the repository it comes from. The repository
        is typically typically specific to the user's home directory:
        ``$XDG_CACHE_HOME/plainbox/sessions``.

    app:
        The name of the application that created the session.  Typically
        `plainbox` or `checkbox`. Plainbox only resumes sessions it has itself
        created.

    flags:
        A list of flags. Existing flags are:

        incomplete:
            The session has some jobs left to run. Sessions with this flag can
            be resumed

        submitted:
            The session was complete and the results were processed somehow.
            Typically this means they were saved to a file or sent to the
            certification website.

        Note that other flags are possible and they are perfectly fine.
        Applications can define their own flags that are not documented here or
        even understood by the core.

    title:
        An arbitrary "title" of the session. Plainbox typically uses the
        command line that was used to launch the session but other applications
        may come up with more interesting titles. Plainbox also uses the title
        to match find a possible resume candidate.
