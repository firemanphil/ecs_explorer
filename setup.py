from setuptools import setup
setup(
    name = 'ecs_explorer',
    packages = ['ecs_explorer'], # this must be the same as the name above
    version = '0.4',
    description = 'CLI for exploring AWS ECS resources',
    author = 'Philip Ince',
    author_email = 'fireman.phil@gmail.com',
    url = 'https://github.com/firemanphil/ecs_explorer', # use the URL to the github repo
    download_url = 'https://github.com/firemanphil/ecs_explorer/archive/0.4.tar.gz', # I'll explain this in a second
    keywords = ['AWS', 'ECS', 'urwid', 'ncurses', 'cli'], # arbitrary keywords
    install_requires = ['boto3>=1.4.4', 'urwid>=1.3.1'],
    classifiers = [],
    entry_points = {
        'console_scripts': [
            'ecs_explorer=ecs_explorer.ecs_explorer:__main__',
        ],
    }
)
