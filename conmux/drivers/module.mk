# (C) Copyright IBM Corp. 2004, 2005, 2006
# Author: Andy Whitcroft <andyw@uk.ibm.com>
#
# The Console Multiplexor is released under the GNU Public License V2

DRIVERS:=blade dli-lpc hmc ivm reboot-netfinity reboot-newisys reboot-numaq \
	reboot-rsa reboot-rsa2 zseries-console x3270_glue.expect \
	reboot-acs48 reboot-apc reboot-laurel fence_apc_snmp.py

install::
	@[ -d $(BASE)$(LIBDIR)/conmux/drivers ] || mkdir $(BASE)$(LIBDIR)/conmux/drivers
	for f in $(DRIVERS); do \
	    rm -f $(BASE)$(LIBDIR)/conmux/drivers/$$f; \
	    cp -p drivers/$$f $(BASE)$(LIBDIR)/conmux/drivers/$$f; \
	    chmod 755 $(BASE)$(LIBDIR)/conmux/drivers/$$f; \
	done
