"""
Tests for pygount source code analysis.
"""
# Copyright (c) 2016, Thomas Aglassinger.
# All rights reserved. Distributed under the BSD License.
import atexit
import os
import tempfile
import unittest

from pygments import lexers, token

from pygount import analysis


class AnalysisTest(unittest.TestCase):
    @staticmethod
    def _test_path(name, suffix='tmp'):
        result = os.path.join(tempfile.gettempdir(), 'pygount_tests_AnalysisTest_' + name + '.' + suffix)
        atexit.register(os.remove, result)
        return result

    def test_can_deline_tokens(self):
        self.assertEqual(
            list(analysis._delined_tokens([(token.Comment, '# a')])),
            [(token.Comment, '# a')]
        )
        self.assertEqual(
            list(analysis._delined_tokens([(token.Comment, '# a\n#  b')])),
            [(token.Comment, '# a\n'), (token.Comment, '#  b')]
        )
        self.assertEqual(
            list(analysis._delined_tokens([(token.Comment, '# a\n#  b\n')])),
            [(token.Comment, '# a\n'), (token.Comment, '#  b\n')]
        )
        self.assertEqual(
            list(analysis._delined_tokens([(token.Comment, '# a\n#  b\n # c\n')])),
            [(token.Comment, '# a\n'), (token.Comment, '#  b\n'), (token.Comment, ' # c\n')]
        )

    def test_can_compute_python_line_parts(self):
        python_lexer = lexers.get_lexer_by_name('python')
        self.assertEqual(
            list(analysis._line_parts(python_lexer, '#')),
            [set('d')]
        )
        self.assertEqual(
            list(analysis._line_parts(python_lexer, "s = 'x'  # x")),
            [set('cds')]
        )

    def test_can_detect_white_text(self):
        python_lexer = lexers.get_lexer_by_name('python')
        self.assertEqual(
            list(analysis._line_parts(python_lexer, '{[()]};')),
            [set()]
        )
        self.assertEqual(
            list(analysis._line_parts(python_lexer, 'pass')),
            [set()]
        )

    def test_can_convert_python_strings_to_comments(self):
        source_code = \
            '#!/bin/python\n' \
            '"Some tool."\n' \
            '#(C) by me\n' \
            'def x():\n' \
            '    "Some function"\n' \
            '    return 1'
        python_lexer = lexers.get_lexer_by_name('python')
        python_tokens = python_lexer.get_tokens(source_code)
        for token_type, token_text in list(analysis._pythonized_comments(analysis._delined_tokens(python_tokens))):
            self.assertNotIn(token_type, token.String, 'token_text=%r' % token_text)

    def test_can_analyze_python(self):
        source_code = \
            '"Some tool."\n' \
            '#!/bin/python\n' \
            '#(C) by me\n' \
            'def x():\n' \
            '    "Some function"\n' \
            '    return "abc"\n'
        python_lexer = lexers.get_lexer_by_name('python')
        actual_line_parts = list(analysis._line_parts(python_lexer, source_code))
        expected_line_parts = [{'d'}, {'d'}, {'d'}, {'c'}, {'d'}, {'c', 's'}]
        self.assertEqual(actual_line_parts, expected_line_parts)

    def test_can_analyze_encoding_error(self):
        test_path = AnalysisTest._test_path('encoding_error', '.py')
        with open(test_path, 'w', encoding='cp1252') as test_file:
            test_file.write('print("\N{EURO SIGN}")')
        source_analysis = analysis.source_analysis(test_path, 'test', encoding='utf-8')
        self.assertEqual(source_analysis.language, 'error')


class EncodingTest(unittest.TestCase):
    _ENCODING_TO_BOM_MAP = dict((encoding, bom) for bom, encoding in analysis._BOM_TO_ENCODING_MAP.items())
    _TEST_CODE = "x = '\u00fd \u20ac'"

    @staticmethod
    def _test_path(name):
        result = os.path.join(tempfile.gettempdir(), 'pygount_tests_EncodingTest_' + name + '.tmp')
        atexit.register(os.remove, result)
        return result

    def _test_can_detect_bom_encoding(self, encoding):
        test_path = EncodingTest._test_path(encoding)
        with open(test_path, 'wb') as test_file:
            if encoding != 'utf-8-sig':
                bom = EncodingTest._ENCODING_TO_BOM_MAP[encoding]
                test_file.write(bom)
            test_file.write(EncodingTest._TEST_CODE.encode(encoding))
        actual_encoding = analysis.encoding_for(test_path)
        self.assertEqual(actual_encoding, encoding)

    def test_can_detect_bom_encodings(self):
        for _, encoding in analysis._BOM_TO_ENCODING_MAP.items():
            self._test_can_detect_bom_encoding(encoding)

    def test_can_detect_plain_encoding(self):
        for encoding in ('cp1252', 'utf-8'):
            test_path = EncodingTest._test_path(encoding)
            with open(test_path, 'w', encoding=encoding) as test_file:
                test_file.write(EncodingTest._TEST_CODE)
            actual_encoding = analysis.encoding_for(test_path)
            self.assertEqual(actual_encoding, encoding)

    def test_can_detect_xml_prolog(self):
        encoding = 'iso-8859-15'
        test_path = EncodingTest._test_path('xml-' + encoding)
        with open(test_path, 'w', encoding=encoding) as test_file:
            xml_code = '<?xml encoding="{0}" standalone="yes"?><some>{1}</some>'.format(
                encoding, EncodingTest._TEST_CODE)
            test_file.write(xml_code)
        actual_encoding = analysis.encoding_for(test_path)
        self.assertEqual(actual_encoding, encoding)

    def test_can_detect_magic_comment(self):
        encoding = 'iso-8859-15'
        test_path = EncodingTest._test_path('magic-' + encoding)
        with open(test_path, 'w', encoding=encoding) as test_file:
            test_file.write('#!/usr/bin/python\n')
            test_file.write('# -*- coding: {0} -*-\n'.format(encoding))
            test_file.write(EncodingTest._TEST_CODE)
        actual_encoding = analysis.encoding_for(test_path)
        self.assertEqual(actual_encoding, encoding)

    def test_can_detect_automatic_encoding_for_empty_source(self):
        test_path = EncodingTest._test_path('empty')
        with open(test_path, 'wb') as _:
            pass  # Write empty file.
        actual_encoding = analysis.encoding_for(test_path)
        self.assertEqual(actual_encoding, 'utf-8')

    def test_can_detect_chardet_encoding(self):
        test_path = __file__
        actual_encoding = analysis.encoding_for(test_path)
        self.assertEqual(actual_encoding, 'utf-8')

    def test_can_use_hardcoded_ending(self):
        test_path = EncodingTest._test_path('hardcoded_cp1252')
        with open(test_path, 'w', encoding='cp1252') as test_file:
            test_file.write('\N{EURO SIGN}')
        actual_encoding = analysis.encoding_for(test_path, 'utf-8')
        self.assertEqual(actual_encoding, 'utf-8')
        # Make sure that we cannot actually read the file using the hardcoded but wrong encoding.
        with open(test_path, 'r', encoding=actual_encoding) as broken_test_file:
            self.assertRaises(UnicodeDecodeError, broken_test_file.read)
