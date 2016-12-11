"""Compile lily code into png and midi."""
from typing import List, Tuple
from pathlib import Path
from itertools import product
from asyncio import create_subprocess_exec
from asyncio.subprocess import PIPE

from voicetrainer.midi import (
    MidiFile, MidiTrack, DeltaTime, MidiEvent, get_numbers_as_list)
from voicetrainer.compile_interface import FileType, Interface, Exercise

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

async def compile_(interface: Interface, file_type: FileType) -> Tuple[str, str]:
    """Open interface file, format, and compile with lilypond."""
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
    return (bytes.decode(outs), bytes.decode(errs))

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

async  def compile_all(path: Path, include_path: Path) -> List[Tuple[str, str]]:
    """Compile all exercises."""
    if not path.is_dir():
        raise Exception('{} is not a directory'.format(path))
    log = []
    for file_name in path.glob('*.ly'):
        variables = product(
            [FileType.midi, FileType.png],
            [note + octave for note, octave in product(
                list("cdefg"), [",", "", "'"])],
            [i*10 for i in range(8, 17)],
            ["Mi", "Na", "Noe", "Nu", "No"])
        for combo in variables:
            exercise = Exercise(
                path,
                include_path,
                name=file_name.stem,
                pitch=combo[1],
                bpm=combo[2],
                sound=combo[3])
            log.append(await compile_(exercise, combo[0]))
    return log
