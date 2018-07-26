from hashlib import md5
from os import path

import logging
import requests
import zipstream

from flask import Flask, Response, request

logger = logging.getLogger(__name__)

app = Flask(__name__)
#app.config.update(flask_conf)

fedora_uri_pfx = 'https://lakesuperior-staging.artic.edu/fcrepo/rest/prod'
solr_url= 'https://lakesolridx-staging.artic.edu/solr/aic_production/select'
qry_tpl = (
    '{{!join+from%3Dfile_set_ids_ssim+to%3Did}}uid_ssim%3A"{}"'
    '&fl=id+title_tesim+rdf_types_ssim&wt=json'
)
fq_tpl = 'rdf_types_ssim:{}'

role_uri_pfx = 'http://definitions.artic.edu/ontology/1.0/type/'
orig_role_uid = 'OriginalFileSet'
pm_role_uid = 'PreservationMasterFileSet'
int_role_uid = 'IntermediateFileSet'


@app.route('/batch_download', methods=['POST'])
def batch_download():
    """
    Download a list of files as a zip stream.
    """
    uids = request.form.get('uids', '').split(',')

    response = Response(generator(uids), mimetype='application/zip')
    response.headers['Content-Disposition'] = (
            'attachment; filename={}'.format('lake_archive.zip'))
    return response


def generator(uids):
    """
    Generate the ZIP stream.

    Wraps :py:meth:`retrieve_contents`, packages the ZIP archive and streams
    it out in chunks.

    :param list uids: List of LAKE asset UIDs to retrieve.
        Optionally, filesets with a specific role can be indicated.
        E.g::

            ['uuid1' , 'uuid2', 'uuid3:pm', 'uuid3:orig',
            'uuid4:int', 'uuid5:int:pm']

    """

    zstream = zipstream.ZipFile(mode='w')


    for uid in uids:
        uid_els = uid.split(':')
        asset_uid = uid_els[0]

        role_uris = []
        for uid_el in uid_els[1:]:
            if uid_el == 'orig':
                role_uid = pm_role_uid
            elif uid_el  == 'pm':
                role_uid = pm_role_uid
            elif uid_el  == 'int':
                role_uid = int_role_uid
            role_uris.append(role_uri_pfx + role_uid)
        src = retrieve_contents(asset_uid, role_uris)
        app.logger.info('Asset UID: {}'.format(asset_uid))
        app.logger.info('Fileset roles: {}'.format(role_uris))

        zstream.write(
                asset_uid, arcname='{}/{}'.format(uid, path.basename(uid)))

    for chunk in zstream:
        yield chunk


def retrieve_contents(asset_uid, role_uris=[]):
    """
    Query Solr and retrieve Fedora resources.
    """
    q = qry_tpl.format(asset_uid)
    fq = fq_tpl.format('("' + '" OR "'.join(role_uris) + '")') if role_uris else ''

    qry_url = '{}?q={}&fq={}'.format(solr_url, q, fq)
    rsp = requests.get(qry_url)
    app.logger.info('Query: {}'.format(qry_url))
    app.logger.info('Response: {}'.format(rsp.text))

    docs = rsp.json()['response']['docs']
    app.logger.debug('Retrieved docs: {}'.format(docs))

    for doc in docs:
        rsp = requests.get(fedora_uri_from_uuid(doc['id']), stream=True)
        app.logger.debug('Fedora URI: {}'.format(fedora_uri_from_uuid(doc['id'])))
        app.logger.debug('Fedora status code: {}'.format(rsp.status_code))
        app.logger.debug('Fedora response headers: {}'.format(rsp.headers))


def fedora_uri_from_uuid(uuid):
    """
    Generate a Fedora pairtree from a given LAKE uid.

    :param str uid: The resource UID.
    """
    cksum_raw = md5(bytes(uuid, 'ascii')).hexdigest()
    cksum = split_md5_hash(cksum_raw)
    path = '/{}/{}/{}/{}/{}'.format(cksum_raw[:2], cksum_raw[2:4],
            cksum_raw[4:6], cksum_raw[6:8], cksum)

    return fedora_uri_pfx + path


def split_md5_hash(hash):
    '''Split MD5 UID with dashes as per ISOXXX.

    @param uid (string) MD5 hash.
    '''
    ## @TODO add validation.
    return '{}-{}-{}-{}-{}'.format(hash[:8],hash[8:12],
            hash[12:16],hash[16:20],hash[20:])


