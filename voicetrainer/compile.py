"""Compile lily code into png and midi."""
from typing import List, Tuple
from pathlib import Path
from itertools import product
from asyncio import create_subprocess_exec, get_event_loop
from asyncio.subprocess import PIPE
from pkg_resources import resource_filename, Requirement, cleanup_resources

from voicetrainer.midi import (
    MidiFile, MidiTrack, DeltaTime, MidiEvent, getNumbersAsList)
from voicetrainer.compile_interface import FileType, Interface, Exercise, Song

def get_measure_num(time_changes, total_ticks, ticks_per_quarter_note):
    """Get current measure number."""
    measure = 1
    curr_tick = 0
    curr_quarts_m = 4
    # pylint: disable=consider-using-enumerate
    for i in range(len(time_changes)):
        stop = False
        next_tick, next_quarts_m = time_changes[i]
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

# pylint: disable=invalid-name,bad-continuation
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
            interface.has_start_measure and interface.start_measure > 1:
        await create_clipped_midi(interface)
    return (bytes.decode(outs), bytes.decode(errs))

def midi_generator(midi: MidiFile) -> Tuple[int, DeltaTime, MidiEvent]:
    """Iterate over midi events."""
    for i, track in enumerate(midi.tracks):
        delta_time = None
        for event in track.events:
            if event.isDeltaTime():
                delta_time = event
            else:
                yield (i, delta_time, event)

# pylint: disable=too-few-public-methods
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


async def create_clipped_midi(interface: Interface):
    """Start midi from start_measure, with events intact."""
    midi = MidiFile()
    midi.open(str(interface.get_filename(
        FileType.midi, compiling=True)))
    midi.read()
    midi.close()
    ticks_per_quarter_note = midi.ticksPerQuarterNote
    # collect time_changes
    time_changes = []
    total_ticks = []
    async for track_num, delta_time, event in MidiIterator(midi):
        if len(total_ticks) == track_num:
            total_ticks.append(0)
        total_ticks[track_num] += delta_time.time
        if event.type == "TIME_SIGNATURE":
            t_signature = getNumbersAsList(event.data)
            num = t_signature[0]
            div = pow(2, t_signature[1])
            time_changes.append(
                (total_ticks[track_num], (num / div) * 4))
    # construct new midi
    total_ticks = []
    new_midi = MidiFile()
    new_midi.ticksPerQuarterNote = midi.ticksPerQuarterNote
    async for track_num, delta_time, event in MidiIterator(midi):
        if len(total_ticks) == track_num:
            total_ticks.append(0)
            new_midi.tracks.append(MidiTrack(track_num))
        total_ticks[track_num] += delta_time.time
        measure = get_measure_num(
            time_changes,
            total_ticks[track_num],
            ticks_per_quarter_note)
        if event.type in ['NOTE_ON', 'NOTE_OFF'] and \
                measure < interface.start_measure:
            continue
        else:
            if measure < interface.start_measure:
                # insert event with timedelta 0
                delta_time.time = 0
            new_midi.tracks[track_num].events.append(delta_time)
            new_midi.tracks[track_num].events.append(event)
    for track in new_midi.tracks:
        track.updateEvents()
    print(new_midi)
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

if __name__ == '__main__':
    data_path_ = Path(resource_filename(
        Requirement.parse("voicetrainer"),
        'voicetrainer/songs'))
    include_path_ = Path(resource_filename(
        Requirement.parse("voicetrainer"),
        'voicetrainer/include'))
    interface_ = Song(
        data_path_,
        include_path_,
        name='test_song',
        start_measure=2)
    loop = get_event_loop()
    loop.run_until_complete(compile_(interface_, FileType.midi))
    loop.close()
    cleanup_resources()
