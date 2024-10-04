Using ``match``
^^^^^^^^^^^^^^^

When a subset of a test plan run fails, it can be expensive to re-run it all.
To help with this, the ``match`` keyword was introduced. It allows you to re-run only a
subset of a test plan.

To only re-run the ``wireless`` portion of the ``sru`` test plan, use the
following launcher:

.. code-block:: ini

  [test plan]
  unit = com.canonical.certification::sru
  forced = yes

  [test selection]
  match = .*wireless.*

To only re-run the WiFi ``bg_np`` and ``ac_np`` tests for ``wlan0``:

.. code-block:: ini
  :emphasize-lines: 7-8

  [test plan]
  unit = com.canonical.certification::sru
  forced = yes

  [test selection]
  match =
    com.canonical.certification::wireless/wireless_connection_open_ac_np_wlan0
    com.canonical.certification::wireless/wireless_connection_open_bg_np_wlan0

To re-run all wireless tests but ``bg_np``:

.. code-block:: ini
  :emphasize-lines: 6-7

  [test plan]
  unit = com.canonical.certification::sru
  forced = yes

  [test selection]
  exclude = .*wireless.*bg_np.*
  match = .*wireless.*

Key features of ``match``:

* All tests in the bootstrap section will always be included
* Test Selection screen is still shown and functional, but only matching tests are shown
* Matched tests pull their dependencies automatically
* ``exclude`` has the priority over ``match``
