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
LIBDIR=/lib
LOGDIR=/var/log
SYSCONFIGDIR=/etc
MODULES=helpers drivers
BINDIR=/bin
SBINDIR=/sbin

all::

install::
	@[ -d $(BASE) ] || mkdir -p $(BASE)
	@[ -d $(BASE)$(BINDIR) ] || mkdir $(BASE)$(BINDIR)
	@[ -d $(BASE)$(LIBDIR)/conmux ] || mkdir -p $(BASE)$(LIBDIR)/conmux
	@[ -d $(BASE)$(SBINDIR) ] || mkdir $(BASE)$(SBINDIR)
	@[ -d $(BUILD)$(LOGDIR)/conmux ] || mkdir -p $(BUILD)$(LOGDIR)/conmux
	@[ -d $(BUILD)$(SYSCONFIGDIR)/conmux ] || mkdir -p $(BUILD)$(SYSCONFIGDIR)/conmux
	for f in $(BINS); do \
	    rm -f $(BASE)$(BINDIR)/$$f; \
	    cp -p $$f $(BASE)$(BINDIR)/$$f; \
	    chmod 755 $(BASE)$(BINDIR)/$$f; \
	done
	for f in $(SBIN); do \
	    rm -f $(BASE)$(SBINDIR)/$$f; \
	    cp -p $$f $(BASE)$(SBINDIR)/$$f; \
	    chmod 755 $(BASE)$(SBINDIR)/$$f; \
	done
	for f in $(LIBS); do \
	    rm -f $(BASE)$(LIBDIR)/conmux/$$f; \
	    cp -p $$f $(BASE)$(LIBDIR)/conmux/$$f; \
	    chmod 644 $(BASE)$(LIBDIR)/conmux/$$f; \
	done

release::
	$(MAKE) BUILD=build install
	(cd build; tar cf - *) | gzip >conmux.tgz
	rm -rf build

clean::
	rm -f conmux.tgz

include $(patsubst %, %/module.mk, $(MODULES))
