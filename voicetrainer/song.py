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
    with so_. All properties that do not start with so_, are assumed to be
    provided the class that this is mixed in.
    """

    def __init__(self):
        self.so_data_path = self.data_path.joinpath('songs')
        self.so_data_path.mkdir(exist_ok=True)
        self.so_pitch_list = [note + octave for octave, note in product(
            [',', '', '\''],
            list("cdefgab"))]
        self.so_tabs = []
        self.so_scroll_time = datetime.now()

        SongMixin.create_widgets(self)

    def create_tab(self, song: str) -> None:
        """Populate song tab."""
        tab = ttk.Frame(self.so_notebook)
        tab.rowconfigure(0, weight=1)
        tab.columnconfigure(1, weight=1)
        self.so_notebook.add(tab, text=song)
        self.so_tabs.append({})
        tab_num = len(self.so_tabs) - 1
        self.so_tabs[tab_num]['tab'] = tab
        self.so_tabs[tab_num]['page'] = 1

        config = Song(
            self.so_data_path, self.include_path, song).get_config()

        # controls
        frame = ttk.Frame(tab)
        self.so_tabs[tab_num]['control_frame'] = frame
        frame.grid(column=0, row=0, sticky=tk.W+tk.N)

        # bpm selector
        bpm_label = ttk.Label(frame, text="bpm:")
        self.so_tabs[tab_num]['bpm_label'] = bpm_label
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
        self.so_tabs[tab_num]['bpm'] = bpm
        bpm.grid(column=1, row=0, sticky=tk.W+tk.N)

        key_label = ttk.Label(frame, text="key:")
        self.so_tabs[tab_num]['key_label'] = key_label
        key_label.grid(column=0, row=1, sticky=tk.N+tk.E)
        textvar = tk.StringVar()
        if 'key' in config:
            textvar.set(config['key'])
        else:
            textvar.set('c')
        self.so_tabs[tab_num]['curr_pitch'] = textvar
        curr_pitch = tk.OptionMenu(
            frame,
            textvar,
            *self.so_pitch_list,
            command=lambda _: asyncio.ensure_future(
                SongMixin.on_pitch_change(self)))
        self.so_tabs[tab_num]['pitch_menu'] = curr_pitch
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
        self.so_tabs[tab_num]['measure_label'] = measure_label
        measure_label.grid(column=0, row=2, sticky=tk.N+tk.E)
        self.so_tabs[tab_num]['curr_measure'] = measure
        measure.grid(column=1, row=2, sticky=tk.W+tk.N)

        velocity = tk.Spinbox(
            frame,
            width=3,
            from_=-50,
            to=50,
            increment=1)
        velocity_label = ttk.Label(frame, text="relative velocity:")
        self.so_tabs[tab_num]['velocity_label'] = velocity_label
        velocity_label.grid(column=0, row=3, sticky=tk.N+tk.E)
        self.so_tabs[tab_num]['velocity'] = velocity
        velocity.grid(column=1, row=3, sticky=tk.W+tk.N)

        first_page = ttk.Button(
            frame,
            text='First page',
            command=lambda: SongMixin.change_page(self, page=1))
        self.so_tabs[tab_num]['first_page'] = first_page
        first_page.grid(column=0, row=4, columnspan=2, sticky=tk.W+tk.N+tk.E)

        next_page = ttk.Button(
            frame,
            text='Next page',
            command=lambda: SongMixin.change_page(self))
        self.so_tabs[tab_num]['next_page'] = next_page
        next_page.grid(column=0, row=5, columnspan=2, sticky=tk.W+tk.N+tk.E)

        prev_page = ttk.Button(
            frame,
            text='Previous page',
            command=lambda: SongMixin.change_page(self, increment=False))
        self.so_tabs[tab_num]['prev_page'] = prev_page
        prev_page.grid(column=0, row=6, columnspan=2, sticky=tk.W+tk.N+tk.E)

        if 'pages' in config:
            num_pages = int(config['pages'])
        else:
            num_pages = 1
        last_page = ttk.Button(
            frame,
            text='Last page',
            command=lambda last=num_pages: SongMixin.change_page(
                self, page=last))
        self.so_tabs[tab_num]['last_page'] = last_page
        last_page.grid(column=0, row=7, columnspan=2, sticky=tk.W+tk.N+tk.E)

        play_stop = tk.StringVar()
        play_stop.set("play")
        self.so_tabs[tab_num]['play_stop'] = play_stop
        play = ttk.Button(
            frame,
            textvariable=play_stop,
            command=lambda: asyncio.ensure_future(
                SongMixin.play_or_stop(self)))
        self.so_tabs[tab_num]['play'] = play
        play.grid(column=0, row=8, columnspan=2, sticky=tk.W+tk.N+tk.E)

        # sheet display
        sheet = tk.Canvas(tab, bd=0, highlightthickness=0)
        sheet.bind(
            "<Configure>",
            lambda e, num=tab_num: asyncio.ensure_future(
                SongMixin.resize_sheet(self, e, num)))
        self.so_tabs[tab_num]['sheet'] = sheet
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
        self.so_menu = tk.Menu(self.menubar)
        self.menubar.add_cascade(label='Songs', menu=self.so_menu)
        self.so_menu.add_command(
            label='Add',
            command=lambda: asyncio.ensure_future(
                SongMixin.add_song(self)))
        self.so_menu.add_command(
            label='Delete',
            command=lambda: asyncio.ensure_future(
                SongMixin.remove_song(self)))
        self.so_menu.add_command(
            label='Export midi',
            command=lambda: asyncio.ensure_future(
                SongMixin.export(self, FileType.midi)))
        self.so_menu.add_command(
            label='Export png',
            command=lambda: asyncio.ensure_future(
                SongMixin.export(self, FileType.png)))
        self.so_menu.add_command(
            label='Export pdf',
            command=lambda: asyncio.ensure_future(
                SongMixin.export(self, FileType.pdf)))
        self.so_menu.add_command(
            label='Export lilypond',
            command=lambda: asyncio.ensure_future(
                SongMixin.export(self, FileType.lily)))

        self.so_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.so_frame, text='Songs')
        self.so_frame.rowconfigure(0, weight=1)
        self.so_frame.columnconfigure(0, weight=1)

        self.so_notebook = ttk.Notebook(self.so_frame)
        for song in self.so_data_path.glob('*.ly'):
            SongMixin.create_tab(self, song.stem)
        self.so_notebook.grid(
            column=0, row=0, sticky=tk.N+tk.S+tk.E+tk.W)
        self.so_notebook.rowconfigure(0, weight=1)
        self.so_notebook.columnconfigure(0, weight=1)

    @property
    def so_num(self):
        """Return index of current tab."""
        tab_id = self.so_notebook.select()
        return self.so_notebook.index(tab_id)

    def save_state(self):
        """Return exercise state."""
        data = {}
        for i in range(len(self.so_tabs)):
            tab_name = self.so_notebook.tab(i)['text']
            data[tab_name] = {}
            data[tab_name]['curr_pitch'] = self.so_tabs[i]['curr_pitch'].get()
            data[tab_name]['bpm'] = self.so_tabs[i]['bpm'].get()
        return data

    def restore_state(self, data):
        """Restore saved settings."""
        for i in range(len(self.so_tabs)):
            tab_name = self.so_notebook.tab(i)['text']
            if tab_name not in data:
                continue
            self.so_tabs[i]['curr_pitch'].set(
                data[tab_name]['curr_pitch'])
            self.so_tabs[i]['bpm'].set(data[tab_name]['bpm'])

    def get_so_interface(self, tab_num=None):
        """Return exercise interface."""
        if tab_num is None:
            tab_num = self.so_num
        tab_name = self.so_notebook.tab(tab_num)['text']
        pitch = self.so_tabs[tab_num]['curr_pitch'].get()
        measure = int(self.so_tabs[tab_num]['curr_measure'].get())
        bpm = int(self.so_tabs[tab_num]['bpm'].get())
        velocity = int(self.so_tabs[tab_num]['velocity'].get())
        return Song(
            self.so_data_path,
            self.include_path,
            name=tab_name,
            pitch=pitch,
            bpm=bpm,
            start_measure=measure,
            velocity=velocity)

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
            new_file = self.so_data_path.joinpath("{}.ly".format(so_name))
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
        tab_num = self.so_num
        tab_name = self.so_notebook.tab(tab_num)['text']
        confirm = OkCancelDialog(
            self.root,
            data="Are you sure you want to delete {}? This cannot be undone.".format(
                tab_name))
        if not await confirm.await_data():
            return
        self.stopping = True
        await self.stop()
        tab = self.so_tabs[tab_num]['tab']
        self.so_notebook.forget(tab)
        tab.destroy()
        del self.so_tabs[tab_num]
        file_name = Path(self.so_data_path).joinpath(
            "{}.ly".format(tab_name))
        # pylint: disable=no-member
        # does too!
        file_name.unlink()

    async def clear_cache(self):
        """Remove all compiled files."""
        # remove files
        for file_ in chain(
                self.so_data_path.glob("*.midi"),
                self.so_data_path.glob("*.png"),
                self.so_data_path.glob("*.pdf")):
            file_.unlink()

        # display fresh sheets
        for i in range(len(self.so_tabs)):
            await SongMixin.update_sheet(self, tab_num=i)

    def change_page(self, increment=True, page=None, scroll=False):
        """Change page."""
        if scroll:
            delta_t = datetime.now() - self.so_scroll_time
            self.so_scroll_time = datetime.now()
            if delta_t.total_seconds() < 0.5:
                return
        if page is not None:
            self.so_tabs[self.so_num]['page'] = int(page)
        elif increment:
            self.so_tabs[self.so_num]['page'] += 1
        else:
            if self.so_tabs[self.so_num]['page'] > 1:
                self.so_tabs[self.so_num]['page'] -= 1
        asyncio.ensure_future(SongMixin.update_sheet(self))

    async def update_sheet(self, tab_num=None):
        """Display relevant sheet."""
        if tab_num is None:
            tab_num = self.so_num
        Size = namedtuple('Size', ['width', 'height'])
        size = Size(
            self.so_tabs[tab_num]['sheet'].winfo_width(),
            self.so_tabs[tab_num]['sheet'].winfo_height())
        await SongMixin.resize_sheet(self, size, tab_num)

    async def resize_sheet(self, event, tab_num):
        """Resize sheets to screen size."""
        self.so_tabs[tab_num]['sheet'].delete("left")
        left = SongMixin.get_so_interface(self, tab_num)
        # make sure pages are compiled
        await self.get_file(left)
        left.page = self.so_tabs[tab_num]['page']
        if not left.get_filename(FileType.png).is_file():
            # page does not exists, roll around to 1
            self.so_tabs[tab_num]['page'] = 1
            left.page = 1
        left_path = await self.get_single_sheet(
            left,
            (event.width - 1)/2,
            event.height)
        self.so_tabs[tab_num]['sheet'].create_image(
            0,
            0,
            image=self.image_cache[left_path]['image'],
            anchor=tk.NW,
            tags="left")
        # right page
        self.so_tabs[tab_num]['sheet'].delete("right")
        right = SongMixin.get_so_interface(self, tab_num)
        right.page = self.so_tabs[tab_num]['page'] + 1
        if right.get_filename(FileType.png).is_file():
            right_path = await self.get_single_sheet(
                right,
                (event.width - 1)/2,
                event.height)
            self.so_tabs[tab_num]['sheet'].create_image(
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
        if self.player is not None:
            # user stopped playback
            self.stopping = True
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
        try:
            self.player = await play_midi(self.port, midi)
        except Exception as err:
            ErrorDialog(
                self.root,
                data="Could not start midi playback\n{}".format(str(err)))
            raise
        self.so_tabs[self.so_num]['play_stop'].set("stop")
        asyncio.ensure_future(exec_on_midi_end(
            self.player,
            partial(SongMixin.on_midi_stop, self)))

    async def on_midi_stop(self):
        """Handle end of midi playback."""
        self.player = None
        self.so_tabs[self.so_num]['play_stop'].set("play")
