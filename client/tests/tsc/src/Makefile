CC=		cc
CFLAGS=		-O
LDFLAGS=	--static
LIBS=		-lpthread

PROGS=		checktsc

SRCS=		checktsc.c
OBJS=		${SRCS:.c=.o}


all:		$(PROGS)

checktsc:	$(OBJS)
		$(CC) $(LDFLAGS) -o checktsc $(OBJS) $(LIBS)

clean:
		-rm -f $(OBJS)

clobber:	clean
		-rm -f $(PROGS)
