from pathlib import Path
import os, subprocess, tempfile
root=Path.cwd()
up=root/'research/xnu-8796'
fd,idx=tempfile.mkstemp(prefix='sweet-patch-index-');os.close(fd);os.unlink(idx)
env=dict(os.environ,GIT_INDEX_FILE=idx)
def git(*args,**kwargs):
    return subprocess.run(['git','-C',str(up),*args],env=env,check=True,**kwargs)
try:
    git('read-tree','HEAD')
    patches=sorted([*root.glob('xnu/patches/*.patch'),*root.glob('research/blacktop-patches/*.patch')],key=lambda p:p.name)
    for p in patches:
        c=subprocess.run(['git','-C',str(up),'apply','--cached','--check',str(p)],env=env,capture_output=True)
        if c.returncode:
            if p.parent == root/'xnu/patches':
                # Sources staged by xnu/patches/*.sh in CI are not in this index.
                if 'sweet_hfs/' in c.stderr.decode() and 'does not exist in index' in c.stderr.decode():
                    print('skip (staged sources)',p.name);continue
                raise RuntimeError(p.name+': '+c.stderr.decode())
            print('skip',p.name);continue
        git('apply','--cached',str(p));print('applied',p.name)
    for tree,path in [('bt23', 'libkern/crypto/corecrypto_aes.c'),('bt28','libkern/conf/files'),('bt28','libkern/conf/Makefile.template'),('bt23', 'libkern/crypto/sweet_aes.c'),('bt23', 'libkern/crypto/sweet_aes_ct.c'),('bt23', 'libkern/crypto/sweet_aes_ct_enc.c'),('bt23', 'libkern/crypto/sweet_aes_ct_dec.c'),('bt23', 'libkern/crypto/sweet_aes_ct_cbcenc.c'),('bt23', 'libkern/crypto/sweet_aes_ct_cbcdec.c'),('bt28','bsd/conf/files'),('bt28','bsd/dev/sweet_ufs.c'),('bt28','iokit/bsddev/IOKitBSDInit.cpp'),('bt28','bsd/kern/sweet_amfi.c'),('bt28','iokit/Kernel/arm/SweetEntitlements.cpp'),('bt28','bsd/kern/bsd_init.c'),('bt28','bsd/miscfs/mockfs/mockfs_vfsops.c'),('bt28','bsd/sweet_hfs/sweet_hfs_iokit.c'),('bt28','bsd/sweet_hfs/sweet_hfs_compat.h'),('bt28','config/MASTER'),('bt28','libkern/crypto/corecrypto_md5.c'),('bt28','libkern/crypto/sweet_md5.c'),('bt28','bsd/conf/Makefile.template'),('bt22', 'bsd/sys/pthread_internal.h'),('bt22', 'bsd/pthread/sweet_pthread_compat.h'),('bt22', 'bsd/pthread/sweet_pthread_init.c'),('bt22', 'bsd/pthread/sweet_pthread_support.c'),('bt22', 'bsd/pthread/sweet_pthread_synch.c'),('bt17','osfmk/prng/prng_random.c'),('bt17','osfmk/prng/entropy.c'),('bt18','bsd/kern/kern_trustcache.c'),('bt21','iokit/KernelConfigTables.cpp'),('bt28','iokit/conf/files.arm64'),('bt19','iokit/Kernel/arm/SweetPlatformExpert.cpp'),('bt21','iokit/Kernel/arm/SweetCPU.cpp'),('bt19', 'pexpert/arm/pe_fiq.c'),('bt19', 'osfmk/arm64/sleh.c'),('bt19', 'pexpert/pexpert/arm/protos.h')]:
        data=git('show',':'+path,capture_output=True).stdout
        assert data == (root/'research'/tree/'xnu'/path).read_bytes(),path
        print('MATCH',path)
finally:
    if os.path.exists(idx):os.unlink(idx)
