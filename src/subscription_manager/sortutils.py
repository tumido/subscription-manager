
import rpm


class ComparableMixin(object):
    """Needs compare_keys to be implemented."""
    def _compare(self, keys, method):
        return method(keys[0], keys[1]) if keys else NotImplemented

    def __eq__(self, other):
        return self._compare(self.compare_keys(other), lambda s, o: s == o)

    def __ne__(self, other):
        return self._compare(self.compare_keys(other), lambda s, o: s != o)

    def __lt__(self, other):
        return self._compare(self.compare_keys(other), lambda s, o: s < o)

    def __gt__(self, other):
        return self._compare(self.compare_keys(other), lambda s, o: s > o)

    def __le__(self, other):
        return self._compare(self.compare_keys(other), lambda s, o: s <= o)

    def __ge__(self, other):
        return self._compare(self.compare_keys(other), lambda s, o: s >= o)


class RpmVersion(object):
    """Represent the epoch, version, release of a rpm style version.

    This includes the rich comparison methods to support >,<,==,!-
    using rpm's labelCompare.

    See http://fedoraproject.org/wiki/Archive:Tools/RPM/VersionComparison
    for more details of the actual comparison rules.
    """

    # Ordered list of suffixes
    #suffixes = ['source-rpms', 'debug-rpms', 'alpha-rpms',
    #            'beta-rpms', 'beta-source-rpms', 'beta-debug-rpms']
    suffixes = ['-source-rpms', '-debug-rpms', '-alpha-rpms',
                '-beta-rpms', '-beta-source-rpms', '-beta-debug-rpms']
    suffixes.reverse()

    def __init__(self, epoch="0", version="0", release="1"):
        self.epoch = epoch
        self.version = version
        self.release = release

    @property
    def evr(self):
        return (self.epoch, self.version, self.release)

    @property
    def evr_nosuff(self):
        def no_suff(s):
            for suff in self.suffixes:
                if s and s.lower().endswith(suff):
                    return s[:-len(suff)].strip('- ')
            return s
        return (self.epoch, self.version, no_suff(self.release))

    def compare(self, other):
        def ends_with_which(s):
            for idx, suff in enumerate(self.suffixes):
                if s.lower().endswith(suff):
                    return idx
            # Easier compare
            return len(self.suffixes)

        raw_compare = rpm.labelCompare(self.evr, other.evr)
        non_beta_compare = rpm.labelCompare(self.evr_nosuff, other.evr_nosuff)
        print
        print "raw", self.evr, other.evr, raw_compare
        print "non_beta", self.evr_nosuff, other.evr_nosuff, non_beta_compare
        print "non_beta != raw", non_beta_compare != raw_compare
        if non_beta_compare != raw_compare:
            print "ew self:", ends_with_which(self.release), \
                "ew other", ends_with_which(other.release), \
                "compare: ", ends_with_which(self.release) < ends_with_which(other.release)
            if ends_with_which(self.release) < ends_with_which(other.release):
                print "-1"
                return -1
            print "1"
            return 1
        return raw_compare

    def __lt__(self, other):
        lc = self.compare(other)
        if lc == -1:
            return True
        return False

    def __le__(self, other):
        lc = self.compare(other)
        if lc > 0:
            return False
        return True

    def __eq__(self, other):
        lc = self.compare(other)
        if lc == 0:
            return True
        return False

    def __ne__(self, other):
        lc = self.compare(other)
        if lc != 0:
            return True
        return False


class ComparableProduct(ComparableMixin):
    """A comparable version from a Product. For comparing and sorting Product objects.

    Products are never equals if they do not have the same product id.
    lt and gt for different products are also always false.

    NOTE: This object doesn't make sense to compare Products with different
    Product ID. The results are kind of nonsense for that case.

    This could be extended to compare, either with a more complicated
    version compare, or using other attributes.

    Awesomeos-1.1 > Awesomeos-1.0
    Awesomeos-1.1 != Awesomeos-1.0
    Awesomeos-1.0 < Awesomeos-1.0

    The algorithm used for comparisions is the rpm version compare, as used
    by rpm, yum, etc. Also known as "rpmvercmp" or "labelCompare".

    There aren't any standard product version comparison rules, but the
    rpm rules are pretty flexible, documented, and well understood.
    """
    def __init__(self, product):
        self.product = product

    def compare_keys(self, other):
        """Create a a tuple of RpmVersion objects.

        Create a RpmVersion using the product's version attribute
        as the 'version' attribute for a rpm label tuple. We let the
        epoch default to 0, and the release to 1 for each, so we are
        only comparing the difference in the version attribute.
        """
        if self.product.id == other.product.id:
            return (RpmVersion(version=self.product.version),
                    RpmVersion(version=other.product.version))
        return None

    def __str__(self):
        return "<ComparableProduct id=%s version=%s name=%s product=%s>" % \
                (self.product.id, self.product.version, self.product.name, self.product)


class ComparableProductCert(ComparableMixin):
    """Compareable version of ProductCert.

    Used to determine the "newer" of two ProductCerts. Initially just based
    on a comparison of a ComparableProduct built from the Product, which compares
    using the Product.version field."""

    def __init__(self, product_cert):
        self.product_cert = product_cert
        self.product = self.product_cert.products[0]
        self.comp_product = ComparableProduct(self.product)

    # keys used to compare certificate. For now, just the keys for the
    # Product.version. This could include say, certificate serial or issue date
    def compare_keys(self, other):
        return self.comp_product.compare_keys(other.comp_product)
