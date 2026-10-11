import maya.cmds as cmds
import json

def check_namespaces():
    namespaces = cmds.namespaceInfo(listOnlyNamespaces=True, recurse=True)
    all_roots = cmds.ls(assemblies=True)
    print("NAMESPACES:" + json.dumps({
        'namespaces': namespaces,
        'assemblies': all_roots
    }))

if __name__ == '__main__':
    check_namespaces()
