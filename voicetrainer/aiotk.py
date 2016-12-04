"""Asyncio ready tkinter classes."""
import tkinter as tk
from tkinter import ttk
import asyncio
from pathlib import Path
import fnmatch

class Root(tk.Tk):

    """
    The root of the asyncio tk application.

    Inspired by: https://bugs.python.org/file43899/loop_tk3.py
    """

    def __init__(self, loop, interval=.05):
        super().__init__()
        self.loop = loop
        self.windows = []
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.updater(interval)

    def updater(self, interval):
        """Keep tkinter active and responsive."""
        self.update()
        self.loop.call_later(interval, self.updater, interval)

    def register_window(self, window):
        """Keep reference to window and take care of graceful exit."""
        self.windows.append(window)

    def unregister_window(self, window):
        """Window is destroyed and does not need tracking."""
        pos = self.windows.index(window)
        del self.windows[pos]

    def close(self, crash=False):
        """Close application and stop event loop."""
        if crash:
            # keyboard interrupt, main window did not close
            self.destroy()
        for task in asyncio.Task.all_tasks(loop=self.loop):
            task.cancel()
        self.loop.stop()

class Dialog:

    """Short lived secondary window for user communication."""

    def __init__(self, root, data=None, on_close=None):
        self.root = root
        self.root.register_window(self)
        self.data = data
        self.return_data = None
        self.return_event = asyncio.Event()
        self.on_close = on_close
        self.top = tk.Toplevel(self.root)
        self.visibility = asyncio.Event()
        self.top.bind('<Visibility>', lambda _=None: self.visibility.set())
        self.frame = tk.Frame(self.top)
        self.top.rowconfigure(0, weight=1)
        self.top.columnconfigure(0, weight=1)

        self.frame.rowconfigure(0, weight=1)
        self.frame.columnconfigure(0, weight=1)
        self.frame.grid(sticky=tk.N+tk.E+tk.S+tk.W)
        self.create_widgets()

    def create_widgets(self):
        """Populate frame."""
        pass

    async def await_data(self):
        """Sleep until data can be returned."""
        await self.return_event.wait()
        self.close()
        return self.return_data

    def close(self):
        """Close this window."""
        self.top.destroy()
        if self.on_close is not None:
            self.on_close(self.return_data)
        self.root.unregister_window(self)

class OkCancelDialog(Dialog):

    """Ask comfirmation."""

    def create_widgets(self):
        """Show question."""
        self.top.protocol('WM_DELETE_WINDOW', self.cancel)
        self.top.title("Confirm")

        self.label = ttk.Label(self.frame, text=self.data)
        self.label.grid(row=0, column=0, columnspan=2)
        self.ok_button = ttk.Button(
            self.frame, text="Ok", command=self.confirm)
        self.ok_button.grid(row=1, column=0)
        self.cancel_button = ttk.Button(
            self.frame, text="Cancel", command=self.cancel)
        self.cancel_button.grid(row=1, column=1)

    def confirm(self, _=None):
        """User pressed ok."""
        self.return_data = True
        self.return_event.set()

    def cancel(self, _=None):
        """User pressed cancel."""
        self.return_data = False
        self.return_event.set()

class InfoDialog(Dialog):

    """Display info."""

    def create_widgets(self):
        """Show info."""
        self.top.title("Info")

        self.label = ttk.Label(self.frame, text=self.data)
        self.label.grid(row=0, column=0)
        self.button = ttk.Button(
            self.frame, text="OK", command=self.close)
        self.button.grid(row=1, column=0)

class ErrorDialog(Dialog):

    """Display error."""

    def create_widgets(self):
        """Show error."""
        self.top.title("Error")

        self.label = ttk.Label(self.frame, text=self.data)
        self.label.grid(row=0, column=0)
        self.button = ttk.Button(
            self.frame, text="OK", command=self.close)
        self.button.grid(row=1, column=0)

# pylint: disable=too-many-instance-attributes
class Messages(Dialog):

    """Display messages."""

    def create_widgets(self):
        """Show messages."""
        self.top.title("Messages")

        self.canvas = tk.Canvas(self.frame)
        self.scrollframe = tk.Frame(self.canvas)
        self.scrollframe.grid(row=0, column=0, sticky=tk.N+tk.E+tk.S+tk.W)

        scrollbar = tk.Scrollbar(
            self.frame, orient=tk.VERTICAL, command=self.canvas.yview)
        self.scrollbar = scrollbar
        scrollbar.grid(row=0, column=1, sticky=tk.N+tk.S+tk.E)

        self.canvas.configure(yscrollcommand=scrollbar.set)
        self.canvas.create_window((0, 0), window=self.scrollframe, anchor='nw')
        self.canvas.grid(row=0, column=0, sticky=tk.N+tk.E+tk.S+tk.W)
        self.canvas.rowconfigure(0, weight=1)
        self.canvas.columnconfigure(0, weight=1)
        self.scrollframe.bind(
            "<Configure>",
            lambda _: self.canvas.configure(
                scrollregion=self.canvas.bbox("all")))
        self.scrollframe.rowconfigure(0, weight=1)
        self.scrollframe.columnconfigure(0, weight=1)

        self.strvar = tk.StringVar()
        self.strvar.set("\n".join(self.data))
        self.label = ttk.Label(
            self.scrollframe,
            textvariable=self.strvar)
        self.label.grid(row=0, column=0, sticky=tk.N+tk.S+tk.W)

        self.button = ttk.Button(
            self.frame, text='Close', command=self.close)
        self.button.grid(row=1, column=0)

        self.resize = ttk.Sizegrip(self.frame)
        self.resize.grid(row=1, column=1, sticky=tk.S+tk.E)

    def update_data(self, data):
        """New data."""
        self.data = data
        self.strvar.set('\n'.join(self.data))
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def to_front(self):
        """Bring window to front."""
        self.top.lift()

# file dialogs adapted from:
# https://hg.python.org/cpython/file/tip/Lib/tkinter/filedialog.py

# pylint: disable=no-member
class FileDialog(Dialog):

    """Standard file selection dialog -- no checks on selected file."""

    title = "File Selection Dialog"

    def create_widgets(self):
        """Populate dialog with widgets."""
        self.directory = None

        self.top.title(self.title)
        self.top.iconname(self.title)

        self.botframe = tk.Frame(self.frame)
        self.botframe.pack(side=tk.BOTTOM, fill=tk.X)

        self.selection = tk.Entry(self.frame)
        self.selection.pack(side=tk.BOTTOM, fill=tk.X)
        self.selection.bind('<Return>', self.ok_event)

        self.filter = tk.Entry(self.frame)
        self.filter.pack(side=tk.TOP, fill=tk.X)
        self.filter.bind('<Return>', self.filter_command)

        self.midframe = tk.Frame(self.frame)
        self.midframe.pack(expand=tk.YES, fill=tk.BOTH)

        self.filesbar = tk.Scrollbar(self.midframe)
        self.filesbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.files = tk.Listbox(
            self.midframe,
            exportselection=0,
            yscrollcommand=(self.filesbar, 'set'))
        self.files.pack(side=tk.RIGHT, expand=tk.YES, fill=tk.BOTH)
        btags = self.files.bindtags()
        self.files.bindtags(btags[1:] + btags[:1])
        self.files.bind('<ButtonRelease-1>', self.files_select_event)
        self.files.bind(
            '<Double-ButtonRelease-1>', self.files_double_event)
        self.filesbar.config(command=(self.files, 'yview'))

        self.dirsbar = tk.Scrollbar(self.midframe)
        self.dirsbar.pack(side=tk.LEFT, fill=tk.Y)
        self.dirs = tk.Listbox(
            self.midframe,
            exportselection=0,
            yscrollcommand=(self.dirsbar, 'set'))
        self.dirs.pack(side=tk.LEFT, expand=tk.YES, fill=tk.BOTH)
        self.dirsbar.config(command=(self.dirs, 'yview'))
        btags = self.dirs.bindtags()
        self.dirs.bindtags(btags[1:] + btags[:1])
        self.dirs.bind('<ButtonRelease-1>', self.dirs_select_event)
        self.dirs.bind(
            '<Double-ButtonRelease-1>', self.dirs_double_event)

        self.ok_button = tk.Button(
            self.botframe,
            text="OK",
            command=lambda _=None: asyncio.ensure_future(self.ok_command()))
        self.ok_button.pack(side=tk.LEFT)
        self.filter_button = tk.Button(
            self.botframe, text="Filter", command=self.filter_command)
        self.filter_button.pack(side=tk.LEFT, expand=tk.YES)
        self.cancel_button = tk.Button(
            self.botframe, text="Cancel", command=self.cancel_command)
        self.cancel_button.pack(side=tk.RIGHT)

        self.top.protocol('WM_DELETE_WINDOW', self.cancel_command)
        self.top.bind('<Alt-w>', self.cancel_command)
        self.top.bind('<Alt-W>', self.cancel_command)

    # pylint: disable=too-many-arguments
    def __init__(
            self,
            root,
            data=None,
            on_close=None,
            dir_or_file=Path.cwd(),
            pattern="*",
            default=None):
        super().__init__(root, data=data, on_close=on_close)
        dir_or_file = dir_or_file.expanduser()
        if dir_or_file.is_dir():
            self.directory = dir_or_file.resolve()
        else:
            self.directory = dir_or_file.parents[0].resolve()
        self.set_filter(pattern)
        if default is not None:
            self.set_selection(self.directory.joinpath(default))
        else:
            self.set_selection(self.directory)
        self.filter_command()
        self.selection.focus_set()
        self.return_data = None
        asyncio.ensure_future(self.grab_set())

    async def grab_set(self):
        """Hack because __init__ can't be a coroutine."""
        # blocking wait
        # self.top.wait_visibility() # window needs to be visible for the grab
        await self.visibility.wait()
        self.top.grab_set()

    async def await_data(self):
        """Sleep until data can be returned."""
        await self.return_event.wait()
        self.close()
        return self.return_data

    def quit(self, how=None):
        """Return data via self.await_data."""
        self.return_data = how
        self.return_event.set()

    def dirs_double_event(self, _):
        """Doubleclick on dir."""
        self.filter_command()

    def dirs_select_event(self, _):
        """Directory selected."""
        subdir = self.dirs.get('active')
        self.directory = self.directory.joinpath(subdir).resolve()
        self.set_selection(self.directory)
        self.filter_command()

    def files_double_event(self, _):
        """Doubleclick on file."""
        asyncio.ensure_future(self.ok_command())

    def files_select_event(self, _):
        """File selected."""
        file_ = self.files.get('active')
        self.set_selection(self.directory.joinpath(file_))

    def ok_event(self, _):
        """Return was pressed with file selected."""
        asyncio.ensure_future(self.ok_command())

    async def ok_command(self, _=None):
        """We have a file."""
        self.quit(self.get_selection())

    def filter_command(self, _=None):
        """Update viewport."""
        # fetch filter from user
        self.pattern = self.filter.get()
        subdirs = [Path('..')]
        matchingfiles = []
        for name in sorted(self.directory.glob('*')):
            if name.is_dir():
                subdirs.append(name.name)
            elif fnmatch.fnmatch(name.name, self.pattern):
                matchingfiles.append(name.name)
        self.dirs.delete(0, tk.END)
        for name in subdirs:
            self.dirs.insert(tk.END, name)
        self.files.delete(0, tk.END)
        for name in matchingfiles:
            self.files.insert(tk.END, name)

    def get_selection(self):
        """Get seleted pach/file from widget."""
        return Path(self.selection.get()).expanduser()

    def cancel_command(self, _=None):
        """Exit without selecting file."""
        self.quit()

    def set_filter(self, pattern: str):
        """Update filter pattern."""
        self.pattern = pattern
        self.filter.delete(0, tk.END)
        self.filter.insert(tk.END, pattern)

    def set_selection(self, file_):
        """Update selection path in viewport."""
        self.selection.delete(0, tk.END)
        self.selection.insert(
            tk.END,
            str(file_))

class LoadFileDialog(FileDialog):

    """File selection dialog which checks that the file exists."""

    title = "Load File Selection Dialog"

    async def ok_command(self, _=None):
        file_ = self.get_selection()
        if not file_.is_file():
            self.root.bell()
        else:
            self.quit(file_)

class SaveFileDialog(FileDialog):

    """File selection dialog which checks that the file may be created."""

    title = "Save File Selection Dialog"

    async def ok_command(self, _=None):
        file_ = self.get_selection()
        if file_.exists():
            if file_.is_dir():
                self.root.bell()
                return
            confirm_dialog = OkCancelDialog(
                self.root,
                data="Overwrite existing file {}?".format(file_))
            confirm_overwrite = await confirm_dialog.await_data()
            if not confirm_overwrite:
                return
        self.quit(file_)
