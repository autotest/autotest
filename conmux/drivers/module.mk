# (C) Copyright IBM Corp. 2004, 2005, 2006
# Author: Andy Whitcroft <andyw@uk.ibm.com>
#
# The Console Multiplexor is released under the GNU Public License V2

DRIVERS:=blade hmc reboot-netfinity reboot-newisys reboot-numaq \
	reboot-rsa reboot-rsa2 zseries-console x3270_glue.expect \
	reboot-acs48 reboot-apc reboot-laurel

install::
	@[ -d $(BASE)/lib/drivers ] || mkdir $(BASE)/lib/drivers
	for f in $(DRIVERS); do \
	    rm -f $(BASE)/lib/drivers/$$f; \
	    cp -p drivers/$$f $(BASE)/lib/drivers/$$f; \
	    chmod 755 $(BASE)/lib/drivers/$$f; \
	done
