"""Installation script for voicetrainer."""
from setuptools import setup, find_packages

setup(
    name='voicetrainer',
    version='1.0',
    description='midi voice exercises',
    author='nihlaeth',
    author_email='info@nihlaeth.nl',
    python_requires='>=3.5.1',
    packages=find_packages(),
    install_requires=['pillow'],
    entry_points={
        'gui_scripts': [
            'voicetrainer = voicetrainer.gui:start']})
