#### standard provider code ####

from .constants import PROVIDER_ID
from ..constants import PROVIDER_SUBMODULE

# define common provider functions based on the constants
from ckan_cloud_operator.providers import manager as providers_manager
def _get_resource_name(suffix=None): return providers_manager.get_resource_name(PROVIDER_SUBMODULE, PROVIDER_ID, suffix=suffix)
def _get_resource_labels(for_deployment=False): return providers_manager.get_resource_labels(PROVIDER_SUBMODULE, PROVIDER_ID, for_deployment=for_deployment)
def _get_resource_annotations(suffix=None): return providers_manager.get_resource_annotations(PROVIDER_SUBMODULE, PROVIDER_ID, suffix=suffix)
def _set_provider(): providers_manager.set_provider(PROVIDER_SUBMODULE, PROVIDER_ID)
def _config_set(key=None, value=None, values=None, namespace=None, is_secret=False, suffix=None): providers_manager.config_set(PROVIDER_SUBMODULE, PROVIDER_ID, key=key, value=value, values=values, namespace=namespace, is_secret=is_secret, suffix=suffix)
def _config_get(key=None, default=None, required=False, namespace=None, is_secret=False, suffix=None): return providers_manager.config_get(PROVIDER_SUBMODULE, PROVIDER_ID, key=key, default=default, required=required, namespace=namespace, is_secret=is_secret, suffix=suffix)
def _config_interactive_set(default_values, namespace=None, is_secret=False, suffix=None, from_file=False): providers_manager.config_interactive_set(PROVIDER_SUBMODULE, PROVIDER_ID, default_values, namespace, is_secret, suffix, from_file)

################################
# custom provider code starts here
#

import subprocess
from ckan_cloud_operator import cloudflare
from ckan_cloud_operator.routers.routes import manager as routes_manager
from ckan_cloud_operator import kubectl
from .management import manager as management_manager


def initialize(interactive=False):
    _set_provider()


def create_management_server(interactive, values):
    management_manager.create_management_server(interactive, values)


def get_management_machine_secrets(key=None):
    return management_manager.get_management_machine_secrets(key=key)


def ssh_management_machine(*args, check_output=False, scp_to_remote_file=None):
    return management_manager.ssh_management_machine(*args, check_output, scp_to_remote_file)


def initialize_docker_registry():
    subprocess.check_call(['helm', 'repo', 'add', 'stable', 'https://kubernetes-charts.storage.googleapis.com/'])
    subprocess.check_call(['helm', 'repo', 'update'])
    _config_interactive_set({
        'docker-registry-username': '',
        'docker-registry-password': ''
    }, is_secret=True)
    htpasswd_secret = subprocess.check_output(['htpasswd', '-Bbn', _config_get('docker-registry-username', is_secret=True), _config_get('docker-registry-password', is_secret=True)]).decode().strip()
    subprocess.check_call(['helm', 'install', '-n', 'default',
                           '--set', 'secrets.htpasswd=' + htpasswd_secret,
                           '--set', 'persistence.enabled=true',
                           '--set', 'persistence.storageClass=nfs-client',
                           '--set', 'persistence.size=20Gi',
                           'docker-registry', 'stable/docker-registry'])


def update_nginx_router(router_name, wait_ready, spec, annotations, routes, dry_run):
    management_secrets = get_management_machine_secrets()
    rancher_subdomain = management_secrets['rancher_sub_domain']
    root_domain = management_secrets['RootDomainName']
    route_subdomains = set()
    for route in routes:
        assert route['spec']['root-domain'] == root_domain
        assert route['spec']['sub-domain'] != rancher_subdomain
        assert route['spec']['sub-domain'] not in route_subdomains
        route_subdomains.add(route['spec']['sub-domain'])
    print('Updating Cloudflare A Records')
    for subdomain in route_subdomains:
        cloudflare.update_a_record(
            management_secrets['CloudflareEmail'], management_secrets['CloudflareApiKey'],
            root_domain,
            subdomain + '.' + root_domain,
            management_secrets['server_public_ip']
        )
    print('Registering certificates')
    ssh_management_machine('certbot', 'certonly',
                           '--agree-tos', '--email', management_secrets['CloudflareEmail'],
                           '--webroot',
                           '-w', '/var/lib/letsencrypt/',
                           '-d', ','.join([f'{s}.{root_domain}' for s in [rancher_subdomain, *route_subdomains]]))
    for route in routes:
        if route['spec']['sub-domain'] in route_subdomains:
            backend_url = routes_manager.get_backend_url(route)
            ssh_management_machine(
                "location / {",
                    f'proxy_pass {backend_url};',
                    "include snippets/http2_proxy.conf;",
                "}",
                scp_to_remote_file=f'/etc/nginx/snippets/{route["spec"]["sub-domain"]}.conf'
            )
            ssh_management_machine(
                "map $http_upgrade $connection_upgrade {",
                    "default Upgrade;",
                    '""      close;',
                "}",
                "server {",
                    "listen 80;",
                    "listen    [::]:80;",
                    f"server_name {route['spec']['sub-domain']}.{root_domain};",
                    "include snippets/letsencrypt.conf;",
                    "return 301 https://$host$request_uri;",
                "}",
                "server {",
                    "listen 443 ssl http2;",
                    "listen [::]:443 ssl http2;",
                    f"server_name {route['spec']['sub-domain']}.{root_domain};",
                    "include snippets/letsencrypt_certs.conf;",
                    "include snippets/ssl.conf;",
                    "include snippets/letsencrypt.conf;",
                    f"include snippets/{route['spec']['sub-domain']}.conf;",
                "}",
                scp_to_remote_file=f'/etc/nginx/sites-enabled/{route["spec"]["sub-domain"]}'
            )
    ssh_management_machine('systemctl reload nginx')


def rancher(*args, context='Default'):
    management_secrets = get_management_machine_secrets()
    subprocess.check_call([
        'rancher', 'login',
        '--token', management_secrets['rancher_bearer_token'],
        management_secrets['rancher_endpoint']
    ])
    subprocess.check_call(['rancher', 'context', 'switch', context])
    subprocess.check_call(['rancher', *args])


def ssh_rancher_nodes(ssh_args):
    for node in kubectl.get('nodes')['items']:
        node_name = node['metadata']['name']
        print()
        print('Running on node ' + node_name)
        print()
        rancher('ssh', node_name, ' '.join(ssh_args))
        print()
        print()
    print('Great Success!')
    print('Ran command on all nodes: "' + ' '.join(ssh_args) + '"')
