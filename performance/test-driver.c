#define _XOPEN_SOURCE 500
#include <stdio.h>
#include <fcntl.h>
#include <unistd.h>
#include <stdint.h>
#include <linux/fanotify.h>
#include <stdlib.h>
#include <stdatomic.h>
#include <sys/time.h>
#include "policy.h"
#include "message.h"
#include "daemon-config.h"
#include "queue.h"
#include "database.h"

// Global variable expected by fapolicyd
unsigned int debug_mode = 0, permissive = 0;
volatile atomic_bool stop = 0;
conf_t config;

// Local variables
static int resp_fd;
static uint64_t mask = FAN_OPEN_PERM | FAN_OPEN_EXEC_PERM;
static pid_t our_pid;
static unsigned int count;

// Make the size a little bigger than
// slots in use to get some ejections
#define OBJ_CACHE_SIZE	5600
#define TEST_CASES	25000
//#define TEST_CASES	100  // callgrind takes a long time

const char *cmd_template =
	"/usr/bin/perf record --call-graph dwarf --no-inherit -p %d &";

void check_file(const char *fpath)
{
	// Stop when we've had enough
	if (++count >= OBJ_CACHE_SIZE)
		return;

	int fd = open(fpath, O_RDONLY|O_CLOEXEC);
	if (fd >= 0) {
		// Build an "event" to exercise fapolicyd's decision making
		struct fanotify_event_metadata metadata;
		metadata.fd = fd; // listener closes after reply
		metadata.pid = our_pid;
		metadata.mask = FAN_OPEN_PERM;

		make_policy_decision(&metadata, resp_fd, mask);
	}
}

int initialize_fapolicyd(void)
{
	debug_mode = DBG_NO; // Change this to 1 to see output
	set_message_mode(MSG_STDERR, debug_mode);
	if (load_daemon_config(&config)) {
		free_daemon_config(&config);
		msg(LOG_ERR, "Exiting due to bad configuration");
		return 1;
	}
	permissive = config.permissive;
	// load rules
	if (load_rules(&config))
		return 1;
	// This is for rpm loading - but we won't use it
	if (preconstruct_fifo(&config)) {
		msg(LOG_ERR, "Cannot contruct a pipe");
		return 1;
	}
	atexit(unlink_fifo);
	// Setup lru caches
	init_event_system(&config);
	if (init_database(&config)) {
		destroy_event_system();
		destroy_rules();
		free_daemon_config(&config);
		exit(1);
	}
	// Init the file test libraries
	file_init();
	// Don't let it accidently emit audit events
	policy_no_audit();

	msg(LOG_INFO, "Init complete");
	return 0;
}

/*static void teardown(void)
{
	file_close();
	close_database();
	destroy_event_system();
	destroy_config();
	free_daemon_config(&config);
}*/

int main(void)
{
	char cmd[80];
	struct timeval t0, t1;

	if (getuid() !=  0) {
		puts("You need to be root");
		return 1;
	}
	if (initialize_fapolicyd())
		return 1;

	// open fanotify response socket as dev null
	resp_fd = open("/dev/null", O_WRONLY|O_CLOEXEC);
	if (resp_fd < 0) {
		puts("Can't open dev null");
		return 1;
	}
	our_pid = getpid();

	// Start the perf recording
	snprintf(cmd, sizeof(cmd), cmd_template, our_pid);
	system(cmd);

	// Start the timer
	gettimeofday(&t0, NULL);

	FILE *file_list = fopen("file-list.txt", "r");
	if (file_list == NULL)
		return 2;

	// Loop over the files to similate cache hits
	unsigned int i;
	puts("starting scan");
	for (i=0; i < TEST_CASES; i++) {
		char path[4096];

		count = 0;
		if (fscanf(file_list, "%s\n", path)) {
		//	puts(path);
			check_file(path);
		}
	}

	stop = 1;

//	teardown();
//	close(resp_fd);

	// Stop the timer and output results
	gettimeofday(&t1, NULL);
	long seconds1  = t1.tv_sec  - t0.tv_sec;
	long useconds1 = t1.tv_usec - t0.tv_usec;
	long mseconds1 = useconds1 / 1000;
	if (mseconds1 < 0) {
		mseconds1 += 1000;
		seconds1--;
	}
	printf("Elapsed: %ld seconds, %ld milliseconds\n",seconds1,mseconds1);

	return 0;
}

