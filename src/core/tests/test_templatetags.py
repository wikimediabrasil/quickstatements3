from django.test import TestCase

from core.factories import BatchFactory
from core.parsers.v1 import V1CommandParser
from core.templatetags.quickstatements import datavalue_display


class DatavalueDisplayEscapeTests(TestCase):
    def command(self, text):
        batch = BatchFactory.load_from_parser(V1CommandParser(), "Test", "user", text)
        return batch.commands()[0]

    def test_string_is_escaped(self):
        command = self.command('Q100999239|P1810|"Campos-Serrano, Alicia <antropologa>"')
        html = datavalue_display(command, command.json["value"])
        self.assertIn("Campos-Serrano, Alicia &lt;antropologa&gt;", html)
        self.assertNotIn("<antropologa>", html)

    def test_qualifier_string_is_escaped(self):
        command = self.command(
            'Q100999239|P396|"LIGV050594"|P1810|"Campos-Serrano, Alicia <antropologa>"'
        )
        html = datavalue_display(command, command.json["qualifiers"][0]["value"])
        self.assertIn("&lt;antropologa&gt;", html)

    def test_monolingualtext_is_escaped(self):
        command = self.command("Q1|P1476|en:\"<script>alert(1)</script>\"")
        html = datavalue_display(command, command.json["value"])
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", html)
        self.assertNotIn("<script>", html)

    def test_label_is_escaped(self):
        command = self.command('Q1|Len|"<b>bold</b>"')
        html = datavalue_display(command, command.json["value"])
        self.assertIn("&lt;b&gt;bold&lt;/b&gt;", html)
