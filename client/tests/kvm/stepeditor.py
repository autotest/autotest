#!/usr/bin/python
"""
Step file creator/editor.

@copyright: Red Hat Inc 2009
@author: mgoldish@redhat.com (Michael Goldish)
@version: "20090401"
"""

import pygtk, gtk, os, glob, shutil, sys, logging
import common, ppm_utils
pygtk.require('2.0')


# General utilities

def corner_and_size_clipped(startpoint, endpoint, limits):
    c0 = startpoint[:]
    c1 = endpoint[:]
    if c0[0] < 0: c0[0] = 0
    if c0[1] < 0: c0[1] = 0
    if c1[0] < 0: c1[0] = 0
    if c1[1] < 0: c1[1] = 0
    if c0[0] > limits[0] - 1: c0[0] = limits[0] - 1
    if c0[1] > limits[1] - 1: c0[1] = limits[1] - 1
    if c1[0] > limits[0] - 1: c1[0] = limits[0] - 1
    if c1[1] > limits[1] - 1: c1[1] = limits[1] - 1
    return ([min(c0[0], c1[0]),
             min(c0[1], c1[1])],
            [abs(c1[0] - c0[0]) + 1,
             abs(c1[1] - c0[1]) + 1])


def key_event_to_qemu_string(event):
    keymap = gtk.gdk.keymap_get_default()
    keyvals = keymap.get_entries_for_keycode(event.hardware_keycode)
    keyval = keyvals[0][0]
    keyname = gtk.gdk.keyval_name(keyval)

    dict = { "Return": "ret",
             "Tab": "tab",
             "space": "spc",
             "Left": "left",
             "Right": "right",
             "Up": "up",
             "Down": "down",
             "F1": "f1",
             "F2": "f2",
             "F3": "f3",
             "F4": "f4",
             "F5": "f5",
             "F6": "f6",
             "F7": "f7",
             "F8": "f8",
             "F9": "f9",
             "F10": "f10",
             "F11": "f11",
             "F12": "f12",
             "Escape": "esc",
             "minus": "minus",
             "equal": "equal",
             "BackSpace": "backspace",
             "comma": "comma",
             "period": "dot",
             "slash": "slash",
             "Insert": "insert",
             "Delete": "delete",
             "Home": "home",
             "End": "end",
             "Page_Up": "pgup",
             "Page_Down": "pgdn",
             "Menu": "menu",
             "semicolon": "0x27",
             "backslash": "0x2b",
             "apostrophe": "0x28",
             "grave": "0x29",
             "less": "0x2b",
             "bracketleft": "0x1a",
             "bracketright": "0x1b",
             "Super_L": "0xdc",
             "Super_R": "0xdb",
             }

    if ord('a') <= keyval <= ord('z') or ord('0') <= keyval <= ord('9'):
        str = keyname
    elif keyname in dict.keys():
        str = dict[keyname]
    else:
        return ""

    if event.state & gtk.gdk.CONTROL_MASK: str = "ctrl-" + str
    if event.state & gtk.gdk.MOD1_MASK: str = "alt-" + str
    if event.state & gtk.gdk.SHIFT_MASK: str = "shift-" + str

    return str


class StepMakerWindow:

    # Constructor

    def __init__(self):
        # Window
        self.window = gtk.Window(gtk.WINDOW_TOPLEVEL)
        self.window.set_title("Step Maker Window")
        self.window.connect("delete-event", self.delete_event)
        self.window.connect("destroy", self.destroy)
        self.window.set_default_size(600, 800)

        # Main box (inside a frame which is inside a VBox)
        self.menu_vbox = gtk.VBox()
        self.window.add(self.menu_vbox)
        self.menu_vbox.show()

        frame = gtk.Frame()
        frame.set_border_width(10)
        frame.set_shadow_type(gtk.SHADOW_NONE)
        self.menu_vbox.pack_end(frame)
        frame.show()

        self.main_vbox = gtk.VBox(spacing=10)
        frame.add(self.main_vbox)
        self.main_vbox.show()

        # EventBox
        self.scrolledwindow = gtk.ScrolledWindow()
        self.scrolledwindow.set_policy(gtk.POLICY_AUTOMATIC,
                                       gtk.POLICY_AUTOMATIC)
        self.scrolledwindow.set_shadow_type(gtk.SHADOW_NONE)
        self.main_vbox.pack_start(self.scrolledwindow)
        self.scrolledwindow.show()

        table = gtk.Table(1, 1)
        self.scrolledwindow.add_with_viewport(table)
        table.show()
        table.realize()

        self.event_box = gtk.EventBox()
        table.attach(self.event_box, 0, 1, 0, 1, gtk.EXPAND, gtk.EXPAND)
        self.event_box.show()
        self.event_box.realize()

        # Image
        self.image = gtk.Image()
        self.event_box.add(self.image)
        self.image.show()

        # Data VBox
        self.data_vbox = gtk.VBox(spacing=10)
        self.main_vbox.pack_start(self.data_vbox, expand=False)
        self.data_vbox.show()

        # User VBox
        self.user_vbox = gtk.VBox(spacing=10)
        self.main_vbox.pack_start(self.user_vbox, expand=False)
        self.user_vbox.show()

        # Screendump ID HBox
        box = gtk.HBox(spacing=10)
        self.data_vbox.pack_start(box)
        box.show()

        label = gtk.Label("Screendump ID:")
        box.pack_start(label, False)
        label.show()

        self.entry_screendump = gtk.Entry()
        self.entry_screendump.set_editable(False)
        box.pack_start(self.entry_screendump)
        self.entry_screendump.show()

        label = gtk.Label("Time:")
        box.pack_start(label, False)
        label.show()

        self.entry_time = gtk.Entry()
        self.entry_time.set_editable(False)
        self.entry_time.set_width_chars(10)
        box.pack_start(self.entry_time, False)
        self.entry_time.show()

        # Comment HBox
        box = gtk.HBox(spacing=10)
        self.data_vbox.pack_start(box)
        box.show()

        label = gtk.Label("Comment:")
        box.pack_start(label, False)
        label.show()

        self.entry_comment = gtk.Entry()
        box.pack_start(self.entry_comment)
        self.entry_comment.show()

        # Sleep HBox
        box = gtk.HBox(spacing=10)
        self.data_vbox.pack_start(box)
        box.show()

        self.check_sleep = gtk.CheckButton("Sleep:")
        self.check_sleep.connect("toggled", self.event_check_sleep_toggled)
        box.pack_start(self.check_sleep, False)
        self.check_sleep.show()

        self.spin_sleep = gtk.SpinButton(gtk.Adjustment(0, 0, 50000, 1, 10, 0),
                                         climb_rate=0.0)
        box.pack_start(self.spin_sleep, False)
        self.spin_sleep.show()

        # Barrier HBox
        box = gtk.HBox(spacing=10)
        self.data_vbox.pack_start(box)
        box.show()

        self.check_barrier = gtk.CheckButton("Barrier:")
        self.check_barrier.connect("toggled", self.event_check_barrier_toggled)
        box.pack_start(self.check_barrier, False)
        self.check_barrier.show()

        vbox = gtk.VBox()
        box.pack_start(vbox)
        vbox.show()

        self.label_barrier_region = gtk.Label("Region:")
        self.label_barrier_region.set_alignment(0, 0.5)
        vbox.pack_start(self.label_barrier_region)
        self.label_barrier_region.show()

        self.label_barrier_md5sum = gtk.Label("MD5:")
        self.label_barrier_md5sum.set_alignment(0, 0.5)
        vbox.pack_start(self.label_barrier_md5sum)
        self.label_barrier_md5sum.show()

        self.label_barrier_timeout = gtk.Label("Timeout:")
        box.pack_start(self.label_barrier_timeout, False)
        self.label_barrier_timeout.show()

        self.spin_barrier_timeout = gtk.SpinButton(gtk.Adjustment(0, 0, 50000,
                                                                  1, 10, 0),
                                                                 climb_rate=0.0)
        box.pack_start(self.spin_barrier_timeout, False)
        self.spin_barrier_timeout.show()

        self.check_barrier_optional = gtk.CheckButton("Optional")
        box.pack_start(self.check_barrier_optional, False)
        self.check_barrier_optional.show()

        # Keystrokes HBox
        box = gtk.HBox(spacing=10)
        self.data_vbox.pack_start(box)
        box.show()

        label = gtk.Label("Keystrokes:")
        box.pack_start(label, False)
        label.show()

        frame = gtk.Frame()
        frame.set_shadow_type(gtk.SHADOW_IN)
        box.pack_start(frame)
        frame.show()

        self.text_buffer = gtk.TextBuffer() ;
        self.entry_keys = gtk.TextView(self.text_buffer)
        self.entry_keys.set_wrap_mode(gtk.WRAP_WORD)
        self.entry_keys.connect("key-press-event", self.event_key_press)
        frame.add(self.entry_keys)
        self.entry_keys.show()

        self.check_manual = gtk.CheckButton("Manual")
        self.check_manual.connect("toggled", self.event_manual_toggled)
        box.pack_start(self.check_manual, False)
        self.check_manual.show()

        button = gtk.Button("Clear")
        button.connect("clicked", self.event_clear_clicked)
        box.pack_start(button, False)
        button.show()

        # Mouse click HBox
        box = gtk.HBox(spacing=10)
        self.data_vbox.pack_start(box)
        box.show()

        label = gtk.Label("Mouse action:")
        box.pack_start(label, False)
        label.show()

        self.button_capture = gtk.Button("Capture")
        box.pack_start(self.button_capture, False)
        self.button_capture.show()

        self.check_mousemove = gtk.CheckButton("Move: ...")
        box.pack_start(self.check_mousemove, False)
        self.check_mousemove.show()

        self.check_mouseclick = gtk.CheckButton("Click: ...")
        box.pack_start(self.check_mouseclick, False)
        self.check_mouseclick.show()

        self.spin_sensitivity = gtk.SpinButton(gtk.Adjustment(1, 1, 100, 1, 10,
                                                              0),
                                                              climb_rate=0.0)
        box.pack_end(self.spin_sensitivity, False)
        self.spin_sensitivity.show()

        label = gtk.Label("Sensitivity:")
        box.pack_end(label, False)
        label.show()

        self.spin_latency = gtk.SpinButton(gtk.Adjustment(10, 1, 500, 1, 10, 0),
                                           climb_rate=0.0)
        box.pack_end(self.spin_latency, False)
        self.spin_latency.show()

        label = gtk.Label("Latency:")
        box.pack_end(label, False)
        label.show()

        self.handler_event_box_press = None
        self.handler_event_box_release = None
        self.handler_event_box_scroll = None
        self.handler_event_box_motion = None
        self.handler_event_box_expose = None

        self.window.realize()
        self.window.show()

        self.clear_state()

    # Utilities

    def message(self, text, title):
        dlg = gtk.MessageDialog(self.window,
                gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
                gtk.MESSAGE_INFO,
                gtk.BUTTONS_CLOSE,
                title)
        dlg.set_title(title)
        dlg.format_secondary_text(text)
        response = dlg.run()
        dlg.destroy()


    def question_yes_no(self, text, title):
        dlg = gtk.MessageDialog(self.window,
                gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
                gtk.MESSAGE_QUESTION,
                gtk.BUTTONS_YES_NO,
                title)
        dlg.set_title(title)
        dlg.format_secondary_text(text)
        response = dlg.run()
        dlg.destroy()
        if response == gtk.RESPONSE_YES:
            return True
        return False


    def inputdialog(self, text, title, default_response=""):
        # Define a little helper function
        def inputdialog_entry_activated(entry):
            dlg.response(gtk.RESPONSE_OK)

        # Create the dialog
        dlg = gtk.MessageDialog(self.window,
                gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
                gtk.MESSAGE_QUESTION,
                gtk.BUTTONS_OK_CANCEL,
                title)
        dlg.set_title(title)
        dlg.format_secondary_text(text)

        # Create an entry widget
        entry = gtk.Entry()
        entry.set_text(default_response)
        entry.connect("activate", inputdialog_entry_activated)
        dlg.vbox.pack_start(entry)
        entry.show()

        # Run the dialog
        response = dlg.run()
        dlg.destroy()
        if response == gtk.RESPONSE_OK:
            return entry.get_text()
        return None


    def filedialog(self, title=None, default_filename=None):
        chooser = gtk.FileChooserDialog(title=title, parent=self.window,
                                        action=gtk.FILE_CHOOSER_ACTION_OPEN,
                buttons=(gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL, gtk.STOCK_OPEN,
                         gtk.RESPONSE_OK))
        chooser.resize(700, 500)
        if default_filename:
            chooser.set_filename(os.path.abspath(default_filename))
        filename = None
        response = chooser.run()
        if response == gtk.RESPONSE_OK:
            filename = chooser.get_filename()
        chooser.destroy()
        return filename


    def redirect_event_box_input(self, press=None, release=None, scroll=None,
                                 motion=None, expose=None):
        if self.handler_event_box_press != None: \
        self.event_box.disconnect(self.handler_event_box_press)
        if self.handler_event_box_release != None: \
        self.event_box.disconnect(self.handler_event_box_release)
        if self.handler_event_box_scroll != None: \
        self.event_box.disconnect(self.handler_event_box_scroll)
        if self.handler_event_box_motion != None: \
        self.event_box.disconnect(self.handler_event_box_motion)
        if self.handler_event_box_expose != None: \
        self.event_box.disconnect(self.handler_event_box_expose)
        self.handler_event_box_press = None
        self.handler_event_box_release = None
        self.handler_event_box_scroll = None
        self.handler_event_box_motion = None
        self.handler_event_box_expose = None
        if press != None: self.handler_event_box_press = \
        self.event_box.connect("button-press-event", press)
        if release != None: self.handler_event_box_release = \
        self.event_box.connect("button-release-event", release)
        if scroll != None: self.handler_event_box_scroll = \
        self.event_box.connect("scroll-event", scroll)
        if motion != None: self.handler_event_box_motion = \
        self.event_box.connect("motion-notify-event", motion)
        if expose != None: self.handler_event_box_expose = \
        self.event_box.connect_after("expose-event", expose)


    def get_keys(self):
        return self.text_buffer.get_text(
                self.text_buffer.get_start_iter(),
                self.text_buffer.get_end_iter())


    def add_key(self, key):
        text = self.get_keys()
        if len(text) > 0 and text[-1] != ' ':
            text += " "
        text += key
        self.text_buffer.set_text(text)


    def clear_keys(self):
        self.text_buffer.set_text("")


    def update_barrier_info(self):
        if self.barrier_selected:
            self.label_barrier_region.set_text("Selected region: Corner: " + \
                                            str(tuple(self.barrier_corner)) + \
                                            " Size: " + \
                                            str(tuple(self.barrier_size)))
        else:
            self.label_barrier_region.set_text("No region selected.")
        self.label_barrier_md5sum.set_text("MD5: " + self.barrier_md5sum)


    def update_mouse_click_info(self):
        if self.mouse_click_captured:
            self.check_mousemove.set_label("Move: " + \
                                           str(tuple(self.mouse_click_coords)))
            self.check_mouseclick.set_label("Click: button %d" %
                                            self.mouse_click_button)
        else:
            self.check_mousemove.set_label("Move: ...")
            self.check_mouseclick.set_label("Click: ...")


    def clear_state(self, clear_screendump=True):
        # Recording time
        self.entry_time.set_text("unknown")
        if clear_screendump:
            # Screendump
            self.clear_image()
        # Screendump ID
        self.entry_screendump.set_text("")
        # Comment
        self.entry_comment.set_text("")
        # Sleep
        self.check_sleep.set_active(True)
        self.check_sleep.set_active(False)
        self.spin_sleep.set_value(10)
        # Barrier
        self.clear_barrier_state()
        # Keystrokes
        self.check_manual.set_active(False)
        self.clear_keys()
        # Mouse actions
        self.check_mousemove.set_sensitive(False)
        self.check_mouseclick.set_sensitive(False)
        self.check_mousemove.set_active(False)
        self.check_mouseclick.set_active(False)
        self.mouse_click_captured = False
        self.mouse_click_coords = [0, 0]
        self.mouse_click_button = 0
        self.update_mouse_click_info()


    def clear_barrier_state(self):
        self.check_barrier.set_active(True)
        self.check_barrier.set_active(False)
        self.check_barrier_optional.set_active(False)
        self.spin_barrier_timeout.set_value(10)
        self.barrier_selection_started = False
        self.barrier_selected = False
        self.barrier_corner0 = [0, 0]
        self.barrier_corner1 = [0, 0]
        self.barrier_corner = [0, 0]
        self.barrier_size = [0, 0]
        self.barrier_md5sum = ""
        self.update_barrier_info()


    def set_image(self, w, h, data):
        (self.image_width, self.image_height, self.image_data) = (w, h, data)
        self.image.set_from_pixbuf(gtk.gdk.pixbuf_new_from_data(
            data, gtk.gdk.COLORSPACE_RGB, False, 8,
            w, h, w*3))
        hscrollbar = self.scrolledwindow.get_hscrollbar()
        hscrollbar.set_range(0, w)
        vscrollbar = self.scrolledwindow.get_vscrollbar()
        vscrollbar.set_range(0, h)


    def set_image_from_file(self, filename):
        if not ppm_utils.image_verify_ppm_file(filename):
            logging.warning("set_image_from_file: Warning: received invalid"
                            "screendump file")
            return self.clear_image()
        (w, h, data) = ppm_utils.image_read_from_ppm_file(filename)
        self.set_image(w, h, data)


    def clear_image(self):
        self.image.clear()
        self.image_width = 0
        self.image_height = 0
        self.image_data = ""


    def update_screendump_id(self, data_dir):
        if not self.image_data:
            return
        # Find a proper ID for the screendump
        scrdump_md5sum = ppm_utils.image_md5sum(self.image_width,
                                                self.image_height,
                                                self.image_data)
        scrdump_id = ppm_utils.find_id_for_screendump(scrdump_md5sum, data_dir)
        if not scrdump_id:
            # Not found; generate one
            scrdump_id = ppm_utils.generate_id_for_screendump(scrdump_md5sum,
                                                              data_dir)
        self.entry_screendump.set_text(scrdump_id)


    def get_step_lines(self, data_dir=None):
        if self.check_barrier.get_active() and not self.barrier_selected:
            self.message("No barrier region selected.", "Error")
            return

        str = "step"

        # Add step recording time
        if self.entry_time.get_text():
            str += " " + self.entry_time.get_text()

        str += "\n"

        # Add screendump line
        if self.image_data:
            str += "screendump %s\n" % self.entry_screendump.get_text()

        # Add comment
        if self.entry_comment.get_text():
            str += "# %s\n" % self.entry_comment.get_text()

        # Add sleep line
        if self.check_sleep.get_active():
            str += "sleep %d\n" % self.spin_sleep.get_value()

        # Add barrier_2 line
        if self.check_barrier.get_active():
            str += "barrier_2 %d %d %d %d %s %d" % (
                    self.barrier_size[0], self.barrier_size[1],
                    self.barrier_corner[0], self.barrier_corner[1],
                    self.barrier_md5sum, self.spin_barrier_timeout.get_value())
            if self.check_barrier_optional.get_active():
                str += " optional"
            str += "\n"

        # Add "Sending keys" comment
        keys_to_send = self.get_keys().split()
        if keys_to_send:
            str += "# Sending keys: %s\n" % self.get_keys()

        # Add key and var lines
        for key in keys_to_send:
            if key.startswith("$"):
                varname = key[1:]
                str += "var %s\n" % varname
            else:
                str += "key %s\n" % key

        # Add mousemove line
        if self.check_mousemove.get_active():
            str += "mousemove %d %d\n" % (self.mouse_click_coords[0],
                                          self.mouse_click_coords[1])

        # Add mouseclick line
        if self.check_mouseclick.get_active():
            dict = { 1 : 1,
                     2 : 2,
                     3 : 4 }
            str += "mouseclick %d\n" % dict[self.mouse_click_button]

        # Write screendump and cropped screendump image files
        if data_dir and self.image_data:
            # Create the data dir if it doesn't exist
            if not os.path.exists(data_dir):
                os.makedirs(data_dir)
            # Get the full screendump filename
            scrdump_filename = os.path.join(data_dir,
                                            self.entry_screendump.get_text())
            # Write screendump file if it doesn't exist
            if not os.path.exists(scrdump_filename):
                try:
                    ppm_utils.image_write_to_ppm_file(scrdump_filename,
                                                      self.image_width,
                                                      self.image_height,
                                                      self.image_data)
                except IOError:
                    self.message("Could not write screendump file.", "Error")

            #if self.check_barrier.get_active():
            #    # Crop image to get the cropped screendump
            #    (cw, ch, cdata) = ppm_utils.image_crop(
            #            self.image_width, self.image_height, self.image_data,
            #            self.barrier_corner[0], self.barrier_corner[1],
            #            self.barrier_size[0], self.barrier_size[1])
            #    cropped_scrdump_md5sum = ppm_utils.image_md5sum(cw, ch, cdata)
            #    cropped_scrdump_filename = \
            #    ppm_utils.get_cropped_screendump_filename(scrdump_filename,
            #                                            cropped_scrdump_md5sum)
            #    # Write cropped screendump file
            #    try:
            #        ppm_utils.image_write_to_ppm_file(cropped_scrdump_filename,
            #                                          cw, ch, cdata)
            #    except IOError:
            #        self.message("Could not write cropped screendump file.",
            #                     "Error")

        return str

    def set_state_from_step_lines(self, str, data_dir, warn=True):
        self.clear_state()

        for line in str.splitlines():
            words = line.split()
            if not words:
                continue

            if line.startswith("#") \
                    and not self.entry_comment.get_text() \
                    and not line.startswith("# Sending keys:") \
                    and not line.startswith("# ----"):
                self.entry_comment.set_text(line.strip("#").strip())

            elif words[0] == "step":
                if len(words) >= 2:
                    self.entry_time.set_text(words[1])

            elif words[0] == "screendump":
                self.entry_screendump.set_text(words[1])
                self.set_image_from_file(os.path.join(data_dir, words[1]))

            elif words[0] == "sleep":
                self.spin_sleep.set_value(int(words[1]))
                self.check_sleep.set_active(True)

            elif words[0] == "key":
                self.add_key(words[1])

            elif words[0] == "var":
                self.add_key("$%s" % words[1])

            elif words[0] == "mousemove":
                self.mouse_click_captured = True
                self.mouse_click_coords = [int(words[1]), int(words[2])]
                self.update_mouse_click_info()

            elif words[0] == "mouseclick":
                self.mouse_click_captured = True
                self.mouse_click_button = int(words[1])
                self.update_mouse_click_info()

            elif words[0] == "barrier_2":
                # Get region corner and size from step lines
                self.barrier_corner = [int(words[3]), int(words[4])]
                self.barrier_size = [int(words[1]), int(words[2])]
                # Get corner0 and corner1 from step lines
                self.barrier_corner0 = self.barrier_corner
                self.barrier_corner1 = [self.barrier_corner[0] +
                                        self.barrier_size[0] - 1,
                                        self.barrier_corner[1] +
                                        self.barrier_size[1] - 1]
                # Get the md5sum
                self.barrier_md5sum = words[5]
                # Pretend the user selected the region with the mouse
                self.barrier_selection_started = True
                self.barrier_selected = True
                # Update label widgets according to region information
                self.update_barrier_info()
                # Check the barrier checkbutton
                self.check_barrier.set_active(True)
                # Set timeout value
                self.spin_barrier_timeout.set_value(int(words[6]))
                # Set 'optional' checkbutton state
                self.check_barrier_optional.set_active(words[-1] == "optional")
                # Update the image widget
                self.event_box.queue_draw()

                if warn:
                    # See if the computed md5sum matches the one recorded in
                    # the file
                    computed_md5sum = ppm_utils.get_region_md5sum(
                            self.image_width, self.image_height,
                            self.image_data, self.barrier_corner[0],
                            self.barrier_corner[1], self.barrier_size[0],
                            self.barrier_size[1])
                    if computed_md5sum != self.barrier_md5sum:
                        self.message("Computed MD5 sum (%s) differs from MD5"
                                     " sum recorded in steps file (%s)" %
                                     (computed_md5sum, self.barrier_md5sum),
                                     "Warning")

    # Events

    def delete_event(self, widget, event):
        pass

    def destroy(self, widget):
        gtk.main_quit()

    def event_check_barrier_toggled(self, widget):
        if self.check_barrier.get_active():
            self.redirect_event_box_input(
                    self.event_button_press,
                    self.event_button_release,
                    None,
                    None,
                    self.event_expose)
            self.event_box.queue_draw()
            self.event_box.window.set_cursor(gtk.gdk.Cursor(gtk.gdk.CROSSHAIR))
            self.label_barrier_region.set_sensitive(True)
            self.label_barrier_md5sum.set_sensitive(True)
            self.label_barrier_timeout.set_sensitive(True)
            self.spin_barrier_timeout.set_sensitive(True)
            self.check_barrier_optional.set_sensitive(True)
        else:
            self.redirect_event_box_input()
            self.event_box.queue_draw()
            self.event_box.window.set_cursor(None)
            self.label_barrier_region.set_sensitive(False)
            self.label_barrier_md5sum.set_sensitive(False)
            self.label_barrier_timeout.set_sensitive(False)
            self.spin_barrier_timeout.set_sensitive(False)
            self.check_barrier_optional.set_sensitive(False)

    def event_check_sleep_toggled(self, widget):
        if self.check_sleep.get_active():
            self.spin_sleep.set_sensitive(True)
        else:
            self.spin_sleep.set_sensitive(False)

    def event_manual_toggled(self, widget):
        self.entry_keys.grab_focus()

    def event_clear_clicked(self, widget):
        self.clear_keys()
        self.entry_keys.grab_focus()

    def event_expose(self, widget, event):
        if not self.barrier_selection_started:
            return
        (corner, size) = corner_and_size_clipped(self.barrier_corner0,
                                                 self.barrier_corner1,
                                                 self.event_box.size_request())
        gc = self.event_box.window.new_gc(line_style=gtk.gdk.LINE_DOUBLE_DASH,
                                          line_width=1)
        gc.set_foreground(gc.get_colormap().alloc_color("red"))
        gc.set_background(gc.get_colormap().alloc_color("dark red"))
        gc.set_dashes(0, (4, 4))
        self.event_box.window.draw_rectangle(
                gc, False,
                corner[0], corner[1],
                size[0]-1, size[1]-1)

    def event_drag_motion(self, widget, event):
        old_corner1 = self.barrier_corner1
        self.barrier_corner1 = [int(event.x), int(event.y)]
        (corner, size) = corner_and_size_clipped(self.barrier_corner0,
                                                 self.barrier_corner1,
                                                 self.event_box.size_request())
        (old_corner, old_size) = corner_and_size_clipped(self.barrier_corner0,
                                                         old_corner1,
                                                  self.event_box.size_request())
        corner0 = [min(corner[0], old_corner[0]), min(corner[1], old_corner[1])]
        corner1 = [max(corner[0] + size[0], old_corner[0] + old_size[0]),
                   max(corner[1] + size[1], old_corner[1] + old_size[1])]
        size = [corner1[0] - corner0[0] + 1,
                corner1[1] - corner0[1] + 1]
        self.event_box.queue_draw_area(corner0[0], corner0[1], size[0], size[1])

    def event_button_press(self, widget, event):
        (corner, size) = corner_and_size_clipped(self.barrier_corner0,
                                                 self.barrier_corner1,
                                                 self.event_box.size_request())
        self.event_box.queue_draw_area(corner[0], corner[1], size[0], size[1])
        self.barrier_corner0 = [int(event.x), int(event.y)]
        self.barrier_corner1 = [int(event.x), int(event.y)]
        self.redirect_event_box_input(
                self.event_button_press,
                self.event_button_release,
                None,
                self.event_drag_motion,
                self.event_expose)
        self.barrier_selection_started = True

    def event_button_release(self, widget, event):
        self.redirect_event_box_input(
                self.event_button_press,
                self.event_button_release,
                None,
                None,
                self.event_expose)
        (self.barrier_corner, self.barrier_size) = \
        corner_and_size_clipped(self.barrier_corner0, self.barrier_corner1,
                                self.event_box.size_request())
        self.barrier_md5sum = ppm_utils.get_region_md5sum(
                self.image_width, self.image_height, self.image_data,
                self.barrier_corner[0], self.barrier_corner[1],
                self.barrier_size[0], self.barrier_size[1])
        self.barrier_selected = True
        self.update_barrier_info()

    def event_key_press(self, widget, event):
        if self.check_manual.get_active():
            return False
        str = key_event_to_qemu_string(event)
        self.add_key(str)
        return True


class StepEditor(StepMakerWindow):
    ui = '''<ui>
    <menubar name="MenuBar">
        <menu action="File">
            <menuitem action="Open"/>
            <separator/>
            <menuitem action="Quit"/>
        </menu>
        <menu action="Edit">
            <menuitem action="CopyStep"/>
            <menuitem action="DeleteStep"/>
        </menu>
        <menu action="Insert">
            <menuitem action="InsertNewBefore"/>
            <menuitem action="InsertNewAfter"/>
            <separator/>
            <menuitem action="InsertStepsBefore"/>
            <menuitem action="InsertStepsAfter"/>
        </menu>
        <menu action="Tools">
            <menuitem action="CleanUp"/>
        </menu>
    </menubar>
</ui>'''

    # Constructor

    def __init__(self, filename=None):
        StepMakerWindow.__init__(self)

        self.steps_filename = None
        self.steps = []

        # Create a UIManager instance
        uimanager = gtk.UIManager()

        # Add the accelerator group to the toplevel window
        accelgroup = uimanager.get_accel_group()
        self.window.add_accel_group(accelgroup)

        # Create an ActionGroup
        actiongroup = gtk.ActionGroup('StepEditor')

        # Create actions
        actiongroup.add_actions([
            ('Quit', gtk.STOCK_QUIT, '_Quit', None, 'Quit the Program',
             self.quit),
            ('Open', gtk.STOCK_OPEN, '_Open', None, 'Open steps file',
             self.open_steps_file),
            ('CopyStep', gtk.STOCK_COPY, '_Copy current step...', "",
             'Copy current step to user specified position', self.copy_step),
            ('DeleteStep', gtk.STOCK_DELETE, '_Delete current step', "",
             'Delete current step', self.event_remove_clicked),
            ('InsertNewBefore', gtk.STOCK_ADD, '_New step before current', "",
             'Insert new step before current step', self.insert_before),
            ('InsertNewAfter', gtk.STOCK_ADD, 'N_ew step after current', "",
             'Insert new step after current step', self.insert_after),
            ('InsertStepsBefore', gtk.STOCK_ADD, '_Steps before current...',
             "", 'Insert steps (from file) before current step',
             self.insert_steps_before),
            ('InsertStepsAfter', gtk.STOCK_ADD, 'Steps _after current...', "",
             'Insert steps (from file) after current step',
             self.insert_steps_after),
            ('CleanUp', gtk.STOCK_DELETE, '_Clean up data directory', "",
             'Move unused PPM files to a backup directory', self.cleanup),
            ('File', None, '_File'),
            ('Edit', None, '_Edit'),
            ('Insert', None, '_Insert'),
            ('Tools', None, '_Tools')
            ])

        def create_shortcut(name, callback, keyname):
            # Create an action
            action = gtk.Action(name, None, None, None)
            # Connect a callback to the action
            action.connect("activate", callback)
            actiongroup.add_action_with_accel(action, keyname)
            # Have the action use accelgroup
            action.set_accel_group(accelgroup)
            # Connect the accelerator to the action
            action.connect_accelerator()

        create_shortcut("Next", self.event_next_clicked, "Page_Down")
        create_shortcut("Previous", self.event_prev_clicked, "Page_Up")

        # Add the actiongroup to the uimanager
        uimanager.insert_action_group(actiongroup, 0)

        # Add a UI description
        uimanager.add_ui_from_string(self.ui)

        # Create a MenuBar
        menubar = uimanager.get_widget('/MenuBar')
        self.menu_vbox.pack_start(menubar, False)

        # Remember the Edit menu bar for future reference
        self.menu_edit = uimanager.get_widget('/MenuBar/Edit')
        self.menu_edit.set_sensitive(False)

        # Remember the Insert menu bar for future reference
        self.menu_insert = uimanager.get_widget('/MenuBar/Insert')
        self.menu_insert.set_sensitive(False)

        # Remember the Tools menu bar for future reference
        self.menu_tools = uimanager.get_widget('/MenuBar/Tools')
        self.menu_tools.set_sensitive(False)

        # Next/Previous HBox
        hbox = gtk.HBox(spacing=10)
        self.user_vbox.pack_start(hbox)
        hbox.show()

        self.button_first = gtk.Button(stock=gtk.STOCK_GOTO_FIRST)
        self.button_first.connect("clicked", self.event_first_clicked)
        hbox.pack_start(self.button_first)
        self.button_first.show()

        #self.button_prev = gtk.Button("<< Previous")
        self.button_prev = gtk.Button(stock=gtk.STOCK_GO_BACK)
        self.button_prev.connect("clicked", self.event_prev_clicked)
        hbox.pack_start(self.button_prev)
        self.button_prev.show()

        self.label_step = gtk.Label("Step:")
        hbox.pack_start(self.label_step, False)
        self.label_step.show()

        self.entry_step_num = gtk.Entry()
        self.entry_step_num.connect("activate", self.event_entry_step_activated)
        self.entry_step_num.set_width_chars(3)
        hbox.pack_start(self.entry_step_num, False)
        self.entry_step_num.show()

        #self.button_next = gtk.Button("Next >>")
        self.button_next = gtk.Button(stock=gtk.STOCK_GO_FORWARD)
        self.button_next.connect("clicked", self.event_next_clicked)
        hbox.pack_start(self.button_next)
        self.button_next.show()

        self.button_last = gtk.Button(stock=gtk.STOCK_GOTO_LAST)
        self.button_last.connect("clicked", self.event_last_clicked)
        hbox.pack_start(self.button_last)
        self.button_last.show()

        # Save HBox
        hbox = gtk.HBox(spacing=10)
        self.user_vbox.pack_start(hbox)
        hbox.show()

        self.button_save = gtk.Button("_Save current step")
        self.button_save.connect("clicked", self.event_save_clicked)
        hbox.pack_start(self.button_save)
        self.button_save.show()

        self.button_remove = gtk.Button("_Delete current step")
        self.button_remove.connect("clicked", self.event_remove_clicked)
        hbox.pack_start(self.button_remove)
        self.button_remove.show()

        self.button_replace = gtk.Button("_Replace screendump")
        self.button_replace.connect("clicked", self.event_replace_clicked)
        hbox.pack_start(self.button_replace)
        self.button_replace.show()

        # Disable unused widgets
        self.button_capture.set_sensitive(False)
        self.spin_latency.set_sensitive(False)
        self.spin_sensitivity.set_sensitive(False)

        # Disable main vbox because no steps file is loaded
        self.main_vbox.set_sensitive(False)

        # Set title
        self.window.set_title("Step Editor")

    # Events

    def delete_event(self, widget, event):
        # Make sure the step is saved (if the user wants it to be)
        self.verify_save()

    def event_first_clicked(self, widget):
        if not self.steps:
            return
        # Make sure the step is saved (if the user wants it to be)
        self.verify_save()
        # Go to first step
        self.set_step(0)

    def event_last_clicked(self, widget):
        if not self.steps:
            return
        # Make sure the step is saved (if the user wants it to be)
        self.verify_save()
        # Go to last step
        self.set_step(len(self.steps) - 1)

    def event_prev_clicked(self, widget):
        if not self.steps:
            return
        # Make sure the step is saved (if the user wants it to be)
        self.verify_save()
        # Go to previous step
        index = self.current_step_index - 1
        if self.steps:
            index = index % len(self.steps)
        self.set_step(index)

    def event_next_clicked(self, widget):
        if not self.steps:
            return
        # Make sure the step is saved (if the user wants it to be)
        self.verify_save()
        # Go to next step
        index = self.current_step_index + 1
        if self.steps:
            index = index % len(self.steps)
        self.set_step(index)

    def event_entry_step_activated(self, widget):
        if not self.steps:
            return
        step_index = self.entry_step_num.get_text()
        if not step_index.isdigit():
            return
        step_index = int(step_index) - 1
        if step_index == self.current_step_index:
            return
        self.verify_save()
        self.set_step(step_index)

    def event_save_clicked(self, widget):
        if not self.steps:
            return
        self.save_step()

    def event_remove_clicked(self, widget):
        if not self.steps:
            return
        if not self.question_yes_no("This will modify the steps file."
                                    " Are you sure?", "Remove step?"):
            return
        # Remove step
        del self.steps[self.current_step_index]
        # Write changes to file
        self.write_steps_file(self.steps_filename)
        # Move to previous step
        self.set_step(self.current_step_index)

    def event_replace_clicked(self, widget):
        if not self.steps:
            return
        # Let the user choose a screendump file
        current_filename = os.path.join(self.steps_data_dir,
                                        self.entry_screendump.get_text())
        filename = self.filedialog("Choose PPM image file",
                                   default_filename=current_filename)
        if not filename:
            return
        if not ppm_utils.image_verify_ppm_file(filename):
            self.message("Not a valid PPM image file.", "Error")
            return
        self.clear_image()
        self.clear_barrier_state()
        self.set_image_from_file(filename)
        self.update_screendump_id(self.steps_data_dir)

    # Menu actions

    def open_steps_file(self, action):
        # Make sure the step is saved (if the user wants it to be)
        self.verify_save()
        # Let the user choose a steps file
        current_filename = self.steps_filename
        filename = self.filedialog("Open steps file",
                                   default_filename=current_filename)
        if not filename:
            return
        self.set_steps_file(filename)

    def quit(self, action):
        # Make sure the step is saved (if the user wants it to be)
        self.verify_save()
        # Quit
        gtk.main_quit()

    def copy_step(self, action):
        if not self.steps:
            return
        self.verify_save()
        self.set_step(self.current_step_index)
        # Get the desired position
        step_index = self.inputdialog("Copy step to position:",
                                      "Copy step",
                                      str(self.current_step_index + 2))
        if not step_index:
            return
        step_index = int(step_index) - 1
        # Get the lines of the current step
        step = self.steps[self.current_step_index]
        # Insert new step at position step_index
        self.steps.insert(step_index, step)
        # Go to new step
        self.set_step(step_index)
        # Write changes to disk
        self.write_steps_file(self.steps_filename)

    def insert_before(self, action):
        if not self.steps_filename:
            return
        if not self.question_yes_no("This will modify the steps file."
                                    " Are you sure?", "Insert new step?"):
            return
        self.verify_save()
        step_index = self.current_step_index
        # Get the lines of a blank step
        self.clear_state()
        step = self.get_step_lines()
        # Insert new step at position step_index
        self.steps.insert(step_index, step)
        # Go to new step
        self.set_step(step_index)
        # Write changes to disk
        self.write_steps_file(self.steps_filename)

    def insert_after(self, action):
        if not self.steps_filename:
            return
        if not self.question_yes_no("This will modify the steps file."
                                    " Are you sure?", "Insert new step?"):
            return
        self.verify_save()
        step_index = self.current_step_index + 1
        # Get the lines of a blank step
        self.clear_state()
        step = self.get_step_lines()
        # Insert new step at position step_index
        self.steps.insert(step_index, step)
        # Go to new step
        self.set_step(step_index)
        # Write changes to disk
        self.write_steps_file(self.steps_filename)

    def insert_steps(self, filename, index):
        # Read the steps file
        (steps, header) = self.read_steps_file(filename)

        data_dir = ppm_utils.get_data_dir(filename)
        for step in steps:
            self.set_state_from_step_lines(step, data_dir, warn=False)
            step = self.get_step_lines(self.steps_data_dir)

        # Insert steps into self.steps
        self.steps[index:index] = steps
        # Write changes to disk
        self.write_steps_file(self.steps_filename)

    def insert_steps_before(self, action):
        if not self.steps_filename:
            return
        # Let the user choose a steps file
        current_filename = self.steps_filename
        filename = self.filedialog("Choose steps file",
                                   default_filename=current_filename)
        if not filename:
            return
        self.verify_save()

        step_index = self.current_step_index
        # Insert steps at position step_index
        self.insert_steps(filename, step_index)
        # Go to new steps
        self.set_step(step_index)

    def insert_steps_after(self, action):
        if not self.steps_filename:
            return
        # Let the user choose a steps file
        current_filename = self.steps_filename
        filename = self.filedialog("Choose steps file",
                                   default_filename=current_filename)
        if not filename:
            return
        self.verify_save()

        step_index = self.current_step_index + 1
        # Insert new steps at position step_index
        self.insert_steps(filename, step_index)
        # Go to new steps
        self.set_step(step_index)

    def cleanup(self, action):
        if not self.steps_filename:
            return
        if not self.question_yes_no("All unused PPM files will be moved to a"
                                    " backup directory. Are you sure?",
                                    "Clean up data directory?"):
            return
        # Remember the current step index
        current_step_index = self.current_step_index
        # Get the backup dir
        backup_dir = os.path.join(self.steps_data_dir, "backup")
        # Create it if it doesn't exist
        if not os.path.exists(backup_dir):
            os.makedirs(backup_dir)
        # Move all files to the backup dir
        for filename in glob.glob(os.path.join(self.steps_data_dir,
                                               "*.[Pp][Pp][Mm]")):
            shutil.move(filename, backup_dir)
        # Get the used files back
        for step in self.steps:
            self.set_state_from_step_lines(step, backup_dir, warn=False)
            self.get_step_lines(self.steps_data_dir)
        # Remove the used files from the backup dir
        used_files = os.listdir(self.steps_data_dir)
        for filename in os.listdir(backup_dir):
            if filename in used_files:
                os.unlink(os.path.join(backup_dir, filename))
        # Restore step index
        self.set_step(current_step_index)
        # Inform the user
        self.message("All unused PPM files may be found at %s." %
                     os.path.abspath(backup_dir),
                     "Clean up data directory")

    # Methods

    def read_steps_file(self, filename):
        steps = []
        header = ""

        file = open(filename, "r")
        for line in file.readlines():
            words = line.split()
            if not words:
                continue
            if line.startswith("# ----"):
                continue
            if words[0] == "step":
                steps.append("")
            if steps:
                steps[-1] += line
            else:
                header += line
        file.close()

        return (steps, header)

    def set_steps_file(self, filename):
        try:
            (self.steps, self.header) = self.read_steps_file(filename)
        except (TypeError, IOError):
            self.message("Cannot read file %s." % filename, "Error")
            return

        self.steps_filename = filename
        self.steps_data_dir = ppm_utils.get_data_dir(filename)
        # Go to step 0
        self.set_step(0)

    def set_step(self, index):
        # Limit index to legal boundaries
        if index < 0:
            index = 0
        if index > len(self.steps) - 1:
            index = len(self.steps) - 1

        # Enable the menus
        self.menu_edit.set_sensitive(True)
        self.menu_insert.set_sensitive(True)
        self.menu_tools.set_sensitive(True)

        # If no steps exist...
        if self.steps == []:
            self.current_step_index = index
            self.current_step = None
            # Set window title
            self.window.set_title("Step Editor -- %s" %
                                  os.path.basename(self.steps_filename))
            # Set step entry widget text
            self.entry_step_num.set_text("")
            # Clear the state of all widgets
            self.clear_state()
            # Disable the main vbox
            self.main_vbox.set_sensitive(False)
            return

        self.current_step_index = index
        self.current_step = self.steps[index]
        # Set window title
        self.window.set_title("Step Editor -- %s -- step %d" %
                              (os.path.basename(self.steps_filename),
                               index + 1))
        # Set step entry widget text
        self.entry_step_num.set_text(str(self.current_step_index + 1))
        # Load the state from the step lines
        self.set_state_from_step_lines(self.current_step, self.steps_data_dir)
        # Enable the main vbox
        self.main_vbox.set_sensitive(True)
        # Make sure the step lines in self.current_step are identical to the
        # output of self.get_step_lines
        self.current_step = self.get_step_lines()

    def verify_save(self):
        if not self.steps:
            return
        # See if the user changed anything
        if self.get_step_lines() != self.current_step:
            if self.question_yes_no("Step contents have been modified."
                                    " Save step?", "Save changes?"):
                self.save_step()

    def save_step(self):
        lines = self.get_step_lines(self.steps_data_dir)
        if lines != None:
            self.steps[self.current_step_index] = lines
            self.current_step = lines
            self.write_steps_file(self.steps_filename)

    def write_steps_file(self, filename):
        file = open(filename, "w")
        file.write(self.header)
        for step in self.steps:
            file.write("# " + "-" * 32 + "\n")
            file.write(step)
        file.close()


if __name__ == "__main__":
    se = StepEditor()
    if len(sys.argv) > 1:
        se.set_steps_file(sys.argv[1])
    gtk.main()
