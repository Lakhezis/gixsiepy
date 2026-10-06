"""Entrada de la aplicación. Ejecutar con /usr/bin/python3 main.py."""

from pathlib import Path
import sys

try:
    import gi
    gi.require_version("Gtk", "4.0")
    gi.require_version("Gdk", "4.0")
    from gi.repository import Gdk, Gtk
except (ImportError, ValueError) as error:
    print(
        "Faltan los bindings de GTK4. Instalalos con:\n"
        "sudo apt install python3-gi gir1.2-gtk-4.0\n"
        "Ejecutá la aplicación con /usr/bin/python3 main.py.\n"
        f"Detalle: {error}", file=sys.stderr,
    )
    raise SystemExit(1)

from ui.window import MainWindow


PROJECT_DIR = Path(__file__).resolve().parent


def load_styles(display):
    provider = Gtk.CssProvider()
    provider.load_from_path(str(PROJECT_DIR / "styles" / "style.css"))
    Gtk.StyleContext.add_provider_for_display(
        display, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
    )
    return provider


class GitGuiApplication(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="org.gixsie.GixsiePy")
        self.window = None

    def do_activate(self):
        if self.window is None:
            if (Gtk.get_major_version(), Gtk.get_minor_version()) < (4, 10):
                print("Esta aplicación necesita GTK 4.10 o posterior.", file=sys.stderr)
                self.quit()
                return
            self.css_provider = load_styles(Gdk.Display.get_default())
            self.window = MainWindow(self, PROJECT_DIR)
            self.window.connect("destroy", self._window_destroyed)
        self.window.present()

    def _window_destroyed(self, _window):
        self.window = None


if __name__ == "__main__":
    raise SystemExit(GitGuiApplication().run(sys.argv))
