#!/usr/bin/env python
import distutils.core

# Attempt to import setuptools so distutils is monkey-patched. This will
# eliminate the "Unknown distribution option" warning caused by distutils' lack
# of support for the install_requires option.
try:
    import setuptools
except ImportError:
    pass

distutils.core.setup(
    name='Chase Online Banking Agent',
    version='0.3.0',
    description='Interface for Chase Online Banking',
    author='Eric Pruitt',
    author_email='eric.pruitt@gmail.com',
    url='https://github.com/ericpruitt/coba',
    license='BSD',
    keywords='chase online banking',
    packages=['coba'],
    install_requires=[
        'beautifulsoup4',
        'zope.testbrowser >=4.0, <5.0',
        'mechanize >= 0.2, < 0.3'
    ],
    scripts=['cobcli'],
)
