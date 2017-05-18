#!/bin/sh
osascript <<EOF
tell application "iTerm" to activate
tell application "System Events" to tell process "iTerm" to keystroke "d" using command down
tell application "System Events" to tell process "iTerm" to keystroke "ssh $1"
tell application "System Events" to tell process "iTerm" to key code 52
EOF
