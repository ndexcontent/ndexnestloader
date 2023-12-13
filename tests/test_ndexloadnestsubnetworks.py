#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Tests for `ndexnestloader` package."""

import os
import tempfile
import shutil

import unittest
from ndexutil.config import NDExUtilConfig
from ndexnestloader import ndexloadnestsubnetworks


class TestNdexnestloader(unittest.TestCase):
    """Tests for `ndexnestloader` package."""

    def setUp(self):
        """Set up test fixtures, if any."""

    def tearDown(self):
        """Tear down test fixtures, if any."""

    def test_parse_arguments(self):
        """Tests parse arguments"""
        res = ndexloadnestsubnetworks._parse_arguments('hi', [])

        self.assertEqual(res.profile, 'ndexnestloader')
        self.assertEqual(res.verbose, 1)
        self.assertEqual(res.logconf, None)
        self.assertEqual(res.conf, None)

        someargs = ['-vv','--conf', 'foo', '--logconf', 'hi',
                    '--profile', 'myprofy']
        res = ndexloadnestsubnetworks._parse_arguments('hi', someargs)

        self.assertEqual(res.profile, 'myprofy')
        self.assertEqual(res.verbose, 3)
        self.assertEqual(res.logconf, 'hi')
        self.assertEqual(res.conf, 'foo')


    def test_setup_logging(self):
        """ Tests logging setup"""
        try:
            ndexloadnestsubnetworks._setup_logging(None)
            self.fail('Expected AttributeError')
        except AttributeError:
            pass

        # args.logconf is None
        res = ndexloadnestsubnetworks._parse_arguments('hi', [])
        ndexloadnestsubnetworks._setup_logging(res)

        # args.logconf set to a file
        try:
            temp_dir = tempfile.mkdtemp()

            logfile = os.path.join(temp_dir, 'log.conf')
            with open(logfile, 'w') as f:
                f.write("""[loggers]
keys=root

[handlers]
keys=stream_handler

[formatters]
keys=formatter

[logger_root]
level=DEBUG
handlers=stream_handler

[handler_stream_handler]
class=StreamHandler
level=DEBUG
formatter=formatter
args=(sys.stderr,)

[formatter_formatter]
format=%(asctime)s %(name)-12s %(levelname)-8s %(message)s""")

            res = ndexloadnestsubnetworks._parse_arguments('hi', ['--logconf',
                                                                       logfile])
            ndexloadnestsubnetworks._setup_logging(res)

        finally:
            shutil.rmtree(temp_dir)

    def test_main(self):
        """Tests main function"""

        # try where loading config is failure
        try:
            temp_dir = tempfile.mkdtemp()
            confile = os.path.join(temp_dir, 'some.conf')
            with open(confile, 'w') as f:
                f.write("""[hi]
                {user} = bob
                {pw} = smith
                {server} = dev.ndexbio.org""".format(user=NDExUtilConfig.USER,
                                                     pw=NDExUtilConfig.PASSWORD,
                                                     server=NDExUtilConfig.SERVER))
            res = ndexloadnestsubnetworks.main(['myprog.py', '--conf',
                                                     confile, '--profile',
                                                     'hi'])
            self.assertEqual(res, 2)
        finally:
            shutil.rmtree(temp_dir)
