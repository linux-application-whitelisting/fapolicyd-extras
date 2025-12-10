
# File surveys
This directory holds utilities to let you survey the types of files on
your system.

## fanotify_mime_type
`fanotify_mime_type` listens for fanotify permission events and records MIME
usage. It holds each permission event long enough to ask libfapolicyd for the
file's MIME type via `get_file_type_from_fd`, increments an in-memory counter
for that MIME type, then always allows the access to continue. On `SIGINT` or
`SIGTERM` the program unhooks from fanotify, sorts the collected MIME types by
count, and prints the top 100 as tab-separated columns.

This allows studying what file types are used in different workloads.

### Building

The program relies on `libfapolicyd` `libmagic`, and `libudev`. You will need to clone and build the fapolicyd application. libfapolicyd is located in fapolicyd/src. After configuring and building the repository, you can build the tool against the produced library:

Edit the Makefile to point the LIBFAPOLICYD variable to the full path to your freshly built fapolicyd project is. Then just run `make`.

```
git clone https://github.com/linux-application-whitelisting/fapolicyd.git
git clone https://github.com/linux-application-whitelisting/fapolicyd-extras.git
cd fapolicyd
autoreconf -f --install
./configure --with-audit --with-rpm --disable-shared
make

# Now we are ready to make the file usage tool
cd ../fapolicyd-extras/file-surveys
vi Makefile     #  <-- edit the path to ../../fapolicyd/src
make
```

Run the binary as root so it can subscribe to fanotify permission events and write its findings after it receives `SIGINT` (Ctrl+C) or `SIGTERM`. Example output from a desktop run:

```
application/x-sharedlib	4233
text/xml	2349
application/octet-stream	1542
text/plain	1406
application/gzip	1067
application/x-executable	351
font/sfnt	109
application/x-bytecode.python	99
application/vnd.ms-opentype	49
text/x-shellscript	42
image/png	33
image/svg+xml	28
application/json	23
application/javascript	19
```
