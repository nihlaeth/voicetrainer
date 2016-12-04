"""All the exercise stuff."""
from tkinter import ttk
import tkinter as tk
import asyncio
from pathlib import Path
from itertools import product, chain
from functools import partial
from random import choice
from pkg_resources import resource_filename, Requirement

from voicetrainer.aiotk import (
    ErrorDialog,
    OkCancelDialog,
    Dialog,
    SaveFileDialog,
    LoadFileDialog)
from voicetrainer.play import (
    get_qsynth_port,
    play_midi,
    exec_on_midi_end)
from voicetrainer.compile import compile_all
from voicetrainer.compile_interface import FileType, Exercise

# pylint: disable=too-many-instance-attributes,too-many-locals
# pylint: disable=too-many-statements,no-member
class ExerciseMixin:

    """
    All the exercise stuff.

    This is a mixin class. If you need a method from here, call it
    specifically. To avoid naming collisions, start all properties
    with ex_. All properties that do not start with ex_, are assumed to be
    provided the class that this is mixed in.
    """

    def __init__(self):
        self.ex_data_path = Path(resource_filename(
            Requirement.parse("voicetrainer"),
            'voicetrainer/exercises'))
        self.ex_pitch_list = [note + octave for octave, note in product(
            [',', '', '\''],
            list("cdefgab"))]
        self.ex_sound_list = ["Mi", "Na", "Noe", "Nu", "No"]
        self.ex_tabs = []
        self.ex_image_cache = {}

        ExerciseMixin.create_widgets(self)

    def create_tab(self, exercise: str) -> None:
        """Populate exercise tab."""
        tab = ttk.Frame(self.ex_notebook)
        tab.rowconfigure(1, weight=1)
        tab.columnconfigure(3, weight=1)
        self.ex_notebook.add(tab, text=exercise)
        self.ex_tabs.append({})
        tab_num = len(self.ex_tabs) - 1
        self.ex_tabs[tab_num]['tab'] = tab

        # bpm selector
        bpm_label = ttk.Label(tab, text="bpm:")
        self.ex_tabs[tab_num]['bpm_label'] = bpm_label
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
        self.ex_tabs[tab_num]['bpm'] = bpm
        bpm.grid(column=3, row=0, sticky=tk.W+tk.N)

        # pitch selector
        scrollbar = tk.Scrollbar(tab, orient=tk.VERTICAL)
        self.ex_tabs[tab_num]['pitch_scrollbar'] = scrollbar
        scrollbar.grid(row=1, column=0, sticky=tk.N+tk.S+tk.W)

        listbox = tk.Listbox(
            tab,
            yscrollcommand=scrollbar.set,
            width=3,
            # make selections in multiple listboxes possible
            exportselection=False,
            selectmode=tk.MULTIPLE)
        self.ex_tabs[tab_num]['pitches'] = listbox
        listbox.grid(row=1, column=1, sticky=tk.N+tk.S+tk.W)
        scrollbar['command'] = listbox.yview

        listbox.insert(0, *self.ex_pitch_list)
        listbox.selection_set(7, 14)

        # controls
        frame = ttk.Frame(tab)
        self.ex_tabs[tab_num]['control_frame'] = frame
        frame.grid(column=2, row=2, columnspan=2, sticky=tk.W+tk.N)
        # sound pitch random autonext repeat_once next play/stop

        soundvar = tk.StringVar()
        soundvar.set("Mi")
        self.ex_tabs[tab_num]['sound'] = soundvar
        sound = tk.OptionMenu(
            frame,
            soundvar,
            *self.ex_sound_list,
            command=lambda _: asyncio.ensure_future(
                ExerciseMixin.update_sheet(self)))
        self.ex_tabs[tab_num]['sound_menu'] = sound
        sound.grid(column=0, row=0, sticky=tk.W+tk.N)

        textvar = tk.StringVar()
        textvar.set(self.ex_pitch_list[listbox.curselection()[0]])
        self.ex_tabs[tab_num]['curr_pitch'] = textvar
        curr_pitch = tk.OptionMenu(
            frame,
            textvar,
            *self.ex_pitch_list,
            command=lambda _: asyncio.ensure_future(
                ExerciseMixin.on_pitch_change(self)))
        self.ex_tabs[tab_num]['pitch_menu'] = curr_pitch
        curr_pitch.grid(column=1, row=0, sticky=tk.W+tk.N)

        rand_int = tk.IntVar()
        self.ex_tabs[tab_num]['random'] = rand_int
        random = ttk.Checkbutton(frame, text="random", variable=rand_int)
        self.ex_tabs[tab_num]['random_box'] = random
        random.grid(column=2, row=0, sticky=tk.W+tk.N)

        auto_int = tk.IntVar()
        self.ex_tabs[tab_num]['autonext'] = auto_int
        autonext = ttk.Checkbutton(
            frame, text="autonext", variable=auto_int)
        self.ex_tabs[tab_num]['autonext_box'] = autonext
        autonext.grid(column=3, row=0, sticky=tk.W+tk.N)

        repeat = ttk.Button(
            frame,
            text="repeat once",
            command=lambda: ExerciseMixin.set_repeat_once(self))
        self.ex_tabs[tab_num]['repeat'] = repeat
        repeat.grid(column=4, row=0, sticky=tk.W+tk.N)

        next_ = ttk.Button(
            frame,
            text="next",
            command=lambda: asyncio.ensure_future(
                ExerciseMixin.next_(self)))
        self.ex_tabs[tab_num]['next_'] = next_
        next_.grid(column=5, row=0, sticky=tk.W+tk.N)

        play_stop = tk.StringVar()
        play_stop.set("play")
        self.ex_tabs[tab_num]['play_stop'] = play_stop
        play = ttk.Button(
            frame,
            textvariable=play_stop,
            command=lambda: asyncio.ensure_future(
                ExerciseMixin.play_or_stop(self)))
        self.ex_tabs[tab_num]['play'] = play
        play.grid(column=6, row=0, sticky=tk.W+tk.N)

        # sheet display
        sheet = ttk.Label(tab)
        self.ex_tabs[tab_num]['sheet'] = sheet
        sheet.grid(column=2, row=1, columnspan=2, sticky=tk.N+tk.W)
        asyncio.ensure_future(
            ExerciseMixin.update_sheet(self, tab_num=tab_num))

    def create_widgets(self):
        """Put some stuff up to look at."""
        self.ex_menu = tk.Menu(self.menubar)
        self.menubar.add_cascade(label='Exercises', menu=self.ex_menu)
        self.ex_menu.add_command(
            label='Add',
            command=lambda: asyncio.ensure_future(
                ExerciseMixin.add_exercise(self)))
        self.ex_menu.add_command(
            label='Delete',
            command=lambda: asyncio.ensure_future(
                ExerciseMixin.remove_exercise(self)))
        self.ex_menu.add_command(
            label='Export midi',
            command=lambda: asyncio.ensure_future(
                ExerciseMixin.export(self, FileType.midi)))
        self.ex_menu.add_command(
            label='Export png',
            command=lambda: asyncio.ensure_future(
                ExerciseMixin.export(self, FileType.png)))
        self.ex_menu.add_command(
            label='Export pdf',
            command=lambda: asyncio.ensure_future(
                ExerciseMixin.export(self, FileType.pdf)))
        self.ex_menu.add_command(
            label='Export lilypond',
            command=lambda: asyncio.ensure_future(
                ExerciseMixin.export(self, FileType.lily)))
        self.ex_menu.add_command(
            label='Clear cache',
            command=lambda: asyncio.ensure_future(
                ExerciseMixin.clear_cache(self)))
        self.ex_menu.add_command(
            label='Precompile',
            command=lambda: asyncio.ensure_future(
                ExerciseMixin.recompile(self)))

        self.ex_notebook = ttk.Notebook(self.window)
        for exercise in self.ex_data_path.glob('*.ly'):
            ExerciseMixin.create_tab(self, exercise.stem)
        self.ex_notebook.grid(
            column=0, row=0, columnspan=3, sticky=tk.N+tk.S+tk.E+tk.W)

    @property
    def ex_num(self):
        """Return index of current tab."""
        tab_id = self.ex_notebook.select()
        return self.ex_notebook.index(tab_id)

    def save_state(self):
        """Return exercise state."""
        data = {}
        for i in range(len(self.ex_tabs)):
            tab_name = self.ex_notebook.tab(i)['text']
            data[tab_name] = {}
            data[tab_name]['pitch_selection'] = self.ex_tabs[i]['pitches'].curselection()
            data[tab_name]['bpm'] = self.ex_tabs[i]['bpm'].get()
            data[tab_name]['sound'] = self.ex_tabs[i]['sound'].get()
            data[tab_name]['autonext'] = self.ex_tabs[i]['autonext'].get()
            data[tab_name]['random'] = self.ex_tabs[i]['random'].get()
        return data

    def restore_state(self, data):
        """Restore saved settings."""
        for i in range(len(self.ex_tabs)):
            tab_name = self.ex_notebook.tab(i)['text']
            if tab_name not in data:
                continue
            self.ex_tabs[i]['pitches'].selection_clear(
                0, len(self.ex_pitch_list) - 1)
            for p_index in data[tab_name]['pitch_selection']:
                self.ex_tabs[i]['pitches'].selection_set(p_index)
            self.ex_tabs[i]['bpm'].set(data[tab_name]['bpm'])
            self.ex_tabs[i]['sound'].set(data[tab_name]['sound'])
            self.ex_tabs[i]['autonext'].set(
                data[tab_name]['autonext'])
            self.ex_tabs[i]['random'].set(data[tab_name]['random'])

    async def recompile(self):
        """Recompile all exercises."""
        self.compiler_count += 1
        self.update_compiler()
        log = await compile_all(self.ex_data_path)
        for output, err in [
                log_tuple for log_item in log for log_tuple in log_item]:
            if len(output) > 0:
                self.messages.append(output)
            if len(err) > 0:
                self.messages.append(err)
        self.compiler_count -= 1
        self.update_compiler()
        self.show_messages()
        self.ex_image_cache = {}
        for i in range(len(self.ex_tabs)):
            await self.ex_update_sheet(tab_num=i)

        # remove files
        for file_ in chain(
                self.ex_data_path.glob("*.midi"),
                self.ex_data_path.glob("*.png"),
                self.ex_data_path.glob("*.pdf")):
            file_.unlink()

        # clear image_cache and display new sheets
        self.ex_image_cache = {}
        for i in range(len(self.ex_tabs)):
            await ExerciseMixin.update_sheet(self, tab_num=i)

    def get_ex_interface(self, tab_num=None):
        """Return exercise interface."""
        if tab_num is None:
            tab_num = self.ex_num
        tab_name = self.ex_notebook.tab(tab_num)['text']
        pitch = self.ex_tabs[tab_num]['curr_pitch'].get()
        bpm = int(self.ex_tabs[tab_num]['bpm'].get())
        sound = self.ex_tabs[tab_num]['sound'].get()
        return Exercise(
            self.ex_data_path,
            tab_name,
            pitch,
            bpm,
            sound)

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
            Dialog(self.root, data="Export complete")
            return
        self.get_file(exercise, file_type)

        save_path.write_bytes(file_name.read_bytes())
        Dialog(self.root, data="Export complete")

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
            new_file = self.ex_data_path.joinpath("{}.ly".format(ex_name))
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
        tab_num = self.ex_num
        tab_name = self.ex_notebook.tab(tab_num)['text']
        confirm = OkCancelDialog(
            self.root,
            data="Are you sure you want to delete {}? This cannot be undone.".format(
                tab_name))
        if not await confirm.await_data():
            return
        self.stopping = True
        await self.stop()
        tab = self.ex_tabs[tab_num]['tab']
        self.ex_notebook.forget(tab)
        tab.destroy()
        del self.ex_tabs[tab_num]
        file_name = Path(self.ex_data_path).joinpath(
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
                self.data_path.glob("*.midi"),
                self.data_path.glob("*.png"),
                self.data_path.glob("*.pdf")):
            file_.unlink()

        # clear image_cache and display new sheets
        self.ex_image_cache = {}
        for i in range(len(self.ex_tabs)):
            await ExerciseMixin.update_sheet(self, tab_num=i)

    async def update_sheet(self, tab_num=None):
        """Display relevant sheet."""
        if tab_num is None:
            tab_num = self.ex_num
        png = await self.get_file(ExerciseMixin.get_ex_interface(self, tab_num))
        if png not in self.ex_image_cache:
            self.ex_image_cache[png] = tk.PhotoImage(file=png)
        self.ex_tabs[tab_num]['sheet'].config(image=self.ex_image_cache[png])

    async def on_pitch_change(self):
        """New pitch was picked by user or app."""
        asyncio.ensure_future(ExerciseMixin.update_sheet(self))
        if self.player is not None:
            self.play_next = True
            await self.stop()
        else:
            await ExerciseMixin.play(self)

    def set_repeat_once(self, _=None):
        """Repeat this midi once, then continue."""
        self.repeat_once = True

    async def next_(self):
        """Skip to next exercise."""
        curr_pitch = self.ex_tabs[self.ex_num]['curr_pitch'].get()
        curr_pos = self.ex_pitch_list.index(curr_pitch)
        pitch_pos = curr_pos
        pitch_selection = self.ex_tabs[self.ex_num]['pitches'].curselection()
        if len(pitch_selection) == 0:
            return
        if self.ex_tabs[self.ex_num]['random'].get() == 1:
            while pitch_pos == curr_pos:
                pitch_pos = choice(pitch_selection)
        elif curr_pos in pitch_selection:
            if pitch_selection.index(curr_pos) >= len(pitch_selection) - 1:
                curr_sound = self.ex_tabs[self.ex_num]['sound'].get()
                sound_pos = self.ex_sound_list.index(curr_sound)
                if sound_pos < len(self.ex_sound_list) - 1:
                    self.ex_tabs[self.ex_num]['sound'].set(
                        self.ex_sound_list[sound_pos + 1])
                else:
                    self.ex_tabs[self.ex_num]['sound'].set(
                        self.ex_sound_list[0])
                asyncio.ensure_future(ExerciseMixin.update_sheet(self))
                pitch_pos = pitch_selection[0]
            else:
                pitch_pos = pitch_selection[
                    pitch_selection.index(curr_pos) + 1]
        else:
            while pitch_pos not in pitch_selection:
                pitch_pos += 1
                if pitch_pos >= len(self.ex_pitch_list):
                    pitch_pos = 0
        self.ex_tabs[self.ex_num]['curr_pitch'].set(
            self.ex_pitch_list[pitch_pos])
        # I thought tkinter would call this, but apparently not
        await ExerciseMixin.on_pitch_change(self)

    async def play_or_stop(self):
        """Play or stop midi."""
        if self.player is not None:
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
            try:
                self.port = "..."
                self.port = await get_qsynth_port()
                self.port_label_text.set('pmidi port: {}'.format(self.port))
            except Exception as err:
                ErrorDialog(
                    self.root,
                    data="Could not find midi port\n{}".format(str(err)))
                raise
        elif self.port == "...":
            # already spawned port searching proc
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
        self.ex_tabs[self.ex_num]['play_stop'].set("stop")
        asyncio.ensure_future(exec_on_midi_end(
            self.player,
            partial(ExerciseMixin.on_midi_stop, self)))

    async def on_midi_stop(self):
        """Handle end of midi playback."""
        self.player = None
        if self.stopping:
            self.play_next = False
            self.stopping = False
            self.ex_tabs[self.ex_num]['play_stop'].set("play")
            return
        if self.play_next or \
                self.ex_tabs[self.ex_num]['autonext'].get() == 1:
            self.play_next = False
            if not self.repeat_once:
                await ExerciseMixin.next_(self)
            else:
                self.repeat_once = False
                await ExerciseMixin.play(self)
            return
        self.ex_tabs[self.ex_num]['play_stop'].set("play")
