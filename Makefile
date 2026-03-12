CC       = gcc
CFLAGS   = -O3 -march=native -std=c99 -Wall -lm
SRC      = worker.c
BIN      = worker
BIN_B    = worker_boinc

BOINC_INC ?= /usr/include/boinc
BOINC_LIB ?= /usr/lib

.PHONY: all boinc test clean

all: $(BIN)

$(BIN): $(SRC)
	$(CC) $(CFLAGS) -o $@ $^
	@echo "Built: $(BIN)"

boinc: $(SRC)
	$(CC) $(CFLAGS) -DBOINC \
	    -I$(BOINC_INC) -L$(BOINC_LIB) \
	    -o $(BIN_B) $^ \
	    -lboinc_api -lboinc -lpthread -lm
	@echo "Built: $(BIN_B)"

test: $(BIN)
	printf "n_start 0\nn_end   500\nx_limit 100000\n" > /tmp/wu_test.txt
	./$(BIN) /tmp/wu_test.txt /tmp/result_test.txt
	@echo "=== Solutions (n=0..500, |x|<=100000) ==="
	@cat /tmp/result_test.txt && echo "(none)" || true

clean:
	rm -f $(BIN) $(BIN_B)
