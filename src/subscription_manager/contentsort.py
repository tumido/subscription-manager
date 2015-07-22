
from subscription_manager import sortutils
# Notes
# Need a RepoLabelCompare that splits on '-' and compares piece by piece
# Might be able to use rpmvercmp ?


class ComparableContent(sortutils.ComparableMixin):
    def __init__(self, content, enabled_contents=None):
        self.content = content
        self.enabled_contents = enabled_contents or []
        self.enabled_contents_prefixes = set([])
        for enabled in self.enabled_contents:
            content_parts = enabled.label.split('-')
            first_three = content_parts[:3]
            self.enabled_contents_prefixes.add('-'.join(first_three))

    def compare_keys(self, other):
        return (sortutils.RpmVersion(epoch=self.enabled_as_epoch(self.content),
                                     version=self.related_to_enabled_repos(self.content),
                                     release=self.content.label),
                sortutils.RpmVersion(epoch=self.enabled_as_epoch(other.content),
                                     version=self.related_to_enabled_repos(other.content),
                                     release=other.content.label))

    def enabled_as_epoch(self, content):
        # flip the sort and return string numbers to use as faux epochs
        if content.enabled:
            return "0"
        return "1"

    def related_to_enabled_repos(self, content):
        for enabled_prefix in self.enabled_contents_prefixes:
            if content.label.startswith(enabled_prefix):
                return "0"
        return "1"

    def __str__(self):
        return "<ComparableContent label=%s enabled=%s name=%s tags=%s>" % \
                (self.content.label, self.content.enabled,
                 self.content.name, self.content.tags)


class ContentSort(object):
    def __init__(self, contents):
        self.contents = contents

        self.enabled_contents = [x for x in self.contents if x.enabled]

    def sorted(self, contents):
        sortable_contents = [ComparableContent(content=x, enabled_contents=self.enabled_contents)
                             for x in self.contents]
        return [x.content for x in sorted(sortable_contents)]
        #return sorted(contents, key=self.content_key)

    def main_repo(self, content):
        for sub_repo in ['source-rpms', 'debug-rpms', 'beta-rpms']:
            if content.label.endswith(sub_repo):
                return 1
        return 0

    # if a repo is approximately the same as a enabled repo
    def fancy_related_to_enabled_repos(self, content):
        for enabled in self.enabled_contents:
            content_parts = enabled.label.split('-')
            parts_count = 3
            while parts_count >= 0:
                if content.label.startswith('-'.join(content_parts[:parts_count])):
                    print "return parts_count", 3 - parts_count, content.label
                    return parts_count
                parts_count -= 1
        return 4

    def related_to_enabled_repos(self, content):
        for enabled in self.enabled_contents:
            content_parts = enabled.label.split('-')
            first_three = content_parts[:3]
            if content.label.startswith('-'.join(first_three)):
                return 0
        return 1

    def content_key(self, content):
        #return (not content.enabled, content.tags, len(content.label), content.label)
        return (not content.enabled,
                self.related_to_enabled_repos(content),
                self.main_repo(content),
                content.tags,
                content.label)
