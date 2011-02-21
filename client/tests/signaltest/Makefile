
CC ?= $(CROSS_COMPILE)gcc
TARGET=signaltest
FLAGS= -Wall -O2 
LIBS = -lpthread -lrt

all: signaltest.c
	$(CC) $(FLAGS) $^ -o $(TARGET) $(LIBS)

clean:
	rm -f $(TARGET) *.o .depend *.*~

