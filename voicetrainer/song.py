"""All the song stuff."""
from tkinter import ttk
import tkinter as tk
import asyncio
from pathlib import Path
from itertools import product, chain
from functools import partial
from collections import namedtuple
from pkg_resources import resource_filename, Requirement

from PIL import Image, ImageTk

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
        self.so_data_path = Path(resource_filename(
            Requirement.parse("voicetrainer"),
            'voicetrainer/songs'))
        self.so_pitch_list = [note + octave for octave, note in product(
            [',', '', '\''],
            list("cdefgab"))]
        self.so_tabs = []
        self.so_image_cache = {}

        SongMixin.create_widgets(self)

    def create_tab(self, song: str) -> None:
        """Populate song tab."""
        tab = ttk.Frame(self.so_notebook)
        tab.rowconfigure(1, weight=1)
        tab.columnconfigure(3, weight=1)
        self.so_notebook.add(tab, text=song)
        self.so_tabs.append({})
        tab_num = len(self.so_tabs) - 1
        self.so_tabs[tab_num]['tab'] = tab

        # bpm selector
        bpm_label = ttk.Label(tab, text="bpm:")
        self.so_tabs[tab_num]['bpm_label'] = bpm_label
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
        self.so_tabs[tab_num]['bpm'] = bpm
        bpm.grid(column=3, row=0, sticky=tk.W+tk.N)

        # controls
        frame = ttk.Frame(tab)
        self.so_tabs[tab_num]['control_frame'] = frame
        frame.grid(column=2, row=2, columnspan=2, sticky=tk.W+tk.N)
        # sound pitch random autonext repeat_once next play/stop

        textvar = tk.StringVar()
        # TODO: set default to natural pitch
        # textvar.set(self.so_pitch_list[listbox.curselection()[0]])
        textvar.set('c')
        self.so_tabs[tab_num]['curr_pitch'] = textvar
        curr_pitch = tk.OptionMenu(
            frame,
            textvar,
            *self.so_pitch_list,
            command=lambda _: asyncio.ensure_future(
                SongMixin.on_pitch_change(self)))
        self.so_tabs[tab_num]['pitch_menu'] = curr_pitch
        curr_pitch.grid(column=1, row=0, sticky=tk.W+tk.N)

        play_stop = tk.StringVar()
        play_stop.set("play")
        self.so_tabs[tab_num]['play_stop'] = play_stop
        play = ttk.Button(
            frame,
            textvariable=play_stop,
            command=lambda: asyncio.ensure_future(
                SongMixin.play_or_stop(self)))
        self.so_tabs[tab_num]['play'] = play
        play.grid(column=6, row=0, sticky=tk.W+tk.N)

        # sheet display
        sheet = tk.Canvas(tab, bd=0, highlightthickness=0)
        sheet.bind(
            "<Configure>",
            lambda e, num=tab_num: asyncio.ensure_future(
                SongMixin.resize_sheet(self, e, num)))
        self.so_tabs[tab_num]['sheet'] = sheet
        sheet.grid(column=2, row=1, columnspan=2, sticky=tk.N+tk.W+tk.S+tk.E)
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
        self.so_menu.add_command(
            label='Clear cache',
            command=lambda: asyncio.ensure_future(
                SongMixin.clear_cache(self)))

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
        bpm = int(self.so_tabs[tab_num]['bpm'].get())
        return Song(
            self.so_data_path,
            self.include_path,
            name=tab_name,
            pitch=pitch,
            bpm=bpm)

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
        # confirm
        confirm_remove = OkCancelDialog(
            self.root,
            "This will remove all compiled files. Are you sure?")
        if not await confirm_remove.await_data():
            return

        # remove files
        for file_ in chain(
                self.so_data_path.glob("*.midi"),
                self.so_data_path.glob("*.png"),
                self.so_data_path.glob("*.pdf")):
            file_.unlink()

        # clear image_cache and display new sheets
        self.so_image_cache = {}
        for i in range(len(self.so_tabs)):
            await SongMixin.update_sheet(self, tab_num=i)

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
        left = await SongMixin.get_single_sheet(
            self,
            SongMixin.get_so_interface(self, tab_num),
            event.width/2,
            event.height)
        self.so_tabs[tab_num]['sheet'].delete("left")
        self.so_tabs[tab_num]['sheet'].create_image(
            0,
            0,
            image=self.so_image_cache[left]['image'],
            anchor=tk.NW,
            tags="left")

    async def get_single_sheet(
            self,
            song: Song,
            max_width: int,
            max_height: int):
        """Fetch and size sheet while preserving ratio."""
        png = await self.get_file(song)
        if png not in self.so_image_cache:
            self.so_image_cache[png] = {}
            self.so_image_cache[png]['original'] = Image.open(str(png))
        original = self.so_image_cache[png]['original']
        width_ratio = float(original.width) / float(max_width)
        height_ratio = float(original.height) / float(max_height)
        ratio = max([width_ratio, height_ratio])
        size = (int(original.width / ratio), int(original.height / ratio))
        if size[0] == 0 or size[1] == 0:
            size = (1, 1)
        self.so_image_cache[png]['resized'] = \
            self.so_image_cache[png]['original'].resize(size, Image.ANTIALIAS)
        self.so_image_cache[png]['image'] = ImageTk.PhotoImage(
            self.so_image_cache[png]['resized'])
        return png

    async def on_pitch_change(self):
        """New pitch was picked by user or app."""
        asyncio.ensure_future(SongMixin.update_sheet(self))
        await SongMixin.get_file(FileType.midi)

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
