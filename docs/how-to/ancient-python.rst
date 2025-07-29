.. _iterating_ancient_python:

Iterating on ancient versions of Python
=======================================

Some of the failures that we encounter only arise in ancient versions of
python. It can be non-trivial to install these versions on a
production machine, and possibly not desirable. In these situations LXD comes
to our aid.

Save the following ``cloud-init`` file in ``python35_cloud_init.yaml``:

.. code-block:: yaml

  #cloud-config
  runcmd:
    - add-apt-repository --yes ppa:deadsnakes/ppa
    - apt update -q -y
    - apt install -q -y "python3.5" "python3.5-venv" "python3.5-dev" gcc "flake8" "shellcheck"
    - python3.5 -m ensurepip
    - python3.5 -m venv /root/venv
    - PIP_TRUSTED_HOST="pypi.python.org pypi.org files.pythonhosted.org" /root/venv/bin/python3.5 -m pip install --upgrade "pip<21"
    - git clone https://github.com/canonical/checkbox /root/checkbox
    - PIP_TRUSTED_HOST="pypi.python.org pypi.org files.pythonhosted.org" /root/venv/bin/python3.5 -m pip install -e /root/checkbox/checkbox-ng
    - PIP_TRUSTED_HOST="pypi.python.org pypi.org files.pythonhosted.org" /root/venv/bin/python3.5 -m pip install -e /root/checkbox/checkbox-support
    - /root/venv/bin/python3.5 /root/checkbox/providers/resource/manage.py develop
    - /root/venv/bin/python3.5 /root/checkbox/providers/base/manage.py develop

Use ``lxc`` to launch a ``focal`` container with the ``cloud-init`` file
provided, log into it and wait for ``cloud-init`` to finish preparing your
environment

.. code-block:: none

   $ lxc launch ubuntu:focal python35 --config=user.user-data="$(cat python35_cloud_init.yaml)"
   $ lxc shell python35
   root@python35:~# cloud-init status --wait
   ...........................................status: done

The ``cloud-init`` file has prepared you a fresh clone of the Checkbox repo in
``/root/checkbox``, it has created a venv you can use in ``/root/venv`` with
Python3.5 and it has developed the ``resource`` and ``base`` provider. You
should now be able to iterate on your tests!
