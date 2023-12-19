#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Tests for `ndexnestloader` package."""

import os
import tempfile
import shutil
from unittest.mock import MagicMock

import unittest
from ndexnestloader.ndexloadnestsubnetworks import NDExNeSTLoader
from ndex2.client import Ndex2

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

    def test_get_ias_score_map_filepath_with_50rows(self):
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
