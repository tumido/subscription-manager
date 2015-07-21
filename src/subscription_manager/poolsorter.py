

class PoolSorter(object):
    def sorted(self, pools):
        return sorted(pools, key=self.pool_key)

    def pool_key(self, pool):
        return pool.get('productId', None)
