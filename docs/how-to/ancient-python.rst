.. _iterating_ancient_python:

Iterating on ancient versions of Python
=======================================

Some of the failures that we encounter only arise in ancient versions of
python. It can be non-trivial to install these versions on a
production machine, and possibly not desirable. In these situations LXD comes
to our aid.

Save the following ``cloud-init`` file in ``python36_cloud_init.yaml``:

.. code-block:: yaml

  #cloud-config
  runcmd:
    - add-apt-repository --yes ppa:checkbox-dev/edge
    - apt update -q -y
    - apt install -q -y "python3.6" "python3.6-venv" "python3.6-dev" gcc "flake8" "shellcheck"
    - python3.6 -m ensurepip
    - python3.6 -m venv /root/venv
    - PIP_TRUSTED_HOST="pypi.python.org pypi.org files.pythonhosted.org" /root/venv/bin/python3.6 -m pip install --upgrade "pip<21"
    - git clone https://github.com/canonical/checkbox /root/checkbox
    - PIP_TRUSTED_HOST="pypi.python.org pypi.org files.pythonhosted.org" /root/venv/bin/python3.6 -m pip install -e /root/checkbox/checkbox-ng
    - PIP_TRUSTED_HOST="pypi.python.org pypi.org files.pythonhosted.org" /root/venv/bin/python3.6 -m pip install -e /root/checkbox/checkbox-support
    - /root/venv/bin/python3.6 /root/checkbox/providers/resource/manage.py develop
    - /root/venv/bin/python3.6 /root/checkbox/providers/base/manage.py develop

Use ``lxc`` to launch a ``focal`` container with the ``cloud-init`` file
provided, log into it and wait for ``cloud-init`` to finish preparing your
environment

.. code-block:: none

   $ lxc launch ubuntu:focal python36 --config=user.user-data="$(cat python36_cloud_init.yaml)"
   $ lxc shell python36
   root@python36:~# cloud-init status --wait
   ...........................................status: done

The ``cloud-init`` file has prepared you a fresh clone of the Checkbox repo in
``/root/checkbox``, it has created a venv you can use in ``/root/venv`` with
Python3.6 and it has developed the ``resource`` and ``base`` provider. You
should now be able to iterate on your tests!

.. note::

  Python 3.6 is no longer in the deadsnakes PPA. We have added
  it to the checkbox-dev PPA to still be able to run the tests.
