Custom Frontend Extra Path Environment
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

To define extra path environment variables that can be accessed globally by
all tests in a frontend create a file in the root of the snap
called ``extra_path_environment``.
All paths in the file are relative to the root of your snap and will be
correctly made absolute before passing them to your tests.

Example:

.. code-block::

  # This library we are installing in a weird location
  LD_LIBRARY_PATH += path to library
  # Additionally we need to define this very important path
  SOME_PATH += /very/important/location

.. note::

   This mechanism is designed to define PATH variables specifically to
   address issues in packaging. Do not use this for general purpose environment
   variable setting.

.. warning::

   All variables paths point to the root of your snap at runtime, regardless
   if you prefix them with a ``/`` or not.
