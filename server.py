from datetime import datetime
from hashlib import md5
from os import path

import logging
import requests
import zipstream

from flask import Flask, Response, request

CHUNK_SIZE = 4096
"""Bytes streamed at a time."""

ZIPROOT_PFX = 'lake_batch_download'
"""Beginning of the ZIP archive root name. It is suffixed with a timestamp."""

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
}}
'''


@app.route('/batch_download', methods=['POST'])
def batch_download():
    """
    Download a list of files as a zip stream.
    """
    uids = request.form.get('uids', '').split(',')
    original_filename = request.form.get('original_filename', False)

    ziproot = '{}-{}'.format(ZIPROOT_PFX, datetime.now().isoformat())

    response = Response(
            generate(uids, ziproot, original_filename), mimetype='application/zip')
    response.headers['Content-Disposition'] = (
            'attachment; filename={}.zip'.format(ziproot))
    return response


def generate(uids, ziproot, original_filename=False):
    """
    Generate the ZIP stream.

    Wraps :py:meth:`retrieve_contents`, packages the ZIP archive and streams
    it out in chunks.

    :param list uids: List of LAKE asset UIDs to retrieve.
    """
    zstream = zipstream.ZipFile(mode='w')

    for uid in uids:
        uid_els = uid.split(':')
        asset_uid = uid_els[0]

        role_uris = []
        for uid_el in uid_els[1:]:
            role_uris.append(role_uri_pfx + fset_types[uid_el])
        for doc in retrieve_contents(asset_uid, role_uris):
            app.logger.info('Requesting asset UID: {}'.format(asset_uid))

            fname = (
                    doc['orig_fname'] if original_filename
                    else '{}-{}{}'.format(
                        asset_uid, doc['fstype'],
                        path.splitext(doc['orig_fname'])[1]))

            arcname = '{}/{}/{}'.format(ziproot, asset_uid, fname)

            zstream.write_iter(iterable=doc['iterable'], arcname=arcname)

    for chunk in zstream:
        yield chunk


def retrieve_contents(asset_uid, role_uris=[]):
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
    app.logger.debug('Query: {}'.format(qry))
    app.logger.debug('Response: {}'.format(rsp.text))

    docs = rsp.json()['results']['bindings']
    #app.logger.debug('Retrieved docs: {}'.format(docs))

    for doc in docs:
        file_rsp = requests.get(doc['f']['value'], stream=True)
        app.logger.debug('Fedora status code: {}'.format(file_rsp.status_code))
        app.logger.debug('Fedora response headers: {}'.format(file_rsp.headers))

        yield {
            'orig_fname': doc['fname']['value'],
            'fstype': fset_pfx[path.basename(doc['fstype']['value'])],
            'iterable': file_rsp.iter_content(chunk_size=CHUNK_SIZE ),
        }
