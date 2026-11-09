"""Offline G4 candidate private subdirectories, never volume-root chmod."""
import os
from pathlib import Path
import stat
from tempfile import TemporaryDirectory
import unittest
from unittest import mock

from fortis_approvals.g4_volume_repair import (
    ROOTS, initialize, check_write, verify_metadata, main)
from fortis_approvals.g4_secret_bootstrap import DEST


class G4SubdirectoryTests(unittest.TestCase):
    def test_secret_and_state_use_subdirectory_below_volume_root(self):
        self.assertEqual(DEST, Path('/run/g4-token/private/sonar_token'))
        self.assertEqual(ROOTS['state'] / 'private', Path('/state/private'))
        self.assertEqual(ROOTS['token'] / 'private', DEST.parent)

    def test_refuses_to_adopt_existing_unknown_volume_contents(self):
        with TemporaryDirectory(prefix='fortis-g4-subdirectory-') as temp:
            root=Path(temp)
            (root/'G2-do-not-touch.sqlite').write_bytes(b'other-owner-data')
            with mock.patch('fortis_approvals.g4_volume_repair.os.geteuid',return_value=0):
                with self.assertRaisesRegex(ValueError,'NOT_EMPTY_UNKNOWN_CONTENT'):
                    initialize(root)
            self.assertEqual((root/'G2-do-not-touch.sqlite').read_bytes(),b'other-owner-data')
            self.assertFalse((root/'private').exists())

    def test_refuses_untrusted_symlink_or_externally_created_private(self):
        with TemporaryDirectory(prefix='fortis-g4-subdirectory-') as temp:
            root=Path(temp)
            other=root/'outside';other.mkdir()
            (root/'private').symlink_to(other)
            with mock.patch('fortis_approvals.g4_volume_repair.os.geteuid',return_value=0):
                with self.assertRaisesRegex(ValueError,'SYMLINK_DENIED'):
                    initialize(root)
            self.assertTrue((root/'private').is_symlink())
            (root/'private').unlink()
            (root/'private').mkdir(mode=0o700)
            with mock.patch('fortis_approvals.g4_volume_repair.os.geteuid',return_value=0):
                with self.assertRaisesRegex(ValueError,'PERMISSIONS_INVALID'):
                    initialize(root)

    def test_read_only_test_permission_check_and_ephemeral_write(self):
        with TemporaryDirectory(prefix='fortis-g4-subdirectory-') as temp:
            root=Path(temp)
            private=root/'private';private.mkdir(mode=0o700)
            with self.assertRaisesRegex(ValueError,'G4_PRIVATE_PERMISSIONS_INVALID'):
                verify_metadata(private)
            with self.assertRaisesRegex(ValueError,'G4_UNPRIVILEGED_VERIFICATION_REQUIRED'):
                check_write(root)
            # Mock uid/metadata only, still verify mkstemp+hardlink and cleanup
            # use the actual test account-owned private temporary directory.
            with mock.patch('fortis_approvals.g4_volume_repair.os.geteuid',return_value=10001):
                with mock.patch('fortis_approvals.g4_volume_repair.verify_metadata'):
                    self.assertEqual(check_write(root),'WRITE_AND_LINK_OK')
            self.assertEqual(list(private.iterdir()),[])

    def test_non_root_initializer_does_not_write(self):
        with TemporaryDirectory(prefix='fortis-g4-subdirectory-') as temp:
            root=Path(temp)
            with mock.patch('fortis_approvals.g4_volume_repair.os.geteuid',return_value=10001):
                with self.assertRaisesRegex(ValueError,'PRIVILEGED_BOOTSTRAP_REQUIRED'):
                    initialize(root)
            self.assertEqual(list(root.iterdir()),[])

    def test_init_requires_explicit_mounted_volume(self):
        from io import StringIO
        from contextlib import redirect_stderr
        sink=StringIO()
        with mock.patch('fortis_approvals.g4_volume_repair._mounted',return_value=False):
            with redirect_stderr(sink):
                self.assertEqual(main(['initialize','state']),3)
        self.assertIn('G4_PRIVATE_STATE_CHECK_FAILED',sink.getvalue())


if __name__=='__main__':
    unittest.main()
