from os import path
from setuptools import setup, find_packages


base_dir = path.dirname(__file__)
with open(path.join(base_dir, 'README.rst')) as f:
    long_description = f.read()


with open('requirements.txt') as f:
    requires = f.read().splitlines()
    print(requires)


extras_require = dict(
     dev=['wheel', 'logjson', 'alembic', 'bumpversion'],
     test=['pytest', 'pytest-cov', 'pytest-asyncio', 'dockerctx',
           'portpicker', 'alembic'],
     doc=['sphinx', 'sphinxcontrib-fulltoc', 'sphinxcontrib-websupport']
)

extras_require['all'] = list(
    set(pkg for pkgs in extras_require.values() for pkg in pkgs)
)

setup(
    name='venus-bug-trap',
    version=open(path.join(base_dir, 'VERSION')).read().strip(),
    description='Centralised logging service',
    long_description=long_description,
    url='https://github.com/cjrh/venus',
    author='Caleb Hattingh',
    author_email='caleb.hattingh@gmail.com',
    classifiers=[
        'Intended Audience :: Developers',
        'License :: OSI Approved :: Apache Software License',
        'Topic :: System :: Logging',
        'Programming Language :: Python',
    ],
    packages=find_packages(exclude=['docs', 'tests*']),
    install_requires=requires,
    extras_require=extras_require,
    python_requires='>=3.7',
    entry_points={
        'console_scripts': [
            'venus = venus.main:main',
        ]
    }
)
