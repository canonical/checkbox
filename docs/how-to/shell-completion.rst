===========================================
How to enable shell completion for Checkbox
===========================================

``checkbox-cli`` can complete subcommands, options, option values, file paths,
test plan IDs and unit IDs when you press :kbd:`Tab`. Completion is available
for Bash, Zsh and Fish.

Test plan and unit IDs depend on the providers installed on the system, and
looking them up can take a second or two. The first lookup is saved to a cache
in ``${XDG_CACHE_HOME:-~/.cache}/checkbox/completion/``, so later completions
are instant. When the cache is older than one minute, Checkbox serves it and
refreshes it in the background, so newly installed or changed test plans and
units appear on the next :kbd:`Tab` press after the refresh. To force a fresh
lookup, delete the cache directory:

.. code-block:: console

   $ rm -rf ~/.cache/checkbox/completion

Debian package
==============

The ``checkbox-ng`` package installs the completion scripts for all three
shells in their standard locations. Open a new shell and completion works
out of the box:

.. code-block:: console

   $ checkbox-cli li<Tab>
   list  list-bootstrapped
   $ checkbox-cli expand com.canonical.certification::6low<Tab>

In Bash, this requires the ``bash-completion`` package, which is installed by
default on Ubuntu.

Checkbox snap
=============

Bash
----

The Checkbox frontend snap ships a Bash completer, so completion works for
``checkbox.checkbox-cli`` as soon as the snap is installed:

.. code-block:: console

   $ checkbox.checkbox-cli tp-export <Tab>

Zsh and Fish
------------

Snapd only supports Bash completion. To make up for this, the classic Checkbox
snap puts small loader scripts in ``/usr/local/share/zsh/site-functions`` and
``/usr/local/share/fish/vendor_completions.d`` when it is installed or
refreshed, and removes them when the snap is removed. Zsh and Fish search these
directories by default, so open a new shell and completion works for
``checkbox.checkbox-cli``. The loaders always use the completion scripts of
the installed snap revision.

If your Zsh configuration doesn't search
``/usr/local/share/zsh/site-functions`` (for example, because it overrides
``fpath``), or you use the Ubuntu Core version of the snap, load the
completion script printed by ``checkbox.checkbox-cli completion`` from your
shell startup file instead.

If Zsh prints ``_checkbox-cli: function definition file not found``, its
completion cache is out of date. Delete it and start a new shell:

.. code-block:: console

   $ rm -f ~/.zcompdump*
   $ exec zsh

For Zsh, add the following line to ``~/.zshrc``, after ``compinit``:

.. code-block:: none

   source <(checkbox.checkbox-cli completion zsh)

For Fish, add the following line to ``~/.config/fish/config.fish``:

.. code-block:: none

   checkbox.checkbox-cli completion fish | source

Installing from source
======================

If you installed Checkbox with ``pip`` or in a virtual environment, load the
completion script for your shell the same way:

.. code-block:: none

   # ~/.bashrc
   source <(checkbox-cli completion bash)
   # ~/.zshrc, after compinit
   source <(checkbox-cli completion zsh)
   # ~/.config/fish/config.fish
   checkbox-cli completion fish | source
