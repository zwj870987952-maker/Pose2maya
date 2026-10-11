import maya.cmds as cmds
import json

def check_modified():
    mod = cmds.file(q=True, modified=True)
    print("SCENE_MODIFIED:" + json.dumps({'modified': mod}))

if __name__ == '__main__':
    check_modified()
