#! /usr/bin/env python

import argparse
import sys
import re
import logging
from logging import config
from ndexutil.config import NDExUtilConfig
from ndex2.client import Ndex2
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
    parser.add_argument('--hiview_link',
                        default='http://hiview.ucsd.edu/274fcd6c-1adc-11ea-a741-0660b7976219?type=test&server=https://test.ndexbio.edu',
                        help='URL for HiView to add to network description')
    parser.add_argument('--maxsize', default=100, type=int,
                        help='Maximum size of NeST subnetwork to extract')
    parser.add_argument('--ccmi_link', default='https://ccmi.org/nest')
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
        self._hiview_link = args.hiview_link
        self._user = None
        self._pass = None
        self._server = None
        self._ndexclient = None
        self._version = args.version
        self._hierarchy = args.hierarchy
        self._ccmi_link = args.ccmi_link
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

        # For each node in hierarchy
        for node in hierarchy.get_nodes().items():
            if not 'ndex:internalLink' in node[1]['v']:
                continue
            sub_net_name, sub_net_uuid = self.get_name_and_uuid_of_subnetwork(node[1])

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

            # Rename subsystem, Add ccmi_link, Add hierarchy link
            ccmi_href = '<a target="_blank" href="' + self._ccmi_link +\
                        '">CCMI NeST</a>'
            hiview_href = '<a target="_bank" href="' +\
                          self._hiview_link +\
                          '">Click here to view whole ' \
                          'hierarchy in HiView</a><br/>'

            net_attrs = sub_network.get_network_attributes()

            if sub_net_name.startswith('NEST:'):
                net_attrs['name'] = re.sub('^NEST:', 'NeST:', sub_net_name)
            else:
                net_attrs['name'] = 'NeST: ' + sub_net_name

            net_attrs['Description'] = 'This network represents a subsystem of<br/>' +\
                                       ccmi_href + ' hierarchy<br/>' + hiview_href
            sub_network.set_network_attributes(net_attrs)
            # Save subsystem as new network
            self._ndexclient.save_new_cx2_network(sub_network.to_cx2(), visibility=self._visibility)

            # Save subsystem to networkset

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
