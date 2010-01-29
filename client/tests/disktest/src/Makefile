CFLAGS = -O2 -Wall -D_FILE_OFFSET_BITS=64 -D _GNU_SOURCE -static
TARGET = disktest


all: $(TARGET)


$(TARGET): disktest.c
	$(CC) $(CFLAGS) $^ -o $@


clean:
	$(RM) $(TARGET)
