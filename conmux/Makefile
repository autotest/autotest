# (C) Copyright IBM Corp. 2004, 2005, 2006
# Author: Andy Whitcroft <andyw@uk.ibm.com>
#
# The Console Multiplexor is released under the GNU Public License V2
BUILD=
PREFIX=/usr/local/conmux
BASE=$(BUILD)$(PREFIX)
BINS=console conmux-attach
LIBS=Conmux.pm
SBIN=conmux-registry conmux start

MODULES=helpers drivers

all::

install::
	@[ -d $(BASE) ] || mkdir -p $(BASE)
	@[ -d $(BASE)/bin ] || mkdir $(BASE)/bin
	@[ -d $(BASE)/lib ] || mkdir $(BASE)/lib
	@[ -d $(BASE)/sbin ] || mkdir $(BASE)/sbin
	@[ -d $(BASE)/log ] || mkdir $(BASE)/log
	@[ -d $(BASE)/etc ] || mkdir $(BASE)/etc
	for f in $(BINS); do \
	    rm -f $(BASE)/bin/$$f; \
	    cp -p $$f $(BASE)/bin/$$f; \
	    chmod 755 $(BASE)/bin/$$f; \
	done
	for f in $(SBIN); do \
	    rm -f $(BASE)/sbin/$$f; \
	    cp -p $$f $(BASE)/sbin/$$f; \
	    chmod 755 $(BASE)/sbin/$$f; \
	done
	for f in $(LIBS); do \
	    rm -f $(BASE)/lib/$$f; \
	    cp -p $$f $(BASE)/lib/$$f; \
	    chmod 644 $(BASE)/lib/$$f; \
	done

release::
	$(MAKE) BUILD=build install
	(cd build; tar cf - *) | gzip >conmux.tgz
	rm -rf build

clean::
	rm -f conmux.tgz

include $(patsubst %, %/module.mk, $(MODULES))
