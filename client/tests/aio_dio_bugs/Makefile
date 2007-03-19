CC=gcc
LDFLAGS=-laio
CFLAGS=-W -Wall

TESTS=aio-dio-invalidate-failure

all: $(TESTS)

aio-dio-invalidate-failure: aio-dio-invalidate-failure.c
	$(CC) $(CFLAGS) $(LDFLAGS) -o $@ $^
