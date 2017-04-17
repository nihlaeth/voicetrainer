"""Compile lily code into png and midi."""
import sys
from typing import Dict, Tuple, Callable
from pathlib import Path
from asyncio import create_subprocess_exec
from asyncio.subprocess import PIPE

from PIL import Image, ImageTk

from voicetrainer.midi import (
    MidiFile, MidiTrack, DeltaTime, MidiEvent, get_numbers_as_list)
from voicetrainer.compile_interface import FileType, Interface

# some state
_ERR_CB = print
_COMPILER_CB = lambda _: None

def set_err_cb(err_cb: Callable[[str], None]):
    """Give module a way to report errors."""
    global _ERR_CB
    _ERR_CB = err_cb

def set_compiler_cb(compiler_cb: Callable[[int], None]):
    """Call compiler_cb with 1 or -1 every time compiling starts or stops."""
    global _COMPILER_CB
    _COMPILER_CB = compiler_cb

def measure_to_tick(time_changes, measure, ticks_per_quarter_note):
    """Convert measure to tick."""
    ticks = 0
    closest_m = 1
    quarts_m = 4
    for next_tick, next_quarts_m in time_changes:
        next_measure = get_measure_num(
            time_changes, next_tick, ticks_per_quarter_note)
        if next_measure > measure:
            break
        else:
            closest_m = next_measure
            ticks = next_tick
            quarts_m = next_quarts_m
    ticks += (measure - closest_m) * quarts_m * ticks_per_quarter_note
    return ticks

def get_measure_num(time_changes, total_ticks, ticks_per_quarter_note):
    """Get current measure number."""
    measure = 1
    curr_tick = 0
    curr_quarts_m = 4
    for next_tick, next_quarts_m in time_changes:
        stop = False
        if next_tick == curr_tick:
            # overwrite current quarts_per_minute
            curr_quarts_m = next_quarts_m
            continue
        if total_ticks < next_tick:
            # not at this time change yet
            next_tick = total_ticks
            # stop after this
            stop = True
        delta_tick = next_tick - curr_tick
        delta_measure = (delta_tick // ticks_per_quarter_note) // curr_quarts_m
        curr_tick = next_tick
        curr_quarts_m = next_quarts_m
        measure += delta_measure
        if stop:
            break
    if curr_tick != total_ticks:
        # we didn't reach total_ticks
        delta_tick = total_ticks - curr_tick
        delta_measure = (delta_tick // ticks_per_quarter_note) // curr_quarts_m
        measure += delta_measure
    return measure

async def compile_(interface: Interface, file_type: FileType) -> None:
    """Open interface file, format, and compile with lilypond."""
    _COMPILER_CB(1)
    proc = await create_subprocess_exec(
        *interface.get_lilypond_options(file_type),
        stdin=PIPE,
        stdout=PIPE,
        stderr=PIPE)
    outs, errs = await proc.communicate(str.encode(
        interface.get_final_lily_code(file_type)))
    if file_type is FileType.midi and \
            (interface.start_measure > 1 or interface.velocity != 0):
        await create_clipped_midi(interface)
    _COMPILER_CB(-1)
    if len(outs) > 0:
        _ERR_CB(bytes.decode(outs))
    if len(errs) > 0:
        _ERR_CB(bytes.decode(errs))

def midi_generator(midi: MidiFile) -> Tuple[int, DeltaTime, MidiEvent]:
    """Iterate over midi events."""
    for i, track in enumerate(midi.tracks):
        delta_time = None
        for event in track.events:
            if event.is_delta_time():
                delta_time = event
            else:
                yield (i, delta_time, event)

class MidiIterator:

    """Wrap midi_generator so it can be used asynchronously."""

    def __init__(self, midi: MidiFile):
        self.midi = midi
        self.iterator = midi_generator(midi)

    async def __aiter__(self):
        return self

    async def __anext__(self):
        try:
            return next(self.iterator)
        except StopIteration:
            raise StopAsyncIteration

async def _collect_time_changes(midi: MidiFile):
    time_changes = []
    total_ticks = [0] * len(midi.tracks)
    async for track_num, delta_time, event in MidiIterator(midi):
        total_ticks[track_num] += delta_time.time
        if event.type_ == "TIME_SIGNATURE":
            # t_signature explained:
            # in a 4/4 time signature, meaning there 4 quarter notes
            # in a measure,
            # t_signature[0] is the numerator, or the first 4
            # pow(2, t_signature[1]) is the divisor, or the second 4
            t_signature = get_numbers_as_list(event.data)
            # what we're doing here in essence is changes in number
            # of quarter notes per measure at the cumulative tick count
            time_changes.append(
                (
                    total_ticks[track_num],
                    (t_signature[0] / pow(2, t_signature[1])) * 4))
    return time_changes

async def create_clipped_midi(interface: Interface):
    """Start midi from start_measure, with events intact."""
    midi = MidiFile()
    midi.open(str(interface.get_filename(
        FileType.midi, compiling=True)))
    midi.read()
    midi.close()

    new_midi = MidiFile()
    new_midi.ticks_per_quarter_note = midi.ticks_per_quarter_note
    new_midi.format = midi.format
    for track_num, _ in enumerate(midi.tracks):
        new_midi.tracks.append(MidiTrack(track_num))

    ticks_per_quarter_note = midi.ticks_per_quarter_note
    time_changes = await _collect_time_changes(midi)
    total_ticks = [0] * len(midi.tracks)
    async for track_num, delta_time, event in MidiIterator(midi):
        total_ticks[track_num] += delta_time.time
        measure = get_measure_num(
            time_changes,
            total_ticks[track_num],
            ticks_per_quarter_note)

        # adjust velocity
        if event.type_ in ['NOTE_ON', 'NOTE_OFF']:
            new_velocity = event.velocity + interface.velocity
            if new_velocity < 0:
                new_velocity = 0
            elif new_velocity > 127:
                new_velocity = 127
            event.velocity = new_velocity

        # the actual clipping
        if event.type_ in ['NOTE_ON', 'NOTE_OFF'] and \
                measure < interface.start_measure:
            continue
        else:
            if measure < interface.start_measure:
                # insert event with timedelta 0
                delta_time.time = 0
            else:
                prev_m = get_measure_num(
                    time_changes,
                    total_ticks[track_num] - delta_time.time,
                    ticks_per_quarter_note)
                if prev_m < interface.start_measure:
                    delta_time.time = int(
                        total_ticks[track_num] - measure_to_tick(
                            time_changes,
                            interface.start_measure,
                            ticks_per_quarter_note))
            new_midi.tracks[track_num].events.append(delta_time)
            new_midi.tracks[track_num].events.append(event)
    for track in new_midi.tracks:
        track.update_events()
    new_midi.open(str(interface.get_filename(FileType.midi)), 'wb')
    new_midi.write()
    new_midi.close()

async def get_single_sheet(
        image_cache: Dict,
        interface: Interface,
        max_width: int,
        max_height: int) -> Path:
    """Fetch and size sheet while preserving ratio."""
    png = await get_file(interface)
    if png not in image_cache:
        image_cache[png] = {}
        image_cache[png]['original'] = Image.open(str(png))
    original = image_cache[png]['original']
    if max_width < 1:
        max_width = 1
    if max_height < 1:
        max_height = 1
    width_ratio = float(original.width) / float(max_width)
    height_ratio = float(original.height) / float(max_height)
    ratio = max([width_ratio, height_ratio])
    size = (int(original.width / ratio), int(original.height / ratio))
    if size[0] == 0 or size[1] == 0:
        size = (1, 1)
    image_cache[png]['resized'] = \
        image_cache[png]['original'].resize(size, Image.ANTIALIAS)
    image_cache[png]['image'] = ImageTk.PhotoImage(
        image_cache[png]['resized'])
    return png

async def get_file(
        interface: Interface,
        file_type: FileType=FileType.png) -> Path:
    """Assemble file_name, compile if non-existent."""
    file_name = interface.get_filename(file_type)
    # TODO: check for naming madness with pages
    if not file_name.is_file():
        await compile_(interface, file_type)
    if not file_name.is_file():
        _ERR_CB("could not compile {}".format(file_name))
    return file_name

def midi_introspection():
    """Show contents of midi file in a readable format."""
    if len(sys.argv) != 2:
        print("usage: midi_introspection file")
        return
    midi = MidiFile()
    midi.open(sys.argv[1])
    midi.read()
    midi.close()

    for track in midi.tracks:
        print("\n\ntrack number {}".format(track.index))
        for event in track.events:
            print(repr(event))
