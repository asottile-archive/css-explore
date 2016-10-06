from setuptools import find_packages
from setuptools import setup

setup(
    name='css_explore',
    description='Visualizations of a css parse tree',
    url='https://github.com/asottile/css-explore',
    version='0.0.7',
    author='Anthony Sottile',
    author_email='asottile@umich.edu',
    classifiers=[
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: Implementation :: CPython',
        'Programming Language :: Python :: Implementation :: PyPy',
    ],
    packages=find_packages('.', exclude=('tests*', 'testing*')),
    package_data={
        'css_explore': [
            'resources/css_to_json.js',
        ],
    },
    install_requires=[
        'nodeenv',
        'six',
    ],
    entry_points={
        'console_scripts': [
            'css-format = css_explore.main:main',
        ],
    },
)
