all:
	make rss.exe finish.exe
rss.exe:
	i686-pc-mingw32-g++ rss.cpp -O2 -static-libgcc -lws2_32 -lshlwapi -mwindows -o rss.exe
finish.exe:
	i686-pc-mingw32-g++ finish.cpp -O2 -lws2_32 -o finish.exe
clean:
	rm -rf rss.exe finish.exe
