
TARGET=synctest
FLAGS= -Wall -O2

all: synctest.c
	$(CROSS_COMPILE)gcc $(FLAGS) $^ -o $(TARGET)

clean:
	rm -f $(TARGET) *.o .depend *.*~

