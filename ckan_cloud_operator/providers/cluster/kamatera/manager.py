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

from tempfile import NamedTemporaryFile


import os
import json
import datetime
import subprocess
import binascii
import yaml
import sys
from ckan_cloud_operator import cloudflare
from ckan_cloud_operator.config import manager as config_manager


def initialize(interactive=False):
    _set_provider()


def _rundata_init(id):
    if not os.path.exists('.rundata'):
        os.mkdir('.rundata')
    filename = '.rundata/{}.json'.format(id)
    if os.path.isfile(filename):
        with open(filename) as f:
            rundata = json.load(f)
    else:
        rundata = {
            'id': id,
            'created': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'updated': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        with open(filename, 'w') as f:
            json.dump(rundata, f)
    return rundata


def _rundata_save(rundata):
    filename = '.rundata/{}.json'.format(rundata['id'])
    rundata['updated'] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    with open(filename, 'w') as f:
        json.dump(rundata, f, indent=2)
    return rundata


def create_management_server(interactive):
    if not interactive:
        print('non-interactive management server creation is not supported')
        exit(1)
    rundata = _rundata_init('create_management_server')
    if not rundata.get('entered_credentials'):
        print('Enter the Kamatera connection details, press Enter to keep existing / default values')
        print('You can get Kamatera client ID and secret from the Kamatera Console: https://console.kamatera.com')
        for param in ['apiServer', 'apiClientid', 'apiSecret']:
            value = rundata[param] if param in rundata else ''
            if param == 'apiServer' and not value:
                value = 'https://cloudcli.cloudwm.com'
            new_value = input('{}{}: '.format(param, (' ('+value+')') if value else ''))
            if new_value:
                value = new_value
            rundata[param] = value
        assert rundata['apiServer'] and rundata['apiClientid'] and rundata['apiSecret']
        rundata['entered_credentials'] = True
        print(_rundata_save(rundata))
    if not rundata.get('downloaded_cloudcli'):
        print('Downloaidng cloudcli')
        subprocess.check_call('curl https://cloudcli.cloudwm.com/binaries/latest/cloudcli-linux-amd64.tar.gz -o cloudcli-linux-amd64.tar.gz', shell=True)
        subprocess.check_call('tar -xzvf cloudcli-linux-amd64.tar.gz', shell=True)
        rundata['downloaded_cloudcli'] = True
        print(_rundata_save(rundata))
    if not rundata.get('entered_domain_name'):
        print('Enter domain settings')
        print('You must have a domain name connected to a Cloudflare account')
        print('You should provide API keys to cloudflare which have permissions to modify DNS records for this domain')
        for param, default in [
            ('RootDomainName', ''),
            ('CloudflareEmail', ''),
            ('CloudflareApiKey', ''),
        ]:
            value = rundata[param] if param in rundata else default
            new_value = input('{}{}: '.format(param, (' ('+value+')') if value else ''))
            if new_value:
                value = new_value
            rundata[param] = value
        rundata['entered_domain_name'] = True
        print(_rundata_save(rundata))
    if not rundata.get('entered_server_args'):
        print('Enter server settings')
        print('You can accept defaults, or check Kamatera Web UI / docs for available values')
        print('Make sure the selected Datacenter matches the datacenter of the private network you created')
        for param, default in [
            ('PrivateNetworkName', ''),
            ('Datacenter (must match private network datacenter)', 'EU'),
            ('RAM', '4096'),
            ('CPU', '2B'),
            ('DiskSizeGB', '30')
        ]:
            value = rundata[param] if param in rundata else default
            new_value = input('{}{}: '.format(param, (' ('+value+')') if value else ''))
            if new_value:
                value = new_value
            rundata[param] = value
        rundata['entered_server_args'] = True
        print(_rundata_save(rundata))
    if not rundata.get('entered_server_name'):
        print('Enter the management server name')
        print('E.g. my-cluster-management')
        rundata['entered_server_name'] = input('server name: ')
        print(_rundata_save(rundata))
    if not rundata.get('generated_password'):
        rundata['generated_password'] = 'Aa'+binascii.hexlify(os.urandom(6)).decode() + '!'
        print(_rundata_save(rundata))
    cloudcli_connection_args = '--api-clientid {clientid} --api-secret {secret} --api-server {server}'.format(
        clientid=rundata['apiClientid'], secret=rundata['apiSecret'], server=rundata['apiServer'], )
    if not rundata.get('server_created'):
        print('Creating server...')
        subprocess.check_call('./cloudcli init {cloudcli_connection_args} && ./cloudcli server create --wait {cloudcli_connection_args} --name {name} --datacenter {datacenter} --image {image} --cpu {cpu} --ram {ram} --disk {disk} --network name=wan --network name={networkname} --password {password}'.format(
            cloudcli_connection_args=cloudcli_connection_args,
            name=rundata['entered_server_name'],
            datacenter=rundata['Datacenter (must match private network datacenter)'],
            image='ubuntu_server_18.04_64-bit',
            cpu=rundata['CPU'],
            ram=rundata['RAM'],
            disk='size=' + str(rundata['DiskSizeGB']),
            networkname=rundata['PrivateNetworkName'],
            password=rundata['generated_password']
        ), shell=True)
        rundata['server_created'] = True
        print(_rundata_save(rundata))
    if not rundata.get('server_public_ip'):
        rundata['server_info'] = json.loads(subprocess.check_output('./cloudcli server info {cloudcli_connection_args} --name {name} --format json'.format(
            cloudcli_connection_args=cloudcli_connection_args,
            name=rundata['entered_server_name']
        ), shell=True))
        for network in rundata['server_info'][0]['networks']:
            if network['network'].startswith('wan'):
                rundata['server_public_ip'] = network['ips'][0]
                break
        assert rundata.get('server_public_ip')
        print(_rundata_save(rundata))
    print('management server public IP: {}'.format(rundata.get('server_public_ip')))
    if not rundata.get('ssh_key'):
        subprocess.check_call('ssh-keygen -t rsa -b 4096 -C "{}" -f .rundata/management_server_id_rsa -N ""'.format(rundata['entered_server_name']), shell=True)
        rundata['ssh_key'] = '.rundata/management_server_id_rsa'
        print(_rundata_save(rundata))
    if not rundata.get('set_ssh_key_on_server'):
        subprocess.check_call('./cloudcli server sshkey {cloudcli_connection_args} --name {name} --password {password} --public-key {public_key}'.format(
            cloudcli_connection_args=cloudcli_connection_args,
            name=rundata['entered_server_name'],
            public_key='.rundata/management_server_id_rsa.pub',
            password=rundata['generated_password']
        ), shell=True)
        rundata['set_ssh_key_on_server'] = True
        print(_rundata_save(rundata))

    def ssh_check_call(cmd):
        cmd = 'chmod 400 .rundata/management_server_id_rsa && ssh -i .rundata/management_server_id_rsa root@{} \'{}\''.format(rundata['server_public_ip'], cmd)
        subprocess.check_call(cmd, shell=True)

    def ssh_getstatusoutput(cmd):
        cmd = 'chmod 400 .rundata/management_server_id_rsa && ssh -i .rundata/management_server_id_rsa root@{} \'{}\''.format(rundata['server_public_ip'], cmd)
        return subprocess.getstatusoutput(cmd)

    def ssh_copy_to_server(local_file, remote_file):
        cmd = 'chmod 400 .rundata/management_server_id_rsa && scp -i .rundata/management_server_id_rsa {} root@{}:{} '.format(
            local_file,
            rundata['server_public_ip'],
            remote_file
        )
        subprocess.check_call(cmd, shell=True)

    exit_code, machine_rundata = ssh_getstatusoutput('cat .rundata')
    if exit_code != 0:
        machine_rundata = 'CREATED:{}'.format(datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        ssh_check_call('echo "{}" > .rundata'.format(machine_rundata))
    print(machine_rundata)

    if 'INSTALLED_NGINX_SSL' not in machine_rundata:
        installation_script = """
        apt update -y &&\
        apt install -y nginx software-properties-common &&\
        add-apt-repository ppa:certbot/certbot &&\
        apt-get update &&\
        apt-get install -y python-certbot-nginx &&\
        if [ -e /etc/ssl/certs/dhparam.pem ]; then warning Ephemeral Diffie-Hellman key already exists at /etc/ssl/certs/dhparam.pem - delete to recreate
        else info Generating Ephemeral Diffie-Hellman key && openssl dhparam -out /etc/ssl/certs/dhparam.pem 2048; fi &&\
        mkdir -p /var/lib/letsencrypt/.well-known &&\
        chgrp www-data /var/lib/letsencrypt &&\
        chmod g+s /var/lib/letsencrypt
        """
        ssh_check_call(installation_script)
        ssh_check_call('echo "INSTALLED_NGINX_SSL:{}" >> .rundata'.format(datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')))

    if 'CREATED_NGINX_CONFIGS' not in machine_rundata:
        with open('.rundata/tmp_nginx_config', 'w') as f:
            f.write("""location ^~ /.well-known/acme-challenge/ {
  allow all;
  root /var/lib/letsencrypt/;
  default_type "text/plain";
  try_files $uri =404;
}""")
        ssh_copy_to_server('.rundata/tmp_nginx_config', '/etc/nginx/snippets/letsencrypt.conf')
        with open('.rundata/tmp_nginx_config', 'w') as f:
            f.write("""ssl_dhparam /etc/ssl/certs/dhparam.pem;
ssl_session_timeout 1d;
ssl_session_cache shared:SSL:50m;
ssl_session_tickets off;
ssl_protocols TLSv1 TLSv1.1 TLSv1.2;
# recommended cipher suite for modern browsers
ssl_ciphers 'EECDH+AESGCM:EDH+AESGCM:AES256+EECDH:AES256+EDH';
# cipher suite for backwards compatibility (IE6/windows XP)
# ssl_ciphers 'ECDHE-ECDSA-CHACHA20-POLY1305:ECDHE-RSA-CHACHA20-POLY1305:ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384:DHE-RSA-AES128-GCM-SHA256:DHE-RSA-AES256-GCM-SHA384:ECDHE-ECDSA-AES128-SHA256:ECDHE-RSA-AES128-SHA256:ECDHE-ECDSA-AES128-SHA:ECDHE-RSA-AES256-SHA384:ECDHE-RSA-AES128-SHA:ECDHE-ECDSA-AES256-SHA384:ECDHE-ECDSA-AES256-SHA:ECDHE-RSA-AES256-SHA:DHE-RSA-AES128-SHA256:DHE-RSA-AES128-SHA:DHE-RSA-AES256-SHA256:DHE-RSA-AES256-SHA:ECDHE-ECDSA-DES-CBC3-SHA:ECDHE-RSA-DES-CBC3-SHA:EDH-RSA-DES-CBC3-SHA:AES128-GCM-SHA256:AES256-GCM-SHA384:AES128-SHA256:AES256-SHA256:AES128-SHA:AES256-SHA:DES-CBC3-SHA:!DSS';
ssl_prefer_server_ciphers on;
ssl_stapling on;
ssl_stapling_verify on;
resolver 8.8.8.8 8.8.4.4 valid=300s;
resolver_timeout 30s;
add_header Strict-Transport-Security "max-age=15768000; includeSubdomains; preload";
add_header X-Frame-Options SAMEORIGIN;
add_header X-Content-Type-Options nosniff;""")
        ssh_copy_to_server('.rundata/tmp_nginx_config', '/etc/nginx/snippets/ssl.conf')
        with open('.rundata/tmp_nginx_config', 'w') as f:
            f.write("""proxy_set_header X-Forwarded-For $remote_addr;
proxy_set_header Host $http_host;
proxy_set_header X-Forwarded-Proto $scheme;
proxy_set_header X-Forwarded-Port $server_port;
proxy_http_version 1.1;
proxy_set_header Upgrade $http_upgrade;
proxy_set_header Connection $connection_upgrade;
proxy_read_timeout 900s;""")
        ssh_copy_to_server('.rundata/tmp_nginx_config', '/etc/nginx/snippets/http2_proxy.conf')
        ssh_check_call('rm -f /etc/nginx/sites-enabled/*')
        with open('.rundata/tmp_nginx_config', 'w') as f:
            f.write("""
map $http_upgrade $connection_upgrade {
    default Upgrade;
    ""      close;
}
server {
  listen 80;
  server_name _;
  include snippets/letsencrypt.conf;
  location / {
      return 200 "it works!";
      add_header Content-Type text/plain;
  }
}""")
        ssh_copy_to_server('.rundata/tmp_nginx_config', '/etc/nginx/sites-enabled/default')
        ssh_check_call('echo "CREATED_NGINX_CONFIGS:{}" >> .rundata'.format(datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')))

    if 'FINALIZED_NGINX_SSL_SETUP' not in machine_rundata:
        ssh_check_call("""
        systemctl list-timers | grep certbot &&\
        cat /lib/systemd/system/certbot.timer &&\
        if ! cat /lib/systemd/system/certbot.service | grep "service nginx reload"; then
            sed -i "s/-q renew/-q renew --deploy-hook \\"service nginx reload\\"/" /lib/systemd/system/certbot.service
        fi && systemctl restart nginx
        """)
        ssh_check_call('echo "FINALIZED_NGINX_SSL_SETUP:{}" >> .rundata'.format(datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')))

    exit_code, output = ssh_getstatusoutput('curl -s http://{}'.format(rundata['server_public_ip']))
    assert exit_code == 0 and output == 'it works!', {'exit_code': exit_code, 'output': output}

    if 'rancher_sub_domain' not in rundata:
        rundata['rancher_sub_domain'] = input('Enter a new sub-domain to use for Rancher under the root domain ' + rundata['RootDomainName'] + ': ')
        rundata['rancher_domain'] = '{rancher_sub_domain}.{RootDomainName}'.format(**rundata)
        cloudflare.update_a_record(rundata['CloudflareEmail'], rundata['CloudflareApiKey'], rundata['RootDomainName'], rundata['rancher_sub_domain'] + '.' + rundata['RootDomainName'], rundata['server_public_ip'])
        ssh_check_call('certbot certonly --agree-tos --email {CloudflareEmail} --webroot -w /var/lib/letsencrypt/ -d {rancher_sub_domain}.{RootDomainName}'.format(**rundata))
        with open('.rundata/tmp_nginx_config', 'w') as f:
            f.write("""ssl_certificate /etc/letsencrypt/live/{rancher_sub_domain}.{RootDomainName}/fullchain.pem;
ssl_certificate_key /etc/letsencrypt/live/{rancher_sub_domain}.{RootDomainName}/privkey.pem;
ssl_trusted_certificate /etc/letsencrypt/live/{rancher_sub_domain}.{RootDomainName}/chain.pem;""".format(**rundata))
        ssh_copy_to_server('.rundata/tmp_nginx_config', '/etc/nginx/snippets/letsencrypt_certs.conf')
        ssh_check_call('systemctl restart nginx')
        ssh_check_call('echo "CONFIGURED_MAIN_DOMAIN:{}" >> .rundata'.format(datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
        print(_rundata_save(rundata))

    if 'docker_installed' not in rundata:
        ssh_check_call('apt-get update -y && apt-get install -y apt-transport-https ca-certificates curl gnupg-agent software-properties-common')
        ssh_check_call('curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo apt-key add -')
        ssh_check_call('apt-key fingerprint 0EBFCD88')
        print('Verify that the fingerprint matches "9DC8 5822 9FC7 DD38 854A E2D8 8D81 803C 0EBF CD88"')
        input('Press <Enter> to continue...')
        ssh_check_call('add-apt-repository "deb [arch=amd64] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable"')
        ssh_check_call('apt-get update -y && apt-get install -y docker-ce docker-ce-cli containerd.io')
        rundata['docker_installed'] = True
        print(_rundata_save(rundata))

    if 'rancher_installed' not in rundata:
        exit_code, output = ssh_getstatusoutput('docker ps | grep rancher')
        if exit_code == 0:
            print('Rancher already running, aborting')
            exit(1)
        rundata['rancher_version'] = input('rancher version (default=v2.3.3): ')
        if not rundata['rancher_version']:
            rundata['rancher_version'] = 'v2.3.3'
        rundata['rancher_image'] = "rancher/rancher:{rancher_version}".format(**rundata)
        ssh_check_call('mkdir -p /var/lib/rancher')
        ssh_check_call('docker run -d --name rancher --restart unless-stopped -p 8000:80 \
                        -v "/var/lib/rancher:/var/lib/rancher" "{rancher_image}"'.format(**rundata))
        rundata['rancher_installed'] = True
        print(_rundata_save(rundata))

    ssh_check_call('docker ps')

    if 'rancher_site_registered' not in rundata:
        rundata['rancher_route_host'] = 'localhost'
        rundata['rancher_route_port'] = '8000'
        with open('.rundata/tmp_nginx_config', 'w') as f:
            f.write("""location / {{
  proxy_pass http://{rancher_route_host}:{rancher_route_port};
  include snippets/http2_proxy.conf;
}}""".format(**rundata))
        ssh_copy_to_server('.rundata/tmp_nginx_config', '/etc/nginx/snippets/rancher.conf')
        with open('.rundata/tmp_nginx_config', 'w') as f:
            f.write("""
map $http_upgrade $connection_upgrade {{
    default Upgrade;
    ""      close;
}}
server {{
  listen 80;
  listen    [::]:80;
  server_name {rancher_domain};
  include snippets/letsencrypt.conf;
  return 301 https://$host$request_uri;
}}
server {{
  listen 443 ssl http2;
  listen [::]:443 ssl http2;
  server_name {rancher_domain};
  include snippets/letsencrypt_certs.conf;
  include snippets/ssl.conf;
  include snippets/letsencrypt.conf;
  include snippets/rancher.conf;
}}""".format(**rundata))
        ssh_copy_to_server('.rundata/tmp_nginx_config', '/etc/nginx/sites-enabled/rancher')
        ssh_check_call('systemctl restart nginx')
        rundata['rancher_site_registered'] = True
        print(_rundata_save(rundata))

    if not rundata.get('entered_token'):
        print('Perform the initial setup of Rancher online at https://{rancher_domain}'.format(**rundata))
        input('Press <Return> to continue... ')
        print('As the Rancher admin user - click on the profile image > api keys')
        print('Generate a non scoped API key and paste the bearer token')
        rundata['rancher_endpoint'] = input('Rancher Endpoint: ')
        rundata['rancher_access_key'] = input('Rancher Access Key: ')
        rundata['rancher_secret_key'] = input('Rancher Secret Key: ')
        rundata['rancher_bearer_token'] = input('Rancher Bearer Token: ')
        rundata['entered_token'] = True
        print(_rundata_save(rundata))

    if not rundata.get('rancher_cli_version'):
        print('Enter the rancher CLI version, you can check this via the Rancher Web UI')
        print('If you used a Rancher Version v2.3.x you can leave the default')
        rundata['rancher_cli_version'] = input('rancher CLI version (v2.3.2): ')
        if not rundata['rancher_cli_version']:
            rundata['rancher_cli_version'] = 'v2.3.2'
        subprocess.check_call('curl https://releases.rancher.com/cli2/{rancher_cli_version}/rancher-linux-amd64-{rancher_cli_version}.tar.gz -o rancher-linux-amd64-{rancher_cli_version}.tar.gz'.format(**rundata), shell=True)
        subprocess.check_call('tar -xzvf rancher-linux-amd64-{rancher_cli_version}.tar.gz'.format(**rundata), shell=True)
        subprocess.check_call('./rancher-{rancher_cli_version}/rancher --version'.format(**rundata), shell=True)
        print(_rundata_save(rundata))

    def rancher_check_call(args):
        subprocess.check_call('./rancher-{rancher_cli_version}/rancher {args}'.format(args=args, **rundata), shell=True)

    if not rundata.get('created_cluster'):
        print('The next steps should be performed manually in the Rancher Web UI')
        print("""Add the Kamatera Docker Machine driver

* Tools > Drivers > Node Drivers > Add Node Driver >
* Set Downlad URL: https://github.com/OriHoch/docker-machine-driver-kamatera/releases/download/v1.0.4/docker-machine-driver-kamatera_v1.0.4_linux_amd64.tar.gz
* Create Driver
* Wait for Kamatera driver to be active
""")
        input('Press <Return> to continue...')
        print("""Create the cluster

* Clusters > Add cluster >
* Infrastructure provider: Kamatera
* Cluster name: my-cluster
* add the controlplane node pool
  * Name Prefix: controlplane-worker
  * Count: 1
  * Template: create new template:
    * apiClientId: {apiClientid}
    * apiSecret: {apiSecret}
    * Set options according to your requirements, see Kamatera server options for the available options (must be logged-in to Kamatera console)
    * CPU must be at least: 2B
    * RAM must be at least: 2048, recommended: 4096
    * Disk size must be at least: 30, recommended: 60
    * Private Network Name: {PrivateNetworkName}
    * Name: kamatera-node
    * Engine options > Storage Driver: overlay2
    * Create template
  * set checkboxes: etcd, Control Plane, Workers
* Create cluster
""".format(**rundata))
        print('Wait for cluster to be in ready state (it might take 5-10 minutes)')
        input('Press <Return> to continue...')
        rundata['created_cluster'] = True
        print(_rundata_save(rundata))

    print('login --token {rancher_bearer_token} {rancher_endpoint}'.format(**rundata))
    rancher_check_call('login --token {rancher_bearer_token} {rancher_endpoint}'.format(**rundata))
    rancher_check_call('context switch System')

    def kubectl_check_call(*args):
        subprocess.check_call([
            './rancher-{rancher_cli_version}/rancher'.format(**rundata),
            'kubectl', '--insecure-skip-tls-verify',
            *args
        ])

    def kubectl_check_output(*args):
        return subprocess.check_output([
            './rancher-{rancher_cli_version}/rancher'.format(**rundata),
            'kubectl', '--insecure-skip-tls-verify',
            *args
        ])

    secret_args = []
    secret_args += ['--from-literal=id_rsa='+subprocess.check_output('cat .rundata/management_server_id_rsa', shell=True).decode()]
    secret_args += ['--from-literal=id_rsa.pub='+subprocess.check_output('cat .rundata/management_server_id_rsa.pub', shell=True).decode()]
    machine_data = {}
    for k, v in rundata.items():
        if v is True or k in ['id', 'server_info', 'ssh_key']:
            continue
        if k.startswith('Datacenter '):
            k = 'Datacenter'
        secret_args += ['--from-literal={}={}'.format(k, v)]
        machine_data[k] = v
    try:
        kubectl_check_call('get', 'namespace', 'ckan-cloud-operator')
    except Exception:
        kubectl_check_call('create', 'namespace', 'ckan-cloud-operator')
    try:
        kubectl_check_call('get', 'secret', '-n', 'ckan-cloud-operator', 'cco-kamatera-management-server')
    except Exception:
        kubectl_check_call('create', 'secret', '-n', 'ckan-cloud-operator', 'generic', 'cco-kamatera-management-server', *secret_args)
    kubeconfig_filename = '.{entered_server_name}.kubeconfig'.format(**rundata)
    new_value = input('Enter path to kubeconfig filename (.{entered_server_name}.kubeconfig): '.format(**rundata))
    if new_value:
       kubeconfig_filename = new_value
    kubeconfig = yaml.load(kubectl_check_output('config', 'view', '--raw'))
    for cluster in kubeconfig['clusters']:
        del cluster['cluster']['certificate-authority-data']
    with open(kubeconfig_filename, 'w') as f:
        yaml.dump(kubeconfig, f)
    print()
    print()
    with open(kubeconfig_filename) as f:
        print(f.read())
    print()
    print()
    for k, v in machine_data.items():
        yaml.dump({k: v}, sys.stdout)
    print()
    print('You should copy and paste the kubeconfig file above and the secret values and keep in a safe place')
    input('Press <Enter> to continue...')


def get_management_machine_secrets(key=None):
    return config_manager.get(key, secret_name='cco-kamatera-management-server', namespace='ckan-cloud-operator')


def ssh_management_machine(*args, check_output=False, scp_to_remote_file=None):
    machine_secrets = get_management_machine_secrets()
    id_rsa = machine_secrets['id_rsa']
    server_ip = machine_secrets['server_public_ip']
    with NamedTemporaryFile('wb') as f:
        f.write(id_rsa.encode('ascii'))
        f.flush()
        if scp_to_remote_file:
            with NamedTemporaryFile('w') as tempfile:
                tempfile.write("\n".join(args))
                tempfile.flush()
                cmd = ['scp', '-i', f.name, tempfile.name, 'root@' + server_ip + ':' + scp_to_remote_file]
                subprocess.check_call(cmd)
                return 0
        else:
            cmd = ['ssh', '-i', f.name, 'root@' + server_ip, *args]
            if check_output:
                return subprocess.check_output(cmd)
            else:
                return subprocess.call(cmd)


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
            ssh_management_machine(
                "location / {",
                    f'proxy_pass {route["spec"]["backend-url"]};',
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
    exit(42)