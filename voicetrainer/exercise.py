"""All the exercise stuff."""
import tkinter as tk
import asyncio
from pathlib import Path
from itertools import chain
from collections import namedtuple
from random import choice

from voicetrainer.aiotk import (
    ErrorDialog,
    OkCancelDialog,
    LoadFileDialog)
from voicetrainer.play import play_or_stop, stop, is_playing
from voicetrainer.common import PITCH_LIST, SOUND_LIST
from voicetrainer.compile import get_file, get_single_sheet
from voicetrainer.compile_interface import FileType, Exercise
from voicetrainer.gui_elements import (
    Notebook,
    Frame,
    Label,
    Listbox,
    Scale,
    OptionMenu,
    Button,
    Checkbutton,
    Spinbox)

class ExerciseTab:

    """Tab containing everything for one exersise."""

    def __init__(
            self,
            notebook: Notebook,
            exercise: Exercise):
        # some control variables
        self.stopping = False
        self.play_next = False
        self.repeat_once = False

        self.name = exercise.name
        self.config = config = exercise.config
        self._data_path = exercise.data_path
        self._include_path = exercise.include_path
        self.tab = Frame(notebook)
        self.tab.rowconfigure(1, weight=1)
        self.tab.columnconfigure(3, weight=1)
        notebook.append({'name': self.name, 'widget': self.tab})

        # bpm selector
        self.bpm_label = Label(self.tab, text="bpm:")
        self.bpm_label.grid(column=2, row=0, sticky=tk.N+tk.W)
        self.bpm = Scale(
            self.tab,
            from_=80,
            to=160,
            tickinterval=10,
            showvalue=0,
            length=300,
            resolution=10,
            default=140,
            orient=tk.HORIZONTAL)
        self.bpm.grid(column=3, row=0, sticky=tk.W+tk.N)
        if 'tempo' not in config:
            self.bpm.disable()

        # pitch selector
        self.pitch_range = Listbox(self.tab, width=3, values=PITCH_LIST)
        self.pitch_range.grid(row=1, column=1, sticky=tk.N+tk.S+tk.W)
        self.pitch_range.set({pitch: True for pitch in PITCH_LIST[7:14]})

        # controls
        self.control_frame = Frame(self.tab)
        self.control_frame.grid(
            column=2, row=2, columnspan=2, sticky=tk.W+tk.N)
        self._create_controls(self.control_frame, config)

        # sheet display
        self._image_cache = {}
        self.sheet = tk.Canvas(self.tab.raw, bd=0, highlightthickness=0)
        self.sheet.bind(
            "<Configure>",
            lambda e: asyncio.ensure_future(
                self._resize_sheet(e)))
        self.sheet.grid(column=2, row=1, columnspan=2, sticky=tk.NSEW)

        self.sheet.bind(
            "<Button-1>",
            lambda e: self._set_repeat_once())
        asyncio.ensure_future(self._update_sheet())

    def _create_controls(self, parent, config):
        self.velocity_label = Label(parent, text="relative velocity:")
        self.velocity_label.grid(column=0, row=0, sticky=tk.N+tk.E)
        self.velocity = Spinbox(
            parent,
            width=3,
            from_=-50,
            to=50,
            default=0,
            increment=1)
        self.velocity.grid(column=1, row=0, sticky=tk.W+tk.N)

        self.sound = OptionMenu(
            parent,
            default='Mi',
            option_list=SOUND_LIST,
            command=lambda _: asyncio.ensure_future(
                self._update_sheet()))
        self.sound.grid(column=2, row=0, sticky=tk.W+tk.N)
        if 'sound' not in config:
            self.sound.disable()

        self.key = OptionMenu(
            parent,
            option_list=PITCH_LIST,
            default='c',
            command=lambda _: asyncio.ensure_future(
                self._on_pitch_change()))
        self.key.grid(column=3, row=0, sticky=tk.W+tk.N)
        if 'key' in config:
            self.key.set(config['key'])
        else:
            self.key.disable()

        self.random = Checkbutton(parent, text="random")
        self.random.grid(column=4, row=0, sticky=tk.W+tk.N)
        self.autonext = Checkbutton(parent, text="autonext")
        self.autonext.grid(column=5, row=0, sticky=tk.W+tk.N)

        self.b_repeat = Button(
            parent,
            text="Repeat once",
            command=self._set_repeat_once)
        self.b_repeat.grid(column=6, row=0, sticky=tk.W+tk.N)

        self.b_next_ = Button(
            parent,
            text="Next",
            command=lambda: asyncio.ensure_future(self._next()))
        self.b_next_.grid(column=7, row=0, sticky=tk.W+tk.N)

        self.b_play = Button(
            parent,
            text="Play",
            command=lambda: asyncio.ensure_future(self.play()))
        self.b_play.grid(column=8, row=0, sticky=tk.W+tk.N)

    def save_state(self):
        """Return exercise state."""
        data = {}
        data['pitch_range'] = self.pitch_range.get()
        data['bpm'] = self.bpm.get()
        data['velocity'] = self.velocity.get()
        data['sound'] = self.sound.get()
        data['autonext'] = self.autonext.get()
        data['random'] = self.random.get()
        return data

    def restore_state(self, data):
        """Restore saved settings."""
        if 'pitch_range' in data:
            self.pitch_range.set(data['pitch_range'])
        if 'bpm' in data:
            self.bpm.set(data['bpm'])
        if 'velocity' in data:
            self.velocity.set(data['velocity'])
        if 'sound' in data:
            self.sound.set(data['sound'])
        if 'autonext' in data:
            self.autonext.set(data['autonext'])
        if 'random' in data:
            self.random.set(data['random'])

    def _get_interface(self):
        """Return exercise interface."""
        return Exercise(
            self._data_path,
            self._include_path,
            name=self.name,
            pitch=self.key.get(),
            bpm=self.bpm.get(),
            sound=self.sound.get(),
            velocity=self.velocity.get())

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
        left = self._get_interface()
        # make sure pages are compiled
        await get_file(left)
        left_path = await get_single_sheet(
            self._image_cache,
            left,
            event.width,
            event.height)
        self.sheet.create_image(
            0,
            0,
            image=self._image_cache[left_path]['image'],
            anchor=tk.NW,
            tags="left")

    async def _on_pitch_change(self):
        """New pitch was picked by user or app."""
        asyncio.ensure_future(self._update_sheet())
        if is_playing():
            self.play_next = True
            await stop()
        else:
            await self.play()

    def _set_repeat_once(self, _=None):
        """Repeat this midi once, then continue."""
        self.repeat_once = True

    async def _next_sound(self):
        if 'sound' in self.config:
            current_sound = self.sound.get()
            sound_position = SOUND_LIST.index(current_sound)
            if sound_position < len(SOUND_LIST) - 1:
                self.sound.set(SOUND_LIST[sound_position + 1])
            else:
                self.sound.set(SOUND_LIST[0])
            asyncio.ensure_future(self._update_sheet())

    async def _next(self):
        """Pick next exercise configuration."""
        if 'key' not in self.config:
            await self._next_sound()
            return
        current_pitch = new_pitch = self.key.get()
        pitch_position = PITCH_LIST.index(current_pitch)
        pitch_range = self.pitch_range.get()
        pitch_selection = [
            pitch for pitch in pitch_range if pitch_range[pitch]]
        if not pitch_selection:
            return
        if self.random.get():
            while new_pitch == current_pitch:
                new_pitch = choice(pitch_selection)
        else:
            while pitch_selection:
                pitch_position += 1
                if pitch_position >= len(PITCH_LIST):
                    pitch_position = 0
                    await self._next_sound()
                if PITCH_LIST[pitch_position] in pitch_selection:
                    new_pitch = PITCH_LIST[pitch_position]
                    break
        self.key.set(new_pitch)
        await self._on_pitch_change()

    async def play(self):
        """Play midi file."""
        midi = await get_file(self._get_interface(), FileType.midi)
        playing = await play_or_stop(midi, self._on_midi_stop)
        if playing:
            self.b_play.set_text("Stop")
        else:
            self.b_play.set_text("Play")

    async def _on_midi_stop(self):
        """Handle end of midi playback."""
        if self.stopping:
            self.play_next = False
            self.stopping = False
            self.b_play.set_text("Play")
            return
        if self.play_next or self.autonext.get() == 1:
            self.play_next = False
            if not self.repeat_once:
                await self._next()
            else:
                self.repeat_once = False
                await self.play()
            return
        self.b_play.set_text("Play")

    def export(self):
        """Export compiled data."""
        return self._get_interface()

class ExerciseMixin:

    """
    All the exercise stuff.

    This is a mixin class. If you need a method from here, call it
    specifically. To avoid naming collisions, start all properties
    with __. All properties that do not start with ex_, are assumed to be
    provided the class that this is mixed in.
    """

    def __init__(self):
        self.__data_path = self.data_path.joinpath('exercises')
        self.__data_path.mkdir(exist_ok=True)
        self.__tabs = {}

        ExerciseMixin.create_widgets(self)

    def create_widgets(self):
        """Put some stuff up to look at."""
        self.__menu = tk.Menu(self.menubar)
        self.menubar.add_cascade(label='Exercises', menu=self.__menu)
        self.__menu.add_command(
            label='Add',
            command=lambda: asyncio.ensure_future(
                ExerciseMixin.add_exercise(self)))
        self.__menu.add_command(
            label='Delete',
            command=lambda: asyncio.ensure_future(
                ExerciseMixin.remove_exercise(self)))

        self.__frame = Frame(self.notebook)
        self.notebook.append(
            {'name': 'Exercises', 'widget': self.__frame})
        self.__frame.rowconfigure(0, weight=1)
        self.__frame.columnconfigure(0, weight=1)

        self.__notebook = Notebook(self.__frame)
        self.__notebook.grid(
            column=0, row=0, sticky=tk.N+tk.S+tk.E+tk.W)
        self.__notebook.rowconfigure(0, weight=1)
        self.__notebook.columnconfigure(0, weight=1)
        for exercise in self.__data_path.glob('*.ly'):
            self.__tabs[str(exercise)] = ExerciseTab(
                self.__notebook,
                Exercise(
                    data_path=self.__data_path,
                    include_path=self.include_path,
                    name=exercise.stem))

    def save_state(self):
        """Return exercise state."""
        data = {}
        for key in self.__tabs:
            data[key] = self.__tabs[key].save_state()
        return data

    def restore_state(self, data):
        """Restore saved settings."""
        for key in self.__tabs:
            if key in data:
                self.__tabs[key].restore_state(data[key])

    def export(self):
        """Export compiled data."""
        return self.__tabs[self.__notebook.get()[1]].export()

    async def add_exercise(self):
        """Add new exercise."""
        dialog = LoadFileDialog(
            self.root,
            dir_or_file=Path('~'),
            pattern="*.ly")
        file_name = await dialog.await_data()
        if file_name is not None:
            path = Path(file_name)
            ex_name = path.stem
            if not path.is_file():
                ErrorDialog(
                    self.root,
                    data="{} is not a file".format(path))
                return
            content = path.read_text()
            new_file = self.__data_path.joinpath("{}.ly".format(ex_name))
            if new_file.is_file():
                ErrorDialog(
                    self.root,
                    data="An exercise with name {} already exists.".format(
                        ex_name))
                return
            new_file.touch()
            new_file.write_text(content)
            self.__tabs[ex_name] = Exercise(
                data_path=self.__data_path,
                include_path=self.include_path,
                name=ex_name)
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
