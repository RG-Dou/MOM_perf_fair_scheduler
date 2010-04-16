import libvirt
import logging

class libvirtInterface:
    """
    libvirtInterface provides a wrapper for the libvirt API so that libvirt-
    related error handling can be consolidated in one place.  An instance of
    this class provides a single libvirt connection that can be shared by all
    threads.  If the connection is broken, an attempt will be made to reconnect.
    """
    def __init__(self, uri):
        self.conn = None
        self.uri = uri
        self.logger = logging.getLogger('mom.libvirtInterface')
        libvirt.registerErrorHandler(self._error_handler, None)
        self._connect()

    def __del__(self):
        if self.conn is not None:
            self.conn.close()

    def _error_handler(ctx, error):
        pass

    def _connect(self):
        try:
            self.conn = libvirt.open(self.uri)
        except libvirt.libvirtError, e:
            self.logger.error("libvirtInterface: error setting up " \
                    "connection: %s", e.message)
            
    def _reconnect(self):
        try:
            self.conn.close()
        except libvirt.libvirtError:
            pass # The connection is in a strange state so ignore these
        try:
            self._connect()
        except libvirt.libvirtError, e:
            self.logger.error('libvirtInterface: Exception while reconnecting')

    def listDomainsID(self):
        try:
            dom_list = self.conn.listDomainsID()
        except libvirt.libvirtError, e:
            self.handleException(e)
            return []
        return dom_list

    def getDomainFromID(self, dom_id):
        try:
            dom = self.conn.lookupByID(dom_id)
        except libvirt.libvirtError, e:
            self.handleException(e)
            return None
        else:
            return dom
            
    def domainIsRunning(self, domain):
        try:
            if domain.info()[0] == libvirt.VIR_DOMAIN_RUNNING:
                return True
        except libvirt.libvirtError, e:
            self.handleException(e)
        return False
        
    def domainGetName(self, domain):
        try:
            name = domain.name()
        except libvirt.libvirtError, e:
            self.handleException(e)
            return None
        return name
            
    def domainGetUUID(self, domain):
        try:
            uuid = domain.UUIDString()
        except libvirt.libvirtError, e:
            self.handleException(e)
            return None
        return uuid
        
    def domainGetInfo(self, domain):
        try:
            info = domain.info()
        except libvirt.libvirtError, e:
            self.handleException(e)
            return None
        return info
        
    def domainGetMemoryStats(self, domain):
        try:
            stats = domain.memoryStats()
        except libvirt.libvirtError, e:
            self.handleException(e)
            return None
        return stats
        
    def domainSetBalloonTarget(self, domain, target):
        try:
            return domain.setMemory(target)
        except libvirt.libvirtError, e:
            self.handleException(e)
            return False
        
    def handleException(self, e):
        reconnect_errors = (libvirt.VIR_ERR_SYSTEM_ERROR,libvirt.VIR_ERR_INVALID_CONN)
        error = e.get_error_code()
        if error in reconnect_errors:
            self.logger.warn('libvirtInterface: connection lost, reconnecting.')
            self._reconnect()
        else:
            self.logger.warn('libvirtInterface: Unhandled libvirt exception.')
