/* Test-launch-only X11 hint. No focus requests, input injection or game changes. */
#define _GNU_SOURCE
#include <X11/Xlib.h>
#include <X11/Xatom.h>
#include <dlfcn.h>
#include <limits.h>
#include <stdatomic.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

static _Atomic(void *) x11_handle;
static atomic_int stamped;
typedef void *(*Lookup)(void *, const char *);

static Lookup lookup(void) {
    Lookup fn = (Lookup)dlvsym(RTLD_NEXT, "dlsym", "GLIBC_2.2.5");
    if (!fn) _exit(125);
    return fn;
}

static int enabled(void) {
    const char *expected = getenv("VOLIBEAR_X11_STARTUP_HINT_EXE");
    char actual[PATH_MAX];
    ssize_t count = readlink("/proc/self/exe", actual, sizeof(actual) - 1);
    if (!expected || count < 0) return 0;
    actual[count] = '\0';
    return strcmp(expected, actual) == 0;
}

static int normal_map(Display *display, Window window) {
    Lookup find = lookup();
    void *handle = atomic_load(&x11_handle);
    int (*map)(Display *, Window) = find(handle, "XMapWindow");
    Atom (*atom)(Display *, const char *, Bool) = find(handle, "XInternAtom");
    int (*get)(Display *, Window, Atom, long, long, Bool, Atom, Atom *, int *, unsigned long *, unsigned long *, unsigned char **) = find(handle, "XGetWindowProperty");
    int (*set)(Display *, Window, Atom, Atom, int, int, const unsigned char *, int) = find(handle, "XChangeProperty");
    int (*release)(void *) = find(handle, "XFree");
    if (!map || !atom || !get || !set || !release) _exit(125);
    if (!atomic_load(&stamped)) {
        Atom type; int format;
        unsigned long count, remaining;
        unsigned char *data = NULL;
        int normal = get(display, window, atom(display, "_NET_WM_WINDOW_TYPE", False), 0, 1, False,
            XA_ATOM, &type, &format, &count, &remaining, &data) == Success &&
            type == XA_ATOM && format == 32 && count == 1 && data &&
            *(unsigned long *)data == atom(display, "_NET_WM_WINDOW_TYPE_NORMAL", False);
        if (data) release(data);
        data = NULL;
        int owned = get(display, window, atom(display, "_NET_WM_PID", False), 0, 1, False,
            XA_CARDINAL, &type, &format, &count, &remaining, &data) == Success &&
            type == XA_CARDINAL && format == 32 && count == 1 && data &&
            *(unsigned long *)data == (unsigned long)getpid();
        if (data) release(data);
        if (normal && owned && !atomic_exchange(&stamped, 1)) {
            unsigned long timestamp = 0;
            /* Same X connection: this property request precedes the first Map request. */
            set(display, window, atom(display, "_NET_WM_USER_TIME", False), XA_CARDINAL,
                32, PropModeReplace, (const unsigned char *)&timestamp, 1);
            fprintf(stderr, "WINDOW_STARTUP_HINT before_map xid=%lu user_time=0 pid=%ld\n", window, (long)getpid());
            fflush(stderr);
        }
    }
    return map(display, window);
}

/* Godot dynamically loads X11 and looks up XMapWindow on that explicit handle. */
void *dlsym(void *handle, const char *name) {
    Lookup find = lookup();
    void *original = find(handle, name);
    if (original && strcmp(name, "XMapWindow") == 0 && enabled()) {
        atomic_store(&x11_handle, handle);
        return (void *)normal_map;
    }
    return original;
}
