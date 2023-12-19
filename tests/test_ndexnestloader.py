#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Tests for `ndexnestloader` package."""

import os
import io
import tempfile
import shutil
import json
from unittest.mock import MagicMock

import unittest
from ndexnestloader.ndexloadnestsubnetworks import NDExNeSTLoader
from ndexnestloader import ndexloadnestsubnetworks
from ndex2.client import Ndex2, DecimalEncoder

class TestNDExNestLoader(unittest.TestCase):
    """Tests for `ndexnestloader` package."""

    def setUp(self):
        """Set up test fixtures, if any."""

    def tearDown(self):
        """Tear down test fixtures, if any."""

    def get_mockargs(self):
        mockargs = MagicMock()
        mockargs.conf = None
        mockargs.profile = 'foo'
        mockargs.visibility = 'PUBLIC'
        mockargs.dryrun = False
        mockargs.version = '1.0'
        mockargs.nest = '12345'
        mockargs.ias_score = 'http://foo'
        mockargs.maxsize = 100
        return mockargs

    def get_example_nest_node(self):
        example_node = {'id': 41376,
                        'x': -1622.0690606338903,
                        'y': -684.7666702109273,
                        'v': {'n': 'NEST:169',
                              'Mutation frequency:OV': 0.078,
                              'Mutation frequency:KIRC': 0.084,
                              'Genes': 'AKT1 CTNNB1 EGF EGFR ILK JADE1 NF2 PPL PTEN SLC9A3R1 STUB1 VIM YWHAZ',
                              'Size': 13,
                              'No. significantly mutated cancer types': 4,
                              'Mutation frequency:LUSC': 0.209,
                              '-log10 adjusted p-value': 0,
                              'Mutation frequency:GBM': 0.504,
                              'adjusted  p-value': 1,
                              'Mutation frequency:BRCA': 0.125,
                              'Mutation frequency:LUAD': 0.235,
                              'Mutation frequency:BLCA': 0.22,
                              'Mutation frequency:UCEC': 0.713,
                              'Mutation frequency:LIHC': 0.344,
                              'Annotation': 'AKT1 activation',
                              'Weight': 0.37,
                              'No. significantly mutated cancer types (aggregate)': 4,
                              'Mutation frequency:SKCM': 0.393,
                              'Mutation frequency:HNSC': 0.133,
                              'Significantly mutated cancer types (aggregate)': 'BRCA GBM LIHC UCEC',
                              'Significantly mutated cancer types': 'BRCA GBM LIHC UCEC',
                              'Mutation frequency:COAD': 0.225,
                              'Size-Log': 3.700439718141092,
                              'Mutation frequency:STAD': 0.239,
                              'NEST ID': 'NEST:169'}}
        return example_node

    def test_get_user_agent(self):
        mockargs = self.get_mockargs()
        loader = NDExNeSTLoader(mockargs)
        self.assertEqual('nest/' + mockargs.version,
                         loader._get_user_agent())

    def test_create_ndex_connection_already_set(self):
        mockargs = self.get_mockargs()
        loader = NDExNeSTLoader(mockargs)
        loader._ndexclient = 'foo'
        loader._create_ndex_connection()
        self.assertEqual('foo', loader._ndexclient)

    def test_create_ndex_connection(self):
        mockargs = self.get_mockargs()
        loader = NDExNeSTLoader(mockargs)
        loader._server = 'foo.com'
        loader._user = 'user'
        loader._pass = 'pass'
        loader._create_ndex_connection()
        self.assertTrue(isinstance(loader._ndexclient, Ndex2))

    def test_download_ias_score_filepath_passed_in(self):
        temp_dir = tempfile.mkdtemp()
        try:
            ias_score_file = os.path.join(temp_dir, 'foo.tsv')
            open(ias_score_file, 'a').close()
            mockargs = self.get_mockargs()
            mockargs.ias_score = ias_score_file
            loader = NDExNeSTLoader(mockargs)
            self.assertEqual(ias_score_file,
                             loader._download_ias_score(temp_dir))
        finally:
            shutil.rmtree(temp_dir)

    def test_get_ias_score_map_filepath_with_5rows(self):
        temp_dir = tempfile.mkdtemp()
        try:
            ias_score_file = os.path.join(os.path.dirname(__file__),
                                          '5rows_ias_score.tsv')
            mockargs = self.get_mockargs()
            mockargs.ias_score = ias_score_file
            loader = NDExNeSTLoader(mockargs)
            score_map = loader._get_ias_score_map()

            self.assertEqual(2, len(score_map.keys()))
            self.assertTrue('A1BG' in score_map)
            self.assertTrue('A1CF' in score_map)
            self.assertEqual(3, len(score_map['A1BG'].keys()))
            self.assertEqual({'Protein 1': 'A1BG',
                              'Protein 2': 'ABCB4',
                              'Integrated score': 0.208,
                              'evidence: Co-dependence': 0.0,
                              'evidence: Physical': 0.092,
                              'evidence: Protein co-expression': 0.007,
                              'evidence: Sequence similarity': 0.112,
                              'evidence: mRNA co-expression': 0.316},
                             score_map['A1BG']['ABCB4'])

            self.assertEqual(2, len(score_map['A1CF'].keys()))

        finally:
            shutil.rmtree(temp_dir)

    def test_name_and_genes_from_node_no_v(self):
        example_node = self.get_example_nest_node()
        del example_node['v']
        mockargs = self.get_mockargs()
        loader = NDExNeSTLoader(mockargs)
        self.assertEqual((None, None), loader.get_name_and_genes_from_node(example_node))

    def test_name_and_genes_from_node_no_genes(self):
        example_node = self.get_example_nest_node()
        del example_node['v']['Genes']
        mockargs = self.get_mockargs()
        loader = NDExNeSTLoader(mockargs)
        self.assertEqual((None, None), loader.get_name_and_genes_from_node(example_node))

    def test_name_and_genes_from_node_raw(self):
        example_node = self.get_example_nest_node()
        mockargs = self.get_mockargs()
        loader = NDExNeSTLoader(mockargs)
        name, gene_list = loader.get_name_and_genes_from_node(example_node)
        self.assertEqual('AKT1 activation', name)
        self.assertEqual(['AKT1', 'CTNNB1', 'EGF',
                          'EGFR', 'ILK', 'JADE1',
                          'NF2', 'PPL', 'PTEN',
                          'SLC9A3R1', 'STUB1',
                          'VIM', 'YWHAZ'], gene_list)

    def test_get_style_from_network(self):
        mockargs = self.get_mockargs()
        loader = NDExNeSTLoader(mockargs)
        self.assertTrue(isinstance(loader.get_style_from_network(),
                                   dict))

    def test_add_assembly_attributes_as_net_attributes(self):
        example_node = self.get_example_nest_node()
        mockargs = self.get_mockargs()
        loader = NDExNeSTLoader(mockargs)
        net_attrs = {}
        loader._add_assembly_attributes_as_net_attributes(example_node,
                                                          net_attrs=net_attrs)
        self.assertEqual(21, len(net_attrs))
        for attr in ['n', 'name', 'Annotation',
                     'Size', 'Size-Log', 'Genes']:
            self.assertFalse(attr in net_attrs)

        self.assertEqual(1, net_attrs['adjusted  p-value'])

    def test_get_network_url_server_none(self):
        mockargs = self.get_mockargs()
        loader = NDExNeSTLoader(mockargs)
        self.assertEqual('https://www.ndexbio.org/viewer/networks/12345',
                         loader._get_network_url('12345'))

    def test_get_network_url_server_isprod(self):
        mockargs = self.get_mockargs()
        loader = NDExNeSTLoader(mockargs)
        loader._server = 'public.ndexbio.org'
        self.assertEqual('https://www.ndexbio.org/viewer/networks/12345',
                         loader._get_network_url('12345'))

    def test_get_network_url_server_istest(self):
        mockargs = self.get_mockargs()
        loader = NDExNeSTLoader(mockargs)
        loader._server = 'test.ndexbio.org'
        self.assertEqual('https://test.ndexbio.org/viewer/networks/12345',
                         loader._get_network_url('12345'))

    def test_get_score_map_edge_attributes(self):
        mockargs = self.get_mockargs()
        loader = NDExNeSTLoader(mockargs)

        # try with empty dict
        self.assertEqual({}, loader._get_score_map_edge_attributes({}))

        ias_attrs = {ndexloadnestsubnetworks.PROTEIN_ONE: 'foo',
                     ndexloadnestsubnetworks.PROTEIN_TWO: 'blah'}

        # try with only protein one and protein two
        self.assertEqual({},
                         loader._get_score_map_edge_attributes(ias_attrs))

        # try with valid attr
        ias_attrs['x'] = 1
        self.assertEqual({'x': 1},
                         loader._get_score_map_edge_attributes(ias_attrs))

    def test_update_network_attributes(self):
        mockargs = self.get_mockargs()
        loader = NDExNeSTLoader(mockargs)
        net_attrs ={'Description': 'hi'}
        loader._update_network_attributes(name='foo',
                                          net_attrs=net_attrs)
        self.assertEqual('foo', net_attrs['name'])
        self.assertTrue(net_attrs['description'].startswith('<p>This'))
        self.assertEqual('20211001', net_attrs['version'])
        self.assertTrue(net_attrs['reference'].startswith('<p>Zh'))

    def test_save_update_network_dryrun_save(self):
        mockargs = self.get_mockargs()
        mockargs.dryrun = True
        loader = NDExNeSTLoader(mockargs)
        net_attrs = {'name': 'x'}
        loader._ndexclient = MagicMock()
        loader._ndexclient.save_new_cx2_network = MagicMock()
        loader._ndexclient.update_cx2_network = MagicMock()
        loader._save_update_network(net_attrs=net_attrs,
                                    network_dict={},
                                    sub_network='foo')

        loader._ndexclient.save_new_cx2_network.assert_not_called()
        loader._ndexclient.update_cx2_network.assert_not_called()

    def test_save_update_network_save(self):
        mockargs = self.get_mockargs()
        mockargs.dryrun = False
        loader = NDExNeSTLoader(mockargs)
        net_attrs = {'name': 'x'}
        sub_network = MagicMock()
        sub_network.to_cx2 = MagicMock(return_value='foo')
        loader._ndexclient = MagicMock()
        loader._ndexclient.save_new_cx2_network = MagicMock()
        loader._ndexclient.update_cx2_network = MagicMock()
        loader._save_update_network(net_attrs=net_attrs,
                                    network_dict={},
                                    sub_network=sub_network)

        sub_network.to_cx2.assert_called_with()
        loader._ndexclient.save_new_cx2_network.assert_called_with('foo',
                                                                   visibility='PUBLIC')
        loader._ndexclient.update_cx2_network.assert_not_called()

    def test_save_update_network_dryrun_update(self):
        mockargs = self.get_mockargs()
        mockargs.dryrun = True
        loader = NDExNeSTLoader(mockargs)
        net_attrs = {'name': 'x'}
        loader._ndexclient = MagicMock()
        loader._ndexclient.save_new_cx2_network = MagicMock()
        loader._save_update_network(net_attrs=net_attrs,
                                    network_dict={'x': '12345'},
                                    sub_network='foo')

        loader._ndexclient.save_new_cx2_network.assert_not_called()
        loader._ndexclient.update_cx2_network.assert_not_called()

    def test_save_update_network_update(self):
        mockargs = self.get_mockargs()
        mockargs.dryrun = False
        loader = NDExNeSTLoader(mockargs)
        net_attrs = {'name': 'x'}
        sub_network = MagicMock()
        sub_network.to_cx2 = MagicMock(return_value='foo')
        loader._ndexclient = MagicMock()
        loader._ndexclient.save_new_cx2_network = MagicMock()
        loader._ndexclient.update_cx2_network = MagicMock()
        loader._save_update_network(net_attrs=net_attrs,
                                    network_dict={'x': '12345'},
                                    sub_network=sub_network)

        sub_network.to_cx2.assert_called_with()
        loader._ndexclient.save_new_cx2_network.assert_not_called()
        c_args = loader._ndexclient.update_cx2_network.call_args.args
        self.assertEqual('12345', c_args[1])
        self.assertTrue(isinstance(c_args[0], io.BytesIO))
