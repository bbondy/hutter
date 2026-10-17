#pragma once
#include <stdlib.h>
#include <sys/mman.h>
#include <string.h>
inline int malloc_trim(size_t) { return 0; }
inline int mallopt(int, int) { return 0; }
#define M_MMAP_THRESHOLD 0
#define POSIX_FADV_DONTNEED 0
inline int posix_fadvise(int, off_t, off_t, int) { return 0; }
#define MREMAP_MAYMOVE 0
inline void* mremap(void* p, size_t old_size, size_t new_size, int) {
 void* q=mmap(nullptr,new_size,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS,-1,0);
 if(q==MAP_FAILED) return q;
 memcpy(q,p,old_size < new_size ? old_size : new_size);
 munmap(p,old_size);return q;
}
