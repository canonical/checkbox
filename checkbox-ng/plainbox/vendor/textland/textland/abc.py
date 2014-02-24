# This file is part of textland.
#
# Copyright 2014 Canonical Ltd.
# Written by:
#   Zygmunt Krynicki <zygmunt.krynicki@canonical.com>
#
# Textland is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3,
# as published by the Free Software Foundation.
#
# Textland is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Textland.  If not, see <http://www.gnu.org/licenses/>.

from abc import abstractmethod, ABCMeta

from .bits import Size
from .events import Event
from .image import TextImage


class IApplication(metaclass=ABCMeta):
    """
    Interface for all applications.

    Applications are simple objects that react to events by repainting
    their buffer. Each application has exactly one full-screen buffer.
    """

    @abstractmethod
    def consume_event(self, event: Event) -> TextImage:
        """
        Send an event to the controller.

        :param event:
            Event that the controller should handle

        This method is called whenever the application should react to an
        event. The application may raise StopIteration to ask the display to
        exit.
        """


# TODO: this is mis-named, rename it
class IDisplay(metaclass=ABCMeta):
    """
    Abstract display system.
    """

    @abstractmethod
    def run(self, app: IApplication) -> None:
        """
        Run forever, feeding events to the controller
        the controller can raise StopIteration to "quit"
        """


class IView(metaclass=ABCMeta):
    """
    Work-in-progress on views that applications can use
    """

    @abstractmethod
    def render(self, size: Size) -> TextImage:
        """
        Render this view to a new image of the specified size
        """
