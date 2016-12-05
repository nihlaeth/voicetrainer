"""Compile lily code into png and midi."""
from typing import List, Tuple
from pathlib import Path
from itertools import product
from asyncio import create_subprocess_exec
from asyncio.subprocess import PIPE

from music21 import converter

from voicetrainer.compile_interface import FileType, Interface, Exercise

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
        # create clipped midi
        stream = converter.parse(
            str(interface.get_filename(FileType.midi, compiling=True)))
        clipped_stream = stream.measures(
            numberStart=interface.start_measure,
            numberEnd=None,
            gatherSpanners=True)
        clipped_stream.write(
            'midi', str(interface.get_filename(FileType.midi)))
    return (bytes.decode(outs), bytes.decode(errs))

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
