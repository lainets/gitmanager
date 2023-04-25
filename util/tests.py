import os.path

from django.conf import settings
from django.test import TestCase, override_settings

from .git import get_diff_names, git_call


# commits in the test git dir
commits = {
    "master": [
        "1020b05551acd01f1baf2618a6cdad079b72247c",
        "7466cd6b25b14bffa81da961a1fe31fde90f96cb",
        "38d1ddd300f2bde3337e64c4a4ad8d40095c5ac1",
        "1bfd20062367f1e1606af258c3961870f02e5184",
    ],
    "otherbranch": [
        "1020b05551acd01f1baf2618a6cdad079b72247c",
        "7fdd342b16edda0639e31a54642deac16c6cbc04",
        "1037396259bd979d097cd98102e688d95cea0441",
    ]
}


@override_settings(
    GIT_OPTIONS=["--git-dir", "dotgit"],
)
class GitTest(TestCase):
    def setUp(self):
        self.git_dir = os.path.join(settings.TESTDATADIR, "gittest")

    def test_git_call(self) -> None:
        nonexistent_response = "Git nonexistentcommand: returncode: 1\nstdout: git: 'nonexistentcommand' is not a git command. See 'git --help'.\n\n"
        success, response = git_call(self.git_dir, "nonexistentcommand", ["nonexistentcommand"], include_cmd_string = False)
        self.assertFalse(success)
        self.assertEqual(response, nonexistent_response)

        success, response = git_call(self.git_dir, "nonexistentcommand", ["nonexistentcommand"], include_cmd_string = True)
        self.assertFalse(success)
        self.assertEqual(response, "git nonexistentcommand\n" + nonexistent_response)

        success, response = git_call(self.git_dir, "rev-parse", ["rev-parse", "HEAD"], include_cmd_string = False)
        self.assertTrue(success)
        self.assertRegex(response, "[0-9a-z]{40}\n")

        success, response = git_call(self.git_dir, "rev-parse", ["rev-parse", "HEAD"], include_cmd_string = True)
        self.assertTrue(success)
        self.assertRegex(response, "git rev-parse HEAD\n[0-9a-z]{40}\n")

    def test_diff_names(self) -> None:
        _, changed_files = get_diff_names(self.git_dir, commits["master"][0])
        self.assertIsNotNone(changed_files)
        self.assertEqual(set(changed_files or []), {"file1"})

        _, changed_files = get_diff_names(self.git_dir, commits["master"][1])
        self.assertIsNotNone(changed_files)
        self.assertEqual(set(changed_files or []), {"file1", "file2"})

        _, changed_files = get_diff_names(self.git_dir, commits["master"][2])
        self.assertIsNotNone(changed_files)
        self.assertEqual(set(changed_files or []), {"file2"})

        _, changed_files = get_diff_names(self.git_dir, commits["otherbranch"][1])
        self.assertIsNotNone(changed_files)
        self.assertEqual(set(changed_files or []), {"file1", "file3"})

        _, changed_files = get_diff_names(self.git_dir, commits["otherbranch"][2])
        self.assertIsNotNone(changed_files)
        self.assertEqual(set(changed_files or []), {"file3"})

        _, changed_files = get_diff_names(self.git_dir, "nonexistentcommit")
        self.assertIsNone(changed_files)
