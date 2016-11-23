"""Asyncio ready tkinter classes."""
import tkinter as tk
from tkinter import ttk
import asyncio
import os
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
# pylint: disable=invalid-name
dialogstates = {}

class FileDialog(Dialog):

    """
    Standard file selection dialog -- no checks on selected file.

    Usage:

        d = FileDialog(master)
        fname = d.go(dir_or_file, pattern, default, key)
        if fname is None: ...canceled...
        else: ...open file...

    All arguments to go() are optional.

    The 'key' argument specifies a key in the global dictionary
    'dialogstates', which keeps track of the values for the directory
    and pattern arguments, overriding the values passed in (it does
    not keep track of the default argument!).  If no key is specified,
    the dialog keeps no memory of previous state.  Note that memory is
    kept even when the dialog is canceled.  (All this emulates the
    behavior of the Macintosh file selection dialogs.)
    """

    title = "File Selection Dialog"

    def create_widgets(self):
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
            dir_or_file=os.curdir,
            pattern="*",
            default="",
            key=None):
        super().__init__(root, data=data, on_close=on_close)
        self.key = key
        if key and key in dialogstates:
            self.directory, pattern = dialogstates[key]
        else:
            dir_or_file = os.path.expanduser(dir_or_file)
            if os.path.isdir(dir_or_file):
                self.directory = dir_or_file
            else:
                self.directory, default = os.path.split(dir_or_file)
        self.set_filter(self.directory, pattern)
        self.set_selection(default)
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
        if self.key:
            directory, pattern = self.get_filter()
            if self.return_data:
                directory = os.path.dirname(self.return_data)
            dialogstates[self.key] = directory, pattern
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
        dir_, pat = self.get_filter()
        subdir = self.dirs.get('active')
        dir_ = os.path.normpath(os.path.join(self.directory, subdir))
        self.set_filter(dir_, pat)

    def files_double_event(self, _):
        """Doubleclick on file."""
        asyncio.ensure_future(self.ok_command())

    def files_select_event(self, _):
        """File selected."""
        file_ = self.files.get('active')
        self.set_selection(file_)

    def ok_event(self, _):
        """Return was pressed with file selected."""
        asyncio.ensure_future(self.ok_command())

    async def ok_command(self, _=None):
        """We have a file."""
        self.quit(self.get_selection())

    def filter_command(self, _=None):
        """Filter was changed."""
        dir_, pat = self.get_filter()
        try:
            names = os.listdir(dir_)
        except OSError:
            self.root.bell()
            return
        self.directory = dir_
        self.set_filter(dir_, pat)
        names.sort()
        subdirs = [os.pardir]
        matchingfiles = []
        for name in names:
            fullname = os.path.join(dir_, name)
            if os.path.isdir(fullname):
                subdirs.append(name)
            elif fnmatch.fnmatch(name, pat):
                matchingfiles.append(name)
        self.dirs.delete(0, tk.END)
        for name in subdirs:
            self.dirs.insert(tk.END, name)
        self.files.delete(0, tk.END)
        for name in matchingfiles:
            self.files.insert(tk.END, name)
        head, tail = os.path.split(self.get_selection())
        if tail == os.curdir:
            tail = ''
        self.set_selection(tail)

    def get_filter(self):
        filter_ = self.filter.get()
        filter_ = os.path.expanduser(filter_)
        if filter_[-1:] == os.sep or os.path.isdir(filter_):
            filter_ = os.path.join(filter_, "*")
        return os.path.split(filter_)

    def get_selection(self):
        file_ = self.selection.get()
        file_ = os.path.expanduser(file_)
        return file_

    def cancel_command(self, _=None):
        self.quit()

    def set_filter(self, dir_, pat):
        if not os.path.isabs(dir_):
            try:
                pwd = os.getcwd()
            except OSError:
                pwd = None
            if pwd:
                dir_ = os.path.join(pwd, dir_) 
                dir_ = os.path.normpath(dir_) 
        self.filter.delete(0, tk.END)
        self.filter.insert(
            tk.END, os.path.join(dir_ or os.curdir, pat or "*"))

    def set_selection(self, file_):
        self.selection.delete(0, tk.END)
        self.selection.insert(tk.END, os.path.join(self.directory, file_))

class LoadFileDialog(FileDialog):

    """File selection dialog which checks that the file exists."""

    title = "Load File Selection Dialog"

    async def ok_command(self):
        file_ = self.get_selection()
        if not os.path.isfile(file_):
            self.root.bell()
        else:
            self.quit(file_)

class SaveFileDialog(FileDialog):

    """File selection dialog which checks that the file may be created."""

    title = "Save File Selection Dialog"

    async def ok_command(self):
        file_ = self.get_selection()
        if os.path.exists(file_):
            if os.path.isdir(file_):
                self.root.bell()
                return
            confirm_dialog = OkCancelDialog(
                self.root,
                data="Overwrite existing file_ %r?" % (file_,))
            confirm_overwrite = await confirm_dialog.await_data()
            if not confirm_overwrite:
                return
        else:
            head, tail = os.path.split(file_)
            if not os.path.isdir(head):
                self.root.bell()
                return
        self.quit(file_)
