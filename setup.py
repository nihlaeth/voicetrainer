"""Installation script for voicetrainer."""
from setuptools import setup, find_packages

setup(
    name='voicetrainer',
    version='1.0',
    description='midi voice exercises',
    author='nihlaeth',
    author_email='info@nihlaeth.nl',
    packages=find_packages(),
    package_data={'voicetrainer': ['exercises/*']},
    entry_points={
        'gui_scripts': [
            'voicetrainer = voicetrainer.gui:start']})
