#!/usr/bin/env python3

import sys
import os
import argparse

import gi

gi.require_version("Gdk", "3.0")
gi.require_version("GdkPixbuf", "2.0")

from gi.repository import (  # noqa: E402
    Gio,  # pyright: ignore[reportMissingModuleSource]
    GLib,  # pyright: ignore[reportMissingModuleSource]
    Gdk,  # pyright: ignore[reportMissingModuleSource]
)

try:
    # GioUnix doesn't exist on 22.04 and older
    gi.require_version("GioUnix", "2.0")
    from gi.repository import (
        GioUnix,  # pyright: ignore[reportMissingModuleSource]
    )
except (ValueError, ImportError):
    # ValueError comes from gi.require_version
    # ImportError comes from the actual import
    # keep the variable, test for null during runtime
    GioUnix = None

APP_ID = "org.gnome.Screenshot"


class XdgPortalScreenshotter:
    """

    Use xdg-desktop-portal's org.freedesktop.portal.Screenshot
    to take a screenshot

    This is intended for wayland session on 24.04 and newer
    """

    RESPONSE_TIMEOUT_SECONDS = 5

    def __init__(self, app_id: str):
        self.app_id = app_id
        self._desktop_file_path = None
        self._permission_app_id = app_id
        self._is_snap = self._running_in_snap()
        if self._is_snap:
            instance_name = os.environ.get(
                "SNAP_INSTANCE_NAME", os.environ.get("SNAP_NAME")
            )
            self._permission_app_id = "snap.{}".format(instance_name)

    @staticmethod
    def _running_in_snap() -> bool:
        return bool(
            os.environ.get("SNAP_NAME") or os.environ.get("SNAP_INSTANCE_NAME")
        )

    def setup(self):
        if self._is_snap:
            return
        self._desktop_file_path = self._ensure_desktop_file()

    def cleanup(self, conn: "Gio.DBusConnection | None"):
        """This undoes everything in setup()

        :param conn: dbus conn created by Gio.Application.get_dbus_connection
        """
        if conn is not None:
            self._delete_permission(conn)
        self._remove_desktop_file()

    def capture(
        self, conn: Gio.DBusConnection, output_path: str, include_cursor: bool
    ) -> bool:
        """Attempt the screenshot via the portal. Returns True if this tier
        handled the request (whether it succeeded, failed, or the user
        cancelled) - False means "not available, try the next tier"."""
        try:
            if not self._is_snap:
                self._register(conn)
            self._pre_authorize(conn)
        except GLib.Error as e:
            print(
                "[portal] setup failed, skipping portal path:",
                e.message,
                file=sys.stderr,
            )
            return False

        try:
            return self._take_screenshot(conn, output_path)
        except GLib.Error as e:
            print(
                "[portal] Screenshot call failed:",
                e.message,
                file=sys.stderr,
            )
            return False

    def _desktop_file_dest(self):
        data_home = os.environ.get(
            "XDG_DATA_HOME", os.path.expanduser("~/.local/share")
        )
        return os.path.join(
            data_home, "applications", "{}.desktop".format(self.app_id)
        )

    def _desktop_entry_content(self):
        script_path = os.path.abspath(sys.argv[0])
        return (
            "\n".join(
                [
                    "[Desktop Entry]",
                    "Name=Screenshotter",
                    "Exec=python3 {}".format(script_path),
                    "Type=Application",
                ]
            )
            + "\n"
        )

    def _ensure_desktop_file(self):
        """
        Creates a desktop file temporarily for this script such that we can 
        _pre_authorize() to take screenshots non-interactively

        :raises RuntimeError: no GioUnix
        :raises RuntimeError: the newly created file is not picked up by GLib
        :return: where the desktop file was created
        """        
        path = self._desktop_file_dest()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write(self._desktop_entry_content())

        if not GioUnix:
            raise RuntimeError(
                "GioUnix must be imported for {} to work".format(
                    XdgPortalScreenshotter.__name__
                )
            )

        app_info = GioUnix.DesktopAppInfo.new("{}.desktop".format(self.app_id))
        if app_info is None:
            raise RuntimeError(
                "Desktop file at {} not found by GLib".format(path),
            )

        return path

    def _remove_desktop_file(self):
        if not self._desktop_file_path:
            return
        try:
            os.remove(self._desktop_file_path)
        except OSError:
            pass
        self._desktop_file_path = None

    def _register(self, conn: Gio.DBusConnection):
        empty_opts = GLib.Variant("a{sv}", {})
        params = GLib.Variant.new_tuple(
            GLib.Variant.new_string(self.app_id),
            empty_opts,
        )
        conn.call_sync(
            "org.freedesktop.portal.Desktop",
            "/org/freedesktop/portal/desktop",
            "org.freedesktop.host.portal.Registry",
            "Register",
            params,
            None,
            Gio.DBusCallFlags.NONE,
            -1,
            None,
        )

    def _pre_authorize(self, conn: Gio.DBusConnection):
        perms = GLib.Variant.new_array(
            GLib.VariantType.new("s"),
            [GLib.Variant.new_string("yes")],
        )
        params = GLib.Variant.new_tuple(
            GLib.Variant.new_string("screenshot"),
            GLib.Variant.new_boolean(True),
            GLib.Variant.new_string("screenshot"),
            GLib.Variant.new_string(self._permission_app_id),
            perms,
        )
        conn.call_sync(
            "org.freedesktop.impl.portal.PermissionStore",
            "/org/freedesktop/impl/portal/PermissionStore",
            "org.freedesktop.impl.portal.PermissionStore",
            "SetPermission",
            params,
            None,
            Gio.DBusCallFlags.NONE,
            -1,
            None,
        )

    def _delete_permission(self, conn: Gio.DBusConnection):
        params = GLib.Variant.new_tuple(
            GLib.Variant.new_string("screenshot"),
            GLib.Variant.new_string("screenshot"),
            GLib.Variant.new_string(self._permission_app_id),
        )
        try:
            conn.call_sync(
                "org.freedesktop.impl.portal.PermissionStore",
                "/org/freedesktop/impl/portal/PermissionStore",
                "org.freedesktop.impl.portal.PermissionStore",
                "DeletePermission",
                params,
                None,
                Gio.DBusCallFlags.NONE,
                -1,
                None,
            )
        except Exception:
            pass

    def _take_screenshot(
        self, conn: Gio.DBusConnection, output_path: str
    ) -> bool:
        options = GLib.Variant(
            "a{sv}",
            {
                "interactive": GLib.Variant("b", False),
                "target": GLib.Variant("u", 1),
            },
        )
        params = GLib.Variant.new_tuple(
            GLib.Variant.new_string(""),
            options,
        )
        result = conn.call_sync(
            "org.freedesktop.portal.Desktop",
            "/org/freedesktop/portal/desktop",
            "org.freedesktop.portal.Screenshot",
            "Screenshot",
            params,
            GLib.VariantType.new("(o)"),
            Gio.DBusCallFlags.NONE,
            -1,
            None,
        )

        # this is an object path string
        # /org/freedesktop/portal/desktop/request/1_483/t
        handle = str(result[0])

        loop = GLib.MainLoop()
        outcome = {}

        def on_response(connection, sender, path, iface, signal, params):
            outcome["response"], outcome["results"] = params
            if loop.is_running():
                loop.quit()

        sub_id = conn.signal_subscribe(
            None,
            "org.freedesktop.portal.Request",
            "Response",
            handle,
            None,
            Gio.DBusSignalFlags.NONE,
            on_response,
        )

        def on_timeout():
            outcome["timed_out"] = True
            if loop.is_running():
                loop.quit()
            return GLib.SOURCE_REMOVE

        timeout_id = GLib.timeout_add_seconds(
            self.RESPONSE_TIMEOUT_SECONDS, on_timeout
        )

        loop.run()

        conn.signal_unsubscribe(sub_id)
        if "timed_out" not in outcome:
            GLib.source_remove(timeout_id)

        if outcome.get("timed_out"):
            print(
                "[portal] timed out waiting for a Screenshot response",
                "(no working portal backend?)",
                file=sys.stderr,
            )
            return False

        response = outcome["response"]
        results = outcome["results"]

        if response == 0:
            uri = str(results.get("uri"))

            if not uri:
                print("[portal] Error: no URI in response", file=sys.stderr)
                return False

            src = Gio.File.new_for_uri(uri)
            dst = Gio.File.new_for_path(output_path)
            src.copy(dst, Gio.FileCopyFlags.OVERWRITE, None, None, None)

            print(output_path)
            return True
        elif response == 1:
            # The user explicitly cancelled the portal's screenshot dialog;
            # that's a real answer, not a missing feature, so don't fall
            # back to the other tiers.
            print("Screenshot cancelled", file=sys.stderr)
            return True
        else:
            print(
                "[portal] Screenshot failed (response={})".format(response),
                file=sys.stderr,
            )
            return False


class GnomeDbusScreenshotter:
    """Tier 2: org.gnome.Shell.Screenshot, called directly.

    Works on older GNOME/X11 sessions (e.g. Ubuntu 18.04-24.04) where the
    portal isn't installed, or has no working backend, but GNOME Shell's own
    D-Bus interface is still reachable without a permission dance.
    """

    def capture(
        self, conn: Gio.DBusConnection, output_path: str, include_cursor: bool
    ) -> bool:
        print(
            "starting gnome dbus capture",
            output_path,
            "include cursor?",
            include_cursor,
        )
        params = GLib.Variant.new_tuple(
            GLib.Variant.new_boolean(include_cursor),
            GLib.Variant.new_boolean(True),  # flash
            GLib.Variant.new_string(output_path),
        )
        try:
            success, filename_used = conn.call_sync(
                "org.gnome.Shell",
                "/org/gnome/Shell/Screenshot",
                "org.gnome.Shell.Screenshot",
                "Screenshot",
                params,
                GLib.VariantType.new("(bs)"),
                Gio.DBusCallFlags.NONE,
                -1,
                None,
            )
        except GLib.Error as e:
            # No org.gnome.Shell.Screenshot available (e.g. Ubuntu 16.04's
            # Unity session doesn't run gnome-shell), or newer GNOME denies
            # unsandboxed callers. Let the caller fall back to X11.
            print(
                "[shell] org.gnome.Shell.Screenshot D-Bus call failed:",
                e.message,
                "(domain={}, code={})".format(e.domain, e.code),
                file=sys.stderr,
            )
            return False

        if success:
            print(filename_used)
            return True

        print("[shell] Screenshot failed", file=sys.stderr)
        return False


class X11Screenshotter:
    """Tier 3: manual GDK/X11 root-window grab.

    The final fallback for sessions with neither a portal nor gnome-shell
    (e.g. Unity on Ubuntu 16.04). Since a plain root-window grab doesn't
    include the mouse pointer, the cursor is composited in separately via
    the XFixes extension when requested.
    """

    def capture(self, output_path: str, include_cursor: bool) -> bool:
        try:
            root = Gdk.get_default_root_window()
            if root is None:
                raise RuntimeError(
                    "No default root window (not running under X11?)"
                )

            width = root.get_width()
            height = root.get_height()
            pixbuf = Gdk.pixbuf_get_from_window(root, 0, 0, width, height)
            if pixbuf is None:
                raise RuntimeError("Failed to grab pixbuf from root window")

            pixbuf.savev(output_path, "png", [], [])
        except (GLib.Error, RuntimeError) as e:
            print("[x11] fallback screenshot failed:", e, file=sys.stderr)
            return False

        print(output_path)
        return True


class ScreenshotterApp(Gio.Application):
    def __init__(self):
        super().__init__(
            application_id=APP_ID,
            flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE,
        )
        self.output_path = "portal-screenshot.png"
        self.include_cursor = False

        self._portal = XdgPortalScreenshotter(APP_ID)
        self._gnome_dbus = GnomeDbusScreenshotter()
        self._x11 = X11Screenshotter()

    def do_command_line(self, command_line: Gio.ApplicationCommandLine):
        parser = argparse.ArgumentParser(
            description="Take a screenshot via xdg-desktop-portal, falling "
            + "back to org.gnome.Shell.Screenshot and then raw X11",
        )
        parser.add_argument(
            "-o",
            "--output",
            default="portal-screenshot.png",
            help="Output file path",
        )
        parser.add_argument(
            "-p",
            "--include-pointer",
            action="store_true",
            help="Include the mouse cursor in the screenshot",
        )
        args = parser.parse_args(command_line.get_arguments()[1:])
        self.output_path = str(args.output)
        self.include_cursor = bool(args.include_pointer)

        self._portal.setup()
        self.activate()
        return 0

    def do_activate(self):
        """The main() function

        Since we can't reliably know what the host ubuntu version is,
        we will try portal -> gnome dbus -> raw 11 in that order

        :raises RuntimeError: failed to get dbus connection
        """
        self.hold()
        conn = self.get_dbus_connection()
        if not conn:
            raise RuntimeError("Failed to get dbus connection")
        try:
            if not self._portal.capture(
                conn, self.output_path, self.include_cursor
            ):
                if not self._gnome_dbus.capture(
                    conn, self.output_path, self.include_cursor
                ):
                    self._x11.capture(self.output_path, self.include_cursor)
        except Exception as e:
            print("Error: {}".format(e), file=sys.stderr)
        finally:
            self.release()

    def do_shutdown(self):
        conn = self.get_dbus_connection()
        self._portal.cleanup(conn)
        Gio.Application.do_shutdown(self)


def main():
    app = ScreenshotterApp()
    app.run(sys.argv)


if __name__ == "__main__":
    main()

