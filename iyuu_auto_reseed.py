import hashlib
import sys
import time
from os import path

import requests
from flexget import plugin
from flexget.entry import Entry
from flexget.event import event
from flexget.utils import json

d = path.dirname(__file__)
sys.path.append(d)
from qbittorrent_client import QBittorrentClient


class PluginIYUUAutoReseed():
    schema = {
        'anyOf': [
            {'type': 'boolean'},
            {
                'type': 'object',
                'properties': {
                    'iyuu': {'type': 'string'},
                    'version': {'type': 'string'},
                    'passkeys': {
                        'type': 'object',
                        'properties': {
                        }
                    },
                    'qbittorrent_ressed': {
                        'host': {'type': 'string'},
                        'use_ssl': {'type': 'boolean'},
                        'port': {'type': 'integer'},
                        'username': {'type': 'string'},
                        'password': {'type': 'string'},
                        'verify_cert': {'type': 'boolean'}
                    }
                },
                'additionalProperties': False
            }
        ]
    }

    def prepare_config(self, config):
        config.setdefault('iyuu', '')
        config.setdefault('version', '0.2.0')
        config.setdefault('passkeys', {})
        config.setdefault('qbittorrent_ressed', {})
        return config

    def on_task_input(self, task, config):
        config = self.prepare_config(config)
        passkeys = config.get('passkeys')

        torrent_dict, torrents_hashes = self.get_torrents_data(config)
        response_json = requests.post('http://pt.iyuu.cn/api/reseed', json=torrents_hashes).json()
        reseed_json = response_json['clients_0']
        sites_json = response_json['sites']

        entries = []
        for info_hash, seeds_data in reseed_json.items():
            for torrent in seeds_data['torrent']:
                site = sites_json[str(torrent['sid'])]
                client_torrent = torrent_dict[info_hash]
                base_url = site['base_url']
                site_name = ''
                passkey = ''
                for key, value in passkeys.items():
                    if key in base_url:
                        site_name = key
                        passkey = value
                        break
                if not passkey:
                    continue
                if site_name == 'totheglory':
                    download_page = site['download_page'].format(str(torrent['torrent_id']) + '/' + passkey)
                else:
                    download_page = site['download_page'].format(str(torrent['torrent_id']) + '&passkey=' + passkey)

                entry = Entry(
                    title=client_torrent['name'],
                    url='https://{}/{}'.format(base_url, download_page),
                    torrent_info_hash=torrent['info_hash']
                )
                entry['autoTMM'] = client_torrent['auto_tmm']
                entry['category'] = client_torrent['category']
                entry['savepath'] = client_torrent['save_path']
                entry['paused'] = 'true'
                entries.append(entry)
        return entries

    def get_torrents_data(self, config):
        client = QBittorrentClient(config.get('qbittorrent_ressed'))
        torrent_dict = {}
        torrents_hashes = {}
        hashes = []
        for torrent in client.torrents:
            if 'up' in torrent['state'].lower():
                torrent_dict[torrent['hash']] = torrent
                hashes.append(torrent['hash'])

        list.sort(hashes)
        hashes_json = json.dumps(hashes)
        sha1 = hashlib.sha1(hashes_json.encode("utf-8")).hexdigest()

        torrents_hashes['hash'] = {}
        torrents_hashes['hash']['clients_0'] = hashes_json
        torrents_hashes['sha1'] = []
        torrents_hashes['sha1'].append(sha1)
        torrents_hashes['sign'] = config['iyuu']
        torrents_hashes['version'] = config['version']
        torrents_hashes['timestamp'] = int(time.time())

        return torrent_dict, torrents_hashes


@event('plugin.register')
def register_plugin():
    plugin.register(PluginIYUUAutoReseed, 'iyuu_auto_reseed', api_ver=2)
