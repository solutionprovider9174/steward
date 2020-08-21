import json
import requests

class Palladion:
    _uri = None
    _api_key = None
    _session = None

    def __init__(self, uri, api_key):
        self._uri = uri
        self._api_key = api_key
        self._session = requests.Session()

    def user_search(self, query):
        uri = '{}/searchUsers'.format(self._uri)
        headers = {'X-API-Key': self._api_key}
        r = self._session.post(uri, headers=headers, data={'query': query}, verify=False)
        return json.loads(r.text)['users']

    def registrations(self, user):
        uri = '{}/getRegs'.format(self._uri)
        headers = {'X-API-Key': self._api_key}
        r = self._session.post(uri, headers=headers, data={'user': user}, verify=False)
        return json.loads(r.text)['regs']

    def devices(self):
        uri = '{}/getAllDevices'.format(self._uri)
        headers = {'X-API-Key': self._api_key}
        r = self._session.post(uri, headers=headers, verify=False)
        return json.loads(r.text)['devices']

    def ua_stats(self, sort_by, direction, stats_list, what, limit, group_by, group_direction):
        uri = '{}/uastats'.format(self._uri)
        headers = {'X-API-Key': self._api_key}
        data = {
            'sort': sort_by,
            'dir': direction,
            'list': stats_list,
            'what': what,
            'limit': limit,
            'groupBy': group_by,
            'groupDir': group_direction
        }
        r = self._session.post(uri, headers=headers, verify=False)
        return json.loads(r.text)

    def ua_users(self, device, start, limit, what, total):
        uri = '{}/uausers'.format(self._url)
        headers = {'X-API-Key': self._api_key}
        data = {
            'device': device,
            'start': start,
            'limit': limit,
            'what': what,
            'total': total,
        }
        r = self._session.post(uri, headers=headers, data=data, verify=False)
        return json.loads(r.text)
