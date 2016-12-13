"""Stuff that I didn't know a better place for."""
from itertools import product

PITCH_LIST = (note + octave for octave, note in product(
    (',', '', '\''),
    tuple("cdefgab")))
