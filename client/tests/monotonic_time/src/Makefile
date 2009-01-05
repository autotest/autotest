CC=	cc

CFLAGS=	-O -std=gnu99 -Wall
LDFLAGS=-static
LIBS=	-lpthread -lrt

PROG=	time_test

SRCS=	time_test.c cpuset.c threads.c logging.c
HDRS=	spinlock.h cpuset.h threads.h logging.h
OBJS=	$(SRCS:.c=.o)

all:	$(PROG)

$(PROG):	$(OBJS)
	$(CC) $(LDFLAGS) -o $(PROG) $(OBJS) $(LIBS)

$(OBJS):	$(HDRS)

clean:
	-rm -f $(OBJS)

clobber:	clean
	-rm -f $(PROG)
