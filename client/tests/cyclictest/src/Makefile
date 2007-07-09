
TARGET=cyclictest
FLAGS= -Wall -Wno-nonnull -O2
LIBS = -lpthread -lrt

all: cyclictest.c
	$(CROSS_COMPILE)gcc $(FLAGS) $^ -o $(TARGET) $(LIBS)

clean:
	rm -f $(TARGET) *.o .depend *.*~

