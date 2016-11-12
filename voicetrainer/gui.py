"""Simple user interface."""
from tkinter import ttk
import tkinter as tk
import asyncio
from os.path import isfile, join, dirname, realpath
from os import listdir
from itertools import product

class Application(tk.Tk):

    """
    Simple user interface.

    Inspired by: https://bugs.python.org/file43899/loop_tk3.py
    """

    def __init__(self, loop, interval=.01):
        super().__init__()
        self.data_path = join(dirname(realpath(__file__)), "../exercises/")
        self.loop = loop
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.tasks = []
        self.notebook = None
        self.tabs = []
        self.bpm = []
        self.labels = []
        self.control_vars = []
        self.scrolling = []
        self.pitches = []
        self.create_widgets()
        self.updater(interval)

    def create_tab(self, exercise: str, tab: ttk.Frame, tab_num: int) -> None:
        # init storage dicts
        self.labels.append({})
        self.control_vars.append({})
        self.scrolling.append({})

        # bpm selector
        bpm_label = ttk.Label(tab, text="bpm:")
        self.labels[tab_num]['bpm'] = bpm_label
        bpm_label.grid(column=2, row=0)
        bpm = tk.Scale(
            tab,
            from_=80,
            to=160,
            tickinterval=10,
            showvalue=0,
            length=300,
            resolution=10,
            orient=tk.HORIZONTAL)
        bpm.set(140)
        self.bpm.append(bpm)
        bpm.grid(column=3, row=0)

        # pitch selector
        scrollbar = tk.Scrollbar(tab, orient=tk.VERTICAL)
        self.scrolling[tab_num]['pitch'] = scrollbar
        scrollbar.grid(row=1, column=0, sticky=tk.N+tk.S+tk.W)

        listbox = tk.Listbox(
            tab,
            yscrollcommand=scrollbar.set,
            width=3,
            selectmode=tk.MULTIPLE)
        self.pitches.append(listbox)
        listbox.grid(row=1, column=1, sticky=tk.N+tk.S+tk.W)
        scrollbar['command'] = listbox.yview

        pitches = [note + octave for octave, note in product(
            [',', '', '\''],
            list("cdefgab"))]
        listbox.insert(0, *pitches)
        listbox.selection_set(7, 14)


    def create_widgets(self):
        self.notebook = ttk.Notebook(self)
        exercises = []
        for item in listdir(self.data_path):
            if isfile(join(self.data_path, item)) and \
                    item.endswith('.ly') and not \
                    item.endswith('-midi.ly'):
                exercises.append(item[:-3])
        for ex in exercises:
            tab = ttk.Frame(self.notebook)
            self.notebook.add(tab, text=ex)
            self.tabs.append(tab)
            self.create_tab(ex, tab, len(self.tabs) - 1)
        self.notebook.grid(column=0, row=0)

    def updater(self, interval):
        self.update()
        self.loop.call_later(interval, self.updater, interval)

    def close(self):
        for task in self.tasks:
            task.cancel()
        self.loop.stop()
        self.destroy()

if __name__ == "__main__":
    # pylint: disable=invalid-name
    loop_ = asyncio.get_event_loop()
    root = Application(loop_)
    try:
        loop_.run_forever()
    except KeyboardInterrupt:
        root.close()
    finally:
        loop_.close()
