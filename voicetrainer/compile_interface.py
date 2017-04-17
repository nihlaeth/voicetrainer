"""Interface between application data and compiled files."""
from pathlib import Path
from enum import Enum
from typing import List
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

class Interface:

    """Filenames and compile flags for exercises."""

    has_start_measure = False
    has_instruments = False

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
            midi_instruments=None,
            instrument_velocities=None,
            sheet_instruments=None) -> None:
        self.data_path = data_path
        self.include_path = include_path
        self.name = name
        self.pitch = pitch
        self.bpm = bpm
        self.sound = sound
        self.page = page
        self.start_measure = start_measure
        self.velocity = velocity
        self.midi_instruments = {} if midi_instruments is None else midi_instruments
        self.instrument_velocities = {instrument: 0 for instrument in self.midi_instruments}
        if instrument_velocities is not None:
            self.instrument_velocities.update(instrument_velocities)
        self.sheet_instruments = {} if sheet_instruments is None else midi_instruments
        self.config = self.get_config()

    def get_filename(self, file_type: FileType, compiling: bool=False):
        """Return full path."""
        naming_elements = [self.name]
        extension = "ly"
        if file_type == FileType.midi:
            extension = "midi"
            naming_elements.append("{}bpm".format(self.bpm))
            naming_elements.append("{}".format(self.pitch))
            naming_elements.append("velocity{}".format(
                self.velocity if not compiling else 0))
            if self.has_instruments:
                instruments = []
                for instrument in self.midi_instruments:
                    if self.midi_instruments[instrument]:
                        instruments.append("{}-{}".format(
                            instrument,
                            self.instrument_velocities[instrument]))
                naming_elements.append('-'.join(instruments))
            if self.has_start_measure:
                naming_elements.append("from-measure-{}".format(
                    self.start_measure if not compiling else 1))
        if file_type == FileType.png:
            extension = "png"
            naming_elements.append("{}".format(self.pitch))
            if self.has_instruments:
                naming_elements.append('-'.join(
                    [instrument for instrument in self.sheet_instruments if \
                    self.sheet_instruments[instrument]]))
            if 'sound' in self.config:
                naming_elements.append("{}".format(self.sound))
            if 'pages' in self.config and not compiling:
                num_pages = int(self.config['pages'])
                if num_pages > 1:
                    naming_elements.append("page{}".format(self.page))
        if file_type == FileType.pdf:
            extension = "pdf"
            naming_elements.append("{}".format(self.pitch))
            if self.has_instruments:
                naming_elements.append('-'.join(
                    [instrument for instrument in self.sheet_instruments if \
                    self.sheet_instruments[instrument]]))
            if 'sound' in self.config:
                naming_elements.append("{}".format(self.sound))
        return self.data_path.joinpath("{}.{}".format(
            '-'.join(naming_elements), extension))

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
        lily_code = self.get_raw_lily_code()
        ignore_count = 0
        keep_data = []
        for line in lily_code.split('\n'):
            tokens = tokenize(line)
            replace_strings = {
                'voicetrainerTempo': self.bpm,
                'voicetrainerKey': self.pitch,
                'voicetrainerSound': '"{}"'.format(self.sound)}
            if (
                    len(tokens) > 2 and
                    tokens[0] in replace_strings and
                    tokens[1] == '='):
                keep_data.append("{} = {}".format(
                    tokens[0],
                    replace_strings[tokens[0]]))
                continue

            if (file_type == FileType.png or file_type == FileType.pdf) and \
                    len(tokens) > 2 and \
                    tokens[0] == '%' and \
                    tokens[1] == 'midionly':
                ignore_count += 1 if tokens[2] == 'start' else -1
            if (file_type == FileType.png or file_type == FileType.pdf) and \
                    self.has_instruments and len(tokens) > 3 and \
                    tokens[0] == '%' and \
                    tokens[1] == 'instrument':
                if not self.sheet_instruments[tokens[3]]:
                    ignore_count += 1 if tokens[2] == 'start' else -1
            if file_type == FileType.midi and \
                    len(tokens) > 2 and \
                    tokens[0] == '%' and \
                    tokens[1] == 'sheetonly':
                ignore_count += 1 if tokens[2] == 'start' else -1
            if file_type == FileType.midi and \
                    self.has_instruments and len(tokens) > 3 and \
                    tokens[0] == '%' and \
                    tokens[1] == 'instrument':
                if not self.midi_instruments[tokens[3]]:
                    ignore_count += 1 if tokens[2] == 'start' else -1
            if ignore_count < 1:
                keep_data.append(line)
        return '\n'.join(keep_data)

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
            if len(tokens) > 2 and \
                    tokens[0].startswith('voicetrainer') and \
                    tokens[1] == '=':
                if tokens[0] == 'voicetrainerTempo':
                    data['tempo'] = tokens[2]
                elif tokens[0] == 'voicetrainerKey':
                    data['key'] = tokens[2]
                elif tokens[0] == 'voicetrainerSound':
                    data['sound'] = tokens[2]
        return data

class Exercise(Interface):

    """Exercise interface."""

class Song(Interface):

    """Song interface."""

    has_start_measure = True
    has_instruments = True
