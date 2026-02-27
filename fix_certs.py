import os; import ssl; import stat; import subprocess; import sys; certifi=__import__('certifi'); openssl_dir, openssl_cafile = os.path.split(ssl.get_default_verify_paths().openssl_cafile)
print(' -- pip install certifi')
subprocess.check_call([sys.executable, '-E', '-s', '-m', 'pip', 'install', '--upgrade', 'certifi'])
print(' -- removing any existing file or link')
try:
    os.remove(openssl_cafile)
except FileNotFoundError:
    pass
print(' -- creating symlink to certifi certificate bundle')
os.symlink(certifi.where(), openssl_cafile)
print(' -- setting permissions')
os.chmod(openssl_cafile, stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
