#! /usr/bin/env python

import os
import io
import argparse
import sys
import csv
import json
import logging
import tempfile
import shutil
import requests
from logging import config
from tqdm import tqdm
from ndexutil.config import NDExUtilConfig
from ndex2.client import Ndex2, DecimalEncoder
from ndex2.cx2 import RawCX2NetworkFactory
from ndex2.cx2 import CX2Network
import ndexnestloader

logger = logging.getLogger(__name__)

TSV2NICECXMODULE = 'ndexutil.tsv.tsv2nicecx2'

LOG_FORMAT = "%(asctime)-15s %(levelname)s %(relativeCreated)dms " \
             "%(filename)s::%(funcName)s():%(lineno)d %(message)s"

GENERATED_BY_ATTRIB = 'prov:wasGeneratedBy'
"""
Network attribute to denote what created this network
"""

DERIVED_FROM_ATTRIB = 'prov:wasDerivedFrom'
"""
Network attribute to denote source of network data
"""

PROTEIN_ONE = 'Protein 1'
"""
Denotes column/attribute for what we assume is source protein in 
IAS_score.tsv file
"""

PROTEIN_TWO = 'Protein 2'
"""
Denotes column/attribute for what we assume is target protein in 
IAS_score.tsv file
"""

FLOAT_ATTRIBUTES = ['Integrated score',
                    'evidence: Protein co-expression',
                    'evidence: Co-dependence',
                    'evidence: Sequence similarity',
                    'evidence: Physical',
                    'evidence: mRNA co-expression']
"""
Attributes on NeST Map - Main Model that are known to be floats
"""


class Formatter(argparse.ArgumentDefaultsHelpFormatter, argparse.RawDescriptionHelpFormatter):
    pass


def _parse_arguments(desc, args):
    """
    Parses command line arguments
    :param desc:
    :param args:
    :return:
    """
    parser = argparse.ArgumentParser(description=desc,
                                     formatter_class=Formatter)
    parser.add_argument('--profile', help='Profile in configuration '
                                          'file to use to load '
                                          'NDEx credentials which means'
                                          'configuration under [XXX] will be'
                                          'used '
                                          '(default '
                                          'ndexnestloader)',
                        default='ndexnestloader')
    parser.add_argument('--nest',
                        default='9a8f5326-aa6e-11ea-aaef-0ac135e8bacf',
                        help='NDEx UUID of NeST Map - Main Model used to '
                             'define members of subnetworks as well as the '
                             'names of those subnetworks')
    parser.add_argument('--ias_score',
                        default='https://zenodo.org/records/4516939/files/'
                                'IAS_score.tsv?download=1',
                        help='Path to IAS_score.tsv file or URL to download '
                             'file')
    parser.add_argument('--maxsize', default=100, type=int,
                        help='Maximum size of NeST subnetwork to extract')
    parser.add_argument('--visibility', default='PUBLIC',
                        choices=['PUBLIC', 'PRIVATE'],
                        help='Denotes visibility of uploaded subnetworks '
                             'on NDEx')
    parser.add_argument('--dryrun', action='store_true',
                        help='Run the processing, but do NOT upload networks '
                             'to NDEx. Operation that would be performed is '
                             'output as INFO level log message')
    parser.add_argument('--tempdir',
                        help='Sets alternate temporary directory used to '
                             'store IAS_Score.tsv file. This directory must exist '
                             'and be writable')
    parser.add_argument('--logconf', default=None,
                        help='Path to python logging configuration file in '
                             'this format: https://docs.python.org/3/library/'
                             'logging.config.html#logging-config-fileformat '
                             'Setting this overrides -v parameter which uses '
                             ' default logger. (default None)')
    parser.add_argument('--conf', help='Configuration file to load '
                                       '(default ~/' +
                                       NDExUtilConfig.CONFIG_FILE)
    parser.add_argument('--verbose', '-v', action='count', default=1,
                        help='Increases verbosity of logger to standard '
                             'error for log messages in this module and'
                             'in ' + TSV2NICECXMODULE + '. Messages are '
                             'output at these python logging levels '
                             '-v = WARNING, -vv = INFO, -vvv = DEBUG, '
                             '-vvvv = NOTSET (default error '
                             'logging)')
    parser.add_argument('--version', action='version',
                        version=('%(prog)s ' +
                                 ndexnestloader.__version__))

    return parser.parse_args(args)


def _setup_logging(args):
    """
    Sets up logging based on parsed command line arguments.
    If args.logconf is set use that configuration otherwise look
    at args.verbose and set logging for this module and the one
    in ndexutil specified by TSV2NICECXMODULE constant
    :param args: parsed command line arguments from argparse
    :raises AttributeError: If args is None or args.logconf is None
    :return: None
    """

    if args.logconf is None:
        level = (50 - (10 * args.verbose))
        logging.basicConfig(format=LOG_FORMAT,
                            level=level)
        logging.getLogger(TSV2NICECXMODULE).setLevel(level)
        logger.setLevel(level)
        return

    # logconf was set use that file
    logging.config.fileConfig(args.logconf,
                              disable_existing_loggers=False)


class NDExNeSTLoader(object):
    """
    Class to load content
    """
    def __init__(self, args,
                 cx2factory=RawCX2NetworkFactory()):
        """

        :param args:
        """
        self._conf_file = args.conf
        self._profile = args.profile
        self._visibility = args.visibility
        self._dryrun = args.dryrun
        self._tempdir = args.tempdir
        self._user = None
        self._pass = None
        self._server = None
        self._ndexclient = None
        self._version = args.version
        self._nest = args.nest
        self._ias_score = args.ias_score
        self._maxsize = args.maxsize
        self._cx2factory = cx2factory

    def _get_user_agent(self):
        """
        Builds user agent string
        :return: user agent string in form of ncipid/<version of this tool>
        :rtype: string
        """
        return 'nest/' + str(self._version)

    def _create_ndex_connection(self):
        """
        creates connection to ndex
        :return:
        """
        if self._ndexclient is None:
            self._ndexclient = Ndex2(host=self._server, username=self._user,
                                     password=self._pass, user_agent=self._get_user_agent(),
                                     skip_version_check=True)

    def _download_ias_score(self, tempdir):
        """
        If needed downloads ias_score

        :return: Path to ias_score.tsv file
        :rtype: str
        """
        if os.path.isfile(self._ias_score):
            return self._ias_score

        # use python requests to download the file and then get its results
        local_file = os.path.join(tempdir,
                                  self._ias_score.split('/')[-1])

        with requests.get(self._ias_score,
                          stream=True) as r:
            content_size = int(r.headers.get('content-length', 0))
            tqdm_bar = tqdm(desc='Downloading ' + os.path.basename(local_file),
                            total=content_size,
                            unit='B', unit_scale=True,
                            unit_divisor=1024)
            logger.debug('Downloading ' + str(self._ias_score) +
                         ' of size ' + str(content_size) +
                         'b to ' + local_file)
            try:
                r.raise_for_status()
                with open(local_file, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)
                        tqdm_bar.update(len(chunk))
            finally:
                tqdm_bar.close()

        return local_file

    def _get_ias_score_map(self):
        """
        Loads IAS_score.tsv file passed in via constructor as a dict
        where the key PROTEIN_ONE column value and the value is a map
        with the remaining columns as keys and values.

        :return:
        :rtype: dict
        """

        score_map = {}

        float_attrs = set(FLOAT_ATTRIBUTES)
        if self._tempdir is None:
            tempdir = tempfile.mkdtemp()
            logger.debug('Creating temp directory: ' + tempdir)
        else:
            tempdir = self._tempdir
        try:
            ias_score_file = self._download_ias_score(tempdir)
            with open(ias_score_file, 'r', newline='') as f:
                reader = csv.DictReader(f, delimiter='\t')
                for row in reader:
                    if row[PROTEIN_ONE] not in score_map:
                        score_map[row[PROTEIN_ONE]] = {}
                    for key in row:
                        if key in float_attrs:
                            row[key] = float(row[key])
                    score_map[row[PROTEIN_ONE]][row[PROTEIN_TWO]] = row
            return score_map
        finally:
            if self._tempdir is None:
                logger.debug('Removing temp directory: ' + tempdir)
                shutil.rmtree(tempdir)

    def _parse_config(self):
            """
            Parses config

            """
            ncon = NDExUtilConfig(conf_file=self._conf_file)
            con = ncon.get_config()
            self._user = con.get(self._profile, NDExUtilConfig.USER)
            self._pass = con.get(self._profile, NDExUtilConfig.PASSWORD)
            self._server = con.get(self._profile, NDExUtilConfig.SERVER)

    def get_network_from_ndex(self, ndexclient=None, network_uuid=None):
        """
        Gets network with **network_uuid** id from NDEx

        :param network_uuid: UUID of network on NDEx
        :type network_uuid: str
        :return: Network loaded from NDEx
        :rtype: :py:class:`~ndex2.cx2.CX2Network`
        """
        myclient = ndexclient
        if myclient is None:
            myclient = self._ndexclient
        logger.debug('getting network ' + str(network_uuid) + ' from NDEx')
        client_resp = myclient.get_network_as_cx2_stream(network_uuid)
        return self._cx2factory.get_cx2network(client_resp.json())

    def get_name_and_genes_from_node(self, node):
        """
        Gets name and genes of assembly from NeST Map - Model Model **node**

        :param node: Node from :py:class:`~ndex2.cx2.CX2Network` that is a dictionary
                     of dictionaries and the node attributes are under ``'v'`` key
        :type node: dict
        :return: (name, list of gene names)
        :rtype: tuple
        """
        if 'v' not in node:
            logger.info('No "v" key in node: ' + str(node))
            return None, None
        if 'Genes' not in node['v']:
            logger.info('No "Genes" key under "v" in node: ' + str(node))
            return None, None
        name = None
        if 'Annotation' in node['v']:
            name = node['v']['Annotation']
        return name, node['v']['Genes'].split(' ')

    def check_for_existing_networks(self, ignore_owner=False):
        """
        Query for networks owned by user and create a map of
        name to UUID

        :return:
        :rtype: dict
        """
        network_dict = {}
        all_netsummaries = []

        net_summaries = self._ndexclient.get_user_network_summaries(self._user,
                                                                    limit=10000)
        while len(net_summaries) == 10000:
            logger.info('User has 10,000 networks at least,'
                        'querying again for all network summaries')
            all_netsummaries.extend(net_summaries)
            net_summaries = self._ndexclient.get_user_network_summaries(self._user,
                                                                        limit=10000)
        all_netsummaries.extend(net_summaries)

        for ns in all_netsummaries:
            if 'name' not in ns:
                logger.debug('Network with UUID: ' +
                             str(ns['externalId'] +
                                 ' lacks a name. Skipping'))
                continue
            if ignore_owner is False and ns['owner'] != self._user:
                logger.debug('Network ' + ns['name'] + ' UUID: ' +
                             ns['externalId'] +
                             ' does not match owner. Skipping')
                continue

            network_dict[ns['name']] = ns['externalId']
        return network_dict

    def get_style_from_network(self):
        """
        Gets visualProperties from style network within package

        :return:
        """
        cx2network = None
        cxfile = os.path.join(os.path.dirname(ndexnestloader.__file__), 'style.cx2')
        with open(cxfile, 'r') as f:
            cx2network = self._cx2factory.get_cx2network(json.load(f))

        return cx2network.get_visual_properties()

    def run(self):
        """
        Runs content loading for NDEx NeST SubNetworks Content Loader

        :return: 0 upon success otherwise error
        :rtype: int
        """
        self._parse_config()
        self._create_ndex_connection()

        # Load Hierarchy
        hierarchy = self.get_network_from_ndex(network_uuid=self._nest)

        network_dict = self.check_for_existing_networks()

        visual_props = self.get_style_from_network()

        score_map = self._get_ias_score_map()
        # For each node in hierarchy
        for node in hierarchy.get_nodes().items():
            name, gene_list = self.get_name_and_genes_from_node(node[1])
            if name is None:
                continue
            if name.startswith('NEST:'):
                logger.debug('Skipping ' + name + ' because assembly lacks a name')
                continue

            num_nodes = len(gene_list)
            if num_nodes > self._maxsize:
                logger.info('Skipping ' + name + ' because it has ' +
                            str(num_nodes) +
                            ' which exceeds --maxsize cutoff of ' +
                            str(self._maxsize))
                continue

            # create network from gene_list
            sub_network = self._create_network_from_gene_list(gene_list, score_map=score_map)

            net_attrs = sub_network.get_network_attributes()

            # Rename subsystem, update description, version, and reference
            self._update_network_attributes(name=name, net_attrs=net_attrs)

            self._add_assembly_attributes_as_net_attributes(node[1], net_attrs=net_attrs)

            sub_network.set_network_attributes(net_attrs)

            sub_network.set_visual_properties(visual_props)

            self._save_update_network(net_attrs=net_attrs, network_dict=network_dict, sub_network=sub_network)
        return 0

    def _update_network_attributes(self, name=None, net_attrs=None):
        """

        :param assembly_node_attrs:
        :param net_attrs:
        :return:
        """
        net_attrs['name'] = name

        if 'Description' in net_attrs:
            del net_attrs['Description']

        net_attrs['description'] = '<p>This network represents a ' \
                                   'subsystem of the NeST ' \
                                   'hierarchical model, generated ' \
                                   'under the <b>C</b>ancer ' \
                                   '<b>C</b>ell <b>M</b>aps ' \
                                   '<b>I</b>nitiative (<b>CCMI</b>).' \
                                   '</p><p>For more information about ' \
                                   'NeST: <a href="https://ccmi.org/' \
                                   'nest"><b>ccmi.org/nest</b></a></p>' \
                                   '<p>Explore the NeST map in <a href' \
                                   '="https://www.ndexbio.org/viewer/' \
                                   'networks/9a8f5326-aa6e-11ea-aaef-' \
                                   '0ac135e8bacf"><b>NDEx</b></a></p><p>' \
                                   'Browse the NeST map in <a href="http://' \
                                   'hiview.ucsd.edu/274fcd6c-1adc-11ea-a7' \
                                   '41-0660b7976219?type=test&amp;server=' \
                                   'https://test.ndexbio.edu"><b>HiView' \
                                   '</b></a></p>'
        net_attrs['version'] = '20211001'
        net_attrs['reference'] = '<p>Zheng F.<i>et al</i>.<br/><b> ' \
                                 'Interpretation of cancer mutations ' \
                                 'using a multiscale map of protein ' \
                                 'systems</b>.<br/>Science. 2021 Oct;374' \
                                 '(6563)<br/>doi: <a href="https://doi.' \
                                 'org/10.1126/science.abf3067">10.1126/' \
                                 'science.abf3067</a></p>'
        net_attrs[GENERATED_BY_ATTRIB] = '<a href="https://github.com/' + \
                                         'ndexcontent/ndexnestloader"' + \
                                         '>ndexnestloader ' + \
                                         str(ndexnestloader.__version__) + \
                                         '</a>'
        net_attrs[DERIVED_FROM_ATTRIB] = '<a href="' + \
                                         self._get_network_url(self._nest) + \
                                         '" target="_blank">NeST Map - ' \
                                         'Main Model</a>'

    def _add_assembly_attributes_as_net_attributes(self, node, net_attrs=None):
        """
        Adds attributes from a NeST assembly/node to **net_attrs** dict that
        will be set as network attributes for subnetwork

        :param node: Attributes in CX2 of NeST assembly node
        :type node: dict
        :param net_attrs:
        :type net_attrs: dict
        :return:
        :rtype: dict
        """
        for entry in node['v'].items():
            if entry[0] in ['n', 'name', 'Annotation', 'Size', 'Size-Log', 'Genes']:
                continue
            net_attrs[entry[0]] = entry[1]

    def _get_score_map_edge_attributes(self, ias_attributes):
        """
        Given a row of data from IAS_score.tsv stored as a dict
        return that dict minus ``Protein 1`` and ``Protein 2``

        :param ias_attributes: Attributes to add to edge
        :type ias_attributes: dict
        :return: Attributes to add to an edge
        :rtype: dict
        """
        res = {}
        for key in ias_attributes:
            if key == PROTEIN_ONE or key == PROTEIN_TWO:
                continue
            res[key] = ias_attributes[key]
        return res

    def _create_network_from_gene_list(self, gene_list, score_map=None):
        """
        Creates network from gene list and score map which has format
        of protein 1 => protein 2 => {scores}

        :param gene_list: List of genes
        :type gene_list: list
        :param score_map:
        :type score_map: dict
        :return: Network created from ias_score and gene list
        :rtype: :py:class:`~ndex2.cx2.CX2Network`
        """
        node_map = {}
        net = CX2Network()
        for protein_one in gene_list:
            if protein_one not in score_map:
                continue
            if protein_one not in node_map:
                node_map[protein_one] = net.add_node(attributes={'name': protein_one})

            for protein_two in gene_list:
                if not protein_two in score_map[protein_one]:
                    continue
                if protein_two not in node_map:
                    node_map[protein_two] = net.add_node(attributes={'name': protein_two})

                net.add_edge(source=node_map[protein_one],
                             target=node_map[protein_two],
                             attributes=self._get_score_map_edge_attributes(score_map[protein_one][protein_two]))
        return net

    def _save_update_network(self, net_attrs=None, network_dict=None, sub_network=None):
        """
        Saves or updates network in NDEx. If ``net_attrs['name']`` is
        in **network_dict** then the network is updated, otherwise it is saved
        as a new network.

        .. note::

            If ``args.dryrun`` is set to ``True`` in constructor then
            no update to NDEx is performed. Instead ``INFO`` level log messages are
            output denoting this is a dry run.

        :param net_attrs: Network's attributes
        :type net_attrs: dict
        :param network_dict: contains mapping of network names to NDEx UUID of networks
                             stored on NDEx
        :type network_dict: dict
        :param sub_network: Network to save or update
        :type sub_network: :py:class:`~ndex2.cx2.CX2Network`
        """
        if net_attrs['name'] in network_dict:
            # this is an update
            logger.info('Updating network ' + net_attrs['name'] + ' ' + network_dict[net_attrs['name']])
            if self._dryrun is True:
                logger.info(
                    'Dry run: ' + 'Updating network ' + net_attrs['name'] + ' ' + network_dict[net_attrs['name']])
            else:
                cx_stream = io.BytesIO(json.dumps(sub_network.to_cx2(),
                                                  cls=DecimalEncoder).encode('utf-8'))
                self._ndexclient.update_cx2_network(cx_stream, network_dict[net_attrs['name']])
        else:
            if self._dryrun is True:
                logger.info('Dry run: Saving network ' + net_attrs['name'])
            else:
                # Save subsystem as new network
                self._ndexclient.save_new_cx2_network(sub_network.to_cx2(), visibility=self._visibility)

    def _get_network_url(self, network_id):
        """
        Gets URL for source NeST subsystem network based on value of
        server in configuration. If server is set to ``public.ndexbio.org``
        the value is switched to ``www.ndexbio.org``

        :return: URL of network that can be pasted into browser
        :rtype: str
        """
        server_url = self._server
        if server_url is None or server_url == 'public.ndexbio.org':
            server_url = 'www.ndexbio.org'
        return 'https://' + server_url + '/viewer/networks/' + network_id


def main(args):
    """
    Main entry point for program

    :param args: Command line arguments with 0 being this invoking script filename or path
    :type args: list
    :return: 0 upon success otherwise error
    :rtype: int
    """
    desc = """
    Version {version}

    Loads NDEx NeST SubNetworks Content Loader data into NDEx (http://ndexbio.org).
    
    NeST subnetworks with more then --maxsize of 100 nodes are excluded. 
    
    To connect to NDEx server a configuration file must be passed
    into --conf parameter. If --conf is unset the configuration 
    the path ~/{confname} is examined. 
         
    The configuration file should be formatted as follows:
         
    [<value in --profile (default ndexnestloader)>]
         
    {user} = <NDEx username>
    {password} = <NDEx password>
    {server} = <NDEx server(omit http) ie public.ndexbio.org>
    
    
    """.format(confname=NDExUtilConfig.CONFIG_FILE,
               user=NDExUtilConfig.USER,
               password=NDExUtilConfig.PASSWORD,
               server=NDExUtilConfig.SERVER,
               version=ndexnestloader.__version__)
    theargs = _parse_arguments(desc, args[1:])
    theargs.program = args[0]
    theargs.version = ndexnestloader.__version__

    try:
        _setup_logging(theargs)
        loader = NDExNeSTLoader(theargs)
        return loader.run()
    except Exception as e:
        logger.exception('Caught exception')
        return 2
    finally:
        logging.shutdown()


if __name__ == '__main__':  # pragma: no cover
    sys.exit(main(sys.argv))
