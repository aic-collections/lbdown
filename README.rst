=====================
LAKE Batch Downloader
=====================

Simple microservice to stream groups of files from LAKE in (large?) batches.

This service takes a set of parameters defining asset UIDs and streams
out a ZIP archive for all files, or selected files within each asset, as an
uncompressed archive file.

Note: For maximum portability & simplicity, only the ZIP format is supported at
the moment. This service is geared at delivering files to OS X and Windows
desktop users.

------------
Installation
------------

Requires Python v3.5 or later and a package manager (examples below use pip).

It is strongly advised to install under a virtual environment. The ``venv``
module from the Python standard library is the most convenient tool.

::

    mkdir lbdown
    cd lbdown
    python3 -m venv virtualenv
    source virtualenv/bin/activate
    git clone https://github.com/aic-collections/lbdown.git src
    cd src
    # Install dependencies.
    pip install -r requirements.txt
    # Make the run script executable.
    chmod +x run.sh

-------------
Configuration
-------------

The source code comes with a sample configuration which is unusable without
modifications. In order to prevent overwriting your configuration when pulling
updates to the git repo, you must copy the sample configuration directory in a
safe place, e.g.::

    cp -r etc.example /usr/local/lake/lbdown/etc

You must provide an endpoint URL for the triplestore index, and if the Fedora
endpoint from which files are downloaded require authentication, credentials
too must be provided.

After configuring the application you need to export an environment variable
pointing to it::

    export LBDOWN_CONFIG_DIR=/usr/local/lake/lbdown/etc

-------
Startup
-------

To start the server, execute `run.sh`::

    ./run.sh

The server will run by default on port 8000 with 4 threads. This is a WSGI,
production-ready server.

-----
Usage
-----

::

    curl -XPOST localhost:5000/batch_download -F'uids=SI-016904,SI-016936' -F'original_filename=true' -o /tmp/lake_dl.zip

The archive file will start downloading very shortly (startup time is
proportional to the number of resources requested, not to the size of the
downloaded files).

**Note**: If you request headers (``curl -i``) they will be added *inside* the
ZIP file. You will receive a warning when you unpack the file.

~~~~~~~~~~
Parameters
~~~~~~~~~~

``uids``: list of LAKE asset UIDs to retrieve.

Optionally, filesets with one or more specific roles can be indicated. The
possible roles are: ``orig`` (Original), ``pm`` (Preservation Master), or
``int`` (Intermediate).

E.g.::

    uuid1,uuid2,uuid3:pm,uuid3:orig,uuid4:int,uuid5:int:pm

Will package and download all files for ``uuid1``, ``uuid2``, the
original file for ``uuid3``, the intermediate for ``uuid4`` and both
intermediate and preservation master for ``uuid5``.

The final ZIP folder structure will look similar to the following::

    <ZIP root>
     │
     ├─uuid1
     │  ├─uuid1-int.tiff
     │  ├─uuid1-pm.tiff
     │  └─uuid1-orig.dng
     ├─uuid2
     │  ├─uuid2-int.tiff
     │  ├─uuid2-pm.tiff
     │  └─uuid2-orig.dng
     ├─uuid3
     │  └─uuid3-orig.dng
     ├─uuid4
     │  └─uuid4-int.tiff
     └─uuid5
        ├─uuid5-int.tiff
        └─uuid5-pm.tiff

If ``original_filename`` is set to ``true`` or any other value, the files are
named as they were originally uploaded.
