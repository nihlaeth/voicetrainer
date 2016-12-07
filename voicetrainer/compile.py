"""Compile lily code into png and midi."""
from typing import List, Tuple
from pathlib import Path
from itertools import product
from asyncio import create_subprocess_exec, get_event_loop
from asyncio.subprocess import PIPE
from pkg_resources import resource_filename, Requirement, cleanup_resources

from voicetrainer.midi import MidiFile, MidiTrack, getNumbersAsList
from voicetrainer.compile_interface import FileType, Interface, Exercise, Song

def get_measure_num(time_changes, total_ticks, ticks_per_quarter_note):
    """Get current measure number."""
    measure = 1
    curr_tick = 0
    curr_quarts_m = 4
    for i in range(len(time_changes)):
        stop = False
        next_tick, next_quarts_m = time_changes[i]
        if next_tick == 0:
            # overwrite default quarts_per_minute
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
        create_clipped_midi(interface)
    return (bytes.decode(outs), bytes.decode(errs))

def create_clipped_midi(interface: Interface):
    """Start midi from start_measure, with events intact."""
    # TODO: refactor this - maybe an asynce iterator will do?
    midi = MidiFile()
    midi.open(str(interface.get_filename(
        FileType.midi, compiling=True)))
    midi.read()
    midi.close()
    ticks_per_quarter_note = midi.ticksPerQuarterNote
    # collect time_changes
    time_changes = []
    for track in midi.tracks:
        total_ticks = 0
        for event in track.events:
            if event.isDeltaTime():
                total_ticks += event.time
            elif event.type == "TIME_SIGNATURE":
                t_signature = getNumbersAsList(event.data)
                num = t_signature[0]
                div = pow(2, t_signature[1])
                time_changes.append(
                    (total_ticks, (num / div) * 4))
    # construct new midi
    new_midi = MidiFile()
    for i, track in enumerate(midi.tracks):
        total_ticks = 0
        new_track = MidiTrack(i)
        measure = 1
        for c, event in enumerate(track.events):
            if event.isDeltaTime():
                total_ticks += event.time
                measure = get_measure_num(
                    time_changes,
                    total_ticks,
                    ticks_per_quarter_note)
                # peek at next event
                if c + 1 == len(track.events):
                    new_track.events.append(event)
                    continue
                next_event = track.events[c + 1]
                if next_event.type in [
                        'NOTE_ON', 'NOTE_OFF'] and \
                        measure < interface.start_measure:
                    continue
                else:
                    new_track.events.append(event)
            elif event.type in ['NOTE_ON', 'NOTE_OFF']:
                if measure >= interface.start_measure:
                    new_track.events.append(event)
            else:
                new_track.events.append(event)
        new_track.updateEvents()
        new_midi.tracks.append(new_track)
    # print(new_midi)
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
    data_path = Path(resource_filename(
        Requirement.parse("voicetrainer"),
        'voicetrainer/songs'))
    include_path = Path(resource_filename(
        Requirement.parse("voicetrainer"),
        'voicetrainer/include'))
    interface = Song(
        data_path,
        include_path,
        name='test_song',
        start_measure=2)
    loop = get_event_loop()
    loop.run_until_complete(compile_(interface, FileType.midi))
    cleanup_resources()
