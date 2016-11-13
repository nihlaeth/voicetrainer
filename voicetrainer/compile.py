"""Compile lily exercise into png and midi."""
from typing import List, Tuple
from string import Template
from os import listdir
from os.path import isfile, join, realpath, dirname
from itertools import product
from asyncio import create_subprocess_exec, get_event_loop
from asyncio.subprocess import PIPE

# pylint: disable=invalid-name,bad-continuation
async def compile_ex(
        file_name: str,
        tempos: List[int],
        pitches: List[str],
        sounds: List[str]) -> List[Tuple[str, str]]:
    """Open exercise file, format, and compile with lilypond."""
    with open(file_name, "r") as f:
        exercise = Template(f.read())
    log = []
    if file_name.endswith('-midi.ly'):
        for tempo, pitch in product(tempos, pitches):
            proc = await create_subprocess_exec(
                'lilypond',
                '--loglevel=WARN',
                '--output={}-{}bpm-{}'.format(
                    file_name[:-8],  # minus '-midi.ly'
                    tempo,
                    pitch),
                '-',
                stdin=PIPE,
                stdout=PIPE,
                stderr=PIPE)
            outs, errs = await proc.communicate(str.encode(
                exercise.safe_substitute(
                    tempo=tempo,
                    pitch=pitch,
                    pitch_noheight=pitch[0])))
            log.append((bytes.decode(outs), bytes.decode(errs)))
    else:
        for pitch, sound in product(pitches, sounds):
            proc = await create_subprocess_exec(
                'lilypond',
                '--loglevel=WARN',
                '--format=png',
                '--png',
                '--output={}-{}-{}'.format(
                    file_name[:-3],  # minus '.ly'
                    pitch,
                    sound),
                '-',
                stdin=PIPE,
                stdout=PIPE,
                stderr=PIPE)
            outs, errs = await proc.communicate(str.encode(
                exercise.safe_substitute(
                    pitch=pitch,
                    pitch_noheight=pitch[0],
                    sound=sound)))
            log.append((bytes.decode(outs), bytes.decode(errs)))
    return log

async def compile_all(path: str) -> List[List[Tuple[str, str]]]:
    """Compile all exercises."""
    exercises = []
    logs = []
    for item in listdir(path):
        if isfile(join(path, item)) and item.endswith('.ly'):
            exercises.append(item)
    for ex in exercises:
        log = await compile_ex(
            join(path, ex),
            [i*10 for i in range(8, 16)],
            [note + octave for note, octave in product(
                list("cdefg"), [",", "", "'"])],
            ["Mi", "Na", "Noe", "Nu", "No"])
        logs.append(log)
    return logs

if __name__ == "__main__":
    loop = get_event_loop()
    result = loop.run_until_complete(
        compile_all(join(dirname(realpath(__file__)), "../exercises/")))
    loop.close()
    print(result)
