======================
plainbox-dev-crash (1)
======================

.. argparse::
    :ref: plainbox.impl.box.get_parser_for_sphinx
    :prog: plainbox
    :manpage:
    :path: dev crash
    :nodefault:

    This command is designed to crash or hang the application.

    Using this command a developer can inspect the built-in development and
    debugging features available in PlainBox.  Specifically, there are several
    options available to the top-level plainbox command (they *have to* be used
    before the ``dev crash`` syntax) that allow to enable one of the following
    actions:

    Jumping Into PDB on Uncaught Exception
    --------------------------------------

    If ``plainbox`` is invoked with the ``--pdb`` command line option then all
    uncaught exceptions are handled by starting a debugger session. Using the
    debugger a developer can inspec the execution stack, including all thre
    threads, local and global variables, etc..

    Jumping into PDB on KeyboardInterrupt
    -------------------------------------

    If ``plainbox`` is invoked with both the ``--pdb`` and the
    ``--debug-interrupt`` command line options then a ``KeyboardInterrupt``
    exception is not ignored, as it usually is, and instead it allowed to
    bubble up the command line implementation call stack until it starts the
    interactive debugger session.

Examples
========

A debugger session on exception::

    plainbox --pdb dev crash --crash

A debugger session on keyboard interrupt::

    plainbox --pdb --debug-interrupt dev crash --hang

See Also
========

:doc:`plainbox-dev`, :doc:`plainbox`, ``pdb3`` (1)
