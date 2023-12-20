====================================
NDEx NeST SubNetworks Content Loader
====================================


.. image:: https://img.shields.io/pypi/v/ndexnestloader.svg
        :target: https://pypi.python.org/pypi/ndexnestloader

.. image:: https://api.travis-ci.com/ndexcontent/ndexnestloader.svg?branch=main
        :target: https://app.travis-ci.com/ndexcontent/ndexnestloader

.. image:: https://readthedocs.org/projects/ndexnestloader/badge/?version=latest
        :target: https://ndexnestloader.readthedocs.io/en/latest/?badge=latest
        :alt: Documentation Status


Extracts Nested Systems in Tumors NeST_ subnetworks from `NeST Map - Main Model`_ and
loads them as new networks in NDEx_

Loads NDEx NeST SubNetworks Content Loader data into NDEx (http://ndexbio.org).
This is done by doing the following:

1) Load the NeST Map - Main Model as specified by ``--nest``
   https://www.ndexbio.org/viewer/networks/9a8f5326-aa6e-11ea-aaef-0ac135e8bacf

2) Load IAS_score.tsv file from url or path specified by ``--ias_score``

3) Find all **named**, assemblies (nodes) that have `Annotation` with a name
   that does not start with ``NEST:`` and have --maxsize genes or less in `Gene`
   attribute

4) For each **named** assembly create subnetwork by extracting edges from
   IAS_score.tsv file that pertain to proteins in `Genes` attribute
   and use the name in `Annotation` attribute for network name

5) Apply a default style to network, as well as set description,
   `version, reference, Prov:generatedBy, Prov:derivedFrom` fields


* Free software: MIT license
* Documentation: https://ndexnestloader.readthedocs.io.



Dependencies
------------

* `ndex2 <https://pypi.org/project/ndex2>`_
* `ndexutil <https://pypi.org/project/ndexutil>`_

Compatibility
-------------

* Python 3.8+

Installation
------------

.. code-block::

   git clone https://github.com/ndexcontent/ndexnestloader
   cd ndexnestloader
   make dist
   pip install dist/ndexloadnestsubnetworks*whl


Run **make** command with no arguments to see other build/deploy options including creation of Docker image 

.. code-block::

   make

Output:

.. code-block::

   clean                remove all build, test, coverage and Python artifacts
   clean-build          remove build artifacts
   clean-pyc            remove Python file artifacts
   clean-test           remove test and coverage artifacts
   lint                 check style with flake8
   test                 run tests quickly with the default Python
   test-all             run tests on every Python version with tox
   coverage             check code coverage quickly with the default Python
   docs                 generate Sphinx HTML documentation, including API docs
   servedocs            compile the docs watching for changes
   testrelease          package and upload a TEST release
   release              package and upload a release
   dist                 builds source and wheel package
   install              install the package to the active Python's site-packages
   dockerbuild          build docker image and store in local repository
   dockerpush           push image to dockerhub


Configuration
-------------

The **ndexloadnestsubnetworks.py** requires a configuration file in the following format be created.
The default path for this configuration is :code:`~/.ndexutils.conf` but can be overridden with
:code:`--conf` flag.

**Format of configuration file**

.. code-block::

    [<value in --profile (default ndexnestloader)>]

    user = <NDEx username>
    password = <NDEx password>
    server = <NDEx server(omit http) ie public.ndexbio.org>

**Example configuration file**

.. code-block::

    [ndexnestloader_dev]

    user = joe123
    password = somepassword123
    server = dev.ndexbio.org


Needed files
------------

**TODO:** Add description of needed files


Usage
-----

For information invoke :code:`ndexloadnestsubnetworks.py -h`

**Example usage**

**TODO:** Add information about example usage

.. code-block::

   ndexloadnestsubnetworks.py # TODO Add other needed arguments here


Via Docker
~~~~~~~~~~~~~~~~~~~~~~

**Example usage**

**TODO:** Add information about example usage


.. code-block::

   Coming soon...


Credits
-------

This package was created with Cookiecutter_ and the `audreyr/cookiecutter-pypackage`_ project template.

.. _Cookiecutter: https://github.com/audreyr/cookiecutter
.. _`audreyr/cookiecutter-pypackage`: https://github.com/audreyr/cookiecutter-pypackage
.. _`audreyr/cookiecutter-pypackage`: https://github.com/audreyr/cookiecutter-pypackage
.. _NDEx: http://www.ndexbio.org
.. _NeST: https://idekerlab.ucsd.edu/nest
.. _`NeST Map - Main Model`: https://www.ndexbio.org/viewer/networks/9a8f5326-aa6e-11ea-aaef-0ac135e8bacf
