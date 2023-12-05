#! /usr/bin/env python

import os
import io
import argparse
import sys
import re
import json
import logging
from logging import config
from ndexutil.config import NDExUtilConfig
from ndex2.client import Ndex2, DecimalEncoder
from ndex2.cx2 import RawCX2NetworkFactory
from ndex2.cx2 import CX2Network
import ndexnestloader

logger = logging.getLogger(__name__)

TSV2NICECXMODULE = 'ndexutil.tsv.tsv2nicecx2'

LOG_FORMAT = "%(asctime)-15s %(levelname)s %(relativeCreated)dms " \
             "%(filename)s::%(funcName)s():%(lineno)d %(message)s"


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
    parser.add_argument('--hierarchy', default='274fcd6c-1adc-11ea-a741-0660b7976219',
                        help='NDEx UUID of NeST hierarchy used to extract subnetworks '
                             'and to name those subnetworks')
    parser.add_argument('--maxsize', default=100, type=int,
                        help='Maximum size of NeST subnetwork to extract')
    parser.add_argument('--visibility', default='PUBLIC', choices=['PUBLIC', 'PRIVATE'],
                        help='Denotes visibility of uploaded subnetworks on NDEx')
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
        self._user = None
        self._pass = None
        self._server = None
        self._ndexclient = None
        self._version = args.version
        self._hierarchy = args.hierarchy
        self._maxsize = args.maxsize
        self._cx2factory = cx2factory

    def _get_user_agent(self):
        """
        Builds user agent string
        :return: user agent string in form of ncipid/<version of this tool>
        :rtype: string
        """
        return 'nest/' + self._version

    def _create_ndex_connection(self):
        """
        creates connection to ndex
        :return:
        """
        if self._ndexclient is None:
            self._ndexclient = Ndex2(host=self._server, username=self._user,
                                     password=self._pass, user_agent=self._get_user_agent(),
                                     skip_version_check=True)

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

    def get_name_and_uuid_of_subnetwork(self, node):
        """
        Gets name and subnetwork UUID from old format hiview network hierarchy.

        :param node: Node from :py:class:`~ndex2.cx2.CX2Network` that is a dictionary
                     of dictionaries and the node attributes are under ``'v'`` key
        :type node: dict
        :return: (name, subnetwork UUID)
        :rtype: tuple
        """
        i_link = node['v']['ndex:internalLink']

        # the value in i_link will look something like this
        # [Vesicle membrane fusion](046718a6-2c3b-11eb-890f-0660b7976219)
        # the next command splits and we use simple trimming to get values
        split_link = i_link.split('](')
        return split_link[0][1:], split_link[1][:-1]

    def check_for_existing_networks(self):
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
            if ns['owner'] != self._user:
                logger.debug('Network ' + ns['name'] + ' UUID: ' +
                             ns['externalId'] +
                             ' does not match owner. Skipping')
                continue

            if not ns['name'].startswith('NeST:'):
                logger.debug('Network ' + ns['name'] + ' UUID: ' +
                             ns['externalId'] +
                             ' does not start with NeST: Skipping')
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

        # test client
        testclient = Ndex2(host='test.ndexbio.org', skip_version_check=True,
                           user_agent=self._get_user_agent())
        # Load Hierarchy
        hierarchy = self.get_network_from_ndex(ndexclient=testclient,
                                               network_uuid=self._hierarchy)

        visual_props = self.get_style_from_network()

        # For each node in hierarchy
        for node in hierarchy.get_nodes().items():
            if not 'ndex:internalLink' in node[1]['v']:
                continue
            sub_net_name, sub_net_uuid = self.get_name_and_uuid_of_subnetwork(node[1])
            if sub_net_name.startswith('NEST:'):
                logger.info('Skipping ' + sub_net_name + ' since it lacks a name')
                continue

            # load subsystem as network and skip if exceeds self._maxsize number of nodes
            sub_network = self.get_network_from_ndex(ndexclient=testclient,
                                                     network_uuid=sub_net_uuid)
            num_nodes = len(sub_network.get_nodes().keys())
            if num_nodes > self._maxsize:
                logger.info('Skipping ' + sub_net_name + ' because it has ' +
                            str(num_nodes) +
                            ' which exceeds --maxsize cutoff of ' +
                            str(self._maxsize))
                continue

            # Rename subsystem, update description, version, and reference
            net_attrs = sub_network.get_network_attributes()

            if sub_net_name.startswith('NEST:'):
                net_attrs['name'] = re.sub('^NEST:', 'NeST:', sub_net_name)
            else:
                net_attrs['name'] = 'NeST: ' + sub_net_name

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
            sub_network.set_network_attributes(net_attrs)

            sub_network.set_visual_properties(visual_props)

            network_dict = self.check_for_existing_networks()

            if net_attrs['name'] in network_dict:
                # this is an update
                logger.info('Updating network ' + net_attrs['name'] + ' ' + network_dict[net_attrs['name']])
                cx_stream = io.BytesIO(json.dumps(sub_network.to_cx2(),
                                       cls=DecimalEncoder).encode('utf-8'))
                self._ndexclient.update_cx2_network(cx_stream, network_dict[net_attrs['name']])
            else:
                # Save subsystem as new network
                self._ndexclient.save_new_cx2_network(sub_network.to_cx2(), visibility=self._visibility)

        return 0


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
