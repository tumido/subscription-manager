# Copyright (c) 2016 Red Hat, Inc.
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
import rhsm.config


class ProtoDict(object):
    """Standard dict methods that are not dependent on underlying structure."""
    def keys(self):
        return list(self)

    def values(self):
        return [self[key] for key in self]

    def items(self):
        return [(key, self[key]) for key in self]

    def iterkeys(self):
        return iter(self)

    def itervalues(self):
        for k in self:
            yield self[k]

    def iteritems(self):
        for k in self:
            yield (k, self[k])

    def get(self, key, default=None):
        if key not in self:
            return default
        return self[key]


class Config(ProtoDict):
    def __init__(self, parser=None):
        if parser:
            self._parser = parser
        else:
            self._parser = rhsm.config.initConfig()

        self._sections = {}
        for s in self._parser.sections():
            self._sections[s] = ConfigSection(self, self._parser, s)
        super(Config, self).__init__()

    def _persist(self):
        self._parser.save()

    def __getitem__(self, name):
        if name in self:
            return self._sections[name]
        raise KeyError("No configuration section '%s' exists" % name)

    def __setitem__(self, key, value, persist=False):
        if key in self:
            raise NotImplementedError("Cannot replace existing sections")

        for k, v in value.iteritems():
            self._sections[key][k] = v

        if persist:
            self._persist()

    def __delitem__(self, key):
        self._parser.remove_section(key)
        del self._sections[key]
        self._persist()

    def __contains__(self, key):
        return key in self._sections

    def __iter__(self):
        return iter(self._parser.sections())

    def __len__(self):
        return len(self._parser.sections())

    def __repr__(self):
        result = {}
        for name, s in self._sections.items():
            result[name] = repr(s)
        return "%s" % result


class ConfigSection(ProtoDict):
    def __init__(self, wrapper, parser, section):
        self._wrapper = wrapper
        self._parser = parser
        self._section = section

    def __iter__(self):
        return self._parser.items(self._section)

    def __getitem__(self, key):
        if key in self:
            return self._parser.get(self._section, key)
        raise KeyError("Property '%s' does not exist in section '%s'" % (key, self._section))

    def __setitem__(self, key, value, persist=False):
        self._parser.set(self._section, key, value)
        if persist:
            self._persist()

    def __delitem__(self, key):
        if key in self:
            self._parser.remove_option(self._section, key)
            self._persist()
        raise KeyError("Property '%s' does not exist in section '%s'" % (key, self._section))

    def __contains__(self, key):
        return self._parser.has_option(self._section, key)

    def __len__(self):
        return len(self._parser.options(self._section))

    def _persist(self):
        self._wrapper.persist()

    def __repr__(self):
        return "%s" % self._parser.items(self._section)
