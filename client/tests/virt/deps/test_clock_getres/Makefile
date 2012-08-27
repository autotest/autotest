CC = gcc
PROG = test_clock_getres
SRC = test_clock_getres.c
LIBS = -lrt

all: $(PROG)

$(PROG):
	$(CC) $(LIBS) -o $(PROG) $(SRC)
clean:
	rm -f $(PROG)
