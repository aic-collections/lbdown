from hashlib import md5
from os import path

import logging
import requests
import zipstream

from flask import Flask, Response, request

CHUNK_SIZE = 4096
"""Bytes streamed at a time."""


logger = logging.getLogger(__name__)

app = Flask(__name__)
#app.config.update(flask_conf)

sparql_ep_url = 'https://laketsidx-staging.artic.edu/blazegraph/namespace/lakeidx/'

role_uri_pfx = 'http://definitions.artic.edu/ontology/1.0/type/'

fset_types = {
    'orig': 'OriginalFileSet',
    'pm': 'PreservationMasterFileSet',
    'int': 'IntermediateFileSet',
}
fset_pfx = {v: k for k, v in fset_types.items()}

qry_tpl = '''
PREFIX ebucore: <http://www.ebu.ch/metadata/ontologies/ebucore/ebucore#>
PREFIX aic: <http://definitions.artic.edu/ontology/1.0/>
PREFIX pcdm: <http://pcdm.org/models#>
PREFIX aictype: <http://definitions.artic.edu/ontology/1.0/type/>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>

SELECT DISTINCT ?fstype ?f ?fname {{
  ?a aic:uid "{uid}"^^xsd:string ;
     pcdm:hasMember ?fs .
  ?fs a ?fstype .
  FILTER (?fstype IN (
    aictype:OriginalFileSet ,
    aictype:PreservationMasterFileSet ,
    aictype:IntermediateFileSet)) .
  ?fs pcdm:hasFile ?f .
  ?f ebucore:filename ?fname .
}} LIMIT 1000
'''


@app.route('/batch_download', methods=['POST'])
def batch_download():
    """
    Download a list of files as a zip stream.
    """
    uids = request.form.get('uids', '').split(',')
    original_filename = request.form.get('original_filename', False)

    response = Response(
            generate(uids, original_filename), mimetype='application/zip')
    response.headers['Content-Disposition'] = (
            'attachment; filename={}'.format('lake_archive.zip'))
    return response


def generate(uids, original_filename=False):
    """
    Generate the ZIP stream.

    Wraps :py:meth:`retrieve_contents`, packages the ZIP archive and streams
    it out in chunks.

    :param list uids: List of LAKE asset UIDs to retrieve.
        Optionally, filesets with one or more specific roles can be indicated.
        E.g.::

            ['uuid1' , 'uuid2', 'uuid3:pm', 'uuid3:orig',
            'uuid4:int', 'uuid5:int:pm']

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
             │  └─uuid3-orig.tiff
             ├─uuid4
             │  └─uuid4-int.tiff
             └─uuid5
                ├─uuid5-int.tiff
                └─uuid5-pm.tiff

    If ``original_filename`` is set to ``True``, the files are named as they
    were originally uploaded.
    """
    zstream = zipstream.ZipFile(mode='w')

    for uid in uids:
        uid_els = uid.split(':')
        asset_uid = uid_els[0]

        role_uris = []
        for uid_el in uid_els[1:]:
            role_uris.append(role_uri_pfx + fset_types[uid_el])
        for src in retrieve_contents(asset_uid, role_uris):
            app.logger.info('Asset UID: {}'.format(asset_uid))
            app.logger.info('Fileset roles: {}'.format(role_uris))
            zstream.write_iter(**src)

    for chunk in zstream:
        yield chunk


def retrieve_contents(asset_uid, role_uris=[], original_filename=False):
    """
    Query the SPARQL endpoint and retrieve Fedora resources.
    """
    app.logger.info('Asset UID: {}'.format(asset_uid))
    qry = qry_tpl.format(uid=asset_uid)
    rsp = requests.post(
        sparql_ep_url,
        data={'query': qry},
        headers={'Accept': 'application/json'}
    )
    app.logger.info('Query: {}'.format(qry))
    app.logger.info('Response: {}'.format(rsp.text))

    docs = rsp.json()['results']['bindings']
    #app.logger.debug('Retrieved docs: {}'.format(docs))

    for doc in docs:
        file_rsp = requests.get(doc['f']['value'], stream=True)
        orig_fname = doc['fname']['value']
        fstype = doc['fstype']['value']
        app.logger.debug('Fedora status code: {}'.format(file_rsp.status_code))
        app.logger.debug('Fedora response headers: {}'.format(file_rsp.headers))

        fname = (
                orig_fname if original_filename
                else fset_pfx[path.basename(fstype)])

        yield {
            'arcname': '{}/{}'.format(asset_uid, fname),
            'iterable': file_rsp.iter_content(chunk_size=4096),
        }
