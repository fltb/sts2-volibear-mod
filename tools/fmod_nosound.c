/* Test-process-only FMOD output adapter. No game logic or asset changes. */
#define _GNU_SOURCE
#include <dlfcn.h>
#include <stdio.h>
#include <stdlib.h>

typedef int (*studio_init_fn)(void *, int, unsigned int, unsigned int, void *);
typedef int (*get_core_fn)(void *, void **);
typedef int (*set_output_fn)(void *, int);

int _ZN4FMOD6Studio6System10initializeEijjPv(void *studio, int channels,
        unsigned int studio_flags, unsigned int flags, void *extra) {
    studio_init_fn real_init = (studio_init_fn)dlsym(RTLD_NEXT, "_ZN4FMOD6Studio6System10initializeEijjPv");
    get_core_fn get_core = (get_core_fn)dlsym(RTLD_NEXT, "FMOD_Studio_System_GetCoreSystem");
    set_output_fn set_output = (set_output_fn)dlsym(RTLD_NEXT, "FMOD_System_SetOutput");
    if (!real_init || !get_core || !set_output || !getenv("VOLIBEAR_TEST_DATA_ROOT")) {
        fputs("[Volibear] AUDIO_ADAPTER_ERROR missing symbol or isolation guard\n", stderr);
        return 31;
    }
    void *core = NULL;
    int result = get_core(studio, &core);
    if (!result) result = set_output(core, 2); /* FMOD_OUTPUTTYPE_NOSOUND */
    if (result) return result;
    fputs("[Volibear] AUDIO_OUTPUT nosound\n", stderr);
    return real_init(studio, channels, studio_flags, flags, extra);
}
