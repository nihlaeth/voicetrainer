"""Compile lily exercise into png and midi."""
from typing import List, Tuple
from string import Template
from os import listdir
from os.path import isfile, join, realpath, dirname
from itertools import product
from subprocess import Popen, PIPE, TimeoutExpired

def compile_ex(
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
            with Popen(
                [
                    'lilypond',
                    '--output={}-{}bmp-{}'.format(
                        file_name[:-8],  # minus '-midi.ly'
                        tempo,
                        pitch),
                    '-'],
                stdin=PIPE,
                stdout=PIPE,
                stderr=PIPE,
                universal_newlines=True) as proc:
                try:
                    outs, errs = proc.communicate(exercise.safe_substitute(
                        tempo=tempo,
                        pitch=pitch,
                        pitch_noheight=pitch[0]))
                except TimeoutExpired:
                    proc.kill()
                    outs, errs = proc.communicate()
                log.append((outs, errs))
                if proc.returncode != 0:
                    print(errs)
                print(outs)
                print(errs)
    else:
        for pitch, sound in product(pitches, sounds):
            with Popen(
                [
                    'lilypond',
                    '--format=png',
                    '--png',
                    '--output={}-{}-{}'.format(
                        file_name[:-3],  # minus '.ly'
                        pitch,
                        sound),
                    '-'],
                stdin=PIPE,
                stdout=PIPE,
                stderr=PIPE,
                universal_newlines=True) as proc:
                try:
                    outs, errs = proc.communicate(exercise.safe_substitute(
                        pitch=pitch,
                        pitch_noheight=pitch[0],
                        sound=sound))
                except TimeoutExpired:
                    proc.kill()
                    outs, errs = proc.communicate()
                log.append((outs, errs))
                if proc.returncode != 0:
                    print(errs)
                print(outs)
                print(errs)
    return log

def compile_all(path: str) -> None:
    """Compile all exercises."""
    exercises = []
    for item in listdir(path):
        if isfile(join(path, item)) and item.endswith('.ly'):
            exercises.append(item)
    for ex in exercises:
        compile_ex(
            join(path, ex),
            [i*10 for i in range(8, 16)],
            [note + octave for note, octave in product(
                list("cdefg"), [",", "", "'"])],
            ["Mi", "Na", "Noe", "Nu", "No"])

if __name__ == "__main__":
    compile_all(join(dirname(realpath(__file__)), "../exercises/"))
