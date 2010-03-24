BINDIR=/usr/bin
LOCALESDIR=/usr/share/locale
MANDIR=/usr/share/man/man1
WARNFLAGS=-Wall  -W -Wshadow
CFLAGS?=-O1 -g ${WARNFLAGS}
CC?=gcc


# 
# The w in -lncursesw is not a typo; it is the wide-character version
# of the ncurses library, needed for multi-byte character languages
# such as Japanese and Chinese etc.
#
# On Debian/Ubuntu distros, this can be found in the
# libncursesw5-dev package. 
#

OBJS = powertop.o config.o process.o misctips.o bluetooth.o display.o suggestions.o wireless.o cpufreq.o \
	sata.o xrandr.o ethernet.o cpufreqstats.o usb.o urbnum.o intelcstates.o
	

powertop: $(OBJS) Makefile powertop.h
	$(CC) ${CFLAGS}  $(OBJS) -lncursesw -o powertop
	@(cd po/ && $(MAKE))

powertop.1.gz: powertop.1
	gzip -c $< > $@

install: powertop powertop.1.gz
	mkdir -p ${DESTDIR}${BINDIR}
	cp powertop ${DESTDIR}${BINDIR}
	mkdir -p ${DESTDIR}${MANDIR}
	cp powertop.1.gz ${DESTDIR}${MANDIR}
	@(cd po/ && env LOCALESDIR=$(LOCALESDIR) DESTDIR=$(DESTDIR) $(MAKE) $@)

# This is for translators. To update your po with new strings, do :
# svn up ; make uptrans LG=fr # or de, ru, hu, it, ...
uptrans:
	xgettext -C -s -k_ -o po/powertop.pot *.c *.h
	@(cd po/ && env LG=$(LG) $(MAKE) $@)

clean:
	rm -f *~ powertop powertop.1.gz po/powertop.pot DEADJOE svn-commit* *.o *.orig 
	@(cd po/ && $(MAKE) $@)


dist:
	rm -rf .svn po/.svn DEADJOE po/DEADJOE todo.txt Lindent svn-commit.* dogit.sh git/ *.rej *.orig
