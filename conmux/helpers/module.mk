# (C) Copyright IBM Corp. 2004, 2005, 2006
# Author: Andy Whitcroft <andyw@uk.ibm.com>
#
# The Console Multiplexor is released under the GNU Public License V2

HELPERS:=autoboot-helper tickle-helper

install::
	@[ -d $(BASE)/lib/helpers ] || mkdir $(BASE)/lib/helpers
	for f in $(HELPERS); do \
	    rm -f $(BASE)/lib/helpers/$$f; \
	    cp -p helpers/$$f $(BASE)/lib/helpers/$$f; \
	    chmod 755 $(BASE)/lib/helpers/$$f; \
	done
