"""Simple user interface."""
from tkinter import ttk
import tkinter as tk
import asyncio
from pathlib import Path
import json

from voicetrainer.compile import set_err_cb as set_compile_err_cb
from voicetrainer.compile import set_compiler_cb, get_file
from voicetrainer.compile_interface import FileType
from voicetrainer.aiotk import (
    Root,
    OkCancelDialog,
    InfoDialog,
    SaveFileDialog,
    ErrorDialog,
    PortSelection,
    Messages)
from voicetrainer.gui_elements import (
    Frame, Notebook, Label, Button)
from voicetrainer.play import set_err_cb as set_play_err_cb
from voicetrainer.play import PortFinder, list_ports, stop, set_pmidi_port
from voicetrainer.exercise import ExerciseMixin
from voicetrainer.song import SongMixin

class MainWindow(ExerciseMixin, SongMixin):

    """Voicetrainer application."""

    def __init__(self, root):
        self.data_path = Path().home().joinpath('.voicetrainer')
        self.data_path.mkdir(exist_ok=True)
        self.include_path = self.data_path.joinpath('include')
        self.include_path.mkdir(exist_ok=True)
        self.root = root

        # compiler state
        self.compiler_count = 0
        set_compiler_cb(self.update_compiler)

        self.messages = []
        self.messages_read = 0
        self.msg_window = None
        set_compile_err_cb(self.new_message)
        set_play_err_cb(self.new_message)

        # midi state
        self.port = None
        self.port_match = 'FLUID'
        asyncio.ensure_future(self.find_port())

        # gui elements storage
        self.create_widgets()

        ExerciseMixin.__init__(self)
        SongMixin.__init__(self)

        self.restore_state()

    async def find_port(self):
        """Find qsynth port."""
        try:
            port_finder = PortFinder(self.port_match)
            async for port in port_finder:
                if port is not None:
                    self.port = port
                    set_pmidi_port(port)
                else:
                    await asyncio.sleep(5)
                    port_finder.match = self.port_match
            self.port_label.set_text('pmidi port: {}'.format(self.port))
        except Exception as err:
            ErrorDialog(
                self.root,
                data="Could not find midi port\n{}".format(str(err)))
            raise

    async def select_port(self, pmidi=True):
        """Change port matching."""
        # FIXME: stay away from private mixin properties
        # pylint: disable=access-member-before-definition,invalid-name
        # pylint: disable=attribute-defined-outside-init
        selection_dialog = PortSelection(
            self.root,
            data=await list_ports(pmidi=pmidi),
            current_port=str(self.port_match) if pmidi else str(self._SongMixin__jpmidi_port))
        if pmidi:
            self.port_match = await selection_dialog.await_data()
            if self.port is not None:
                # not currently searching for port, start
                self.port = None
                self.port_label.set_text('pmidi port: None')
                await self.find_port()
        else:
            self._SongMixin__jpmidi_port = await selection_dialog.await_data()

    def create_widgets(self):
        """Put some stuff up to look at."""
        self.window = Frame(self.root)
        self.window.rowconfigure(0, weight=1)
        self.window.columnconfigure(2, weight=1)
        self.window.grid(column=0, row=0, sticky=tk.N+tk.S+tk.E+tk.W)
        self.top = self.window.winfo_toplevel()
        self.top.rowconfigure(0, weight=1)
        self.top.columnconfigure(0, weight=1)
        self.top.title("VoiceTrainer")
        self.top.protocol(
            "WM_DELETE_WINDOW",
            lambda: asyncio.ensure_future(self.quit()))

        # self.top menu
        self.menubar = tk.Menu(self.top)
        self.top['menu'] = self.menubar

        self.file_menu = tk.Menu(self.menubar)
        self.menubar.add_cascade(label='File', menu=self.file_menu)
        self.file_menu.add_command(
            label='Select port',
            command=lambda: asyncio.ensure_future(self.select_port()))
        self.file_menu.add_separator()
        self.file_menu.add_command(
            label='Export midi',
            command=lambda: asyncio.ensure_future(
                self.export(FileType.midi)))
        self.file_menu.add_command(
            label='Export png',
            command=lambda: asyncio.ensure_future(
                self.export(FileType.png)))
        self.file_menu.add_command(
            label='Export pdf',
            command=lambda: asyncio.ensure_future(
                self.export(FileType.pdf)))
        self.file_menu.add_command(
            label='Export lilypond',
            command=lambda: asyncio.ensure_future(
                self.export(FileType.lily)))
        self.file_menu.add_separator()
        self.file_menu.add_command(
            label='Save state',
            command=self.save_state)
        self.file_menu.add_command(
            label='Clear cache',
            command=lambda: asyncio.ensure_future(
                self.clear_cache()))
        self.file_menu.add_command(
            label='Quit',
            command=lambda: asyncio.ensure_future(self.quit()))

        self.notebook = Notebook(self.window)
        self.notebook.grid(
            column=0, row=0, columnspan=3, sticky=tk.N+tk.S+tk.E+tk.W)
        self.notebook.rowconfigure(0, weight=1)
        self.notebook.columnconfigure(0, weight=1)
        self.separators = []

        self.statusbar = Frame(self.window)
        self.statusbar.grid(row=1, column=0, sticky=tk.N+tk.W)

        self.compiler_label = Label(self.statusbar, text="Compiler:")
        self.compiler_label.grid(row=0, column=0, sticky=tk.N+tk.E)
        self.progress = ttk.Progressbar(
            self.statusbar.raw,
            mode='indeterminate',
            orient=tk.HORIZONTAL)
        self.progress.grid(row=0, column=1, sticky=tk.N+tk.W)

        sep = ttk.Separator(self.statusbar, orient=tk.VERTICAL)
        sep.grid(row=0, column=2)
        self.separators.append(sep)

        self.port_label = Label(
            self.statusbar,
            text='pmidi port: None')
        self.port_label.grid(row=0, column=3, sticky=tk.N+tk.W)

        sep = ttk.Separator(self.statusbar, orient=tk.VERTICAL)
        sep.grid(row=0, column=4)
        self.separators.append(sep)

        self.msg_button = Button(
            self.statusbar,
            text='messages',
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
        if self.player is not None:
            await stop()
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
        data['port_match'] = self.port_match
        data['exercises'] = ExerciseMixin.save_state(self)
        data['songs'] = SongMixin.save_state(self)
        self.data_path.joinpath('state.json').write_text(
            json.dumps(data))

    def restore_state(self, _=None):
        """Restore saved settings."""
        state_file = self.data_path.joinpath('state.json')
        if not state_file.is_file():
            return
        data = json.loads(state_file.read_text())
        if 'port_match' in data:
            self.port_match = data['port_match']
        if 'exercises' in data:
            ExerciseMixin.restore_state(self, data['exercises'])
        if 'songs' in data:
            SongMixin.restore_state(self, data['songs'])

    def show_messages(self):
        """Show if there unread messages."""
        if len(self.messages) > self.messages_read:
            self.msg_button.set_text('!!!Messages!!!')
            if self.msg_window is not None:
                self.msg_window.update_data(self.messages)

    def new_message(self, msg):
        """There's a new message to report."""
        self.messages.append(msg)
        self.show_messages()

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
        self.msg_button.set_text('Messages')

    def on_close_msg_window(self, _):
        """Messages window was closed."""
        self.msg_window = None

    def update_compiler(self, delta_compilers: int):
        """Set compiler progress bar status."""
        self.compiler_count += delta_compilers
        if self.compiler_count > 0:
            self.progress.start()
        else:
            self.progress.stop()

    async def clear_cache(self):
        """Remove all compiled files."""
        # confirm
        confirm_remove = OkCancelDialog(
            self.root,
            "This will remove all compiled files. Are you sure?")
        if not await confirm_remove.await_data():
            return

        await ExerciseMixin.clear_cache(self)
        await SongMixin.clear_cache(self)

    async def export(self, file_type: FileType):
        """Export compiled data."""
        tab_name = self.notebook.get()[1]
        if tab_name == 'Songs':
            interface = await SongMixin.export(self, file_type)
        elif tab_name == 'Exercises':
            interface = await ExerciseMixin.export(self, file_type)
        else:
            return

        # get save_path
        file_name = interface.get_filename(file_type)
        save_dialog = SaveFileDialog(
            self.root,
            dir_or_file=Path('~'),
            default=file_name.name)
        save_path = await save_dialog.await_data()
        if save_path is None:
            return

        # compile and save
        if file_type is FileType.lily:
            # we don't compile lily
            save_path.write_text(
                interface.get_final_lily_code(file_type))
            InfoDialog(self.root, data="Export complete")
            return
        await get_file(interface, file_type)

        save_path.write_bytes(file_name.read_bytes())
        InfoDialog(self.root, data="Export complete")

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
