import logging
from pathlib import Path
import subprocess

from django.apps import AppConfig as DjangoAppConfig
from django.conf import settings


LOGGER = logging.getLogger('main')
ssh_key = None


class AppConfig(DjangoAppConfig):
    name="builder"
    def ready(self) -> None:
        global ssh_key

        if not Path(settings.SSH_KEY_PATH).exists():
            LOGGER.info(f"Generating SSH key in {settings.SSH_KEY_PATH}")
            Path(settings.SSH_KEY_PATH).parent.mkdir(parents=True, exist_ok=True)
            process = subprocess.run(["ssh-keygen", "-t", "ecdsa", "-b 521", "-q", "-N", "", "-f", settings.SSH_KEY_PATH], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, encoding='utf8')
            if process.returncode != 0:
                raise Exception("Failed to generate ssh key:\n" + process.stdout)

        ssh_key = open(settings.SSH_KEY_PATH + ".pub").read()

        return super().ready()