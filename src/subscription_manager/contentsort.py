
# Notes
# Need a RepoLabelCompare that splits on '-' and compares piece by piece
# Might be able to use rpmvercmp ?


class ContentSort(object):
    def __init__(self, contents):
        self.contents = contents

        self.enabled_contents = [x for x in self.contents if x.enabled]

    def sorted(self, contents):
        return sorted(contents, key=self.content_key)

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
