import gi
import os
import json
gi.require_version("Gtk", "3.0")
gi.require_version("Vte", "2.91")
from gi.repository import Gtk, Vte, GLib, Gdk

TEMPLATES_FILE = "ctf_templates.json"
VARIABLES_FILE = "ctf_variables.json"

class TerminalApp(Gtk.Window):
    def __init__(self):
        Gtk.Window.__init__(self, title="CTF Toolkit")
        self.set_default_size(1200, 700)
        self.connect("destroy", Gtk.main_quit)
        self.creating_tab = False  # Flag to prevent loop

        # Load data
        self.variables = self.load_json(VARIABLES_FILE, default={"IP": "10.10.14.3", "HOST": "target.local"})
        self.templates = self.load_json(TEMPLATES_FILE, default=[
            {"label": "Nmap Full", "command": "nmap -A <$IP>", "category": "Recon"},
            {"label": "Nikto", "command": "nikto -h <$HOST>", "category": "Web"}
        ])

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.add(vbox)

        # Menu bar
        menu_bar = self.create_menu_bar()
        vbox.pack_start(menu_bar, False, False, 0)

        # Main horizontal split
        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        vbox.pack_start(hbox, True, True, 0)

        # Left panel with scripts inside scrollable area
        self.left_panel = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        left_scroll = Gtk.ScrolledWindow()
        left_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        left_scroll.add(self.left_panel)

        left_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        left_container.pack_start(left_scroll, True, True, 0)

        # Add Script button outside of scrollable/dynamic area
        add_btn = Gtk.Button(label="Add Script")
        add_btn.connect("clicked", self.open_add_script_dialog)
        left_container.pack_start(add_btn, False, False, 10)

        hbox.pack_start(left_container, False, False, 0)

        self.build_variable_ui()

        # 🧱 Add this line before calling build_script_categories()
        self.script_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.left_panel.pack_start(self.script_container, True, True, 0)

        self.build_script_categories()

        # Add script button
        add_btn = Gtk.Button(label="Add Script")
        add_btn.connect("clicked", self.open_add_script_dialog)
        #self.left_panel.pack_start(add_btn, False, False, 10)

        # Terminal area with tab support
        self.notebook = Gtk.Notebook()
        self.notebook.set_scrollable(True)
        hbox.pack_start(self.notebook, True, True, 0)

        self.terminals = []  # Track real terminals
        self.add_addtab_button_tab()
        GLib.idle_add(self.notebook.set_current_page, 0)

        # Detect Add Tab selection
        self.notebook.connect("switch-page", self.on_tab_switched)


    def add_addtab_button_tab(self):
        # Create a simple label "+" instead of a full Gtk.Box with a button
        placeholder = Gtk.Label(label="")  # This is the invisible page
        tab_label = Gtk.Label(label="+")   # This is what shows as the tab text

        self.notebook.append_page(placeholder, tab_label)


        self.creating_tab = True

        # Find the index of the "+" tab (always last one)
        plus_index = self.notebook.get_n_pages() - 1

        terminal = Vte.Terminal()
        terminal.spawn_async(
            Vte.PtyFlags.DEFAULT, None, ["/bin/bash"], [],
            GLib.SpawnFlags.DEFAULT, None, None, -1, None, None
        )

        terminal.set_input_enabled(True)
        terminal.set_can_focus(True)
        terminal.connect("key-press-event", self.on_terminal_keypress)
        terminal.connect("button-press-event", self.on_terminal_right_click)


        label = Gtk.Label(label=f"Tab {len(self.terminals) + 1}")
        self.terminals.append(terminal)

        self.notebook.insert_page(terminal, label, plus_index)
        self.notebook.set_current_page(plus_index)

        self.notebook.show_all()
        self.creating_tab = False

    def on_terminal_keypress(self, widget, event):
        ctrl = event.state & Gdk.ModifierType.CONTROL_MASK
        shift = event.state & Gdk.ModifierType.SHIFT_MASK
        key = Gdk.keyval_name(event.keyval)

        if ctrl and shift and key == 'C':
            widget.copy_clipboard()
            return True
        elif ctrl and shift and key == 'V':
            widget.paste_clipboard()
            return True

        return False  # let other keys pass through
    
    def on_terminal_right_click(self, terminal, event):
        if event.button == 3:
            menu = Gtk.Menu()

            copy_item = Gtk.MenuItem(label="Copy")
            copy_item.connect("activate", lambda _: terminal.copy_clipboard())
            menu.append(copy_item)

            paste_item = Gtk.MenuItem(label="Paste")
            paste_item.connect("activate", lambda _: terminal.paste_clipboard())
            menu.append(paste_item)

            menu.show_all()
            menu.popup_at_pointer(event)
            return True
        return False

    def create_new_tab_from_button(self):
        self.creating_tab = True

        plus_index = self.notebook.get_n_pages() - 1

        terminal = Vte.Terminal()
        terminal.spawn_async(
            Vte.PtyFlags.DEFAULT, None, ["/bin/bash"], [],
            GLib.SpawnFlags.DEFAULT, None, None, -1, None, None
        )

        terminal.set_input_enabled(True)
        terminal.set_can_focus(True)
        terminal.connect("key-press-event", self.on_terminal_keypress)
        terminal.connect("button-press-event", self.on_terminal_right_click)

        label = Gtk.Label(label=f"Tab {len(self.terminals) + 1}")
        self.terminals.append(terminal)

        self.notebook.insert_page(terminal, label, plus_index)
        
        # Move focus to the new tab (same index as just inserted)
        GLib.idle_add(self.notebook.set_current_page, plus_index)

        self.notebook.show_all()
        self.creating_tab = False


    def on_tab_switched(self, notebook, page, page_num):
        if self.creating_tab:
            return

        if page_num == notebook.get_n_pages() - 1:
            self.creating_tab = True
            GLib.idle_add(self.create_new_tab_from_button)

    # ------------------------------
    # UI
    # ------------------------------
    def create_menu_bar(self):
        menu_bar = Gtk.MenuBar()
        file_menu = Gtk.Menu()
        file_item = Gtk.MenuItem(label="File")
        file_item.set_submenu(file_menu)

        export_item = Gtk.MenuItem(label="Export Templates")
        export_item.connect("activate", self.export_templates)
        file_menu.append(export_item)

        import_item = Gtk.MenuItem(label="Import Templates")
        import_item.connect("activate", self.import_templates)
        file_menu.append(import_item)

        menu_bar.append(file_item)
        return menu_bar

    def build_variable_ui(self):
        for var, val in self.variables.items():
            box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
            label = Gtk.Label(label=f"{var}:")
            entry = Gtk.Entry()
            entry.set_text(val)
            entry.connect("changed", self.on_var_changed, var)
            box.pack_start(label, False, False, 4)
            box.pack_start(entry, True, True, 4)
            self.left_panel.pack_start(box, False, False, 4)

    def build_script_categories(self):
        # Remove all widgets below the variable entries and Add Script button
        for child in self.left_panel.get_children()[len(self.variables) + 1:]:
            self.left_panel.remove(child)

        categories = {}
        for tpl in self.templates:
            categories.setdefault(tpl["category"], []).append(tpl)

        for cat, tpls in categories.items():
            expander = Gtk.Expander(label=cat)
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
            expander.add(box)
            self.left_panel.pack_start(expander, False, False, 4)
            for tpl in tpls:
                self.add_script_button(box, tpl["label"], tpl["command"])
        self.left_panel.show_all()


    def add_script_button(self, container, label, cmd_template):
        btn = Gtk.Button(label=label)
        btn.connect("clicked", self.run_template_command, cmd_template, False)
        btn.connect("button-press-event", self.on_script_right_click, cmd_template)
        container.pack_start(btn, False, False, 0)
        container.show_all()

    def run_template_command(self, widget, cmd_template, new_tab=False):
        final_cmd = cmd_template
        for key, val in self.variables.items():
            final_cmd = final_cmd.replace(f"<${key}>", val)
        final_cmd += "\n"

        if new_tab:
            # Avoid recursion from switch-page signal
            self.notebook.disconnect_by_func(self.on_tab_switched)

            # Create new terminal
            terminal = Vte.Terminal()
            terminal.spawn_async(
                Vte.PtyFlags.DEFAULT, None, ["/bin/bash"], [],
                GLib.SpawnFlags.DEFAULT, None, None, -1, None, None
            )

            index = self.notebook.get_n_pages() - 1  # Insert before the "+" tab
            label = Gtk.Label(label=f"Tab {len(self.terminals) + 1}")
            self.terminals.append(terminal)
            self.notebook.insert_page(terminal, label, index)
            self.notebook.set_current_page(index)
            self.notebook.show_all()

            # Reconnect the signal
            self.notebook.connect("switch-page", self.on_tab_switched)

            # Feed command into the newly created terminal
            GLib.idle_add(lambda: terminal.feed_child(final_cmd.encode()))
        else:
            terminal = self.notebook.get_nth_page(self.notebook.get_current_page())
            terminal.feed_child(final_cmd.encode())



    def on_script_right_click(self, widget, event, cmd_template):
        if event.type == Gdk.EventType.BUTTON_PRESS and event.button == 3:
            menu = Gtk.Menu()
            run_current = Gtk.MenuItem(label="Run in Current Tab")
            run_current.connect("activate", lambda w: self.run_template_command(widget, cmd_template, False))
            menu.append(run_current)

            run_new = Gtk.MenuItem(label="Run in New Tab")
            run_new.connect("activate", lambda w: self.run_template_command(widget, cmd_template, True))
            menu.append(run_new)

            menu.show_all()
            menu.popup_at_pointer(event)
            return True
        return False

    def on_var_changed(self, entry, var_name):
        self.variables[var_name] = entry.get_text()
        self.save_json(VARIABLES_FILE, self.variables)

    def open_add_script_dialog(self, button):
        dialog = Gtk.Dialog(title="Add Script", transient_for=self, flags=0)
        dialog.add_buttons(
            Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
            Gtk.STOCK_OK, Gtk.ResponseType.OK
        )
        box = dialog.get_content_area()

        name_entry = Gtk.Entry()
        name_entry.set_placeholder_text("Script Name")
        cmd_entry = Gtk.Entry()
        cmd_entry.set_placeholder_text("Command Template (e.g., curl http://<$HOST>)")
        cat_entry = Gtk.Entry()
        cat_entry.set_placeholder_text("Category (e.g., Web)")

        for lbl, entry in [("Name:", name_entry), ("Command Template:", cmd_entry), ("Category:", cat_entry)]:
            box.pack_start(Gtk.Label(label=lbl), False, False, 4)
            box.pack_start(entry, False, False, 4)

        dialog.show_all()
        response = dialog.run()

        if response == Gtk.ResponseType.OK:
            name, cmd, cat = name_entry.get_text(), cmd_entry.get_text(), cat_entry.get_text()
            if name and cmd:
                new_tpl = {"label": name, "command": cmd, "category": cat or "Misc"}
                self.templates.append(new_tpl)
                self.save_json(TEMPLATES_FILE, self.templates)
                self.build_script_categories()

        dialog.destroy()

    def export_templates(self, _):
        with open("exported_templates.json", "w") as f:
            json.dump({"templates": self.templates, "variables": self.variables}, f, indent=2)

    def import_templates(self, _):
        dialog = Gtk.FileChooserDialog("Import Templates", self, Gtk.FileChooserAction.OPEN,
                                       (Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
                                        Gtk.STOCK_OPEN, Gtk.ResponseType.OK))
        response = dialog.run()
        if response == Gtk.ResponseType.OK:
            path = dialog.get_filename()
            try:
                with open(path, "r") as f:
                    data = json.load(f)
                    self.templates = data.get("templates", self.templates)
                    self.variables = data.get("variables", self.variables)
                    self.save_json(TEMPLATES_FILE, self.templates)
                    self.save_json(VARIABLES_FILE, self.variables)
                    self.build_script_categories()
            except Exception as e:
                print(f"Error importing: {e}")
        dialog.destroy()

    def load_json(self, path, default):
        if os.path.exists(path):
            try:
                with open(path, "r") as f:
                    return json.load(f)
            except Exception:
                return default
        return default

    def save_json(self, path, data):
        with open(path, "w") as f:
            json.dump(data, f, indent=2)


# ------------------------------
# MAIN
# ------------------------------
win = TerminalApp()
win.show_all()
Gtk.main()
