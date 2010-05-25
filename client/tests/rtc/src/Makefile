CC=		cc
CFLAGS=	        -O -Wall -Wstrict-prototypes

PROGS=		rtctest

SRCS=		rtctest.c
OBJS=		${SRCS:.c=.o}


all:		$(PROGS)

rtctest:	$(OBJS)
		$(CC) $(LDFLAGS) -o rtctest $(OBJS)

clean:
		-rm -f $(OBJS)

clobber:	clean
		-rm -f $(PROGS)
