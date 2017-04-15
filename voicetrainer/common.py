"""Stuff that I didn't know a better place for."""
from itertools import product

PITCH_LIST = tuple((note + octave for octave, note in product(
    (',', '', '\''),
    tuple("cdefgab"))))

SOUND_LIST = ("Mi", "Na", "Noe", "Nu", "No")
