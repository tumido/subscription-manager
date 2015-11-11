#
# Copyright (c) 2013 Red Hat, Inc.
#
#
# This software is licensed to you under the GNU General Public License,
# version 2 (GPLv2). There is NO WARRANTY for this software, express or
# implied, including the implied warranties of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. You should have received a copy of GPLv2
# along with this software; if not, see
# http://www.gnu.org/licenses/old-licenses/gpl-2.0.txt.
#
# Red Hat trademarks are not licensed under GPLv2. No permission is
# granted to use or replicate Red Hat trademarks that are incorporated
# in this software or its documentation.
#
from subscription_manager import injection as inj
#from subscription_manager.repolib import RepoActionInvoker
#from subscription_manager.content_action_client import ContentActionClient
from subscription_manager.cache import OverrideStatusCache, WrittenOverrideCache

import logging

log = logging.getLogger('rhsm-app.' + __name__)

# Module for manipulating content overrides


# TODO: this is what overrides.Overrides() intended?
class RepoOverrides(dict):
    """Map contentLabel -> (key, value)"""
    def __init__(self, cache_only=None):
        super(RepoOverrides, self).__init__()

        self.cp_provider = inj.require(inj.CP_PROVIDER)
        self.uep = self.cp_provider.get_consumer_auth_cp()
        self.identity = inj.require(inj.IDENTITY)

        self.cache_only = cache_only or False

        self.override_supported = False
        if self.identity.is_valid() and self.uep:
            self.override_supported = self.uep.supports_resource('content_overrides')

        if not self.override_supported:
            return

        self.written_overrides = WrittenOverrideCache()
        # NOTE: if anything in the RepoActionInvoker init blocks, and it
        #       could, yum could still block. The closest thing to an
        #       event loop we have is the while True: sleep() in lock.py:Lock.acquire()

        # Only attempt to update the overrides if they are supported
        # by the server.
        self.written_overrides._read_cache()

        try:
            override_cache = inj.require(inj.OVERRIDE_STATUS_CACHE)
        except KeyError:
            override_cache = OverrideStatusCache()

        if self.cache_only:
            status = override_cache._read_cache()
        else:
            status = override_cache.load_status(self.uep, self.identity.uuid)

        for item in status or []:
            # Don't iterate through the list
            content_label, name, value = (item['contentLabel'],
                                          item['name'],
                                          item['value'])
            if content_label not in self:
                self[content_label] = {}
            self[content_label][name] = value


class Overrides(object):
    def __init__(self, consumer_uuid):
        self.cp_provider = inj.require(inj.CP_PROVIDER)

        self.cache = inj.require(inj.OVERRIDE_STATUS_CACHE)

        # add and require a WrittenOverrideCache()

        # FIXME: cache_only?
#        self.content_action = ContentActionClient()

        self.consumer_uuid = consumer_uuid

    def get_overrides(self):

        res = self._build_from_dict(self.cache.load_status(self._getuep(),
                                                           self.consumer_uuid))
        log.debug("get_overrides %s", res)
        return res

    def update(self, overrides):
        # huh? why is this explicitly adding things to the cache?
        self.cache.server_status = [override for override in overrides]
        self.cache.write_cache()
        # Why does updating content overrides update content_action instead
        # of vice versa?
#        self.content_action.update()

    def add_overrides(self, overrides):
        return self._build_from_dict(self._getuep().setContentOverrides(self.consumer_uuid,
                                                                 self._add(overrides)))

    def _add(self, overrides):
        return [override for override in overrides]

    def remove_overrides(self, overrides):
        return self._delete_overrides(self.consumer_uuid, self._remove(overrides))

    def remove_all_overrides(self, repos):
        return self._delete_overrides(self.consumer_uuid, self._remove_all(repos))

    def _delete_overrides(self, override_data):
        # delete overrides always takes a list of overrides
        return self._build_from_dict(self._getuep().deleteContentOverrides(self.consumer_uuid, override_data))

    def _remove(self, overrides):
        return [{'contentLabel': override.repo_id, 'name': override.name} for override in overrides]

    def _remove_all(self, repos):
        if repos:
            return [{'contentLabel': repo} for repo in repos]
        else:
            return None

    def _build_from_dict(self, override_json):
        return [Override.from_dict(override_dict) for override_dict in override_json]

    def _getuep(self):
        return self.cp_provider.get_consumer_auth_cp()

    def sync_to_server(self, override_list):
        res = self._getuep().setContentOverrides(self.consumer_uuid, override_list.serializable())
        return res

    def remove(self, override_list):
        self._getuep().deleteContentOverrides(self.consumer_uuid)


class OverrideList(object):
    def __init__(self, overrides=None):
        self._overrides = overrides or []

    @classmethod
    def from_repos_to_change_enabled(cls, repos_to_modify):
        overrides = [Override(repo_id, 'enabled', status)
                     for repo_id, status in repos_to_modify]
        override_list = cls(overrides=overrides)
        return override_list

    @classmethod
    def from_repos_to_modify(cls, repos_to_modify):
        overrides = [Override(repo_id, name, status)
                     for repo_id, name, status in repos_to_modify]
        override_list = cls(overrides=overrides)
        return override_list

    def __iter__(self):
        return iter(self._overrides)

    def __len__(self):
        return len(self._overrides)

    def __getitem__(self, key):
        return self._overrides[key]

    def serializable(self):
        return self._overrides
        #return [self._json_encode(x) for x in self._overrides]

    def _json_encode(self, obj):
        if isinstance(obj, Override):
            return obj.data
        return obj


class OverrideData(dict):
    def __init__(self, repo_id, name, value=None):
        self['contentLabel'] = repo_id
        self['name'] = name
        self['value'] = value


class Override(OverrideData):
    def __init__(self, repo_id, name, value=None):
        super(Override, self).__init__(repo_id, name, value)
        self.repo_id = repo_id
        self.name = name
        self.value = value
#        self.data = OverrideData(self.repo_id, self.name, self.value)

    @classmethod
    def from_dict(cls, json_obj):
        return cls(json_obj['contentLabel'],
                   json_obj['name'],
                   json_obj['value'])

    #def to_json(self):
    #    return self.data
