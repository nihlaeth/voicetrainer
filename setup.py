"""Installation script for voicetrainer."""
from setuptools import setup, find_packages

setup(
    name='voicetrainer',
    version='1.0',
    description='midi voice exercises',
    author='nihlaeth',
    author_email='info@nihlaeth.nl',
    python_requires='>=3.5.2',
    packages=find_packages(),
    install_requires=['pillow'],
    package_data={'voicetrainer': ['reset.midi']},
    entry_points={
        'gui_scripts': [
            'voicetrainer = voicetrainer.gui:start']})
