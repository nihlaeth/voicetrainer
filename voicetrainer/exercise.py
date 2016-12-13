"""All the exercise stuff."""
import tkinter as tk
import asyncio
from pathlib import Path
from itertools import chain
from collections import namedtuple
from random import choice

from voicetrainer.aiotk import (
    ErrorDialog,
    InfoDialog,
    OkCancelDialog,
    SaveFileDialog,
    LoadFileDialog)
from voicetrainer.play import play_or_stop, play
from voicetrainer.common import PITCH_LIST
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
        self.name = exercise.name
        config = exercise.config
        self._data_path = exercise.data_path
        self._include_path = exercise.include_path
        self.tab = Frame(notebook)
        self.tab.rowconfigure(0, weight=1)
        self.tab.columnconfigure(1, weight=1)
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
        self.pitch_range.set(PITCH_LIST[7:14])

        # controls
        self.control_frame = Frame(self.tab)
        self.control_frame.grid(
            column=2, row=2, columnspan=2, sticky=tk.W+tk.N)
        self._create_controls(self.control_frame, config)

        # sheet display
        sheet = tk.Canvas(self.tab, bd=0, highlightthickness=0)
        sheet.bind(
            "<Configure>",
            lambda e: asyncio.ensure_future(
                self._resize_sheet(e)))
        sheet.grid(column=2, row=1, columnspan=2, sticky=tk.NSEW)

        sheet.bind(
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
            option_list=["Mi", "Na", "Noe", "Nu", "No"],
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
            name=self.name.get(),
            pitch=self.key.get(),
            bpm=self.bpm.get(),
            sound=self.sound.get(),
            velocity=self.velocity.get())

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
        self.__menu.add_command(
            label='Export midi',
            command=lambda: asyncio.ensure_future(
                ExerciseMixin.export(self, FileType.midi)))
        self.__menu.add_command(
            label='Export png',
            command=lambda: asyncio.ensure_future(
                ExerciseMixin.export(self, FileType.png)))
        self.__menu.add_command(
            label='Export pdf',
            command=lambda: asyncio.ensure_future(
                ExerciseMixin.export(self, FileType.pdf)))
        self.__menu.add_command(
            label='Export lilypond',
            command=lambda: asyncio.ensure_future(
                ExerciseMixin.export(self, FileType.lily)))

        self.__frame = Frame(self.notebook)
        self.notebook.append(
            {'name': 'Exercises', 'widget': self.__frand})
        self.__frame.rowconfigure(0, weight=1)
        self.__frame.columnconfigure(0, weight=1)

        self.__notebook = Notebook(self.__frame)
        self.__notebook.grid(
            column=0, row=0, sticky=tk.N+tk.S+tk.E+tk.W)
        self.__notebook.rowconfigure(0, weight=1)
        self.__notebook.columnconfigure(0, weight=1)
        for exercise in self.__data_path.glob('*.ly'):
            self.__tabs[exercise] = ExerciseTab(
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

    async def export(self, file_type: FileType):
        """Export compiled data."""
        # get interface
        exercise = ExerciseMixin.get_ex_interface(self)

        # get save_path
        file_name = exercise.get_filename(file_type)
        save_dialog = SaveFileDialog(
            self.root,
            dir_or_file=Path('~'),
            default=file_name.name)
        save_path = await save_dialog.await_data()
        if save_path is None:
            return

        # compile and save
        if file_type == FileType.lily:
            # we don't compile lily
            save_path.write_text(exercise.get_final_lily_code(file_type))
            InfoDialog(self.root, data="Export complete")
            return
        await self.get_file(exercise, file_type)

        save_path.write_bytes(file_name.read_bytes())
        InfoDialog(self.root, data="Export complete")

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
            ExerciseMixin.create_tab(self, ex_name)

    async def remove_exercise(self):
        """Remove exercise."""
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
        file_name.unlink()

    async def clear_cache(self):
        """Remove all compiled files."""
        # remove files
        for file_ in chain(
                self.__data_path.glob("*.midi"),
                self.__data_path.glob("*.png"),
                self.__data_path.glob("*.pdf")):
            file_.unlink()

        # clear image_cache and display new sheets
        for i in range(len(self.__tabs)):
            await ExerciseMixin.update_sheet(self, tab_num=i)

    # FIXME: move this to MainWindow
    async def update_sheet(self, tab_num=None):
        """Display relevant sheet."""
        if tab_num is None:
            tab_num = self.__num
        # pylint: disable=invalid-name
        # type declaration
        Size = namedtuple('Size', ['width', 'height'])
        size = Size(
            self.__tabs[tab_num]['sheet'].winfo_width(),
            self.__tabs[tab_num]['sheet'].winfo_height())
        await ExerciseMixin.resize_sheet(self, size, tab_num)

    async def resize_sheet(self, event, tab_num):
        """Resize sheets to screen size."""
        left = await self.get_single_sheet(
            ExerciseMixin.get_ex_interface(self, tab_num),
            event.width,
            event.height)
        self.__tabs[tab_num]['sheet'].delete("left")
        self.__tabs[tab_num]['sheet'].create_image(
            0,
            0,
            image=self.image_cache[left]['image'],
            anchor=tk.NW,
            tags="left")

    async def on_pitch_change(self):
        """New pitch was picked by user or app."""
        asyncio.ensure_future(ExerciseMixin.update_sheet(self))
        if self.player is not None:
            self.play_next = True
            if self.player != '...':
                await self.stop()
        else:
            await ExerciseMixin.play(self)

    def set_repeat_once(self, _=None):
        """Repeat this midi once, then continue."""
        self.repeat_once = True

    async def next_(self):
        """Skip to next exercise."""
        curr_pitch = self.__tabs[self.__num]['curr_pitch'].get()
        curr_pos = self.__pitch_list.index(curr_pitch)
        pitch_pos = curr_pos
        pitch_selection = self.__tabs[self.__num]['pitches'].curselection()
        if len(pitch_selection) == 0:
            return
        if self.__tabs[self.__num]['random'].get() == 1:
            while pitch_pos == curr_pos:
                pitch_pos = choice(pitch_selection)
        elif curr_pos in pitch_selection:
            if pitch_selection.index(curr_pos) >= len(pitch_selection) - 1:
                curr_sound = self.__tabs[self.__num]['sound'].get()
                sound_pos = self.__sound_list.index(curr_sound)
                if sound_pos < len(self.__sound_list) - 1:
                    self.__tabs[self.__num]['sound'].set(
                        self.__sound_list[sound_pos + 1])
                else:
                    self.__tabs[self.__num]['sound'].set(
                        self.__sound_list[0])
                asyncio.ensure_future(ExerciseMixin.update_sheet(self))
                pitch_pos = pitch_selection[0]
            else:
                pitch_pos = pitch_selection[
                    pitch_selection.index(curr_pos) + 1]
        else:
            while pitch_pos not in pitch_selection:
                pitch_pos += 1
                if pitch_pos >= len(self.__pitch_list):
                    pitch_pos = 0
        self.__tabs[self.__num]['curr_pitch'].set(
            self.__pitch_list[pitch_pos])
        # I thought tkinter would call this, but apparently not
        await ExerciseMixin.on_pitch_change(self)

    async def play_or_stop(self):
        """Play or stop midi."""
        if self.player is not None and self.player != '...':
            # user stopped playback
            self.stopping = True
            await self.stop()
        else:
            await ExerciseMixin.play(self)

    async def play(self):
        """Play midi file."""
        midi = await self.get_file(
            ExerciseMixin.get_ex_interface(self),
            FileType.midi)
        if self.port is None:
            self.messages.append(
                "Still searching for pmidi port, cancelled playback.")
            self.show_messages()
            return
        if self.player is not None:
            self.new_message("already playing")
            return
        # reserve player
        self.player = "..."
        try:
            self.player = await play_midi(
                self.port,
                midi,
                on_midi_end=lambda: ExerciseMixin.on_midi_stop(self))
        except Exception as err:
            ErrorDialog(
                self.root,
                data="Could not start midi playback\n{}".format(str(err)))
            raise
        self.__tabs[self.__num]['play_stop'].set("stop")

    async def on_midi_stop(self):
        """Handle end of midi playback."""
        self.player = None
        if self.stopping:
            self.play_next = False
            self.stopping = False
            self.__tabs[self.__num]['play_stop'].set("play")
            return
        if self.play_next or \
                self.__tabs[self.__num]['autonext'].get() == 1:
            self.play_next = False
            if not self.repeat_once:
                await ExerciseMixin.next_(self)
            else:
                self.repeat_once = False
                await ExerciseMixin.play(self)
            return
        self.__tabs[self.__num]['play_stop'].set("play")
