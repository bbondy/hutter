#include "ppmd_page_ptr.h"
namespace ppmd_page {
Vorrat V; int hilfs=0;
int start(unsigned long long bytes,unsigned long long,const char*) {
 V={}; V.heapgr=bytes;
 V.heap=(unsigned char*)mmap(nullptr,bytes,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS,-1,0);
 if(V.heap==MAP_FAILED) { perror("native PPMd mmap"); return 1; }
 fprintf(stderr,"native PPMd: anonymous heap %llu MiB; no Linux RSS clamp\n",bytes>>20);
 return 0;
}
void freigeben() { if(V.heap) munmap(V.heap,V.heapgr);V={}; }
void schluss() { freigeben(); }
void bericht(unsigned long long) {}
void dyn_tick() {}
void zonen_setze(unsigned long long) {}
void zonen_aus() {}
void kopiere(unsigned char* d,const unsigned char* s,unsigned long long n) { memmove(d,s,n); }
}
