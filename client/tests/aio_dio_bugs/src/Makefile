CC=gcc
LDFLAGS=-laio
CFLAGS=-W -Wall

TESTS=aio-dio-invalidate-failure aio-dio-subblock-eof-read \
      aio-free-ring-with-bogus-nr-pages \
      aio-io-setup-with-nonwritable-context-pointer aio-dio-extend-stat

all: $(TESTS)

aio-dio-invalidate-failure: aio-dio-invalidate-failure.c
	$(CC) $(CFLAGS) $(LDFLAGS) -o $@ $^

aio-dio-subblock-eof-read: aio-dio-subblock-eof-read.c
	$(CC) $(CFLAGS) $(LDFLAGS) -o $@ $^

aio-free-ring-with-bogus-nr-pages: aio-free-ring-with-bogus-nr-pages.c
	$(CC) $(CFLAGS) $(LDFLAGS) -o $@ $^

aio-io-setup-with-nonwritable-context-pointer: aio-io-setup-with-nonwritable-context-pointer.c
	$(CC) $(CFLAGS) $(LDFLAGS) -o $@ $^

aio-dio-extend-stat: aio-dio-extend-stat.c
	$(CC) $(CFLAGS) $(LDFLAGS) -lpthread -o $@ $^
