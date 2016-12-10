"""All the song stuff."""
from tkinter import ttk
import tkinter as tk
import asyncio
from pathlib import Path
from itertools import product, chain
from functools import partial
from collections import namedtuple
from datetime import datetime

from voicetrainer.aiotk import (
    ErrorDialog,
    InfoDialog,
    OkCancelDialog,
    SaveFileDialog,
    LoadFileDialog)
from voicetrainer.play import (
    play_midi,
    exec_on_midi_end)
from voicetrainer.compile_interface import FileType, Song

# pylint: disable=too-many-instance-attributes,no-member
class SongMixin:

    """
    All the song stuff.

    This is a mixin class. If you need a method from here, call it
    specifically. To avoid naming collisions, start all properties
    with __. All properties that do not start with so_, are assumed to be
    provided the class that this is mixed in.
    """

    def __init__(self):
        self.__data_path = self.data_path.joinpath('songs')
        self.__data_path.mkdir(exist_ok=True)
        self.__pitch_list = [note + octave for octave, note in product(
            [',', '', '\''],
            list("cdefgab"))]
        self.__tabs = []
        self.__scroll_time = datetime.now()
        self.__jpmidi_port = 'system:'

        SongMixin.create_widgets(self)

    def create_tab(self, song: str) -> None:
        """Populate song tab."""
        tab = ttk.Frame(self.__notebook)
        tab.rowconfigure(0, weight=1)
        tab.columnconfigure(1, weight=1)
        self.__notebook.add(tab, text=song)
        self.__tabs.append({})
        tab_num = len(self.__tabs) - 1
        self.__tabs[tab_num]['tab'] = tab
        self.__tabs[tab_num]['page'] = 1

        config = Song(
            self.__data_path, self.include_path, song).get_config()

        # controls
        frame = ttk.Frame(tab)
        self.__tabs[tab_num]['control_frame'] = frame
        frame.grid(column=0, row=0, sticky=tk.W+tk.N)

        # bpm selector
        bpm_label = ttk.Label(frame, text="bpm:")
        self.__tabs[tab_num]['bpm_label'] = bpm_label
        bpm_label.grid(column=0, row=0, sticky=tk.N+tk.E)
        bpm = tk.Scale(
            frame,
            from_=60,
            to=240,
            tickinterval=20,
            showvalue=1,
            length=300,
            resolution=1,
            orient=tk.VERTICAL)
        if 'tempo' in config:
            bpm.set(int(config['tempo']))
        else:
            bpm.set(140)
        self.__tabs[tab_num]['bpm'] = bpm
        bpm.grid(column=1, row=0, sticky=tk.W+tk.N)

        key_label = ttk.Label(frame, text="key:")
        self.__tabs[tab_num]['key_label'] = key_label
        key_label.grid(column=0, row=1, sticky=tk.N+tk.E)
        textvar = tk.StringVar()
        if 'key' in config:
            textvar.set(config['key'])
        else:
            textvar.set('c')
        self.__tabs[tab_num]['curr_pitch'] = textvar
        curr_pitch = tk.OptionMenu(
            frame,
            textvar,
            *self.__pitch_list,
            command=lambda _: asyncio.ensure_future(
                SongMixin.on_pitch_change(self)))
        self.__tabs[tab_num]['pitch_menu'] = curr_pitch
        curr_pitch.grid(column=1, row=1, sticky=tk.W+tk.N)

        if 'measures' in config:
            max_measure = int(config['measures'])
        else:
            max_measure = 1
        measure = tk.Spinbox(
            frame,
            width=3,
            from_=1,
            to=max_measure,
            increment=1)
        measure_label = ttk.Label(frame, text="start from measure:")
        self.__tabs[tab_num]['measure_label'] = measure_label
        measure_label.grid(column=0, row=2, sticky=tk.N+tk.E)
        self.__tabs[tab_num]['curr_measure'] = measure
        measure.grid(column=1, row=2, sticky=tk.W+tk.N)

        velocity = tk.Spinbox(
            frame,
            width=3,
            from_=-50,
            to=50,
            increment=1)
        velocity_label = ttk.Label(frame, text="relative velocity:")
        self.__tabs[tab_num]['velocity_label'] = velocity_label
        velocity_label.grid(column=0, row=3, sticky=tk.N+tk.E)
        self.__tabs[tab_num]['velocity'] = velocity
        velocity.grid(column=1, row=3, sticky=tk.W+tk.N)

        iframe = ttk.LabelFrame(frame, text="Instruments:")
        self.__tabs[tab_num]['iframe'] = iframe
        iframe.grid(column=0, row=4, columnspan=2, sticky=tk.N+tk.E+tk.W+tk.S)

        self.__tabs[tab_num]['instruments'] = {}
        self.__tabs[tab_num]['icheckboxes'] = []
        for i, instrument in enumerate(config['instruments']):
            intvar = tk.IntVar()
            intvar.set(True)
            checkbox = ttk.Checkbutton(
                iframe, text=instrument, variable=intvar)
            checkbox.grid(column=0, row=i, sticky=tk.N+tk.W)
            self.__tabs[tab_num]['instruments'][instrument] = intvar
            self.__tabs[tab_num]['icheckboxes'].append(checkbox)

        first_page = ttk.Button(
            frame,
            text='First page',
            command=lambda: SongMixin.change_page(self, page=1))
        self.__tabs[tab_num]['first_page'] = first_page
        first_page.grid(column=0, row=5, columnspan=2, sticky=tk.W+tk.N+tk.E)

        next_page = ttk.Button(
            frame,
            text='Next page',
            command=lambda: SongMixin.change_page(self))
        self.__tabs[tab_num]['next_page'] = next_page
        next_page.grid(column=0, row=6, columnspan=2, sticky=tk.W+tk.N+tk.E)

        prev_page = ttk.Button(
            frame,
            text='Previous page',
            command=lambda: SongMixin.change_page(self, increment=False))
        self.__tabs[tab_num]['prev_page'] = prev_page
        prev_page.grid(column=0, row=7, columnspan=2, sticky=tk.W+tk.N+tk.E)

        if 'pages' in config:
            num_pages = int(config['pages'])
        else:
            num_pages = 1
        last_page = ttk.Button(
            frame,
            text='Last page',
            command=lambda last=num_pages: SongMixin.change_page(
                self, page=last))
        self.__tabs[tab_num]['last_page'] = last_page
        last_page.grid(column=0, row=8, columnspan=2, sticky=tk.W+tk.N+tk.E)

        play_stop = tk.StringVar()
        play_stop.set("play")
        self.__tabs[tab_num]['play_stop'] = play_stop
        play = ttk.Button(
            frame,
            textvariable=play_stop,
            command=lambda: asyncio.ensure_future(
                SongMixin.play_or_stop(self)))
        self.__tabs[tab_num]['play'] = play
        play.grid(column=0, row=9, columnspan=2, sticky=tk.W+tk.N+tk.E)

        # sheet display
        sheet = tk.Canvas(tab, bd=0, highlightthickness=0)
        sheet.bind(
            "<Configure>",
            lambda e, num=tab_num: asyncio.ensure_future(
                SongMixin.resize_sheet(self, e, num)))
        self.__tabs[tab_num]['sheet'] = sheet
        sheet.grid(column=1, row=0, sticky=tk.N+tk.W+tk.S+tk.E)

        # sheet mouse events
        sheet.bind(
            "<Button-1>",
            lambda e: SongMixin.change_page(self))
        sheet.bind(
            "<Button-4>",
            lambda e: SongMixin.change_page(
                self, scroll=True, increment=False))
        sheet.bind(
            "<Button-5>",
            lambda e: SongMixin.change_page(self, scroll=True))

        asyncio.ensure_future(
            SongMixin.update_sheet(self, tab_num=tab_num))

    def create_widgets(self):
        """Put some stuff up to look at."""
        self.__menu = tk.Menu(self.menubar)
        self.menubar.add_cascade(label='Songs', menu=self.__menu)
        self.__menu.add_command(label='Midi', state=tk.DISABLED)
        self.__menu.add_command(
            label='Select jpmidi port',
            command=lambda: asyncio.ensure_future(
                self.select_port(pmidi=False)))
        self.__menu.add_separator()
        self.__menu.add_command(label='Options', state=tk.DISABLED)
        self.__midi_executable = tk.StringVar()
        self.__midi_executable.set('pmidi')
        self.__menu.add_radiobutton(
            label='pmidi',
            value='pmidi',
            variable=self.__midi_executable)
        self.__menu.add_radiobutton(
            label='jpmidi',
            value='jpmidi',
            variable=self.__midi_executable)
        self.__await_jack = tk.IntVar()
        self.__await_jack.set(False)
        self.__menu.add_checkbutton(
            label='-- await jack_transport',
            variable=self.__await_jack)
        self.__menu.add_separator()
        self.__menu.add_command(
            label='Add',
            command=lambda: asyncio.ensure_future(
                SongMixin.add_song(self)))
        self.__menu.add_command(
            label='Delete',
            command=lambda: asyncio.ensure_future(
                SongMixin.remove_song(self)))
        self.__menu.add_command(
            label='Export midi',
            command=lambda: asyncio.ensure_future(
                SongMixin.export(self, FileType.midi)))
        self.__menu.add_command(
            label='Export png',
            command=lambda: asyncio.ensure_future(
                SongMixin.export(self, FileType.png)))
        self.__menu.add_command(
            label='Export pdf',
            command=lambda: asyncio.ensure_future(
                SongMixin.export(self, FileType.pdf)))
        self.__menu.add_command(
            label='Export lilypond',
            command=lambda: asyncio.ensure_future(
                SongMixin.export(self, FileType.lily)))

        self.__frame = ttk.Frame(self.notebook)
        self.notebook.add(self.__frame, text='Songs')
        self.__frame.rowconfigure(0, weight=1)
        self.__frame.columnconfigure(0, weight=1)

        self.__notebook = ttk.Notebook(self.__frame)
        for song in self.__data_path.glob('*.ly'):
            SongMixin.create_tab(self, song.stem)
        self.__notebook.grid(
            column=0, row=0, sticky=tk.N+tk.S+tk.E+tk.W)
        self.__notebook.rowconfigure(0, weight=1)
        self.__notebook.columnconfigure(0, weight=1)

    @property
    def __num(self):
        """Return index of current tab."""
        tab_id = self.__notebook.select()
        return self.__notebook.index(tab_id)

    def save_state(self):
        """Return exercise state."""
        data = {}
        data['midi_executable'] = self.__midi_executable.get()
        data['await_jack'] = self.__await_jack.get()
        data['jpmidi_port'] = self.__jpmidi_port
        for i in range(len(self.__tabs)):
            tab_name = self.__notebook.tab(i)['text']
            data[tab_name] = {}
            data[tab_name]['curr_pitch'] = self.__tabs[i]['curr_pitch'].get()
            data[tab_name]['bpm'] = self.__tabs[i]['bpm'].get()
            data[tab_name]['instruments'] = {}
            for instrument in self.__tabs[i]['instruments']:
                data[tab_name]['instruments'][instrument] = \
                    self.__tabs[i]['instruments'][instrument].get()
        return data

    def restore_state(self, data):
        """Restore saved settings."""
        if 'midi_executable' in data:
            self.__midi_executable.set(data['midi_executable'])
        if 'await_jack' in data:
            self.__await_jack.set(data['await_jack'])
        if 'jpmidi_port' in data:
            self.__jpmidi_port = data['jpmidi_port']
        for i in range(len(self.__tabs)):
            tab_name = self.__notebook.tab(i)['text']
            if tab_name not in data:
                continue
            self.__tabs[i]['curr_pitch'].set(
                data[tab_name]['curr_pitch'])
            self.__tabs[i]['bpm'].set(data[tab_name]['bpm'])
            if 'instruments' not in data[tab_name]:
                continue
            for instrument in data[tab_name]['instruments']:
                if instrument not in self.__tabs[i]['instruments']:
                    continue
                self.__tabs[i]['instruments'][instrument].set(
                    data[tab_name]['instruments'][instrument])

    def get_so_interface(self, tab_num=None):
        """Return exercise interface."""
        if tab_num is None:
            tab_num = self.__num
        tab_name = self.__notebook.tab(tab_num)['text']
        pitch = self.__tabs[tab_num]['curr_pitch'].get()
        measure = int(self.__tabs[tab_num]['curr_measure'].get())
        bpm = int(self.__tabs[tab_num]['bpm'].get())
        velocity = int(self.__tabs[tab_num]['velocity'].get())
        instruments = {}
        for instrument in self.__tabs[tab_num]['instruments']:
            instruments[instrument] = bool(
                self.__tabs[tab_num]['instruments'][instrument].get())
        return Song(
            self.__data_path,
            self.include_path,
            name=tab_name,
            pitch=pitch,
            bpm=bpm,
            start_measure=measure,
            velocity=velocity,
            instruments=instruments)

    async def export(self, file_type: FileType):
        """Export compiled data."""
        # get interface
        song = SongMixin.get_so_interface(self)

        # get save_path
        file_name = song.get_filename(file_type)
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
            save_path.write_text(song.get_final_lily_code(file_type))
            InfoDialog(self.root, data="Export complete")
            return
        await self.get_file(song, file_type)

        save_path.write_bytes(file_name.read_bytes())
        InfoDialog(self.root, data="Export complete")

    async def add_song(self):
        """Add new song."""
        dialog = LoadFileDialog(
            self.root,
            dir_or_file=Path('~'),
            pattern="*.ly")
        file_name = await dialog.await_data()
        if file_name is not None:
            path = Path(file_name)
            so_name = path.stem
            if not path.is_file():
                ErrorDialog(
                    self.root,
                    data="{} is not a file".format(path))
                return
            content = path.read_text()
            new_file = self.__data_path.joinpath("{}.ly".format(so_name))
            if new_file.is_file():
                ErrorDialog(
                    self.root,
                    data="An song with name {} already exists.".format(
                        so_name))
                return
            new_file.touch()
            new_file.write_text(content)
            SongMixin.create_tab(self, so_name)

    async def remove_song(self):
        """Remove song."""
        tab_num = self.__num
        tab_name = self.__notebook.tab(tab_num)['text']
        confirm = OkCancelDialog(
            self.root,
            data="Are you sure you want to delete {}? This cannot be undone.".format(
                tab_name))
        if not await confirm.await_data():
            return
        self.stopping = True
        await self.stop()
        tab = self.__tabs[tab_num]['tab']
        self.__notebook.forget(tab)
        tab.destroy()
        del self.__tabs[tab_num]
        file_name = Path(self.__data_path).joinpath(
            "{}.ly".format(tab_name))
        # pylint: disable=no-member
        # does too!
        file_name.unlink()

    async def clear_cache(self):
        """Remove all compiled files."""
        # remove files
        for file_ in chain(
                self.__data_path.glob("*.midi"),
                self.__data_path.glob("*.png"),
                self.__data_path.glob("*.pdf")):
            file_.unlink()

        # display fresh sheets
        for i in range(len(self.__tabs)):
            await SongMixin.update_sheet(self, tab_num=i)

    def change_page(self, increment=True, page=None, scroll=False):
        """Change page."""
        if scroll:
            delta_t = datetime.now() - self.__scroll_time
            self.__scroll_time = datetime.now()
            if delta_t.total_seconds() < 0.5:
                return
        if page is not None:
            self.__tabs[self.__num]['page'] = int(page)
        elif increment:
            self.__tabs[self.__num]['page'] += 1
        else:
            if self.__tabs[self.__num]['page'] > 1:
                self.__tabs[self.__num]['page'] -= 1
        asyncio.ensure_future(SongMixin.update_sheet(self))

    async def update_sheet(self, tab_num=None):
        """Display relevant sheet."""
        if tab_num is None:
            tab_num = self.__num
        Size = namedtuple('Size', ['width', 'height'])
        size = Size(
            self.__tabs[tab_num]['sheet'].winfo_width(),
            self.__tabs[tab_num]['sheet'].winfo_height())
        await SongMixin.resize_sheet(self, size, tab_num)

    async def resize_sheet(self, event, tab_num):
        """Resize sheets to screen size."""
        self.__tabs[tab_num]['sheet'].delete("left")
        left = SongMixin.get_so_interface(self, tab_num)
        # make sure pages are compiled
        await self.get_file(left)
        left.page = self.__tabs[tab_num]['page']
        if not left.get_filename(FileType.png).is_file():
            # page does not exists, roll around to 1
            self.__tabs[tab_num]['page'] = 1
            left.page = 1
        left_path = await self.get_single_sheet(
            left,
            (event.width - 1)/2,
            event.height)
        self.__tabs[tab_num]['sheet'].create_image(
            0,
            0,
            image=self.image_cache[left_path]['image'],
            anchor=tk.NW,
            tags="left")
        # right page
        self.__tabs[tab_num]['sheet'].delete("right")
        right = SongMixin.get_so_interface(self, tab_num)
        right.page = self.__tabs[tab_num]['page'] + 1
        if right.get_filename(FileType.png).is_file():
            right_path = await self.get_single_sheet(
                right,
                (event.width - 1)/2,
                event.height)
            self.__tabs[tab_num]['sheet'].create_image(
                self.image_cache[left_path]['image'].width() + 1,
                0,
                image=self.image_cache[right_path]['image'],
                anchor=tk.NW,
                tags="right")

    async def on_pitch_change(self):
        """New pitch was picked by user or app."""
        asyncio.ensure_future(SongMixin.update_sheet(self))
        await self.get_file(SongMixin.get_so_interface(self), FileType.midi)

    async def play_or_stop(self):
        """Play or stop midi."""
        if self.player is not None and self.player != '...':
            await self.stop()
        else:
            await SongMixin.play(self)

    async def play(self):
        """Play midi file."""
        midi = await self.get_file(
            SongMixin.get_so_interface(self),
            FileType.midi)
        if self.port is None:
            self.messages.append(
                "Still searching for pmidi port, cancelled playback.")
            self.show_messages()
            return
        if self.__jpmidi_port is None and self.__midi_executable.get() == 'jpmidi':
            await self.select_port(pmidi=False)
        if self.player is not None:
            self.new_message("already playing")
            return
        # reserve player
        self.player = "..."
        try:
            if self.__midi_executable.get() == 'pmidi':
                self.player = await play_midi(self.port, midi)
            else:
                self.player = await play_midi(
                    self.__jpmidi_port,
                    midi,
                    pmidi=False,
                    error_cb=self.new_message)
        except Exception as err:
            ErrorDialog(
                self.root,
                data="Could not start midi playback\n{}".format(str(err)))
            raise
        self.__tabs[self.__num]['play_stop'].set("stop")
        asyncio.ensure_future(exec_on_midi_end(
            self.player,
            partial(SongMixin.on_midi_stop, self)))

    async def on_midi_stop(self):
        """Handle end of midi playback."""
        self.player = None
        self.__tabs[self.__num]['play_stop'].set("play")
