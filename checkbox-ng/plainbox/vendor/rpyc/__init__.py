"""
::

         #####    #####             ####
        ##   ##  ##   ##           ##             ####
        ##  ##   ##  ##           ##                 #
        #####    #####   ##   ##  ##               ##
        ##  ##   ##       ## ##   ##                 #
        ##   ##  ##        ###    ##              ###
        ##   ##  ##        ##      #####
     -------------------- ## ------------------------------------------
                         ##

Remote Python Call (RPyC)
Licensed under the MIT license (see `LICENSE` file)

A transparent, symmetric and light-weight RPC and distributed computing
library for python.

Usage::

    >>> import rpyc
    >>> c = rpyc.connect_by_service("SERVICENAME")
    >>> print c.root.some_function(1, 2, 3)

Classic-style usage::

    >>> import rpyc
    >>> # `hostname` is assumed to be running a slave-service server
    >>> c = rpyc.classic.connect("hostname")
    >>> print c.execute("x = 5")
    None
    >>> print c.eval("x + 2")
    7
    >>> print c.modules.os.listdir(".")       #doctest: +ELLIPSIS
    [...]
    >>> print c.modules["xml.dom.minidom"].parseString("<a/>")   #doctest: +ELLIPSIS
    <xml.dom.minidom.Document instance at ...>
    >>> f = c.builtin.open("foobar.txt", "rb")     #doctest: +SKIP
    >>> print f.read(100)     #doctest: +SKIP
    ...

"""
# flake8: noqa: F401
from plainbox.vendor.rpyc.core import (SocketStream, TunneledSocketStream, PipeStream, Channel,
                       Connection, Service, BaseNetref, AsyncResult, GenericException,
                       AsyncResultTimeout, VoidService, SlaveService, MasterService, ClassicService)
from plainbox.vendor.rpyc.utils.factory import (connect_stream, connect_channel, connect_pipes,
                                connect_stdpipes, connect, ssl_connect, discover, connect_by_service, connect_subproc,
                                connect_thread, ssh_connect)
from plainbox.vendor.rpyc.utils.helpers import async_, timed, buffiter, BgServingThread, restricted
from plainbox.vendor.rpyc.utils import classic
from plainbox.vendor.rpyc.version import version as __version__

from plainbox.vendor.rpyc.lib import setup_logger, spawn
from plainbox.vendor.rpyc.utils.server import OneShotServer, ThreadedServer, ThreadPoolServer, ForkingServer

__author__ = "Tomer Filiba (tomerfiliba@gmail.com)"

globals()['async'] = async_     # backward compatibility
