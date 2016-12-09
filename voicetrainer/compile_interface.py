"""Interface between application data and compiled files."""
from pathlib import Path
from enum import Enum
from typing import List
from string import Template
import re

def tokenize(text):
    """Break down text into a list of words."""
    return re.findall(r"\\?[%=:{}()]|\\?[a-zA-Z_\-0-9,.']+", text)

class FileType(Enum):

    """File types that we compile to and from."""
    lily = 1
    midi = 2
    png = 3
    pdf = 4

# pylint: disable=too-many-instance-attributes
class Interface:

    """Filenames and compile flags for exercises."""

    has_pages = False
    has_sound = False
    has_start_measure = False
    has_instruments = False

    # pylint: disable=too-many-arguments
    def __init__(
            self,
            data_path: Path,
            include_path: Path,
            name: str,
            pitch: str='c',
            bpm: int=140,
            sound: str='Mi',
            page: int=1,
            start_measure: int=1,
            velocity: int=0,
            instruments=None) -> None:
        self.data_path = data_path
        self.include_path = include_path
        self.name = name
        self.pitch = pitch
        self.bpm = bpm
        self.sound = sound
        self.page = page
        self.start_measure = start_measure
        self.velocity = velocity
        self.instruments = {} if instruments is None else instruments

    def get_filename(self, file_type: FileType, compiling: bool=False):
        """Return full path."""
        if file_type == FileType.lily:
            return self.data_path.joinpath("{}.ly".format(self.name))
        if file_type == FileType.midi:
            measure = "-from-measure-{}".format(
                self.start_measure if not compiling else 1) if \
                    self.has_start_measure else ""
            velocity = "velocity{}".format(
                self.velocity if not compiling else 0)
            instruments = "-{}".format('-'.join(
                [instrument for instrument in self.instruments if \
                    self.instruments[instrument]])) if \
                    self.has_instruments else ""
            return self.data_path.joinpath(
                "{}-{}bpm-{}-{}{}{}.midi".format(
                    self.name,
                    self.bpm,
                    self.pitch,
                    velocity,
                    instruments,
                    measure))
        if file_type == FileType.png:
            sound = "-{}".format(self.sound) if self.has_sound else ""
            config = self.get_config()
            if 'pages' in config:
                num_pages = int(config['pages'])
            else:
                num_pages = 1
            page = "-page{}".format(
                self.page) if self.has_pages and num_pages > 1 and \
                    not compiling else ""
            return self.data_path.joinpath("{}-{}{}{}.png".format(
                self.name, self.pitch, sound, page))
        if file_type == FileType.pdf:
            sound = "-{}".format(self.sound) if self.has_sound else ""
            return self.data_path.joinpath("{}-{}{}.pdf".format(
                self.name, self.pitch, sound))

    def get_lilypond_options(self, file_type: FileType) -> List[str]:
        """Return list of lilypond cli options to compile file_type."""
        partial_name = self.data_path.joinpath(
            self.get_filename(file_type, compiling=True).stem)
        options = [
            "lilypond",
            "--loglevel=WARN",
            "--include={}".format(self.include_path),
            "--output={}".format(partial_name)]
        if file_type == FileType.lily:
            return
        if file_type == FileType.midi:
            pass
        if file_type == FileType.png:
            options.append("--format=png")
            options.append("--png")
        if file_type == FileType.pdf:
            pass
        options.append("-")
        return options

    def get_raw_lily_code(self) -> str:
        """Raw content of lily file."""
        return self.get_filename(FileType.lily).read_text()

    def get_final_lily_code(self, file_type: FileType) -> str:
        """Lily code with substitutions made."""
        lily_code = Template(self.get_raw_lily_code())
        if file_type == FileType.midi:
            midion = ""
            midioff = ""
            sheeton = "%{"
            sheetoff = "%}"
        else:
            midion = "%{"
            midioff = "%}"
            sheeton = ""
            sheetoff = ""
        if self.has_sound:
            s_lily_code = lily_code.safe_substitute(
                midion=midion,
                midioff=midioff,
                sheeton=sheeton,
                sheetoff=sheetoff,
                tempo=self.bpm,
                pitch=self.pitch,
                pitch_noheight=self.pitch[0],
                sound=self.sound)
        else:
            s_lily_code = lily_code.safe_substitute(
                midion=midion,
                midioff=midioff,
                sheeton=sheeton,
                sheetoff=sheetoff,
                tempo=self.bpm,
                pitch=self.pitch,
                pitch_noheight=self.pitch[0])
        if self.has_instruments:
            ignore_count = 0
            keep_data = []
            for line in s_lily_code.split('\n'):
                tokens = tokenize(line)
                if len(tokens) > 3 and \
                        tokens[0] == '%' and \
                        tokens[1] == 'instrument':
                    if not self.instruments[tokens[3]]:
                        ignore_count += 1 if tokens[2] == 'start' else -1
                if ignore_count < 1:
                    keep_data.append(line)
            s_lily_code = '\n'.join(keep_data)
        return s_lily_code


    def get_config(self):
        """Extract config from lily code."""
        lily = self.get_raw_lily_code().split('\n')
        data = {}
        data['instruments'] = []
        for line in lily:
            tokens = tokenize(line)
            # read config from comments
            if len(tokens) > 5 and \
                    tokens[0] == '%' and \
                    tokens[1] == 'voicetrainer' and \
                    tokens[2] == ':' and\
                    tokens[4] == '=':
                if tokens[3] not in data:
                    data[tokens[3]] = tokens[5]
            if len(tokens) > 3 and \
                    tokens[0] == '%' and \
                    tokens[1] == 'instrument' and \
                    tokens[2] == 'start':
                if tokens[3] not in data['instruments']:
                    data['instruments'].append(tokens[3])
            # extract key
            if '\\transpose' in tokens:
                index_transpose = tokens.index('\\transpose')
                if 'key' not in data and len(tokens) > index_transpose + 1:
                    data['key'] = tokens[index_transpose + 1]
        return data

class Exercise(Interface):

    """Exercise interface."""

    has_pages = False
    has_sound = True
    has_start_measure = False

class Song(Interface):

    """Song interface."""

    has_pages = True
    has_sound = False
    has_start_measure = True
    has_instruments = True
