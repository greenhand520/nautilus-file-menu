from gi import require_version

require_version('Gtk', '4.0')
from gi.repository import Gtk, Gdk


def connect_spin_keys(spin, win, ok_btn):
    """Connect Enter/Escape on a SpinButton's internal Text widget."""
    text_widget = spin.get_first_child()
    if text_widget is None:
        text_widget = spin

    def _on_key(ctrl, keyval, keycode, state):
        if keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter):
            ok_btn.activate()
            return True
        if keyval == Gdk.KEY_Escape:
            win.destroy()
            return True
        return False

    controller = Gtk.EventControllerKey()
    controller.connect("key-pressed", _on_key)
    text_widget.add_controller(controller)
