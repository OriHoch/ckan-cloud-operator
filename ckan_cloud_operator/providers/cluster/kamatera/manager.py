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
import os
import traceback
from ckan_cloud_operator import cloudflare
from ckan_cloud_operator.routers.routes import manager as routes_manager
from ckan_cloud_operator import kubectl
from ckan_cloud_operator.config import manager as config_manager
from .management import manager as management_manager


def initialize(interactive=False):
    _set_provider()


def create_management_server(interactive, values):
    management_manager.create_management_server(interactive=interactive, values=values)


def get_management_machine_secrets(key=None):
    return management_manager.get_management_machine_secrets(key=key)


def ssh_management_machine(*args, check_output=False, scp_to_remote_file=None):
    return management_manager.ssh_management_machine(*args, check_output=check_output, scp_to_remote_file=scp_to_remote_file)


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
    external_domains = {}
    for route in routes:
        if route['spec']['root-domain'] == root_domain:
            assert route['spec']['sub-domain'] != rancher_subdomain
            assert route['spec']['sub-domain'] not in route_subdomains
            route_subdomains.add(route['spec']['sub-domain'])
        else:
            external_domains.setdefault(route['spec']['root-domain'], set()).add(route['spec']['sub-domain'])
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
    for external_root_domain, external_sub_domains in external_domains.items():
        if ssh_management_machine('ls', f"/etc/nginx/snippets/letsencrypt_certs-{external_root_domain}.conf") != 0:
            ssh_management_machine(
                f"ssl_certificate /etc/letsencrypt/live/{external_root_domain}/fullchain.pem;",
                f"ssl_certificate_key /etc/letsencrypt/live/{external_root_domain}/privkey.pem;",
                f"ssl_trusted_certificate /etc/letsencrypt/live/{external_root_domain}/chain.pem;",
                scp_to_remote_file=f"/etc/nginx/snippets/letsencrypt_certs-{external_root_domain}.conf"
            )
        print('Registering certificates for external root domain ' + external_root_domain)
        print('subdomains = {}'.format(external_sub_domains))
        print('Make sure DNS is configured properly before adding the route!')
        try:
            ssh_management_machine('certbot', 'certonly',
                                   '--agree-tos', '--email', management_secrets['CloudflareEmail'],
                                   '--webroot',
                                   '-w', '/var/lib/letsencrypt/',
                                   '--cert-name', external_root_domain,
                                   '-d', ','.join([f'{s}.{external_root_domain}' for s in external_sub_domains]))
        except Exception:
            traceback.print_exc()
            print('Error registering SSL certificate for external root domain ' + external_root_domain)
    for route in routes:
        if route['spec']['root-domain'] == root_domain:
            snippet_name = route["spec"]["sub-domain"]
            letsencrypt_certs = 'letsencrypt_certs.conf'
        else:
            snippet_name = '{}.{}'.format(route["spec"]["sub-domain"], route['spec']['root-domain'])
            letsencrypt_certs = 'letsencrypt_certs-{}.conf'.format(route['spec']['root-domain'])
        backend_url = routes_manager.get_backend_url(route).strip()
        if not backend_url.startswith('http'):
            backend_url = 'http://' + backend_url
        ssh_management_machine(
            "location / {",
                f"proxy_pass {backend_url};",
                "include snippets/http2_proxy.conf;",
            "}",
            scp_to_remote_file=f'/etc/nginx/snippets/{snippet_name}.conf'
        )
        client_max_body_size = route['spec'].get('client-max-body-size')
        client_max_body_size = f"client_max_body_size {client_max_body_size};" if client_max_body_size else ""
        ssh_management_machine(
            "map $http_upgrade $connection_upgrade {",
                "default Upgrade;",
                '""      close;',
            "}",
            "server {",
                "listen 80;",
                "listen    [::]:80;",
                f"server_name {route['spec']['sub-domain']}.{route['spec']['root-domain']};",
                "include snippets/letsencrypt.conf;",
                "return 301 https://$host$request_uri;",
            "}",
            "server {",
                client_max_body_size,
                "listen 443 ssl http2;",
                "listen [::]:443 ssl http2;",
                f"server_name {route['spec']['sub-domain']}.{route['spec']['root-domain']};",
                f"include snippets/{letsencrypt_certs};",
                "include snippets/ssl.conf;",
                "include snippets/letsencrypt.conf;",
                f"include snippets/{snippet_name}.conf;",
            "}",
            scp_to_remote_file=f'/etc/nginx/sites-enabled/{snippet_name}'
        )
    ssh_management_machine('systemctl reload nginx')


def rancher(*args, context='Default', check_output=False):
    management_secrets = get_management_machine_secrets()
    default_rancher_context_id = _config_get('default-rancher-context-id', is_secret=True)
    if not default_rancher_context_id:
        print('Please set the ID of the Default context in Rancher')
        print('e.g. c-fghij:p-abcde')
        _config_interactive_set({'default-rancher-context-id': None}, is_secret=True)
        default_rancher_context_id = _config_get('default-rancher-context-id', is_secret=True)
    output = None
    try:
        output = subprocess.check_output(' '.join([
            'rancher', 'login', '--context', default_rancher_context_id,
            '--token', management_secrets['rancher_bearer_token'],
            management_secrets['rancher_endpoint']
        ]) + ' 2>&1', shell=True)
        output = subprocess.check_output(' '.join(['rancher', 'context', 'switch', context]) + ' 2>&1', shell=True)
    except Exception:
        print(output)
        raise
    ssh_known_hosts = config_manager.get('ssh_known_hosts', secret_name='cco-kamatera-management-server',
                                         namespace='ckan-cloud-operator', required=False, default=None)
    if ssh_known_hosts:
        os.makedirs('/root/.ssh', exist_ok=True)
        with open('/root/.ssh/known_hosts', 'w') as known_hosts_file:
            known_hosts_file.write(ssh_known_hosts)
    if check_output:
        res = subprocess.check_output(['rancher', *args])
    else:
        subprocess.check_call(['rancher', *args])
        res = None
    if os.path.exists('/root/.ssh/known_hosts'):
        with open('/root/.ssh/known_hosts') as f:
            new_known_hosts = f.read().strip()
        if new_known_hosts != ssh_known_hosts.strip():
            config_manager.set('ssh_known_hosts', new_known_hosts, secret_name='cco-kamatera-management-server', namespace='ckan-cloud-operator')
    return res


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


def get_management_public_ip():
    return management_manager.get_management_public_ip()


def get_nodeport_url(service_name, namespace):
    if not namespace:
        namespace = 'default'
    service = kubectl.get('service', service_name, namespace=namespace)
    node_port = service['spec']['ports'][0]['nodePort']
    node_name = kubectl.get('nodes')['items'][0]['metadata']['name']
    output = rancher('ssh', node_name, 'ifconfig', 'eth1', check_output=True).decode()
    node_ip = output.split(' inet ')[1].split(' ')[0]
    return '{}:{}'.format(node_ip, node_port)
