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


def import_class(name):
    """Load a class from a string.  Thanks http://stackoverflow.com/a/547867/61248 """
    components = name.split('.')
    current_level = components[0]
    module = __import__(current_level)
    for comp in components[1:-1]:
        # import all the way down to the class
        current_level = ".".join([current_level, comp])
        __import__(current_level)
        # the class will be an attribute on the lowest level module
        module = getattr(module, comp)
    return getattr(module, components[-1])
