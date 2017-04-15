from distutils.core import setup
setup(
  name = 'ecs-explorer',
  packages = ['ecs-explorer'], # this must be the same as the name above
  version = '0.1',
  description = 'CLI for exploring AWS ECS resources',
  author = 'Philip Ince',
  author_email = 'fireman.phil@gmail.com',
  url = 'https://github.com/firemanphil/ecs_explorer', # use the URL to the github repo
  download_url = 'https://github.com/firemanphil/ecs_explorer/archive/0.1.tar.gz', # I'll explain this in a second
  keywords = ['AWS', 'ECS', 'urwid', 'ncurses', 'cli'], # arbitrary keywords
  classifiers = [],
)
