#!/usr/bin/env python
import distutils.core

distutils.core.setup(
    name='Chase Online Banking Agent',
    version='0.1.20130901',
    description='Interface for Chase Online Banking',
    author='Eric Pruitt',
    author_email='eric.pruitt@gmail.com',
    url='https://github.com/jameseric/coba',
    license='BSD',
    keywords='chase online banking',
    packages=['coba'],
    install_requires=['bs4', 'zope.testbrowser', 'mechanize'],
    scripts=['cobcli'],
)
