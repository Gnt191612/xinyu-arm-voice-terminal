# 使用板载编译器或厂商匹配sysroot的交叉编译器，不假定板子ABI。
CC = gcc
CFLAGS = -O2 -Wall -Wextra -march=armv7-a -marm

all: libpcm_gate.so compare

libpcm_gate.so: pcm_gate.S
	$(CC) $(CFLAGS) -fPIC -shared -o $@ $<

compare: compare.c reference.c pcm_gate.S
	$(CC) $(CFLAGS) -o $@ $^
