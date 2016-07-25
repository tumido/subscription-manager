#
# Copyright (c) 2005-2010 Red Hat, Inc.
#
# This software is licensed to you under the GNU General Public License,
# version 2 (GPLv2). There is NO WARRANTY for this software, express or
# implied, including the implied warranties of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. You should have received a copy of GPLv2
# along with this software; if not, see
# http://www.gnu.org/licenses/old-licenses/gpl-2.0.txt.
#

import ConfigParser
import logging
import logging.handlers
import logging.config
import os
import sys

LOGGING_CONFIG = "/etc/rhsm/logging.conf"
YUM_LOGGING_CONFIG = "/etc/rhsm/yum_logging.conf"
LOGFILE_PATH = "/var/log/rhsm/rhsm.log"


# Don't need this for syslog
class ContextLoggingFilter(object):
    """Find the name of the process as 'cmd_name'"""
    current_cmd = os.path.basename(sys.argv[0])
    cmd_line = ' '.join(sys.argv)

    def __init__(self, name):
        self.name = name

    def filter(self, record):
        record.cmd_name = self.current_cmd
        record.cmd_line = self.cmd_line

        # TODO: if we merge "no-rpm-version" we could populate it here
        return True


class SubmanDebugLoggingFilter(object):
    """Filter all log records unless env SUBMAN_DEBUG exists

    Used to turn on stdout logging for cli debugging."""

    def __init__(self, name):
        self.name = name
        self.on = 'SUBMAN_DEBUG' in os.environ

    def filter(self, record):
        return self.on


# NOTE: python 2.6 and earlier versions of the logging module
#       defined the log handlers as old style classes. In order
#       to use super(), we also inherit from 'object'
class RHSMLogHandler(logging.handlers.RotatingFileHandler, object):
    """Logging Handler for /var/log/rhsm/rhsm.log"""
    def __init__(self, *args, **kwargs):
        try:
            super(RHSMLogHandler, self).__init__(*args, **kwargs)
        # fallback to stdout if we can't open our logger
        except Exception:
            logging.StreamHandler.__init__(self)
        self.addFilter(ContextLoggingFilter(name=""))


class SubmanDebugHandler(logging.StreamHandler, object):
    """Logging Handler for cli debugging.

    This handler only emits records if SUBMAN_DEBUG exists in os.environ."""

    def __init__(self, *args, **kwargs):
        super(SubmanDebugHandler, self).__init__(*args, **kwargs)
        self.addFilter(ContextLoggingFilter(name=""))
        self.addFilter(SubmanDebugLoggingFilter(name=""))


# Note: this only does anything for python 2.6+, if the
# logging module has 'captureWarnings'. Otherwise it will not
# be triggered.
class PyWarningsLoggingFilter(object):
    """Add a prefix to the messages from py.warnings.

    To help distinquish log messages from python and pygtk 'warnings',
    while avoiding changing the log format."""

    label = "py.warnings:"

    def __init__(self, name):
        self.name = name

    def filter(self, record):
        record.msg = u'%s %s' % (self.label, record.msg)
        return True


class PyWarningsLogger(logging.getLoggerClass()):
    """Logger for py.warnings for use in file based logging config."""
    level = logging.WARNING

    def __init__(self, name):
        super(PyWarningsLogger, self).__init__(name)

        self.setLevel(self.level)
        self.addFilter(PyWarningsLoggingFilter(name="py.warnings"))


def __file_config(fname, defaults=None, disable_existing_loggers=1):
        """
        Copied from python 2.6 logging.config module.

        Read the logging configuration from a ConfigParser-format file.
        """
        import ConfigParser

        cp = ConfigParser.ConfigParser(defaults)
        if hasattr(cp, 'readfp') and hasattr(fname, 'readline'):
            cp.readfp(fname)
        else:
            cp.read(fname)

        formatters = logging.config._create_formatters(cp)

        # critical section
        logging._acquireLock()
        try:
            logging._handlers.clear()
            del logging._handlerList[:]
            # Handlers add themselves to logging._handlers
            handlers = logging.config._install_handlers(cp, formatters)
            __install_loggers(cp, handlers, disable_existing_loggers)
        finally:
            logging._releaseLock()

def __install_loggers(cp, handlers, disable_existing_loggers):
        """Create and install loggers"""

        # configure the root first
        llist = cp.get("loggers", "keys")
        llist = llist.split(",")
        llist = list(map(lambda x: x.strip(), llist))
        try:
            llist.remove("root")
            sectname = "logger_root"
            root = logging.root
            log = root
            opts = cp.options(sectname)
            if "level" in opts:
                level = cp.get(sectname, "level")
                log.setLevel(logging._levelNames[level])
            for h in root.handlers[:]:
                root.removeHandler(h)
            hlist = cp.get(sectname, "handlers")
            if len(hlist):
                hlist = hlist.split(",")
                hlist = logging.config._strip_spaces(hlist)
                for hand in hlist:
                    log.addHandler(handlers[hand])
        except ValueError:
            root = logging.root
            # We don't have a configuration for the root logger.
            # Continue to handle the other loggers
            # This allows configurations to be used that do not override
            # the root logger

        # and now the others...
        # we don't want to lose the existing loggers,
        # since other threads may have pointers to them.
        # existing is set to contain all existing loggers,
        # and as we go through the new configuration we
        # remove any which are configured. At the end,
        # what's left in existing is the set of loggers
        # which were in the previous configuration but
        # which are not in the new configuration.
        existing = list(root.manager.loggerDict.keys())
        # The list needs to be sorted so that we can
        # avoid disabling child loggers of explicitly
        # named loggers. With a sorted list it is easier
        # to find the child loggers.
        existing.sort()
        # We'll keep the list of existing loggers
        # which are children of named loggers here...
        child_loggers = []
        # now set up the new ones...
        for log in llist:
            sectname = "logger_%s" % log
            qn = cp.get(sectname, "qualname")
            opts = cp.options(sectname)
            if "propagate" in opts:
                propagate = cp.getint(sectname, "propagate")
            else:
                propagate = 1
            logger = logging.getLogger(qn)
            if qn in existing:
                i = existing.index(qn) + 1  # start with the entry after qn
                prefixed = qn + "."
                pflen = len(prefixed)
                num_existing = len(existing)
                while i < num_existing:
                    if existing[i][:pflen] == prefixed:
                        child_loggers.append(existing[i])
                    i += 1
                existing.remove(qn)
            if "level" in opts:
                level = cp.get(sectname, "level")
                logger.setLevel(logging._levelNames[level])
            for h in logger.handlers[:]:
                logger.removeHandler(h)
            logger.propagate = propagate
            logger.disabled = 0
            hlist = cp.get(sectname, "handlers")
            if len(hlist):
                hlist = hlist.split(",")
                hlist = logging.config._strip_spaces(hlist)
                for hand in hlist:
                    logger.addHandler(handlers[hand])

        # Disable any old loggers. There's no point deleting
        # them as other threads may continue to hold references
        # and by disabling them, you stop them doing any logging.
        # However, don't disable children of named loggers, as that's
        # probably not what was intended by the user.
        for log in existing:
            logger = root.manager.loggerDict[log]
            if log in child_loggers:
                logger.level = logging.NOTSET
                logger.handlers = []
                logger.propagate = 1
            else:
                logger.disabled = disable_existing_loggers


def file_config(logging_config):
    """Load logging config from the file logging_config and setup logging."""

    # NOTE: without disable_existing_loggers, this would have to
    # be close to the first thing ran. Any loggers created after
    # that are disabled. This likely includes module level loggers
    # like all of ours.
    try:
        # Use our slightly altered file_config method (doesn't require an
        # override for the root logger)
        __file_config(logging_config,
                      defaults={'logfilepath': LOGFILE_PATH},
                      disable_existing_loggers=False)
    except ConfigParser.Error, e:
        # If the log config file doesn't exist, or is empty, we end up
        # with ConfigParser errors.

        # TODO: fallback default logger?
        print e
    log = logging.getLogger(__name__)
    log.debug('Test')

def init_logger():
    """Load logging config file and setup logging.

    Only needs to be called once per process."""

    file_config(logging_config=LOGGING_CONFIG)


def init_logger_for_yum():
    file_config(YUM_LOGGING_CONFIG)

    # TODO: switch this to reference /etc/rhsm/yum_logging.conf

    # Don't send log records up to yum/yum plugin conduit loggers
    logging.getLogger("subscription_manager").propagate = False
    logging.getLogger("rhsm").propagate = False
    logging.getLogger("rhsm-app").propagate = False
