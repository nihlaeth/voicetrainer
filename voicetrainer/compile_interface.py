"""Interface between application data and compiled files."""
from pathlib import Path
from enum import Enum
from typing import List
from string import Template

class FileType(Enum):

    """File types that we compile to and from."""
    lily = 1
    midi = 2
    png = 3
    pdf = 4

class Exercise:

    """Filenames and compile flags for exercises."""

    # pylint: disable=too-many-arguments
    def __init__(
            self,
            data_path: Path,
            name: str,
            pitch: str='c',
            bpm: int=140,
            sound: str='Mi') -> None:
        self.data_path = data_path
        self.name = name
        self.pitch = pitch
        self.bpm = bpm
        self.sound = sound

    def get_filename(self, file_type: FileType):
        """Return full path."""
        if file_type == FileType.lily:
            return self.data_path.joinpath("{}.ly".format(self.name))
        if file_type == FileType.midi:
            return self.data_path.joinpath("{}-{}bpm-{}.midi".format(
                self.name, self.bpm, self.pitch))
        if file_type == FileType.png:
            return self.data_path.joinpath("{}-{}-{}.png".format(
                self.name, self.pitch, self.sound))
        if file_type == FileType.pdf:
            return self.data_path.joinpath("{}-{}-{}.pdf".format(
                self.name, self.pitch, self.sound))

    def get_lilypond_options(self, file_type: FileType) -> List[str]:
        """Return list of lilypond cli options to compile file_type."""
        partial_name = self.data_path.joinpath(
            self.get_filename(file_type).stem)
        options = [
            "lilypond",
            "--loglevel=WARN",
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
        return lily_code.safe_substitute(
            midion=midion,
            midioff=midioff,
            sheeton=sheeton,
            sheetoff=sheetoff,
            tempo=self.bpm,
            pitch=self.pitch,
            pitch_noheight=self.pitch[0],
            sound=self.sound)
