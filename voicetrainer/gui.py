"""Simple user interface."""
from tkinter import ttk
import tkinter as tk
import asyncio
from pathlib import Path
from itertools import product
from random import choice
import json
from pkg_resources import resource_filename, Requirement, cleanup_resources

from voicetrainer.aiotk import (
    Root,
    ErrorDialog,
    OkCancelDialog,
    Messages,
    LoadFileDialog)
from voicetrainer.play import (
    get_qsynth_port,
    play_midi,
    stop_midi,
    exec_on_midi_end)
from voicetrainer.compile import compile_ex, compile_all

# pylint: disable=too-many-instance-attributes,too-many-locals
# pylint: disable=too-many-statements, too-many-public-methods
# It's messy, but there simply too many references to keep alive.
# pylint: disable=broad-except
# because of asyncio exceptions are only displayed at exit, we
# want to give the user immediate feedback.

class MainWindow:

    """Voicetrainer application."""

    def __init__(self, root):
        self.data_path = Path(resource_filename(
            Requirement.parse("voicetrainer"),
            'voicetrainer/exercises'))
        self.pitch_list = [note + octave for octave, note in product(
            [',', '', '\''],
            list("cdefgab"))]
        self.sound_list = ["Mi", "Na", "Noe", "Nu", "No"]
        self.root = root

        # compiler state
        self.compiler_count = 0

        self.messages = []
        self.messages_read = 0
        self.msg_window = None

        # midi state
        self.port = None
        self.player = None
        self.stopping = False
        self.play_next = False
        self.repeat_once = False

        # gui elements storage
        self.tabs = []
        self.image_cache = {}
        self.create_widgets()

    def create_tab(self, exercise: str) -> None:
        """Populate exercise tab."""
        tab = ttk.Frame(self.notebook)
        tab.rowconfigure(1, weight=1)
        tab.columnconfigure(3, weight=1)
        self.notebook.add(tab, text=exercise)
        self.tabs.append({})
        tab_num = len(self.tabs) - 1
        self.tabs[tab_num]['tab'] = tab

        # bpm selector
        bpm_label = ttk.Label(tab, text="bpm:")
        self.tabs[tab_num]['bpm_label'] = bpm_label
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
        self.tabs[tab_num]['bpm'] = bpm
        bpm.grid(column=3, row=0, sticky=tk.W+tk.N)

        # pitch selector
        scrollbar = tk.Scrollbar(tab, orient=tk.VERTICAL)
        self.tabs[tab_num]['pitch_scrollbar'] = scrollbar
        scrollbar.grid(row=1, column=0, sticky=tk.N+tk.S+tk.W)

        listbox = tk.Listbox(
            tab,
            yscrollcommand=scrollbar.set,
            width=3,
            # make selections in multiple listboxes possible
            exportselection=False,
            selectmode=tk.MULTIPLE)
        self.tabs[tab_num]['pitches'] = listbox
        listbox.grid(row=1, column=1, sticky=tk.N+tk.S+tk.W)
        scrollbar['command'] = listbox.yview

        listbox.insert(0, *self.pitch_list)
        listbox.selection_set(7, 14)

        # controls
        frame = ttk.Frame(tab)
        self.tabs[tab_num]['control_frame'] = frame
        frame.grid(column=2, row=2, columnspan=2, sticky=tk.W+tk.N)
        # sound pitch random autonext repeat_once next play/stop

        soundvar = tk.StringVar()
        soundvar.set("Mi")
        self.tabs[tab_num]['sound'] = soundvar
        sound = tk.OptionMenu(
            frame,
            soundvar,
            *self.sound_list,
            command=lambda _: asyncio.ensure_future(self.update_sheet()))
        self.tabs[tab_num]['sound_menu'] = sound
        sound.grid(column=0, row=0, sticky=tk.W+tk.N)

        textvar = tk.StringVar()
        textvar.set(self.pitch_list[listbox.curselection()[0]])
        self.tabs[tab_num]['curr_pitch'] = textvar
        curr_pitch = tk.OptionMenu(
            frame,
            textvar,
            *self.pitch_list,
            command=lambda _: asyncio.ensure_future(
                self.on_pitch_change()))
        self.tabs[tab_num]['pitch_menu'] = curr_pitch
        curr_pitch.grid(column=1, row=0, sticky=tk.W+tk.N)

        rand_int = tk.IntVar()
        self.tabs[tab_num]['random'] = rand_int
        random = ttk.Checkbutton(frame, text="random", variable=rand_int)
        self.tabs[tab_num]['random_box'] = random
        random.grid(column=2, row=0, sticky=tk.W+tk.N)

        auto_int = tk.IntVar()
        self.tabs[tab_num]['autonext'] = auto_int
        autonext = ttk.Checkbutton(
            frame, text="autonext", variable=auto_int)
        self.tabs[tab_num]['autonext_box'] = autonext
        autonext.grid(column=3, row=0, sticky=tk.W+tk.N)

        repeat = ttk.Button(
            frame,
            text="repeat once",
            command=self.set_repeat_once)
        self.tabs[tab_num]['repeat'] = repeat
        repeat.grid(column=4, row=0, sticky=tk.W+tk.N)

        next_ = ttk.Button(
            frame,
            text="next",
            command=lambda: asyncio.ensure_future(self.next_()))
        self.tabs[tab_num]['next_'] = next_
        next_.grid(column=5, row=0, sticky=tk.W+tk.N)

        play_stop = tk.StringVar()
        play_stop.set("play")
        self.tabs[tab_num]['play_stop'] = play_stop
        play = ttk.Button(
            frame,
            textvariable=play_stop,
            command=lambda: asyncio.ensure_future(self.play_or_stop()))
        self.tabs[tab_num]['play'] = play
        play.grid(column=6, row=0, sticky=tk.W+tk.N)

        # sheet display
        sheet = ttk.Label(tab)
        self.tabs[tab_num]['sheet'] = sheet
        sheet.grid(column=2, row=1, columnspan=2, sticky=tk.N+tk.W)
        asyncio.ensure_future(self.update_sheet(tab_num=tab_num))

    def create_widgets(self):
        """Put some stuff up to look at."""
        self.window = ttk.Frame(self.root)
        self.window.rowconfigure(0, weight=1)
        self.window.columnconfigure(2, weight=1)
        self.window.grid(column=0, row=0, sticky=tk.N+tk.S+tk.E+tk.W)
        self.top = self.window.winfo_toplevel()
        self.top.rowconfigure(0, weight=1)
        self.top.columnconfigure(0, weight=1)
        self.top.title("VoiceTrainer")

        # self.top menu
        self.menubar = tk.Menu(self.top)
        self.top['menu'] = self.menubar

        self.file_menu = tk.Menu(self.menubar)
        self.menubar.add_cascade(label='File', menu=self.file_menu)
        self.file_menu.add_command(
            label='Save state',
            command=self.save_state)
        self.file_menu.add_command(
            label='Quit',
            command=lambda: asyncio.ensure_future(self.quit()))

        self.ex_menu = tk.Menu(self.menubar)
        self.menubar.add_cascade(label='Exercises', menu=self.ex_menu)
        self.ex_menu.add_command(
            label='Add',
            command=lambda: asyncio.ensure_future(self.add_exercise()))
        self.ex_menu.add_command(
            label='Delete',
            command=lambda: asyncio.ensure_future(self.remove_exercise()))
        self.ex_menu.add_command(
            label='Clear cache',
            command=None)
        self.ex_menu.add_command(
            label='Precompile',
            command=lambda: asyncio.ensure_future(self.recompile()))

        self.notebook = ttk.Notebook(self.window)
        for exercise in self.data_path.glob('*.ly'):
            self.create_tab(exercise.stem)
        self.notebook.grid(
            column=0, row=0, columnspan=3, sticky=tk.N+tk.S+tk.E+tk.W)

        self.separators = []

        self.statusbar = ttk.Frame(self.window)
        self.statusbar.grid(row=1, column=0, sticky=tk.N+tk.W)

        self.compiler_label = ttk.Label(self.statusbar, text="Compiler:")
        self.compiler_label.grid(row=0, column=0, sticky=tk.N+tk.E)
        self.progress = ttk.Progressbar(
            self.statusbar,
            mode='indeterminate',
            orient=tk.HORIZONTAL)
        self.progress.grid(row=0, column=1, sticky=tk.N+tk.W)

        sep = ttk.Separator(self.statusbar, orient=tk.VERTICAL)
        sep.grid(row=0, column=2)
        self.separators.append(sep)

        self.port_label_text = tk.StringVar()
        self.port_label_text.set('pmidi port: None')
        self.port_label = ttk.Label(
            self.statusbar,
            textvariable=self.port_label_text)
        self.port_label.grid(row=0, column=3, sticky=tk.N+tk.W)

        sep = ttk.Separator(self.statusbar, orient=tk.VERTICAL)
        sep.grid(row=0, column=4)
        self.separators.append(sep)

        self.msg_text = tk.StringVar()
        self.msg_text.set('messages')
        self.msg_button = ttk.Button(
            self.statusbar,
            textvariable=self.msg_text,
            command=self.display_messages)
        self.msg_button.grid(row=0, column=5, sticky=tk.N+tk.W)

        self.resize = ttk.Sizegrip(self.window)
        self.resize.grid(row=1, column=2, sticky=tk.S+tk.E)
        self.restore_state()

    async def quit(self):
        """Confirm exit."""
        if self.compiler_count > 0:
            # ask conformation before quit
            confirm_exit = OkCancelDialog(
                self.root,
                (
                    "Uncompleted background task\n"
                    "An exercise is still being compiled in the "
                    "background. Do you still want to exit? The "
                    "task will be aborted."))
            if not await confirm_exit.await_data():
                return
        self.close()

    def close(self):
        """Exit main application."""
        self.save_state()
        self.progress.stop()
        self.top.destroy()
        self.root.close()

    @property
    def tab_num(self):
        """Return index of current tab."""
        tab_id = self.notebook.select()
        return self.notebook.index(tab_id)

    def save_state(self):
        """Save settings to json file."""
        data = {}
        for i in range(len(self.tabs)):
            tab_name = self.notebook.tab(i)['text']
            data[tab_name] = {}
            data[tab_name]['pitch_selection'] = self.tabs[i]['pitches'].curselection()
            data[tab_name]['bpm'] = self.tabs[i]['bpm'].get()
            data[tab_name]['sound'] = self.tabs[i]['sound'].get()
            data[tab_name]['autonext'] = self.tabs[i]['autonext'].get()
            data[tab_name]['random'] = self.tabs[i]['random'].get()
        self.data_path.joinpath('state.json').write_text(
            json.dumps(data))

    def restore_state(self):
        """Restore saved settings."""
        state_file = self.data_path.joinpath('state.json')
        if not state_file.is_file():
            return
        data = json.loads(state_file.read_text())
        for i in range(len(self.tabs)):
            tab_name = self.notebook.tab(i)['text']
            if tab_name not in data:
                continue
            self.tabs[i]['pitches'].selection_clear(
                0, len(self.pitch_list) - 1)
            for p_index in data[tab_name]['pitch_selection']:
                self.tabs[i]['pitches'].selection_set(p_index)
            self.tabs[i]['bpm'].set(data[tab_name]['bpm'])
            self.tabs[i]['sound'].set(data[tab_name]['sound'])
            self.tabs[i]['autonext'].set(
                data[tab_name]['autonext'])
            self.tabs[i]['random'].set(data[tab_name]['random'])

    def show_messages(self):
        """Show if there unread messages."""
        if len(self.messages) > self.messages_read:
            self.msg_text.set('!!!Messages!!!')
            if self.msg_window is not None:
                self.msg_window.update_data(self.messages)

    def display_messages(self, _=None):
        """Display all messages."""
        if self.msg_window is None:
            self.msg_window = Messages(
                self.root,
                data=self.messages,
                on_close=self.on_close_msg_window)
        else:
            self.msg_window.to_front()
        self.messages_read = len(self.messages)
        self.msg_text.set('Messages')

    def on_close_msg_window(self, _):
        """Messages window was closed."""
        self.msg_window = None

    async def add_exercise(self):
        """Add new exercise."""
        dialog = LoadFileDialog(
            self.root,
            dir_or_file='~',
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
            new_file = self.data_path.joinpath("{}.ly".format(ex_name))
            if new_file.is_file():
                ErrorDialog(
                    self.root,
                    data="An exercise with name {} already exists.".format(
                        ex_name))
                return
            new_file.touch()
            new_file.write_text(content)
            self.create_tab(ex_name)

    async def remove_exercise(self):
        """Remove exercise."""
        tab_num = self.tab_num
        tab_name = self.notebook.tab(tab_num)['text']
        confirm = OkCancelDialog(
            self.root,
            data="Are you sure you want to delete {}? This cannot be undone.".format(
                tab_name))
        if not await confirm.await_data():
            return
        self.stopping = True
        await self.stop()
        tab = self.tabs[tab_num]['tab']
        self.notebook.forget(tab)
        tab.destroy()
        del self.tabs[tab_num]
        file_name = Path(self.data_path).joinpath(
            "{}.ly".format(tab_name))
        # pylint: disable=no-member
        # does too!
        file_name.unlink()

    def update_compiler(self):
        """Set compiler progress bar status."""
        if self.compiler_count > 0:
            self.progress.start()
        else:
            self.progress.stop()

    async def recompile(self):
        """Recompile all exercises."""
        self.compiler_count += 1
        self.update_compiler()
        log = await compile_all(self.data_path)
        for output, err in [
                log_tuple for log_item in log for log_tuple in log_item]:
            if len(output) > 0:
                self.messages.append(output)
            if len(err) > 0:
                self.messages.append(err)
        self.compiler_count -= 1
        self.update_compiler()
        self.show_messages()
        self.image_cache = {}
        for i in range(len(self.tabs)):
            await self.update_sheet(tab_num=i)

    async def update_sheet(self, tab_num=None):
        """Display relevant sheet."""
        if tab_num is None:
            tab_num = self.tab_num
        png = await self.get_file(tab_num=tab_num)
        if png not in self.image_cache:
            self.image_cache[png] = tk.PhotoImage(file=png)
        self.tabs[tab_num]['sheet'].config(image=self.image_cache[png])

    async def on_pitch_change(self):
        """New pitch was picked by user or app."""
        asyncio.ensure_future(self.update_sheet())
        if self.player is not None:
            self.play_next = True
            await self.stop()
        else:
            await self.play()

    def set_repeat_once(self, _=None):
        """Repeat this midi once, then continue."""
        self.repeat_once = True

    async def next_(self):
        """Skip to next exercise."""
        curr_pitch = self.tabs[self.tab_num]['curr_pitch'].get()
        curr_pos = self.pitch_list.index(curr_pitch)
        pitch_pos = curr_pos
        pitch_selection = self.tabs[self.tab_num]['pitches'].curselection()
        if len(pitch_selection) == 0:
            return
        if self.tabs[self.tab_num]['random'].get() == 1:
            while pitch_pos == curr_pos:
                pitch_pos = choice(pitch_selection)
        elif curr_pos in pitch_selection:
            if pitch_selection.index(curr_pos) >= len(pitch_selection) - 1:
                curr_sound = self.tabs[self.tab_num]['sound'].get()
                sound_pos = self.sound_list.index(curr_sound)
                if sound_pos < len(self.sound_list) - 1:
                    self.tabs[self.tab_num]['sound'].set(
                        self.sound_list[sound_pos + 1])
                else:
                    self.tabs[self.tab_num]['sound'].set(
                        self.sound_list[0])
                asyncio.ensure_future(self.update_sheet())
                pitch_pos = pitch_selection[0]
            else:
                pitch_pos = pitch_selection[
                    pitch_selection.index(curr_pos) + 1]
        else:
            while pitch_pos not in pitch_selection:
                pitch_pos += 1
                if pitch_pos >= len(self.pitch_list):
                    pitch_pos = 0
        self.tabs[self.tab_num]['curr_pitch'].set(
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

    async def get_file(self, midi: bool=False, tab_num=None) -> str:
        """Assemble file_name, compile if non-existent."""
        if tab_num is None:
            tab_num = self.tab_num
        tab_name = self.notebook.tab(tab_num)['text']
        pitch = self.tabs[tab_num]['curr_pitch'].get()
        bpm = int(self.tabs[tab_num]['bpm'].get())
        sound = self.tabs[tab_num]['sound'].get()
        extension = ".ly"
        if midi:
            file_name = self.data_path.joinpath(
                "{}-{}bpm-{}.midi".format(tab_name, bpm, pitch))
        else:
            file_name = self.data_path.joinpath(
                "{}-{}-{}.png".format(tab_name, pitch, sound))
        if not file_name.is_file():
            try:
                self.compiler_count += 1
                self.update_compiler()
                log = await compile_ex(
                    self.data_path.joinpath(
                        "{}{}".format(tab_name, extension)),
                    [bpm],
                    [pitch],
                    [sound],
                    midi)
                if len(log[0][0]) > 0:
                    self.messages.append(log[0][0])
                if len(log[0][1]) > 0:
                    self.messages.append(log[0][1])
                self.show_messages()
            except Exception as err:
                ErrorDialog(
                    self.root,
                    data="Could not compile exercise\n{}".format(str(err)))
                raise
            finally:
                self.compiler_count -= 1
                self.update_compiler()
        return file_name

    async def play(self):
        """Play midi file."""
        midi = await self.get_file(midi=True)
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
        self.tabs[self.tab_num]['play_stop'].set("stop")
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
            self.stopping = False
            self.tabs[self.tab_num]['play_stop'].set("play")
            return
        if self.play_next or \
                self.tabs[self.tab_num]['autonext'].get() == 1:
            self.play_next = False
            if not self.repeat_once:
                await self.next_()
            else:
                self.repeat_once = False
                await self.play()
            return
        self.tabs[self.tab_num]['play_stop'].set("play")

def start():
    """Start gui and event loop."""
    loop = asyncio.get_event_loop()
    root = Root(loop)
    root.register_window(MainWindow(root))
    try:
        loop.run_forever()
    except KeyboardInterrupt:
        root.close(crash=True)
    finally:
        loop.close()
        cleanup_resources()
