TextLand
========

TextLand is a portable console textual frame-buffer-like display system. It
offers portable character-attribute matrix and input event system. TextLand is
not a widget library, it doesn't have concepts of windows, buttons or labels.
Any widget library that can render to TextLand buffers can be used to build
classical text widget applications.

Example
=======

See demos in the top-level directory

Environment
===========

TEXTLAND_DISPLAY can be set to one of the following strings:

 * ``curses`` (default): to use the ncurses interface
 * ``print``: to use portable printer 80x25 "display"
 * ``test``: to use a off-screen display that replays injected test events and
   records all the screens that were "displayed"

Supported Platforms
===================

Linux:
    Keyboard events, display resize events, no mouse events yet.  Bold,
    underline and reverse video character attributes. Standard 16+8 colors
    available (foreground+background).

Windows:
    Port is in the works, text display and console attributes work. Mouse
    events and resize events are in the works.

OSX:
    Same as Linux with the exception of the display resize event which is not
    supported in the same way on the OSX curses library. Should be fixed later
    on but there is no active OSX developer yet.
