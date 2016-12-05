"""Compile lily exercise into png and midi."""
from typing import List, Tuple
from pathlib import Path
from itertools import product
from asyncio import create_subprocess_exec, get_event_loop
from asyncio.subprocess import PIPE
from pkg_resources import resource_filename, Requirement, cleanup_resources

from voicetrainer.compile_interface import FileType, Exercise

# pylint: disable=invalid-name,bad-continuation
async def compile_(exercise: Exercise, file_type: FileType) -> Tuple[str, str]:
    """Open exercise file, format, and compile with lilypond."""
    proc = await create_subprocess_exec(
        *exercise.get_lilypond_options(file_type),
        stdin=PIPE,
        stdout=PIPE,
        stderr=PIPE)
    outs, errs = await proc.communicate(str.encode(
        exercise.get_final_lily_code(file_type)))
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
                file_name.stem,
                combo[1],
                combo[2],
                combo[3])
            log.append(await compile_(exercise, combo[0]))
    return log
