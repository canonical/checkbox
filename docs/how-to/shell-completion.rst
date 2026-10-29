===========================================
How to enable shell completion for Checkbox
===========================================

``checkbox-cli`` can complete subcommands, options, option values, file paths,
test plan IDs and unit IDs when you press :kbd:`Tab`. Completion is available
for Bash, Zsh and Fish.

Test plan and unit IDs depend on the providers installed on the system, so
Checkbox looks them up each time you complete them. This can take a second or
two on systems with many providers.

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

Snapd only supports Bash completion. For Zsh and Fish, load the completion
script printed by ``checkbox.checkbox-cli completion`` from your shell startup
file.

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
