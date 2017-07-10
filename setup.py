# -*- coding: utf-8 -*-
from setuptools import setup, find_packages

setup(
    name='mmeowlink',
    version='0.11.1',
    description='Driver layer for communicating with Medtronic pumps over a variety of radios',
    packages=find_packages(),
    include_package_data=True,
    author='Oskar Pearson',
    author_email='oskar+mmeowlink-pypi@deckle.co.uk',
    license='GPL',
    url='https://github.com/oskarpearson/mmeowlink',
    install_requires=[
      'argcomplete',
      'decocare',
      'python-dateutil',
      'pyserial'
    ],
    scripts = [
      'bin/mmeowlink-bolus.py',
      'bin/mmeowlink-any-pump-comms.py',
      'bin/mmeowlink-rf-dump.py',
      'bin/mmeowlink-send.py',
      'bin/mmtune.py'
    ],
    classifiers = [
      'Development Status :: 3 - Alpha',
      'Intended Audience :: Developers',
      'Intended Audience :: Science/Research',
      'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
      'Programming Language :: Python',
      'Topic :: Scientific/Engineering',
      'Topic :: Software Development :: Libraries',
    ],
    zip_safe=False
)
