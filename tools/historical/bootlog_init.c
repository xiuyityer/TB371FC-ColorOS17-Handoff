/* SPDX-License-Identifier: GPL-2.0-or-later
 * TB371FC slot A diagnostics only. Record kmsg in a builder-verified unused
 * boot_a padding window [80 MiB,84 MiB). Never mount/format a filesystem.
 * /dev/sde11 is major 8 minor 75 on the specifically guarded test device.
 */
typedef unsigned long ulong;
typedef unsigned int u32;
static char pending[2<<20],record[16384],header[4096],check[4096];
struct log_header {char magic[16];u32 version,header_size;ulong committed;u32 crc,flags;char token[64];};
#define BASE (80UL<<20)
#define CAP ((4UL<<20)-4096)
#define TOKEN "0003-c17-bootlog-20261117-r2"
void *memcpy(void *d,const void *s,ulong n){volatile char*a=d;const char*b=s;for(ulong i=0;i<n;i++)a[i]=b[i];return d;}
void *memset(void *d,int c,ulong n){volatile char*a=d;for(ulong i=0;i<n;i++)a[i]=c;return d;}
static long sys(long nr,long a,long b,long c,long d){
 register long x0 __asm__("x0")=a,x1 __asm__("x1")=b,x2 __asm__("x2")=c,x3 __asm__("x3")=d,x4 __asm__("x4")=0,x8 __asm__("x8")=nr;
 __asm__ volatile("svc #0":"+r"(x0):"r"(x1),"r"(x2),"r"(x3),"r"(x4),"r"(x8):"memory","cc");return x0;
}
static long openfile(const char*p,long f){return sys(56,-100,(long)p,f,0);}
static int equal(const char*a,const char*b,ulong n){for(ulong i=0;i<n;i++)if(a[i]!=b[i])return 0;return 1;}
static int put(long fd,const char*p,ulong n,ulong off){while(n){long r=sys(68,fd,(long)p,n,off);if(r<=0)return -1;p+=r;n-=r;off+=r;}return 0;}
static u32 update(u32 crc,const char*p,ulong n){for(ulong i=0;i<n;i++){crc^=(unsigned char)p[i];for(int j=0;j<8;j++)crc=(crc>>1)^((0U-(crc&1))&0xedb88320U);}return crc;}
static int commit(long fd,ulong size,u32 crc,u32 flags){
 struct log_header*h=(struct log_header*)header;h->committed=size;h->crc=crc^0xffffffffU;h->flags=flags;
 if(sys(82,fd,0,0,0)<0)return -1;
 if(put(fd,header,sizeof(header),BASE)<0)return -1;
 return sys(82,fd,0,0,0)<0?-1:0;
}
static void collect(int test){
 long input=openfile("/c17_kmsg",2048),output=-1;
 if(input<0)input=openfile("/dev/kmsg",2048);
 if(input<0)return;
 ulong buffered=0,written=0;u32 crc=0xffffffffU;
 struct log_header*h=(struct log_header*)header;memcpy(h->magic,"C17_BOOTLOG_V1",14);h->version=1;h->header_size=4096;memcpy(h->token,TOKEN,sizeof(TOKEN));
 for(int iteration=0;iteration<(test?100:12000)&&written<CAP;iteration++){
  if(output<0){
   long fd=openfile(test?"/tmp/c17-bootlog-test.img":"/c17_bootlog",2);
   if(fd>=0){
    long n=sys(67,fd,(long)check,sizeof(check),BASE);int zero=1;
    for(ulong i=0;i<sizeof(check);i++)if(check[i])zero=0;
    if(n==sizeof(check)&&(zero||(equal(check,"C17_BOOTLOG_V1",14)&&equal(check+40,TOKEN,sizeof(TOKEN))))){
     output=fd;
     if(buffered){if(put(output,pending,buffered,BASE+4096)<0)break;crc=update(crc,pending,buffered);written=buffered;buffered=0;}
     if(commit(output,written,crc,0)<0)break;
    }else{sys(57,fd,0,0,0);break;}
   }
  }
  ulong before=written;
  for(int j=0;j<128;j++){
   long n=sys(63,input,(long)record,sizeof(record),0);if(n==-32)continue;if(n<=0)break;
   if(output>=0){
    if(written+(ulong)n>CAP)break;
    if(put(output,record,n,BASE+4096+written)<0)goto finished;
    crc=update(crc,record,n);written+=n;
   }else if(buffered+(ulong)n<sizeof(pending)){memcpy(pending+buffered,record,n);buffered+=n;}
  }
  if(output>=0&&written!=before&&commit(output,written,crc,0)<0)break;
  long delay[2]={0,10000000};sys(101,(long)delay,0,0,0);
 }
finished:
 if(output>=0){commit(output,written,crc,1);sys(57,output,0,0,0);}sys(57,input,0,0,0);
}
__attribute__((noreturn,used)) void entry(ulong*stack){
 char**argv=(char**)(stack+1),**envp=argv+stack[0]+1;
 if(sys(172,0,0,0,0)!=1){collect(1);sys(93,0,0,0,0);for(;;);}
 sys(33,-100,(long)"/c17_kmsg",0020600,267);
 sys(33,-100,(long)"/c17_bootlog",0060600,(8<<8)|75);
 long child=sys(220,17,0,0,0);if(child==0){collect(0);sys(93,0,0,0,0);for(;;);}
 sys(221,(long)"/init.android",(long)argv,(long)envp,0);for(;;)sys(93,127,0,0,0);
}
__asm__(".global _start\n_start:\nmov x0, sp\nbl entry\nb .\n");
