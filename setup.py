#!/usr/bin/env python
from setuptools import setup, find_packages

setup(
    name='voicetrainer',
    version='1.0',
    description='midi voice exercises',
    author='nihlaeth',
    author_email='info@nihlaeth.nl',
    packages=find_packages(),
    package_data={'voicetrainer': ['exercises/*']})
