
TARGET=signaltest
FLAGS= -Wall -O2 
LIBS = -lpthread -lrt

all: signaltest.c
	$(CROSS_COMPILE)gcc $(FLAGS) $^ -o $(TARGET) $(LIBS)

clean:
	rm -f $(TARGET) *.o .depend *.*~

