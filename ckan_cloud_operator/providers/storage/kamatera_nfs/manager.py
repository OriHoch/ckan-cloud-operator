#### standard provider code ####

# import the correct PROVIDER_SUBMODULE and PROVIDER_ID constants for your provider
from .constants import PROVIDER_ID
from ..constants import PROVIDER_SUBMODULE

# define common provider functions based on the constants
from ckan_cloud_operator.providers import manager as providers_manager
def _get_resource_name(suffix=None): return providers_manager.get_resource_name(PROVIDER_SUBMODULE, PROVIDER_ID, suffix=suffix)
def _get_resource_labels(for_deployment=False, suffix=None): return providers_manager.get_resource_labels(PROVIDER_SUBMODULE, PROVIDER_ID, for_deployment=for_deployment, suffix=suffix)
def _get_resource_annotations(suffix=None): return providers_manager.get_resource_annotations(PROVIDER_SUBMODULE, PROVIDER_ID, suffix=suffix)
def _set_provider(): providers_manager.set_provider(PROVIDER_SUBMODULE, PROVIDER_ID)
def _config_set(key=None, value=None, values=None, namespace=None, is_secret=False, suffix=None): providers_manager.config_set(PROVIDER_SUBMODULE, PROVIDER_ID, key=key, value=value, values=values, namespace=namespace, is_secret=is_secret, suffix=suffix)
def _config_get(key=None, default=None, required=False, namespace=None, is_secret=False, suffix=None): return providers_manager.config_get(PROVIDER_SUBMODULE, PROVIDER_ID, key=key, default=default, required=required, namespace=namespace, is_secret=is_secret, suffix=suffix)
def _config_interactive_set(default_values, namespace=None, is_secret=False, suffix=None, from_file=False, interactive=False): providers_manager.config_interactive_set(PROVIDER_SUBMODULE, PROVIDER_ID, default_values, namespace, is_secret, suffix, from_file, interactive)

################################
# custom provider code starts here
#

import subprocess
from ckan_cloud_operator.providers.cluster.kamatera import manager as kamatera_manager


def initialize(interactive=False, storage_suffix=None, use_existing_disk_name=None, dry_run=False):
    if not interactive:
        raise NotImplementedError('non-interactive initialization is not supported')
    if kamatera_manager.ssh_management_machine('--', 'systemctl status nfs-kernel-server') != 0:
        for line in [
            "apt install -y nfs-kernel-server",
            "mkdir -p /srv/default",
            "echo Hello from Kamatera! > /srv/default/hello.txt",
            "chown -R nobody:nogroup /srv/default/",
            "chmod 777 /srv/default/",
            "echo '/srv/default 172.16.0.0/23(rw,sync,no_subtree_check)' > /etc/exports",
            "echo exportfs -a",
            "systemctl restart nfs-kernel-server"
        ]:
            assert kamatera_manager.ssh_management_machine('--', line) == 0, 'failed to run line: ' + line
    ifconfig = kamatera_manager.ssh_management_machine('--', 'ifconfig eth1 | grep "inet "', check_output=True).decode()
    internal_ip = ifconfig.split('inet ')[1].split(' ')[0]
    _config_interactive_set({
        'nfs-internal-ip': internal_ip,
        'nfs-srv-dir': '/srv/default'
    }, interactive=interactive)
    subprocess.check_call(['helm', 'repo', 'add', 'stable', 'https://kubernetes-charts.storage.googleapis.com/'])
    subprocess.check_call(['helm', 'repo', 'update'])
    subprocess.check_call(['helm', 'install', '-n', 'default',
                           '--set', 'nfs.server=' + _config_get('nfs-internal-ip'),
                           '--set', 'nfs.path=' + _config_get('nfs-srv-dir'),
                           'nfs-client-provisioner', 'stable/nfs-client-provisioner'])
