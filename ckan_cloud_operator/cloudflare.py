import subprocess
import json


def get_zone_id(auth_email, auth_key, zone_name):
    data = curl(auth_email, auth_key, 'zones')
    zones = [zone['id'] for zone in data['result'] if zone['name'] == zone_name]
    return zones[0] if len(zones) > 0 else None


def get_record_id(auth_email, auth_key, zone_id, record_name):
    data = curl(auth_email, auth_key, f'zones/{zone_id}/dns_records?name={record_name}')
    records = [record['id'] for record in data['result'] if record['name'] == record_name]
    return records[0] if len(records) > 0 else None


def update_a_record(auth_email, auth_key, zone_name, record_name, target_ip):
    zone_id = get_zone_id(auth_email, auth_key, zone_name)
    assert zone_id is not None, f'Invalid zone name: {zone_name}'
    record_id = get_record_id(auth_email, auth_key, zone_id, record_name)
    if record_id:
        print(f'Updating existing record {record_name}')
        cf_record = {'type': 'A', 'name': record_name, 'content': target_ip, 'ttl': 120, 'proxied': False}
        data = curl(auth_email, auth_key, f'zones/{zone_id}/dns_records/{record_id}', cf_record, 'PUT')
    else:
        print(f'Creating new record: {record_name}')
        cf_record = {'type': 'A', 'name': record_name, 'content': target_ip, 'ttl': 120, 'proxied': False}
        data = curl(auth_email, auth_key, f'zones/{zone_id}/dns_records', cf_record, 'POST')
    print(data)
    assert data.get('success')


def curl(auth_email, auth_key, urlpart, data=None, method='GET'):
    cmd = ['curl', '-s', '-X', method, f'https://api.cloudflare.com/client/v4/{urlpart}']
    cmd += [
        '-H', f'X-Auth-Email: {auth_email}',
        '-H', f'X-Auth-Key: {auth_key}',
        '-H', 'Content-Type: application/json'
    ]
    if data:
        cmd += ['--data', json.dumps(data)]
    output = subprocess.check_output(cmd)
    return json.loads(output)
