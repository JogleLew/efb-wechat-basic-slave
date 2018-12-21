import sys
from setuptools import setup, find_packages

if sys.version_info < (3, 6):
    raise Exception("Python 3.6 or higher is required. Your version is %s." % sys.version)

__version__ = ""
exec(open('efb_wechat_basic_slave/__version__.py').read())

long_description = open('README.rst').read()

setup(
    name='efb-wechat-basic-slave',
    packages=find_packages(exclude=["*.tests", "*.tests.*", "tests.*", "tests"]),
    version=__version__,
    description='WeChat Slave Channel for EH Forwarder Bot, working with WeChat macOS Hook.',
    long_description=long_description,
    include_package_data=True,
    author='JogleLew',
    author_email='jogle@jogle.top',
    url='https://github.com/JogleLew/efb-wechat-basic-slave',
    license='GPLv3',
    python_requires='>=3.6',
    keywords=['ehforwarderbot', 'EH Forwarder Bot', 'EH Forwarder Bot Slave Channel',
              'wechat', 'chatbot'],
    classifiers=[
        "Development Status :: 3 - Alpha",
        "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
        "Intended Audience :: Developers",
        "Intended Audience :: End Users/Desktop",
        "Programming Language :: Python :: 3 :: Only",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Topic :: Communications :: Chat",
        "Topic :: Utilities"
    ],
    install_requires=[
        "ehforwarderbot",
        "PyYaml",
        'requests',
        'python-magic', 
        'Pillow'
    ],
    entry_points={
        'ehforwarderbot.slave': 'jogle.wechat = efb_wechat_basic_slave:WechatMessengerChannel'
    }
)
