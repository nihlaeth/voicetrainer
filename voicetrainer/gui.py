"""Simple user interface."""
from tkinter import ttk
import tkinter as tk
from tkinter.messagebox import showerror
import asyncio
from os.path import isfile, join, dirname, realpath
from os import listdir
from itertools import product
from random import choice

from voicetrainer.play import (
    get_qsynth_port,
    play_midi,
    stop_midi,
    exec_on_midi_end)
from voicetrainer.compile import compile_ex, compile_all

# pylint: disable=too-many-instance-attributes,too-many-locals
# pylint: disable=too-many-statements
# It's messy, but there simply too many references to keep alive.
# pylint: disable=broad-except
# because of asyncio exceptions are only displayed at exit, we
# want to give the user immediate feedback.
class Application(tk.Tk):

    """
    Async user interface.

    Inspired by: https://bugs.python.org/file43899/loop_tk3.py
    """

    def __init__(self, loop, interval=.05):
        super().__init__()
        self.data_path = join(dirname(realpath(__file__)), "../exercises/")
        self.pitch_list = [note + octave for octave, note in product(
            [',', '', '\''],
            list("cdefgab"))]
        self.loop = loop
        self.protocol("WM_DELETE_WINDOW", self.close)

        # midi state
        self.port = None
        self.player = None
        self.stopping = False
        self.play_next = False

        # gui elements storage
        self.notebook = None
        self.resize = None
        self.tabs = []
        self.bpm = []
        self.labels = []
        self.control_vars = []
        self.scrolling = []
        self.pitches = []
        self.sheets = []
        self.controls = []
        self.image_cache = {}
        self.create_widgets()
        self.updater(interval)

    def create_tab(self, tab: ttk.Frame, tab_num: int) -> None:
        """Populate exercise tab."""
        # init storage dicts
        self.labels.append({})
        self.control_vars.append({})
        self.scrolling.append({})
        self.controls.append({})

        # bpm selector
        bpm_label = ttk.Label(tab, text="bpm:")
        self.labels[tab_num]['bpm'] = bpm_label
        bpm_label.grid(column=2, row=0, sticky=tk.N+tk.W)
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
        bpm.grid(column=3, row=0, sticky=tk.W+tk.N)

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

        listbox.insert(0, *self.pitch_list)
        listbox.selection_set(7, 14)

        # controls
        frame = ttk.Frame(tab)
        self.controls[tab_num]['frame'] = frame
        frame.grid(column=2, row=2, columnspan=2, sticky=tk.W+tk.N)
        # sound pitch random autonext next play/stop

        soundvar = tk.StringVar()
        soundvar.set("Mi")
        self.control_vars[tab_num]['sound'] = soundvar
        sound = tk.OptionMenu(
            frame,
            soundvar,
            *["Mi", "Na", "Noe", "Nu", "No"],
            command=lambda _: asyncio.ensure_future(self.update_sheet()))
        self.controls[tab_num]['sound'] = sound
        sound.grid(column=0, row=0, sticky=tk.W+tk.N)

        textvar = tk.StringVar()
        textvar.set(self.pitch_list[listbox.curselection()[0]])
        self.control_vars[tab_num]['curr_pitch'] = textvar
        curr_pitch = tk.OptionMenu(
            frame,
            textvar,
            *self.pitch_list,
            command=lambda _: asyncio.ensure_future(
                self.on_pitch_change()))
        self.controls[tab_num]['pitch'] = curr_pitch
        curr_pitch.grid(column=1, row=0, sticky=tk.W+tk.N)

        rand_int = tk.IntVar()
        self.control_vars[tab_num]['random'] = rand_int
        random = ttk.Checkbutton(frame, text="random", variable=rand_int)
        self.controls[tab_num]['random'] = random
        random.grid(column=2, row=0, sticky=tk.W+tk.N)

        auto_int = tk.IntVar()
        self.control_vars[tab_num]['autonext'] = auto_int
        autonext = ttk.Checkbutton(
            frame, text="autonext", variable=auto_int)
        self.controls[tab_num]['autonext'] = autonext
        autonext.grid(column=3, row=0, sticky=tk.W+tk.N)

        next_ = ttk.Button(
            frame,
            text="next",
            command=lambda: asyncio.ensure_future(self.next_()))
        self.controls[tab_num]['next_'] = next_
        next_.grid(column=4, row=0, sticky=tk.W+tk.N)

        play_stop = tk.StringVar()
        play_stop.set("play")
        self.control_vars[tab_num]['play_stop'] = play_stop
        play = ttk.Button(
            frame,
            textvariable=play_stop,
            command=lambda: asyncio.ensure_future(self.play_or_stop()))
        self.controls[tab_num]['play'] = play
        play.grid(column=5, row=0, sticky=tk.W+tk.N)

        # sheet display
        sheet = ttk.Label(tab)
        self.sheets.append(sheet)
        sheet.grid(column=2, row=1, columnspan=2, sticky=tk.N+tk.W)
        asyncio.ensure_future(self.update_sheet())

    def create_widgets(self):
        """Put some stuff up to look at."""
        top = self.winfo_toplevel()
        top.rowconfigure(0, weight=1)
        top.columnconfigure(0, weight=1)
        top.title("VoiceTrainer")

        # top menu
        self.menubar = tk.Menu(top)
        top['menu'] = self.menubar
        self.file_menu = tk.Menu(self.menubar)
        self.menubar.add_cascade(label='File', menu=self.file_menu)
        self.file_menu.add_command(
            label='Recompile',
            command=lambda: asyncio.ensure_future(
                compile_all(self.data_path)))
        self.file_menu.add_command(label='Quit', command=self.close)

        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)
        self.notebook = ttk.Notebook(self)
        exercises = []
        for item in listdir(self.data_path):
            if isfile(join(self.data_path, item)) and \
                    item.endswith('.ly') and not \
                    item.endswith('-midi.ly'):
                exercises.append(item[:-3])
        for ex in exercises:
            tab = ttk.Frame(self.notebook)
            tab.rowconfigure(1, weight=1)
            tab.columnconfigure(3, weight=1)
            self.notebook.add(tab, text=ex)
            self.tabs.append(tab)
            self.create_tab(tab, len(self.tabs) - 1)
        self.notebook.grid(column=0, row=0, sticky=tk.N+tk.S+tk.E+tk.W)
        self.resize = ttk.Sizegrip(self).grid(row=1, sticky=tk.S+tk.E)

    def updater(self, interval):
        """Keep tkinter active and responsive."""
        self.update()
        self.loop.call_later(interval, self.updater, interval)

    def close(self):
        """Close application and stop event loop."""
        for task in asyncio.Task.all_tasks(loop=self.loop):
            task.cancel()
        self.loop.stop()
        self.destroy()

    @property
    def tab_num(self):
        """Return index of current tab."""
        tab_id = self.notebook.select()
        return self.notebook.index(tab_id)

    async def update_sheet(self):
        """Display relevant sheet."""
        png = await self.get_file()
        if png not in self.image_cache:
            self.image_cache[png] = tk.PhotoImage(file=png)
        self.sheets[self.tab_num].config(image=self.image_cache[png])

    async def on_pitch_change(self):
        """New pitch was picked by user or app."""
        asyncio.ensure_future(self.update_sheet())
        if self.player is not None:
            self.play_next = True
            await self.stop()
        else:
            await self.play()

    async def next_(self):
        """Skip to next exercise."""
        curr_pitch = self.control_vars[self.tab_num]['curr_pitch'].get()
        curr_pos = self.pitch_list.index(curr_pitch)
        pitch_pos = curr_pos
        pitch_selection = self.pitches[self.tab_num].curselection()
        if len(pitch_selection) == 0:
            return
        if self.control_vars[self.tab_num]['random'].get() == 1:
            while pitch_pos == curr_pos:
                pitch_pos = choice(pitch_selection)
        elif curr_pos in pitch_selection:
            if pitch_selection.index(curr_pos) >= len(pitch_selection) - 1:
                # TODO: cycle through sounds
                pitch_pos = pitch_selection[0]
            else:
                pitch_pos = pitch_selection[
                    pitch_selection.index(curr_pos) + 1]
        else:
            while pitch_pos not in pitch_selection:
                pitch_pos += 1
                if pitch_pos >= len(self.pitch_list):
                    pitch_pos = 0
        self.control_vars[self.tab_num]['curr_pitch'].set(
            self.pitch_list[pitch_pos])
        # I thought tkinter would call this, but apparently not
        await self.on_pitch_change()

    async def play_or_stop(self):
        """Play or stop midi."""
        if self.player is not None:
            # user stopped playback
            self.stopping = True
            await self.stop()
        else:
            await self.play()

    async def get_file(self, midi: bool=False) -> str:
        """Assemble file_name, compile if non-existent."""
        tab_name = self.notebook.tab(self.tab_num)['text']
        pitch = self.control_vars[self.tab_num]['curr_pitch'].get()
        bpm = self.bpm[self.tab_num].get()
        sound = self.control_vars[self.tab_num]['sound'].get()
        if midi:
            extension = "-midi.ly"
            file_name = join(
                self.data_path,
                "{}-{}bpm-{}.midi".format(tab_name, bpm, pitch))
        else:
            extension = ".ly"
            file_name = join(
                self.data_path,
                "{}-{}-{}.png".format(tab_name, pitch, sound))
        if not isfile(file_name):
            try:
                log = await compile_ex(
                    join(
                        self.data_path,
                        "{}{}".format(tab_name, extension)),
                    [bpm],
                    [pitch],
                    [sound])
                if len(log[0][0]) > 0 or len(log[0][1]) > 1:
                    showerror("lilyponderror", "{}\n{}".format(
                        log[0][0], log[0][1]))
            except Exception as err:
                showerror("Could not compile exercise", str(err))
                raise
        return file_name

    async def play(self):
        """Play midi file."""
        midi = await self.get_file(midi=True)
        if self.port is None:
            try:
                self.port = "..."
                self.port = await get_qsynth_port()
            except Exception as err:
                showerror("Could not find midi port", str(err))
                raise
        elif self.port == "...":
            # already spawned port searching proc
            return
        try:
            self.player = await play_midi(self.port, midi)
        except Exception as err:
            showerror("Could not start midi playback", str(err))
            raise
        self.control_vars[self.tab_num]['play_stop'].set("stop")
        asyncio.ensure_future(exec_on_midi_end(
            self.player,
            self.on_midi_stop))

    async def stop(self):
        """Stop midi regardless of state."""
        if self.player is not None:
            await stop_midi(self.player)

    async def on_midi_stop(self):
        """Handle end of midi playback."""
        self.player = None
        if self.stopping:
            self.play_next = False
            self.control_vars[self.tab_num]['play_stop'].set("play")
            return
        if self.play_next or \
                self.control_vars[self.tab_num]['autonext'].get() == 1:
            self.play_next = False
            await self.next_()
            return
        self.control_vars[self.tab_num]['play_stop'].set("play")

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
