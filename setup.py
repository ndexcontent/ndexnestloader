#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""The setup script."""
import os
import re
from setuptools import setup, find_packages


with open(os.path.join('ndexnestloader', '__init__.py')) as ver_file:
    for line in ver_file:
        if line.startswith('__version__'):
            version=re.sub("'", "", line[line.index("'"):])

with open('README.rst') as readme_file:
    readme = readme_file.read()

with open('HISTORY.rst') as history_file:
    history = history_file.read()

requirements = ['ndex2>=3.6.0',
                'ndexutil',
                'requests',
                'tqdm']

setup_requirements = [ ]

test_requirements = [ ]

setup(
    author="Chris Churas",
    author_email='cchuras@ucsd.edu',
    classifiers=[
        'Development Status :: 2 - Pre-Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Natural Language :: English',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
    ],
    description="Loads NeST interactome subnetworks into NDEx",
    install_requires=requirements,
    license="MIT license",
    long_description=readme + '\n\n' + history,
    include_package_data=True,
    keywords='ndexnestloader',
    name='ndexnestloader',
    packages=find_packages(include=['ndexnestloader']),
    package_dir={'ndexnestloader': 'ndexnestloader'},
    package_data={'ndexnestloader': ['loadplan.json',
                                       'style.cx2']},
    scripts=[ 'ndexnestloader/ndexloadnestsubnetworks.py'],
    setup_requires=setup_requirements,
    test_suite='tests',
    tests_require=test_requirements,
    url='https://github.com/ndexcontent/ndexnestloader',
    version=version,
    zip_safe=False,
)
