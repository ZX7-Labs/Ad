import os
import stat
import sys
import tempfile
import unittest
from pathlib import Path

from studio_next.body_deploy import configure_independent_studio


@unittest.skipUnless(sys.platform=="linux","Host service installer targets Linux")
class SecurePersistentFilmBodyInstallerTests(unittest.TestCase):
    def fixture(self,root):
        base=Path(root)
        repo=base/"trusted-code"
        (repo/"studio_next").mkdir(parents=True)
        (repo/"studio_next"/"body_service.py").write_text("original packaged trusted service")
        return repo

    def test_real_owner_studio_data_token_and_os_service_are_separated(self):
        with tempfile.TemporaryDirectory() as root:
            base=Path(root)
            code=self.fixture(root)
            data=base/"original-workspaces"
            secret=base/"private-config"
            service=base/"user-systemd"
            first=configure_independent_studio(data,code_root=code,
                  config_dir=secret,unit_dir=service,python=sys.executable)
            self.assertTrue(first["configured"])
            self.assertFalse(first["enabled_automatically"])
            self.assertIsNone(first["password_or_api_token"])
            token=secret/"body.env"
            self.assertFalse(token.is_relative_to(data))
            self.assertFalse(token.is_relative_to(code))
            self.assertEqual(stat.S_IMODE(token.stat().st_mode)&0o077,0)
            self.assertIn("ZX7_BODY_API_TOKEN=",token.read_text())
            unit=(service/"zx7-studio-body.service").read_text()
            self.assertIn("127.0.0.1",str(first["host_network_interface"]))
            self.assertIn("--workspace-root",unit)
            self.assertIn("Restart=on-failure",unit)
            previous=token.read_bytes()
            second=configure_independent_studio(data,code_root=code,
                  config_dir=secret,unit_dir=service,python=sys.executable)
            self.assertEqual(previous,token.read_bytes())
            self.assertEqual(first["service_unit"],second["service_unit"])

    def test_fail_if_persistent_project_or_secret_is_inside_git_checkout(self):
        with tempfile.TemporaryDirectory() as root:
            base=Path(root)
            code=self.fixture(root)
            with self.assertRaisesRegex(ValueError,"code checkout"):
                configure_independent_studio(code/"model-output",code_root=code,
                    config_dir=base/"config",unit_dir=base/"unit")
            with self.assertRaisesRegex(ValueError,"backups"):
                configure_independent_studio(base/"data",code_root=code,
                    config_dir=base/"data"/"private-secrets",unit_dir=base/"unit")
            with self.assertRaisesRegex(ValueError,"source control"):
                configure_independent_studio(base/"data",code_root=code,
                    config_dir=code/"keys",unit_dir=base/"unit")

    def test_broken_or_existing_service_symlink_cannot_write_into_outside_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            code=self.fixture(tmp)
            config=root/"config"
            units=root/"units"
            outside=root/"outside-other-owner.service"
            outside.write_bytes(b"unchanged-original-systemd-service")
            units.mkdir()
            service=units/"zx7-studio-body.service"
            service.symlink_to(outside)
            params={"code_root":code,"config_dir":config,"unit_dir":units}
            with self.assertRaisesRegex(ValueError,"symlink"):
                configure_independent_studio(root/"films",**params)
            self.assertEqual(outside.read_bytes(),
                             b"unchanged-original-systemd-service")
            service.unlink()
            missing=root/"unrelated-future-unit.service"
            service.symlink_to(missing)
            with self.assertRaisesRegex(ValueError,"symlink"):
                configure_independent_studio(root/"films",**params)
            self.assertFalse(missing.exists())
            service.unlink()
            proof=configure_independent_studio(root/"films",**params)
            self.assertTrue(proof["configured"])
            self.assertFalse(proof["enabled_automatically"])
            self.assertTrue(service.is_file())
            self.assertFalse(service.is_symlink())

    def test_private_token_and_unit_will_not_be_silently_overwritten(self):
        with tempfile.TemporaryDirectory() as root:
            base=Path(root)
            code=self.fixture(root)
            params={"code_root":code,"config_dir":base/"config",
                    "unit_dir":base/"units"}
            configure_independent_studio(base/"work",**params)
            token=base/"config"/"body.env"
            token.chmod(0o644)
            with self.assertRaisesRegex(ValueError,"readable"):
                configure_independent_studio(base/"work",**params)
            token.chmod(0o600)
            unit=base/"units"/"zx7-studio-body.service"
            unit.write_text("[Service]\nExecStart=/untrusted/example\n")
            with self.assertRaises(FileExistsError):
                configure_independent_studio(base/"work",**params)


if __name__=="__main__":unittest.main()
