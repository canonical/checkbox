How to migrate PXU units away from Jinja2
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

This guide shows you how to remove Jinja2 templates from your PXU units so
they can be accurately translated into YAML.

.. note::

   Textual fields like ``purpose``, ``steps`` and ``verification`` may need to
   use jinja more often, to give platform-specific instructions. Try to keep
   the usage to a minimum.

.. note::

   This document will help you fix your PXUs before calling the translator,
   therefore all examples here will be in PXU format. Everything should be
   easily transposed into YAML but beware before copy pasting!

Values templating
=================

Units using Jinja to template values from resources can transition to normal
formatting as follows:

.. code-block:: none

  [...]
  template-resource: some
  template-engine: jinja2
  command:
    echo {{ name }}

Can be expressed as:

.. code-block:: none

  [...]
  template-resource: some
  command:
    echo {name}

Units that use Jinja special ``__...___`` variables like ``__system_env__`` or
``__checkbox_env__`` although their usage should be rarely necessary.

Command section
===============

Command section usage of jinja is especially dangerous and there is little one
can do with jinja that is not possible without.

Conditionals
------------

Transitioning away from conditionals is just a matter of re-writing the code as
follows:

.. code-block:: none

  [...]
  command:
    {%- if __on_ubuntucore__ %}
      echo "on ubuntu core"
    {%- else %}
      echo "not on ubuntu core"
    {% endif -%}

Can be rewritten as:

.. code-block:: none

  [...]
  command:
    if [ "$CHECKBOX_RUNNING_STRICT_SNAP" = "1" ]; then
      echo "on ubuntu core"
    else
      echo "not on ubuntu core"
    fi

Similarly for ``__checkbox_env__`` or ``__system_env__``:

.. code-block:: none

  [...]
  command:
    {%- if __checkbox_env__.get("SOME") == "foo" %}
      echo "SOME envvar is foo"
    {%- else %}
      echo "SOME envvar is not foo"
    {%- endif %}

Can be rewritten as:

.. code-block:: none

  environ:
    - SOME
  command:
    if [ "$SOME" = "foo" ]; then
      echo "SOME envvar is foo"
    else
      echo "SOME envvar is not foo"
    fi

Comments
--------

Use bash comments as follows:

.. code-block:: none

  command:
    {% some comment %}

Can be rewritten as:

.. code-block:: none

  command:
    # some comment

Requires section
================

Using conditionals in the requires field hides requirements from the user.
Flatten these into standard boolean logic.

Conditionals
------------

Conditionals in the requires field "hide" part of the requirement away from
the user/report, leading to confusion.

To remove ``__on_ubuntucore__``:

.. code-block::

  requires:
    a.a == 'a'
    {%- if __on_ubuntucore__ %}
    b.b == 'b'
    {%- else %}
    c.c == 'c'
    {% endif -%}

Can be written as:

.. code-block::

  requires:
    a.a == 'a'
    environment.CHECKBOX_RUNNING_STRICT_SNAP != 1 or b.b == 'b'
    environment.CHECKBOX_RUNNING_STRICT_SNAP == 1 or c.c == 'c'

To remove usages of ``__checkbox_env__`` or ``__system_env__``:

.. code-block::

  requires:
    {%- if __checkbox_env__.get("A") == "A" %}
    b.b == "b"
    {%- endif %}

Can be changed to:

.. code-block::

  requires:
    environment.A != "A" or b.b == "b"

.. note::
  Even though ``__checkbox_env__`` and ``__system_env__`` are not the same as
  environment, most of the times environment is a superset of both. The only
  exception is when an environment variable is present in both, in that case,
  the system environment prevails.
