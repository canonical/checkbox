===================
Installing checkbox
===================

In order to install checkbox you are going to need two parts, a ``runtime``
and a ``fronted``.

First we need to install the ``runtime``::

   $ sudo snap install checkbox22
   Ensure prerequisites for "checkbox22" are available
   Fetch and check assertions for snap "checkbox22"
   Mount snap "checkbox22"
   Mount snap "checkbox22"
   Copy snap "checkbox22" data
   Run configure hook of "checkbox22" snap if present
   checkbox22 X.Y.Z from Canonical Certification Team (ce-certification-qa) installed

Now that we have the ``checkbox22`` runtime, we need a ``frontend``, to install it
run the following::

  $ sudo snap install checkbox --channel uc22
  Ensure prerequisites for "checkbox" are available
  Mount snap "checkbox"
  Copy snap "checkbox" data
  Automatically connect eligible plugs and slots of snap "checkbox"
  Start snap "checkbox" services
  Run configure hook of "checkbox" snap if present
  checkbox (22.04/stable) X.Y.Z from Canonical Certification Team (ce-certification-qa) installed

.. note::
  If you are unsure about what ``frontend`` you should use, consider
  reading this page: `ref_which_snap`_

Now that we have installed both we can launch checkbox running:

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

If your screen is similar to this one, rejoyce! You can start using
checkbox! For now you can close it using ``Ctrl+C``.

You may have noticed that this tutorial has guided you to install a specific version of
checkbox: ``checkbox22``. We offer more, please refer to `ref_which_snap`_ to know which
one you should use.
