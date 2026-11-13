"""Standalone onboarding instructions — no actual Tk window required."""
import unittest
from unittest.mock import patch
from tools import windows_fictional_gui as gui

class PracticeHelpAcceptance(unittest.TestCase):
    def test_help_is_fictional_and_private(self):
        with patch.object(gui.messagebox,"showinfo") as display:
            root = object()
            gui.show_practice_help(root)
            display.assert_called_once()
            args, kwargs = display.call_args
            self.assertEqual(kwargs["parent"],root)
            text=args[1]
            for phrase in ("Create Practice Case","Open Practice Case",
                           "access codes","made-up information",
                           "second reviewer","uncertain result","Close"):
                self.assertIn(phrase.lower(),text.lower())
            self.assertIn("Never enter real client details",text)
            for phrase in ("Back Up Practice Case", "Restore Practice Backup",
                           "NOT encrypted", "owner code", "NEW, unused file",
                           "Old codes", "Never overwrite"):
                self.assertIn(phrase.lower(), text.lower())

    def test_existing_main_controls_preserved(self):
        from pathlib import Path
        source=(Path(__file__).resolve().parents[1]/
                "tools"/"windows_fictional_gui.py").read_text(encoding="utf-8")
        self.assertIn('tk.Button(root,text="Create Practice Case"',source)
        self.assertIn('tk.Button(root,text="Open Practice Case"',source)
        self.assertIn('tk.Button(root,text="Practice Help"',source)
        self.assertIn('tk.Button(root,text="Close"',source)

if __name__ == "__main__":
    unittest.main()
