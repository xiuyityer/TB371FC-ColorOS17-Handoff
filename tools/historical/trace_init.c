/* SPDX-License-Identifier: GPL-2.0-or-later
 * Short-lived early kmsg recorder. Never mounts/checks a disk filesystem.
 * Waits for Android to mount metadata, then opens a unique per-boot file.
 */
typedef unsigned long ulong;
static char pending[2 << 20];
static char record[16384];
void *memcpy(void *d, const void *s, ulong n) {
    volatile char *a=d; const char *b=s; for(ulong i=0;i<n;i++)a[i]=b[i]; return d;
}
static long sys(long nr,long a,long b,long c,long d) {
    register long x0 __asm__("x0")=a,x1 __asm__("x1")=b,x2 __asm__("x2")=c,x3 __asm__("x3")=d;
    register long x4 __asm__("x4")=0,x8 __asm__("x8")=nr;
    __asm__ volatile("svc #0":"+r"(x0):"r"(x1),"r"(x2),"r"(x3),"r"(x4),"r"(x8):"memory","cc");return x0;
}
static long openfile(const char *p,long flags,long mode) {return sys(56,-100,(long)p,flags,mode);}
static void writeall(long fd,const char *p,ulong n) {
    while(n){long r=sys(64,fd,(long)p,n,0);if(r<=0)return;p+=r;n-=r;}
}
static void collect(void) {
    long input=openfile("/c17_kmsg",2048,0),output=-1,procdir=-1;
    ulong buffered=0,written=0;
    if(input<0)return;
    /* Give this child a private procfs before PID 1 starts switch_root.
     * PID 1 keeps its original mount namespace and normal mount sequence. */
    if(sys(97,0x20000,0,0,0)==0) {
        sys(40,0,(long)"/",0,0x40000|0x4000);
        sys(40,(long)"proc",(long)"/proc",(long)"proc",14);
    }
    for(int iteration=0;iteration<12000 && written<(16<<20);iteration++) {
        if(output<0) {
            ulong info[32];
            if(procdir<0) {
                long candidate=openfile("/proc",65536,0);
                if(candidate>=0) {
                    if(sys(44,candidate,(long)info,0,0)==0 && info[0]==0x9fa0)procdir=candidate;
                    else sys(57,candidate,0,0,0);
                }
            }
            /* PID 1 changes root; our inherited root can become detached.
             * Retain procfs and follow PID 1's current root through its fd. */
            long directory=procdir>=0?sys(56,procdir,(long)"1/root/metadata",65536,0):-1;
            if(directory>=0 && sys(44,directory,(long)info,0,0)==0 && info[0]==0xef53) {
                /* Anchor operations to the mounted filesystem across switch_root. */
                sys(34,directory,(long)"c17-port-early",0700,0);
                char path[128]="c17-port-early/";
                ulong pos=sizeof("c17-port-early/")-1;
                const ulong prefixlen=pos;
                long fd=sys(56,procdir,(long)"sys/kernel/random/boot_id",0,0);
                char uuid[40]; long count=fd>=0?sys(63,fd,(long)uuid,36,0):-1;
                if(fd>=0)sys(57,fd,0,0,0);
                if(count==36) {
                    int valid=1;
                    for(int i=0;i<36;i++)if(!((uuid[i]>='0'&&uuid[i]<='9')||(uuid[i]>='a'&&uuid[i]<='f')||uuid[i]=='-'))valid=0;
                    if(valid){for(int i=0;i<36;i++)path[pos++]=uuid[i];}
                }
                if(pos==prefixlen){const char *s="unknown";while(*s)path[pos++]=*s++;}
                path[pos++]='.';path[pos++]='l';path[pos++]='o';path[pos++]='g';path[pos]=0;
                output=sys(56,directory,(long)path,1|64|128,0600); /* O_EXCL: preserve earlier boots. */
                if(output>=0 && buffered){writeall(output,pending,buffered);written+=buffered;buffered=0;sys(82,output,0,0,0);}
            }
            if(directory>=0)sys(57,directory,0,0,0);
        }
        for(int j=0;j<128;j++) {
            long n=sys(63,input,(long)record,sizeof(record),0);
            if(n==-32)continue; /* kmsg ring overrun: keep later records. */
            if(n<=0)break;
            if(output>=0){writeall(output,record,n);written+=n;}
            else if(buffered+(ulong)n<sizeof(pending)){memcpy(pending+buffered,record,n);buffered+=n;}
        }
        if(output>=0 && iteration%100==0)sys(82,output,0,0,0);
        long delay[2]={0,10000000};sys(101,(long)delay,0,0,0);
    }
    if(output>=0){sys(82,output,0,0,0);sys(57,output,0,0,0);}
    sys(57,input,0,0,0);
    if(procdir>=0)sys(57,procdir,0,0,0);
}
__attribute__((noreturn,used)) void entry(ulong *stack) {
    char **argv=(char **)(stack+1),**envp=argv+stack[0]+1;
    sys(33,-100,(long)"/c17_kmsg",0020600,267);
    long child=sys(220,17,0,0,0);
    if(child==0){collect();sys(93,0,0,0,0);for(;;);}
    sys(221,(long)"/init.android",(long)argv,(long)envp,0);
    for(;;)sys(93,127,0,0,0);
}
__asm__(".global _start\n_start:\nmov x0, sp\nbl entry\nb .\n");
