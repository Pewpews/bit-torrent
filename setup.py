import re
from setuptools import setup, find_packages

with open('happy_bittorrent/__init__.py', 'r') as f:
    version = re.search(r'^__version__\s*=\s*[\'"]([^\'"]*)[\'"]',
                        f.read(), re.MULTILINE).group(1)

setup(
    name='happy-bittorrent',
    version=version,
    url='https://github.com/Pewpews/happy-bittorrent',
    license='MIT',
    author='Pewpews',
    author_email='pew@pewpew.com',
    description="Simple BitTorrent client built with Python's asyncio for use in HPX",
    packages=find_packages(),
    zip_safe=False,
    include_package_data=True,
    platforms='any',
    install_requires=[
        'aiohttp>=2.0.7',
        'bencodepy>=0.9.5',
        'bitarray>=0.8.1'
    ],
    classifiers=[
        'Environment :: Console',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 3 :: Only'
        'Programming Language :: Python :: 3.5',
        'Topic :: Software Development :: Libraries :: Python Modules'
    ]
)