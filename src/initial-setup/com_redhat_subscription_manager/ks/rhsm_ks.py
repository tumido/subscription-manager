#
# Copyright (C) 2015  Red Hat, Inc.
#
# This copyrighted material is made available to anyone wishing to use,
# modify, copy, or redistribute it subject to the terms and conditions of
# the GNU General Public License v.2, or (at your option) any later version.
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY expressed or implied, including the implied warranties of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General
# Public License for more details.  You should have received a copy of the
# GNU General Public License along with this program; if not, write to the
# Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
"""Module with the RHSM initial-setup class."""

import logging

from pyanaconda.addons import AddonData

log = logging.getLogger(__name__)

# export RHSMAddonData class to prevent Anaconda's collect method from taking
# AddonData class instead of the RHSMAddonData class
# @see: pyanaconda.kickstart.AnacondaKSHandler.__init__
__all__ = ["RHSMAddonData"]


"""
# Sample ks file ideas

# all on the header
%addon com_redhat_subscription_manager --serverUrl=https://grimlock.usersys.redhat.com/candlepin --activationkey=SOMEKEY

%end

%addon com_redhat_subscription_manager
    # only one
    server-url = https://grimlock.usersys.redhat.com:8443/candlepin

    # can have many act keys. Does order matter?
    activation-key = SOMEKEY-1
    activation-key = SOMEKEY-2

    # If we should attempt to auto-attach
%end
"""

# To test
# utf8 streams
# inlined base64 blobs (ie, cert pems)
# inline yum.repo
# if anything needs to match a value from a cert,
#  need to verify the encodings all work

class RHSMAddonData(AddonData):
    """This is a common parent class for loading and storing
       3rd party data to kickstart. It is instantiated by
       kickstart parser and stored as ksdata.addons.<name>
       to be used in the user interfaces.

       The mandatory method handle_line receives all lines
       from the corresponding addon section in kickstart and
       the mandatory __str__ implementation is responsible for
       returning the proper kickstart text (to be placed into
       the %addon section) back.

       There is also a mandatory method execute, which should
       make all the described changes to the installed system.
    """

    def __init__(self, name):
        self.name = name
        self.content = ""
        self.header_args = ""

        # TODO: make this a data class
        self.server_url = None
        self.activation_keys = []
        self.auto_attach = True
        self.org = None

        self.line_handlers = {'server-url': self._parse_server_url,
                              'activation-key': self._parse_activation_key,
                              'auto-attach': self._parse_auto_attach,
                              'org': self._parse_org}

    def __str__(self):
        return "%%addon %s %s\n%s%%end\n" % (self.name, self.header_args, self.content)

    def setup(self, storage, ksdata, instClass):
        """Make the changes to the install system.

           This method is called before the installation
           is started and directly from spokes. It must be possible
           to call it multiple times without breaking the environment."""
        super(RHSMAddonData, self).setup(storage, ksdata, instClass)

        self.log.debug("storage %s", storage)
        self.log.debug("ksdata %s", ksdata)
        self.log.debug("instClass %s", instClass)

    def execute(self, storage, ksdata, instClass, users):

        """Make the changes to the underlying system.

           This method is called only once in the post-install
           setup phase.
        """
#        pass

    def handle_header(self, lineno, args):
        """Process additional arguments to the %addon line.

           This function receives any arguments on the %addon line after the
           addon ID. For example, for the line:

               %addon com_example_foo --argument='example'

           This function would be called with args=["--argument='example'"].

           By default AddonData.handle_header just preserves the passed
           arguments by storing them and adding them to the __str__ output.

        """

        if args:
            self.header_args += " ".join(args)

    def _bool(self, value):
        if value == 'true':
            return True
        return False

    def _parse_server_url(self, value):
        self.server_url = value

    def _parse_activation_key(self, value):
        self.activation_keys.append(value)

    def _parse_auto_attach(self, value):
        self.auto_attach = self._bool(value)

    def _parse_org(self, value):
        self.org = value

    def handle_line(self, line):
        """Process one kickstart line."""
        self.content += line

        line = line.strip()
        (pre, sep, post) = line.partition('=')
        pre = pre.strip()
        sep = sep.strip()
        # could trailing space be valid for a value?
        post = post.strip('"')

        if pre[0] == '#':
            return

        try:
            self.line_handlers[pre](post)
        except KeyError, e:
            log.debug("Parse error, unknown RHSM addon ks cmd %s", pre)

    def finalize(self):
        """No additional data will come.

           Addon should check if all mandatory attributes were populated.
        """
        pass
    # NOTE: no execute() or handle_line() yet
