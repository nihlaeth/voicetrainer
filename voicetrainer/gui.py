"""Simple user interface."""
from tkinter import ttk
import tkinter as tk
import asyncio
from pathlib import Path
import json
from pkg_resources import resource_filename, Requirement, cleanup_resources

from voicetrainer.aiotk import (
    Root,
    OkCancelDialog,
    Messages)
from voicetrainer.play import stop_midi
from voicetrainer.exercise import ExerciseMixin

# pylint: disable=too-many-instance-attributes,too-many-locals
# pylint: disable=too-many-statements, too-many-public-methods, no-member
# It's messy, but there simply too many references to keep alive.
# pylint: disable=broad-except
# because of asyncio exceptions are only displayed at exit, we
# want to give the user immediate feedback.

class MainWindow(ExerciseMixin):

    """Voicetrainer application."""

    def __init__(self, root):
        self.data_path = Path(resource_filename(
            Requirement.parse("voicetrainer"),
            'voicetrainer/exercises'))
        self.root = root

        # compiler state
        self.compiler_count = 0

        self.messages = []
        self.messages_read = 0
        self.msg_window = None

        # midi state
        self.port = None
        self.player = None
        self.stopping = False
        self.play_next = False
        self.repeat_once = False

        # gui elements storage
        self.create_widgets()

        ExerciseMixin.__init__(self)

        self.restore_state()

    def create_widgets(self):
        """Put some stuff up to look at."""
        self.window = ttk.Frame(self.root)
        self.window.rowconfigure(0, weight=1)
        self.window.columnconfigure(2, weight=1)
        self.window.grid(column=0, row=0, sticky=tk.N+tk.S+tk.E+tk.W)
        self.top = self.window.winfo_toplevel()
        self.top.rowconfigure(0, weight=1)
        self.top.columnconfigure(0, weight=1)
        self.top.title("VoiceTrainer")

        # self.top menu
        self.menubar = tk.Menu(self.top)
        self.top['menu'] = self.menubar

        self.file_menu = tk.Menu(self.menubar)
        self.menubar.add_cascade(label='File', menu=self.file_menu)
        self.file_menu.add_command(
            label='Save state',
            command=self.save_state)
        self.file_menu.add_command(
            label='Quit',
            command=lambda: asyncio.ensure_future(self.quit()))

        self.separators = []

        self.statusbar = ttk.Frame(self.window)
        self.statusbar.grid(row=1, column=0, sticky=tk.N+tk.W)

        self.compiler_label = ttk.Label(self.statusbar, text="Compiler:")
        self.compiler_label.grid(row=0, column=0, sticky=tk.N+tk.E)
        self.progress = ttk.Progressbar(
            self.statusbar,
            mode='indeterminate',
            orient=tk.HORIZONTAL)
        self.progress.grid(row=0, column=1, sticky=tk.N+tk.W)

        sep = ttk.Separator(self.statusbar, orient=tk.VERTICAL)
        sep.grid(row=0, column=2)
        self.separators.append(sep)

        self.port_label_text = tk.StringVar()
        self.port_label_text.set('pmidi port: None')
        self.port_label = ttk.Label(
            self.statusbar,
            textvariable=self.port_label_text)
        self.port_label.grid(row=0, column=3, sticky=tk.N+tk.W)

        sep = ttk.Separator(self.statusbar, orient=tk.VERTICAL)
        sep.grid(row=0, column=4)
        self.separators.append(sep)

        self.msg_text = tk.StringVar()
        self.msg_text.set('messages')
        self.msg_button = ttk.Button(
            self.statusbar,
            textvariable=self.msg_text,
            command=self.display_messages)
        self.msg_button.grid(row=0, column=5, sticky=tk.N+tk.W)

        self.resize = ttk.Sizegrip(self.window)
        self.resize.grid(row=1, column=2, sticky=tk.S+tk.E)

    async def quit(self):
        """Confirm exit."""
        if self.compiler_count > 0:
            # ask conformation before quit
            confirm_exit = OkCancelDialog(
                self.root,
                (
                    "Uncompleted background task\n"
                    "An exercise is still being compiled in the "
                    "background. Do you still want to exit? The "
                    "task will be aborted."))
            if not await confirm_exit.await_data():
                return
        self.close()

    def close(self):
        """Exit main application."""
        self.save_state()
        self.progress.stop()
        self.top.destroy()
        self.root.close()

    def save_state(self):
        """Save settings to json file."""
        data = {}
        data['exercises'] = ExerciseMixin.save_state(self)
        self.data_path.joinpath('state.json').write_text(
            json.dumps(data))

    def restore_state(self):
        """Restore saved settings."""
        state_file = self.data_path.joinpath('state.json')
        if not state_file.is_file():
            return
        data = json.loads(state_file.read_text())
        if 'exercises' in data:
            ExerciseMixin.restore_state(self, data['exercises'])

    def show_messages(self):
        """Show if there unread messages."""
        if len(self.messages) > self.messages_read:
            self.msg_text.set('!!!Messages!!!')
            if self.msg_window is not None:
                self.msg_window.update_data(self.messages)

    def display_messages(self, _=None):
        """Display all messages."""
        if self.msg_window is None:
            self.msg_window = Messages(
                self.root,
                data=self.messages,
                on_close=self.on_close_msg_window)
        else:
            self.msg_window.to_front()
        self.messages_read = len(self.messages)
        self.msg_text.set('Messages')

    def on_close_msg_window(self, _):
        """Messages window was closed."""
        self.msg_window = None

    def update_compiler(self):
        """Set compiler progress bar status."""
        if self.compiler_count > 0:
            self.progress.start()
        else:
            self.progress.stop()

    async def stop(self):
        """Stop midi regardless of state."""
        if self.player is not None:
            await stop_midi(self.player)

def start():
    """Start gui and event loop."""
    loop = asyncio.get_event_loop()
    root = Root(loop)
    root.register_window(MainWindow(root))
    try:
        loop.run_forever()
    except KeyboardInterrupt:
        root.close(crash=True)
    finally:
        loop.close()
        cleanup_resources()
