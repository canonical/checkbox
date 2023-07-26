.. _installing_checkbox:

===================
Installing Checkbox
===================

In order to install Checkbox you are going to need two parts, a ``runtime``
and a ``frontend``.

First we need to install the ``runtime``, this tutorial will use the ``checkbox22``
runtime on Ubuntu22. We also offer versions for ``16``, ``18`` and ``20``
Use the one that matches your Ubuntu version or refer to :ref:`ref_which_snap` to
understand and pick the one that fits your needs::

   $ sudo snap install checkbox22
   [...]
   checkbox22 X.Y.Z from Canonical Certification Team (ce-certification-qa) installed

Now that we have the ``checkbox22`` runtime, we need a ``frontend``, to install it
run the following::

  $ sudo snap install checkbox --channel uc22
  [...]
  checkbox (22.04/stable) X.Y.Z from Canonical Certification Team (ce-certification-qa) installed

.. note::
  There are multiple frontends as you may discover by typing ``snap info checkbox``.
  If you are unsure about what ``frontend`` you should use, consider
  reading this page: :ref:`ref_which_snap`, but for the scope of this tutorial the one
  installed in this snipped is enough.

Now that we have installed both we can launch Checkbox running:

.. code-block:: none

  $ checkbox.checkbox-cli
  Select test plan
  ┌─────────────────────────────────────────────────────────────────────────────────────┐
  │ ( ) (Deprecated) Fully Automatic Client Certification Tests                         │
  │ ( ) 18.04 Server Certification Full                                                 │
  │ ( ) 18.04 Server Certification Functional                                           │
  │ ( ) 18.04 System On Chip Certification (For SoC Testing)                            │
  │ ( ) 18.04 Virtual Machine Full (For Hypervisors)                                    │
  │ ( ) 20.04 Server Certification Full                                                 │
  └─────────────────────────────────────────────────────────────────────────────────────┘
  Press <Enter> to continue                                                      (H) Help

If your screen is similar to this one, rejoice! You can start using
Checkbox! For now you can close it using ``Ctrl+C``.

You may have noticed that this tutorial has guided you to install a specific version of
Checkbox: ``checkbox22``. We offer more, please refer to :ref:`ref_which_snap` to know which
one you should use.
