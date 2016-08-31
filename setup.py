#!/usr/bin/env python
"""Setup file for cassandra-toolbox.

Execute `setup.py install` to install the latest cassandra-toolbox scripts
into your environment.  You can also execute `setup.py sdist` or
`setup.py bdist` to generate source and binary distributions.
"""
import glob
from setuptools import find_packages, setup
import warnings


def get_readme():
    """Get the README from the current directory.

    **Args:**
        None

    **Returns:**
        str:    String is empty if no README file exists.
    """
    all_readmes = sorted(glob.glob("README*"))
    if len(all_readmes) > 1:
        warnings.warn(
            "There seems to be more than one README in this directory."
            "Choosing the first in lexicographic order."
        )
    if len(all_readmes) > 0:
        return open(all_readmes[0], 'r').read()

    warnings.warn("There doesn't seem to be a README in this directory.")
    return ""


def parse_requirements(filename):
    """Parse a requirements file .

    Parser ignores comments and -r inclusions of other files.

    **Args:**
        filename (str):     Path of the requirements file to be parsed

    **Returns:**
        list<str>:          List of PKG=VERSION strings
    """
    reqs = []
    with open(filename, 'r') as f:
        for line in f:
            hash_idx = line.find('#')
            if hash_idx >= 0:
                line = line[:hash_idx]
            line = line.strip()
            reqs.append(line)
    return reqs


setup(
    name="cassandra-toolbox",
    version='0.1.3',
    author="Knewton Database Team",
    author_email="database@knewton.com",
    license="Apache2",
    url="https://github.com/Knewton/cassandra-toolbox",
    packages=find_packages(),
    install_requires=parse_requirements('requirements.txt'),
    include_package_data=True,
    scripts=[
        'cassandra-toolbox/cassandra-stat',
        'cassandra-toolbox/cassandra-tracing'
    ],
    description=(
        "A suite of tools for Cassandra - A highly scalable distributed "
        "NoSQL datastore."
    ),
    long_description="\n" + get_readme()
)
