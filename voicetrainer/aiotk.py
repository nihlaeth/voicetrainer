"""Asyncio ready tkinter classes."""
import tkinter as tk
from tkinter import ttk
import asyncio

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
        self.top.title("Confirm")

        self.label = ttk.Label(self.frame, text=self.data)
        self.label.grid(row=0, column=0, columnspan=2)
        self.ok_button = ttk.Button(
            self.frame, text="Ok", command=self.confirm)
        self.ok_button.grid(row=1, column=0)
        self.cancel_button = ttk.Button(
            self.frame, text="Cancel", command=self.cancel)
        self.cancel_button.grid(row=1, column=1)

    def confirm(self, _):
        """User pressed ok."""
        self.return_data = True
        self.return_event.set()

    def cancel(self, _):
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
