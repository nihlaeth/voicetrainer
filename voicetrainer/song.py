"""All the song stuff."""
import tkinter as tk
import asyncio
from pathlib import Path
from itertools import chain
from collections import namedtuple
from datetime import datetime

from voicetrainer.aiotk import (
    ErrorDialog,
    OkCancelDialog,
    LoadFileDialog)
from voicetrainer.common import PITCH_LIST
from voicetrainer.play import play_or_stop
from voicetrainer.compile import get_file, get_single_sheet
from voicetrainer.compile_interface import FileType, Song
from voicetrainer.gui_elements import (
    Notebook,
    Frame,
    Label,
    LabelFrame,
    Scale,
    OptionMenu,
    Button,
    Checkbutton,
    Spinbox)

class SongTab:

    """Tab containing everything for one song."""

    def __init__(
            self,
            notebook: Notebook,
            song: Song):
        self.name = song.name
        config = song.config
        self._data_path = song.data_path
        self._include_path = song.include_path
        self.tab = Frame(notebook)
        self.tab.rowconfigure(0, weight=1)
        self.tab.columnconfigure(1, weight=1)
        notebook.append({'name': self.name, 'widget': self.tab})
        self.page = 1
        self._scroll_time = datetime.now()

        # controls
        self.controls = Frame(self.tab)
        self.controls.grid(column=0, row=0, sticky=tk.W+tk.N)
        self._create_controls(self.controls, config)

        # sheet display
        self._image_cache = {}
        self.sheet = tk.Canvas(self.tab.raw, bd=0, highlightthickness=0)
        self.sheet.bind(
            "<Configure>",
            lambda e: asyncio.ensure_future(self._resize_sheet(e)))
        self.sheet.grid(column=1, row=0, sticky=tk.N+tk.W+tk.S+tk.E)

        # sheet mouse events
        self.sheet.bind(
            "<Button-1>",
            lambda e: self._change_page())
        self.sheet.bind(
            "<Button-4>",
            lambda e: self._change_page(scroll=True, increment=False))
        self.sheet.bind(
            "<Button-5>",
            lambda e: self._change_page(scroll=True))

        asyncio.ensure_future(self._update_sheet())

    def _create_controls(self, parent, config):
        row_count = 0

        self.measure_label = Label(parent, text="measure")
        self.measure_label.grid(
            column=0, row=row_count, sticky=tk.S+tk.E+tk.W)
        self.bpm_label = Label(parent, text="bpm")
        self.bpm_label.grid(
            column=1, row=row_count, sticky=tk.S+tk.E+tk.W)
        row_count += 1

        if 'measures' in config:
            max_measure = int(config['measures'])
            no_measures = False
        else:
            max_measure = 1
            no_measures = True
        self.measure = Scale(
            parent,
            from_=1,
            to=max_measure,
            tickinterval=10,
            showvalue=True,
            length=300,
            resolution=1,
            orient=tk.VERTICAL,
            label=None,
            default=1)
        self.measure.grid(column=0, row=row_count, sticky=tk.W+tk.N+tk.E)
        if no_measures:
            self.measure.disable()
        self.bpm = Scale(
            parent,
            from_=40,
            to=240,
            tickinterval=20,
            showvalue=True,
            length=300,
            resolution=1,
            orient=tk.VERTICAL,
            label=None,
            default=140)
        self.bpm.grid(column=1, row=row_count, sticky=tk.W+tk.N+tk.E)
        if 'tempo' in config:
            self.bpm.set(config['tempo'])
        else:
            self.bpm.disable()
        row_count += 1

        self.key_label = Label(parent, text="key:")
        self.key_label.grid(column=0, row=row_count, sticky=tk.N+tk.E)
        self.key = OptionMenu(
            parent,
            option_list=PITCH_LIST,
            default='c',
            command=lambda _: asyncio.ensure_future(
                self._on_pitch_change()))
        self.key.grid(column=1, row=row_count, sticky=tk.W+tk.N)
        if 'key' in config:
            self.key.set(config['key'])
        else:
            self.key.disable()
        row_count += 1

        self.velocity_label = Label(parent, text="rel. velocity:")
        self.velocity_label.grid(column=0, row=row_count, sticky=tk.N+tk.E)
        self.velocity = Spinbox(
            parent,
            width=3,
            from_=-50,
            to=50,
            increment=1,
            default=0)
        self.velocity.grid(column=1, row=row_count, sticky=tk.W+tk.N)
        row_count += 1

        self.iframe = LabelFrame(parent, text="Instruments")
        self.iframe.grid(
            column=0, row=row_count, columnspan=2, sticky=tk.NSEW)
        self.instruments = {}
        for i, instrument in enumerate(config['instruments']):
            checkbox = Checkbutton(
                self.iframe, text=instrument, default=True)
            checkbox.grid(column=0, row=i, sticky=tk.N+tk.W)
            self.instruments[instrument] = checkbox
        row_count += 1

        self.b_recompile = Button(
            parent,
            text='Recompile',
            command=lambda: asyncio.ensure_future(self.clear_cache()))
        self.b_recompile.grid(
            column=0, row=row_count, columnspan=2, sticky=tk.NSEW)
        row_count += 1

        self.b_reset = Button(
            parent,
            text='Reset to song default',
            command=self._reset_song)
        self.b_reset.grid(
            column=0, row=row_count, columnspan=2, sticky=tk.NSEW)
        row_count += 1

        if 'pages' in config:
            num_pages = int(config['pages'])
            no_pages = False
        else:
            num_pages = 1
            no_pages = True

        self.b_first_page = Button(
            parent,
            text='First page',
            command=lambda: self._change_page(page=1))
        self.b_first_page.grid(
            column=0, row=row_count, columnspan=2, sticky=tk.NSEW)
        row_count += 1

        self.b_next_page = Button(
            parent,
            text='Next page',
            command=self._change_page)
        self.b_next_page.grid(
            column=0, row=row_count, columnspan=2, sticky=tk.NSEW)
        row_count += 1

        self.b_prev_page = Button(
            parent,
            text='Previous page',
            command=lambda: self._change_page(increment=False))
        self.b_prev_page.grid(
            column=0, row=row_count, columnspan=2, sticky=tk.NSEW)
        row_count += 1

        self.b_last_page = Button(
            parent,
            text='Last page',
            command=lambda last=num_pages: self._change_page(page=last))
        self.b_last_page.grid(
            column=0, row=row_count, columnspan=2, sticky=tk.NSEW)
        row_count += 1

        if no_pages:
            self.b_first_page.disable()
            self.b_next_page.disable()
            self.b_prev_page.disable()
            self.b_last_page.disable()

        self.b_play = Button(
            parent,
            text='Play',
            command=lambda: asyncio.ensure_future(self.play()))
        self.b_play.grid(
            column=0, row=row_count, columnspan=2, sticky=tk.NSEW)
        row_count += 1

    def _reset_song(self):
        """Set song pitch and bpm to song default."""
        config = self._get_interface().config
        if 'key' in config:
            self.key.set(config['key'])
        if 'tempo' in config:
            self.bpm.set(config['tempo'])
        asyncio.ensure_future(self._update_sheet())

    def save_state(self):
        """Return exercise state."""
        data = {}
        data['key'] = self.key.get()
        data['bpm'] = self.bpm.get()
        data['velocity'] = self.velocity.get()
        data['instruments'] = {}
        for instrument in self.instruments:
            data['instruments'][instrument] = \
                self.instruments[instrument].get()
        return data

    def restore_state(self, data):
        """Restore saved settings."""
        if 'key' in data:
            self.key.set(data['key'])
        if 'bpm' in data:
            self.bpm.set(data['bpm'])
        if 'velocity' in data:
            self.velocity.set(data['velocity'])
        if 'instruments' not in data:
            return
        for instrument in data['instruments']:
            if instrument not in self.instruments:
                continue
            self.instruments[instrument].set(
                data['instruments'][instrument])

    def _get_interface(self):
        """Return song interface."""
        instruments = {
            instrument: self.instruments[instrument].get() \
            for instrument in self.instruments}
        return Song(
            self._data_path,
            self._include_path,
            name=self.name,
            pitch=self.key.get(),
            bpm=self.bpm.get(),
            start_measure=self.measure.get(),
            velocity=self.velocity.get(),
            instruments=instruments)

    async def clear_cache(self):
        """Remove all compiled files."""
        # remove files
        for file_ in chain(
                self._data_path.glob("{}-*.midi".format(self.name)),
                self._data_path.glob("{}-*.png".format(self.name)),
                self._data_path.glob("{}-*.pdf".format(self.name))):
            file_.unlink()
        self._image_cache = {}
        await self._update_sheet()

    def _change_page(self, increment=True, page=None, scroll=False):
        """Change page."""
        if scroll:
            delta_t = datetime.now() - self._scroll_time
            self._scroll_time = datetime.now()
            if delta_t.total_seconds() < 0.5:
                return
        if page is not None:
            self.page = int(page)
        elif increment:
            self.page += 1
        else:
            if self.page > 1:
                self.page -= 1
        asyncio.ensure_future(self._update_sheet())

    async def _update_sheet(self):
        """Display relevant sheet."""
        # pylint: disable=invalid-name
        # type declaration
        Size = namedtuple('Size', ['width', 'height'])
        size = Size(
            self.sheet.winfo_width(),
            self.sheet.winfo_height())
        await self._resize_sheet(size)

    async def _resize_sheet(self, event):
        """Resize sheets to screen size."""
        self.sheet.delete("left")
        self.sheet.delete("right")
        left = self._get_interface()
        # make sure pages are compiled
        await get_file(left)
        left.page = self.page
        if not left.get_filename(FileType.png).is_file():
            # page does not exists, roll around to 1
            self.page = 1
            left.page = 1
        left_path = await get_single_sheet(
            self._image_cache,
            left,
            (event.width - 1)/2,
            event.height)
        self.sheet.create_image(
            0,
            0,
            image=self._image_cache[left_path]['image'],
            anchor=tk.NW,
            tags="left")
        # right page
        right = self._get_interface()
        right.page = self.page + 1
        if right.get_filename(FileType.png).is_file():
            right_path = await get_single_sheet(
                self._image_cache,
                right,
                (event.width - 1)/2,
                event.height)
            self.sheet.create_image(
                self._image_cache[left_path]['image'].width() + 1,
                0,
                image=self._image_cache[right_path]['image'],
                anchor=tk.NW,
                tags="right")

    async def _on_pitch_change(self):
        """New pitch was picked by user or app."""
        asyncio.ensure_future(self._update_sheet())
        await get_file(self._get_interface(), FileType.midi)

    async def play(self):
        """Play midi file."""
        midi = await get_file(self._get_interface(), FileType.midi)
        # if self.__midi_executable.get() == 'pmidi':
        playing = await play_or_stop(midi, self._on_midi_stop)
        # else:
        #     # FIXME: fetch midi_executable and await_jack somehow
        #     # have them trickle down from MainWindow with singular
        #     # play/stop button
        #     playing = await play_or_stop(
        #         midi,
        #         on_midi_end=self._on_midi_stop,
        #         pmidi=False)
        if playing:
            self.b_play.set_text("Stop")
        else:
            self.b_play.set_text("Play")

    async def _on_midi_stop(self):
        """Handle end of midi playback."""
        self.b_play.set_text("Play")

    def export(self):
        """Export compiled data."""
        return self._get_interface()

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
        self.__tabs = {}
        self.__scroll_time = datetime.now()
        self.__jpmidi_port = 'system:'

        SongMixin.create_widgets(self)

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

        self.__frame = Frame(self.notebook)
        self.notebook.append({'name': 'Songs', 'widget': self.__frame})
        self.__frame.rowconfigure(0, weight=1)
        self.__frame.columnconfigure(0, weight=1)

        self.__notebook = Notebook(self.__frame)
        self.__notebook.grid(
            column=0, row=0, sticky=tk.N+tk.S+tk.E+tk.W)
        self.__notebook.rowconfigure(0, weight=1)
        self.__notebook.columnconfigure(0, weight=1)
        for song in self.__data_path.glob('*.ly'):
            self.__tabs[str(song)] = SongTab(
                self.__notebook,
                Song(
                    data_path=self.__data_path,
                    include_path=self.include_path,
                    name=song.stem))

    def save_state(self):
        """Return exercise state."""
        # FIXME: imagine a user adding a song named await_jeck
        data = {}
        data['midi_executable'] = self.__midi_executable.get()
        data['await_jack'] = self.__await_jack.get()
        data['jpmidi_port'] = self.__jpmidi_port
        for key in self.__tabs:
            data[key] = self.__tabs[key].save_state()
        return data

    def restore_state(self, data):
        """Restore saved settings."""
        if 'midi_executable' in data:
            self.__midi_executable.set(data['midi_executable'])
        if 'await_jack' in data:
            self.__await_jack.set(data['await_jack'])
        if 'jpmidi_port' in data:
            self.__jpmidi_port = data['jpmidi_port']
        for key in self.__tabs:
            if key in data:
                self.__tabs[key].restore_state(data[key])

    def export(self):
        """Export compiled data."""
        return self.__tabs[self.__notebook.get()[1]].export()

    async def add_song(self):
        """Add new song."""
        # FIXME: race condition
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
            self.__tabs[so_name] = Song(
                data_path=self.__data_path,
                include_path=self.include_path,
                name=so_name)
            self.__notebook.sort()

    async def remove_song(self):
        """Remove song."""
        tab_index, tab_name = self.__notebook.get()
        confirm = OkCancelDialog(
            self.root,
            data="Are you sure you want to delete {}? This cannot be undone.".format(
                tab_name))
        if not await confirm.await_data():
            return
        self.stopping = True
        await self.stop()
        del self.__notebook[tab_index]
        del self.__tabs[tab_name]
        file_name = Path(self.__data_path).joinpath(
            "{}.ly".format(tab_name))
        file_name.unlink()

    async def clear_cache(self):
        """Remove all compiled files."""
        for key in self.__tabs:
            self.__tabs[key].clear_cache()
