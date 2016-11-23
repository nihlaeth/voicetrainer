"""Compile lily exercise into png and midi."""
from typing import List, Tuple
from string import Template
from pathlib import Path
from itertools import product
from asyncio import create_subprocess_exec, get_event_loop
from asyncio.subprocess import PIPE
from pkg_resources import resource_filename, Requirement, cleanup_resources

# pylint: disable=invalid-name,bad-continuation
async def compile_ex(
        file_name: Path,
        tempos: List[int],
        pitches: List[str],
        sounds: List[str],
        midi: bool=False) -> List[Tuple[str, str]]:
    """Open exercise file, format, and compile with lilypond."""
    exercise = Template(file_name.read_text())
    log = []
    if midi:
        for tempo, pitch in product(tempos, pitches):
            output_filename = file_name.parents[0].joinpath(
                "{}-bpm{}-{}".format(file_name.stem, tempo, pitch))
            proc = await create_subprocess_exec(
                'lilypond',
                '--loglevel=WARN',
                '--output={}'.format(output_filename),
                '-',
                stdin=PIPE,
                stdout=PIPE,
                stderr=PIPE)
            outs, errs = await proc.communicate(str.encode(
                exercise.safe_substitute(
                    midion='',
                    midioff='',
                    sheeton='%{',
                    sheetoff='%}',
                    tempo=tempo,
                    pitch=pitch,
                    pitch_noheight=pitch[0])))
            log.append((bytes.decode(outs), bytes.decode(errs)))
    else:
        for pitch, sound in product(pitches, sounds):
            output_filename = file_name.parents[0].joinpath(
                "{}-{}-{}".format(file_name.stem, pitch, sound))
            proc = await create_subprocess_exec(
                'lilypond',
                '--loglevel=WARN',
                '--format=png',
                '--png',
                '--output={}'.format(output_filename),
                '-',
                stdin=PIPE,
                stdout=PIPE,
                stderr=PIPE)
            outs, errs = await proc.communicate(str.encode(
                exercise.safe_substitute(
                    midion='%{',
                    midioff='%}',
                    sheeton='',
                    sheetoff='',
                    pitch=pitch,
                    pitch_noheight=pitch[0],
                    sound=sound)))
            log.append((bytes.decode(outs), bytes.decode(errs)))
    return log

async def compile_all(path: Path) -> List[List[Tuple[str, str]]]:
    """Compile all exercises."""
    if not path.is_dir():
        raise Exception('{} is not a directory'.format(path))
    logs = []
    for exercise in path.glob('*.ly'):
        for midi in [True, False]:
            log = await compile_ex(
                path.joinpath(exercise),
                [i*10 for i in range(8, 17)],
                [note + octave for note, octave in product(
                    list("cdefg"), [",", "", "'"])],
                ["Mi", "Na", "Noe", "Nu", "No"],
                midi)
            logs.append(log)
    return logs

if __name__ == "__main__":
    loop = get_event_loop()
    data_path = Path(resource_filename(
        Requirement.parse("voicetrainer"),
        'voicetrainer/exercises'))
    try:
        result = loop.run_until_complete(compile_all(data_path))
    finally:
        cleanup_resources()
        loop.close()
        print(result)
